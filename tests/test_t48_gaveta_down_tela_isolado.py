# -*- coding: utf-8 -*-
"""Contratos de comportamento de T48 (gaveta ``down`` limitada ao espaço da tela)
e T49 (``+N more`` e ``Collapse`` nunca recortados).

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada 5,
tarefas T48 e T49. Nenhum arquivo de produto foi lido: nem ``content/Widget.qml``
nem ``service/``. As fontes são o bloco T48/T49 da SPEC, o sintoma relatado pelo
dono no shell real em 2026-11-10, a interface pública declarada (``heightBudget``)
e as convenções dos testes já existentes.

O sintoma que esta suíte contrata
---------------------------------
Com ``drawerDirection: down``, abrir a gaveta de um secundário fazia o popout
crescer além da tela: o rodapé (``updated … ago``, ``Copy keybind``, refresh) saía
da tela e o ``Collapse`` ficava cortado pela metade. O host centraliza o popout
pela altura implícita da view e RECORTA em silêncio o que não cabe. Logo, o que
se mede é: **a altura real da view (``implicitHeight * s``) contra o orçamento
``heightBudget`` informado**, e a posição do rodapé e do ``Collapse`` dentro dele.

Método
------
``tests/qml/t48_gaveta_down_tela_harness.qml`` monta APENAS ``content/Widget.qml``
num processo ``quickshell`` OFFLINE (offscreen), dentro de uma janela de palco
maior que qualquer caso, com ``pluginApi`` sintético. O ``ai-usagebar`` nunca
roda: sem rede, sem credencial, sem escrita em config. A sonda despeja a árvore
renderizada (nó, pai, tipo, texto, geometria, clip, cor, opacidade) e entrega
cliques REAIS de ponteiro por coordenada (necessário ao item 5 do contrato).

Duas passadas, e por quê: os orçamentos apertados são definidos RELATIVAMENTE à
altura da view fechada e ao crescimento da gaveta livre, e essas duas medidas só
existem depois de montar a view. A 1ª passada (``livre``) mede com orçamento
folgado; a 2ª (``apertado``) usa ``H = fechada + folga`` calculado dessas medidas.
Nenhum pixel absoluto de layout é fixado neste arquivo.

Nada depende de ``objectName`` nem de nome de componente: a grade é achada por
tipo, o painel da gaveta é o ancestral com ``clip`` mais próximo da linha de
status do provider aberto (``<ID>-PLAN``, texto que só existe na gaveta), e
"inteiro"/"não recortado" significa geometricamente dentro desse painel.

Partição (``-k``)
-----------------
* ``tela``    — específicos de T48. Cada um exige que a view aberta não passe
  de max(H, fechada) num caso em que a gaveta livre não caberia, logo nenhum
  sobrevive a uma base sem o limite.
* ``recorte`` — T49 (``+N more``/``Collapse``/leituras dentro do painel, contagem,
  líder), em ``down`` e em ``left``/``right``. O recorte medido nas laterais
  antes da correção está registrado em ``RECORTE_LATERAL_ANTES``.
* ``ctrl``    — controles: o que já valia antes (lateral, H grande, espaço de
  sobra empurra, fechar devolve a altura) e a antipassividade do instrumento.

ATENÇÃO: o nome deste ARQUIVO contém "tela", e ``-k`` casa também o nome do
módulo — ``-k "tela or recorte"`` sozinho seleciona TUDO, inclusive os controles.
A partição correta é pelo prefixo da função ou pela negação de ``ctrl``:

    python -m pytest ai-usage/tests/test_t48_gaveta_down_tela_isolado.py -k "not ctrl"   # específicos
    python -m pytest ai-usage/tests/test_t48_gaveta_down_tela_isolado.py -k ctrl         # controles
    python -m pytest ai-usage/tests/test_t48_gaveta_down_tela_isolado.py -k "test_tela"  # só T48
    python -m pytest ai-usage/tests/test_t48_gaveta_down_tela_isolado.py -k "test_recorte or test_tela_recorte"  # T49

CONTRATO T48 REVISADO (depois do smoke no shell real) — e a regra que caiu
-------------------------------------------------------------------------
REGRA ANTIGA (itens 4 e 6 originais): sem espaço abaixo da grade, a gaveta
`down` cobria SÓ a grade e cortava pela cauda o que não coubesse nesse espaço
(`+N more` por aperto de tela); se nem o piso coubesse, a view excedia H.
POR QUE CAIU: foi medida e reprovada. No monitor do dono, grade + folga davam
200 px e uma métrica com contador precisa de 219 — a gaveta só conseguia mostrar
`+2 more`. (Nesta bancada a mesma regra dava view=303 contra H=258 com grade de
uma linha, e `+5 more` com 142 px de folga.)

REGRA NOVA, que este arquivo contrata:
  1'. View aberta ≤ max(H, altura fechada). Se a fechada já excede H, abrir a
      gaveta não aumenta a view além da fechada.
  4'. Sem espaço abaixo da grade, a gaveta sobe a partir da base (ancorada
      embaixo, opaca), sobre a grade e sobre o que estiver acima dela. Aperto de
      tela, por si só, NÃO corta métricas: a gaveta desenha as mesmas métricas e
      leituras que desenharia com H grande.
  6'. O corte por `+N more` em `down` vem do teto (`drawerMaxHeight` × s) e de a
      gaveta não poder passar do topo do conteúdo: ela não é mais alta que tudo o
      que há do topo da view até a base da grade, mais a folga abaixo. Piso
      inalterado: nunca menor que nome + status + contador + `Collapse`.

Como isso vira oráculo sem fixar pixel: para cada caso apertado calcula-se, das
medidas da própria view, ``disponível = base da grade (fechada) + folga``, com
``folga = max(H − altura fechada, 0)``. Dois grupos de casos:
  * ``CHEIOS`` — a gaveta livre cabe no disponível com margem de mais de uma
    linha de métrica: ali o conteúdo tem de ser IGUAL ao de H grande (4').
  * ``TOPO``   — a gaveta livre é mais alta que o disponível: ali há corte pela
    cauda, anunciado, e a gaveta não passa do topo da view (6').
Cada teste confere em tempo de execução que o caso pertence ao grupo declarado;
casos na fronteira (menos de uma linha de margem) não são usados.

``LACUNAS_DE_OBSERVACAO`` lista o que este arquivo NÃO prova.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Localização dos artefatos (a implementação nunca é lida)
# --------------------------------------------------------------------------- #

TEST_DIR = Path(__file__).resolve().parent
PLUGIN_DIR = Path(os.environ.get("T48_PLUG_DIR", TEST_DIR.parent))
HARNESS = Path(os.environ.get("T48_HARNESS",
                              TEST_DIR / "qml" / "t48_gaveta_down_tela_harness.qml"))

_QUICK = shutil.which("quickshell") or shutil.which("qs")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

_skip_sem_quickshell = pytest.mark.skipif(
    _QUICK is None,
    reason="quickshell ausente: a view QML não pode ser exercitada",
)
pytestmark = _skip_sem_quickshell

LACUNAS_DE_OBSERVACAO = {
    "tela_real_e_margens_do_host": (
        "O orçamento é INFORMADO pela sonda (`heightBudget`). Como o host calcula "
        "esse número a partir da tela (margens, barra, escala) não é observável "
        "aqui; depende do smoke por captura no shell real."),
    "heightBudget_zero": (
        "`heightBudget: 0` (não informado) deriva da tela; em offscreen a tela é "
        "um artefato do harness. Nenhum caso depende disso — todos informam H."),
    "pintura": (
        "'Opaca' é medida por cor (alfa) e opacidade do painel, e a precedência de "
        "entrada por clique real. Nenhum pixel é rasterizado: um defeito de ordem "
        "de pintura sem efeito sobre entrada nem geometria não aparece."),
    "animacao": (
        "As medidas são tomadas com a view assentada (≥ 600 ms). Um estouro "
        "transitório durante a animação de abertura não é observável."),
    "piso_em_pixels": (
        "O piso (nome + status + contador + Collapse) é verificado por CONTEÚDO e "
        "por não-recorte, não por um número de pixels."),
}

TOL = 0.75  #: tolerância geométrica (px): arredondamento de layout, não folga de contrato
_SCROLLER = re.compile(r"Flickable|ScrollView|ListView|GridView|ScrollBar|WheelHandler")
_COUNTER = re.compile(r"^\+(\d+)\s+more$", re.I)
H_LIVRE = 100000  #: orçamento que nenhuma view deste arquivo alcança
EPOCH = 1750000000


# --------------------------------------------------------------------------- #
# Fixtures de modelo — sintéticas, nenhum dado real de conta
# --------------------------------------------------------------------------- #

#: Texto de detalhe no formato do relatório (o mesmo da fixture pública de
#: `tests/fixtures/report-schema1.json`): é o que liga as leituras Elapsed/Pace.
DETALHE = "Resets in 1h 56m · 61% elapsed · 30pts ahead"


def metric(label: str, percent: int, rico: bool = True) -> dict:
    return {
        "label": label,
        "percent": percent,
        "value": "%d%%" % percent,
        "severity": "low",
        "detail": DETALHE if rico else "",
        "reset_at": "2025-06-15T18:00:00Z" if rico else None,
        "window_secs": 18000,
    }


def provider(pid: str, name: str, metrics: list) -> dict:
    return {
        "id": pid,
        "display_name": name,
        "short_name": pid[:3],
        "plan": pid + "-plan",
        "status": "ready",
        "stale": False,
        "metrics": metrics,
        "error": None,
        "account": None,
    }


#: nome fictício por tamanho; nenhum é prefixo de outro.
NOMES = {5: ("p05", "Pill Qui"), 8: ("p08", "Pill Oct"), 12: ("p12", "Pill Dod")}


def percentuais(n: int) -> list:
    """10,20,…,80,10,20,… — o líder (maior percent) NÃO é o primeiro da ordem."""
    return [10 + (i % 8) * 10 for i in range(n)]


def grande(n: int) -> dict:
    pid, nome = NOMES[n]
    curto = nome.split()[-1]
    return provider(pid, nome, [metric("%s M%d" % (curto, i + 1), p)
                                for i, p in enumerate(percentuais(n))])


def empatado() -> dict:
    """Cinco métricas com o MESMO percent: o líder é a primeira pela ordem."""
    return provider("ptie", "Pill Tie", [metric("Tie M%d" % (i + 1), 50) for i in range(5)])


def pequeno(i: int) -> dict:
    return provider("s%d" % i, "Pill S%d" % i,
                    [metric("S%d M1" % i, 10), metric("S%d M2" % i, 20)])


PRIMARIO = provider("alpha", "Pill Alpha",
                    [metric("Alpha M1", 10, rico=False), metric("Alpha M2", 20, rico=False)])


def modelo(*secundarios: dict) -> dict:
    ps = [PRIMARIO] + list(secundarios)
    return {"schema": 1, "primary": ps[0], "secondary": ps[1:], "all": ps,
            "total_providers": len(ps), "with_issues": 0}


#: M1 — grade de UMA linha (2 secundários em 2 colunas).
M1 = modelo(grande(8), pequeno(1))
#: M3 — grade de TRÊS linhas (6 secundários): mais alta que o piso da gaveta.
M3 = modelo(grande(8), *[pequeno(i) for i in range(1, 6)])

BASE_SETTINGS = {
    "showSecondaries": True,
    "maxSecondary": 12,
    "secondaryLabel": "name",
    "showMetricDetail": True,
    "drawerDirection": "down",
    "drawerMaxHeight": 320,
    "columns": 2,
    "accent": "wallpaper",
    "language": "en",
}


def cfg(**kw) -> dict:
    d = dict(BASE_SETTINGS)
    d.update(kw)
    return d


# --------------------------------------------------------------------------- #
# Passos
# --------------------------------------------------------------------------- #

def SNAP(nome: str) -> dict:
    return {"op": "snap", "name": nome}


def abrir(prov: dict, nome: str = "open") -> dict:
    """Abre pela pílula; o marcador é a linha de status, que só existe na gaveta."""
    return {"op": "openDrawer", "text": prov["plan"].upper(),
            "click": prov["display_name"], "name": nome, "ms": 700}


def clique_real_em(texto: str, nome: str) -> dict:
    return {"op": "mouseText", "value": texto, "name": nome, "ms": 650}


def clique_real_na_pilula(prov: dict, nome: str, fy: float = 0.9) -> dict:
    return {"op": "mouseOnControl", "value": prov["display_name"], "fx": 0.5, "fy": fy,
            "name": nome, "ms": 650}


OCT = grande(8)
DOD = grande(12)
S1 = pequeno(1)

#: M12 — 12 métricas, grade de uma linha (para o teto pequeno sob aperto).
M12 = modelo(DOD, S1)
#: MC — conteúdo CURTO acima da grade: primário com uma métrica só.
PRIMARIO_CURTO = provider("alpha", "Pill Alpha", [metric("Alpha M1", 10, rico=False)])
MC = {"schema": 1, "primary": PRIMARIO_CURTO, "secondary": [DOD, S1],
      "all": [PRIMARIO_CURTO, DOD, S1], "total_providers": 3, "with_issues": 0}
#: MP — relatório SEM primário: acima da grade só o cabeçalho da view.
MP = {"schema": 1, "primary": None, "secondary": [OCT, S1], "all": [OCT, S1],
      "total_providers": 2, "with_issues": 0}


def caso(nome: str, model: dict, H, steps: list, s: float = 1, largura: int = 460,
         **settings) -> dict:
    return {"name": nome, "settings": cfg(**settings), "model": model,
            "widthBudget": largura, "heightBudget": H, "s": s, "epoch": EPOCH,
            "steps": steps}


# --------------------------------------------------------------------------- #
# 1ª passada — orçamento folgado (medidas de referência + matriz de T49)
# --------------------------------------------------------------------------- #

TETOS = (160, 240, 320, 480)
TAMANHOS = (5, 8, 12)
LARGO = 900  #: largura folgada: lateral não cede para `down` por falta de largura

CASOS_LIVRES: list[dict] = []

#: referência de M1/M3: fechada, aberta, recolhida, e o pequeno aberto.
for _tag, _m in (("m1", M1), ("m3", M3)):
    CASOS_LIVRES.append(caso("livre-" + _tag, _m, H_LIVRE, [
        SNAP("closed"), abrir(OCT), clique_real_em("Collapse", "recolhido"),
        abrir(S1, "s1")]))
CASOS_LIVRES.append(caso("livre-m1-5000", M1, 5000, [SNAP("closed"), abrir(OCT)]))
CASOS_LIVRES.append(caso("livre-m1-nodet", M1, H_LIVRE, [SNAP("closed"), abrir(OCT)],
                         showMetricDetail=False))
CASOS_LIVRES.append(caso("livre-m1-s15", M1, H_LIVRE, [SNAP("closed"), abrir(OCT)],
                         s=1.5, largura=690))
#: 6' — teto pequeno com muitas métricas; conteúdo curto acima da grade; e
#: relatório SEM primário (o menor conteúdo acima da grade que a view admite).
CASOS_LIVRES.append(caso("livre-m12-160", M12, H_LIVRE, [SNAP("closed"), abrir(DOD)],
                         drawerMaxHeight=160))
CASOS_LIVRES.append(caso("livre-curto", MC, H_LIVRE, [SNAP("closed"), abrir(DOD)],
                         drawerMaxHeight=480))
CASOS_LIVRES.append(caso("livre-mp", MP, H_LIVRE, [SNAP("closed"), abrir(OCT)]))

#: controle lateral: mesmo relatório, H pequeno (menor que a própria view) × grande.
for _d in ("left", "right"):
    for _h in (300, 5000):
        CASOS_LIVRES.append(caso("lat-%s-%d" % (_d, _h), M1, _h,
                                 [SNAP("closed"), abrir(OCT)],
                                 largura=LARGO, drawerDirection=_d))

#: matriz de T49: direção × teto × tamanho × leitura ligada/desligada.
for _d in ("down", "left", "right"):
    for _t in TETOS:
        for _n in TAMANHOS:
            for _det in (True, False):
                CASOS_LIVRES.append(caso(
                    "rc-%s-%d-%d-%s" % (_d, _t, _n, "det" if _det else "nodet"),
                    modelo(grande(_n), pequeno(1)), H_LIVRE, [abrir(grande(_n))],
                    largura=(460 if _d == "down" else LARGO),
                    drawerDirection=_d, drawerMaxHeight=_t, showMetricDetail=_det))
for _t in (160, 480):
    CASOS_LIVRES.append(caso("rc-down-%d-tie" % _t, modelo(empatado(), pequeno(1)), H_LIVRE,
                             [abrir(empatado())], drawerMaxHeight=_t))


# --------------------------------------------------------------------------- #
# 2ª passada — orçamentos apertados, derivados das medidas da 1ª
# --------------------------------------------------------------------------- #

#: folgas (px reais acima da view fechada) com grade de UMA linha.
FOLGAS_M1 = (60, 100, 142, 200)
#: com grade de TRÊS linhas.
FOLGAS_M3 = (0, 40, 100)

APERTADOS_M1 = ["ap-m1-d%d" % d for d in FOLGAS_M1]
APERTADOS_M3 = ["ap-m3-d%d" % d for d in FOLGAS_M3]

#: CHEIOS — a gaveta livre cabe entre o topo da view e a base da grade + folga:
#: aperto de tela não corta nada (4').
CHEIOS = ["ap-m1-d142", "ap-m1-d200", "ap-m3-d40", "ap-m3-d100", "ap-m1-quase",
          "ap-m1-nodet-d140", "ap-m1-s15-d240", "ap-m12-160-d42"]
#: TOPO — a gaveta livre é mais alta que isso: corta pela cauda sem passar do
#: topo (6').
TOPO = ["ap-m1-d60", "ap-m1-d100", "ap-m3-d0", "ap-m1-nodet-d60", "ap-m1-s15-d60",
        "ap-curto-d0", "ap-curto-d51"]
APERTADOS = CHEIOS + TOPO

#: caso apertado -> caso livre de referência (mesmo modelo, settings e escala)
REFERENCIA = {n: "livre-m1" for n in APERTADOS_M1}
REFERENCIA.update({n: "livre-m3" for n in APERTADOS_M3})
REFERENCIA.update({
    "ap-m1-quase": "livre-m1",
    "ap-m1-nodet-d140": "livre-m1-nodet", "ap-m1-nodet-d60": "livre-m1-nodet",
    "ap-m1-s15-d240": "livre-m1-s15", "ap-m1-s15-d60": "livre-m1-s15",
    "ap-m12-160-d42": "livre-m12-160",
    "ap-curto-d0": "livre-curto", "ap-curto-d51": "livre-curto",
})
#: provider aberto em cada caso (OCT quando não listado)
_PROV = {"ap-m12-160-d42": DOD, "ap-curto-d0": DOD, "ap-curto-d51": DOD,
         "livre-m12-160": DOD, "livre-curto": DOD}
REFERENCIAS = ("livre-m1", "livre-m3", "livre-m1-nodet", "livre-m1-s15",
               "livre-m12-160", "livre-curto", "livre-mp")


def prov_de(nome: str) -> dict:
    return _PROV.get(nome, OCT)


def lider_de(prov: dict) -> int:
    ps = [m["percent"] for m in prov["metrics"]]
    return ps.index(max(ps)) + 1


def casos_apertados(med: dict) -> list:
    """`med[ref] = (fechada, aberta)` em px reais, medidos na 1ª passada."""
    c1, o1 = med["livre-m1"]
    c3, _ = med["livre-m3"]
    cn, _ = med["livre-m1-nodet"]
    cs, _ = med["livre-m1-s15"]
    c12, _ = med["livre-m12-160"]
    cc, _ = med["livre-curto"]
    cp, _ = med["livre-mp"]
    g1 = o1 - c1
    passos = [SNAP("closed"), abrir(OCT)]
    passos12 = [SNAP("closed"), abrir(DOD)]
    out = []
    for d in FOLGAS_M1:
        out.append(caso("ap-m1-d%d" % d, M1, c1 + d, passos))
    for d in FOLGAS_M3:
        out.append(caso("ap-m3-d%d" % d, M3, c3 + d, passos))
    #: 4 px a menos que o necessário para a gaveta inteira: o menor aperto.
    out.append(caso("ap-m1-quase", M1, c1 + g1 - 4, passos))
    #: exatamente o necessário: nada pode mudar em relação ao livre.
    out.append(caso("ap-m1-exato", M1, c1 + g1, passos))
    for d in (140, 60):
        out.append(caso("ap-m1-nodet-d%d" % d, M1, cn + d, passos, showMetricDetail=False))
    for d in (240, 60):
        out.append(caso("ap-m1-s15-d%d" % d, M1, cs + d, passos, s=1.5, largura=690))
    #: 6' — teto pequeno (160) com 12 métricas, sob aperto de tela.
    out.append(caso("ap-m12-160-d42", M12, c12 + 42, passos12, drawerMaxHeight=160))
    #: 6' — conteúdo curto acima da grade, teto alto: o limite é o topo.
    out.append(caso("ap-curto-d0", MC, cc, passos12, drawerMaxHeight=480))
    out.append(caso("ap-curto-d51", MC, cc + 51, passos12, drawerMaxHeight=480))
    #: item 1 com grade de uma linha e H == altura fechada.
    out.append(caso("ap-m1-d0", M1, c1, passos))
    #: 1' — H menor que a própria view fechada.
    out.append(caso("menor-m1-h100", M1, 100, passos))
    out.append(caso("menor-m1-h1", M1, 1, passos))
    #: piso — sem primário, o espaço do topo à base da grade não comporta métrica.
    out.append(caso("piso-mp-fechada", MP, cp, passos))
    out.append(caso("piso-mp-h1", MP, 1, passos))
    #: item 5 — clique real. Primeiro o controle do instrumento (pílula
    #: descoberta, gaveta fechada), depois o clique sobre o painel.
    out.append(caso("mouse-m1", M1, c1 + 142, [
        SNAP("closed"),
        clique_real_na_pilula(S1, "ctl-abre"),
        clique_real_em("Collapse", "ctl-fecha"),
        abrir(OCT),
        clique_real_na_pilula(S1, "sobre-o-painel"),
        clique_real_em("Collapse", "fechado")]))
    #: item 9 — trocar de provider e fechar, sob orçamento apertado.
    out.append(caso("troca-m1", M1, c1 + 142, [
        SNAP("closed"),
        abrir(S1, "s1"),
        {"op": "clickText", "value": OCT["display_name"]},
        {"op": "wait", "ms": 700, "name": "oct"},
        clique_real_em("Collapse", "fechado")]))
    #: o orçamento muda com a gaveta aberta (tela/rotação/escala em uso).
    out.append(caso("dyn-m1", M1, H_LIVRE, [
        SNAP("closed"), abrir(OCT, "livre"),
        {"op": "setHeightBudget", "value": c1 + 60, "name": "apertado", "ms": 700},
        {"op": "setHeightBudget", "value": c1 + 142, "name": "medio", "ms": 700},
        {"op": "setHeightBudget", "value": H_LIVRE, "name": "devolvido", "ms": 700}]))
    return out


# --------------------------------------------------------------------------- #
# Bancada
# --------------------------------------------------------------------------- #

class Node:
    __slots__ = ("id", "parent", "kind", "text", "x", "y", "w", "h", "clip",
                 "interactive", "color", "opacity")

    def __init__(self, fields: list):
        self.id = int(fields[0])
        self.parent = int(fields[1])
        self.kind = fields[2]
        self.text = json.loads(fields[3])
        self.x = float(fields[4])
        self.y = float(fields[5])
        self.w = float(fields[6])
        self.h = float(fields[7])
        self.clip = fields[8] == "1"
        self.interactive = fields[9] == "true"
        self.color = fields[10] if len(fields) > 10 else ""
        self.opacity = float(fields[11]) if len(fields) > 11 and fields[11] else 1.0

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def right(self) -> float:
        return self.x + self.w

    def __repr__(self) -> str:
        return "<%s#%d y=%g..%g %r>" % (self.kind, self.id, self.y, self.bottom, self.text)


class Snap:
    """Censo de um estado da view."""

    def __init__(self, name: str, s: float, H):
        self.name = name
        self.s = s          #: escala informada à view neste caso
        self.H = H          #: orçamento informado no INÍCIO do caso
        self.props: dict = {}
        self.iw = self.ih = 0.0
        self.nodes: list[Node] = []
        self._by_id: dict[int, Node] = {}
        self._kids: dict[int, list[int]] = {}
        self.log: list[str] = []   #: linhas MOUSE/CLICK/HB emitidas ANTES deste censo

    def finish(self) -> "Snap":
        self._by_id = {n.id: n for n in self.nodes}
        for n in self.nodes:
            self._kids.setdefault(n.parent, []).append(n.id)
        return self

    # -- medidas da view ---------------------------------------------------
    @property
    def altura(self) -> float:
        """Altura REAL ocupada: implicitHeight (não escalado) × s."""
        return self.ih * self.s

    @property
    def largura(self) -> float:
        return self.iw * self.s

    def prop(self, name: str):
        return self.props.get(name)

    @property
    def texts(self) -> list[str]:
        return [n.text for n in self.nodes if n.text]

    @property
    def conteudo(self) -> list[str]:
        """Textos desenhados, MENOS a idade do rodapé (`updated … ago`), que anda
        com o relógio de parede entre dois casos e não é conteúdo do contrato."""
        return [t for t in self.texts if not t.strip().lower().startswith("updated")]

    def com_texto(self, texto: str) -> list[Node]:
        alvo = texto.strip().upper()
        return [n for n in self.nodes if n.text.strip().upper() == alvo]

    def subtree(self, nid: int) -> list[Node]:
        out = [self._by_id[nid]]
        for k in self._kids.get(nid, []):
            out.extend(self.subtree(k))
        return out

    def pai(self, n: Node):
        return self._by_id.get(n.parent)

    def ancestrais(self, n: Node) -> list[Node]:
        out, cur = [], self._by_id.get(n.parent)
        while cur is not None and len(out) < 40:
            out.append(cur)
            cur = self._by_id.get(cur.parent)
        return out

    # -- estrutura ---------------------------------------------------------
    def grade(self) -> Node:
        gs = [n for n in self.nodes if n.kind == "QQuickGrid"]
        assert len(gs) == 1, "esperava UMA grade de pílulas; achei %d" % len(gs)
        return gs[0]

    def painel(self, prov: dict):
        """O painel da gaveta do provider: ancestral com clip mais próximo da
        linha de status (`<ID>-PLAN`), que só existe na gaveta. ``None`` se a
        gaveta não está desenhada."""
        status = self.com_texto(prov["plan"])
        if not status:
            return None
        assert len(status) == 1, (
            "a linha de status %r aparece %d vezes: o marcador da gaveta não é "
            "único" % (prov["plan"], len(status)))
        for a in self.ancestrais(status[0]):
            if a.clip:
                return a
        return None

    def dentro(self, painel: Node) -> list[Node]:
        return self.subtree(painel.id)[1:]

    def metricas(self, prov: dict) -> list[int]:
        """Índices (1-based) das métricas DESENHADAS no painel, de cima para baixo."""
        p = self.painel(prov)
        if p is None:
            return []
        curto = prov["display_name"].split()[-1]
        pat = re.compile(r"^%s M(\d+)$" % re.escape(curto), re.I)
        achados = []
        for n in self.dentro(p):
            m = pat.match(n.text.strip())
            if m:
                achados.append((n.y, int(m.group(1))))
        return [ix for _, ix in sorted(achados)]

    def contador(self, prov: dict):
        """(nó, N) do `+N more` dentro do painel, ou ``None``."""
        p = self.painel(prov)
        if p is None:
            return None
        cs = [(n, int(_COUNTER.match(n.text.strip()).group(1)))
              for n in self.dentro(p) if _COUNTER.match(n.text.strip())]
        assert len(cs) <= 1, "mais de um contador no painel: %r" % (cs,)
        return cs[0] if cs else None

    def leituras(self, prov: dict) -> list[Node]:
        p = self.painel(prov)
        if p is None:
            return []
        return [n for n in self.dentro(p) if n.text.strip() in ("Elapsed:", "Pace:")]

    def collapse(self, prov: dict):
        """(texto, botão) do `Collapse` dentro do painel."""
        p = self.painel(prov)
        if p is None:
            return None
        ts = [n for n in self.dentro(p) if n.text.strip() == "Collapse"]
        if not ts:
            return None
        return ts[0], (self.pai(ts[0]) or ts[0])

    def rodape(self) -> list[Node]:
        """Os três elementos do rodapé (e os botões que envolvem os dois últimos)."""
        out = [n for n in self.nodes if n.text.strip().lower().startswith("updated")]
        for t in ("Copy keybind", "↻"):
            for n in self.com_texto(t):
                out.append(n)
                if self.pai(n) is not None:
                    out.append(self.pai(n))
        return out

    def recortados(self, painel: Node) -> list[Node]:
        """Nós com conteúdo (texto ou barra) do painel que saem do retângulo dele."""
        fora = []
        for n in self.dentro(painel):
            if not (n.text or n.kind == "Meter"):
                continue
            if n.y < painel.y - TOL or n.bottom > painel.bottom + TOL:
                fora.append(n)
        return fora

    def rolaveis(self) -> list[Node]:
        return [n for n in self.nodes if _SCROLLER.search(n.kind)]


def _parse(stdout: str, cases: list) -> dict:
    meta = {c["name"]: c for c in cases}
    casos: dict[str, dict[str, Snap]] = {}
    case = snap = None
    pend: list[str] = []
    for raw in stdout.splitlines():
        if " qml: " in raw:
            raw = raw.split(" qml: ", 1)[1]
        line = raw.strip()
        if line.startswith("===CASE|"):
            case = line[len("===CASE|"):-3]
            casos.setdefault(case, {})
            snap, pend = None, []
        elif line.startswith("===CASE_END|"):
            case = snap = None
        elif line.startswith("===SNAP|"):
            assert case is not None, "SNAP fora de um CASE"
            c = meta.get(case, {})
            snap = Snap(line[len("===SNAP|"):-3], c.get("s", 1), c.get("heightBudget"))
            snap.log, pend = pend, []
            casos[case][snap.name] = snap
        elif line.startswith("===SNAP_END|"):
            if snap is not None:
                snap.finish()
            snap = None
        elif snap is not None and line.startswith("PROP|"):
            parts = line.split("|")
            if len(parts) >= 4:
                try:
                    snap.props[parts[1]] = json.loads(parts[3])
                except ValueError:
                    snap.props[parts[1]] = parts[3]
                if "IW" in parts:
                    k = parts.index("IW")
                    snap.iw, snap.ih = float(parts[k + 1]), float(parts[k + 2])
        elif snap is not None and line.startswith("NODE|"):
            snap.nodes.append(Node(line.split("|")[1:]))
        elif case is not None and line.startswith(
                ("MOUSE", "CLICK", "HB_", "VIEW_ERR")):
            pend.append(line)
            casos[case].setdefault("__log__", []).append(line)  # type: ignore[arg-type]
    return casos


def _run(cases: list) -> dict:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("WAYLAND_DISPLAY", None)
    env["T48_PLUG_DIR"] = str(PLUGIN_DIR)
    payload = json.dumps(cases, ensure_ascii=False)
    parts = [payload[i:i + 60000] for i in range(0, len(payload), 60000)] or ["[]"]
    for k, part in enumerate(parts):
        env["T48_CASES_%d" % k] = part
    env["T48_CASES_PARTS"] = str(len(parts))
    env["T48_STATE_DIR"] = tempfile.mkdtemp(prefix="t48-state-")
    try:
        proc = subprocess.run([_QUICK, "-p", str(HARNESS)], capture_output=True,
                              text=True, env=env, timeout=1200)
    except subprocess.TimeoutExpired:
        pytest.fail("o harness QML não terminou em 1200s — a view provavelmente não "
                    "monta. Sem view não há comportamento a verificar.")
    out = _ANSI.sub("", proc.stdout + proc.stderr)
    parsed = _parse(out, cases)
    faltando = [c["name"] for c in cases if c["name"] not in parsed]
    assert not faltando, ("a sonda não montou os casos %r; rc=%s\nsaída(tail)=%s"
                          % (faltando, proc.returncode, out[-1500:]))
    return parsed


@pytest.fixture(scope="session")
def livre():
    """1ª passada: orçamento folgado."""
    return _run(CASOS_LIVRES)


@pytest.fixture(scope="session")
def apertado(livre):
    """2ª passada: orçamentos derivados das medidas da 1ª."""
    med = {}
    for ref in REFERENCIAS:
        med[ref] = (snap_of(livre, ref, "closed").altura, snap_of(livre, ref, "open").altura)
        assert med[ref][0] > 0 and med[ref][1] > med[ref][0], (
            "a referência %r não mediu uma gaveta que cresce (fechada=%g, aberta=%g): "
            "sem isso não há orçamento apertado a derivar" % ((ref,) + med[ref]))
    return _run(casos_apertados(med))


def snap_of(bancada: dict, caso_: str, nome: str) -> Snap:
    assert caso_ in bancada, "caso %r não existe na sonda" % caso_
    d = bancada[caso_]
    assert nome in d, "o caso %r não censou %r; censos=%r" % (
        caso_, nome, sorted(k for k in d if k != "__log__"))
    return d[nome]


def log_of(bancada: dict, caso_: str) -> list:
    return bancada[caso_].get("__log__", [])


# --------------------------------------------------------------------------- #
# Âncoras comuns
# --------------------------------------------------------------------------- #

def exigir_aberta(s: Snap, prov: dict) -> Node:
    assert s.prop("openDrawerId") == prov["id"], (
        "a gaveta não está aberta em %r: openDrawerId=%r"
        % (prov["id"], s.prop("openDrawerId")))
    p = s.painel(prov)
    assert p is not None, (
        "a gaveta de %r não desenhou painel com a linha de status: %s"
        % (prov["id"], s.texts[:14]))
    return p


def exigir_caso_discriminante(livre, nome: str, fechada: Snap) -> float:
    """O caso só prova algo se a gaveta LIVRE não couber no orçamento dele, e se o
    orçamento não for menor que a view fechada. Devolve H."""
    H = fechada.H
    ref = REFERENCIA[nome]
    c = snap_of(livre, ref, "closed").altura
    o = snap_of(livre, ref, "open").altura
    assert abs(fechada.altura - c) <= TOL, (
        "%s: a view fechada mede %g e a referência livre mede %g: o orçamento "
        "mudou a view FECHADA" % (nome, fechada.altura, c))
    assert H >= c - TOL, "%s: H=%g menor que a view fechada (%g)" % (nome, H, c)
    assert o > H + 1, (
        "%s: a gaveta livre (%g) cabe em H=%g: o caso não aperta nada" % (nome, o, H))
    return H


def exigir_cabe(s: Snap, H: float, contexto: str) -> None:
    """Item 1 — a altura real da view não ultrapassa o orçamento."""
    assert s.altura <= H + TOL, (
        "%s: com a gaveta `down` aberta a view ocupa %g px reais "
        "(implicitHeight=%g × s=%g) e o orçamento é H=%g: estoura em %g px — o host "
        "recorta o excesso em silêncio (rodapé fora da tela, Collapse cortado)"
        % (contexto, s.altura, s.ih, s.s, H, s.altura - H))


def disponivel(fechada: Snap) -> float:
    """6' — a altura máxima da gaveta `down` neste caso: tudo o que há do topo da
    view (y=0) até a base da grade, mais a folga abaixo (H − altura fechada)."""
    return fechada.grade().bottom + max(fechada.H - fechada.altura, 0.0)


def passo_de_metrica(ref_aberta: Snap, prov: dict) -> float:
    """Altura de UMA linha de métrica, medida na gaveta livre (distância entre
    dois rótulos consecutivos). É a unidade de 'cabia mais uma'."""
    p = ref_aberta.painel(prov)
    curto = prov["display_name"].split()[-1]
    pat = re.compile(r"^%s M\d+$" % re.escape(curto), re.I)
    ys = sorted(n.y for n in ref_aberta.dentro(p) if pat.match(n.text.strip()))
    assert len(ys) >= 2, "a referência livre não tem duas métricas para medir o passo"
    return ys[1] - ys[0]


def exigir_grupo(livre, nome: str, fechada: Snap, grupo: str) -> float:
    """Confere que o caso pertence ao grupo declarado (CHEIOS/TOPO) e devolve o
    disponível. Um caso na fronteira não discrimina e é recusado."""
    prov = prov_de(nome)
    ref = snap_of(livre, REFERENCIA[nome], "open")
    livre_h = exigir_aberta(ref, prov).h
    disp = disponivel(fechada)
    passo = passo_de_metrica(ref, prov)
    if grupo == "cheio":
        assert livre_h + passo <= disp, (
            "%s: a gaveta livre mede %g e o disponível (topo da view até a base da "
            "grade + folga) é %g: o caso não está folgado por uma linha (%g) e não "
            "serve ao item 4'" % (nome, livre_h, disp, passo))
    else:
        assert livre_h > disp + TOL, (
            "%s: a gaveta livre (%g) cabe no disponível (%g): o caso não exercita o "
            "limite do topo (6')" % (nome, livre_h, disp))
    return disp


def par(apertado_, nome: str):
    return snap_of(apertado_, nome, "closed"), snap_of(apertado_, nome, "open")


# --------------------------------------------------------------------------- #
# 0. Antipassividade
# --------------------------------------------------------------------------- #

def test_ctrl_artefatos_existem():
    """Falha rápido se a view ou a sonda sumiram: revert não pode virar SKIP."""
    assert (PLUGIN_DIR / "content" / "Widget.qml").is_file(), "content/Widget.qml ausente"
    assert HARNESS.is_file(), "sonda QML ausente: %s" % HARNESS


def test_ctrl_detectores():
    """Controle de vacuidade do contador e do detector de scroll."""
    for texto in ("+1 more", "+3 more", "+12 MORE"):
        assert _COUNTER.match(texto), "o detector não reconhece %r" % texto
    for texto in ("more", "+ more", "3 more", "+3"):
        assert not _COUNTER.match(texto), "o detector casa %r por engano" % texto
    for tipo in ("QQuickFlickable", "QQuickScrollView", "QQuickListView", "QQuickScrollBar"):
        assert _SCROLLER.search(tipo), "o detector de scroll não reconhece %r" % tipo
    assert not _SCROLLER.search("QQuickRectangle")


def test_ctrl_view_monta_e_gaveta_abre(livre):
    """Âncora de toda a suíte: view montada, gaveta `down` abre, medidas resolvem."""
    f = snap_of(livre, "livre-m1", "closed")
    a = snap_of(livre, "livre-m1", "open")
    assert f.prop("drawerDirection") == "down", f.prop("drawerDirection")
    assert f.prop("openDrawerId") == "", "o censo inicial deveria estar sem gaveta"
    assert f.altura > 50, "a view fechada não resolveu altura: %g" % f.altura
    assert f.painel(OCT) is None, "há painel de gaveta com a gaveta fechada"
    assert f.rodape(), "o rodapé não foi encontrado: %s" % f.texts[-6:]
    assert any(n.text.strip() == "Copy keybind" for n in f.rodape())
    p = exigir_aberta(a, OCT)
    assert p.h > 20 and p.w > 100, "painel sem tamanho: %r" % p
    assert a.collapse(OCT) is not None, "a gaveta `down` não tem `Collapse`"
    assert a.metricas(OCT), "a gaveta não desenhou nenhuma métrica: %s" % a.texts
    assert a.com_texto("Pill Alpha"), "o primário sumiu ao abrir a gaveta"


def test_ctrl_instrumento_de_clique_real(apertado):
    """O clique REAL chega à view: numa pílula descoberta ele abre a gaveta, e no
    `Collapse` ele a fecha. Sem isto, 'o clique não atravessou' poderia significar
    'o clique não foi entregue a ninguém'."""
    abriu = snap_of(apertado, "mouse-m1", "ctl-abre")
    assert abriu.prop("openDrawerId") == S1["id"], (
        "clique real na pílula descoberta não abriu a gaveta (openDrawerId=%r; "
        "log=%r)" % (abriu.prop("openDrawerId"), abriu.log))
    fechou = snap_of(apertado, "mouse-m1", "ctl-fecha")
    assert fechou.prop("openDrawerId") == "", (
        "clique real no `Collapse` não fechou a gaveta: %r" % (fechou.prop("openDrawerId"),))


# --------------------------------------------------------------------------- #
# 1. Controles: o que já valia e tem de continuar valendo
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("ref", ("livre-m1", "livre-m3", "livre-m1-nodet", "livre-m1-s15"))
def test_ctrl_espaco_de_sobra_empurra(livre, ref):
    """Item 3 — com espaço de sobra a gaveta EMPURRA: fica abaixo da grade, não
    sobrepõe pílulas, e a view aberta é mais alta que a fechada."""
    f, a = snap_of(livre, ref, "closed"), snap_of(livre, ref, "open")
    p = exigir_aberta(a, OCT)
    g = a.grade()
    assert p.y >= g.bottom - TOL, (
        "com orçamento folgado o painel começa em y=%g e a grade termina em %g: a "
        "gaveta sobrepõe pílulas sem necessidade" % (p.y, g.bottom))
    assert a.altura > f.altura + p.h - TOL, (
        "a gaveta não empurrou: fechada=%g, aberta=%g, painel=%g"
        % (f.altura, a.altura, p.h))
    assert not a.recortados(p), "conteúdo recortado no painel livre: %r" % a.recortados(p)
    assert a.contador(OCT) is None, (
        "8 métricas no teto padrão e orçamento folgado não deveriam ter corte: %r"
        % (a.contador(OCT),))
    assert a.metricas(OCT)[0] == 8, "a líder (M8, 80%%) não é a primeira: %r" % a.metricas(OCT)
    assert sorted(a.metricas(OCT)) == list(range(1, 9)), a.metricas(OCT)


def test_ctrl_h_grande_igual_a_sem_limite(livre):
    """Item 7 — H=5000 não muda nada: mesma altura e mesmo conteúdo que um
    orçamento que nenhuma view alcança."""
    for censo in ("closed", "open"):
        a, b = snap_of(livre, "livre-m1-5000", censo), snap_of(livre, "livre-m1", censo)
        assert abs(a.altura - b.altura) <= TOL, (
            "%s: H=5000 dá %g px e H=%d dá %g" % (censo, a.altura, H_LIVRE, b.altura))
        assert a.conteudo == b.conteudo, "%s: o conteúdo desenhado difere com H=5000" % censo
    a, b = snap_of(livre, "livre-m1-5000", "open"), snap_of(livre, "livre-m1", "open")
    assert a.metricas(OCT) == b.metricas(OCT) and len(a.metricas(OCT)) == 8


def test_ctrl_painel_livre_respeita_o_teto(livre):
    """Sem aperto de tela vale o teto da setting (× s), como na rodada 4."""
    for ref, s in (("livre-m1", 1), ("livre-m1-nodet", 1), ("livre-m1-s15", 1.5)):
        a = snap_of(livre, ref, "open")
        p = exigir_aberta(a, OCT)
        assert p.h <= 320 * s + TOL, "%s: painel de %g px com teto %g" % (ref, p.h, 320 * s)


def test_ctrl_espaco_exato_empurra(livre, apertado):
    """Item 3 no limite — se H é exatamente o que a gaveta inteira precisa, nada
    muda em relação ao livre: mesma altura, mesmas métricas, sem sobrepor."""
    ref = snap_of(livre, "livre-m1", "open")
    f, a = par(apertado, "ap-m1-exato")
    p = exigir_aberta(a, OCT)
    assert abs(f.H - ref.altura) <= TOL, "o caso não é o de espaço exato"
    assert abs(a.altura - ref.altura) <= TOL, (
        "com H exatamente igual ao necessário (%g) a view mede %g em vez de %g"
        % (f.H, a.altura, ref.altura))
    assert a.metricas(OCT) == ref.metricas(OCT), (
        "métricas com espaço exato %r × livre %r" % (a.metricas(OCT), ref.metricas(OCT)))
    assert a.contador(OCT) is None, "corte anunciado com espaço suficiente"
    assert p.y >= a.grade().bottom - TOL, "sobrepôs a grade com espaço suficiente"


@pytest.mark.parametrize("direcao", ("left", "right"))
def test_ctrl_lateral_ignora_orcamento_de_altura(livre, direcao):
    """Item 8 — `left`/`right` não são afetados por `heightBudget`: mesmas alturas
    e mesmo conteúdo com H pequeno (300, menor que a própria view) ou grande."""
    for censo in ("closed", "open"):
        p, g = (snap_of(livre, "lat-%s-300" % direcao, censo),
                snap_of(livre, "lat-%s-5000" % direcao, censo))
        assert p.prop("drawerDirection") == direcao, p.prop("drawerDirection")
        assert abs(p.altura - g.altura) <= TOL, (
            "%s/%s: altura %g com H=300 e %g com H=5000" % (direcao, censo, p.altura, g.altura))
        assert abs(p.largura - g.largura) <= TOL, (
            "%s/%s: largura %g com H=300 e %g com H=5000" % (direcao, censo, p.largura, g.largura))
        assert p.conteudo == g.conteudo, "%s/%s: conteúdo difere com H pequeno" % (direcao, censo)
        assert ([(n.kind, n.x, n.y, n.w, n.h) for n in p.nodes]
                == [(n.kind, n.x, n.y, n.w, n.h) for n in g.nodes]), (
            "%s/%s: a geometria da árvore difere com H pequeno" % (direcao, censo))
    aberto = snap_of(livre, "lat-%s-300" % direcao, "open")
    exigir_aberta(aberto, OCT)
    fechado = snap_of(livre, "lat-%s-300" % direcao, "closed")
    assert abs(aberto.altura - fechado.altura) <= TOL, (
        "%s: a reserva lateral mudou ao abrir (%g -> %g)"
        % (direcao, fechado.altura, aberto.altura))


def test_ctrl_fechar_devolve_altura_fechada(livre):
    """Item 9 (sem aperto) — recolher devolve a altura fechada, e abrir depois um
    provider pequeno não herda a altura do grande."""
    for ref in ("livre-m1", "livre-m3"):
        f = snap_of(livre, ref, "closed")
        a = snap_of(livre, ref, "open")
        r = snap_of(livre, ref, "recolhido")
        s1 = snap_of(livre, ref, "s1")
        assert r.prop("openDrawerId") == "", "o `Collapse` não fechou a gaveta"
        assert abs(r.altura - f.altura) <= TOL, (
            "%s: fechada=%g, depois de recolher=%g" % (ref, f.altura, r.altura))
        exigir_aberta(s1, S1)
        assert f.altura < s1.altura < a.altura - 1, (
            "%s: o provider pequeno abriu com %g px (fechada=%g, grande=%g)"
            % (ref, s1.altura, f.altura, a.altura))


def test_ctrl_largura_nao_muda_com_orcamento_de_altura(livre, apertado):
    """SPEC T48.5 — a largura do popout não depende do orçamento de altura."""
    ref = snap_of(livre, "livre-m1", "open")
    for nome in APERTADOS_M1:
        a = snap_of(apertado, nome, "open")
        assert abs(a.largura - ref.largura) <= TOL, (
            "%s: largura %g × %g no livre" % (nome, a.largura, ref.largura))


# --------------------------------------------------------------------------- #
# 2. T48 — a view cabe no orçamento
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("nome", APERTADOS)
def test_tela_view_aberta_cabe_no_orcamento(livre, apertado, nome):
    """**O sintoma.** Item 1' — com `down`, H informado (≥ view fechada) e a gaveta
    aberta, a altura real da view não ultrapassa H; e a gaveta está de fato
    aberta (uma view que se recusasse a abrir também 'caberia')."""
    f, a = par(apertado, nome)
    H = exigir_caso_discriminante(livre, nome, f)
    exigir_aberta(a, prov_de(nome))
    exigir_cabe(a, H, nome)
    assert a.altura >= f.altura - TOL, (
        "%s: a view aberta (%g) ficou MENOR que a fechada (%g)" % (nome, a.altura, f.altura))


@pytest.mark.parametrize("nome", APERTADOS)
def test_tela_collapse_e_rodape_inteiros(livre, apertado, nome):
    """Item 2 — `Collapse` inteiro dentro do painel; rodapé inteiro dentro da view
    E dentro do orçamento (é o que estava fora da tela no shell real), e não
    coberto pela gaveta."""
    prov = prov_de(nome)
    f, a = par(apertado, nome)
    H = exigir_caso_discriminante(livre, nome, f)
    p = exigir_aberta(a, prov)
    exigir_cabe(a, H, nome)
    col = a.collapse(prov)
    assert col is not None, "%s: a gaveta `down` aberta não tem `Collapse`" % nome
    for n in col:
        assert p.y - TOL <= n.y and n.bottom <= p.bottom + TOL, (
            "%s: `Collapse` recortado pelo painel: %r fora de y=%g..%g"
            % (nome, n, p.y, p.bottom))
        assert n.bottom <= H + TOL, "%s: `Collapse` abaixo do orçamento: %r" % (nome, n)
    rod = a.rodape()
    assert any(n.text.strip() == "Copy keybind" for n in rod), "%s: rodapé ausente" % nome
    assert any(n.text.strip().lower().startswith("updated") for n in rod), (
        "%s: texto 'updated … ago' ausente" % nome)
    limite = min(a.altura, H)
    for n in rod:
        assert n.y >= p.bottom - TOL, (
            "%s: o painel da gaveta cobre o rodapé: %r começa antes do fim do painel "
            "(%g)" % (nome, n, p.bottom))
        assert n.bottom <= limite + TOL, (
            "%s: rodapé fora da área visível: %r termina em %g e a view/orçamento "
            "acaba em %g" % (nome, n, n.bottom, limite))


@pytest.mark.parametrize("nome", APERTADOS)
def test_tela_gaveta_sobe_pela_base(livre, apertado, nome):
    """Item 4' — sem espaço abaixo da grade, a gaveta não aumenta a view além de
    H: SOBE a partir da base (o fundo do painel nunca fica acima do fim da
    grade), sobre a grade e, se a gaveta for mais alta que grade + folga, sobre o
    que está acima da grade; é opaca; não passa do topo da view; sem scroll.

    REGRA ANTIGA (caiu): este teste se chamava `…_sobrepoe_a_grade_pela_base` e
    exigia `painel.y >= topo da grade` — a gaveta só podia cobrir a grade. Foi
    reprovada no shell real: grade + folga davam 200 px e uma métrica com
    contador precisa de 219, então a gaveta só mostrava `+2 more`."""
    prov = prov_de(nome)
    f, a = par(apertado, nome)
    H = exigir_caso_discriminante(livre, nome, f)
    p = exigir_aberta(a, prov)
    exigir_cabe(a, H, nome)
    g = a.grade()
    folga = H - f.altura
    assert p.bottom >= g.bottom - TOL, (
        "%s: o painel termina em %g, ACIMA do fim da grade (%g): não está ancorado "
        "embaixo" % (nome, p.bottom, g.bottom))
    assert p.bottom <= g.bottom + folga + TOL, (
        "%s: o painel desce até %g; a grade termina em %g e a folga é %g"
        % (nome, p.bottom, g.bottom, folga))
    livre_y = exigir_aberta(snap_of(livre, REFERENCIA[nome], "open"), prov).y
    assert p.y < livre_y - TOL, (
        "%s: a gaveta livre não cabe abaixo da grade e o painel não subiu (painel "
        "y=%g; com H grande começa em y=%g)" % (nome, p.y, livre_y))
    if nome != "ap-m1-quase":
        #: no caso `quase` faltam só 4 px, menos que o vão entre grade e painel:
        #: o painel sobe sem chegar a cobrir a grade.
        assert p.y < g.bottom - TOL, (
            "%s: o painel não sobe sobre a grade (painel y=%g, grade até %g)"
            % (nome, p.y, g.bottom))
    if p.h > g.h + folga + 1:
        assert p.y < g.y - TOL, (
            "%s: a gaveta (%g px) é mais alta que grade + folga (%g) e começa em "
            "y=%g, sem subir acima do topo da grade (%g)"
            % (nome, p.h, g.h + folga, p.y, g.y))
    assert p.y >= -TOL, "%s: o painel passa do topo da view (y=%g)" % (nome, p.y)
    assert p.h <= disponivel(f) + TOL, (
        "%s: painel de %g px, mais alto que tudo do topo da view até a base da "
        "grade + folga (%g)" % (nome, p.h, disponivel(f)))
    assert re.fullmatch(r"#(?:ff)?[0-9a-f]{6}", p.color.lower()), (
        "%s: o painel sobreposto não tem fundo opaco (cor=%r): o conteúdo aparece "
        "por baixo" % (nome, p.color))
    assert p.opacity == 1, "%s: painel sobreposto com opacidade %g" % (nome, p.opacity)
    assert not a.rolaveis(), "%s: há superfície rolável: %r" % (nome, a.rolaveis())


@pytest.mark.parametrize("nome", CHEIOS)
def test_tela_aperto_de_tela_nao_corta_metricas(livre, apertado, nome):
    """Item 4' — aperto de tela, por si só, NÃO corta: com H ≥ fechada e espaço
    entre o topo da view e a base da grade + folga, a gaveta `down` desenha as
    MESMAS métricas e leituras (e o mesmo contador, se o teto já cortava) que com
    H grande, com a mesma altura de painel — e a view fica ≤ H.

    REGRA ANTIGA (caiu): o que não coubesse em grade + folga era cortado e
    anunciado por `+N more` (nesta bancada, `+5 more` com 142 px de folga)."""
    prov = prov_de(nome)
    f, a = par(apertado, nome)
    H = exigir_caso_discriminante(livre, nome, f)
    exigir_grupo(livre, nome, f, "cheio")
    p = exigir_aberta(a, prov)
    exigir_cabe(a, H, nome)
    ref = snap_of(livre, REFERENCIA[nome], "open")
    pr = exigir_aberta(ref, prov)
    assert a.metricas(prov) == ref.metricas(prov), (
        "%s: sob aperto de tela a gaveta desenha %r e com H grande %r: a tela "
        "cortou métrica" % (nome, a.metricas(prov), ref.metricas(prov)))
    assert ([n.text for n in a.leituras(prov)] == [n.text for n in ref.leituras(prov)]), (
        "%s: leituras sob aperto %r × H grande %r"
        % (nome, [n.text for n in a.leituras(prov)], [n.text for n in ref.leituras(prov)]))
    ca, cr = a.contador(prov), ref.contador(prov)
    assert (ca and ca[1]) == (cr and cr[1]), (
        "%s: contador sob aperto %r × H grande %r"
        % (nome, ca and ca[0].text, cr and cr[0].text))
    assert abs(p.h - pr.h) <= TOL, (
        "%s: painel de %g px sob aperto e %g com H grande" % (nome, p.h, pr.h))
    assert not a.recortados(p), "%s: conteúdo recortado: %r" % (nome, a.recortados(p))


@pytest.mark.parametrize("nome", TOPO)
def test_tela_corte_so_pelo_topo_do_conteudo(livre, apertado, nome):
    """Item 6' — quando a gaveta livre é mais alta que tudo o que há do topo da
    view até a base da grade + folga, ela não passa do topo: algo cede — as
    leituras primeiro e, se ainda não couber, métricas pela cauda, anunciadas
    por `+N more` — e o corte não desperdiça espaço (não sobra uma linha inteira
    de métrica sem uso)."""
    prov = prov_de(nome)
    f, a = par(apertado, nome)
    H = exigir_caso_discriminante(livre, nome, f)
    disp = exigir_grupo(livre, nome, f, "topo")
    p = exigir_aberta(a, prov)
    exigir_cabe(a, H, nome)
    ref = snap_of(livre, REFERENCIA[nome], "open")
    assert p.y >= -TOL and p.h <= disp + TOL, (
        "%s: painel y=%g h=%g passa do topo (disponível %g)" % (nome, p.y, p.h, disp))
    cont = a.contador(prov)
    omitidas = len(ref.metricas(prov)) - len(a.metricas(prov))
    leituras_cedidas = len(ref.leituras(prov)) - len(a.leituras(prov))
    assert omitidas >= 0 and leituras_cedidas >= 0, (
        "%s: sob limite do topo a gaveta desenha MAIS que com H grande" % nome)
    assert omitidas > 0 or leituras_cedidas > 0, (
        "%s: a gaveta livre (%g px) não cabe em %g e nada cedeu (métricas %r, "
        "leituras %d): o painel teria de estar recortado"
        % (nome, ref.painel(prov).h, disp, a.metricas(prov), len(a.leituras(prov))))
    assert not a.recortados(p), "%s: conteúdo recortado: %r" % (nome, a.recortados(p))
    if omitidas > 0:
        assert cont is not None, (
            "%s: %d métrica(s) a menos que com H grande e nenhum `+N more`: %r"
            % (nome, omitidas, a.metricas(prov)))
        assert cont[1] + len(a.metricas(prov)) == len(prov["metrics"]), (
            "%s: `%s` + %d desenhadas != %d" % (nome, cont[0].text, len(a.metricas(prov)),
                                                 len(prov["metrics"])))
        passo = passo_de_metrica(ref, prov)
        assert disp - p.h < passo, (
            "%s: o painel mede %g e o disponível é %g: sobram %g px, mais que uma "
            "linha de métrica (%g) — cortou métrica que cabia"
            % (nome, p.h, disp, disp - p.h, passo))
    else:
        cr = ref.contador(prov)
        assert (cont and cont[1]) == (cr and cr[1]), (
            "%s: nenhuma métrica a menos que com H grande, mas o contador mudou: "
            "%r × %r" % (nome, cont and cont[0].text, cr and cr[0].text))


@pytest.mark.parametrize("nome", APERTADOS)
def test_tela_corte_pela_cauda_anunciado(livre, apertado, nome):
    """Itens 4'/6' — o que não é desenhado é a CAUDA e é anunciado por `+N more`,
    com N = métricas omitidas; a líder continua primeiro; nada desenhado no
    painel sai do recorte dele (corte silencioso)."""
    prov = prov_de(nome)
    f, a = par(apertado, nome)
    H = exigir_caso_discriminante(livre, nome, f)
    p = exigir_aberta(a, prov)
    exigir_cabe(a, H, nome)
    total = len(prov["metrics"])
    lider = lider_de(prov)
    des = a.metricas(prov)
    cont = a.contador(prov)
    fora = a.recortados(p)
    assert not fora, "%s: conteúdo recortado em silêncio pelo painel: %r" % (nome, fora)
    assert len(set(des)) == len(des), "%s: métrica desenhada duas vezes: %r" % (nome, des)
    if len(des) < total:
        assert cont is not None, (
            "%s: %d de %d métricas desenhadas e nenhum `+N more`: corte silencioso"
            % (nome, len(des), total))
        assert cont[1] == total - len(des), (
            "%s: o contador diz +%d e faltam %d (desenhadas=%r de %d)"
            % (nome, cont[1], total - len(des), des, total))
    else:
        assert cont is None, "%s: contador %r sem métrica omitida" % (nome, cont[0])
    if des:
        assert des[0] == lider, "%s: a líder (M%d) não é a primeira: %r" % (nome, lider, des)
        resto = [i for i in range(1, total + 1) if i != lider]
        assert des[1:] == resto[:len(des) - 1], (
            "%s: o corte não foi pela cauda: desenhadas %r, esperado líder + %r"
            % (nome, des, resto[:len(des) - 1]))


def test_tela_mais_espaco_nunca_mostra_menos(livre, apertado):
    """Mais orçamento nunca desenha menos métricas; a série chega ao conteúdo
    de H grande assim que a gaveta cabe entre o topo e a base + folga (4'), e só
    corta enquanto ela não cabe (6').

    REGRA ANTIGA (caiu): a série inteira ficava abaixo do total, porque até a
    maior folga apertada cortava por aperto de tela."""
    ref = snap_of(livre, "livre-m1", "open")
    serie = []
    for d in FOLGAS_M1:
        f, a = par(apertado, "ap-m1-d%d" % d)
        H = exigir_caso_discriminante(livre, "ap-m1-d%d" % d, f)
        exigir_cabe(a, H, "ap-m1-d%d" % d)
        serie.append(len(a.metricas(OCT)))
    assert serie == sorted(serie), (
        "métricas desenhadas por folga %r = %r: mais espaço mostrou menos"
        % (FOLGAS_M1, serie))
    assert serie[-1] == len(ref.metricas(OCT)), (
        "com a maior folga (%d) a gaveta desenha %d métricas e com H grande %d"
        % (FOLGAS_M1[-1], serie[-1], len(ref.metricas(OCT))))
    assert serie[0] < serie[-1], (
        "a série %r não varia: o limite do topo (6') não cortou nada na menor folga"
        % (serie,))
    assert serie[0] >= 1, "na menor folga nenhuma métrica foi desenhada: %r" % (serie,)


def test_tela_escala_usa_pixels_reais(livre, apertado):
    """`heightBudget` está nos mesmos pixels escalados de `widthBudget`: com
    s=1.5 o que não pode passar de H é implicitHeight × s, não implicitHeight."""
    f, a = par(apertado, "ap-m1-s15-d240")
    H = exigir_caso_discriminante(livre, "ap-m1-s15-d240", f)
    p = exigir_aberta(a, OCT)
    exigir_cabe(a, H, "s=1.5")
    assert a.s == 1.5 and a.prop("s") == 1.5, "a escala não chegou à view"
    assert a.altura > f.altura + 1, (
        "s=1.5: havia 240 px de folga e a view não cresceu (%g -> %g): o orçamento "
        "foi comparado em unidades não escaladas" % (f.altura, a.altura))
    assert a.ih < H / 1.5 + TOL, "implicitHeight=%g com H/s=%g" % (a.ih, H / 1.5)
    assert not a.recortados(p), "s=1.5: conteúdo recortado: %r" % a.recortados(p)


def test_tela_clique_no_painel_nao_atravessa(livre, apertado):
    """Item 5 — um clique REAL sobre o painel `down`, num ponto que também está
    dentro de uma pílula coberta, não troca o provider aberto."""
    antes = snap_of(apertado, "mouse-m1", "open")
    depois = snap_of(apertado, "mouse-m1", "sobre-o-painel")
    fechada = snap_of(apertado, "mouse-m1", "closed")
    exigir_cabe(antes, fechada.H, "mouse-m1")
    p = exigir_aberta(antes, OCT)
    cliques = [l for l in depois.log if l.startswith("MOUSE|")]
    assert len(cliques) == 1, "esperava um clique real antes do censo: %r" % depois.log
    x, y = (float(v) for v in cliques[0].split("|")[1:3])
    pilulas = [n for n in antes.nodes if n.interactive
               and n.x <= x <= n.right and n.y <= y <= n.bottom
               and antes.grade().id in [a.id for a in antes.ancestrais(n)]]
    assert pilulas, "o ponto do clique (%g,%g) não está sobre nenhuma pílula" % (x, y)
    assert p.x <= x <= p.right and p.y + 1 <= y <= p.bottom - 1, (
        "o ponto do clique (%g,%g) não está sobre o painel (y=%g..%g): a gaveta não "
        "cobre a pílula, então não há o que atravessar" % (x, y, p.y, p.bottom))
    assert depois.prop("openDrawerId") == OCT["id"], (
        "o clique sobre o painel atravessou para a pílula de baixo: openDrawerId "
        "passou de %r para %r" % (OCT["id"], depois.prop("openDrawerId")))
    assert depois.conteudo == antes.conteudo, "o clique sobre o painel mudou o conteúdo"
    assert abs(depois.altura - antes.altura) <= TOL


@pytest.mark.parametrize("nome", ("menor-m1-h100", "menor-m1-h1"))
def test_tela_h_menor_que_a_fechada_nao_aumenta_a_view(livre, apertado, nome):
    """Item 1' — se a view fechada já excede H, abrir a gaveta não aumenta a view
    além da fechada: a gaveta sobe sobre o conteúdo, inteira dentro do painel, e
    o rodapé continua onde estava.

    REGRA ANTIGA (caiu): com H < fechada a gaveta ficava no piso (`+8 more`, sem
    métrica) e a view EXCEDIA a fechada (303 contra 258 nesta bancada)."""
    f, a = par(apertado, nome)
    assert f.H < f.altura - 1, "o caso não tem H menor que a view fechada"
    p = exigir_aberta(a, OCT)
    assert abs(a.altura - f.altura) <= TOL, (
        "%s: H=%g, fechada=%g e a view aberta mede %g: abrir aumentou (ou "
        "encolheu) a view" % (nome, f.H, f.altura, a.altura))
    assert p.y >= -TOL and p.h <= disponivel(f) + TOL, (
        "%s: painel y=%g h=%g passa do topo da view" % (nome, p.y, p.h))
    assert abs(p.bottom - a.grade().bottom) <= TOL, (
        "%s: sem folga o painel deveria terminar na base da grade (%g); termina em "
        "%g" % (nome, a.grade().bottom, p.bottom))
    assert not a.recortados(p), "%s: conteúdo recortado: %r" % (nome, a.recortados(p))
    assert a.collapse(OCT) is not None, "%s: sem `Collapse`" % nome
    cont = a.contador(OCT)
    assert (cont[1] if cont else 0) + len(a.metricas(OCT)) == len(OCT["metrics"])
    rf = sorted((n.text, n.y, n.h) for n in f.rodape() if not n.text.lower().startswith("updated"))
    ra = sorted((n.text, n.y, n.h) for n in a.rodape() if not n.text.lower().startswith("updated"))
    assert rf == ra, "%s: o rodapé mudou de lugar ao abrir: %r -> %r" % (nome, rf, ra)
    igual = snap_of(apertado, "ap-m1-d0", "open")
    assert a.conteudo == igual.conteudo, (
        "%s: com H < fechada o conteúdo difere do caso H == fechada" % nome)


@pytest.mark.parametrize("nome", ("piso-mp-fechada", "piso-mp-h1"))
def test_tela_piso_mostra_so_contador_e_collapse(livre, apertado, nome):
    """Piso (inalterado em 6') — num relatório sem primário, do topo da view à
    base da grade não cabe métrica alguma: a gaveta fica no piso — nome, linha de
    status, `+N more` com N = TOTAL de métricas e `Collapse`, tudo inteiro; e a
    view não passa de max(H, fechada).

    REGRA ANTIGA (caiu): o piso era exercitado com H < fechada num relatório com
    primário, e era 'o único caso em que a view pode exceder H'. Sob 4' a gaveta
    sobe sobre o conteúdo acima da grade, então aquele caso deixou de ser piso."""
    f, a = par(apertado, nome)
    ref = snap_of(livre, "livre-mp", "open")
    p = exigir_aberta(a, OCT)
    total = len(OCT["metrics"])
    passo = passo_de_metrica(ref, OCT)
    assert disponivel(f) < p.h + passo, (
        "%s: o disponível (%g) comporta o piso (%g) mais uma linha de métrica (%g): "
        "o caso não é o do piso" % (nome, disponivel(f), p.h, passo))
    assert a.metricas(OCT) == [], (
        "%s: não cabe métrica e a gaveta desenhou %r" % (nome, a.metricas(OCT)))
    cont = a.contador(OCT)
    assert cont is not None and cont[1] == total, (
        "%s: esperado `+%d more` (todas omitidas); achei %r"
        % (nome, total, cont and cont[0].text))
    assert a.collapse(OCT) is not None, "%s: piso sem `Collapse`" % nome
    assert [n for n in a.dentro(p) if n.text.strip() == OCT["display_name"]], (
        "%s: piso sem o nome do provider" % nome)
    assert not a.leituras(OCT), "%s: leituras desenhadas no piso" % nome
    assert not a.recortados(p), "%s: piso recortado: %r" % (nome, a.recortados(p))
    for n in a.collapse(OCT):
        assert n.bottom <= p.bottom + TOL, "%s: `Collapse` recortado no piso: %r" % (nome, n)
    for n in a.rodape():
        assert n.y >= p.bottom - TOL and n.bottom <= a.altura + TOL, (
            "%s: rodapé fora da view ou sob o painel: %r" % (nome, n))
    assert a.altura <= max(f.H, f.altura) + TOL, (
        "%s: view aberta de %g px com H=%g e fechada=%g"
        % (nome, a.altura, f.H, f.altura))
    assert a.altura < ref.altura - 100, (
        "%s: no piso a view mede %g, perto da gaveta livre (%g)" % (nome, a.altura, ref.altura))
    assert p.bottom >= a.grade().bottom - TOL, "%s: piso não ancorado embaixo" % nome


def test_tela_piso_nao_encolhe_abaixo_do_minimo(apertado):
    """O piso é um piso: H == fechada e H=1 dão a mesma gaveta (nome, status,
    `+8 more`, `Collapse`), do mesmo tamanho.

    REGRA ANTIGA: a mesma intenção, medida com H=100 × H=1 no relatório com
    primário; sob 4' aquele relatório deixou de cair no piso."""
    af = snap_of(apertado, "piso-mp-fechada", "open")
    a1 = snap_of(apertado, "piso-mp-h1", "open")
    pf, p1 = exigir_aberta(af, OCT), exigir_aberta(a1, OCT)
    assert af.contador(OCT) is not None and af.contador(OCT)[1] == 8, (
        "sem o piso contratado (`+8 more`) a comparação não descreve nada")
    assert abs(pf.h - p1.h) <= TOL and abs(af.altura - a1.altura) <= TOL, (
        "o piso varia com H: painel %g/%g, view %g/%g"
        % (pf.h, p1.h, af.altura, a1.altura))
    assert af.conteudo == a1.conteudo
    assert not a1.recortados(p1), "piso recortado com H=1: %r" % a1.recortados(p1)


def test_tela_piso_grade_de_uma_linha_h_igual_fechada(livre, apertado):
    """Item 1' — H é exatamente a altura da view fechada e a grade tem uma linha
    só (mais baixa que qualquer gaveta). A view não ultrapassa H 'sempre que H
    for pelo menos a altura da view com a gaveta fechada'. Sob a regra antiga
    isto media 303 px contra H=258; sob 4' a gaveta sobe sobre o que está acima
    da grade e abrir nunca deixa a view maior que H quando a fechada cabia."""
    f, a = par(apertado, "ap-m1-d0")
    ref = snap_of(livre, "livre-m1", "closed")
    assert abs(f.H - ref.altura) <= TOL and abs(f.altura - ref.altura) <= TOL
    exigir_aberta(a, OCT)
    exigir_cabe(a, f.H, "grade de uma linha, H == altura fechada")


def test_tela_orcamento_muda_com_a_gaveta_aberta(livre, apertado):
    """O orçamento pode mudar com a gaveta aberta: ao apertar, a view volta a
    caber (e só corta o que o limite do topo exige, anunciado); com folga média
    cabe em H com TODO o conteúdo de H grande; ao folgar, volta ao estado livre.

    REGRA ANTIGA (caiu): qualquer aperto tinha de anunciar corte; sob 4' só há
    corte quando a gaveta não cabe entre o topo e a base + folga."""
    liv = snap_of(apertado, "dyn-m1", "livre")
    ap = snap_of(apertado, "dyn-m1", "apertado")
    med = snap_of(apertado, "dyn-m1", "medio")
    dev = snap_of(apertado, "dyn-m1", "devolvido")
    ref = snap_of(livre, "livre-m1", "open")
    fechada = snap_of(apertado, "dyn-m1", "closed")
    assert any(l.startswith("HB_SET|") for l in ap.log), (
        "a view não aceitou `heightBudget`: %r" % ap.log)
    assert abs(liv.altura - ref.altura) <= TOL
    # apertado: fechada + 60 — a gaveta livre não cabe nem subindo até o topo.
    p = exigir_aberta(ap, OCT)
    exigir_cabe(ap, fechada.altura + 60, "orçamento reduzido com a gaveta aberta")
    direto = snap_of(apertado, "ap-m1-d60", "open")
    assert ap.conteudo == direto.conteudo and abs(ap.altura - direto.altura) <= TOL, (
        "apertar com a gaveta aberta dá %g px/%r; abrir já apertado dá %g px/%r"
        % (ap.altura, ap.metricas(OCT), direto.altura, direto.metricas(OCT)))
    assert not ap.recortados(p), "recorte silencioso depois de apertar: %r" % ap.recortados(p)
    assert p.y >= -TOL, "o painel passou do topo da view: y=%g" % p.y
    # médio: fechada + 142 — cabe em H com tudo.
    pm = exigir_aberta(med, OCT)
    exigir_cabe(med, fechada.altura + 142, "orçamento médio com a gaveta aberta")
    assert med.metricas(OCT) == ref.metricas(OCT) and med.contador(OCT) is None, (
        "com 142 px de folga a gaveta desenha %r e com H grande %r"
        % (med.metricas(OCT), ref.metricas(OCT)))
    assert not med.recortados(pm)
    # devolvido
    exigir_aberta(dev, OCT)
    assert abs(dev.altura - ref.altura) <= TOL and dev.conteudo == ref.conteudo, (
        "depois de devolver o orçamento a view não voltou ao estado livre "
        "(%g × %g)" % (dev.altura, ref.altura))


def test_tela_trocar_e_fechar_devolvem_altura_fechada(livre, apertado):
    """Item 9 — sob orçamento apertado: trocar do provider pequeno para o grande
    dá o mesmo estado de abrir o grande direto (e cabe em H); fechar devolve a
    altura fechada."""
    f = snap_of(apertado, "troca-m1", "closed")
    s1 = snap_of(apertado, "troca-m1", "s1")
    oct_ = snap_of(apertado, "troca-m1", "oct")
    fechado = snap_of(apertado, "troca-m1", "fechado")
    direto = snap_of(apertado, "ap-m1-d142", "open")
    H = f.H
    exigir_aberta(s1, S1)
    exigir_cabe(s1, H, "provider pequeno aberto")
    exigir_aberta(oct_, OCT)
    exigir_cabe(oct_, H, "depois de trocar para o provider grande")
    assert s1.painel(OCT) is None and oct_.painel(S1) is None, "duas gavetas desenhadas"
    assert abs(oct_.altura - direto.altura) <= TOL and oct_.metricas(OCT) == direto.metricas(OCT), (
        "trocar para o grande dá %g px/%r; abrir direto dá %g px/%r"
        % (oct_.altura, oct_.metricas(OCT), direto.altura, direto.metricas(OCT)))
    assert fechado.prop("openDrawerId") == "", "o `Collapse` não fechou"
    assert abs(fechado.altura - f.altura) <= TOL, (
        "depois de fechar a view mede %g; fechada media %g" % (fechado.altura, f.altura))
    assert fechado.painel(OCT) is None


@pytest.mark.parametrize("nome", TOPO)
def test_tela_recorte_leituras_cedem_ao_limite_do_topo(livre, apertado, nome):
    """T48 × T49 — quando o limite do topo (6') aperta: `Collapse` (e o contador,
    se houver métrica omitida) inteiros no painel, `Collapse` abaixo do contador;
    se as leituras `Elapsed`/`Pace` aparecem, estão inteiras; elas são as
    PRIMEIRAS a ceder (se sem elas a gaveta cabe, nenhuma métrica é cortada) e
    não custam métrica (com a leitura desligada, na mesma folga, não se desenha
    MAIS métrica).

    REGRA ANTIGA (caiu): este teste exigia `+N more` em QUALQUER aperto de tela
    (chamava-se `…_cedem_ao_aperto`). Sob 4' o aperto sozinho não corta; o que
    continua valendo é a ordem de cessão quando o topo limita."""
    prov = prov_de(nome)
    f, a = par(apertado, nome)
    H = exigir_caso_discriminante(livre, nome, f)
    exigir_grupo(livre, nome, f, "topo")
    p = exigir_aberta(a, prov)
    exigir_cabe(a, H, nome)
    ref = snap_of(livre, REFERENCIA[nome], "open")
    cont = a.contador(prov)
    if len(a.metricas(prov)) < len(ref.metricas(prov)):
        assert cont is not None, "%s: métrica omitida sem corte anunciado" % nome
    if cont is not None:
        assert cont[0].bottom <= p.bottom + TOL and cont[0].y >= p.y - TOL, (
            "%s: `%s` recortado: y=%g..%g, painel y=%g..%g"
            % (nome, cont[0].text, cont[0].y, cont[0].bottom, p.y, p.bottom))
    for n in a.collapse(prov):
        assert p.y - TOL <= n.y and n.bottom <= p.bottom + TOL, (
            "%s: `Collapse` recortado: %r" % (nome, n))
        if cont is not None:
            assert n.y >= cont[0].bottom - TOL, (
                "%s: `Collapse` (%r) sobre o contador (%r)" % (nome, n, cont[0]))
    if nome in ("ap-m1-d100", "ap-m3-d0"):
        #: aqui a gaveta COM leituras não cabe, mas a gaveta SEM leituras (medida
        #: em `livre-m1-nodet`, mesmo provider e teto) cabe: quem cede é a
        #: leitura, nunca uma métrica.
        sem_h = exigir_aberta(snap_of(livre, "livre-m1-nodet", "open"), OCT).h
        assert sem_h <= disponivel(f) + TOL < exigir_aberta(ref, OCT).h, (
            "%s: o caso não separa 'com leitura não cabe' de 'sem leitura cabe' "
            "(sem=%g, disponível=%g)" % (nome, sem_h, disponivel(f)))
        assert a.metricas(OCT) == ref.metricas(OCT) and cont is None, (
            "%s: sem as leituras a gaveta caberia inteira (%g ≤ %g) e mesmo assim "
            "cortou métrica: %r, contador %r"
            % (nome, sem_h, disponivel(f), a.metricas(OCT), cont and cont[0].text))
        assert a.leituras(OCT) == [], (
            "%s: leituras desenhadas onde não cabem: %r" % (nome, a.leituras(OCT)))
    for n in a.leituras(prov):
        assert p.y - TOL <= n.y and n.bottom <= p.bottom + TOL, (
            "%s: leitura recortada: %r" % (nome, n))
    if nome == "ap-m1-d60":
        sem = snap_of(apertado, "ap-m1-nodet-d60", "open")
        assert len(a.metricas(OCT)) >= len(sem.metricas(OCT)), (
            "com a leitura ligada cabem %d métricas e com ela desligada %d: a "
            "leitura não cedeu primeiro" % (len(a.metricas(OCT)), len(sem.metricas(OCT))))


def test_tela_teto_pequeno_sob_aperto_corta_pelo_teto(livre, apertado):
    """Item 6' — teto 160 com 12 métricas, `down`, sob aperto de tela: há
    `+N more` (o corte é do TETO, igual ao de H grande), contador e `Collapse`
    inteiros, painel ≤ teto, view ≤ H."""
    nome = "ap-m12-160-d42"
    f, a = par(apertado, nome)
    H = exigir_caso_discriminante(livre, nome, f)
    p = exigir_aberta(a, DOD)
    exigir_cabe(a, H, nome)
    ref = snap_of(livre, "livre-m12-160", "open")
    assert p.h <= 160 + TOL, "painel de %g px com teto 160" % p.h
    cont, cref = a.contador(DOD), ref.contador(DOD)
    assert cont is not None and cref is not None, (
        "12 métricas no teto 160 sem `+N more` (aperto=%r, livre=%r)" % (cont, cref))
    assert cont[1] == cref[1] and a.metricas(DOD) == ref.metricas(DOD), (
        "sob aperto `%s` e %r; com H grande `%s` e %r: a tela mudou o corte do teto"
        % (cont[0].text, a.metricas(DOD), cref[0].text, ref.metricas(DOD)))
    assert cont[1] + len(a.metricas(DOD)) == 12
    assert a.metricas(DOD) and a.metricas(DOD)[0] == lider_de(DOD)
    assert p.y - TOL <= cont[0].y and cont[0].bottom <= p.bottom + TOL, (
        "`%s` recortado: y=%g..%g, painel y=%g..%g"
        % (cont[0].text, cont[0].y, cont[0].bottom, p.y, p.bottom))
    for n in a.collapse(DOD):
        assert p.y - TOL <= n.y and n.bottom <= p.bottom + TOL, "`Collapse` recortado: %r" % n
        assert n.y >= cont[0].bottom - TOL
    assert not a.recortados(p), "conteúdo recortado: %r" % a.recortados(p)
    assert p.y < a.grade().bottom - TOL, "sem espaço abaixo e o painel não sobe sobre a grade"


def test_tela_conteudo_curto_limita_pelo_topo(livre, apertado):
    """Item 6' — com conteúdo CURTO acima da grade (primário de uma métrica) e
    teto alto (480), o limite é o topo: a gaveta desenha MENOS que com H grande,
    anuncia o corte, não passa do topo da view; e dar folga abaixo devolve
    métricas (nunca tira)."""
    ref = snap_of(livre, "livre-curto", "open")
    total_livre = len(ref.metricas(DOD))
    assert total_livre == 12 and ref.contador(DOD) is None, (
        "a referência (teto 480, H grande) deveria desenhar as 12: %r" % ref.metricas(DOD))
    desenhadas = []
    for nome in ("ap-curto-d0", "ap-curto-d51"):
        f, a = par(apertado, nome)
        H = exigir_caso_discriminante(livre, nome, f)
        p = exigir_aberta(a, DOD)
        exigir_cabe(a, H, nome)
        assert p.y >= -TOL, "%s: o painel passa do topo da view (y=%g)" % (nome, p.y)
        assert p.h <= disponivel(f) + TOL, (
            "%s: painel de %g px; do topo da view à base da grade + folga há %g"
            % (nome, p.h, disponivel(f)))
        assert p.h < 480 - 100, "%s: o painel (%g) ficou perto do teto 480" % (nome, p.h)
        cont = a.contador(DOD)
        assert cont is not None and cont[1] + len(a.metricas(DOD)) == 12, (
            "%s: corte pelo topo sem contador coerente: %r / %r"
            % (nome, cont and cont[0].text, a.metricas(DOD)))
        assert 1 <= len(a.metricas(DOD)) < total_livre
        desenhadas.append(len(a.metricas(DOD)))
    assert desenhadas[1] >= desenhadas[0], (
        "com 51 px de folga a gaveta desenha %d métricas e sem folga %d"
        % (desenhadas[1], desenhadas[0]))


# --------------------------------------------------------------------------- #
# 3. T49 — `+N more` e `Collapse` nunca recortados (teto da setting)
# --------------------------------------------------------------------------- #

def rc(livre_, direcao: str, teto: int, n: int, det: bool) -> Snap:
    return snap_of(livre_, "rc-%s-%d-%d-%s" % (direcao, teto, n, "det" if det else "nodet"),
                   "open")


MATRIZ = [(t, n, d) for t in TETOS for n in TAMANHOS for d in (True, False)]
_ids = lambda v: ("det" if v is True else "nodet" if v is False else str(v))


def test_recorte_matriz_tem_corte_e_tem_folga(livre):
    """Âncora anti-vacuidade: a matriz contém casos COM corte (12 métricas no
    teto 160) e SEM corte (5 métricas no teto 480); sem os dois, 'o contador está
    inteiro' poderia ser verdade por nunca haver contador."""
    apertado_ = rc(livre, "down", 160, 12, True)
    folgado = rc(livre, "down", 480, 5, False)
    exigir_aberta(apertado_, grande(12))
    exigir_aberta(folgado, grande(5))
    assert apertado_.contador(grande(12)) is not None, "12 métricas em 160 px sem corte"
    assert folgado.contador(grande(5)) is None, "5 métricas em 480 px com corte"
    assert len(folgado.metricas(grande(5))) == 5
    com_corte = sum(1 for t, n, d in MATRIZ if rc(livre, "down", t, n, d).contador(grande(n)))
    assert com_corte >= 6, "só %d casos da matriz `down` têm corte" % com_corte


@pytest.mark.parametrize("teto,n,det", MATRIZ, ids=_ids)
def test_recorte_down_contador_e_collapse_inteiros(livre, teto, n, det):
    """T49 — em `down`, com corte: `+N more` inteiro dentro do painel (base do
    texto ≤ base do painel) e `Collapse` também; nada do painel é recortado; e o
    painel respeita o teto."""
    prov = grande(n)
    a = rc(livre, "down", teto, n, det)
    p = exigir_aberta(a, prov)
    assert p.h <= teto + TOL, "painel de %g px com teto %d" % (p.h, teto)
    col = a.collapse(prov)
    assert col is not None, "gaveta `down` sem `Collapse`"
    for c in col:
        assert p.y - TOL <= c.y and c.bottom <= p.bottom + TOL, (
            "`Collapse` recortado: %r, painel y=%g..%g" % (c, p.y, p.bottom))
    cont = a.contador(prov)
    if cont is not None:
        assert cont[0].y >= p.y - TOL and cont[0].bottom <= p.bottom + TOL, (
            "`%s` recortado: y=%g..%g e o painel termina em %g (excesso %g px)"
            % (cont[0].text, cont[0].y, cont[0].bottom, p.bottom, cont[0].bottom - p.bottom))
        assert cont[0].bottom <= col[1].y + TOL, (
            "`%s` (até %g) invade o `Collapse` (desde %g)"
            % (cont[0].text, cont[0].bottom, col[1].y))
    fora = a.recortados(p)
    assert not fora, "conteúdo do painel recortado em silêncio: %r" % fora


@pytest.mark.parametrize("teto,n,det", MATRIZ, ids=_ids)
def test_recorte_down_contagem_fecha(livre, teto, n, det):
    """T49 — N + métricas desenhadas = total; sem contador, todas desenhadas."""
    prov = grande(n)
    a = rc(livre, "down", teto, n, det)
    exigir_aberta(a, prov)
    des = a.metricas(prov)
    cont = a.contador(prov)
    assert len(set(des)) == len(des), "métrica repetida: %r" % des
    if cont is None:
        assert len(des) == n, (
            "%d de %d métricas desenhadas e nenhum `+N more`: corte silencioso"
            % (len(des), n))
    else:
        assert cont[1] >= 1 and cont[1] + len(des) == n, (
            "`%s` + %d desenhadas (%r) != %d métricas do provider"
            % (cont[0].text, len(des), des, n))


@pytest.mark.parametrize("teto,n,det", MATRIZ, ids=_ids)
def test_recorte_down_lider_primeiro_e_corte_pela_cauda(livre, teto, n, det):
    """T49 — a líder (maior percent) é a primeira desenhada; o resto segue a
    ordem do relatório e o que falta é a cauda."""
    prov = grande(n)
    a = rc(livre, "down", teto, n, det)
    exigir_aberta(a, prov)
    des = a.metricas(prov)
    ps = percentuais(n)
    lider = ps.index(max(ps)) + 1
    assert des, "nenhuma métrica desenhada com teto %d (o piso é exceção de tela, não de teto)" % teto
    assert des[0] == lider, "a líder é M%d (%d%%) e a primeira desenhada é M%d: %r" % (
        lider, max(ps), des[0], des)
    resto = [i for i in range(1, n + 1) if i != lider]
    assert des[1:] == resto[:len(des) - 1], (
        "o corte não foi pela cauda: %r, esperado M%d + %r" % (des, lider, resto[:len(des) - 1]))


@pytest.mark.parametrize("teto", (160, 480))
def test_recorte_down_empate_lidera_pela_ordem(livre, teto):
    """T49 — empate de percent: lidera a primeira pela ordem do relatório."""
    prov = empatado()
    a = snap_of(livre, "rc-down-%d-tie" % teto, "open")
    p = exigir_aberta(a, prov)
    des = a.metricas(prov)
    assert des and des[0] == 1, "empate em 50%%: a primeira desenhada é M%r (%r)" % (
        des[:1], des)
    assert des == list(range(1, len(des) + 1)), "ordem fora do relatório: %r" % des
    cont = a.contador(prov)
    assert (cont[1] if cont else 0) + len(des) == 5
    assert not a.recortados(p), "recorte: %r" % a.recortados(p)


@pytest.mark.parametrize("teto", TETOS)
@pytest.mark.parametrize("n", TAMANHOS)
def test_recorte_down_leituras_cedem_primeiro(livre, teto, n):
    """T49 — `Elapsed`/`Pace` são as primeiras a ceder: ligar a leitura nunca
    custa uma métrica (não se desenha menos do que com ela desligada), e quando
    aparecem estão inteiras, sem empurrar contador nem `Collapse` para fora."""
    prov = grande(n)
    on, off = rc(livre, "down", teto, n, True), rc(livre, "down", teto, n, False)
    p = exigir_aberta(on, prov)
    exigir_aberta(off, prov)
    assert not off.leituras(prov), "leituras desenhadas com showMetricDetail desligado"
    assert len(on.metricas(prov)) >= len(off.metricas(prov)), (
        "teto %d, %d métricas: com a leitura ligada desenha %d e desligada %d — a "
        "leitura tomou o lugar de métrica" % (teto, n, len(on.metricas(prov)),
                                             len(off.metricas(prov))))
    for l in on.leituras(prov):
        assert l.y >= p.y - TOL and l.bottom <= p.bottom + TOL, "leitura recortada: %r" % l
    col = on.collapse(prov)
    assert col is not None and col[1].bottom <= p.bottom + TOL, "`Collapse` recortado"
    cont = on.contador(prov)
    if cont is not None:
        assert cont[0].bottom <= p.bottom + TOL, "contador recortado: %r" % cont[0]


def test_recorte_down_leituras_aparecem_quando_ha_espaco(livre):
    """Âncora: a leitura existe de fato quando sobra espaço (5 métricas, teto
    480) — sem isto, 'cedem primeiro' passaria com a leitura nunca desenhada."""
    a = rc(livre, "down", 480, 5, True)
    textos = [n.text.strip() for n in a.leituras(grande(5))]
    assert "Elapsed:" in textos and "Pace:" in textos, (
        "com showMetricDetail ligado e espaço de sobra as leituras não aparecem: %s"
        % a.texts)


# ---- left / right: contador inteiro (contrato T49 atualizado) --------------- #

#: REGISTRO DO "ANTES" (medição de 2026-11-17, antes da correção de T49). Não é
#: mais expectativa: é o histórico do defeito que as asserções abaixo proíbem.
#: Nas duas laterais (`left` e `right` mediram igual), sempre com
#: `showMetricDetail` ligado — `Elapsed`/`Pace` eram desenhadas ACIMA do
#: contador e o empurravam para fora do painel:
#:
#:   teto 160 ·  5 métricas · `+2 more` · texto y=326..337 · painel y=173..333 · 4 px de 11 fora
#:   teto 160 ·  8 métricas · `+5 more` · texto y=326..337 · painel y=173..333 · 4 px de 11 fora
#:   teto 160 · 12 métricas · `+9 more` · texto y=326..337 · painel y=173..333 · 4 px de 11 fora
#:   teto 240 ·  8 métricas · `+2 more` · texto y=407..418 · painel y=173..413 · 5 px de 11 fora
#:   teto 240 · 12 métricas · `+6 more` · texto y=407..418 · painel y=173..413 · 5 px de 11 fora
#:
#: Com a leitura desligada, ou nos tetos 320/480, não havia recorte (38 de 48
#: casos). Esses 10 casos foram `xfail(strict=True)` enquanto a tarefa pedia só
#: medição; hoje são asserções normais.
RECORTE_LATERAL_ANTES = {
    (d, t, n, True): excesso
    for d in ("left", "right")
    for (t, n, excesso) in ((160, 5, 4), (160, 8, 4), (160, 12, 4), (240, 8, 5), (240, 12, 5))
}


def _lateral_params():
    return [pytest.param(d, t, n, det,
                         id="%s-%d-%d-%s" % (d, t, n, "det" if det else "nodet"))
            for d in ("left", "right") for t, n, det in MATRIZ]


@pytest.mark.parametrize("direcao,teto,n,det", _lateral_params())
def test_recorte_lateral_contador_inteiro(livre, direcao, teto, n, det):
    """T49 — em `left`/`right`, quando há corte, a linha `+N more` está inteira
    dentro do painel (inclusive com `showMetricDetail` ligado, onde o recorte foi
    medido antes — ver RECORTE_LATERAL_ANTES), e N + desenhadas = total."""
    prov = grande(n)
    a = rc(livre, direcao, teto, n, det)
    assert a.prop("drawerDirection") == direcao, a.prop("drawerDirection")
    p = exigir_aberta(a, prov)
    des = a.metricas(prov)
    cont = a.contador(prov)
    if cont is None:
        assert len(des) == n, "%d de %d métricas e nenhum contador" % (len(des), n)
        return
    assert cont[1] + len(des) == n, "`%s` + %d desenhadas != %d" % (cont[0].text, len(des), n)
    assert cont[0].y >= p.y - TOL and cont[0].bottom <= p.bottom + TOL, (
        "`%s` recortado: texto y=%g..%g, painel y=%g..%g (excesso %g px; leituras "
        "desenhadas=%d)" % (cont[0].text, cont[0].y, cont[0].bottom, p.y, p.bottom,
                           cont[0].bottom - p.bottom, len(a.leituras(prov))))



@pytest.mark.parametrize("direcao", ("left", "right"))
@pytest.mark.parametrize("teto", TETOS)
@pytest.mark.parametrize("n", TAMANHOS)
def test_recorte_lateral_leituras_cedem_primeiro(livre, direcao, teto, n):
    """T49 — nas laterais, quando o espaço aperta, `Elapsed`/`Pace` cedem ANTES do
    contador: ligar a leitura nunca reduz as métricas desenhadas, e quando as
    leituras aparecem estão inteiras dentro do painel. (O contador inteiro com a
    leitura ligada é o caso `-det` de `test_recorte_lateral_contador_inteiro`.)"""
    prov = grande(n)
    on, off = rc(livre, direcao, teto, n, True), rc(livre, direcao, teto, n, False)
    p = exigir_aberta(on, prov)
    exigir_aberta(off, prov)
    assert not off.leituras(prov), "leituras desenhadas com showMetricDetail desligado"
    assert len(on.metricas(prov)) >= len(off.metricas(prov)), (
        "%s, teto %d, %d métricas: com a leitura ligada desenha %d (%r) e desligada "
        "%d (%r) — a leitura tomou o lugar de métrica"
        % (direcao, teto, n, len(on.metricas(prov)), on.metricas(prov),
           len(off.metricas(prov)), off.metricas(prov)))
    for l in on.leituras(prov):
        assert l.y >= p.y - TOL and l.bottom <= p.bottom + TOL, (
            "%s, teto %d: leitura recortada: %r, painel y=%g..%g"
            % (direcao, teto, l, p.y, p.bottom))


def test_recorte_lateral_leituras_aparecem_quando_ha_espaco(livre):
    """Âncora: na lateral a leitura existe quando sobra espaço (5 métricas, teto
    480) — sem isto, 'cedem primeiro' passaria com a leitura nunca desenhada."""
    for direcao in ("left", "right"):
        a = rc(livre, direcao, 480, 5, True)
        textos = [x.text.strip() for x in a.leituras(grande(5))]
        assert "Elapsed:" in textos and "Pace:" in textos, (
            "%s: com espaço de sobra as leituras não aparecem: %s" % (direcao, a.texts))
