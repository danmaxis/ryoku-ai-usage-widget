# -*- coding: utf-8 -*-
"""Contratos de comportamento da EMENDA T38 — gaveta lateral com DESLOCAMENTO.

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada 4,
emenda T38 assinada pelo dono em 2026-10-30. Nenhum arquivo de implementação foi
lido: nem ``content/Widget.qml`` nem ``service/Main.qml``.

Por que este arquivo existe
---------------------------
O sintoma declarado ao tester é preciso: **o teste anterior aceitou sobreposição
sem deslocamento**. A suíte de T42 media a direção "efetiva" com uma regra que
aceitava o painel dentro da faixa da grade — e é exatamente o desenho que o dono
reprovou no shell. Aqui a medida é outra: o que se afirma é que **a grade SAI do
lugar** e que **o painel ocupa o espaço que ela desocupou**, sem sobreposição.

O contrato, em uma frase por frente (todas da emenda assinada):

* ``left``  — o detalhe entra pela esquerda e as pílulas deslizam para a DIREITA.
* ``right`` — espelho: detalhe à direita, pílulas para a ESQUERDA.
* ``down``  — comportamento preservado (o detalhe empurra para baixo, nada desliza).
* A faixa alta na ponta do detalhe mostra ``→`` (pílulas foram para a direita) ou
  ``←`` (foram para a esquerda) e **clicar nela devolve à grade**.
* Pílulas visíveis, inteiras **ou parciais**, são clicáveis e **trocam o provider**.
* Pílulas cortadas recebem **fade na borda EXTERNA do viewport**, onde são
  recortadas: direita em ``left``, esquerda em ``right`` — **não** na costura
  com a gaveta (esclarecimento do dono após o smoke).
* O título ("Other Providers") fica **fixo** — não desliza com as pílulas.
* A **largura** do popout é **constante**; a **altura lateral é reservada desde a
  abertura** e não muda ao abrir/fechar.
* Refinamento do dono (pós-smoke), que esta versão do arquivo corrige:
  (a) entre o detalhe e a grade deslocada há uma **folga pequena** — contato NÃO é
  obrigatório; (b) a altura lateral reservada é a **maior altura necessária entre
  os detalhes dos secundários disponíveis, limitada pelo teto** — não é forçada
  igual ao teto; (c) a parte visível de uma pílula **pode ser parcial** e continua
  clicável; (d) `left`/`right` são **espelhados** e `down` é **preservado**.
* **Rodapé**: divisória ACIMA do conteúdo, com espaçamento; botões de copiar e
  atualizar alinhados entre si e com o texto de status.
* Preservados: acordeão, teto e ``+N more``, sem scroll.

Método (o que a sonda vê e o que ela não vê)
--------------------------------------------
``tests/qml/t45_emenda_lateral_harness.qml`` monta a view num processo
``quickshell`` OFFLINE com ``pluginApi`` sintético. O ``ai-usagebar`` nunca roda:
sem rede, sem credencial, sem escrita em config.

A sonda despeja a ÁRVORE RENDERIZADA (nó, pai, tipo, texto, geometria, gradiente,
clip). Posição de PÍLULA não resolve offline quando a grade tem uma coluna efetiva
— por isso as asserções de deslocamento usam a posição da **GRADE** e a do
**PAINEL**, que resolvem e são determinísticas. Essa limitação está declarada em
``LACUNAS_DE_OBSERVACAO`` e nenhuma asserção depende do que não resolve.

Cada teste traz, na docstring, a **vacuidade que ele evita**: quase toda afirmação
de "não acontece" deste arquivo é acompanhada de uma âncora que prova que o caso
de controle aconteceu. Sem isso, um verde poderia significar "nada foi desenhado".

O que a versão anterior deste arquivo afirmava e o refinamento revogou
---------------------------------------------------------------------
1. "painel e grade são CONTÍGUOS" (``|g.x - (p.x+p.w)| <= 1``) — revogado: agora
   se exige folga pequena e ``deslocamento = largura do painel + folga``.
2. "a reserva lateral é IGUAL ao teto" — revogado: agora se exige reserva estável,
   ``<= teto``, **igual entre dois tetos folgados** e **menor com detalhes menores**.
3. "o fade fica na costura com a gaveta" — a versão em teste desenha o gradiente
   encostado na borda da grade que encara o painel. O dono fixou a leitura
   contrária: o fade é indicador do CORTE e vive na borda externa do viewport.
   Este arquivo passou a afirmar isso; enquanto a view desenhar o gradiente na
   costura, estes testes REPROVAM — é desvio de contrato, não ambiguidade.

Ambiguidade registrada, não resolvida por invenção
--------------------------------------------------
(i) A emenda diz "faixa alta ... exibe → ... clicar retorna" e não fixa a
    largura/altura da faixa. Os testes exigem que ela exista, esteja DENTRO do
    painel, na PONTA do lado expandido, e que o clique feche a gaveta — não fixam
    pixels. (ii) A emenda diz "sombra OU fade"; o teste exige uma das duas na borda
    do recorte, sem exigir qual das duas formas. A sonda reconhece as duas formas
    de gradiente (``gradient`` no retângulo e um item de gradiente com ``stops``);
    uma sombra desenhada como retângulo semitransparente NÃO é reconhecida como
    fade — está declarado como lacuna, para não inventar oráculo. QUAL borda é o
    recorte não é mais ambiguidade: o dono fixou a borda externa do viewport. (iii) A emenda não define o que acontece quando
    a lateral não cabe; a decisão vigente (R4-v1/T38.3) é abrir para baixo — é
    isso que o teste de queda afirma.

Seleção executável e classificação por contrato (revisão T45, pós revert)
------------------------------------------------------------------------
Rodado contra a árvore congelada em ``daa1e7a``, a versão anterior deste arquivo
deu 59 vermelhos e 64 verdes. Dos 64 verdes, 62 ids são **controles** legítimos —
contratos que a emenda PRESERVA (``down``, clipboard, antipassividade, teto e
``+N more``, título fixo, largura constante do popout, rodapé como último bloco)
— e 2 ids, de UMA função, eram da alteração e passavam por FALTA DE PREMISSA:
``test_pilula_inteira_continua_clicavel_com_a_gaveta_aberta`` afirmava "clicável
COM a gaveta aberta" sem exigir que houvesse deslocamento, e por isso era verde
numa árvore em que a grade nunca sai de ``x = pad``. Ele passou a exigir sinal de
deslocamento e agora reprova no revert, como os demais da emenda. Com isso a
partição fica exata: 61 vermelhos (todos os ``-k alteracao``) e 62 verdes (todos
os ``-k "not alteracao"``), sem sobra de um lado nem do outro.

Dois termos de ``-k`` (o ``-k`` do pytest casa também o nome das marcas):

    -k alteracao          # específico da emenda: 61 ids, ZERO verdes no revert
    -k "not alteracao"    # controles/preservação: 62 ids, TODOS verdes no revert

Cada teste declara o grupo na PRIMEIRA linha da docstring. Uma marca só (e não
duas) porque o contrato é uma PARTIÇÃO: o que não é específico da emenda é
controle de preservação. As marcas não estão registradas em config do projeto
(este arquivo não edita config), então o pytest emite um
``PytestUnknownMarkWarning`` por marca — ruído conhecido, não falha.
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
PLUGIN_DIR = Path(os.environ.get("T45_PLUG_DIR", TEST_DIR.parent))
HARNESS = TEST_DIR / "qml" / "t45_emenda_lateral_harness.qml"

_QUICK = shutil.which("quickshell") or shutil.which("qs")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

pytestmark = pytest.mark.skipif(
    _QUICK is None,
    reason="quickshell ausente: a view QML não pode ser exercitada",
)

#: Marca da seleção executável: o que é ESPECÍFICO da emenda e tem de REPROVAR no
#: revert-and-test. ``-k alteracao`` seleciona só isto; ``-k "not alteracao"``
#: seleciona os controles de preservação. Uma marca só porque o contrato é uma
#: partição: o que não é da emenda é controle.
alteracao = pytest.mark.alteracao

#: LACUNAS DE OBSERVAÇÃO — o que este arquivo NÃO consegue medir, e por quê.
#:
#: Registrado para que um "verde" não seja lido como prova além do que é. Nenhuma
#: asserção depende de nada desta lista; se dependesse, seria oráculo inventado.
LACUNAS_DE_OBSERVACAO = {
    "posição_de_pílula": (
        "Em offscreen a posição de pílula só resolve quando a grade tem mais de uma "
        "coluna efetiva. Com 2 pílulas em 2 colunas todas saem no x da grade. Por "
        "isso o deslocamento é medido na GRADE e no PAINEL, que resolvem, e a coluna "
        "de uma célula é inferida dos x observados."),
    "altura_de_conteúdo": (
        "`height` derivado de conteúdo não resolve offline. A RESERVA de altura "
        "lateral é medida no contêiner da seção (que resolve); a altura exata que a "
        "gaveta ocuparia não é afirmada — só o corte, que é observável em texto. "
        "Por isso a reserva é afirmada por RELAÇÕES (estável, <= teto, igual entre "
        "dois tetos folgados, menor com detalhes menores), nunca por um pixel."),
    "reserva_em_poll": (
        "O dono diz que 'uma atualização do relatório PODE alterar essa reserva'. "
        "Este arquivo não afirma estabilidade nem mudança da reserva entre polls: "
        "afirmar qualquer das duas seria inventar oráculo. A estabilidade que se "
        "afirma é a de montagem vs gaveta aberta, que é o redimensionamento que a "
        "emenda quer evitar."),
    "folga_exata": (
        "O contrato diz 'pequena distância' e não fixa pixels. A sonda mede 6 "
        "unidades nos dois espelhos; as asserções usam a faixa [0, 16] e a "
        "igualdade entre as direções. Não há prova de qual valor o dono julga "
        "'pequeno' — só de que existe folga e de que ela é espelhada."),
    "borda_do_fade": (
        "RESOLVIDA pelo dono, e é o que os testes afirmam: o fade fica na borda "
        "EXTERNA do viewport onde as pílulas são recortadas (borda direita do "
        "content box em `left`, esquerda em `right`) — não na costura com a gaveta. "
        "Medição da versão em teste: o gradiente está na costura (x=208 com grade "
        "em 208 em `left`; x=240..252 com grade até 240 em `right`) e NÃO há "
        "gradiente na borda do corte (448 em `left`, 12 em `right`). Por isso os "
        "testes de fade reprovam nesta versão: é desvio medido, não lacuna."),
    "piso_da_pilula_parcial": (
        "O dono diz que 'apenas metade de uma das colunas de pílulas permaneça "
        "visível' é ACEITÁVEL — é permissão, não piso. A sonda mede fatias bem "
        "menores (19 px de 120/141). Este arquivo NÃO impõe piso de meia coluna: "
        "afirma só que a fatia visível é > 0 e que o clique nela troca o provider. "
        "Se o dono quiser a meia coluna como garantia, é um número novo a assinar."),
    "animacao": (
        "A emenda pede que a ANIMAÇÃO deixe claro que as pílulas foram deslocadas. "
        "A sonda espera assentar e mede o estado final, com o DESLOCAMENTO como "
        "prova; o movimento quadro a quadro não é observável aqui e a direção visual "
        "continua dependendo do smoke no shell real (é o que a própria emenda diz)."),
    "fade_versus_sombra": (
        "A emenda aceita 'sombra ou fade'. A sonda reconhece gradiente nas duas "
        "formas (propriedade `gradient` e item com `stops`). Uma sombra desenhada "
        "como retângulo semitransparente sem gradiente NÃO é reconhecida — a "
        "asserção de fade falharia nesse desenho."),
    "largura_da_faixa": (
        "A emenda não fixa a largura/altura da faixa da seta. Os testes exigem "
        "existência, posição na ponta e efeito do clique; pixels da faixa não são "
        "afirmados."),
    "altura_da_janela": (
        "A reserva lateral é medida contra o teto da setting. O termo "
        "`0.6 x altura de tela` (medido em T32) não entra: o harness offscreen "
        "devolve uma geometria de tela que não corresponde à do dono, e afirmar "
        "sobre ela seria medir o harness."),
}

#: Teto da FOLGA entre o detalhe e a grade deslocada, em unidades da view.
#:
#: O dono pediu "pequena distância" e, depois do smoke, deixou explícito que ela
#: NÃO é contato obrigatório. Não há número no contrato: mede-se a faixa
#: ``0 <= folga <= SMALL_GAP_MAX`` e a IGUALDADE entre os dois espelhos. 16 é
#: folgado de propósito (a medição da versão em teste é 6 em ``left`` e 6 em
#: ``right``); fixar 6 seria transformar a medição em oráculo.
SMALL_GAP_MAX = 16.0

#: Glifos da faixa de retorno, exatamente como a emenda os nomeia.
ARROW_RIGHT = "\u2192"
ARROW_LEFT = "\u2190"
ARROWS = (ARROW_RIGHT, ARROW_LEFT)


# --------------------------------------------------------------------------- #
# Fixtures de modelo — a forma que a view consome, nada de dado real
# --------------------------------------------------------------------------- #

def metric(label: str, percent, detail: str = "") -> dict:
    return {
        "label": label,
        "percent": percent,
        "value": ("%s%%" % percent) if isinstance(percent, (int, float)) else "",
        "severity": "low",
        "detail": detail,
        "reset_at": None,
        "window_secs": 18000,
    }


def provider(pid: str, name: str, labels: list, status: str = "ready",
             stale: bool = False) -> dict:
    return {
        "id": pid,
        "display_name": name,
        "short_name": pid[:3],
        "plan": pid + "-plan",
        "status": status,
        "stale": stale,
        "metrics": [metric(l, 10 + 10 * i) for i, l in enumerate(labels)],
        "error": None,
        "account": None,
    }


def model_of(providers: list) -> dict:
    return {
        "schema": 1,
        "primary": providers[0] if providers else None,
        "secondary": providers[1:],
        "all": providers,
        "total_providers": len(providers),
        "with_issues": sum(1 for p in providers if p["status"] == "error"),
    }


#: Primário com DUAS métricas: o caso de controle de "a gaveta não apaga o primário".
PRIMARY = provider("alpha", "Pill Alpha", ["Alpha Session", "Alpha Weekly"])

#: Providers de secundário. Nomes deliberadamente NÃO aninhados entre si ("Pill A"
#: dentro de "Pill Aaron" faria uma asserção por substring casar dois).
TAU = provider("tau", "Pill Tau", ["Tau Alpha", "Tau Beta", "Tau Gamma"])
SIGMA = provider("sigma", "Pill Sigma", ["Sigma Chat", "Sigma Week"])
OMEGA = provider("omega", "Pill Omega", ["Omega M%d" % i for i in range(1, 7)])

#: Ordem deliberadamente NÃO alfabética: a grade não pode reordenar.
FILLERS = [
    provider("aaron", "Pill Aaron", ["Aaron A"]),
    provider("bianca", "Pill Bianca", ["Bianca B"]),
    provider("carla", "Pill Carla", ["Carla C"]),
    provider("dario", "Pill Dario", ["Dario D"]),
]

THREE = model_of([PRIMARY, TAU, SIGMA])
SIX = model_of([PRIMARY, OMEGA, SIGMA])
MANY = model_of([PRIMARY] + FILLERS + [TAU, SIGMA])

#: Settings default do manifest (T40): columns 2, gaveta 320, direção down.
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


def st(**kw) -> dict:
    d = dict(BASE_SETTINGS)
    d.update(kw)
    return d


# --------------------------------------------------------------------------- #
# Casos
# --------------------------------------------------------------------------- #

COLS = (2, 3, 4)
DIRECTIONS = ("down", "left", "right")
#: Larguras de orçamento. 460 é a medição desta máquina; 900 é folgada de
#: propósito, para que uma falha de direção não seja confundida com orçamento.
NARROW, WIDE = 460, 900


def snap(name: str) -> dict:
    return {"op": "snap", "name": name}


def opened(name: str = "open", marker: str = "TAU ALPHA",
           click: str = "Pill Tau") -> dict:
    """Abre a gaveta de Tau (se o marcador ainda não está na árvore), espera
    assentar e censa."""
    return {"op": "openDrawer", "text": marker, "click": click, "name": name, "ms": 900}


CASES: list[dict] = []
for _cols in COLS:
    for _dir in DIRECTIONS:
        for _w in (NARROW, WIDE):
            tag = "%d-%s-%d" % (_cols, _dir, _w)
            CASES.append({"name": "closed-" + tag, "settings": st(columns=_cols, drawerDirection=_dir),
                          "widthBudget": _w, "model": THREE, "epoch": 0,
                          "steps": [snap("s")]})
            CASES.append({"name": "open-" + tag, "settings": st(columns=_cols, drawerDirection=_dir),
                          "widthBudget": _w, "model": THREE, "epoch": 0,
                          "steps": [opened()]})

#: Teto e corte, nas três direções: a emenda manda PRESERVAR ambos.
for _dir in DIRECTIONS:
    for _cap in (160, 320, 480):
        CASES.append({"name": "cap-%s-%d" % (_dir, _cap),
                      "settings": st(drawerDirection=_dir, drawerMaxHeight=_cap),
                      "widthBudget": WIDE, "model": SIX, "epoch": 0,
                      "steps": [snap("closed"), opened("open", "OMEGA M1", "Pill Omega")]})

#: Acordeão: abrir a gaveta de outro provider fecha a primeira (preservado).
for _dir in ("left", "right"):
    CASES.append({"name": "accordion-" + _dir,
                  "settings": st(drawerDirection=_dir), "widthBudget": WIDE,
                  "model": THREE, "epoch": 0,
                  "steps": [opened("tau"), opened("sigma", "SIGMA CHAT", "Pill Sigma")]})

#: Seta de retorno: abre, clica a seta, e reabre para provar que a grade voltou a
#: ser clicável (sem o segundo passo, "voltou" seria indiscernível de "sumiu").
for _dir, _sym in (("left", ARROW_RIGHT), ("right", ARROW_LEFT)):
    CASES.append({"name": "return-" + _dir,
                  "settings": st(drawerDirection=_dir), "widthBudget": WIDE,
                  "model": THREE, "epoch": 0,
                  "steps": [opened("open"),
                            {"op": "clickArrow", "symbol": _sym, "name": "back", "ms": 900},
                            opened("again")]})
    #: Trocar de provider clicando outra pílula com a gaveta aberta: o
    #: deslocamento tem de continuar depois da troca.
    CASES.append({"name": "swap-" + _dir,
                  "settings": st(drawerDirection=_dir), "widthBudget": NARROW,
                  "model": MANY, "epoch": 0,
                  "steps": [opened("tau", "TAU ALPHA", "Pill Tau"),
                            {"op": "clickText", "value": "Pill Bianca"},
                            {"op": "wait", "ms": 900, "name": "swap"}]})

#: Pílula PARCIAL: 4 colunas no mesmo orçamento garante pílulas cortadas pela
#: borda; clicar a fatia visível da célula 1 tem de trocar o provider.
for _dir in ("left", "right"):
    for _cols in (3, 4):
        CASES.append({"name": "partial-%s-%d" % (_dir, _cols),
                      "settings": st(columns=_cols, drawerDirection=_dir),
                      "widthBudget": NARROW, "model": MANY, "epoch": 0,
                      "steps": [opened(), {"op": "clickPillIx", "ix": 1, "name": "hit", "ms": 900}]})

#: Reserva lateral x TAMANHO dos detalhes disponíveis: ``MANY`` tem, no máximo, 3
#: métricas por secundário; ``SIX`` tem um secundário de 6. Mesmo teto (480) e
#: mesma direção — só o modelo muda. É o par que prova "maior altura entre os
#: detalhes disponíveis" (e não "o teto").
for _dir in ("left", "right"):
    CASES.append({"name": "reserve-small-" + _dir,
                  "settings": st(columns=2, drawerDirection=_dir, drawerMaxHeight=480),
                  "widthBudget": WIDE, "model": MANY, "epoch": 0,
                  "steps": [snap("closed"), opened()]})

#: Recollher em `down` (controle abaixo da grade) versus em `left`/`right`
#: (a faixa da seta): contratos diferentes, casos distintos.
CASES.append({"name": "collapse-down", "settings": st(drawerDirection="down"),
              "widthBudget": WIDE, "model": THREE, "epoch": 0,
              "steps": [opened(), {"op": "clickDownCloser", "name": "after", "ms": 900}]})

#: Poll com o MESMO provider: a gaveta fica e o deslocamento não se perde.
TAU_AGAIN = provider("tau", "Pill Tau", ["Tau Alpha", "Tau Beta", "Tau Gamma"])
CASES.append({"name": "poll-same", "settings": st(drawerDirection="left"),
              "widthBudget": WIDE, "model": THREE, "epoch": 0,
              "steps": [opened(), {"op": "poll", "name": "after",
                                   "model": model_of([PRIMARY, TAU_AGAIN, SIGMA]), "ms": 900}]})

#: Rodapé com instante de sucesso (frescor) e com provider em erro.
ERR = provider("zeta", "Pill Zeta", ["Zeta Chat"], status="error")
CASES += [
    {"name": "footer-clean", "settings": st(), "widthBudget": NARROW,
     "model": THREE, "epoch": 1750000000, "steps": [{"op": "probeSave"}, snap("s")]},
    {"name": "footer-issues", "settings": st(), "widthBudget": NARROW,
     "model": model_of([PRIMARY, TAU, SIGMA, ERR]), "epoch": 1750000000,
     "steps": [snap("s")]},
    {"name": "footer-left", "settings": st(drawerDirection="left"), "widthBudget": NARROW,
     "model": model_of([PRIMARY, TAU, SIGMA, ERR]), "epoch": 1750000000,
     "steps": [snap("s")]},
]

#: Ações do rodapé: copiar escreve no clipboard, atualizar chama refresh().
CASES += [
    {"name": "copy", "settings": st(), "widthBudget": NARROW, "model": THREE,
     "epoch": 1750000000, "steps": [snap("pre"),
                                    {"op": "copyKeybind", "name": "post", "ms": 600}]},
    {"name": "refresh", "settings": st(), "widthBudget": NARROW, "model": THREE,
     "epoch": 1750000000, "steps": [snap("pre"),
                                    {"op": "refresh", "name": "post", "ms": 600}]},
]


# --------------------------------------------------------------------------- #
# Banco: um processo quickshell para todos os casos
# --------------------------------------------------------------------------- #

class Node:
    __slots__ = ("id", "parent", "kind", "text", "x", "y", "w", "h", "radius",
                 "alpha", "interactive", "fade", "clip")

    def __init__(self, fields: list):
        self.id = int(fields[0])
        self.parent = int(fields[1])
        self.kind = fields[2]
        self.text = json.loads(fields[3])
        self.x = float(fields[4])
        self.y = float(fields[5])
        self.w = float(fields[6])
        self.h = float(fields[7])
        self.radius = float(fields[8])
        self.alpha = float(fields[9])
        self.interactive = fields[10] == "true"
        self.fade = int(float(fields[11] or 0)) if len(fields) > 11 else 0
        self.clip = (fields[12] == "1") if len(fields) > 12 else False

    def __repr__(self) -> str:
        return "<%s#%d %.0f,%.0f %gx%g %r>" % (
            self.kind, self.id, self.x, self.y, self.w, self.h, self.text)


class Snap:
    """Censo de um estado da view."""

    def __init__(self, name: str):
        self.name = name
        self.props: dict[str, object] = {}
        self.saves: list[str] = []
        self.iw = self.ih = self.w = self.h = 0.0
        self.refreshes = 0
        self.nodes: list[Node] = []
        self._by_id: dict[int, Node] = {}
        self._kids: dict[int, list[int]] = {}

    def finish(self) -> "Snap":
        self._by_id = {n.id: n for n in self.nodes}
        self._kids = {}
        for n in self.nodes:
            self._kids.setdefault(n.parent, []).append(n.id)
        return self

    # -- leitura ---------------------------------------------------------
    @property
    def texts(self) -> list[str]:
        return [n.text for n in self.nodes if n.text]

    def has(self, needle: str) -> bool:
        up = needle.upper()
        return any(up in t.upper() for t in self.texts)

    def prop(self, name: str):
        return self.props.get(name)

    def children(self, nid: int) -> list[Node]:
        return [self._by_id[k] for k in self._kids.get(nid, [])]

    def subtree(self, nid: int) -> list[Node]:
        out = [self._by_id[nid]]
        for k in self._kids.get(nid, []):
            out.extend(self.subtree(k))
        return out

    def ancestors(self, nid: int) -> list[Node]:
        out, cur = [], self._by_id[nid].parent
        while cur and cur in self._by_id and len(out) < 40:
            out.append(self._by_id[cur])
            cur = self._by_id[cur].parent
        return out

    # -- estrutura -------------------------------------------------------
    _NON_VISUAL = re.compile(
        r"Repeater|Timer|Handler|Behavior|Animation|Transition|Instantiator|Delegate")

    def grid(self) -> Node:
        """A grade de pílulas da seção de secundários.

        Exige UMA só: duas grades seria outra view. A grade é identificada por
        TIPO, que é estrutura pública de layout — não por nome de componente
        interno nem por objectName.
        """
        gs = [n for n in self.nodes if n.kind == "QQuickGrid"]
        assert len(gs) == 1, (
            "esperava UMA grade de pílulas; achei %d: %s"
            % (len(gs), [(g.kind, g.x, g.y, g.w) for g in gs]))
        return gs[0]

    def grid_cells(self) -> list[Node]:
        """Células visíveis da grade, na ordem de inserção (= ordem de leitura)."""
        g = self.grid()
        return [c for c in self.children(g.id) if not self._NON_VISUAL.search(c.kind)]

    def trunk(self) -> Node:
        """O tronco vertical da view: a coluna que é filha direta da raiz.

        Achado por ESTRUTURA (raiz → primeira coluna), nunca por id de nó: um id
        é ordem de criação, e a ordem de criação muda com qualquer edição. Foi
        assim que uma versão anterior deste arquivo passou a medir o nó errado
        quando a view ganhou um bloco novo.
        """
        roots = [n for n in self.nodes if n.parent == 0]
        assert len(roots) == 1, "esperava UMA raiz; achei %d" % len(roots)
        colunas = [c for c in self.children(roots[0].id) if c.kind == "QQuickColumn"]
        assert len(colunas) == 1, (
            "esperava UMA coluna-tronco filha da raiz; achei %d: %s"
            % (len(colunas), [(c.kind, c.y, c.h) for c in self.children(roots[0].id)]))
        return colunas[0]

    def blocks(self) -> list[Node]:
        """Os blocos do tronco, na ordem em que aparecem."""
        return self.children(self.trunk().id)

    def section(self) -> Node:
        """O contêiner da seção de secundários: o ancestral da grade que é filho
        do tronco da view.

        É nele que a RESERVA DE ALTURA é medida. Subir até o filho do tronco é
        estrutural; escolher "o filho mais alto" seria arbitrário, e escolher por
        nome de componente seria ler a implementação.
        """
        g = self.grid()
        t = self.trunk()
        cur = self._by_id[g.parent]
        while cur is not None and cur.parent != t.id:
            cur = self._by_id.get(cur.parent)
        assert cur is not None, "a grade não está sob o tronco da view"
        return cur

    def drawer_panel(self, marker: str) -> Node:
        """O painel da gaveta: o retângulo que CONTÉM o rótulo exclusivo do
        provider aberto.

        Achado por conteúdo + tipo, sem nome de componente. ``marker`` é o rótulo
        de uma métrica que só existe na gaveta (a pílula mostra o líder).
        """
        alvo = marker.upper()
        # O painel é um RETÂNGULO visível com altura de bloco (as barras de métrica
        # são finas, h≈4) que CONTÉM o marcador. A opacidade do fundo não é
        # asserida aqui: ela é escolha de apresentação, não do contrato — exigir
        # opacidade alta faria uma gaveta translúcida parecer "não abriu".
        hits = [n for n in self.nodes
                if n.kind.startswith("QQuickRectangle") and not self._NON_VISUAL.search(n.kind)
                and n.alpha > 0.01 and n.h > 10
                and any(alvo in t.upper() for t in (x.text for x in self.subtree(n.id)))]
        # Um retângulo pode conter outro; fica o MENOR que ainda contém o texto —
        # o painel, não o fundo da view.
        assert hits, "nenhum retângulo contém o marcador %r; a gaveta não abriu: %s" % (
            marker, self.texts)
        return min(hits, key=lambda n: n.w * max(n.h, 1))

    def title_node(self) -> Node:
        """O título da seção de secundários ("Other Providers …")."""
        hits = [n for n in self.nodes if "PROVIDERS" in n.text.upper()]
        assert len(hits) == 1, (
            "esperava UM título de secundários; achei %d: %s"
            % (len(hits), [h.text for h in hits]))
        return hits[0]

    def arrows(self) -> list[Node]:
        return [n for n in self.nodes if n.text in ARROWS]

    def arrow(self, symbol: str) -> Node:
        hits = [n for n in self.nodes if n.text == symbol]
        assert len(hits) == 1, (
            "esperava UMA faixa com %r; achei %d. Setas na árvore: %s"
            % (symbol, len(hits), [(a.text, a.x) for a in self.arrows()]))
        return hits[0]

    def faded(self) -> list[Node]:
        return [n for n in self.nodes if n.fade > 0]

    def scrollers(self) -> list[Node]:
        """Qualquer coisa que role. A emenda veta scroll na gaveta."""
        return [n for n in self.nodes
                if re.search(r"Flickable|ScrollView|ListView|GridView|"
                             r"ScrollBar|WheelHandler", n.kind)]

    def pct_of(self, marker: str) -> str:
        """Textos que contêm o marcador (para o contador de omitidas)."""
        up = marker.upper()
        return [t for t in self.texts if up in t.upper()]

    def more_counter(self) -> list[Node]:
        return [n for n in self.nodes
                if re.fullmatch(r"\+\d+\s+more", n.text.strip(), re.I)]


class Dump:
    def __init__(self):
        self.cases: dict[str, dict[str, Snap]] = {}
        self.raw = ""


def _feed(snap: Snap, line: str) -> None:
    if line.startswith("PROP|"):
        parts = line.split("|")
        _, name, typeof, value = parts[0], parts[1], parts[2], parts[3]
        parsed = None
        if typeof in ("number", "string", "boolean"):
            try:
                parsed = json.loads(value)
            except ValueError:
                parsed = value
        snap.props[name] = parsed
        rest = "|".join(parts[4:])
        m = re.match(r"SAVES\|(.*?)\|IW\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|RF\|([^|]*)$", rest)
        if m:
            try:
                snap.saves = json.loads(m.group(1))
            except ValueError:
                snap.saves = ["<ilegível>"]
            snap.iw, snap.ih, snap.w, snap.h = (float(m.group(i)) for i in (2, 3, 4, 5))
            snap.refreshes = int(m.group(6))
    elif line.startswith("NODE|"):
        snap.nodes.append(Node(line.split("|")[1:]))


def _parse(stdout: str) -> Dump:
    d = Dump()
    d.raw = stdout
    case = snap = None
    for raw in _ANSI.sub("", stdout).splitlines():
        if " qml: " in raw:
            raw = raw.split(" qml: ", 1)[1]
        line = raw.strip()
        if line.startswith("===CASE|"):
            case = line[len("===CASE|"):-3]
            d.cases.setdefault(case, {})
            snap = None
        elif line.startswith("===CASE_END|"):
            case = snap = None
        elif line.startswith("===SNAP|"):
            assert case is not None, "SNAP fora de um CASE"
            snap = Snap(line[len("===SNAP|"):-3])
            d.cases[case][snap.name] = snap
        elif line.startswith("===SNAP_END|"):
            assert snap is not None, "SNAP_END sem SNAP"
            snap.finish()
            snap = None
        elif snap is not None and line:
            _feed(snap, line)
    return d


def _run(cases: list[dict]) -> tuple[Dump, str]:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("WAYLAND_DISPLAY", None)
    env["T45_PLUG_DIR"] = str(PLUGIN_DIR)
    # Cada caso viaja em PARTES de <=60000 chars: um único valor de ambiente acima
    # de MAX_ARG_STRLEN (128 KiB) impede o processo de iniciar.
    payload = json.dumps(cases, ensure_ascii=False)
    parts = [payload[i:i + 60000] for i in range(0, len(payload), 60000)] or ["[]"]
    for k, part in enumerate(parts):
        env["T45_CASES_%d" % k] = part
    env["T45_CASES_PARTS"] = str(len(parts))
    # stateDir ÚNICO por execução: caminho fixo compartilhado entre dois processos
    # simultâneos (suítes em paralelo) cria interferência cruzada.
    env["T45_STATE_DIR"] = tempfile.mkdtemp(prefix="t45-state-")
    try:
        proc = subprocess.run([_QUICK, "-p", str(HARNESS)], capture_output=True,
                              text=True, env=env, timeout=900)
    except subprocess.TimeoutExpired:
        pytest.fail(
            "o harness QML não terminou em 900s — a view provavelmente não monta "
            "(arquivo ausente/quebrado). Sem view não há comportamento a verificar.")
    out = _ANSI.sub("", proc.stdout + proc.stderr)
    parsed = _parse(out)
    missing = [c["name"] for c in cases if c["name"] not in parsed.cases]
    assert not missing, (
        "a sonda não montou os casos %r; rc=%s\nstderr(tail)=%s"
        % (missing, proc.returncode, proc.stderr[-1500:]))
    return parsed, out


@pytest.fixture(scope="session")
def bancada():
    parsed, raw = _run(CASES)
    return {"dumps": parsed.cases, "raw": raw}


def snap_of(bancada, case: str, snap: str = "s") -> Snap:
    assert case in bancada["dumps"], (
        "caso %r não existe na sonda; tem %r" % (case, sorted(bancada["dumps"])[:20]))
    d = bancada["dumps"][case]
    assert snap in d, "o caso %r não censou %r; censos=%r" % (case, snap, sorted(d))
    return d[snap]


def case_pair(tag: str, bancada):
    """(fechado, aberto) para um mesmo settings/orçamento.

    Os dois nomes de censo são os do gerador de casos: ``closed-*`` censa ``s`` e
    ``open-*`` censa ``open`` (a abertura espera assentar antes de censar).
    """
    return snap_of(bancada, "closed-" + tag, "s"), snap_of(bancada, "open-" + tag, "open")


def where(g: Node, p: Node) -> str:
    return "grade(x=%g y=%g w=%g) painel(x=%g y=%g w=%g h=%g)" % (
        g.x, g.y, g.w, p.x, p.y, p.w, p.h)


def caiu_no_desenho_de_down(g: Node, p: Node) -> bool:
    """A lateral CAIU no desenho de ``down``? Painel empilhado ABAIXO da grade e
    com a largura dela.

    Esta é a checagem que antecede toda medida de deslocamento: se o painel está
    embaixo, o número medido não é um deslocamento LATERAL — é o empurrão de
    ``down``, que é justamente o comportamento PRESERVADO. Sem ela, "houve
    deslocamento" aceitaria uma view que deslocasse para baixo em todas as
    direções.
    """
    return p.y > g.y + 0.5 and abs(p.w - g.w) <= 1


# --------------------------------------------------------------------------- #
# 0. Antipassividade
# --------------------------------------------------------------------------- #

def test_artefatos_sob_teste_existem():
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    Falha rápido se a view/harness sumiram — revert não pode virar SKIP."""
    assert (PLUGIN_DIR / "content" / "Widget.qml").is_file(), "content/Widget.qml ausente"
    assert HARNESS.is_file(), "harness QML ausente: %s" % HARNESS


