# -*- coding: utf-8 -*-
"""Testes de comportamento de T26 — escala de cores semânticas derivada da accent.

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada 3,
tarefa T26. Contrato transcrito (itens 1–4 do bloco assinado + interface pública):

  1. Limiares: ``<60%`` neutro · ``60–84%`` atenção · ``>=85%`` crítico.
  2. Derivação: a escala parte da ``accent`` do host mas garante atenção quente e
     crítico vermelho; se a accent colidir com a semântica (accent vermelha), a
     escala semântica vence para o crítico. Contraste medido contra a superfície
     do popout (``#1e100d``).
  3. Fallback: o cálculo devolve SEMPRE uma cor; accent inválida ou ausente cai
     na paleta padrão.
  4. Estado também em palavra (WCAG 1.4.1): a cor reforça, não informa sozinha.

Interface pública exercitada (funções PURAS no ``Item`` raiz da view)::

    usageColour(percent, accent) -> color
    isDangerHue(c) -> bool
    neutralColour(accent) -> color
    validColour(c) -> bool

Como o comportamento é observado sem host visual
------------------------------------------------
``quickshell`` OFFLINE (``QT_QPA_PLATFORM=offscreen``): o harness
``tests/qml/t26_usage_colour_harness.qml`` monta a view, resolve cada uma das
quatro funções pelo nome e as CHAMA com as entradas escolhidas aqui, despejando o
resultado bruto canal a canal. O julgamento é contra o CONTRATO — nunca contra uma
cópia do corpo das funções, que este arquivo não lê.

Duas armadilhas desta base, tratadas explicitamente
---------------------------------------------------
* Um objeto ``color`` do QML não sobrevive a ``JSON.stringify`` em toda build
  (vira ``{}``). O harness lê ``r/g/b/a``, os componentes HSL/HSV, ``valid`` e
  ``String(c)`` UM A UM; este arquivo confere cada canal (número finito, 0..1) em
  vez de confiar num dump único.
* Uma STRING ``"#e2342a"`` como ``accent`` é tratada como accent INVÁLIDA (caso 3
  do contrato). Para exercitar uma accent vermelha de verdade, as entradas usam
  ``Qt.rgba``/``Qt.hsla`` — objeto ``color`` real.

Contraste (WCAG 2.x, luminância relativa com correção sRGB)
----------------------------------------------------------
Calculado aqui, em Python, e colado como constantes:

    #d9a441 (atenção)  × #1e100d (superfície do popout) = 8.22 : 1
    #e2342a (crítico)  × #1e100d                        = 4.19 : 1

Ambos passam do mínimo de 3:1 do SC 1.4.11 (componente de interface não-textual)
e o crítico fica abaixo de 4.5:1 — o que é coerente com o item 4 do contrato (a
cor reforça, não informa sozinha; o número e o rótulo carregam o estado). O teste
mede isso DUAS vezes: nas constantes do contrato e nas cores que a função
realmente devolve.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Localização dos artefatos (o conteúdo de Widget.qml nunca é lido)
# --------------------------------------------------------------------------- #

TEST_DIR = Path(__file__).resolve().parent          # <repo>/ai-usage/tests
#: Override por ambiente: uso EXCLUSIVO da verificação de falsificabilidade
#: desta própria suíte. O caminho de produção não o define.
PLUGIN_DIR = Path(os.environ.get("T26_PLUGIN_DIR", TEST_DIR.parent))  # <repo>/ai-usage
HARNESS = TEST_DIR / "qml" / "t26_usage_colour_harness.qml"

_QUICK = shutil.which("quickshell") or shutil.which("qs")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

pytestmark = pytest.mark.skipif(
    _QUICK is None,
    reason="quickshell ausente: a view QML e as funções puras não podem ser exercitadas",
)

# --------------------------------------------------------------------------- #
# Constantes do contrato (transcritas do bloco da tarefa, não do código)
# --------------------------------------------------------------------------- #

SUPERFICIE = "#1e100d"      # superfície do popout (F014 citado na SPEC)
COR_ATENCAO = "#d9a441"     # faixa 60–84%
COR_CRITICA = "#e2342a"     # faixa >=85%

#: Accents "seguras" (nenhuma delas pode significar perigo).
ACCENT_TEAL = "#4fd1c5"     # hsl 174.5°, s 0.59, l 0.57
ACCENT_AZUL = "#4a5b8c"     # hsl 224.5°, s 0.31, l 0.42 — cor fria do contrato
ACCENT_VERDE = "#3a7d44"    # hsl 129.0°, s 0.37, l 0.36 — "neutro/verde"
ACCENT_VERMELHA = "#e2342a"  # colide com a semântica: o caso do item 2
ACCENT_PESSEGO = "#ffb4a8"  # hsl 8.3°, s 1.00, l 0.83 — o caso central do item 4
ACCENT_QUENTE = "#d9a441"   # âmbar: quente, mas não é alarme (matiz de atenção)

#: Contraste WCAG calculado em Python (luminância relativa, correção sRGB),
#: colado aqui como constante para que a asserção seja verificável sem rodar nada.
CONTRASTE_ATENCAO_SUPERFICIE = 8.22
CONTRASTE_CRITICO_SUPERFICIE = 4.19
MINIMO_WCAG_UI = 3.0


# --------------------------------------------------------------------------- #
# WCAG — luminância relativa e razão de contraste (em Python, como o critério pede)
# --------------------------------------------------------------------------- #


def _canal_linear(v: int) -> float:
    """Canal 0–255 → luminância linear sRGB (WCAG 2.x, §relative luminance)."""
    c = v / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminancia(rgb: tuple[int, int, int]) -> float:
    r, g, b = (_canal_linear(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def razao_contraste(a: str, b: str) -> float:
    la, lb = luminancia(_hex_para_rgb(a)), luminancia(_hex_para_rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _hex_para_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def hsl_de_rgb(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """HSL (matiz em graus 0–360, saturação e luz 0–1) — medido aqui, não no QML."""
    r, g, b = (x / 255.0 for x in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    luz = (mx + mn) / 2
    d = mx - mn
    if d == 0:
        return (0.0, 0.0, luz)
    sat = d / (2 - mx - mn) if luz > 0.5 else d / (mx + mn)
    if mx == r:
        matiz = ((g - b) / d) % 6
    elif mx == g:
        matiz = (b - r) / d + 2
    else:
        matiz = (r - g) / d + 4
    return (matiz * 60.0, sat, luz)


def distancia_matiz(a: float, b: float) -> float:
    """Distância angular entre duas matizes em graus (0–180)."""
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


# --------------------------------------------------------------------------- #
# Transporte: um processo quickshell, muitos casos
# --------------------------------------------------------------------------- #


def _limpo(stdout: str) -> list[str]:
    saida: list[str] = []
    for linha in _ANSI.sub("", stdout).splitlines():
        if " qml: " in linha:
            linha = linha.split(" qml: ", 1)[1]
        linha = linha.strip()
        if linha:
            saida.append(linha)
    return saida


class Cor:
    """Uma cor devolvida pela função, com os canais VERIFICADOS um a um.

    Acessar ``.r`` num resultado que não é cor levanta AssertionError com o dump
    completo — é assim que "devolveu algo que não é cor" aparece como falha e não
    como ``TypeError`` obscuro lá adiante.
    """

    def __init__(self, caso: str, dados: dict):
        self.caso = caso
        self.dados = dados

    def _canal(self, k: str) -> float:
        v = self.dados.get(k)
        if isinstance(v, dict):
            raise AssertionError(
                f"[{self.caso}] o canal {k!r} não é um número: {v} — o contrato "
                f"exige uma cor sempre válida (item 3). dump={self.dados}"
            )
        assert isinstance(v, (int, float)), (
            f"[{self.caso}] o canal {k!r} veio {v!r} (tipo {type(v).__name__}); "
            f"dump={self.dados}"
        )
        return float(v)

    @property
    def tipo(self) -> str:
        return str(self.dados.get("$type"))

    @property
    def r(self) -> float:
        return self._canal("r")

    @property
    def g(self) -> float:
        return self._canal("g")

    @property
    def b(self) -> float:
        return self._canal("b")

    @property
    def a(self) -> float:
        return self._canal("a")

    @property
    def valid(self):
        return self.dados.get("valid")

    @property
    def rgb8(self) -> tuple[int, int, int]:
        return (
            int(round(max(0.0, min(1.0, self.r)) * 255)),
            int(round(max(0.0, min(1.0, self.g)) * 255)),
            int(round(max(0.0, min(1.0, self.b)) * 255)),
        )

    @property
    def hex(self) -> str:
        return "#%02x%02x%02x" % self.rgb8

    @property
    def hsl(self) -> tuple[float, float, float]:
        return hsl_de_rgb(self.rgb8)

    @property
    def hsl_qml(self):
        """O ``hslHue``/``hslSaturation`` que o próprio Qt calculou (0–1)."""
        h, s = self.dados.get("hslHue"), self.dados.get("hslSaturation")
        if isinstance(h, dict) or isinstance(s, dict):
            return None
        try:
            return (float(h) * 360.0, float(s))
        except (TypeError, ValueError):
            return None

    def canais_finitos(self) -> bool:
        import math
        try:
            return all(math.isfinite(c) for c in (self.r, self.g, self.b, self.a))
        except AssertionError:
            return False

    def __repr__(self) -> str:
        extra = ""
        try:
            extra = f" rgb={self.rgb8}"
        except AssertionError:
            extra = " <canais inválidos>"
        return f"<Cor {self.caso} {self.tipo}{extra} dump={self.dados}>"


class Bancada:
    def __init__(self, registros: list[str]):
        self.registros = registros
        self.roles: dict[str, str] = {}      # role -> nome real da função
        self.hosts: dict[str, str] = {}      # role -> tipo do objeto que hospeda
        self.candidatos: dict[str, dict[str, bool]] = {}
        self.casos: dict[str, dict] = {}     # "role/caso" -> dump normalizado
        self.tipos: dict[str, str] = {}
        self.excecoes: dict[str, str] = {}   # "role/caso" -> mensagem
        self.erros: list[str] = []
        for r in registros:
            if r.startswith("FN_ROLE|"):
                _t, role, nome, estado = r.split("|", 3)
                self.roles[role] = nome if estado == "present" else ""
            elif r.startswith("FN_HOST|"):
                _t, role, kind, _nome = r.split("|", 3)
                self.hosts[role] = kind
            elif r.startswith("FN_PROBE|"):
                _t, role, cand, presente = r.split("|", 3)
                self.candidatos.setdefault(role, {})[cand] = presente == "true"
            elif r.startswith("FN_THROW|"):
                _t, role, caso, msg = r.split("|", 3)
                self.excecoes[f"{role}/{caso}"] = msg
            elif r.startswith("FN|"):
                _t, role, caso, tipo, bruto = r.split("|", 4)
                self.casos[f"{role}/{caso}"] = json.loads(bruto)
                self.tipos[f"{role}/{caso}"] = tipo
            elif r.startswith("VIEW_ERR|"):
                self.erros.append(r)
        self.view_present = any(r == "VIEW_PRESENT|true" for r in registros)
        self.terminou = any(r.startswith("END|") for r in registros)

    def bruto(self, role: str, caso: str) -> dict:
        chave = f"{role}/{caso}"
        assert chave not in self.excecoes, (
            f"[{chave}] a função lançou exceção: {self.excecoes[chave]!r} — o "
            "contrato exige que accent absurda/percent inválido NÃO quebrem (itens 2 e 3)"
        )
        assert chave in self.casos, (
            f"[{chave}] caso não executado; função {self.roles.get(role)!r}; "
            f"registros={self.registros}"
        )
        return self.casos[chave]

    def cor(self, role: str, caso: str) -> Cor:
        return Cor(f"{role}/{caso}", self.bruto(role, caso))

    def booleano(self, role: str, caso: str) -> bool:
        dados = self.bruto(role, caso)
        valor = dados.get("$value")
        if valor is True or valor is False:
            return valor
        if dados.get("$undefined"):
            raise AssertionError(
                f"[{role}/{caso}] a função devolveu undefined; o contrato a "
                f"descreve como -> bool. dump={dados}"
            )
        raise AssertionError(
            f"[{role}/{caso}] a função devolveu {dados.get('$type')} "
            f"({dados.get('$string') or dados.get('$value') or dados}); esperado bool"
        )

    def __repr__(self) -> str:
        return f"<Bancada roles={self.roles} hosts={self.hosts} casos={sorted(self.casos)}>"


# --------------------------------------------------------------------------- #
# Corpus — cada caso é (role, nome, args). Marcadores do harness:
#   {"$num": n} número · {"$color": "#hex"} color real · {"$hsla": [h,s,l,a]}
#   {"$null": true} · {"$undef": true} · {"$nan": true} · string crua = string JS
# --------------------------------------------------------------------------- #


def C(hexcor: str) -> dict:
    return {"$color": hexcor}


def N(n) -> dict:
    return {"$num": n}


NULL = {"$null": True}
UNDEF = {"$undef": True}
NAN = {"$nan": True}

ACENTO_SEGURO = C(ACCENT_TEAL)

#: Fronteiras do critério de done, com o accent seguro (banda neutra = a accent).
FRONTEIRAS_NEUTRAS = [
    ("p-0", 0), ("p-30", 30), ("p-59", 59),
    ("p-59.9", 59.9), ("p-meio", 59.999),
]
FRONTEIRAS_ATENCAO = [("p-60", 60), ("p-84", 84), ("p-84.9", 84.9)]
FRONTEIRAS_CRITICAS = [("p-85", 85), ("p-99", 99), ("p-100", 100), ("p-150", 150)]

CASOS: list[dict] = []
CASOS += [{"name": n, "role": "usage", "args": [N(p), ACENTO_SEGURO]}
          for n, p in FRONTEIRAS_NEUTRAS + FRONTEIRAS_ATENCAO + FRONTEIRAS_CRITICAS]

#: A mesma fronteira com uma SEGUNDA accent segura (fria): a banda não pode
#: depender de qual accent segura o host escolheu.
CASOS += [{"name": f"azul-{n}", "role": "usage", "args": [N(p), C(ACCENT_AZUL)]}
          for n, p in [("p-30", 30), ("p-70", 70), ("p-90", 90)]]

#: percent inválido (item 2) — sempre com accent seguro, para comparar com a
#: banda neutra da MESMA accent.
CASOS += [
    {"name": "pct-null", "role": "usage", "args": [NULL, ACENTO_SEGURO]},
    {"name": "pct-undef", "role": "usage", "args": [UNDEF, ACENTO_SEGURO]},
    {"name": "pct-nan", "role": "usage", "args": [NAN, ACENTO_SEGURO]},
    {"name": "pct-string", "role": "usage", "args": ["abc", ACENTO_SEGURO]},
    {"name": "pct-critico-com-null", "role": "usage", "args": [NULL, C(ACCENT_VERMELHA)]},
]

#: accent inválida (item 3). A string "#123456" precisa ser tratada como inválida.
CASOS += [
    {"name": "acc-null", "role": "usage", "args": [N(30), NULL]},
    {"name": "acc-undef", "role": "usage", "args": [N(85), UNDEF]},
    {"name": "acc-string", "role": "usage", "args": [N(30), "#123456"]},
    {"name": "acc-string-critico", "role": "usage", "args": [N(90), "#123456"]},
    {"name": "acc-null-atencao", "role": "usage", "args": [N(70), NULL]},
]

#: accent vermelha de verdade — objeto color, nunca string (armadilha da base).
CASOS += [
    {"name": "vermelha-baixo", "role": "usage", "args": [N(30), C(ACCENT_VERMELHA)]},
    {"name": "vermelha-atencao", "role": "usage", "args": [N(70), C(ACCENT_VERMELHA)]},
    {"name": "vermelha-critico", "role": "usage", "args": [N(90), C(ACCENT_VERMELHA)]},
    {"name": "vermelha-pura-baixo", "role": "usage", "args": [N(10), {"$hsla": [0.0, 1.0, 0.5, 1.0]}]},
]

#: accent absurda (critério de done: "accent absurda não quebra").
ABSURDAS = [
    ("abs-quase-preto", {"$hsla": [0.6, 1.0, 0.02, 1.0]}),
    ("abs-branco", {"$hsla": [0.0, 0.0, 1.0, 1.0]}),
    ("abs-alpha-zero", {"$hsla": [0.33, 0.8, 0.5, 0.0]}),
    ("abs-hue-limite", {"$hsla": [0.999, 1.0, 0.5, 1.0]}),
    ("abs-pessego", C(ACCENT_PESSEGO)),
    ("abs-ambar", C(ACCENT_QUENTE)),
]
CASOS += [{"name": f"{n}-critico", "role": "usage", "args": [N(95), a]} for n, a in ABSURDAS]
CASOS += [{"name": f"{n}-baixo", "role": "usage", "args": [N(5), a]} for n, a in ABSURDAS]

#: "would the bar read as an alarm?" — composed through the PUBLIC functions
#: (isDangerHue(usageColour(p, accent))). This is how the contract line "accent
#: vermelha não pode fazer baixo consumo parecer perigo" is checked without
#: copying the band colours into the test: 30% must NOT be a danger colour, 90%
#: MUST be. See AMBIGUIDADES item 10.
CASOS += [
    {"name": "du-vermelha-baixo", "role": "dangerOfUsage", "args": [N(30), C(ACCENT_VERMELHA)]},
    {"name": "du-vermelha-puro-baixo", "role": "dangerOfUsage", "args": [N(10), {"$hsla": [0.0, 1.0, 0.5, 1.0]}]},
    {"name": "du-vermelha-atencao", "role": "dangerOfUsage", "args": [N(70), C(ACCENT_VERMELHA)]},
    {"name": "du-vermelha-critico", "role": "dangerOfUsage", "args": [N(90), C(ACCENT_VERMELHA)]},
    {"name": "du-teal-baixo", "role": "dangerOfUsage", "args": [N(30), ACENTO_SEGURO]},
    {"name": "du-teal-critico", "role": "dangerOfUsage", "args": [N(90), ACENTO_SEGURO]},
    {"name": "du-null-baixo", "role": "dangerOfUsage", "args": [NULL, C(ACCENT_VERMELHA)]},
    {"name": "du-pessego-accent-baixo", "role": "dangerOfUsage", "args": [N(20), C(ACCENT_PESSEGO)]},
]

#: isDangerHue — o item mais importante do contrato.
CASOS += [
    {"name": "d-critico", "role": "danger", "args": [C(COR_CRITICA)]},
    {"name": "d-vermelho-puro", "role": "danger", "args": [{"$hsla": [0.0, 1.0, 0.5, 1.0]}]},
    {"name": "d-pessego-pastel", "role": "danger", "args": [C(ACCENT_PESSEGO)]},
    {"name": "d-azul", "role": "danger", "args": [C(ACCENT_AZUL)]},
    {"name": "d-verde", "role": "danger", "args": [C(ACCENT_VERDE)]},
    {"name": "d-ambar", "role": "danger", "args": [C(ACCENT_QUENTE)]},
    {"name": "d-null", "role": "danger", "args": [NULL]},
    {"name": "d-string", "role": "danger", "args": ["#e2342a"]},
]

#: neutralColour
CASOS += [
    {"name": "n-teal", "role": "neutral", "args": [ACENTO_SEGURO]},
    {"name": "n-azul", "role": "neutral", "args": [C(ACCENT_AZUL)]},
    {"name": "n-verde", "role": "neutral", "args": [C(ACCENT_VERDE)]},
    {"name": "n-pessego", "role": "neutral", "args": [C(ACCENT_PESSEGO)]},
    {"name": "n-vermelha", "role": "neutral", "args": [C(ACCENT_VERMELHA)]},
    {"name": "n-vermelho-puro", "role": "neutral", "args": [{"$hsla": [0.0, 1.0, 0.5, 1.0]}]},
    {"name": "n-null", "role": "neutral", "args": [NULL]},
    {"name": "n-string", "role": "neutral", "args": ["#123456"]},
]

#: validColour
CASOS += [
    {"name": "v-teal", "role": "valid", "args": [ACENTO_SEGURO]},
    {"name": "v-critico", "role": "valid", "args": [C(COR_CRITICA)]},
    {"name": "v-branco", "role": "valid", "args": [{"$hsla": [0.0, 0.0, 1.0, 1.0]}]},
    {"name": "v-null", "role": "valid", "args": [NULL]},
    {"name": "v-undef", "role": "valid", "args": [UNDEF]},
    {"name": "v-string", "role": "valid", "args": ["#123456"]},
    {"name": "v-numero", "role": "valid", "args": [N(42)]},
]


def _artefatos() -> None:
    assert HARNESS.is_file(), f"harness QML ausente: {HARNESS}"
    assert (PLUGIN_DIR / "content" / "Widget.qml").is_file(), "content/Widget.qml ausente"


def test_artefatos_sob_teste_existem():
    """Falha rápida se a view/harness sumiram (revert-and-test não pode virar SKIP)."""
    _artefatos()


@pytest.fixture(scope="module")
def bancada(tmp_path_factory) -> Bancada:
    _artefatos()
    tmp = tmp_path_factory.mktemp("t26-cores")
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("WAYLAND_DISPLAY", None)
    env["T26_PLUG_DIR"] = str(PLUGIN_DIR)
    env["T26_STATE_DIR"] = str(tmp / "state")
    env["T26_CASES"] = json.dumps(CASOS, ensure_ascii=False)
    env["T26_SETTLE_MS"] = "1200"

    try:
        proc = subprocess.run(
            [_QUICK, "-p", str(HARNESS)],
            capture_output=True, text=True, env=env, timeout=120,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            "o harness das cores não terminou em 120s — possível laço em "
            "neutralColour/usageColour com accent absurda (critério 'accent absurda "
            "não quebra') ou view que não monta."
        )

    b = Bancada(_limpo(proc.stdout + proc.stderr))
    assert b.terminou, (
        f"o harness não chegou ao fim; rc={proc.returncode}\n"
        f"registros={b.registros}\nstderr(tail)={proc.stderr[-1200:]}"
    )
    return b


# --------------------------------------------------------------------------- #
# Âncora: as quatro funções públicas existem e são alcançáveis
# --------------------------------------------------------------------------- #


def test_as_quatro_funcoes_puras_existem_e_sao_alcancaveis(bancada):
    """Sem esta âncora todos os outros testes falhariam por atributo ausente.

    O harness sonda grafias (``usageColour`` e o ``corDoUso`` que a linha do
    critério de done ainda usa, por exemplo) e REPORTA a real; aqui só se exige
    que exista uma por papel. O nome observado vai na mensagem de falha.
    """
    assert bancada.view_present, (
        f"a view não montou; erros={bancada.erros}; nada a exercitar"
    )
    faltando = [r for r in ("usage", "danger", "neutral", "valid") if not bancada.roles.get(r)]
    assert bancada.roles.get("dangerOfUsage"), (
        "não há função de perigo alcançável para compor 'a cor pintada seria "
        "lida como alarme?'; candidatos="
        + str(bancada.candidatos.get("dangerOfUsage"))
    )
    assert not faltando, (
        f"função pública ausente para o(s) papel(is) {faltando}. O contrato exige "
        f"usageColour(percent, accent), isDangerHue(c), neutralColour(accent) e "
        f"validColour(c) alcançáveis na view montada. Sondagem={bancada.candidatos}. "
        f"Hosts={bancada.hosts}"
    )


# --------------------------------------------------------------------------- #
# Item 1 — fronteiras exatas
# --------------------------------------------------------------------------- #


def _mesma_cor(obtida: Cor, esperada: str) -> bool:
    """Igualdade a 8 bits (o QML quantiza cor em bytes: ±1 por canal é o mesmo)."""
    alvo = _hex_para_rgb(esperada)
    return all(abs(x - y) <= 1 for x, y in zip(obtida.rgb8, alvo))


def test_abaixo_de_60_a_banda_e_neutra_e_igual_a_accent_segura(bancada):
    """0, 30, 59, 59.9, 59.999 → banda NEUTRA = a própria accent (se for segura).

    A comparação é com a ACCENT devolvida por ``neutralColour`` da mesma accent,
    e também com a accent literal: o contrato diz "= o accent, se ele for seguro".
    """
    neutra_teal = bancada.cor("neutral", "n-teal")
    for nome, _p in FRONTEIRAS_NEUTRAS:
        obtida = bancada.cor("usage", nome)
        assert obtida.canais_finitos(), (
            f"[{nome}] a cor devolvida não tem canais finitos: {obtida}"
        )
        assert _mesma_cor(obtida, ACCENT_TEAL), (
            f"[{nome}] contrato item 1: abaixo de 60% a banda é NEUTRA e, com uma "
            f"accent segura ({ACCENT_TEAL}), deve ser a própria accent; devolveu "
            f"{obtida.hex}. Todos os canais: {obtida.dados}"
        )
        assert _mesma_cor(obtida, neutra_teal.hex), (
            f"[{nome}] a banda neutra ({obtida.hex}) divergiu de "
            f"neutralColour({ACCENT_TEAL}) ({neutra_teal.hex}); o neutro de "
            f"usageColour tem de ser o mesmo neutro da função pública"
        )


def test_de_60_a_84_a_banda_e_atencao(bancada):
    """60, 84, 84.9 → banda ATENÇÃO, literalmente ``#d9a441``."""
    for nome, p in FRONTEIRAS_ATENCAO:
        obtida = bancada.cor("usage", nome)
        assert obtida.canais_finitos(), f"[{nome}] canais inválidos: {obtida.dados}"
        assert _mesma_cor(obtida, COR_ATENCAO), (
            f"[{nome}] contrato item 1: {p}% cai na banda ATENÇÃO ({COR_ATENCAO}); "
            f"devolveu {obtida.hex}. dump={obtida.dados}"
        )
        matiz, sat, _luz = obtida.hsl
        assert 20.0 <= matiz <= 60.0 and sat > 0.3, (
            f"[{nome}] contrato item 2: a atenção tem de ser QUENTE (âmbar); "
            f"devolveu {obtida.hex} com matiz {matiz:.1f}° e saturação {sat:.2f}"
        )


