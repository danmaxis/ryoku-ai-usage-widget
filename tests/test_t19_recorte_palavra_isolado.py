# -*- coding: utf-8 -*-
"""Testes de comportamento de T19 — erro legível, sem corte cego no meio da palavra.

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada 2,
tarefa T19. Contrato transcrito (itens 1–4 do bloco assinado):

  1. Nenhum ``slice(0, N)`` cego em texto visível. O truncamento visual é do
     ``elide: Text.ElideRight`` do próprio ``Text``.
  2. Função PURA de corte por limite de palavra, ``truncarNaPalavra(texto, limite)``:
     entrada vazia/``null``/``undefined`` → ``""``; texto mais curto que o limite →
     inalterado, sem reticências; texto longo → corta no último espaço antes do
     limite, apara as pontas, acrescenta ``…`` (U+2026); palavra única maior que o
     limite → corta no limite, sem laço e sem devolver vazio; limite ≤ 0 → ``""``.
  3. A altura do popout não pode crescer (nada de ``wrapMode``).
  4. O ``NO DATA ·`` da view também passa pela elisão, sem corte cego do
     ``lastError``.

Como o comportamento é observado sem host visual
------------------------------------------------
``quickshell`` OFFLINE (``QT_QPA_PLATFORM=offscreen``), dois canais:

* **Função pura** (``tests/qml/t19_funcao_pura_harness.qml``) — monta a view e
  CHAMA a função com as entradas escolhidas aqui, despejando o resultado bruto
  (``typeof`` + ``JSON.stringify``). É o que o critério de done pede: a função
  exercitada diretamente, não só o texto que aparece na tela. O resultado é
  julgado contra o CONTRATO, nunca contra uma cópia do corpo da função.
* **Renderização** (``tests/qml/t19_erro_render_harness.qml``) — monta
  ``service/Main.qml`` + ``content/Widget.qml`` de verdade e substitui o
  ``ai-usagebar`` do PATH por um FAKE que emite um relatório de fixture. Assim a
  linha de erro do provider e a linha ``NO DATA ·`` são observadas pelo caminho
  real (coletor → relatório → view), sem depender do upstream.

Por que a função pura é testada por PROPRIEDADE, e não por string exata
-----------------------------------------------------------------------
O oráculo é a intenção do contrato, não um literal: onde o contrato diz "algo
como", o teste exige a PROPRIEDADE (não parte palavra, é prefixo do original,
não passa do limite, não fica vazio). Onde o contrato é literal (``""``,
"inalterado", ``…``), o teste é literal. Ver ``AMBIGUIDADES`` no fim.

Sobre o corte na tela: a view aplica ``AllUppercase`` ao erro
-------------------------------------------------------------
O texto de erro chega ao ``Text`` em CAIXA ALTA (medido, não lido no fonte), de
modo que toda comparação com a mensagem original é feita sem diferenciar caixa.
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Localização dos artefatos (o conteúdo de Widget.qml nunca é lido)
# --------------------------------------------------------------------------- #

TEST_DIR = Path(__file__).resolve().parent          # <repo>/ai-usage/tests
#: Override por ambiente: uso EXCLUSIVO da verificação de falsificabilidade
#: desta própria suíte (apontar para uma árvore de controle e conferir que os
#: testes de contrato passam a verde). O caminho de produção não o define.
PLUGIN_DIR = Path(os.environ.get("T19_PLUGIN_DIR", TEST_DIR.parent))  # <repo>/ai-usage
HARNESS_FN = TEST_DIR / "qml" / "t19_funcao_pura_harness.qml"
HARNESS_RENDER = TEST_DIR / "qml" / "t19_erro_render_harness.qml"

_QUICK = shutil.which("quickshell") or shutil.which("qs")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

pytestmark = pytest.mark.skipif(
    _QUICK is None,
    reason="quickshell ausente: a view QML e a função pura não podem ser exercitadas",
)

#: Reticências do contrato: UM caractere U+2026 (não três pontos).
RETICENCIAS = "\u2026"

#: Mensagem real do `kiro` medida em 2026-10-27 (102 caracteres). Usada como
#: MATERIAL do teste — nunca como oráculo de string: o relatório muda, a
#: propriedade "não parte palavra" não.
KIRO_ERRO = (
    "credentials error: no Kiro CLI `kirocli:odic:token` entry found. "
    "Run `kiro-cli login`, then try again."
)

#: Token que identifica a linha de erro injetada na árvore montada, sem casar
#: com o nome do provider ("Kiro") nem com o rótulo da seção.
KIRO_TOKEN = "odic:token"


# --------------------------------------------------------------------------- #
# Artefatos
# --------------------------------------------------------------------------- #


def _artefatos() -> None:
    assert HARNESS_FN.is_file(), f"harness QML ausente: {HARNESS_FN}"
    assert HARNESS_RENDER.is_file(), f"harness QML ausente: {HARNESS_RENDER}"
    assert (PLUGIN_DIR / "content" / "Widget.qml").is_file(), "content/Widget.qml ausente"
    assert (PLUGIN_DIR / "service" / "Main.qml").is_file(), "service/Main.qml ausente"


def test_artefatos_sob_teste_existem():
    """Falha rápida se a view/entrada sumiram (revert-and-test não pode virar SKIP)."""
    _artefatos()


# --------------------------------------------------------------------------- #
# Canal 1 — a função PURA
# --------------------------------------------------------------------------- #


def _limpo(stdout: str) -> list[str]:
    """Linhas de log do quickshell, sem escapes ANSI e sem o prefixo `qml:`."""
    saida: list[str] = []
    for linha in _ANSI.sub("", stdout).splitlines():
        if " qml: " in linha:
            linha = linha.split(" qml: ", 1)[1]
        linha = linha.strip()
        if linha:
            saida.append(linha)
    return saida


class ResultadoFn:
    """Um caso da função pura: o que ela devolveu, sem interpretação."""

    def __init__(self, nome: str, tipo: str, bruto: str):
        self.nome = nome
        self.tipo = tipo
        self.bruto = bruto

    @property
    def texto(self) -> str:
        valor = json.loads(self.bruto)
        assert isinstance(valor, str), (
            f"[{self.nome}] a função deve devolver string; devolveu {self.tipo} {self.bruto!r}"
        )
        return valor

    def __repr__(self) -> str:
        return f"<ResultadoFn {self.nome}: {self.bruto}>"


class BancadaFn:
    def __init__(self, registros: list[str]):
        self.registros = registros
        self.nome_fn = None
        self.host = None
        self.candidatos: dict[str, bool] = {}
        self.casos: dict[str, ResultadoFn] = {}
        self.excecoes: dict[str, str] = {}
        for r in registros:
            if r.startswith("FN_NAME|"):
                _tag, self.nome_fn, _estado = r.split("|", 2)
            elif r.startswith("FN_CAND|"):
                _tag, cand, presente = r.split("|", 2)
                self.candidatos[cand] = presente == "true"
            elif r.startswith("FN_HOST|"):
                self.host = r.split("|", 1)[1]
            elif r.startswith("FN_THROW|"):
                _tag, nome, msg = r.split("|", 2)
                self.excecoes[nome] = msg
            elif r.startswith("FN|"):
                _tag, nome, tipo, bruto = r.split("|", 3)
                self.casos[nome] = ResultadoFn(nome, tipo, bruto)
        self.view_present = any(r == "VIEW_PRESENT|true" for r in registros)
        self.terminou = any(r.startswith("END|") for r in registros)

    def __call__(self, nome: str) -> str:
        assert nome not in self.excecoes, (
            f"[{nome}] a função lançou exceção: {self.excecoes[nome]!r}"
        )
        assert nome in self.casos, (
            f"[{nome}] caso não executado; registros={self.registros}"
        )
        return self.casos[nome].texto

    def __repr__(self) -> str:
        return f"<BancadaFn fn={self.nome_fn!r} host={self.host!r} casos={sorted(self.casos)}>"


def _rodar_fn(casos: list[dict], tmp: Path) -> BancadaFn:
    """Um processo quickshell offline; chama a função para todos os casos."""
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("WAYLAND_DISPLAY", None)
    env["T19_PLUG_DIR"] = str(PLUGIN_DIR)
    env["T19_STATE_DIR"] = str(tmp / "state")
    env["T19_FN_CASES"] = json.dumps(casos, ensure_ascii=False)
    env["T19_SETTLE_MS"] = "1200"

    try:
        proc = subprocess.run(
            [_QUICK, "-p", str(HARNESS_FN)],
            capture_output=True, text=True, env=env, timeout=120,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            "o harness da função pura não terminou em 120s — possível laço infinito "
            "no corte por palavra (caso 4 do contrato) ou view que não monta."
        )

    bancada = BancadaFn(_limpo(proc.stdout + proc.stderr))
    assert bancada.terminou, (
        f"o harness não chegou ao fim; rc={proc.returncode}\n"
        f"registros={bancada.registros}\nstderr(tail)={proc.stderr[-800:]}"
    )
    return bancada


#: Corpus da função pura. Cada entrada é (nome, texto, limite).
#: Os nomes são estáveis: as asserções os citam.
CASOS_FN: list[tuple[str, object, object]] = [
    # -- caso 1: vazio / null / undefined -------------------------------- #
    ("vazio", "", 20),
    ("null", {"$null": True}, 20),
    ("undef", {"$undef": True}, 20),
    # -- caso 2: cabe no limite, volta inalterado ------------------------ #
    ("cabe-longo", "alpha beta", 20),
    ("cabe-curto", "abc", 20),
    ("cabe-uma-palavra", "abcdef", 10),
    # -- caso 3: texto longo, corte no espaço antes do limite ------------ #
    ("longo-20", "alpha beta gamma delta", 20),
    ("longo-12", "alpha beta gamma delta", 12),
    ("longo-7", "alpha  beta gamma", 7),
    ("longo-acentos", "ação rápida coração índio", 12),
    # -- caso 4: palavra única maior que o limite ------------------------ #
    ("unica-10", "abcdefghijklmnop", 10),
    ("unica-5", "abcdefghijklmnop", 5),
    ("unica-gigante", "a" * 4000, 10),
    # -- caso 5: limite <= 0 --------------------------------------------- #
    ("limite-zero", "alpha beta", 0),
    ("limite-negativo", "alpha beta", -5),
    ("limite-zero-vazio", "", 0),
    # -- limite sem fronteira antes do limite ---------------------------- #
    ("sem-fronteira", "alpha beta gamma", 2),
    ("sem-fronteira-1", "alpha beta gamma", 1),
]


def _casos_para_json() -> list[dict]:
    return [{"name": nome, "args": [texto, limite]} for nome, texto, limite in CASOS_FN]


#: Textos do corpus que o contrato manda cortar em fronteira de palavra.
LONGOS_COM_FRONTEIRA = ["longo-20", "longo-12", "longo-7", "longo-acentos"]

#: Textos do corpus em que NÃO há fronteira de palavra antes do limite.
SEM_FRONTEIRA = ["sem-fronteira", "sem-fronteira-1"]


@pytest.fixture(scope="module")
def fn(tmp_path_factory) -> BancadaFn:
    _artefatos()
    tmp = tmp_path_factory.mktemp("t19-fn")
    return _rodar_fn(_casos_para_json(), tmp)


def test_funcao_pura_de_corte_por_palavra_existe_e_e_alcancavel(fn):
    """Item 2: a função existe e é alcançável a partir da view montada.

    Sem esta âncora, todo o resto da suíte falharia por atributo ausente e o
    diagnóstico seria "NoneType não é chamável" em vez de "não há função pura
    de corte por palavra" — o defeito que a tarefa pede para eliminar.
    """
    assert fn.view_present, "a view não montou; nada a exercitar"
    assert fn.nome_fn and fn.nome_fn != "<absent>", (
        "não há função pura de corte por limite de palavra alcançável na view "
        f"montada; candidatos sondados={fn.candidatos}. O contrato a exige com a "
        "assinatura truncarNaPalavra(texto, limite)."
    )
    # A assinatura do contrato: dois parâmetros, string na saída. O nome é
    # relatado (FN_HOST/FN_NAME) para que o relatório diga o real.
    assert fn("longo-20"), (
        f"a função {fn.nome_fn!r} devolveu vazio para texto longo; contrato item 3"
    )


def test_entrada_vazia_null_ou_undefined_devolvem_string_vazia(fn):
    """Caso 1, literal: vazio, ``null`` e ``undefined`` → ``""``."""
    for nome in ("vazio", "null", "undef"):
        assert fn(nome) == "", (
            f"contrato item 2/1: entrada {nome!r} deve devolver a string vazia; "
            f"devolveu {fn(nome)!r}"
        )


def test_texto_que_cabe_no_limite_volta_inalterado_e_sem_reticencias(fn):
    """Caso 2: mais curto que o limite → idêntico, sem ``…``.

    Caso NEGATIVO embutido: nada de reticências num texto que já cabe. Sem essa
    metade, uma implementação que sempre acrescenta ``…`` passaria no teste de
    "devolveu o texto".
    """
    for nome, original in (("cabe-longo", "alpha beta"), ("cabe-curto", "abc"),
                           ("cabe-uma-palavra", "abcdef")):
        obtido = fn(nome)
        assert RETICENCIAS not in obtido, (
            f"contrato item 2/2: {nome} já cabe no limite e não pode ganhar "
            f"reticências; devolveu {obtido!r}"
        )
        assert obtido == original, (
            f"contrato item 2/2: {nome} deve voltar INALTERADO; "
            f"devolveu {obtido!r}, esperado {original!r}"
        )


def test_texto_longo_corta_antes_do_limite_com_reticencias(fn):
    """Caso 3: corta, apara as pontas e sinaliza com ``…`` (U+2026)."""
    obtido = fn("longo-20")
    assert obtido.endswith(RETICENCIAS), (
        f"contrato item 2/3: texto cortado precisa terminar em reticências "
        f"(U+2026); devolveu {obtido!r}"
    )
    miolo = obtido[: -len(RETICENCIAS)]
    assert miolo == miolo.rstrip(), (
        f"contrato item 2/3: o texto não pode terminar com espaço antes das "
        f"reticências; devolveu {obtido!r}"
    )
    assert "alpha beta gamma delta".startswith(miolo), (
        f"contrato item 6: o miolo tem de ser prefixo do original; "
        f"miolo={miolo!r}, original={'alpha beta gamma delta'!r}"
    )


def test_palavra_unica_maior_que_o_limite_corta_no_limite_e_nunca_fica_vazia(fn):
    """Caso 4: sem espaço algum, corta no limite — e não devolve ``""``.

    Este é o caso em que uma implementação ingênua ("recuar até o último espaço")
    devolve vazio ou entra em laço; o contrato o nomeia explicitamente.
    """
    for nome, limite, original in (("unica-10", 10, "abcdefghijklmnop"),
                                   ("unica-5", 5, "abcdefghijklmnop")):
        obtido = fn(nome)
        assert obtido != "", (
            f"contrato item 2/4: palavra única maior que o limite ({nome}) não "
            "pode devolver string vazia"
        )
        esperado = original[:limite]
        assert obtido.startswith(esperado), (
            f"contrato item 2/4: {nome} deve começar pelos primeiros {limite} "
            f"caracteres ({esperado!r}); devolveu {obtido!r}"
        )


def test_palavra_unica_gigante_nao_entra_em_laco(fn):
    """Caso 4, anti-laço: 4000 caracteres sem espaço, limite 10.

    A ausência de laço é observada pelo PROCESSO que termina (um laço infinito
    estoura o timeout do harness e vira falha explícita em ``_rodar_fn``) e pelo
    resultado ser curto e não-vazio.
    """
    obtido = fn("unica-gigante")
    assert obtido != "", "contrato item 2/4: palavra gigante não pode virar vazio"
    miolo = obtido[: -len(RETICENCIAS)] if obtido.endswith(RETICENCIAS) else obtido
    assert len(miolo) <= 10, (
        f"contrato item 2/4: com limite 10 o corte da palavra única não pode "
        f"passar de 10 caracteres; devolveu {len(miolo)} ({miolo[:40]!r}...)"
    )
    assert set(miolo) <= {"a"}, (
        f"o corte inventou caracteres que não existem no original: {miolo[:40]!r}"
    )


def test_limite_zero_ou_negativo_devolve_vazio(fn):
    """Caso 5, literal: limite ≤ 0 → ``""``."""
    for nome in ("limite-zero", "limite-negativo", "limite-zero-vazio"):
        assert fn(nome) == "", (
            f"contrato item 2/5: limite não-positivo ({nome}) deve devolver a "
            f"string vazia; devolveu {fn(nome)!r}"
        )


def test_resultado_nunca_parte_uma_palavra_que_existia_no_original(fn):
    """Item 6 — a invariante central, exercitada em TODO texto com fronteira.

    Para cada resultado, o texto antes das reticências tem de ser prefixo do
    original E terminar em fim-de-palavra (o caractere seguinte no original é
    espaço). É a propriedade que o defeito medido violava: ``entry`` virava
    ``entr`` na tela.
    """
    originais = {
        "longo-20": "alpha beta gamma delta",
        "longo-12": "alpha beta gamma delta",
        "longo-7": "alpha  beta gamma",
        "longo-acentos": "ação rápida coração índio",
    }
    for nome in LONGOS_COM_FRONTEIRA:
        original = originais[nome]
        obtido = fn(nome)
        assert obtido.endswith(RETICENCIAS), (
            f"[{nome}] era esperado corte com reticências; devolveu {obtido!r}"
        )
        miolo = obtido[: -len(RETICENCIAS)].rstrip()
        assert miolo and original.startswith(miolo), (
            f"[{nome}] contrato item 6: o miolo tem de ser prefixo não-vazio do "
            f"original; miolo={miolo!r}, original={original!r}"
        )
        resto = original[len(miolo):]
        palavra = resto.split()[0] if resto.split() else ""
        assert resto == "" or resto[0].isspace(), (
            f"[{nome}] contrato item 6: o corte partiu a palavra "
            f"{miolo[-10:] + palavra!r}; o texto termina no meio dela. "
            f"renderizado={obtido!r}, original={original!r}"
        )


def test_com_limite_sem_fronteira_de_palavra_corta_no_proprio_limite(fn):
    """Item 6, exceção: quando nenhum espaço cabe antes do limite, corta no limite.

    Sem esta exceção a invariante "nunca parte palavra" seria impossível de
    cumprir para ``limite`` menor que a primeira palavra — e o contrato a admite
    (caso 4 é a mesma situação sem espaço algum).
    """
    for nome, limite in (("sem-fronteira", 2), ("sem-fronteira-1", 1)):
        original = "alpha beta gamma"
        obtido = fn(nome)
        assert obtido != "", f"[{nome}] o corte não pode devolver vazio"
        assert obtido.startswith(original[:limite]), (
            f"[{nome}] contrato item 6 (exceção): sem fronteira antes do limite, "
            f"o corte é no limite ({original[:limite]!r}); devolveu {obtido!r}"
        )


# -- a mesma invariante, agora varrida por PROPRIEDADE --------------------- #

_PALAVRAS = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta",
             "theta", "iota", "kappa", "lambda", "sigma"]


def _corpus_sorteado() -> list[tuple[str, str, int]]:
    """40 textos determinísticos (semente fixa), cobrindo limite de 1 a 50."""
    rnd = random.Random(19)
    casos: list[tuple[str, str, int]] = []
    for i in range(40):
        n = rnd.randint(1, 12)
        texto = " ".join(rnd.choice(_PALAVRAS) for _ in range(n))
        limite = rnd.randint(1, 50)
        casos.append((f"varredura-{i:02d}", texto, limite))
    return casos


@pytest.fixture(scope="module")
def varredura(tmp_path_factory) -> BancadaFn:
    _artefatos()
    tmp = tmp_path_factory.mktemp("t19-varredura")
    casos = [{"name": n, "args": [t, lim]} for n, t, lim in _corpus_sorteado()]
    return _rodar_fn(casos, tmp)


def test_varredura_de_textos_e_limites_respeita_o_contrato(varredura):
    """Propriedade sobre 40 entradas: nenhuma parte palavra, nenhuma inventa texto.

    O oráculo é o contrato, não uma tabela de saídas esperadas: para cada par
    (texto, limite) o teste deriva a expectativa de três regras —
    (a) cabe no limite → inalterado;
    (b) há espaço dentro do limite → o miolo é prefixo do original e termina em
        fim-de-palavra;
    (c) não há espaço dentro do limite → o resultado começa pelos primeiros
        ``limite`` caracteres.
    """
    falhas: list[str] = []
    for nome, texto, limite in _corpus_sorteado():
        obtido = varredura(nome)
        prefixo = texto[:limite]

        if len(texto) <= limite:
            if obtido != texto:
                falhas.append(
                    f"[{nome}] len={len(texto)} <= limite={limite}: deveria voltar "
                    f"inalterado; veio {obtido!r}"
                )
            continue

        if obtido == "":
            falhas.append(f"[{nome}] devolveu vazio para {texto!r} com limite {limite}")
            continue

        if " " in prefixo:
            miolo = obtido[: -len(RETICENCIAS)] if obtido.endswith(RETICENCIAS) else obtido
            miolo = miolo.rstrip()
            if not miolo or not texto.startswith(miolo):
                falhas.append(
                    f"[{nome}] limite={limite}: miolo {miolo!r} não é prefixo de {texto!r}"
                )
            elif len(miolo) > limite:
                falhas.append(
                    f"[{nome}] limite={limite}: miolo {miolo!r} excede o limite"
                )
            else:
                resto = texto[len(miolo):]
                if resto and not resto[0].isspace():
                    falhas.append(
                        f"[{nome}] limite={limite}: corte partiu a palavra "
                        f"{miolo[-10:]!r}+{resto.split()[0][:10]!r} em {texto!r}"
                    )
            if not obtido.endswith(RETICENCIAS):
                falhas.append(
                    f"[{nome}] limite={limite}: corte sem reticências finais ({obtido!r})"
                )
        else:
            if not obtido.startswith(prefixo):
                falhas.append(
                    f"[{nome}] limite={limite}: sem espaço antes do limite, esperado "
                    f"começar por {prefixo!r}; veio {obtido!r}"
                )

    assert not falhas, "violações do contrato na varredura:\n" + "\n".join(falhas)


def test_a_funcao_nao_e_identidade_nem_devolve_o_texto_inteiro_quando_corta(fn):
    """Caso NEGATIVO: cortar é cortar.

    Uma "correção" que apenas devolvesse o texto inteiro (ou que ignorasse o
    limite) passaria em vários testes de "não partiu palavra" — este a barra.
    """
    original = "alpha beta gamma delta"
    obtido = fn("longo-20")
    assert obtido != original, (
        f"com limite 20 e 22 caracteres, o texto tem de ser reduzido; "
        f"devolveu o original inteiro {obtido!r}"
    )
    miolo = obtido[: -len(RETICENCIAS)] if obtido.endswith(RETICENCIAS) else obtido
    assert len(miolo) <= 20, (
        f"o corte não pode passar do limite de 20 caracteres; miolo tem "
        f"{len(miolo)} ({miolo!r})"
    )


# --------------------------------------------------------------------------- #
# Canal 2 — o que a view RENDERIZA
# --------------------------------------------------------------------------- #


def _relatorio(erro: str) -> dict:
    """Relatório no formato do ``ai-usagebar``: um primário pronto + o kiro em erro.

    O provider em erro fica em SEGUNDO lugar de propósito: é ali que a view
    desenha a linha de diagnóstico do provider (a superfície do defeito medido).
    """
    return {
        "schema_version": 1,
        "primary": "anthropic",
        "entries": [
            {
                "id": "anthropic", "name": "anthropic", "display_name": "Sonnet",
                "short_name": "cld", "icon": "i", "brand": "anthropic",
                "plan": "Claude Pro", "status": "ready", "error": None,
                "stale": False, "fetched_at": "2026-10-15T14:43:32Z",
                "reset_credits": None,
                "metrics": [{
                    "label": "Session (5h)", "percent": 91, "value": "91%",
                    "headline": "percent", "severity": "critical",
                    "detail": "Resets in 1h 56m", "reset_at": None,
                    "window_secs": 18000,
                }],
                "sections": [],
            },
            {
                "id": "kiro", "name": "kiro", "display_name": "Kiro",
                "short_name": "kir", "icon": "i", "brand": "kiro", "plan": None,
                "status": "error", "error": erro, "stale": False,
                "fetched_at": None, "reset_credits": None, "metrics": [],
                "sections": [],
            },
        ],
    }


class TextObj:
    """Um ``Text`` da árvore montada, com a geometria que o Qt realmente mediu."""

    def __init__(self, bruto: str):
        self.dados = json.loads(bruto)
        self.texto = self.dados.get("text", "")
        self.width = self.dados.get("width", 0)
        self.height = self.dados.get("height", 0)
        self.implicit_width = self.dados.get("implicitWidth", 0)
        self.implicit_height = self.dados.get("implicitHeight", 0)
        self.line_count = self.dados.get("lineCount", -1)
        self.wrap_mode = self.dados.get("wrapMode", -1)
        self.elide = self.dados.get("elide", -1)
        self.pixel_size = self.dados.get("pixelSize", -1)
        self.truncated = self.dados.get("truncated")

    def __repr__(self) -> str:
        return f"<TextObj px={self.pixel_size} {self.texto[:70]!r}>"


class Render:
    def __init__(self, registros: list[str]):
        self.registros = registros
        self.textos = [TextObj(r.split("|", 1)[1]) for r in registros if r.startswith("TEXTOBJ|")]
        self.view_present = any(r == "VIEW_PRESENT|true" for r in registros)
        self.erros = [r for r in registros if r.startswith("VIEW_ERR|")]
        self.terminou = any(r.startswith("END|") for r in registros)
        self.root_h = None
        self.root_implicit_h = None
        for r in registros:
            if r.startswith("ROOT_H|"):
                partes = r.split("|")
                try:
                    self.root_h = float(partes[1])
                    self.root_implicit_h = float(partes[2])
                except (IndexError, ValueError):
                    pass

    def contendo(self, agulha: str) -> list[TextObj]:
        a = agulha.lower()
        return [t for t in self.textos if a in t.texto.lower()]

    def __repr__(self) -> str:
        return f"<Render h={self.root_h} textos={[t.texto[:40] for t in self.textos]}>"


def _rodar_render(relatorio: dict, tmp: Path, *, nome: str,
                  width: int = 260) -> Render:
    """Um processo quickshell offline, com o FAKE `ai-usagebar` no PATH."""
    pasta = tmp / f"fakebin-{nome}"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = tmp / f"relatorio-{nome}.json"
    arquivo.write_text(json.dumps(relatorio, ensure_ascii=False), encoding="utf-8")
    falso = pasta / "ai-usagebar"
    falso.write_text(f"#!/bin/sh\nexec /bin/cat {arquivo}\n", encoding="utf-8")
    falso.chmod(0o755)

    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("WAYLAND_DISPLAY", None)
    env["PATH"] = f"{pasta}{os.pathsep}{env.get('PATH', '')}"
    env["HOME"] = str(tmp / f"home-{nome}")
    env["XDG_CACHE_HOME"] = str(tmp / f"cache-{nome}")
    env["XDG_CONFIG_HOME"] = str(tmp / f"cfg-{nome}")
    env["T19R_PLUG_DIR"] = str(PLUGIN_DIR)
    env["T19R_STATE_DIR"] = str(tmp / f"state-{nome}")
    env["T19R_WIDTH"] = str(width)
    env["T19R_SETTLE_MS"] = "3500"

    try:
        proc = subprocess.run(
            [_QUICK, "-p", str(HARNESS_RENDER)],
            capture_output=True, text=True, env=env, timeout=120,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"[{nome}] o harness de renderização não terminou em 120s")

    registros = _limpo(proc.stdout + proc.stderr)
    render = Render(registros)
    assert render.terminou, (
        f"[{nome}] o harness não chegou ao fim; rc={proc.returncode}\n"
        f"registros={registros}\nstderr(tail)={proc.stderr[-800:]}"
    )
    return render


def _parte_palavra(renderizado: str, original: str) -> str | None:
    """Devolve a palavra partida, se o texto renderizado cortou uma ao meio.

    A comparação é sem caixa porque a view aplica ``AllUppercase`` ao erro. Um
    resultado que seja o original inteiro, ou um prefixo terminando em espaço
    (ou em fim-de-palavra após apara de reticências), está correto.
    """
    r = renderizado.strip()
    for marca in (RETICENCIAS, "..."):
        if r.endswith(marca):
            r = r[: -len(marca)].rstrip()
            break
    r_norm = r.upper()
    o_norm = original.strip().upper()
    if not r_norm or r_norm == o_norm:
        return None
    if not o_norm.startswith(r_norm):
        return None                    # não é prefixo: outra asserção cobre
    resto = o_norm[len(r_norm):]
    if resto and not r_norm[-1:].isspace() and not resto[0].isspace():
        partida = resto.split()[0] if resto.split() else ""
        return f"{r_norm[-12:]!r} + {resto[0]}... (palavra {r_norm[-6:]}{partida} partida)"
    return None


@pytest.fixture(scope="module")
def render_erro_longo(tmp_path_factory) -> Render:
    _artefatos()
    tmp = tmp_path_factory.mktemp("t19-render-longo")
    return _rodar_render(_relatorio(KIRO_ERRO), tmp, nome="kiro")


@pytest.fixture(scope="module")
def render_erro_curto(tmp_path_factory) -> Render:
    _artefatos()
    tmp = tmp_path_factory.mktemp("t19-render-curto")
    return _rodar_render(_relatorio("boom"), tmp, nome="curto")


def test_view_desenha_a_linha_de_erro_do_provider(render_erro_longo):
    """Âncora: sem a linha na árvore, as asserções seguintes seriam vacuamente
    verdadeiras (uma tela em branco "não parte palavra" nenhuma)."""
    assert render_erro_longo.view_present, "a view não montou"
    alvos = render_erro_longo.contendo(KIRO_TOKEN)
    assert alvos, (
        f"a linha de erro do provider não chegou à árvore montada; "
        f"textos={[t.texto for t in render_erro_longo.textos]}"
    )


def test_erro_do_provider_nao_parte_palavra_na_tela(render_erro_longo):
    """O defeito MEDIDO: "…odic:token` entr" com a palavra "entry" partida.

    Não se exige o texto exato do erro do kiro (o relatório muda): exige-se a
    propriedade — o que está na tela é o original inteiro, ou um prefixo que
    termina em fim-de-palavra.
    """
    alvos = render_erro_longo.contendo(KIRO_TOKEN)
    assert alvos, "a linha de erro do provider não foi renderizada"
    for t in alvos:
        partida = _parte_palavra(t.texto, KIRO_ERRO)
        assert partida is None, (
            "o texto de erro do provider aparece partido no meio da palavra: "
            f"{partida}\nrenderizado={t.texto!r}\noriginal={KIRO_ERRO!r}"
        )


def test_erro_do_provider_nao_passa_de_uma_linha_e_continua_elidido(render_erro_longo):
    """Item 3: a linha continua em UMA linha, com ``elide`` fazendo o corte visual.

    ``wrapMode`` diferente de ``NoWrap`` faria o popout crescer em altura; o
    ``elide`` precisa permanecer ligado, senão o texto longo seria cortado em
    seco pela borda do item (ilegível, sem reticências).
    """
    alvos = render_erro_longo.contendo(KIRO_TOKEN)
    assert alvos, "a linha de erro do provider não foi renderizada"
    for t in alvos:
        assert t.wrap_mode == 0, (   # Text.NoWrap
            f"o texto de erro não pode usar wrapMode ({t.wrap_mode}); "
            "isso faz o popout crescer"
        )
        assert t.line_count <= 1, (
            f"o texto de erro ocupou {t.line_count} linhas; o contrato exige uma"
        )
        assert t.elide != 0, (       # Text.ElideNone == 0
            "o texto de erro perdeu o elide: sem ele, um texto mais largo que o "
            "item é cortado em seco e sem reticências"
        )


def test_altura_do_popout_nao_cresce_com_um_erro_longo(render_erro_curto, render_erro_longo):
    """Item 3, medido: o MESMO popout com erro curto e com erro de 102 caracteres.

    Guarda de NÃO-REGRESSÃO (passa também na base ``4d5375e``): ela existe para
    que a correção do corte não seja obtida às custas de ``wrapMode`` — a troca
    mais tentadora, e a que a tarefa proíbe.
    """
    assert render_erro_curto.root_h is not None and render_erro_longo.root_h is not None, (
        "a geometria do nó raiz da view não foi observada"
    )
    assert render_erro_longo.root_h <= render_erro_curto.root_h, (
        "a altura do popout cresceu com um erro longo: "
        f"curto={render_erro_curto.root_h}, longo={render_erro_longo.root_h}"
    )


def test_linha_no_data_nao_parte_palavra(tmp_path_factory):
    """Item 4: o ``NO DATA · <lastError>`` também passa pela elisão, sem corte cego.

    Guarda de NÃO-REGRESSÃO: na base o ``NO DATA`` já não era fatiado; o teste
    impede que a correção do outro ``Text`` introduza ali um corte por caractere.
    O diagnóstico vem do próprio coletor, então o comprimento é o que ele emitir
    (aqui, uma mensagem longa e sintética, que é a que separa corte de elisão).
    """
    _artefatos()
    # Um `ai-usagebar` que falha com stderr longo: o serviço compõe o
    # diagnóstico e a view o exibe na linha "NO DATA ·".
    longa = " ".join(f"palavra{i:02d}" for i in range(1, 31))
    assert len(longa) > 56, "o material do teste precisa passar do limite antigo"

    tmp = tmp_path_factory.mktemp("t19-nodata")
    pasta = tmp / "fakebin-falha"
    pasta.mkdir(parents=True, exist_ok=True)
    falso = pasta / "ai-usagebar"
    falso.write_text(
        f"#!/bin/sh\nprintf '%s\\n' '{longa}' >&2\nexit 7\n", encoding="utf-8"
    )
    falso.chmod(0o755)

    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("WAYLAND_DISPLAY", None)
    env["PATH"] = f"{pasta}{os.pathsep}{env.get('PATH', '')}"
    env["HOME"] = str(tmp / "home")
    env["XDG_CACHE_HOME"] = str(tmp / "cache")
    env["XDG_CONFIG_HOME"] = str(tmp / "cfg")
    env["T19R_PLUG_DIR"] = str(PLUGIN_DIR)
    env["T19R_STATE_DIR"] = str(tmp / "state")
    env["T19R_SETTLE_MS"] = "3500"

    try:
        proc = subprocess.run(
            [_QUICK, "-p", str(HARNESS_RENDER)],
            capture_output=True, text=True, env=env, timeout=120,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("o harness de renderização não terminou em 120s")

    render = Render(_limpo(proc.stdout + proc.stderr))
    assert render.terminou, f"o harness não chegou ao fim; registros={render.registros}"

    alvos = [t for t in render.textos if "NO DATA" in t.texto.upper()]
    assert alvos, (
        "a linha 'NO DATA' não foi renderizada; "
        f"textos={[t.texto for t in render.textos]}"
    )
    for t in alvos:
        assert t.wrap_mode == 0, f"a linha 'NO DATA' não pode usar wrapMode ({t.wrap_mode})"
        assert t.line_count <= 1, f"a linha 'NO DATA' ocupou {t.line_count} linhas"


# --------------------------------------------------------------------------- #
# AMBIGUIDADES do contrato (resolvidas por PROPRIEDADE, não por invenção)
# --------------------------------------------------------------------------- #
AMBIGUIDADES = """
1. "corta no último espaço ANTES do limite" tem duas leituras quando o prefixo
   de comprimento ``limite`` TERMINA exatamente em espaço — p.ex. limite 10 com
   "alpha beta gamma": prefixo "alpha beta" (10) já é fronteira de palavra.
   Ler literalmente "último espaço antes do limite" dá "alpha…"; ler "maior
   prefixo em fronteira que caiba" dá "alpha beta…". Os testes usam apenas
   entradas em que as duas leituras CONCORDAM, e não fixam esse caso.

2. "texto mais curto que o limite" não cobre o caso de comprimento IGUAL ao
   limite. Não há asserção para igualdade; a varredura só exige "inalterado"
   quando ``len(texto) <= limite``… o que também assume a leitura "cabe"
   para igualdade. Se a implementação tratar igualdade como corte, apenas a
   varredura acusa — é o único ponto em que o teste assume uma leitura.

3. A função é descrita como "função num Item raiz do Widget.qml", mas nada
   impede que ela viva num ``QtObject`` interno. O harness procura primeiro no
   nó raiz e, se não achar, na árvore inteira, e REPORTA onde achou
   (``FN_HOST``). Não há asserção de que esteja no raiz.

4. O nome ``truncarNaPalavra`` é uma suposição do enunciado. O harness sonda
   nove grafias e relata a real; se for outra, todos os testes de função
   falham com a mensagem que lista os candidatos — ruidoso de propósito, para
   não passar em silêncio.

5. O tipo do parâmetro ``limite`` não é declarado (int? real?). O harness
   passa inteiros; nenhuma asserção depende de coerção numérica.
"""