def test_a_view_monta_com_a_gaveta_aberta(bancada):
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    Âncora de toda a suíte: sem view montada e sem gaveta aberta, nada abaixo
    prova nada.

    As propriedades afirmadas aqui (``columns``, ``drawerDirection``,
    ``openDrawerId``) são o contrato de interface do formato único; a ausência
    delas significa que a view sob teste não é a que este arquivo contrata.
    """
    s = snap_of(bancada, "open-2-left-%d" % WIDE, "open")
    assert s.texts, "a árvore renderizada está vazia"
    assert s.prop("columns") == 2, "a view não resolveu `columns` para um número"
    assert s.prop("drawerDirection") == "left", (
        "a view não resolveu `drawerDirection` para %r: %r" % ("left", s.prop("drawerDirection")))
    assert s.prop("openDrawerId") == "tau", (
        "a gaveta não abriu em Tau: openDrawerId=%r" % (s.prop("openDrawerId"),))
    assert s.has("TAU ALPHA"), "a gaveta não expôs a métrica do provider aberto"
    # Âncora do primário: a gaveta não pode apagar a outra seção da view.
    assert s.has("Pill Alpha") and s.has("ALPHA SESSION"), "a gaveta apagou o primário"


# --------------------------------------------------------------------------- #
# 1. O SINTOMA: sobreposição sem deslocamento
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("cols", COLS)
@pytest.mark.parametrize("width", (NARROW, WIDE))
@alteracao
def test_em_left_as_pilulas_deslocam_para_a_direita(bancada, cols, width):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    **O teste do sintoma.** Em ``left``, a grade sai para a DIREITA e o painel
    ocupa o espaço desocupado — sem sobreposição.

    O defeito que esta suíte existe para pegar é "gaveta sobreposta sobre as
    pílulas": a direção estava certa, o conteúdo aparecia, e um teste que só
    olhasse "abriu ao lado" ou "o texto está na árvore" passava. Aqui a asserção
    é o DESLOCAMENTO, em duas partes que juntas são a transição:

      1. ``x`` da grade AUMENTA em relação ao estado fechado;
      2. o painel ocupa, do lado esquerdo, a faixa que a grade deixou — separados
         por uma FOLGA PEQUENA (não contato: refinamento do dono), com interseção
         horizontal vazia e deslocamento = largura do painel + folga.

    O passo (1) sozinho ainda aceitaria "deslocou mas o painel ficou por cima"; o
    passo (2) sozinho aceitaria "o painel está à esquerda de uma grade que nunca
    saiu do lugar". Os dois juntos são a transição que o dono pediu.
    """
    closed, opened_ = case_pair("%d-left-%d" % (cols, width), bancada)
    g0, g1 = closed.grid(), opened_.grid()
    p = opened_.drawer_panel("TAU ALPHA")
    cw = closed.prop("contentWidth")

    # Antes de MEDIR o deslocamento: a lateral não pode ter caído no desenho de
    # `down`. Se caiu, o número medido descreveria o empurrão preservado, não a
    # coluna lateral — e "deslocou" seria verdade pela razão errada.
    assert not caiu_no_desenho_de_down(g1, p), (
        "em `left` o painel está empilhado abaixo da grade, com a largura dela: é o "
        "desenho de `down`, não a lateral. %s" % where(g1, p))

    # Âncora: o caso fechado é o ponto de comparação, e a grade existe nele.
    assert closed.prop("openDrawerId") == "", (
        "o caso de controle deveria estar SEM gaveta; openDrawerId=%r"
        % (closed.prop("openDrawerId"),))
    assert not closed.faded(), "o caso fechado já desenha fade (não haveria recorte)"

    deslocamento = g1.x - g0.x
    assert deslocamento > 0.5, (
        "em `left` a grade deveria deslizar para a DIREITA; x ficou em %g (era %g). "
        "Deslocamento zero/negativo é o defeito 'painel por cima da grade'. %s"
        % (g1.x, g0.x, where(g1, p)))

    sobreposicao = min(g1.x + g1.w, p.x + p.w) - max(g1.x, p.x)
    assert sobreposicao <= 0.5, (
        "grade e painel se sobrepõem horizontalmente em %g px — é a sobreposição "
        "que o dono reprovou. %s" % (sobreposicao, where(g1, p)))

    # O painel está à ESQUERDA da grade. Entre os dois há uma FOLGA PEQUENA: o
    # refinamento do dono pede "pequena distância entre detalhe e pílulas
    # deslocadas" e explicitamente NÃO exige contato. O valor exato não é oráculo;
    # exige-se que exista (>= 0, sem sobreposição) e que seja pequena
    # (<= SMALL_GAP_MAX, folgado em relação à medição de 6 unidades).
    folga = g1.x - (p.x + p.w)
    assert -0.5 <= folga <= SMALL_GAP_MAX, (
        "a folga entre painel e grade deveria ser pequena e não negativa; painel "
        "termina em %g, grade começa em %g, folga=%g. %s"
        % (p.x + p.w, g1.x, folga, where(g1, p)))
    assert p.x >= 12 - 1, (
        "o painel começa fora da área de conteúdo (x=%g < 12): a emenda pede o "
        "detalhe DENTRO do popout, com suas bordas. %s" % (p.x, where(g1, p)))
    # A grade DESLIZA: ela mantém a largura e muda de lugar. Encolher seria "reduzir
    # colunas", que a decisão do dono proíbe como efeito colateral da gaveta.
    assert abs(g1.w - g0.w) <= 1, (
        "a grade mudou de LARGURA ao abrir a gaveta (%g -> %g): o contrato pede "
        "deslocamento, não encolhimento. %s" % (g0.w, g1.w, where(g1, p)))
    # O deslocamento continua sendo o espaço que as pílulas cederam: largura do
    # painel MAIS a folga. Isto preserva a garantia original ("o deslocamento é o
    # espaço do painel") sem proibir a folga que o dono pediu.
    assert abs(deslocamento - (p.w + folga)) <= 1, (
        "o deslocamento (%g) deveria ser a largura do painel (%g) mais a folga (%g) "
        "— o espaço que a gaveta tomou é o que as pílulas cederam. %s"
        % (deslocamento, p.w, folga, where(g1, p)))



