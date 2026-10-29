# -*- coding: utf-8 -*-
"""Testes de comportamento de T13 — `errorKind` no serviço e o texto na view.

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada 2,
tarefa T13. Contrato observável (itens 4–7 do bloco assinado):

  4. O serviço expõe ``errorKind``, string, com exatamente três valores:
     ``""`` (sem erro), ``"dep-missing"`` (rc exatamente 3) e ``"upstream"``
     (qualquer outro rc != 0 ou saída não-JSON). ``lastError`` continua com o
     texto do stderr como diagnóstico — ``errorKind`` discrimina, ``lastError``
     é a prosa.
  5. ``errorKind === "dep-missing"``: a view mostra texto em INGLÊS que
     (i) nomeia o ``ai-usagebar``, (ii) manda instalar com o comando
     ``paru -S ai-usagebar-bin``, e (iii) NÃO mostra o diagnóstico do coletor.
  6. ``errorKind === "upstream"``: preserva o comportamento atual — mostra o
     diagnóstico do upstream. Os dois casos não podem renderizar o MESMO texto.
  7. Sem erro e sem modelo: ``LOADING`` ENQUANTO a coleta está em curso;
     ``NO PROVIDERS`` quando ela já terminou sem nada (ver nota de T13-b).

Como a view é observada sem host visual
---------------------------------------
``quickshell`` em modo OFFLINE (``QT_QPA_PLATFORM=offscreen``) monta
``service/Main.qml`` + ``content/Widget.qml`` via
``tests/qml/t13_dep_missing_harness.qml``, que injeta um ``pluginApi``
sintético. O harness despeja (a) os campos públicos da instância principal e
(b) só o que foi RENDERIZADO (textos de nós visíveis). Nada de introspecção de
fonte: se o texto não chegou à árvore montada, ele não existe para o usuário.

Dois modos, de propósito:

* ``real`` — monta o ``Main.qml`` DE VERDADE e deixa o coletor rodar, com um
  PATH que contém ou não um ``ai-usagebar``. É o caminho de ponta a ponta
  (coletor -> rc -> errorKind -> view). Um processo por caso, porque o PATH é
  do processo.
* ``stub`` — injeta um ``mainInstance`` com ``errorKind``/``lastError``
  escolhidos. Isola a VIEW: prova que ela honra ``errorKind`` e não o texto, e
  permite alimentá-la com a frase do diagnóstico do coletor para provar que ela
  NÃO vaza nesse caso.

Sobre "the collector's diagnostic": a detecção NÃO é heurística de idioma. São
âncoras exatas, literais que o coletor emite hoje (medidas por execução, não por
leitura de fonte). Elas eram em português até T21 traduzir o coletor; o que se
afirma não é o idioma, e sim que o diagnóstico do coletor não vaza:

  * ``FAILED:``                      — prefixo de todo diagnóstico do coletor;
  * ``is not on PATH``               — frase do caso de ausência;
  * ``is not valid JSON``            — frase do caso de relatório malformado;
  * ``cannot read the report``       — frase do caso de arquivo inexistente.

Nota medida sobre a view atual: o texto de erro é ELIDIDO em ~70 caracteres.
Por isso as âncoras escolhidas são curtas e as frases injetadas no modo stub são
mais curtas que o limite de elisão — uma frase longa poderia "sumir" por
truncamento e o teste passaria por motivo errado (vacuidade geométrica).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Localização dos artefatos (nunca leio o conteúdo de Main.qml / Widget.qml)
# --------------------------------------------------------------------------- #

TEST_DIR = Path(__file__).resolve().parent          # <repo>/ai-usage/tests
#: Override por ambiente: uso EXCLUSIVO da verificação de falsificabilidade
#: desta própria suíte (apontar para uma árvore de controle e conferir que os
#: testes de contrato passam a verde). O caminho de produção não o define.
PLUGIN_DIR = Path(os.environ.get("T13_PLUGIN_DIR", TEST_DIR.parent))  # <repo>/ai-usage
REPO_ROOT = PLUGIN_DIR.parent                       # <repo>
HARNESS = TEST_DIR / "qml" / "t13_dep_missing_harness.qml"

#: O fixture é ancorado na posição DESTE arquivo, não em PLUGIN_DIR: com o
#: override de falsificabilidade (árvore de controle fora do repo) o fixture
#: precisa continuar achável.
_REPO_POR_TESTES = TEST_DIR.parent.parent

FIXTURE_CANDIDATES = (
    _REPO_POR_TESTES / "tests" / "fixtures" / "report-schema1.json",
    TEST_DIR / "fixtures" / "report-schema1.json",
)

_QUICK = shutil.which("quickshell") or shutil.which("qs")

#: quickshell pinta o log; o código de reset ANSI cai ANTES dos dois-pontos de
#: "qml:", então o prefixo só é reconhecível depois de remover os escapes.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

pytestmark = pytest.mark.skipif(
    _QUICK is None,
    reason="quickshell ausente: a view QML não pode ser exercitada",
)

#: EXACT anchors of the collector's diagnostic (measured by execution, not by
#: reading the source). They were Portuguese until T21 translated the collector;
#: the anchors are updated to English, and the PROPERTY they assert is unchanged:
#: the collector's diagnostic must not leak into the surface where the user has
#: their own actionable warning instead.
DIAG_PREFIX = "FAILED:"
DIAG_DEP_MISSING = "is not on PATH"
DIAG_BAD_JSON = "is not valid JSON"
DIAG_UNREADABLE = "cannot read the report"

#: Every rendered text carrying any of these anchors is the collector's diagnostic
#: leaking into the surface.
DIAG_ANCHORS = (DIAG_PREFIX, DIAG_DEP_MISSING, DIAG_BAD_JSON, DIAG_UNREADABLE)

#: Comando de instalação exigido (item 5).
INSTALL_CMD = "paru -S ai-usagebar-bin"

#: Nome que o aviso precisa carregar (item 5, "nomeia o que falta").
DEP_NAME = "ai-usagebar"

#: Marcador curto que o upstream falso escreve em stderr. Curto de propósito: a
#: view elide a ~70 caracteres e um marcador longo poderia desaparecer por
#: truncamento (o teste passaria/falharia pelo motivo errado).
UPSTREAM_MARKER = "T13UPSTREAM_MARKER"

_SETTINGS = {
    "accent": "wallpaper", "order": "upstream", "showMetricDetail": True,
    "secondaryLabel": "name", "showSecondaries": True, "maxSecondary": 6,
    "padding": 12, "gap": 6, "pollSeconds": 300,
}


def _fixture() -> Path:
    for cand in FIXTURE_CANDIDATES:
        if cand.is_file():
            return cand
    pytest.skip("fixture report-schema1.json não encontrada")


def _artefatos() -> None:
    assert HARNESS.is_file(), f"harness QML ausente: {HARNESS}"
    assert (PLUGIN_DIR / "content" / "Widget.qml").is_file(), "content/Widget.qml ausente"
    assert (PLUGIN_DIR / "service" / "Main.qml").is_file(), "service/Main.qml ausente"


def test_artefatos_sob_teste_existem():
    """Falha rápida se a view/entrada sumiram (revert-and-test não pode virar SKIP)."""
    _artefatos()


# --------------------------------------------------------------------------- #
# Bancada de observação
# --------------------------------------------------------------------------- #


class Dump:
    """Registros de um caso: campos da instância principal + textos renderizados."""

    def __init__(self, nome: str, registros: list[str]):
        self.nome = nome
        self.registros = registros
        self.textos = [r.split("|", 1)[1] for r in registros if r.startswith("TEXT|")]

        def campo(tag: str):
            for r in registros:
                if r.startswith(tag + "|"):
                    return r.split("|", 1)[1]
            return None

        self.main_present = campo("MAIN_PRESENT") == "true"
        self.error_kind = campo("MAIN_ERRORKIND")
        self.error_kind_type = campo("MAIN_ERRORKIND_TYPE")
        self.last_error = campo("MAIN_LASTERROR")
        self.loading = campo("MAIN_LOADING")
        self.model_null = campo("MAIN_MODEL_NULL")
        self.view_present = campo("VIEW_PRESENT") == "true"
        self.erros = [r for r in registros if r.startswith("VIEW_ERR|") or r.startswith("EMIT_ERR|")]
        self.ended = any(r.startswith("END|") for r in registros)

    # -- helpers de asserção sobre o que o usuário vê ----------------------- #

    def has(self, needle: str) -> bool:
        return any(needle in t for t in self.textos)

    def find(self, needle: str) -> list[str]:
        return [t for t in self.textos if needle in t]

    def textos_de_diagnostico(self) -> list[str]:
        """Texts carrying the collector's own diagnostic (prefix or phrase)."""
        return [t for t in self.textos if any(a in t for a in DIAG_ANCHORS)]

    def __repr__(self) -> str:
        return f"<Dump {self.nome}: kind={self.error_kind!r} textos={self.textos}>"