def test_de_85_em_diante_a_banda_e_critica(bancada):
    """85, 99, 100, 150 → banda CRÍTICA, literalmente ``#e2342a``."""
    for nome, p in FRONTEIRAS_CRITICAS:
        obtida = bancada.cor("usage", nome)
        assert obtida.canais_finitos(), f"[{nome}] canais inválidos: {obtida.dados}"
        assert _mesma_cor(obtida, COR_CRITICA), (
            f"[{nome}] contrato item 1: {p}% cai na banda CRÍTICA ({COR_CRITICA}); "
            f"devolveu {obtida.hex}. dump={obtida.dados}"
        )
        matiz, sat, _luz = obtida.hsl
        assert distancia_matiz(matiz, 3.3) <= 20.0 and sat > 0.4, (
            f"[{nome}] contrato item 2: o crítico tem de ser VERMELHO; devolveu "
            f"{obtida.hex} com matiz {matiz:.1f}° e saturação {sat:.2f}"
        )


def test_a_banda_nao_depende_de_qual_accent_segura_o_host_escolheu(bancada):
    """Teal e azul (ambas seguras) produzem as MESMAS bandas de atenção/crítico."""
    for nome, esperado in (("azul-p-70", COR_ATENCAO), ("azul-p-90", COR_CRITICA)):
        obtida = bancada.cor("usage", nome)
        assert _mesma_cor(obtida, esperado), (
            f"[{nome}] com a accent azul a banda deveria ser {esperado}; devolveu "
            f"{obtida.hex}. As faixas de atenção e crítico são semânticas e não "
            f"podem variar com a accent do host."
        )
    azul_neutra = bancada.cor("usage", "azul-p-30")
    assert _mesma_cor(azul_neutra, ACCENT_AZUL), (
        f"[azul-p-30] com a accent azul segura, 30% deve devolver a própria accent "
        f"({ACCENT_AZUL}); devolveu {azul_neutra.hex}"
    )
    # A banda neutra de uma accent FRIA não é alarme (o predicado concorda).
    assert bancada.booleano("dangerOfUsage", "du-teal-baixo") is False, (
        "30% com accent teal foi lido como cor de perigo pelo próprio módulo"
    )