@pytest.mark.parametrize("cols", COLS)
@pytest.mark.parametrize("width", (NARROW, WIDE))
@alteracao
def test_em_right_as_pilulas_deslocam_para_a_esquerda(bancada, cols, width):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    Espelho de ``left``: em ``right`` a grade desloca para a ESQUERDA e o
    painel fica à direita, sem sobreposição.

    O espelhamento é afirmado em SINAL: ``deslocamento < 0`` aqui e ``> 0`` em
    ``left`` com o mesmo settings. Um "espelho" que deslocasse para o mesmo lado
    passaria num teste que só medisse "houve deslocamento".
    """
    closed, opened_ = case_pair("%d-right-%d" % (cols, width), bancada)
    g0, g1 = closed.grid(), opened_.grid()
    p = opened_.drawer_panel("TAU ALPHA")
    cw = closed.prop("contentWidth")

    # Antes de MEDIR o deslocamento: a lateral não pode ter caído no desenho de
    # `down`. Se caiu, o número medido descreveria o empurrão preservado, não a
    # coluna lateral — e "deslocou" seria verdade pela razão errada.
    assert not caiu_no_desenho_de_down(g1, p), (
        "em `right` o painel está empilhado abaixo da grade, com a largura dela: é o "
        "desenho de `down`, não a lateral. %s" % where(g1, p))

    assert closed.prop("openDrawerId") == "", "o caso de controle deveria estar SEM gaveta"

    deslocamento = g1.x - g0.x
    assert deslocamento < -0.5, (
        "em `right` a grade deveria deslizar para a ESQUERDA; x ficou em %g (era %g). %s"
        % (g1.x, g0.x, where(g1, p)))

    sobreposicao = min(g1.x + g1.w, p.x + p.w) - max(g1.x, p.x)
    assert sobreposicao <= 0.5, (
        "grade e painel se sobrepõem horizontalmente em %g px. %s"
        % (sobreposicao, where(g1, p)))

    # Espelho da folga: entre a grade e o painel há uma folga PEQUENA — nunca
    # negativa (sobreposição, afirmada acima) e nunca grande (espaço desperdiçado).
    # O refinamento do dono pede "pequena distância" e explicitamente NÃO exige
    # contato; o valor exato não é oráculo.
    folga = p.x - (g1.x + g1.w)
    assert -0.5 <= folga <= SMALL_GAP_MAX, (
        "a folga entre grade e painel deveria ser pequena e não negativa; grade "
        "termina em %g, painel começa em %g, folga=%g. %s"
        % (g1.x + g1.w, p.x, folga, where(g1, p)))
    assert p.x + p.w <= 12 + cw + 1, (
        "o painel transborda a área de conteúdo (%g > %g). %s"
        % (p.x + p.w, 12 + cw, where(g1, p)))
    # A grade desliza para a esquerda, mantendo a largura (encolher seria "reduzir
    # colunas", vetado pela decisão do dono).
    assert abs(g1.w - g0.w) <= 1, (
        "a grade mudou de LARGURA ao abrir a gaveta (%g -> %g): %s"
        % (g0.w, g1.w, where(g1, p)))
    # O deslocamento continua sendo o espaço cedido: largura do painel MAIS a folga.
    assert abs(deslocamento + (p.w + folga)) <= 1, (
        "o deslocamento (%g) deveria ser a largura do painel (%g) mais a folga (%g), "
        "com sinal oposto. %s" % (deslocamento, p.w, folga, where(g1, p)))



@pytest.mark.parametrize("cols", COLS)
@pytest.mark.parametrize("width", (NARROW, WIDE))
@alteracao
def test_left_e_right_sao_espelhos_e_nao_o_mesmo_desenho(bancada, cols, width):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    **Negativo do sintoma.** ``left`` e ``right`` não podem produzir a MESMA
    geometria — o defeito do dono era "a direção não está funcionando".

    As duas direções compartilham modelo, colunas e orçamento, então a única
    variável é a setting. Comparar as geometrias diretamente é o que impede um
    "as duas abrem" de passar como se fosse "as duas respeitam a setting".
    """
    _, left = case_pair("%d-left-%d" % (cols, width), bancada)
    _, right = case_pair("%d-right-%d" % (cols, width), bancada)
    gl, gr = left.grid(), right.grid()
    pl, pr = left.drawer_panel("TAU ALPHA"), right.drawer_panel("TAU ALPHA")

    geo_l = (round(gl.x, 1), round(pl.x, 1), round(pl.w, 1))
    geo_r = (round(gr.x, 1), round(pr.x, 1), round(pr.w, 1))
    assert geo_l != geo_r, (
        "`left` e `right` desenharam a MESMA geometria (grade x=%g, painel x=%g w=%g): "
        "a setting de direção não chega ao layout" % geo_l)
    # E cada uma respeita o seu lado, na leitura humana do contrato.
    assert pl.x < gl.x, "em `left` o painel deveria estar à ESQUERDA da grade"
    assert pr.x > gr.x, "em `right` o painel deveria estar à DIREITA da grade"
    # O espelho vale também para o TAMANHO do detalhe: mesma largura e mesma
    # altura nos dois lados. Um painel mais estreito de um lado mudaria a reserva
    # de largura (T33) conforme a direção — e a setting não pode mexer nisso.
    assert abs(pl.w - pr.w) <= 1, (
        "o painel tem larguras diferentes em `left` e `right` (%g vs %g): a "
        "direção mudou o orçamento de largura" % (pl.w, pr.w))
    assert abs(pl.h - pr.h) <= 1, (
        "o painel tem alturas diferentes em `left` e `right` (%g vs %g)"
        % (pl.h, pr.h))