def _path_so_python(tmp: Path) -> Path:
    """Diretório de PATH com o interpretador e mais nada (sem ai-usagebar)."""
    d = tmp / "path-so-python"
    d.mkdir(parents=True, exist_ok=True)
    link = d / "python3"
    if not link.exists():
        link.symlink_to(Path(os.path.realpath(sys.executable)))
    return d


def _path_com_fake(tmp: Path, corpo: str) -> Path:
    """PATH cujo primeiro item tem um ``ai-usagebar`` falso com o corpo dado."""
    d = tmp / "path-com-fake"
    d.mkdir(parents=True, exist_ok=True)
    falso = d / "ai-usagebar"
    falso.write_text(corpo, encoding="utf-8")
    falso.chmod(0o755)
    return d


def _rodar_harness(nome: str, env: dict, tmp: Path) -> Dump:
    """Um processo quickshell offline por caso; devolve o dump parseado."""
    complet = dict(os.environ)
    complet.update(env)
    complet["QT_QPA_PLATFORM"] = "offscreen"
    complet.pop("WAYLAND_DISPLAY", None)
    complet["T13_PLUG_DIR"] = str(PLUGIN_DIR)
    complet["T13_STATE_DIR"] = str(tmp / "state")
    complet["T13_SETTINGS"] = json.dumps(_SETTINGS)

    try:
        proc = subprocess.run(
            [_QUICK, "-p", str(HARNESS)],
            capture_output=True, text=True, env=complet, timeout=120,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"[{nome}] o harness QML não terminou em 120s — a view ou o serviço "
            "provavelmente não monta."
        )

    bruto = _ANSI.sub("", proc.stdout + proc.stderr)
    registros: list[str] = []
    for linha in bruto.splitlines():
        if " qml: " in linha:
            linha = linha.split(" qml: ", 1)[1]
        linha = linha.strip()
        if not linha:
            continue
        if linha.startswith(("TEXT|", "MAIN_", "VIEW_", "END|")):
            registros.append(linha)

    dump = Dump(nome, registros)
    if not dump.ended:
        pytest.fail(
            f"[{nome}] o harness não chegou ao fim (nem settle nem watchdog). "
            f"rc={proc.returncode}\nregistros={registros}\nstderr(tail)={proc.stderr[-800:]}"
        )
    return dump