def test_consumo_baixo_nunca_e_lido_como_perigo(bancada):
    """Caso NEGATIVO do item 1: a banda neutra não pode ser o vermelho crítico.

    Uma implementação que devolvesse sempre a cor crítica (ou que "arredondasse"
    tudo para cima) passaria em vários testes de "devolveu uma cor válida" — esta
    a barra, pelo próprio predicado do contrato: ``isDangerHue(neutra) == false``.
    """
    for nome in ("p-0", "p-30", "p-59", "p-59.9", "pct-null", "pct-nan"):
        obtida = bancada.cor("usage", nome)
        assert not _mesma_cor(obtida, COR_CRITICA), (
            f"[{nome}] consumo baixo/indefinido devolveu o vermelho crítico "
            f"({COR_CRITICA}); a leitura de perigo seria falsa"
        )


# --------------------------------------------------------------------------- #
# Item 2 e 3 — entradas inválidas nunca produzem cor inválida
# --------------------------------------------------------------------------- #


def test_percent_invalido_cai_na_banda_neutra_com_canais_finitos(bancada):
    """``null``, ``undefined``, ``NaN`` e ``"abc"`` → banda neutra, cor válida.

    O oráculo é relacional: o resultado do percent inválido tem de ser o MESMO da
    fronteira neutra com a mesma accent (0 e 59). Assim não se inventa qual é o
    valor neutro padrão — ele é o que a própria função usa abaixo de 60.
    """
    referencia = {n: bancada.cor("usage", n) for n in ("p-0", "p-59")}
    for nome in ("pct-null", "pct-undef", "pct-nan", "pct-string"):
        obtida = bancada.cor("usage", nome)
        assert obtida.canais_finitos(), (
            f"[{nome}] contrato item 2: percent inválido devolveu canais não "
            f"finitos/ausentes ({obtida.dados}); a cor precisa ser sempre válida"
        )
        assert obtida.valid is not False, (
            f"[{nome}] a cor devolvida se declara inválida: {obtida.dados}"
        )
        assert any(_mesma_cor(obtida, r.hex) for r in referencia.values()), (
            f"[{nome}] contrato item 2: percent inválido deve cair na banda NEUTRA "
            f"(0%={referencia['p-0'].hex}, 59%={referencia['p-59'].hex}); devolveu "
            f"{obtida.hex}. dump={obtida.dados}"
        )
        assert 0.0 <= obtida.a <= 1.0, f"[{nome}] alfa fora de 0..1: {obtida.a}"