@pytest.mark.parametrize("cols", COLS)
@pytest.mark.parametrize("width", (NARROW, WIDE))
@alteracao
def test_a_folga_entre_o_detalhe_e_as_pilulas_e_pequena_e_espelhada(bancada, cols, width):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    A folga entre o detalhe e a grade deslocada é **pequena** e **igual nos dois
    espelhos**.

    O refinamento do dono pede "pequena distância entre detalhe e pílulas
    deslocadas" — e o pedido explícito do dono ao tester é que isso NÃO vire
    exigência de contato. Por isso a asserção é uma FAIXA (``0 <= folga <=
    SMALL_GAP_MAX``) e a igualdade entre as direções; o valor exato não é oráculo.

    A simetria é o que impede a folga de virar "espaço que sobrou": se ela
    diferençasse entre os lados, um dos dois estaria desperdiçando largura ou
    colando o detalhe na pílula.
    """
    _, left = case_pair("%d-left-%d" % (cols, width), bancada)
    _, right = case_pair("%d-right-%d" % (cols, width), bancada)
    gl, pl = left.grid(), left.drawer_panel("TAU ALPHA")
    gr, pr = right.grid(), right.drawer_panel("TAU ALPHA")

    folga_l = gl.x - (pl.x + pl.w)
    folga_r = pr.x - (gr.x + gr.w)
    for nome, folga, g, p_ in (("left", folga_l, gl, pl), ("right", folga_r, gr, pr)):
        assert -0.5 <= folga <= SMALL_GAP_MAX, (
            "em `%s` a folga entre detalhe e grade é %g (esperado entre 0 e %g): "
            "negativa é sobreposição, grande é espaço desperdiçado. %s"
            % (nome, folga, SMALL_GAP_MAX, where(g, p_)))
    assert abs(folga_l - folga_r) <= 1, (
        "a folga não é espelhada: %g em `left`, %g em `right` (grade x=%g/%g, "
        "painel x+w=%g/%g)" % (folga_l, folga_r, gl.x, gr.x, pl.x + pl.w, pr.x))


@pytest.mark.parametrize("cols", COLS)
@pytest.mark.parametrize("width", (NARROW, WIDE))
def test_em_down_nada_desloca_e_a_gaveta_empurra_para_baixo(bancada, cols, width):
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    ``down`` preservado: a grade NÃO desloca e o painel aparece ABAIXO dela, com
    a largura dela.

    Este é o negativo que protege a decisão "preservar o comportamento atual" — e
    também o controle do teste do sintoma: se ``down`` deslocasse, o deslocamento
    não seria propriedade das laterais.
    """
    closed, opened_ = case_pair("%d-down-%d" % (cols, width), bancada)
    g0, g1 = closed.grid(), opened_.grid()
    p = opened_.drawer_panel("TAU ALPHA")

    assert closed.prop("openDrawerId") == "", "o caso de controle deveria estar SEM gaveta"
    # Âncora de PREMISSA: "nada desloca" só é observação sobre a view se a gaveta
    # de `down` abriu. Sem ela, o verde seria verdade numa view sem gaveta nenhuma.
    assert opened_.prop("openDrawerId") == "tau" and opened_.has("TAU ALPHA"), (
        "em `down` a gaveta não abriu com conteúdo (openDrawerId=%r): 'nada "
        "desloca' seria verdade por ausência" % (opened_.prop("openDrawerId"),))
    assert abs(g1.x - g0.x) <= 0.5, (
        "em `down` a grade não pode deslocar horizontalmente; x foi de %g para %g. %s"
        % (g0.x, g1.x, where(g1, p)))
    assert p.y >= g1.y + 1, (
        "em `down` o painel deveria começar ABAIXO da grade; %s" % where(g1, p))
    assert abs(p.w - g1.w) <= 1, (
        "em `down` o painel deveria ter a largura da grade (%g vs %g). %s"
        % (p.w, g1.w, where(g1, p)))
    assert not opened_.faded(), (
        "em `down` não há recorte lateral, logo não deveria haver fade: %s"
        % [(n.x, n.w) for n in opened_.faded()])