# --------------------------------------------------------------------------- #
# Casos: modo REAL (ponta a ponta) e modo STUB (view isolada)
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def bancada(tmp_path_factory):
    """Roda todos os casos uma única vez e devolve os dumps por nome."""
    _artefatos()
    tmp = tmp_path_factory.mktemp("t13")
    fixture = _fixture()
    dumps: dict[str, Dump] = {}

    # --- modo REAL -------------------------------------------------------- #
    # 1) sem ai-usagebar no PATH.
    only_py = _path_so_python(tmp)
    dumps["real-ausente"] = _rodar_harness("real-ausente", {
        "T13_MODE": "real",
        "PATH": str(only_py),
        "HOME": str(tmp / "home-ausente"),
        "XDG_CACHE_HOME": str(tmp / "cache-ausente"),
        "XDG_CONFIG_HOME": str(tmp / "cfg-ausente"),
        "T13_SETTLE_MS": "3000",
    }, tmp)

    # 2) ai-usagebar presente e falhando (rc=7, marcador em stderr).
    fake_err = _path_com_fake(tmp, f"#!/bin/sh\necho '{UPSTREAM_MARKER}' >&2\nexit 7\n")
    dumps["real-upstream"] = _rodar_harness("real-upstream", {
        "T13_MODE": "real",
        "PATH": f"{fake_err}{os.pathsep}{only_py}",
        "HOME": str(tmp / "home-upstream"),
        "XDG_CACHE_HOME": str(tmp / "cache-upstream"),
        "XDG_CONFIG_HOME": str(tmp / "cfg-upstream"),
        "T13_SETTLE_MS": "3000",
    }, tmp)

    # 3) ai-usagebar presente e funcionando (emite o fixture).
    fake_ok = _path_com_fake(tmp, f"#!/bin/sh\nexec /bin/cat {fixture}\n")
    dumps["real-ok"] = _rodar_harness("real-ok", {
        "T13_MODE": "real",
        "PATH": f"{fake_ok}{os.pathsep}{only_py}",
        "HOME": str(tmp / "home-ok"),
        "XDG_CACHE_HOME": str(tmp / "cache-ok"),
        "XDG_CONFIG_HOME": str(tmp / "cfg-ok"),
        "T13_SETTLE_MS": "3000",
    }, tmp)

    # --- modo STUB (view isolada) ----------------------------------------- #
    # A frase que o coletor emite hoje é injetada como lastError: é a tentação
    # mais forte de vazamento no caso dep-missing.
    dumps["stub-ausente"] = _rodar_harness("stub-ausente", {
        "T13_MODE": "stub",
        "T13_ERRORKIND": "dep-missing",
        "T13_LASTERROR": f"{DIAG_PREFIX} {DEP_NAME} {DIAG_DEP_MISSING}",
        "T13_LOADING": "0",
        "T13_MODEL": "",
        "T13_SETTLE_MS": "1500",
    }, tmp)

    dumps["stub-upstream"] = _rodar_harness("stub-upstream", {
        "T13_MODE": "stub",
        "T13_ERRORKIND": "upstream",
        "T13_LASTERROR": f"{DIAG_PREFIX} {DEP_NAME} rc=7 {UPSTREAM_MARKER}",
        "T13_LOADING": "0",
        "T13_MODEL": "",
        "T13_SETTLE_MS": "1500",
    }, tmp)

    # Sem erro, sem modelo, e a coleta JÁ TERMINOU (loading=0).
    # O contrato original dizia "LOADING" aqui; o review de aceitação de
    # 2026-10-28 apontou que isso promete uma operação que já acabou. O texto
    # passou a distinguir os dois casos (T13-b), e este dump fixa o lado que
    # NÃO está carregando.
    dumps["stub-vazio"] = _rodar_harness("stub-vazio", {
        "T13_MODE": "stub",
        "T13_ERRORKIND": "",
        "T13_LASTERROR": "",
        "T13_LOADING": "0",
        "T13_MODEL": "",
        "T13_SETTLE_MS": "1500",
    }, tmp)

    return dumps