def test_accent_invalida_ou_ausente_cai_na_paleta_padrao(bancada):
    """``null``, ``undefined`` e a STRING ``"#123456"`` → paleta padrão, cor válida.

    A string é o caso que a base trata como accent INVÁLIDA (não é objeto color);
    o contrato a nomeia explicitamente.
    """
    for nome in ("acc-null", "acc-undef", "acc-string"):
        obtida = bancada.cor("usage", nome)
        assert obtida.canais_finitos() and obtida.valid is not False, (
            f"[{nome}] contrato item 3: accent inválida precisa cair na paleta "
            f"padrão e devolver cor válida; devolveu {obtida.dados}"
        )
        # A cor não pode ser "transparente por acidente" (alfa 0 é o que um
        # objeto color default costuma dar): seria uma barra invisível.
        assert obtida.a > 0.0, (
            f"[{nome}] a cor da paleta padrão saiu com alfa {obtida.a} — "
            f"invisível na tela. dump={obtida.dados}"
        )
    # Mesma BANDA, accents inválidas diferentes → mesma entrada da paleta padrão.
    # (Comparar 30% com 85% seria comparar bandas distintas — o corpus tem
    #  'acc-null' em 30% e 'acc-undef' em 85% de propósito, para que a banda seja
    #  observável apesar do fallback; por isso a igualdade é dentro da banda.)
    pares_mesma_banda = [("acc-null", "acc-string")]        # ambos 30%
    for a, b in pares_mesma_banda:
        ca, cb = bancada.cor("usage", a), bancada.cor("usage", b)
        assert _mesma_cor(ca, cb.hex), (
            f"accent null ({ca.hex}) e accent-string ({cb.hex}) deveriam cair na "
            f"MESMA entrada da paleta padrão, na banda neutra"
        )
    # E o fallback da banda neutra é opaco e finito.
    fallback = bancada.cor("usage", "acc-null")
    assert fallback.a > 0.0 and fallback.canais_finitos(), (
        f"o fallback neutro saiu inválido/transparente: {fallback.dados}"
    )