def test_a_geometria_de_down_nao_e_a_de_left(bancada):
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    Controle cruzado: `down` e `left` não compartilham geometria.

    Sem isto, uma implementação que ignorasse ``drawerDirection`` e desenhasse
    sempre ``down`` passaria nos dois testes acima (o de ``down`` por ser o
    desenho e o de ``left``... não passaria — mas aqui a falha fica explícita e
    legível, com a geometria que se viu).
    """
    _, down = case_pair("2-down-%d" % WIDE, bancada)
    _, left = case_pair("2-left-%d" % WIDE, bancada)
    gd, gl = down.grid(), left.grid()
    pd, pl = down.drawer_panel("TAU ALPHA"), left.drawer_panel("TAU ALPHA")

    # A régua é o DESENHO de `down` (empilhado abaixo, com a largura da grade), não
    # a desigualdade de uma tupla de coordenadas. A versão anterior comparava
    # ``(grade.x, painel.x, painel.y)`` e passava por 6 unidades de ``y`` num
    # arranjo em que o eixo horizontal — o que a direção governa — era IDÊNTICO
    # nas duas direções. Medir a relação nomeada é o que impede esse acidente.
    assert caiu_no_desenho_de_down(gd, pd), (
        "o caso `down` não desenhou `down` (painel abaixo da grade, com a largura "
        "dela): não serve de referência. %s" % where(gd, pd))
    assert not caiu_no_desenho_de_down(gl, pl), (
        "`left` desenhou o empilhamento de `down` — a setting de direção é "
        "ignorada: %s" % where(gl, pl))


@alteracao
def test_o_deslocamento_sobrevive_a_troca_de_provider(bancada):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    A transição não é só da primeira abertura: trocar o provider com a gaveta
    aberta mantém a grade deslocada e o painel ao lado.

    A troca é feita clicando OUTRA pílula — que só é alcançável porque ela
    permanece clicável durante o deslocamento. Um teste que só abrisse a gaveta
    não veria uma implementação que "desloca ao abrir e volta ao trocar".
    """
    caso = "swap-left"
    opened_ = snap_of(bancada, caso, "tau")
    trocado = snap_of(bancada, caso, "swap")
    g1, g2 = opened_.grid(), trocado.grid()
    p = trocado.drawer_panel("BIANCA B")

    assert opened_.prop("openDrawerId") == "tau", (
        "a primeira gaveta não abriu em Tau: %r" % (opened_.prop("openDrawerId"),))
    assert trocado.prop("openDrawerId") == "bianca", (
        "o clique na outra pílula não trocou o provider: %r. Censo: %s"
        % (trocado.prop("openDrawerId"), trocado.texts))
    assert abs(g2.x - g1.x) <= 1, (
        "o deslocamento da grade mudou na troca de provider (x %g -> %g): %s"
        % (g1.x, g2.x, where(g2, p)))
    assert g2.x > 12 + 1, (
        "depois da troca a grade voltou para a origem (x=%g): o deslocamento se "
        "perdeu. %s" % (g2.x, where(g2, p)))


# --------------------------------------------------------------------------- #
# 2. A seta alta que devolve à grade
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("cols", COLS)
@alteracao
def test_a_seta_aponta_para_onde_as_pilulas_foram(bancada, cols):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    A faixa alta exibe ``→`` quando as pílulas foram para a direita (``left``) e
    ``←`` quando foram para a esquerda (``right``).

    O glifo é afirmado contra a GEOMETRIA no mesmo censo: a seta certa com as
    pílulas do lado errado seria uma seta mentirosa. E ela vive DENTRO do painel,
    na PONTA do lado expandido (a ponta voltada para a grade), que é o que a emenda
    descreve ("na ponta do detalhe").
    """
    _, left = case_pair("%d-left-%d" % (cols, WIDE), bancada)
    _, right = case_pair("%d-right-%d" % (cols, WIDE), bancada)

    for s, sym, direcao in ((left, ARROW_RIGHT, "esquerda"),
                            (right, ARROW_LEFT, "direita")):
        g = s.grid()
        p = s.drawer_panel("TAU ALPHA")
        a = s.arrow(sym)
        oposto = ARROW_LEFT if sym == ARROW_RIGHT else ARROW_RIGHT
        assert not [x for x in s.arrows() if x.text == oposto], (
            "a faixa mostra o glifo OPOSTO (%r) além de %r: %s"
            % (oposto, sym, [(x.text, x.x, x.y) for x in s.arrows()]))
        # Dentro do painel (com suas bordas).
        assert p.x - 1 <= a.x and a.x + a.w <= p.x + p.w + 1, (
            "a faixa %r está fora do painel: faixa x=%g..%g, painel x=%g..%g"
            % (sym, a.x, a.x + a.w, p.x, p.x + p.w))
        # Na PONTA voltada para a grade.
        if direcao == "esquerda":   # painel à esquerda: ponta = lado direito
            dist = (p.x + p.w) - (a.x + a.w)
            assert dist <= 28, (
                "em `left` a faixa deveria estar na ponta DIREITA do painel "
                "(distância %g px da ponta): %s" % (dist, where(g, p)))
        else:
            dist = a.x - p.x
            assert dist <= 28, (
                "em `right` a faixa deveria estar na ponta ESQUERDA do painel "
                "(distância %g px da ponta): %s" % (dist, where(g, p)))


@pytest.mark.parametrize("direcao,sym", (("left", ARROW_RIGHT), ("right", ARROW_LEFT)))
@alteracao
def test_clicar_a_seta_devolve_a_grade_e_a_pilula_volta_a_abrir(bancada, direcao, sym):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    Clicar a faixa **retorna à grade**: o deslocamento desfaz, o painel sai da
    árvore, e a pílula volta a abrir.

    A terceira parte ("volta a abrir") é o que impede um verde por vazio: uma view
    que simplesmente sumisse com a pílula também satisfaria "o detalhe saiu".
    """
    caso = "return-" + direcao
    aberto = snap_of(bancada, caso, "open")
    voltou = snap_of(bancada, caso, "back")
    reabriu = snap_of(bancada, caso, "again")

    assert aberto.prop("openDrawerId") == "tau", (
        "a gaveta não abriu antes do clique na seta: %r" % (aberto.prop("openDrawerId"),))
    assert aberto.has("TAU ALPHA"), "a gaveta não expôs o detalhe antes do clique"
    assert aberto.arrow(sym) is not None

    # 1. O detalhe saiu.
    assert not voltou.has("TAU ALPHA"), (
        "clicar a faixa %r não fechou a gaveta: o detalhe continua na árvore: %s"
        % (sym, [t for t in voltou.texts if "TAU" in t.upper()]))
    assert voltou.prop("openDrawerId") == "", (
        "openDrawerId não voltou a vazio: %r" % (voltou.prop("openDrawerId"),))
    # 2. A grade voltou ao lugar de origem.
    assert voltou.grid().x <= 12.5, (
        "a grade não voltou à origem depois do clique na faixa: x=%g"
        % (voltou.grid().x,))
    assert not voltou.faded(), (
        "o fade do recorte ficou depois de voltar à grade: %s"
        % [(n.x, n.w) for n in voltou.faded()])
    # 3. A pílula continua clicável e reabre.
    assert reabriu.prop("openDrawerId") == "tau" and reabriu.has("TAU ALPHA"), (
        "depois de voltar à grade a pílula não reabre a gaveta: %r / %s"
        % (reabriu.prop("openDrawerId"),
           [t for t in reabriu.texts if "TAU" in t.upper()]))


@alteracao
def test_em_down_nao_existe_a_faixa_de_retorno(bancada):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    Em ``down`` o recolher é o controle do rodapé da gaveta, não a faixa lateral
    (T38.4). A faixa não pode aparecer ali: ela promete um deslocamento que ``down``
    não faz.

    Controle de vacuidade: em ``left``, no MESMO modelo, a faixa existe — senão
    "não apareceu" seria verdade mesmo com a faixa morta na view inteira.
    """
    _, down = case_pair("2-down-%d" % WIDE, bancada)
    _, left = case_pair("2-left-%d" % WIDE, bancada)
    assert left.arrows(), (
        "no caso de controle (left) a faixa não apareceu — a asserção de `down` "
        "seria vácua")
    assert not down.arrows(), (
        "em `down` apareceu faixa de retorno lateral: %s"
        % [(a.text, a.x, a.y) for a in down.arrows()])


def test_o_recolher_de_down_existe_e_fecha_a_gaveta(bancada):
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    ``down`` tem controle próprio de recolher (T38.4) e ele fecha a gaveta.

    O controle é achado por POSIÇÃO e comportamento (vive abaixo da grade, não é
    pílula, tem sinal ``clicked``), não pelo rótulo traduzido: um teste que
    dependesse do texto quebraria ao trocar de idioma sem que houvesse defeito.
    """
    caso = "collapse-down"
    aberto = snap_of(bancada, caso, "open")
    depois = snap_of(bancada, caso, "after")
    assert aberto.prop("openDrawerId") == "tau", "a gaveta não abriu — nada a recolher"
    assert aberto.has("TAU ALPHA"), "a gaveta não expôs o detalhe"
    assert not depois.has("TAU ALPHA"), (
        "o controle de recolher de `down` não fechou a gaveta: %s"
        % [t for t in depois.texts if "TAU" in t.upper()])
    assert depois.prop("openDrawerId") == "", (
        "openDrawerId não voltou a vazio: %r" % (depois.prop("openDrawerId"),))
    # O que NÃO deve acontecer: recolher apaga a pílula.
    assert depois.has("Pill Tau"), "recolher a gaveta apagou a pílula do provider"