# --------------------------------------------------------------------------- #
# Item 4 — o serviço expõe errorKind com os três valores
# --------------------------------------------------------------------------- #


def test_servico_expoe_error_kind_como_string(bancada):
    d = bancada["real-ausente"]
    assert d.main_present, "a instância principal não montou"
    assert d.error_kind_type == "string", (
        f"errorKind deve ser string; o tipo observado foi {d.error_kind_type!r} "
        f"(valor {d.error_kind!r})"
    )


def test_servico_marca_dependencia_ausente_como_dep_missing(bancada):
    """Ponta a ponta: PATH sem binário -> coletor rc 3 -> errorKind 'dep-missing'."""
    d = bancada["real-ausente"]
    assert d.error_kind == "dep-missing", (
        "sem ai-usagebar no PATH o serviço deve expor errorKind == 'dep-missing'; "
        f"veio {d.error_kind!r} (lastError={d.last_error!r})"
    )


def test_servico_marca_falha_do_upstream_como_upstream(bancada):
    d = bancada["real-upstream"]
    assert d.error_kind == "upstream", (
        "binário presente com rc=7 deve expor errorKind == 'upstream'; "
        f"veio {d.error_kind!r} (lastError={d.last_error!r})"
    )


def test_servico_sem_erro_expoe_error_kind_vazio(bancada):
    """Caso negativo: sucesso não pode carregar um discriminador de erro."""
    d = bancada["real-ok"]
    assert d.main_present
    assert d.loading == "false", f"após sucesso o serviço não pode continuar em loading: {d.loading!r}"
    assert d.model_null == "false", "o caso de controle precisa ter carregado um modelo"
    assert d.error_kind == "", (
        f"sem erro, errorKind deve ser a string vazia; veio {d.error_kind!r}"
    )
    assert d.error_kind not in ("dep-missing", "upstream")