def test_critico_e_atencao_sobrevivem_a_accent_invalida(bancada):
    """Item 2 + 3 juntos: sem accent válida, 70% e 90% ainda significam o mesmo."""
    atencao = bancada.cor("usage", "acc-null-atencao")
    critico = bancada.cor("usage", "acc-string-critico")
    assert _mesma_cor(atencao, COR_ATENCAO), (
        f"[acc-null-atencao] 70% com accent nula devolveu {atencao.hex}; a faixa "
        f"de atenção tem de continuar {COR_ATENCAO}"
    )
    assert _mesma_cor(critico, COR_CRITICA), (
        f"[acc-string-critico] 90% com accent-string devolveu {critico.hex}; a "
        f"faixa crítica tem de continuar {COR_CRITICA}"
    )


def test_accent_absurda_nao_quebra_nem_engole_a_semantica(bancada):
    """Critério de done: "accent absurda não quebra".

    Quase-preto saturado, branco puro, alfa zero, matiz no limite, pêssego e âmbar.
    Em todos os casos a cor sai finita e as bandas de atenção/crítico continuam
    sendo as do contrato — a escala semântica vence.
    """
    falhas = []
    for nome_base, _accent in ABSURDAS:
        critico = bancada.cor("usage", f"{nome_base}-critico")
        baixo = bancada.cor("usage", f"{nome_base}-baixo")
        if not critico.canais_finitos() or not baixo.canais_finitos():
            falhas.append(f"[{nome_base}] canais inválidos: critico={critico.dados} baixo={baixo.dados}")
            continue
        if not _mesma_cor(critico, COR_CRITICA):
            falhas.append(
                f"[{nome_base}] 95% com accent absurda devolveu {critico.hex}; "
                f"o crítico é {COR_CRITICA} e é não-negociável (item 2)"
            )
        if _mesma_cor(baixo, COR_CRITICA):
            falhas.append(
                f"[{nome_base}] 5% devolveu o vermelho crítico — perigo falso"
            )
    assert not falhas, "accent absurda quebrou o contrato:\n" + "\n".join(falhas)