# --------------------------------------------------------------------------- #
# 3. Pílulas visíveis, inteiras ou parciais, são clicáveis
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("direcao", ("left", "right"))
@pytest.mark.parametrize("cols", (3, 4))
@alteracao
def test_pilula_parcialmente_visivel_troca_o_provider(bancada, direcao, cols):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    Uma pílula CORTADA pela borda do recorte continua sendo alvo: clicar a parte
    visível dela troca o provider selecionado.

    Por que a fatia visível e não o centro: o centro geométrico de uma pílula
    cortada está FORA do popout, então um clique no centro não chegaria nela. A
    sonda calcula o meio da interseção entre a célula e a caixa de conteúdo — se a
    implementação só funcionasse pelo centro, este teste falharia, que é o
    comportamento desejado.

    A âncora é dupla: a célula 1 tem de estar REALMENTE cortada (0 < visível <
    total) e a gaveta tem de estar aberta antes do clique. Sem isso, o teste
    passaria clicando uma pílula inteira.

    O que NÃO se exige: um piso de visibilidade. O dono diz que "apenas metade de
    uma das colunas permaneça visível" é ACEITÁVEL — permissão, não garantia — e a
    sonda mede fatias bem menores (19 px de 120/141). A garantia afirmada é a do
    contrato: a fatia visível é > 0 e clicar nela troca o provider. Ver
    ``LACUNAS_DE_OBSERVACAO['piso_da_pilula_parcial']``.
    """
    caso = "partial-%s-%d" % (direcao, cols)
    antes = snap_of(bancada, caso, "open")
    depois = snap_of(bancada, caso, "hit")

    assert antes.prop("openDrawerId") == "tau", (
        "a gaveta não abriu antes do clique na pílula parcial: %r"
        % (antes.prop("openDrawerId"),))
    eventos = [l for l in bancada["raw"].splitlines() if "PILLIX|1|" in l]
    assert eventos, (
        "a sonda não conseguiu mirar a célula 1 — a asserção seria vácua. "
        "CLICK_MISS: %s" % [l.strip() for l in bancada["raw"].splitlines() if "CLICK_MISS" in l][:6])
    # A pílula alvo estava cortada: parte visível estritamente menor que o total.
    alvo = None
    for linha in eventos:
        campos = linha.split("PILLIX|", 1)[1].split("|")
        if len(campos) >= 4:
            visivel, total = float(campos[2]), float(campos[3])
            if 0 < visivel < total - 0.5:
                alvo = (campos[1], visivel, total)
    assert alvo is not None, (
        "a célula 1 não estava CORTADA em nenhuma execução — o caso não exercitou a "
        "pílula parcial: %s" % eventos)

    assert depois.prop("openDrawerId") not in ("", "tau"), (
        "clicar a pílula parcial não trocou o provider (openDrawerId=%r): a pílula "
        "cortada deixou de ser alvo. %s"
        % (depois.prop("openDrawerId"), alvo))
    # E a gaveta mostra o provider NOVO — o clique não foi só "algo aconteceu".
    nome = depois.prop("openDrawerId").upper()
    assert any(nome[:4] in t.upper() for t in depois.texts), (
        "a gaveta não passou a mostrar o provider clicado (%r): %s"
        % (depois.prop("openDrawerId"), depois.texts))
    # O que NÃO deve acontecer: a pílula clicada sumir da grade.
    assert depois.grid_cells(), "a grade ficou sem células depois do clique"


@pytest.mark.parametrize("direcao", ("left", "right"))
@alteracao
def test_pilula_inteira_continua_clicavel_com_a_gaveta_aberta(bancada, direcao):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    Pílulas inteiras continuam alvo durante o deslocamento.

    Este é o caso fácil de esquecer: durante o deslocamento a grade fica
    parcialmente fora da view, e uma implementação que desabilitasse a grade
    ("enquanto a gaveta está aberta") passaria no teste do deslocamento e falharia
    aqui.

    A troca é por TEXTO (a pílula inteira, não a fatia): é o caminho que o usuário
    faz quando a pílula que ele quer está visível por completo.
    """
    caso = "swap-" + direcao
    antes = snap_of(bancada, caso, "tau")
    depois = snap_of(bancada, caso, "swap")
    assert antes.prop("openDrawerId") == "tau", (
        "a gaveta não estava aberta no censo de partida: %r"
        % (antes.prop("openDrawerId"),))
    assert antes.has("Pill Bianca"), (
        "a pílula Bianca não está na árvore com a gaveta aberta: %s" % antes.texts)

    # PREMISSA do enunciado — e a vacuidade que este teste teve até a revisão T45:
    # "clicável DURANTE o deslocamento" degenera em "clicável" quando não se exige
    # o deslocamento. Numa árvore em que a grade nunca sai da origem (``x == pad``)
    # o clique na pílula funciona igual e o teste passa sem exercitar a emenda —
    # foi exatamente assim que ele sobreviveu ao revert-and-test, com a grade em
    # x=12 e o painel por cima. O sinal é positivo e vem da DIREÇÃO: nenhum pixel
    # novo é fixado, só a origem do conteúdo e o sinal do eixo.
    pad = float(antes.prop("pad"))
    eixo = 1.0 if direcao == "left" else -1.0
    for rotulo, censo in (("antes do clique", antes), ("depois do clique", depois)):
        deslocamento = censo.grid().x - pad
        assert eixo * deslocamento > 0.5, (
            "em `%s` a grade não estava deslocada no censo '%s' (x=%g, origem do "
            "conteúdo=%g, deslocamento=%g): a premissa 'pílula clicável DURANTE o "
            "deslocamento' não foi exercitada e o verde seria vazio."
            % (direcao, rotulo, censo.grid().x, pad, deslocamento))

    assert depois.prop("openDrawerId") == "bianca", (
        "a pílula inteira não respondeu ao clique com a gaveta aberta em %s: %r"
        % (direcao, depois.prop("openDrawerId")))


# --------------------------------------------------------------------------- #
# 4. Fade na borda do recorte
# --------------------------------------------------------------------------- #

def _borda_do_recorte(s: Snap, direcao: str):
    """A borda EXTERNA do viewport onde as pílulas são recortadas.

    Em ``left`` a grade desloca para a direita e o excedente é cortado na borda
    **direita** do content box; em ``right``, na **esquerda**. É a posição que o
    dono fixou depois do smoke: "o fade fica na borda externa do viewport onde as
    pílulas são recortadas, não na costura com a gaveta".

    Devolve ``(inicio, fim, borda, na_borda, fora)``, onde ``inicio``/``fim`` são
    os limites do content box: é a faixa VISÍVEL, e um gradiente desenhado fora
    dela não indica recorte nenhum.
    """
    pad = s.prop("pad")
    cw = s.prop("contentWidth")
    assert isinstance(pad, (int, float)) and isinstance(cw, (int, float)), (
        "a view não resolveu pad/contentWidth (%r/%r): sem eles não há como medir a "
        "borda do recorte" % (pad, cw))
    inicio, fim = float(pad), float(pad) + float(cw)
    borda = fim if direcao == "left" else inicio
    na_borda, fora = [], []
    for f in s.faded():
        # A faixa TOCA a borda do corte: o gradiente começa, termina ou atravessa.
        toca = f.x - 1 <= borda <= f.x + f.w + 1
        (na_borda if toca else fora).append(f)
    return inicio, fim, borda, na_borda, fora


@pytest.mark.parametrize("cols", COLS)
@pytest.mark.parametrize("width", (NARROW, WIDE))
@alteracao
def test_o_fade_fica_na_borda_do_recorte_em_left(bancada, cols, width):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    Pílulas cortadas recebem **sombra ou fade na borda do recorte** — e a borda é
    a EXTERNA do viewport: em ``left``, a borda DIREITA do content box.

    A emenda aceita "sombra ou fade", então a asserção é a presença de um gradiente
    (a sonda reconhece as duas formas: a propriedade ``gradient`` do retângulo e um
    item de gradiente com ``stops``) e a POSIÇÃO dele: encostado na borda por onde
    o popout CORTA as pílulas. O dono fixou essa leitura depois do smoke, contra a
    alternativa de pôr o gradiente na costura com a gaveta.

    Três âncoras contra verde vazio: (a) com a gaveta fechada não há fade — sem
    recorte não há o que indicar; (b) a grade de fato TRANSBORDA essa borda, então
    existe pílula sendo cortada ali; (c) a faixa do gradiente tem parte VISÍVEL
    dentro do viewport — um gradiente desenhado do lado de fora não sinaliza nada.

    A altura coberta é a faixa das pílulas: o fade é indicador do corte, não um
    risco decorativo.
    """
    closed, opened_ = case_pair("%d-left-%d" % (cols, width), bancada)
    g = opened_.grid()
    p = opened_.drawer_panel("TAU ALPHA")
    inicio, fim, borda, na_borda, _ = _borda_do_recorte(opened_, "left")

    assert not closed.faded(), (
        "com a gaveta fechada já existe fade (não há recorte a indicar): %s"
        % [(n.x, n.y, n.w, n.h) for n in closed.faded()])
    assert opened_.faded(), (
        "nenhum fade/sombra na view com a gaveta aberta: a pílula cortada fica sem "
        "aviso visual de que continua. %s" % where(g, p))
    assert g.x + g.w > borda + 1, (
        "a grade não passa da borda do recorte (grade até x=%g, borda x=%g): não há "
        "pílula cortada a indicar e a asserção seria vácua. %s"
        % (g.x + g.w, borda, where(g, p)))
    assert na_borda, (
        "nenhum fade/sombra na borda do RECORTE (x=%g, borda direita do viewport). "
        "Colocar o gradiente na costura com a gaveta foi descartado pelo dono. "
        "Fades na árvore: %s. %s"
        % (borda, [(f.x, f.x + f.w) for f in opened_.faded()], where(g, p)))
    visivel = [f for f in na_borda if min(f.x + f.w, fim) - max(f.x, inicio) > 0.5]
    assert visivel, (
        "o fade está na borda do recorte mas inteiramente FORA do viewport "
        "(content box %.0f..%.0f; faixas %s): não sinaliza corte nenhum. %s"
        % (inicio, fim, [(f.x, f.x + f.w) for f in na_borda], where(g, p)))
    celulas = opened_.grid_cells()
    topo = min(c.y for c in celulas)
    altura_pilula = max(c.h for c in celulas if c.h > 1)
    assert any(f.y <= topo + 1 and f.y + f.h <= topo + altura_pilula + 60 for f in visivel), (
        "o fade não cobre a faixa das pílulas (topo=%g, altura da pílula=%g; "
        "fades=%s)" % (topo, altura_pilula, [(f.y, f.h) for f in visivel]))


@pytest.mark.parametrize("cols", COLS)
@alteracao
def test_o_fade_fica_na_borda_do_recorte_em_right(bancada, cols):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    Espelho do fade: em ``right`` a grade desloca para a esquerda e é cortada na
    borda ESQUERDA do viewport.

    Um fade sempre à direita passaria no teste de ``left`` e estaria errado aqui —
    é este teste que separa "há um fade" de "há um fade do lado espelhado do
    recorte". A âncora é a grade passar da borda esquerda no mesmo censo.
    """
    _, opened_ = case_pair("%d-right-%d" % (cols, WIDE), bancada)
    g = opened_.grid()
    p = opened_.drawer_panel("TAU ALPHA")
    inicio, fim, borda, na_borda, _ = _borda_do_recorte(opened_, "right")

    assert g.x < borda - 1, (
        "a grade não passa da borda esquerda do viewport (grade x=%g, borda x=%g): "
        "não há pílula cortada a indicar. %s" % (g.x, borda, where(g, p)))
    assert na_borda, (
        "em `right` o fade deveria encostar na borda ESQUERDA do recorte (x=%g); "
        "fades na árvore: %s. %s"
        % (borda, [(f.x, f.x + f.w) for f in opened_.faded()], where(g, p)))
    visivel = [f for f in na_borda if min(f.x + f.w, fim) - max(f.x, inicio) > 0.5]
    assert visivel, (
        "o fade está fora do viewport em `right` (content box %.0f..%.0f; faixas "
        "%s): não sinaliza corte. %s"
        % (inicio, fim, [(f.x, f.x + f.w) for f in na_borda], where(g, p)))



# --------------------------------------------------------------------------- #
# 5. Título fixo, largura constante, altura reservada
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("cols", COLS)
@pytest.mark.parametrize("direcao", DIRECTIONS)
@pytest.mark.parametrize("width", (NARROW, WIDE))
def test_o_titulo_dos_secundarios_fica_fixo(bancada, cols, direcao, width):
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    O título "Other Providers" fica **fixo**: mesma posição, mesma largura e
    mesmo texto com a gaveta fechada e aberta.

    É a exigência explícita da emenda ("manter fixo o título"). Em ``left``/``right``
    a grade desloca, e é tentador deslocar a seção inteira junto — este teste
    separa as duas coisas.
    """
    closed, opened_ = case_pair("%d-%s-%d" % (cols, direcao, width), bancada)
    # Âncora de PREMISSA: a comparação só diz algo se o segundo censo tiver mesmo a
    # gaveta aberta. Sem isto, "o título não se moveu" poderia estar comparando
    # dois estados idênticos por AUSÊNCIA de gaveta.
    assert closed.prop("openDrawerId") == "", (
        "o caso de controle deveria estar SEM gaveta; openDrawerId=%r"
        % (closed.prop("openDrawerId"),))
    assert opened_.prop("openDrawerId") == "tau" and opened_.has("TAU ALPHA"), (
        "a gaveta não abriu no censo de comparação (openDrawerId=%r, detalhe na "
        "árvore=%s): 'título fixo' estaria medindo dois estados iguais por ausência"
        % (opened_.prop("openDrawerId"), opened_.has("TAU ALPHA")))
    t0, t1 = closed.title_node(), opened_.title_node()
    assert t0.text == t1.text, (
        "o título mudou de texto ao abrir a gaveta: %r -> %r" % (t0.text, t1.text))
    assert (round(t0.x, 1), round(t0.y, 1), round(t0.w, 1)) == (
        round(t1.x, 1), round(t1.y, 1), round(t1.w, 1)), (
        "o título se moveu ao abrir a gaveta (%.1f,%.1f,%.1f) -> (%.1f,%.1f,%.1f): "
        "a emenda pede título FIXO em %s" % (t0.x, t0.y, t0.w, t1.x, t1.y, t1.w, direcao))


@pytest.mark.parametrize("cols", COLS)
@pytest.mark.parametrize("direcao", DIRECTIONS)
@pytest.mark.parametrize("width", (NARROW, WIDE))
def test_a_largura_do_popout_nao_muda_ao_abrir_a_gaveta(bancada, cols, direcao, width):
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    A largura do popout é **constante**: abrir a gaveta não a redimensiona.

    A emenda é explícita ("sem alterar a largura do popout"). Se a lateral
    esticasse o popout, o deslocamento seria desnecessário — e é justamente o
    deslocamento que o dono pediu. A altura também é comparada: a única coisa que
    pode crescer em ``down`` é a seção, não o popout.
    """
    closed, opened_ = case_pair("%d-%s-%d" % (cols, direcao, width), bancada)
    assert closed.iw > 0, "o caso fechado não mediu implicitWidth"
    # Âncora de PREMISSA: comparar largura com e sem gaveta exige que a gaveta
    # tenha aberto. Igualdade entre dois censos em que nada abriu é vacuidade por
    # ausência, não "largura constante".
    assert opened_.prop("openDrawerId") == "tau" and opened_.has("TAU ALPHA"), (
        "a gaveta não abriu no censo de comparação (openDrawerId=%r): a igualdade "
        "de implicitWidth/implicitHeight seria vácua"
        % (opened_.prop("openDrawerId"),))
    assert abs(closed.iw - opened_.iw) < 0.01, (
        "implicitWidth mudou ao abrir a gaveta (%g -> %g): a largura do popout deve "
        "ser constante" % (closed.iw, opened_.iw))
    assert abs(closed.ih - opened_.ih) < 0.01, (
        "implicitHeight mudou ao abrir a gaveta (%g -> %g)" % (closed.ih, opened_.ih))