def test_last_error_preserva_o_diagnostico_do_stderr(bancada):
    """``errorKind`` discrimina, ``lastError`` é a prosa — a prosa continua indo."""
    d = bancada["real-upstream"]
    assert d.last_error, "lastError não pode ficar vazio numa falha do upstream"
    assert UPSTREAM_MARKER in (d.last_error or ""), (
        "lastError deve carregar o stderr do coletor como diagnóstico; "
        f"veio {d.last_error!r}"
    )


def test_error_kind_e_um_vocabulario_fechado_e_nao_a_prosa_do_erro(bancada):
    """O discriminador não pode ser o próprio diagnóstico (senão não discrimina).

    Motivos DIFERENTES precisam de valores diferentes, e todo valor observado
    tem de pertencer ao vocabulário de três itens. Se o serviço reexpusesse o
    stderr, os valores seriam frases — e o casamento por `errorKind` na view
    voltaria a ser casamento por texto, que é o defeito que a tarefa evita.
    """
    casos = [bancada["real-ausente"], bancada["real-upstream"], bancada["real-ok"]]
    for d in casos:
        assert d.error_kind in ("", "dep-missing", "upstream"), (
            f"errorKind fora do vocabulário de três valores: {d.error_kind!r}"
        )
    assert bancada["real-ausente"].error_kind != bancada["real-upstream"].error_kind, (
        "ausência de dependência e falha do upstream compartilham o mesmo errorKind"
    )
    # E o valor não é a prosa: não contém o prefixo do diagnóstico do coletor.
    for d in casos:
        assert DIAG_PREFIX not in (d.error_kind or ""), (
            f"errorKind carrega o texto do erro em vez do discriminador: {d.error_kind!r}"
        )


# --------------------------------------------------------------------------- #
# Item 5 — a view desenha o aviso acionável em inglês
# --------------------------------------------------------------------------- #


def test_view_de_dependencia_ausente_nomeia_o_ai_usagebar(bancada):
    """Item 5(i), endurecido: o nome tem de estar num aviso que NÃO seja o
    diagnóstico do coletor.

    Sem esse recorte o teste passaria de carona na base: o texto do diagnóstico
    ("FALHA: ai-usagebar não está no PATH") também contém o nome, então
    `has("ai-usagebar")` sozinho é satisfeito justamente pelo vazamento que o
    item 5(iii) proíbe.
    """
    d = bancada["stub-ausente"]
    assert d.view_present, "a view não montou"
    avisos = [t for t in d.find(DEP_NAME) if t not in d.textos_de_diagnostico()]
    assert avisos, (
        f"o aviso de dependência ausente precisa nomear {DEP_NAME!r} em texto "
        f"próprio (não no diagnóstico do coletor); textos renderizados={d.textos}"
    )


def test_view_de_dependencia_ausente_mostra_o_comando_de_instalacao(bancada):
    """Item 5(ii): o comando exato, presente no que foi RENDERIZADO."""
    d = bancada["stub-ausente"]
    assert d.has(INSTALL_CMD), (
        f"o aviso precisa mostrar o comando de instalação {INSTALL_CMD!r}; "
        f"textos renderizados={d.textos}"
    )


def test_view_de_dependencia_ausente_nao_vaza_o_diagnostico_do_coletor(bancada):
    """Item 5(iii): com lastError em PT injetado, nada de PT pode aparecer.

    O stub recebe a frase que o coletor emite hoje; se a view a renderizasse, as
    âncoras abaixo apareceriam. A presença do comando de instalação é exigida
    ANTES da ausência do diagnóstico — sem ela, "o diagnóstico não vazou" seria vacuamente
    verdade para uma tela em branco.
    """
    d = bancada["stub-ausente"]
    assert d.has(INSTALL_CMD), (
        f"antipassividade: a tela precisa ter o aviso antes de 'o diagnóstico não vazou'; textos={d.textos}"
    )
    vazados = d.textos_de_diagnostico()
    assert not vazados, (
        f"o aviso de dependência ausente não pode mostrar o diagnóstico do coletor: "
        f"{vazados}\ntodos os textos={d.textos}"
    )


def test_view_de_dependencia_ausente_nao_vaza_o_diagnostico_no_caminho_real(bancada):
    """Mesma afirmação, agora ponta a ponta (o PT vem do stderr de verdade)."""
    d = bancada["real-ausente"]
    assert d.error_kind == "dep-missing", d
    assert d.has(INSTALL_CMD), (
        f"no caminho real o comando de instalação não foi renderizado; textos={d.textos}"
    )
    vazados = d.textos_de_diagnostico()
    assert not vazados, (
        f"o diagnóstico do coletor vazou na superfície: {vazados}"
    )