# --------------------------------------------------------------------------- #
# Item 2 — "a leitura de perigo não é negociável": accent vermelha
# --------------------------------------------------------------------------- #


def test_accent_vermelha_nao_faz_consumo_baixo_parecer_perigo(bancada):
    """O sintoma original: a cor vem da accent do host e pode significar o oposto.

    Com accent vermelha (``#e2342a`` de verdade, objeto color) 30% NÃO pode ser
    um vermelho que o próprio contrato classifica como alarme.
    """
    baixo = bancada.cor("usage", "vermelha-baixo")
    assert baixo.canais_finitos(), f"[vermelha-baixo] canais inválidos: {baixo.dados}"
    assert not _mesma_cor(baixo, COR_CRITICA), (
        f"[vermelha-baixo] 30% devolveu exatamente o vermelho crítico "
        f"({COR_CRITICA}); consumo baixo com accent vermelha passaria a parecer "
        f"perigo. devolveu {baixo.hex}"
    )
    eh_perigo = bancada.booleano("dangerOfUsage", "du-vermelha-baixo")
    assert eh_perigo is False, (
        "[du-vermelha-baixo] 30% com accent vermelha ainda é classificado como "
        "cor de perigo pela própria função — a escala semântica não venceu"
    )


def test_accent_vermelha_ainda_produz_critico_vermelho(bancada):
    """Item 2: se a accent colide, a escala semântica vence PARA O CRÍTICO."""
    critico = bancada.cor("usage", "vermelha-critico")
    assert _mesma_cor(critico, COR_CRITICA), (
        f"[vermelha-critico] 90% com accent vermelha devolveu {critico.hex}; "
        f"o crítico tem de continuar sendo o vermelho do contrato ({COR_CRITICA})"
    )
    atencao = bancada.cor("usage", "vermelha-atencao")
    assert _mesma_cor(atencao, COR_ATENCAO), (
        f"[vermelha-atencao] 70% com accent vermelha devolveu {atencao.hex}; "
        f"a atenção continua sendo a da paleta ({COR_ATENCAO}), não a accent"
    )


def test_percent_vermelho_puro_na_accent_tambem_e_neutralizado(bancada):
    """``Qt.hsla(0, 1, 0.5)`` = vermelho puro: 10% não pode sair alarme."""
    baixo = bancada.cor("usage", "vermelha-pura-baixo")
    assert baixo.canais_finitos(), f"[vermelha-pura-baixo] canais inválidos: {baixo.dados}"
    assert not _mesma_cor(baixo, "#ff0000"), (
        f"[vermelha-pura-baixo] 10% devolveu o próprio vermelho puro da accent; "
        f"a banda neutra precisa sobreviver à colisão semântica"
    )
    assert bancada.booleano("dangerOfUsage", "du-vermelha-puro-baixo") is False, (
        "[du-vermelha-puro-baixo] 10% com accent de vermelho puro ainda é "
        "classificável como perigo"
    )


# --------------------------------------------------------------------------- #
# Item 4 (o ponto mais importante) — isDangerHue
# --------------------------------------------------------------------------- #


def test_is_danger_hue_reconhece_vermelho_saturado_e_escuro(bancada):
    """``#e2342a`` (hsl l≈0.53, s≈0.76) e vermelho puro são alarme."""
    assert bancada.booleano("danger", "d-critico") is True, (
        f"isDangerHue({COR_CRITICA}) devolveu falso: o vermelho crítico do próprio "
        f"contrato precisa ser reconhecido como cor de perigo (hsl l≈0.53)"
    )
    assert bancada.booleano("danger", "d-vermelho-puro") is True, (
        "isDangerHue(vermelho puro, s=1.0, l=0.5) devolveu falso: vermelho "
        "saturado e escuro é alarme"
    )


def test_pessego_claro_nao_e_alarme(bancada):
    """O teste que o contrato chama de mais importante.

    ``#ffb4a8`` tem saturação 1.0 — um predicado que só olhasse saturação o
    chamaria de alarme. A luz dele é ≈0.83: é um pêssego de fundo, não um alerta.
    """
    assert bancada.booleano("danger", "d-pessego-pastel") is False, (
        f"isDangerHue({ACCENT_PESSEGO}) devolveu VERDADEIRO: um pêssego claro "
        f"(saturação 1.0, luz ≈0.83) está sendo lido como alarme. A saturação "
        f"sozinha não decide — a luz também"
    )


def test_cores_frias_nunca_sao_alarme(bancada):
    """Azul ``#4a5b8c`` e verde ``#3a7d44``: frias, seguras."""
    for nome, cor in (("d-azul", ACCENT_AZUL), ("d-verde", ACCENT_VERDE)):
        assert bancada.booleano("danger", nome) is False, (
            f"isDangerHue({cor}) devolveu verdadeiro: cor fria não é perigo"
        )


def test_is_danger_hue_nao_quebra_com_entrada_invalida(bancada):
    """Item 2/3 aplicados ao predicado: ``null`` ou string não podem explodir."""
    for nome, descricao in (("d-null", "null"), ("d-string", 'a string "#e2342a"')):
        # O harness registra exceção; consultar levanta AssertionError explicativo.
        valor = bancada.booleano("danger", nome)
        assert valor is False, (
            f"isDangerHue({descricao}) devolveu verdadeiro; uma entrada que não é "
            f"objeto color não representa cor de perigo"
        )


def test_o_neutro_de_uma_accent_vermelha_nao_e_ele_proprio_alarme(bancada):
    """Fecho do item 4 com o item 5: a banda neutra inteira não é alarme.

    O caminho composto é o que importa — 30% com accent vermelha, pintado e depois
    julgado pelo próprio predicado do módulo.
    """
    neutra = bancada.cor("neutral", "n-vermelha")
    assert neutra.canais_finitos(), f"[n-vermelha] canais inválidos: {neutra.dados}"
    assert not _mesma_cor(neutra, ACCENT_VERMELHA), (
        f"neutralColour(accent vermelha) devolveu o próprio vermelho ({neutra.hex})"
    )
    assert bancada.booleano("dangerOfUsage", "du-vermelha-baixo") is False, (
        "o neutro derivado de uma accent vermelha ainda seria lido como alarme"
    )
    assert bancada.booleano("dangerOfUsage", "du-vermelha-critico") is True, (
        "90% com accent vermelha NÃO foi lido como alarme: com a accent já "
        "vermelha, a faixa crítica perdeu a leitura de perigo"
    )