@pytest.mark.parametrize("direcao", ("left", "right"))
@pytest.mark.parametrize("cap", (160, 320, 480))
@alteracao
def test_a_altura_lateral_e_reservada_desde_a_abertura(bancada, direcao, cap):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    A altura da área lateral é **reservada desde a montagem** e **não muda** ao
    abrir/fechar a gaveta.

    O que se mede é o contêiner da seção: com a gaveta FECHADA ele já tem a altura
    que o detalhe vai precisar, e a MESMA altura com a gaveta aberta. É isso que
    evita "redimensionar durante o uso" — a queixa que a emenda nomeia.

    O que este teste NÃO afirma: que a reserva seja igual ao teto. O refinamento do
    dono diz que a reserva é a maior altura necessária entre os detalhes dos
    secundários disponíveis, **limitada** pelo teto — logo pode ser menor que ele.
    Medição da versão em teste: 210 para um detalhe de 6 métricas com teto 320 e
    com teto 480; 144 com teto 160 (o corte de T37 desenha 3 das 6 métricas).
    Afirmar ``== cap`` era a contradição da versão anterior deste arquivo; aqui o
    teto entra só como LIMITE SUPERIOR. A relação "segue o conteúdo, não o teto"
    é o teste seguinte.
    """
    d = bancada["dumps"]["cap-%s-%d" % (direcao, cap)]
    fechada = d["closed"]
    aberta = d["open"]
    h0 = fechada.section().h
    h1 = aberta.section().h

    assert fechada.prop("drawerMaxHeight") == cap, (
        "a view resolveu drawerMaxHeight=%r, esperado %d"
        % (fechada.prop("drawerMaxHeight"), cap))
    assert h0 > 0, (
        "com a gaveta FECHADA a área lateral reservou altura zero (seção h=0): não "
        "há reserva desde a montagem. Em `down` o controle equivalente mede 0 — em "
        "%s, com teto %d, zero significa que a reserva não existe" % (direcao, cap))
    assert h0 <= cap + 1, (
        "a reserva lateral EXCEDE o teto (seção h=%g, teto=%d): o teto é limite "
        "superior, não piso" % (h0, cap))
    assert h1 <= cap + 1, (
        "com a gaveta ABERTA a seção passou do teto (h=%g, teto=%d)" % (h1, cap))
    assert abs(h1 - h0) <= 1, (
        "a altura lateral mudou ao abrir a gaveta (%g -> %g): redimensionamento "
        "durante o uso, que é o que a reserva existe para evitar" % (h0, h1))


@pytest.mark.parametrize("direcao", ("left", "right"))
@alteracao
def test_a_reserva_lateral_segue_o_conteudo_e_nao_o_teto(bancada, direcao):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    Dois tetos que ambos acomodam o detalhe reservam a MESMA altura; um teto
    apertado encolhe a reserva junto com o conteúdo cortado.

    É a prova direta do refinamento: "a maior altura necessária entre os detalhes
    dos secundários disponíveis, limitada pelo teto; não é necessariamente o
    próprio teto". Se a reserva fosse ``drawerMaxHeight``, 320 e 480 dariam
    alturas diferentes — medido: 210 nos dois. Se fosse constante, 160 não daria
    uma reserva menor — medido: 144, porque o corte de T37 desenha 3 das 6
    métricas e a reserva acompanha o que sobrou.

    As comparações são entre CENSOS do mesmo modelo: o oráculo é a relação, não um
    pixel que este arquivo teria inventado.
    """
    h160 = bancada["dumps"]["cap-%s-160" % direcao]["closed"].section().h
    h320 = bancada["dumps"]["cap-%s-320" % direcao]["closed"].section().h
    h480 = bancada["dumps"]["cap-%s-480" % direcao]["closed"].section().h

    assert abs(h320 - h480) <= 1, (
        "com tetos 320 e 480 o detalhe cabe nos dois, mas a reserva mudou "
        "(%g vs %g): a reserva está seguindo o TETO, não a altura necessária"
        % (h320, h480))
    assert h480 < 480 - 1, (
        "com teto 480 e um detalhe que precisa de %g unidades, a reserva foi "
        "forçada ao teto: o dono pediu o contrário — a reserva é a altura "
        "necessária LIMITADA pelo teto" % h480)
    assert h160 <= 160 + 1, (
        "com teto 160 a reserva passou do teto: h=%g" % h160)
    assert h160 < h320 - 1, (
        "o teto apertado (160) corta o detalhe (T37), mas a reserva não acompanhou "
        "o corte (h160=%g, h320=%g): ou a reserva ignora o conteúdo cortado, ou é "
        "uma constante" % (h160, h320))


@pytest.mark.parametrize("direcao", ("left", "right"))
@alteracao
def test_a_reserva_lateral_e_a_maior_altura_entre_os_detalhes(bancada, direcao):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    A reserva é a MAIOR altura entre os detalhes dos secundários **disponíveis**.

    Comparação no mesmo teto (480) e na mesma direção, mudando só o modelo: o caso
    ``reserve-small`` tem secundários de no máximo 3 métricas, o caso ``cap-*`` tem
    um secundário de 6. A reserva menor tem de ser a do conjunto menor — é isso que
    "maior altura necessária entre os detalhes" significa, e uma reserva fixa
    passaria no teste anterior sem passar neste.
    """
    pequeno = bancada["dumps"]["reserve-small-%s" % direcao]["closed"].section().h
    grande = bancada["dumps"]["cap-%s-480" % direcao]["closed"].section().h

    assert pequeno > 0, (
        "o caso de detalhes pequenos reservou altura zero: a comparação seria "
        "vácua (seção h=%g)" % pequeno)
    assert pequeno < grande - 1, (
        "com secundários de no máximo 3 métricas a reserva (%g) não é menor que a "
        "do secundário de 6 métricas (%g): a reserva não é a maior altura entre os "
        "detalhes disponíveis" % (pequeno, grande))


@pytest.mark.parametrize("cap", (160, 320, 480))
def test_em_down_nao_ha_reserva_de_altura_lateral_fechada(bancada, cap):
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    ``down`` preservado: com a gaveta fechada a seção NÃO reserva altura de teto
    (senão o popout carregaria um vazio permanente de até 480 px).

    Este é o controle do teste de reserva: sem ele, uma view que reservasse sempre
    passaria nos dois, e a diferença entre as direções — que é o contrato — não
    estaria medida.
    """
    d = bancada["dumps"]["cap-down-%d" % cap]
    fechada, aberta = d["closed"], d["open"]
    h0, h1 = fechada.section().h, aberta.section().h
    assert h0 < cap - 1, (
        "em `down` com a gaveta fechada a seção reservou %g px (teto %d): o popout "
        "fica com um vazio permanente" % (h0, cap))
    assert h1 > h0 + 1, (
        "em `down` a seção não cresceu ao abrir a gaveta (%g -> %g): a gaveta não "
        "empurra para baixo" % (h0, h1))



# --------------------------------------------------------------------------- #
# 6. Rodapé: divisória acima, botões alinhados
# --------------------------------------------------------------------------- #

def _footer_container(s: Snap) -> Node:
    """O contêiner do rodapé: o filho do tronco que tem uma divisória (linha fina e
    larga) E pelo menos dois controles.

    Achado por estrutura (linha + controles), não por nome de componente: a emenda
    fala de "divisória acima do conteúdo" e "botões alinhados", não de classes.
    """
    for c in s.blocks():
        sub = s.subtree(c.id)
        linha = [n for n in sub if n.kind.startswith("QQuickRectangle")
                 and n.h <= 2.01 and n.w > 40]
        controles = [n for n in sub if n.interactive]
        if linha and len(controles) >= 2:
            return c
    raise AssertionError(
        "nenhum contêiner de rodapé com divisória e dois controles; filhos do tronco: "
        "%s" % [(c.kind, c.y, c.h, [t for t in (x.text for x in s.subtree(c.id)) if t][:3])
                for c in s.blocks()])


@alteracao
def test_o_rodape_tem_divisoria_acima_dos_botoes_com_espacamento(bancada):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    A divisória do rodapé fica **acima** do conteúdo, **com espaçamento**.

    "Acima" é medido em y (a linha termina antes de os controles começarem) e
    "espaçamento" é medido como uma folga positiva entre a base da linha e o topo do
    controle mais alto — divisória colada no botão é o estado que a emenda corrige.
    """
    s = snap_of(bancada, "footer-issues", "s")
    rodape = _footer_container(s)
    sub = s.subtree(rodape.id)
    linhas = [n for n in sub if n.kind.startswith("QQuickRectangle")
              and n.h <= 2.01 and n.w > 40]
    controles = [n for n in sub if n.interactive]
    assert linhas, "o rodapé não tem divisória"
    assert len(controles) >= 2, (
        "o rodapé deveria ter dois controles (copiar e atualizar); achei %d" % len(controles))

    linha = max(linhas, key=lambda n: n.w)
    assert all(n.y >= linha.y for n in controles), (
        "a divisória não está ACIMA dos controles: linha y=%g, controles y=%s"
        % (linha.y, [round(n.y, 1) for n in controles]))
    topo_conteudo = min(n.y for n in controles)
    folga = topo_conteudo - (linha.y + linha.h)
    assert folga >= 2, (
        "a divisória está colada no conteúdo (folga=%g px entre a linha e o topo dos "
        "controles): a emenda pede espaçamento" % folga)


@alteracao
def test_os_botoes_do_rodape_estao_alinhados_entre_si_e_com_o_status(bancada):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    Os botões de copiar e atualizar ficam **alinhados entre si** e **com o texto
    de status**.

    "Alinhados" é comparado no centro vertical de cada elemento (o texto de status,
    o rótulo do copiar e o glifo do atualizar). Comparar as bordas puniria uma
    diferença legítima de altura de alvo; o centro é o que o olho lê como alinhado,
    e é o que a emenda descreve ("alinhar ... entre si e com o texto de status").
    """
    s = snap_of(bancada, "footer-issues", "s")
    rodape = _footer_container(s)
    sub = s.subtree(rodape.id)

    status = [n for n in sub if "provider" in n.text.lower() or "updated" in n.text.lower()]
    rotulos = [n for n in sub if "copy" in n.text.lower()]
    icones = [n for n in sub if n.text in ("\u21bb",)]
    assert status, "o rodapé não mostra o texto de status: %s" % [n.text for n in sub if n.text]
    assert rotulos, "o rodapé não mostra o botão de copiar: %s" % [n.text for n in sub if n.text]
    assert icones, "o rodapé não mostra o botão de atualizar: %s" % [n.text for n in sub if n.text]

    def centro(n: Node) -> float:
        return n.y + n.h / 2

    c_status = centro(status[0])
    for n in rotulos + icones:
        assert abs(centro(n) - c_status) <= 2, (
            "elemento do rodapé desalinhado do status: %r centro=%g, status centro=%g "
            "(status y=%g h=%g, elemento y=%g h=%g)"
            % (n.text or n.kind, centro(n), c_status, status[0].y, status[0].h, n.y, n.h))

    # Os dois botões também estão alinhados entre si.
    centros = [centro(n) for n in rotulos + icones]
    assert max(centros) - min(centros) <= 2, (
        "os botões do rodapé não estão alinhados entre si: centros=%s"
        % [round(c, 1) for c in centros])