# --------------------------------------------------------------------------- #
# Item 6 — falha do upstream preserva o texto atual; os dois não coincidem
# --------------------------------------------------------------------------- #


def test_view_de_falha_do_upstream_mostra_o_diagnostico(bancada):
    d = bancada["stub-upstream"]
    assert d.view_present
    assert d.textos_de_diagnostico(), (
        "falha do upstream deve preservar o diagnóstico do coletor; "
        f"textos renderizados={d.textos}"
    )


def test_view_de_falha_do_upstream_nao_mostra_a_instrucao_de_instalacao(bancada):
    """Negativo essencial: com o binário PRESENTE, mandar instalar é mentira."""
    d = bancada["stub-upstream"]
    assert d.textos_de_diagnostico(), "antipassividade: o diagnóstico precisa estar na tela"
    assert not d.has(INSTALL_CMD), (
        f"falha do upstream não pode exibir {INSTALL_CMD!r}; textos={d.textos}"
    )


def test_view_de_falha_do_upstream_preserva_o_marcador_no_caminho_real(bancada):
    d = bancada["real-upstream"]
    assert d.error_kind == "upstream", d
    assert d.has(UPSTREAM_MARKER), (
        "o stderr do upstream precisa chegar à superfície no caso 'upstream'; "
        f"textos={d.textos}"
    )


def test_os_dois_casos_de_erro_nao_renderizam_o_mesmo_texto(bancada):
    """Item 6, forma direta: dep-missing != upstream, na tela."""
    ausente = bancada["stub-ausente"]
    upstream = bancada["stub-upstream"]
    assert ausente.textos, "o caso dep-missing não renderizou nada"
    assert upstream.textos, "o caso upstream não renderizou nada"
    assert ausente.textos != upstream.textos, (
        "os dois estados de erro renderizam exatamente o mesmo texto — são "
        f"indistinguíveis para o usuário: {ausente.textos}"
    )
    # E a diferença é a que importa: um tem a instrução, o outro o diagnóstico.
    assert ausente.has(INSTALL_CMD) and not upstream.has(INSTALL_CMD)


def test_os_dois_casos_de_erro_diferem_tambem_no_caminho_real(bancada):
    """Ponta a ponta. A distinção exigida é do DISCRIMINADOR, não do texto.

    Comparar só os textos seria satisfeito na base por acidente: as duas
    mensagens do diagnóstico já são frases diferentes ("is not on PATH" x
    "rc=7"), sem que nada discrimine os estados. Por isso aqui se exige o
    vocabulário de `errorKind` e, no caso de ausência, a instrução na tela.
    """
    ausente = bancada["real-ausente"]
    upstream = bancada["real-upstream"]
    assert ausente.error_kind == "dep-missing", ausente
    assert upstream.error_kind == "upstream", upstream
    assert ausente.has(INSTALL_CMD), (
        f"ponta a ponta, o comando de instalação não apareceu; textos={ausente.textos}"
    )
    assert not upstream.has(INSTALL_CMD), (
        f"ponta a ponta, a falha do upstream mostrou a instrução de instalação; textos={upstream.textos}"
    )
    assert ausente.textos != upstream.textos


# --------------------------------------------------------------------------- #
# Item 7 — sem erro e sem modelo: LOADING
# --------------------------------------------------------------------------- #


def test_view_sem_erro_e_sem_modelo_mostra_estado_terminal(bancada):
    """T13-b: coleta terminada, sem erro, sem modelo.

    O contrato original (T13/T19) exigia `LOADING` neste caso. O review de
    aceitação de 2026-10-28 mostrou o problema: com `loading == false` a coleta
    JÁ TERMINOU, e dizer `LOADING` promete uma operação que não está acontecendo —
    o usuário espera em vez de agir. O texto agora é `NO PROVIDERS`.

    O que o teste fixa deixou de ser a PALAVRA e passou a ser a PROPRIEDADE: um
    estado terminal, distinto de `LOADING`, sem instrução de instalação.
    """
    d = bancada["stub-vazio"]
    assert d.view_present, "a view não montou"
    assert d.error_kind == "", f"o caso de controle não deveria ter erro: {d.error_kind!r}"
    assert d.has("NO PROVIDERS"), (
        f"coleta terminada sem modelo deve dizer NO PROVIDERS; textos={d.textos}"
    )
    assert not d.has("LOADING"), (
        f"não pode dizer LOADING quando loading=0 (a coleta terminou); textos={d.textos}"
    )
    # Caso negativo: LOADING não pode conviver com os avisos de erro.
    assert not d.has(INSTALL_CMD), "LOADING não pode carregar a instrução de instalação"
    assert not d.textos_de_diagnostico(), "LOADING não pode carregar diagnóstico do coletor"