# --------------------------------------------------------------------------- #
# Item 5 — neutralColour
# --------------------------------------------------------------------------- #


def test_neutral_colour_devolve_a_propria_accent_quando_ela_e_segura(bancada):
    """Accent segura → a própria accent, sem alterar matiz nem saturação."""
    for nome, accent in (("n-teal", ACCENT_TEAL), ("n-azul", ACCENT_AZUL),
                         ("n-verde", ACCENT_VERDE), ("n-pessego", ACCENT_PESSEGO)):
        obtida = bancada.cor("neutral", nome)
        assert _mesma_cor(obtida, accent), (
            f"[{nome}] neutralColour({accent}) devolveu {obtida.hex}; para uma "
            f"accent segura o contrato manda devolver a PRÓPRIA accent"
        )


def test_neutral_colour_dessatura_mantendo_a_matiz(bancada):
    """Accent de perigo → cor DIFERENTE, MENOS saturada, na MESMA família.

    As três exigências são do contrato: não pode virar cinza puro (sat 0) nem
    mudar de família de cor (matiz longe da original).
    """
    for nome, accent in (("n-vermelha", ACCENT_VERMELHA),
                         ("n-vermelho-puro", "#ff0000")):
        obtida = bancada.cor("neutral", nome)
        assert obtida.canais_finitos(), f"[{nome}] canais inválidos: {obtida.dados}"
        assert not _mesma_cor(obtida, accent), (
            f"[{nome}] neutralColour({accent}) devolveu a própria cor de perigo "
            f"({obtida.hex}); o neutro precisa ser DIFERENTE"
        )
        matiz_orig, sat_orig, luz_orig = hsl_de_rgb(_hex_para_rgb(accent.lstrip("#")))
        matiz, sat, luz = obtida.hsl
        assert sat < sat_orig, (
            f"[{nome}] a saturação não caiu: {sat:.3f} >= {sat_orig:.3f} "
            f"(original {accent}, devolvida {obtida.hex})"
        )
        assert sat > 0.05, (
            f"[{nome}] a cor neutra virou cinza puro (saturação {sat:.3f}); o "
            f"contrato exige manter a matiz, não apagar a cor ({obtida.hex})"
        )
        assert luz > luz_orig, (
            f"[{nome}] a luz não subiu ({luz:.3f} <= {luz_orig:.3f}); clarear é o "
            f"que torna a cor de perigo inofensiva em fundo escuro ({obtida.hex})"
        )
        assert distancia_matiz(matiz, matiz_orig) <= 15.0, (
            f"[{nome}] a matiz mudou de família: original {matiz_orig:.1f}°, "
            f"devolvida {matiz:.1f}° ({obtida.hex})"
        )


def test_neutral_colour_nunca_devolve_cor_invalida(bancada):
    """Item 3: ``neutralColour(null)`` e ``neutralColour("#123456")`` → válida."""
    for nome in ("n-null", "n-string"):
        obtida = bancada.cor("neutral", nome)
        assert obtida.canais_finitos(), f"[{nome}] canais inválidos: {obtida.dados}"
        assert obtida.a > 0.0, (
            f"[{nome}] a cor neutra saiu transparente (alfa {obtida.a}): barra "
            f"invisível. dump={obtida.dados}"
        )


# --------------------------------------------------------------------------- #
# validColour
# --------------------------------------------------------------------------- #


def test_valid_colour_aceita_objetos_color_e_recusa_o_resto(bancada):
    """``validColour`` é o guarda do item 3: string, null, undefined, número."""
    assert bancada.booleano("valid", "v-teal") is True, (
        f"validColour({ACCENT_TEAL}) devolveu falso para um objeto color real"
    )
    assert bancada.booleano("valid", "v-critico") is True, (
        f"validColour({COR_CRITICA}) devolveu falso para um objeto color real"
    )
    assert bancada.booleano("valid", "v-branco") is True, (
        "validColour(branco) devolveu falso para um objeto color real"
    )
    for nome, descricao in (("v-null", "null"), ("v-undef", "undefined"),
                            ("v-string", 'a string "#123456"'), ("v-numero", "42")):
        assert bancada.booleano("valid", nome) is False, (
            f"validColour({descricao}) devolveu verdadeiro; só um objeto color "
            f"QML é accent válida (item 3 trata a string como inválida)"
        )


# --------------------------------------------------------------------------- #
# Item 4 do critério — contraste medido (em Python) e documentado
# --------------------------------------------------------------------------- #


def test_contraste_das_constantes_do_contrato_contra_a_superficie_do_popout():
    """O cálculo em Python, com os valores documentados amarrados na asserção."""
    medido_atencao = razao_contraste(COR_ATENCAO, SUPERFICIE)
    medido_critico = razao_contraste(COR_CRITICA, SUPERFICIE)

    assert medido_atencao >= MINIMO_WCAG_UI, (
        f"{COR_ATENCAO} × {SUPERFICIE} dá {medido_atencao:.2f}:1, abaixo de "
        f"{MINIMO_WCAG_UI}:1"
    )
    assert medido_critico >= MINIMO_WCAG_UI, (
        f"{COR_CRITICA} × {SUPERFICIE} dá {medido_critico:.2f}:1, abaixo de "
        f"{MINIMO_WCAG_UI}:1"
    )
    # Os valores colados no cabeçalho não podem divergir do cálculo.
    assert abs(medido_atencao - CONTRASTE_ATENCAO_SUPERFICIE) < 0.01, (
        f"o valor documentado ({CONTRASTE_ATENCAO_SUPERFICIE}) não confere com o "
        f"medido ({medido_atencao:.4f})"
    )
    assert abs(medido_critico - CONTRASTE_CRITICO_SUPERFICIE) < 0.01, (
        f"o valor documentado ({CONTRASTE_CRITICO_SUPERFICIE}) não confere com o "
        f"medido ({medido_critico:.4f})"
    )


def test_as_cores_REAIS_da_atencao_e_do_critico_passam_de_3_para_1(bancada):
    """Mede o que a função DEVOLVE, não a constante: se a cor mudar, o teste cai.

    Escolhe o pior caso entre as accents: uma cor semântica que só passasse com a
    accent padrão falharia aqui.
    """
    alvos = [("usage", "p-60", "atenção/teal"), ("usage", "p-85", "crítico/teal"),
             ("usage", "azul-p-70", "atenção/azul"), ("usage", "azul-p-90", "crítico/azul"),
             ("usage", "acc-null-atencao", "atenção/fallback"),
             ("usage", "acc-string-critico", "crítico/fallback"),
             ("usage", "vermelha-critico", "crítico/accent vermelha")]
    falhas = []
    for role, caso, etiqueta in alvos:
        cor = bancada.cor(role, caso)
        ratio = razao_contraste(cor.hex, SUPERFICIE)
        if ratio < MINIMO_WCAG_UI:
            falhas.append(
                f"[{etiqueta}] {cor.hex} × {SUPERFICIE} = {ratio:.2f}:1 < "
                f"{MINIMO_WCAG_UI}:1"
            )
    assert not falhas, (
        "cores devolvidas com contraste insuficiente contra a superfície do "
        "popout:\n" + "\n".join(falhas)
    )