def test_o_rodape_e_o_ultimo_bloco_da_view(bancada):
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    O rodapé é o ÚLTIMO bloco: nada (nem a área lateral reservada) vem depois
    dele.

    Em ``left``/``right`` a área lateral é reservada com altura de teto; se ela
    ficasse ABAIXO do rodapé, os botões subiriam e desceriam conforme o tamanho do
    popout. A ordem dos blocos é estrutura, não pixel.
    """
    for caso in ("footer-issues", "footer-left"):
        s = snap_of(bancada, caso, "s")
        blocos = s.blocks()
        assert len(blocos) >= 3, "a view tem só %d blocos no tronco" % len(blocos)
        rodape = _footer_container(s)
        assert blocos.index(rodape) == len(blocos) - 1, (
            "%s: o rodapé não é o último bloco (índice %d de %d): %s"
            % (caso, blocos.index(rodape), len(blocos),
               [(b.kind, round(b.y), round(b.h)) for b in blocos]))


def test_copiar_escreve_o_comando_real_no_clipboard(bancada):
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    O botão de copiar coloca **o comando real** no clipboard.

    O valor exigido é o que a decisão R4-v1 nomeia textualmente
    (``ryoku-shell plugin ai-usage``). É o único teste deste arquivo que depende de
    uma string literal, e ela vem da decisão assinada, não de uma escolha do teste.
    """
    s = snap_of(bancada, "copy", "post")
    copias = [l for l in bancada["raw"].splitlines() if "COPY|" in l]
    assert copias, (
        "a sonda não leu o clipboard — a asserção seria vácua. CLICK_MISS: %s"
        % [l.strip() for l in bancada["raw"].splitlines() if "CLICK_MISS" in l][:6])
    # A ÚLTIMA leitura é a deste caso (o clipboard é global no processo).
    texto = json.loads(copias[-1].split("COPY|", 1)[1])
    assert texto.strip() == "ryoku-shell plugin ai-usage", (
        "o botão de copiar não colocou o comando real no clipboard: %r" % texto)
    # E não escreveu setting nenhuma (R5: a view não persiste).
    assert not [k for k in s.saves if k != "T45_PROBE_CONTROL"], (
        "copiar gravou settings %r — a view não persiste (R5)" % (s.saves,))


def test_atualizar_chama_a_recoleta(bancada):
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    O botão de atualizar dispara a coleta de novo.

    A prova é o contador de ``refresh()`` do serviço falso: sem ele, "o botão
    existe" não distinguiria um botão morto de um vivo. O caso de controle é o
    censo ANTES do clique.
    """
    pre = snap_of(bancada, "refresh", "pre")
    post = snap_of(bancada, "refresh", "post")
    assert post.refreshes > pre.refreshes, (
        "o botão de atualizar não chamou refresh(): contador %d -> %d"
        % (pre.refreshes, post.refreshes))


def test_a_view_nunca_grava_setting(bancada):
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    A view não persiste nada (R5) — nem nesta superfície nova.

    Controle de vacuidade embutido: o caso ``footer-clean`` dispara ``saveSetting``
    uma vez de propósito, então "não gravou" é uma observação sobre a view, não
    sobre um gancho quebrado.
    """
    assert "SAVE_PROBE_OK|1" in bancada["raw"], (
        "o controle da sonda não disparou: o gancho saveSetting sintético está "
        "quebrado e a asserção de vacuidade seria falsa")
    assert "T45_PROBE_CONTROL" in snap_of(bancada, "footer-clean", "s").saves, (
        "o controle positivo não chegou ao censo — a leitura de SAVES não funciona")
    for caso, censos in bancada["dumps"].items():
        for nome, s in censos.items():
            gravadas = [k for k in s.saves if k != "T45_PROBE_CONTROL"]
            assert not gravadas, (
                "%s/%s: a view gravou settings %r (R5: o popout não persiste)"
                % (caso, nome, gravadas))


# --------------------------------------------------------------------------- #
# 7. Preservados: acordeão, teto, +N more, sem scroll
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("direcao", ("left", "right"))
@alteracao
def test_o_acordeao_sobrevive_ao_deslocamento(bancada, direcao):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    Abrir a gaveta de outro provider fecha a primeira — e a segunda abre NA
    MESMA direção, com a grade ainda deslocada.

    A segunda metade é o que liga o acordeão à emenda: uma implementação que
    fechasse a gaveta anterior mas voltasse a grade ao lugar deixaria o usuário sem
    onde clicar para ver o detalhe seguinte.
    """
    caso = "accordion-" + direcao
    primeiro = snap_of(bancada, caso, "tau")
    segundo = snap_of(bancada, caso, "sigma")

    assert primeiro.prop("openDrawerId") == "tau", (
        "a primeira gaveta não abriu em Tau: %r" % (primeiro.prop("openDrawerId"),))
    assert segundo.prop("openDrawerId") == "sigma", (
        "a segunda gaveta não abriu em Sigma: %r" % (segundo.prop("openDrawerId"),))
    assert segundo.has("SIGMA CHAT"), "a segunda gaveta não expôs o detalhe"
    assert not segundo.has("TAU ALPHA"), (
        "as métricas da primeira gaveta sobreviveram (acordeão quebrado): %s"
        % [t for t in segundo.texts if t.upper().startswith("TAU")])
    # A grade continua deslocada no segundo estado — comparada com a linha de base
    # do MESMO settings e modelo, porque "deslocado" tem sinal oposto em left/right.
    fechado = snap_of(bancada, "closed-2-%s-%d" % (direcao, WIDE), "s")
    x0 = fechado.grid().x
    assert abs(segundo.grid().x - primeiro.grid().x) <= 1, (
        "a grade voltou enquanto o acordeão trocava de provider: x %g -> %g"
        % (primeiro.grid().x, segundo.grid().x))
    assert abs(segundo.grid().x - x0) > 1, (
        "no segundo estado a grade voltou à posição de origem (x=%g, base=%g): o "
        "acordeão desfez o deslocamento" % (segundo.grid().x, x0))


@pytest.mark.parametrize("direcao", DIRECTIONS)
def test_o_teto_e_o_contador_mais_N_more_sobrevivem(bancada, direcao):
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    O teto corta e o contador diz quantas métricas ficaram de fora — contando
    MÉTRICAS, não linhas, e nas TRÊS direções.

    O número não é fixado no teste: ele é comparado com o censo. Assim o teste
    continua válido com a altura que o layout escolher, mas quebra se o contador
    mentir — o defeito perigoso, porque o host recorta o excesso em silêncio e o
    texto é o único aviso.
    """
    caso = "cap-%s-160" % direcao
    aberto = snap_of(bancada, caso, "open")
    p = aberto.drawer_panel("OMEGA M1")
    rotulos = ["OMEGA M%d" % i for i in range(1, 7)]
    desenhadas = [r for r in rotulos if aberto.has(r)]

    assert aberto.prop("openDrawerId") == "omega", (
        "a gaveta não abriu em Omega: %r" % (aberto.prop("openDrawerId"),))
    assert desenhadas, "a gaveta não desenhou nenhuma métrica com teto pequeno"
    assert len(desenhadas) < 6, (
        "com teto 160 as 6 métricas couberam — o corte não foi exercitado: %s"
        % aberto.texts)
    contadores = aberto.more_counter()
    assert contadores, (
        "gaveta cortada sem o anúncio '+N more' em %s: %s" % (direcao, aberto.texts))
    numero = int(re.search(r"\d+", contadores[0].text).group())
    assert numero == 6 - len(desenhadas), (
        "o contador diz %d omitidas, mas %d foram omitidas (desenhadas: %s) em %s"
        % (numero, 6 - len(desenhadas), desenhadas, direcao))
    assert p.h <= 160.5, (
        "o painel excede o teto de 160 px: h=%g em %s" % (p.h, direcao))


@pytest.mark.parametrize("direcao", DIRECTIONS)
def test_com_teto_generoso_nao_aparece_contador(bancada, direcao):
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    Sem estouro, nenhum ``+N more``.

    Âncora: no MESMO modelo e com teto pequeno o contador aparece — senão "não
    apareceu" poderia ser só um contador que nunca é desenhado.
    """
    generoso = snap_of(bancada, "cap-%s-480" % direcao, "open")
    pequeno = snap_of(bancada, "cap-%s-160" % direcao, "open")

    assert generoso.prop("openDrawerId") == "omega", (
        "a gaveta não abriu no caso de teto generoso: %r" % (generoso.prop("openDrawerId"),))
    assert pequeno.more_counter(), (
        "o caso de controle (teto 160) não tem contador — o negativo seria vácuo")
    assert not generoso.more_counter(), (
        "contador apareceu sem corte em %s: %s"
        % (direcao, [n.text for n in generoso.more_counter()]))
    assert all(generoso.has("OMEGA M%d" % i) for i in range(1, 7)), (
        "com teto generoso a gaveta não desenhou as 6 métricas em %s: %s"
        % (direcao, generoso.texts))


@pytest.mark.parametrize("direcao", ("left", "right"))
def test_o_contador_mais_N_more_e_inerte_na_lateral(bancada, direcao):
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    ``+N more`` não é controle: nenhum ancestral dele é interativo e ele próprio
    não é clicável.

    A prova é estrutural, e não de rótulo: a emenda veta que o ``+N more`` pareça
    um controle. Se ele fosse clicável, o usuário tentaria usá-lo e nada
    aconteceria — comportamento pior que o de um contador só de leitura.
    """
    aberto = snap_of(bancada, "cap-%s-160" % direcao, "open")
    contadores = aberto.more_counter()
    assert contadores, "o caso de controle não tem contador: %s" % aberto.texts
    for no in contadores:
        culpados = [a.kind for a in aberto.ancestors(no.id) if a.interactive]
        assert not culpados, (
            "'+N more' está dentro de um controle %s em %s — deixou de ser inerte"
            % (culpados, direcao))
        assert not no.interactive, "'+N more' foi marcado como nó interativo em %s" % direcao


def test_a_gaveta_lateral_nao_rola(bancada):
    """Controle de preservação — **deve ficar verde no revert-and-test**.

    A gaveta não tem scroll — vetado pelo dono, e é o que justifica o corte com
    ``+N more``.

    A âncora é o corte: no mesmo censo o contador existe, portanto há conteúdo de
    sobra; se houvesse scroll, o contador seria dispensável. Sem essa âncora, "não
    há scroll" seria verdade também numa gaveta vazia.
    """
    for direcao in ("left", "right", "down"):
        aberto = snap_of(bancada, "cap-%s-160" % direcao, "open")
        assert aberto.more_counter(), (
            "%s: o caso não exercitou conteúdo de sobra — a asserção seria vácua"
            % direcao)
        rolagem = aberto.scrollers()
        assert not rolagem, (
            "%s: a gaveta tem elemento rolável %s — o dono vetou scroll"
            % (direcao, [(n.kind, n.w, n.h) for n in rolagem]))


# --------------------------------------------------------------------------- #
# 8. Poll: o deslocamento não se perde
# --------------------------------------------------------------------------- #

@alteracao
def test_o_deslocamento_sobrevive_a_um_poll_do_mesmo_provider(bancada):
    """Específico da emenda — **deve ficar vermelho no revert-and-test**.

    Um poll que mantém o provider aberto não pode fechar a gaveta nem devolver a
    grade ao lugar.

    Sem isso, quem está lendo o detalhe perde o lugar a cada ciclo de coleta — e o
    "deslocamento" seria um estado transitório que ninguém veria.
    """
    caso = "poll-same"
    antes = snap_of(bancada, caso, "open")
    depois = snap_of(bancada, caso, "after")

    assert antes.prop("openDrawerId") == "tau", "a gaveta não abriu antes do poll"
    assert depois.prop("openDrawerId") == "tau", (
        "o poll fechou a gaveta do MESMO provider: %r" % (depois.prop("openDrawerId"),))
    assert depois.has("TAU ALPHA"), (
        "depois do poll a gaveta não mostra mais o detalhe: %s" % depois.texts)
    assert abs(depois.grid().x - antes.grid().x) <= 1, (
        "o deslocamento da grade mudou no poll: x %g -> %g"
        % (antes.grid().x, depois.grid().x))
    assert depois.grid().x > 12 + 1, (
        "a grade voltou ao lugar depois do poll (x=%g), mesmo com a gaveta aberta"
        % (depois.grid().x,))
    # O painel continua do mesmo lado, com a mesma largura.
    p0, p1 = antes.drawer_panel("TAU ALPHA"), depois.drawer_panel("TAU ALPHA")
    assert abs(p0.w - p1.w) <= 1 and abs(p0.x - p1.x) <= 1, (
        "o painel mudou de lugar/tamanho no poll: (%g,%g) -> (%g,%g)"
        % (p0.x, p0.w, p1.x, p1.w))