def test_loading_nao_e_o_texto_dos_estados_de_erro(bancada):
    """LOADING é um terceiro estado, não um sinônimo dos erros.

    A antipassividade é o aviso de dependência: na base os estados de erro já
    diferem de LOADING (renderizam o diagnóstico), então só comparar textos passaria
    sem que o terceiro estado exista de verdade.
    """
    vazio = bancada["stub-vazio"]
    ausente = bancada["stub-ausente"]
    assert vazio.has("NO PROVIDERS"), "antipassividade: o estado terminal precisa existir"
    assert ausente.has(INSTALL_CMD), (
        "antipassividade: o estado de dependência ausente precisa ter o próprio "
        f"aviso antes de se afirmar que ele difere de LOADING; textos={ausente.textos}"
    )
    assert ausente.textos != vazio.textos
    assert bancada["stub-upstream"].textos != vazio.textos, (
        "a falha do upstream renderiza o mesmo texto do estado sem erro"
    )


# --------------------------------------------------------------------------- #
# Nenhum caso pode falhar ao montar
# --------------------------------------------------------------------------- #


def test_nenhum_caso_produziu_erro_de_renderizacao(bancada):
    for nome in ("real-ausente", "real-upstream", "real-ok",
                 "stub-ausente", "stub-upstream", "stub-vazio"):
        d = bancada[nome]
        assert d.main_present or nome.startswith("stub"), f"{nome}: instância principal ausente"
        assert d.view_present, f"{nome}: a view não montou"
        assert not d.erros, f"{nome} produziu erro de montagem/renderização: {d.erros}"


# --------------------------------------------------------------------------- #
# Ambiguidades / lacunas do contrato (honestidade D5)
# --------------------------------------------------------------------------- #

AMBIGUIDADES = """
1. "texto em INGLÊS" (item 5) não é verificável por heurística sem inventar
   oráculo. Testo o que é objetivo: presença do nome `ai-usagebar`, presença do
   comando exato `paru -S ai-usagebar-bin`, e AUSÊNCIA das âncoras exatas do
   diagnóstico do coletor. A escolha das palavras inglesas fica
   aberta de propósito.
2. R11 é citado como razão do inglês, mas R11 ("Honesty") no AGENTS.md do plugin
   fala de `official`/`author`/README, não de idioma da UI. Nenhum dos dois
   documentos fixa a frase. Não inventei frase: só exigi os dois elementos
   obrigatórios (nome + comando) e a não-presença do PT.
3. Item 4 diz "exatamente três valores", mas não diz o que acontece durante o
   carregamento inicial nem após erro de montagem. Assumi `""` enquanto não há
   erro; não testei o estado transitório antes do primeiro poll.
4. "saída não-JSON/vazia com rc 0" -> `upstream` aparece na SPEC assinada; o
   bloco entregue ao tester só cita "rc 1 ou saída não-JSON". Testei via rc 1
   (o coletor já converte saída vazia/não-JSON em rc 1 — medido), então a
   distinção não altera nenhuma asserção deste arquivo.
5. A view ELIDE o texto de erro em ~70 caracteres (medido). Isso é anterior a
   T13 e não está no contrato. Consequência: diagnósticos longos do upstream
   aparecem truncados na superfície. Não escrevi teste contra isso (seria
   inventar requisito), mas registro porque afeta qualquer asserção textual
   sobre `lastError` — por isso as âncoras aqui são curtas.
6. O caso "binário presente mas sem bit +x" não está descrito no contrato e,
   medido, dá rc 1 com traceback de Python em stderr. Não testei; se a intenção
   humana é tratá-lo como dep-missing, o coletor precisa mudar.
"""