def test_atencao_e_critico_se_distinguem_entre_si(bancada):
    """Sem isso a "escala" seria uma cor só com dois nomes.

    Exige diferença de matiz perceptível (não basta alfa ou ruído de quantização)
    e que o crítico seja mais vermelho que a atenção.
    """
    atencao = bancada.cor("usage", "p-60")
    critico = bancada.cor("usage", "p-85")
    m_a, _s_a, _l_a = atencao.hsl
    m_c, _s_c, _l_c = critico.hsl
    assert distancia_matiz(m_a, m_c) >= 20.0, (
        f"atenção ({atencao.hex}, {m_a:.1f}°) e crítico ({critico.hex}, "
        f"{m_c:.1f}°) são quase a mesma cor: a escala não comunica dois estados"
    )
    assert 330.0 <= m_c or m_c <= 25.0, (
        f"o crítico {critico.hex} não está na faixa do vermelho (matiz {m_c:.1f}°)"
    )


# --------------------------------------------------------------------------- #
# AMBIGUIDADES do contrato (D5) — o que foi assumido e o que ficou sem oráculo
# --------------------------------------------------------------------------- #
AMBIGUIDADES = """
1. NOME DAS FUNÇÕES. A interface pública colada na tarefa nomeia as funções em
   inglês (``usageColour``, ``isDangerHue``, ``neutralColour``, ``validColour``),
   mas a linha do critério de done da SPEC ainda diz ``corDoUso(percent, accent)``.
   O harness sonda as duas famílias de grafia e REPORTA a que existe; a suíte não
   exige nenhum nome específico, só que exista uma função por papel. Se a
   implementação usar outro nome fora da lista, todos os testes falham listando
   os candidatos — ruidoso de propósito.

2. "BANDA NEUTRA = O ACCENT" x "PALETA PADRÃO". O contrato diz que abaixo de 60%
   a banda é "o accent, se ele for seguro" (item 1) e que accent inválida cai na
   "paleta padrão" (item 3), sem dizer QUAL é a paleta padrão. Os testes não
   fixam esse valor: exigem apenas cor válida, opaca, e que as duas accent
   inválidas diferentes caiam na MESMA entrada.

3. `neutralColour` PARA UMA ACCENT "SEGURA"... E PARA A ÂMBAR? O item 5 só define
   dois ramos: seguro → a própria accent; "de perigo" → dessaturada na mesma
   matiz. Não diz onde a âmbar (``#d9a441``, matiz de atenção) cai. A suíte
   exercita ``usageColour(95, âmbar)`` e ``isDangerHue(âmbar)`` apenas como
   DIAGNÓSTICO (o resultado aparece no dump em caso de falha), sem asserção
   própria: exigir "âmbar não é perigo" ou "âmbar é perigo" seria inventar oráculo.

4. QUANTO É "MENOS SATURAÇÃO" E "MESMA MATIZ". O contrato não dá número. A suíte
   usa a exigência estrita (sat MENOR que a original, > 0.05 para não virar cinza)
   e uma tolerância de 15° de matiz, mais "luz aumentou" — clarear é a única
   leitura geométrica que sobrevive ao requisito de contraste contra fundo escuro.
   Um dessaturamento por HSL com luz fixa, por exemplo, falharia na asserção de
   luz; se a implementação fizer isso e ainda cumprir contraste, a ambiguidade é
   esta asserção, não a intenção declarada.

5. FRONTEIRA EXATA E PONTO FLUTUANTE. ``59.9`` e ``59.999`` são neutros,
   ``84.9`` é atenção, ``85.0`` é crítico — asserido. Se a implementação comparar
   após arredondar o percent (``Math.round``), ``59.9`` viraria 60 e o teste
   falharia; o contrato diz "<60%" e não autoriza arredondar, então o teste adota
   a leitura literal.

6. "CONTRA O TRILHO" SEM COR. O item 2 manda medir contraste também contra o
   trilho, mas o trilho não é declarado (nem hex, nem alfa). Não há asserção de
   contraste contra ele — só contra ``#1e100d``, que é o único valor dado. Se o
   trilho for escuro como a superfície, o resultado é o mesmo; se for claro, o
   requisito está sem oráculo.

7. WCAG E O ITEM 4. O contraste do crítico é 4.19:1 contra a superfície: passa de
   3:1 (SC 1.4.11, componente não-textual) e NÃO passa de 4.5:1 (texto normal).
   Isso é compatível com o item 4 — a cor reforça e o número/rótulo informa — mas
   o teste não pode exigir 4.5:1 da cor sem contradizer o hex do contrato.

8. O QUE "ACENTO SEGURO" SIGNIFICA. Não há lista de matizes proibidas. A suíte
   usa teal/azul/verde como seguras porque o próprio contrato as cita como frias,
   e o pêssego como seguro porque o item 4 declara que ele NÃO é alarme. Se a
   implementação considerar o pêssego perigoso por outro critério, o teste
   ``test_neutral_colour_devolve_a_propria_accent_quando_ela_e_segura`` acusa —
   e o conflito é entre os itens 4 e 5, não entre o teste e o texto.

9. `isDangerHue(null)` / `isDangerHue("...")`. O contrato só descreve entradas que
   são objetos color. A suíte adota a leitura mais fraca e segura: não lançar e
   devolver falso. Lançar seria defensável, mas aí a falha seria legítima — este é
   o único ponto em que os testes escolhem um dos dois comportamentos aceitáveis
   em vez de derivá-lo do texto.

10. "BAIXO CONSUMO NÃO PODE PARECER PERIGO" — COMO ISSO É VERIFICADO. O sintoma
   do objetivo é relacional: "a cor que a barra pinta" lida como alarme. Fingir
   isso comparando contra ``#e2342a`` presumiria que a implementação usa aquele
   hex para o crítico (ela pode usar outro vermelho igualmente correto). A suíte
   compõe as DUAS funções públicas no harness —
   ``isDangerHue(usageColour(p, accent))`` — e exige falso em 30% com accent
   vermelha e verdadeiro em 90%. Se o módulo não expuser as duas, o caso composto
   falha como "função ausente", não passa em silêncio. A comparação literal
   contra ``#d9a441``/``#e2342a`` fica restrita às fronteiras do item 1, onde o
   contrato dá os hex.

11. A PALETA PADRÃO PARTICIPA DA ESCALA. Com accent inválida, 30% devolveu
   ``#ffb4a8`` (o pêssego que o item 4 usa como exemplo de "NÃO é alarme") e 95%
   devolveu ``#e2342a``. É coerente, mas nada no contrato fixa essa paleta: a
   suíte só exige cor válida, opaca, e a MESMA entrada para accents inválidas
   diferentes. Se o dono quiser um neutro específico no fallback, não há oráculo
   aqui para isso.
"""
