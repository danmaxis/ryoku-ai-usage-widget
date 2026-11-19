# -*- coding: utf-8 -*-
"""Contratos de comportamento da EMENDA T38 — ALTURA LATERAL INDEPENDENTE DO PROVIDER.

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada 4,
tarefa T38 (emenda assinada pelo dono em 2026-10-30 + esclarecimento posterior).
Nenhum arquivo de produto foi lido: nem ``content/Widget.qml``, nem
``service/Main.qml``, nem o ``manifest.json``.

O sintoma que esta suíte contrata
---------------------------------
O esclarecimento do dono, verbatim, é o oráculo:

    "a altura lateral reservada desde a abertura é a maior altura necessária
     entre os detalhes dos secundários disponíveis, limitada pelo teto; não é
     necessariamente o próprio teto. Uma atualização do relatório pode alterar
     essa reserva."

O que isso torna verificável, e o que a suíte NÃO aceita:

* **Não é o teto.** Uma implementação que reserve sempre ``drawerMaxHeight``
  está ERRADA por este contrato, mesmo que passe em tudo o mais. Um teste antigo
  desta base afirmava exatamente ``altura == teto`` — ver
  ``CONFLITO_COM_TESTE_ANTERIOR`` no fim deste cabeçalho.
* **É o MAIOR, não a soma** dos detalhes dos secundários disponíveis.
* **É reservada desde a abertura**: com a gaveta FECHADA (no primeiro censo após
  montar a view, sem nunca ter aberto nada) a área lateral já tem a altura da
  reserva. Abrir e fechar não a muda.
* **Trocar de provider não a muda** — o conjunto de secundários é o mesmo, logo a
  reserva é a mesma. (Isto é o que o nome do arquivo contrata.)
* **Relatório novo pode movê-la** — e a lei (maior detalhe disponível, ≤ teto)
  tem de continuar valendo depois do poll. É assim que "pode acompanhar" vira
  asserção em vez de permissão vazia: o que se proíbe é a reserva **obsoleta**,
  pequena demais para o provider que passou a existir (clipe silencioso) e grande
  demais para os que existem (vazio permanente).
* **Sem scroll** — vetado pelo dono. Nenhuma superfície rolável na área lateral.
* **``down`` preservado** — não reserva altura lateral com a gaveta fechada, e a
  reserva não depende do tamanho do secundário.

Método e limites de observação
------------------------------
``tests/qml/t46_altura_independente_harness.qml`` monta APENAS
``content/Widget.qml`` num processo ``quickshell`` OFFLINE (offscreen) com
``pluginApi`` sintético. O ``ai-usagebar`` nunca roda: sem rede, sem credencial,
sem escrita em config.

A sonda despeja a ÁRVORE RENDERIZADA (nó, pai, tipo, texto, geometria, clip). A
reserva é medida na **altura do contêiner da seção de secundários** — o elo da
cadeia de ancestrais da grade que o layout dimensiona. Isso é estrutura de
layout, não nome interno: não há dependência de ``objectName`` nem de nome de
componente em nenhuma asserção deste arquivo.

Como a lei "maior detalhe disponível" é medida sem ler implementação: cada
secundário é medido SOZINHO (caso ``solo-<n>-<teto>``), e a reserva de um
relatório com vários secundários é comparada com o máximo dessas medidas. Assim a
asserção é relacional e não numérica: nada aqui fixa um pixel que o dono não
tenha fixado.

Seleção executável: emenda × controles
---------------------------------------
O nome de cada teste carrega o papel, para que a seleção seja um ``-k`` — nenhum
arquivo de configuração do projeto é tocado (o nome deste ARQUIVO contém
"emenda"/"altura", então esses prefixos não servem como seletor):

* ``test_reserva_*`` — específicos da alteração de altura. **Exigência de gate:
  ZERO verdes quando a reserva é removida** (revert-and-test).
* ``test_ctrl_*`` — controles, antipassividade e o que o dono mandou PRESERVAR
  (``down`` empurrando, ``down`` sem reserva, ausência de scroll, seção ausente
  sem secundários). Esses **devem** ficar verdes no revert: é a prova de que a
  suíte distingue "mudou o que devia" de "quebrou o que não devia".

    python -m pytest tests/test_emenda_altura_independente.py -k reserva   # gate
    python -m pytest tests/test_emenda_altura_independente.py -k ctrl      # preservação
    python -m pytest tests/test_emenda_altura_independente.py              # tudo

Âncoras anti-vacuidade (o que o revert-and-test de 2026-11-04 ensinou)
---------------------------------------------------------------------
Contra a base ``daa1e7a`` (sem reserva alguma) **56 casos específicos passaram**
com 14 px em toda parte: todas as comparações eram relativas a uma régua que
valia o mesmo zero. Quatro âncoras fecham isso, e cada uma derruba uma família
inteira de falso verde:

* **R1** ``base_sem_reserva`` — altura da área com a gaveta fechada em ``down``,
  que é o que o layout ocupa quando NÃO reserva. Toda medida lateral é exigida
  **acima** dessa linha de base; sem ela, ``0 ≤ teto`` e ``0 == 0`` passam.
* **R2** ``esperado > base`` — a régua ``solo(...)`` tem de ser maior que a linha
  de base antes de servir de referência à lei do maior.
* **R3** no relatório truncado: a reserva tem de ser **uma das duas respostas
  coerentes** de "disponíveis" (o maior VISÍVEL ou o maior DO RELATÓRIO), em vez
  de qualquer número — sem decidir a ambiguidade (i), que o dono não assinou.
* **R0** ``test_reserva_regua_nao_e_zero`` — piso explícito da régua.

``LACUNAS_DE_OBSERVACAO`` lista o que este arquivo NÃO consegue provar. Nenhuma
asserção depende de nada dessa lista.

Ambiguidades registradas, não resolvidas por invenção
-----------------------------------------------------
(i) "**disponíveis**" não diz se um secundário ESCONDIDO por
    ``maxSecondary``/``showSecondaries`` conta para a reserva. Medido na base
    atual: ele NÃO conta (a reserva segue as pílulas que o usuário pode
    selecionar), o que é a leitura mais coerente — provider que não se pode abrir
    não tem detalhe a exibir. A suíte NÃO afirma essa leitura: em relatório
    truncado ela só exige o lado seguro, ``reserva >= maior detalhe VISÍVEL``,
    que é verdade sob as duas leituras. Ver
    ``test_relatorio_truncado_nunca_reserva_menos_que_o_maior_visivel``.
(ii) O termo ``0.6 x altura de tela`` do teto não entra: o harness offscreen
    devolve uma geometria de tela que não é a do dono, e afirmar sobre ela seria
    medir o harness.

CONFLITO_COM_TESTE_ANTERIOR (relatado, não corrigido aqui — este arquivo não
altera testes existentes): ``test_t45_gaveta_lateral_deslocamento_isolado.py``
afirma ``abs(altura_da_secao - teto) <= 1`` fechada e aberta
(``test_a_altura_lateral_e_reservada_desde_a_abertura``). Isso é a regra ANTIGA
("reserva == teto") e contradiz o esclarecimento do dono, que este arquivo
contrata. As duas afirmações não podem ser verdadeiras ao mesmo tempo; o
orquestrador decide qual sobrevive.
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
PLUGIN_DIR = Path(os.environ.get("T46_PLUG_DIR", TEST_DIR.parent))
#: Instrumento próprio por decisão declarada. A sonda de T45 é de outro contrato e
#: está em movimento (untracked); herdá-la acoplaria duas suítes. Para trocar de
#: instrumento sem editar este arquivo: ``T46_HARNESS=/caminho/sonda.qml``.
HARNESS = Path(os.environ.get("T46_HARNESS",
                              TEST_DIR / "qml" / "t46_altura_independente_harness.qml"))

_QUICK = shutil.which("quickshell") or shutil.which("qs")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

pytestmark = pytest.mark.skipif(
    _QUICK is None,
    reason="quickshell ausente: a view QML não pode ser exercitada",
)

#: LACUNAS DE OBSERVAÇÃO — o que este arquivo NÃO mede, e por quê.
#:
#: Registrado para que um verde não seja lido como prova além do que é.
LACUNAS_DE_OBSERVACAO = {
    "altura_do_popout": (
        "`implicitHeight` do popout não resolve offline (o item não é dimensionado "
        "pelo host). O que resolve é a altura do contêiner da seção — é ela que se "
        "mede. A altura em pixels do popout no shell real continua dependendo do "
        "smoke do dono."),
    "altura_da_gaveta_em_down": (
        "Em `down` a altura da gaveta é derivada de conteúdo e não resolve offline. "
        "De `down` este arquivo afirma: não reserva fechada, cresce ao abrir, e a "
        "reserva fechada não depende do tamanho do secundário. Afirmar o número "
        "final em `down` seria medir o harness."),
    "animacao": (
        "A reserva é medida com a view assentada (900-1200 ms). O comportamento "
        "quadro a quadro — se a altura 'pula' durante a transição — não é "
        "observável aqui."),
    "termo_de_altura_de_tela": (
        "O teto é afirmado contra `drawerMaxHeight`. O segundo termo "
        "(`0.6 x maior altura de tela`, medido em T32) não entra: a geometria de "
        "tela do offscreen não é a do dono."),
    "pixels_exatos_da_reserva": (
        "Nenhum teste fixa um valor absoluto de reserva. A lei é relacional "
        "(reserva == maior detalhe medido sozinho, ≤ teto), porque o dono fixou a "
        "REGRA de altura e não um número."),
}

#: Tipos que rolam. A emenda veta scroll na gaveta.
_SCROLLER = re.compile(r"Flickable|ScrollView|ListView|GridView|ScrollBar|WheelHandler")
_COUNTER = re.compile(r"^\+\d+\s+more$", re.I)


# --------------------------------------------------------------------------- #
# Fixtures de modelo — a forma que a view consome, nada de dado real
# --------------------------------------------------------------------------- #

def metric(label: str, percent: int) -> dict:
    return {
        "label": label,
        "percent": percent,
        "value": "%d%%" % percent,
        "severity": "low",
        "detail": "",
        "reset_at": None,
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


def secundario(n: int) -> dict:
    """Um secundário com `n` métricas.

    O nome é único e NÃO é prefixo de nenhum outro nome desta suíte (``Pill Duo``
    não contém ``Pill Uni``): um clique ou uma busca por substring não pode casar
    dois providers diferentes.
    """
    nomes = {1: "Pill Uni", 2: "Pill Duo", 4: "Pill Qua", 8: "Pill Oct",
             12: "Pill Dod", 20: "Pill Ven"}
    nome = nomes[n]
    return provider("p%02d" % n, nome,
                    [metric("%s M%d" % (nome.split()[-1], i + 1), 10 + (i % 8) * 10)
                     for i in range(n)])


#: Primário fixo em TODOS os casos: ele nunca é o provider medido, e a âncora de
#: "a gaveta não apaga o primário" depende de existir.
PRIMARIO = provider("alpha", "Pill Alpha",
                    [metric("Alpha M1", 10), metric("Alpha M2", 20)])

#: Tamanhos de detalhe exercitados. 1..4 ficam abaixo de qualquer teto testado;
#: 8 e 12 são estouro em teto baixo e caibam em teto alto; 20 estoura sempre.
TAMANHOS = (1, 2, 4, 8, 12, 20)
TETOS = (160, 320, 480)


def modelo(*tamanhos: int) -> dict:
    """Relatório com o primário e os secundários pedidos, na ordem dada."""
    ps = [PRIMARIO] + [secundario(n) for n in tamanhos]
    return {
        "schema": 1,
        "primary": ps[0],
        "secondary": ps[1:],
        "all": ps,
        "total_providers": len(ps),
        "with_issues": 0,
    }


def crescido(pid: str, nome: str, n: int) -> dict:
    """Relatório com o primário e UM secundário de `n` métricas com id/nome dados.

    Existe para o caso "o provider aberto ganhou métricas no poll": o id tem de ser
    o MESMO, senão a gaveta fecha (T39) e o caso mediria outra coisa.
    """
    grande = provider(pid, nome,
                      [metric("%s M%d" % (nome.split()[-1], i + 1), 10 + (i % 8) * 10)
                       for i in range(n)])
    return {"schema": 1, "primary": PRIMARIO, "secondary": [grande],
            "all": [PRIMARIO, grande], "total_providers": 2, "with_issues": 0}


BASE_SETTINGS = {
    "showSecondaries": True,
    "maxSecondary": 12,
    "secondaryLabel": "name",
    "showMetricDetail": True,
    "drawerDirection": "left",
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
# Casos
# --------------------------------------------------------------------------- #

#: Orçamento de largura folgado. A direção lateral desta base cede para `down`
#: quando cobriria a grade inteira (decisão do dono, T38.3); um orçamento apertado
#: faria uma falha de ALTURA ser lida como falha de DIREÇÃO. Todas as asserções de
#: reserva conferem antes que a seção é lateral de fato.
LARGO = 900

SNAP = lambda nome: {"op": "snap", "name": nome}


def abrir_por(n: int, nome: str = "open", ms: int = 900) -> dict:
    """Abre pelo rótulo da métrica líder e pelo nome do provider."""
    rotulo = "%s M1" % secundario(n)["display_name"].split()[-1]
    return {"op": "openDrawer", "text": rotulo, "click": secundario(n)["display_name"],
            "name": nome, "ms": ms}


CASES: list[dict] = []

#: (a) MEDIDA DE REFERÊNCIA: cada secundário sozinho, em cada teto, nas duas
#: laterais. É o "detalhe que aquele provider exige neste teto" — a régua contra a
#: qual a lei do maior é conferida. Sem esta tabela a lei não seria verificável
#: sem inventar um número.
for n in TAMANHOS:
    for teto in TETOS:
        for direcao in ("left", "right"):
            tag = "solo-%d-%d-%s" % (n, teto, direcao)
            CASES.append({"name": "closed-" + tag,
                          "settings": cfg(drawerDirection=direcao, drawerMaxHeight=teto),
                          "model": modelo(n), "widthBudget": LARGO, "epoch": 1750000000,
                          "steps": [SNAP("s")]})
            CASES.append({"name": "open-" + tag,
                          "settings": cfg(drawerDirection=direcao, drawerMaxHeight=teto),
                          "model": modelo(n), "widthBudget": LARGO, "epoch": 1750000000,
                          "steps": [abrir_por(n)]})

#: (b) Relatórios com VÁRIOS secundários, gaveta fechada: a reserva tem de ser o
#: MAIOR detalhe, não a soma nem o primeiro. Os pares são escolhidos para que
#: maior, soma e primeiro sejam três números diferentes.
CONJUNTOS = (
    (1, 2),
    (1, 8),
    (2, 12),
    (4, 20),
    (1, 4, 12),
)
for tamanhos in CONJUNTOS:
    for teto in (320, 480):
        tag = "multi-%s-%d" % ("-".join(map(str, tamanhos)), teto)
        CASES.append({"name": "closed-" + tag,
                      "settings": cfg(drawerDirection="left", drawerMaxHeight=teto),
                      "model": modelo(*tamanhos), "widthBudget": LARGO, "epoch": 1750000000,
                      "steps": [SNAP("s")]})

#: (b2) LINHA DE BASE SEM RESERVA (R1): `down` FECHADO com o maior detalhe do
#: inventário. É a altura que o layout ocupa quando não reserva nada para a
#: gaveta — o piso contra o qual toda medida lateral é comparada. Que `down` não
#: reserve é premissa do próprio contrato (preservado), e é por isso que ele serve
#: de linha de base sem que a suíte precise de uma constante em pixels.
for teto in TETOS:
    CASES.append({"name": "closed-base-down-%d" % teto,
                  "settings": cfg(drawerDirection="down", drawerMaxHeight=teto),
                  "model": modelo(20), "widthBudget": LARGO, "epoch": 1750000000,
                  "steps": [SNAP("s")]})

#: (c) O mesmo relatório, abrindo o MENOR e abrindo o MAIOR: a reserva não pode
#: depender de quem está aberto. Teto 480 para que "reserva == maior" e
#: "reserva == teto" sejam números diferentes e distinguíveis.
for quem in (1, 8):
    CASES.append({"name": "aberto-%d-de-1-8-480" % quem,
                  "settings": cfg(drawerDirection="left", drawerMaxHeight=480),
                  "model": modelo(1, 8), "widthBudget": LARGO, "epoch": 1750000000,
                  "steps": [SNAP("fechado"), abrir_por(quem)]})

#: (d) TROCAR DE PROVIDER com a gaveta aberta: pequeno -> grande e grande ->
#: pequeno, no MESMO relatório. A altura não pode mudar (é o nome do arquivo).
for primeiro, segundo in ((1, 8), (8, 1)):
    CASES.append({"name": "troca-%d-para-%d" % (primeiro, segundo),
                  "settings": cfg(drawerDirection="left", drawerMaxHeight=480),
                  "model": modelo(1, 8), "widthBudget": LARGO, "epoch": 1750000000,
                  "steps": [abrir_por(primeiro),
                            {"op": "clickText", "value": secundario(segundo)["display_name"]},
                            {"op": "wait", "ms": 900, "name": "trocado"}]})

#: (e) RELATÓRIO QUE MUDA por poll: cresce e diminui. A lei tem de valer depois.
CASES += [
    {"name": "poll-cresce", "settings": cfg(drawerDirection="left", drawerMaxHeight=480),
     "model": modelo(1), "widthBudget": LARGO, "epoch": 1750000000,
     "steps": [SNAP("antes"), {"op": "poll", "model": modelo(1, 8), "name": "depois", "ms": 1400}]},
    {"name": "poll-diminui", "settings": cfg(drawerDirection="left", drawerMaxHeight=480),
     "model": modelo(1, 8), "widthBudget": LARGO, "epoch": 1750000000,
     "steps": [SNAP("antes"),
               {"op": "poll", "model": modelo(1), "name": "depois", "ms": 1400}]},
    #: O secundário ABERTO muda de tamanho com o MESMO id: a reserva acompanha e a
    #: gaveta continua aberta (T39: mesmo id presente => a gaveta fica). Construir
    #: este caso com um id diferente fecharia a gaveta — e o teste mediria a
    #: ausência dela, não o crescimento do detalhe.
    {"name": "poll-o-aberto-cresce", "settings": cfg(drawerDirection="left", drawerMaxHeight=480),
     "model": modelo(1), "widthBudget": LARGO, "epoch": 1750000000,
     "steps": [abrir_por(1),
               {"op": "poll", "model": crescido("p01", "Pill Uni", 8),
                "name": "depois", "ms": 1400}]},
]

#: (f) `down` preservado: fechado, aberto e com secundário grande.
for tamanhos in ((1,), (1, 12)):
    for teto in (160, 480):
        tag = "down-%s-%d" % ("-".join(map(str, tamanhos)), teto)
        CASES.append({"name": "closed-" + tag,
                      "settings": cfg(drawerDirection="down", drawerMaxHeight=teto),
                      "model": modelo(*tamanhos), "widthBudget": LARGO, "epoch": 1750000000,
                      "steps": [SNAP("s")]})
        CASES.append({"name": "open-" + tag,
                      "settings": cfg(drawerDirection="down", drawerMaxHeight=teto),
                      "model": modelo(*tamanhos), "widthBudget": LARGO, "epoch": 1750000000,
                      "steps": [SNAP("fechado"), abrir_por(tamanhos[-1])]})

#: (g) Relatório TRUNCADO: o maior secundário existe mas não vira pílula. Ver a
#: ambiguidade (i) no cabeçalho — aqui só se exige o lado seguro.
CASES.append({"name": "truncado-maxsec1",
              "settings": cfg(drawerDirection="left", drawerMaxHeight=480, maxSecondary=1),
              "model": modelo(1, 12), "widthBudget": LARGO, "epoch": 1750000000,
              "steps": [SNAP("s")]})
CASES.append({"name": "sem-secundarios",
              "settings": cfg(drawerDirection="left", drawerMaxHeight=480, showSecondaries=False),
              "model": modelo(1, 12), "widthBudget": LARGO, "epoch": 1750000000,
              "steps": [SNAP("s")]})

#: (h) Controle de vacuidade do DETECTOR de scroll: os tipos que a sonda precisa
#: reconhecer. Sem esta âncora, "nenhum scroller na árvore" poderia significar
#: "o detector não reconhece nada".
TIPOS_ROLaveis = (
    "QQuickFlickable", "QQuickScrollView", "QQuickListView", "QQuickGridView",
    "QQuickScrollBar", "QQuickWheelHandler",
)


# --------------------------------------------------------------------------- #
# Bancada: um processo quickshell para todos os casos
# --------------------------------------------------------------------------- #

class Node:
    __slots__ = ("id", "parent", "kind", "text", "x", "y", "w", "h", "clip", "interactive")

    def __init__(self, fields: list):
        self.id = int(fields[0])
        self.parent = int(fields[1])
        self.kind = fields[2]
        self.text = json.loads(fields[3])
        self.x = float(fields[4])
        self.y = float(fields[5])
        self.w = float(fields[6])
        self.h = float(fields[7])
        self.clip = (fields[8] == "1") if len(fields) > 8 else False
        self.interactive = (fields[9] == "true") if len(fields) > 9 else False

    def __repr__(self) -> str:
        return "<%s#%d y=%g h=%g %r>" % (self.kind, self.id, self.y, self.h, self.text)


class Snap:
    """Censo de um estado da view."""

    _NON_VISUAL = re.compile(
        r"Repeater|Timer|Handler|Behavior|Animation|Transition|Instantiator|Delegate")

    def __init__(self, name: str):
        self.name = name
        self.props: dict[str, object] = {}
        self.iw = self.ih = self.w = self.h = 0.0
        self.nodes: list[Node] = []
        self._by_id: dict[int, Node] = {}
        self._kids: dict[int, list[int]] = {}
        self.misses: list[str] = []

    def finish(self) -> "Snap":
        self._by_id = {n.id: n for n in self.nodes}
        self._kids = {}
        for n in self.nodes:
            self._kids.setdefault(n.parent, []).append(n.id)
        return self

    # -- leitura de conteúdo ------------------------------------------------
    @property
    def texts(self) -> list[str]:
        return [n.text for n in self.nodes if n.text]

    def has(self, needle: str) -> bool:
        up = needle.upper()
        return any(up in t.upper() for t in self.texts)

    def prop(self, name: str):
        return self.props.get(name)

    def subtree(self, nid: int) -> list[Node]:
        out = [self._by_id[nid]]
        for k in self._kids.get(nid, []):
            out.extend(self.subtree(k))
        return out

    # -- estrutura ---------------------------------------------------------
    def raiz(self) -> Node:
        raizes = [n for n in self.nodes if n.parent == 0]
        assert raizes, "a árvore não tem raiz: a view não montou"
        return raizes[0]

    def grade(self):
        """A grade de pílulas, achada por TIPO. Duas grades seria outra view."""
        gs = [n for n in self.nodes if n.kind == "QQuickGrid"]
        if not gs:
            return None
        assert len(gs) == 1, (
            "esperava UMA grade de pílulas; achei %d: %s"
            % (len(gs), [(g.kind, g.y, g.w) for g in gs]))
        return gs[0]

    def cadeia_da_secao(self) -> list[Node]:
        """Ancestrais da grade, da mais próxima à raiz (exclusive).

        Nomear a seção por "filho do tronco" seria arbitrário quando o layout
        ganha um invólucro; por isso a cadeia inteira é devolvida e a RESERVA é a
        maior altura dela. O que se afirma não é "qual nó é a seção", e sim
        "existe um bloco de altura H que contém a grade e não contém o resto".
        """
        g = self.grade()
        if g is None:
            return []
        raiz = self.raiz().id
        out, cur = [], self._by_id.get(g.parent)
        while cur is not None and cur.id != raiz and len(out) < 20:
            out.append(cur)
            cur = self._by_id.get(cur.parent)
        return out

    def altura_da_area(self):
        """A altura RESERVADA para a área da gaveta lateral, em px.

        ``None`` quando não há grade (seção de secundários ausente).
        """
        cadeia = self.cadeia_da_secao()
        if not cadeia:
            return None
        return max(n.h for n in cadeia)

    def detalhe_do_aberto(self) -> list[Node]:
        """Nós que só existem dentro da gaveta: os rótulos das métricas.

        A pílula mostra a métrica líder; a gaveta mostra todas. Um rótulo de
        métrica que aparece DUAS vezes na árvore é (pílula + gaveta). Usado só
        como âncora de "a gaveta abriu", nunca como medida de altura.
        """
        return [n for n in self.nodes if re.match(r"^\S+ M\d+$", (n.text or "").strip())]

    def contador(self) -> list[Node]:
        return [n for n in self.nodes if _COUNTER.match((n.text or "").strip())]

    def rolaveis(self) -> list[Node]:
        return [n for n in self.nodes if _SCROLLER.search(n.kind)]


def _feed(snap: Snap, line: str) -> None:
    if line.startswith("PROP|"):
        parts = line.split("|")
        if len(parts) < 4:
            return
        nome, tipo, valor = parts[1], parts[2], parts[3]
        parsed = None
        if tipo in ("number", "string", "boolean"):
            try:
                parsed = json.loads(valor)
            except ValueError:
                parsed = valor
        snap.props[nome] = parsed
        m = re.search(r"IW\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)$", "|".join(parts[4:]))
        if m:
            snap.iw, snap.ih, snap.w, snap.h = (float(x) for x in m.groups())
    elif line.startswith("NODE|"):
        snap.nodes.append(Node(line.split("|")[1:]))
    elif line.startswith("CLICK_MISS|"):
        snap.misses.append(line)


def _parse(stdout: str) -> dict[str, dict[str, Snap]]:
    casos: dict[str, dict[str, Snap]] = {}
    case = snap = None
    for raw in stdout.splitlines():
        if " qml: " in raw:
            raw = raw.split(" qml: ", 1)[1]
        line = raw.strip()
        if line.startswith("===CASE|"):
            case = line[len("===CASE|"):-3]
            casos.setdefault(case, {})
            snap = None
        elif line.startswith("===CASE_END|"):
            case = snap = None
        elif line.startswith("===SNAP|"):
            assert case is not None, "SNAP fora de um CASE"
            snap = Snap(line[len("===SNAP|"):-3])
            casos[case][snap.name] = snap
        elif line.startswith("===SNAP_END|"):
            assert snap is not None, "SNAP_END sem SNAP"
            snap.finish()
            snap = None
        elif snap is not None and line:
            _feed(snap, line)
    return casos


def _run(cases: list[dict]):
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("WAYLAND_DISPLAY", None)
    env["T46_PLUG_DIR"] = str(PLUGIN_DIR)
    # Cada caso viaja em PARTES: um único valor de ambiente acima de
    # MAX_ARG_STRLEN (128 KiB) impede o processo de iniciar.
    payload = json.dumps(cases, ensure_ascii=False)
    parts = [payload[i:i + 60000] for i in range(0, len(payload), 60000)] or ["[]"]
    for k, part in enumerate(parts):
        env["T46_CASES_%d" % k] = part
    env["T46_CASES_PARTS"] = str(len(parts))
    # stateDir ÚNICO por execução: caminho fixo compartilhado entre duas execuções
    # simultâneas (suítes em paralelo) cria interferência cruzada.
    env["T46_STATE_DIR"] = tempfile.mkdtemp(prefix="t46-state-")
    try:
        proc = subprocess.run([_QUICK, "-p", str(HARNESS)], capture_output=True,
                              text=True, env=env, timeout=1200)
    except subprocess.TimeoutExpired:
        pytest.fail(
            "o harness QML não terminou em 1200s — a view provavelmente não monta "
            "(arquivo ausente/quebrado). Sem view não há comportamento a verificar.")
    out = _ANSI.sub("", proc.stdout + proc.stderr)
    parsed = _parse(out)
    faltando = [c["name"] for c in cases if c["name"] not in parsed]
    assert not faltando, (
        "a sonda não montou os casos %r; rc=%s\nstderr(tail)=%s"
        % (faltando, proc.returncode, out[-1500:]))
    return parsed, out


@pytest.fixture(scope="session")
def bancada():
    parsed, raw = _run(CASES)
    return {"dumps": parsed, "raw": raw}


def snap_of(bancada, caso: str, nome: str = "s") -> Snap:
    assert caso in bancada["dumps"], (
        "caso %r não existe na sonda; tem %r" % (caso, sorted(bancada["dumps"])[:12]))
    d = bancada["dumps"][caso]
    assert nome in d, "o caso %r não censou %r; censos=%r" % (caso, nome, sorted(d))
    return d[nome]


def solo(bancada, n: int, teto: int, direcao: str = "left") -> float:
    """Altura que o secundário de `n` métricas exige sozinho, neste teto."""
    h = snap_of(bancada, "closed-solo-%d-%d-%s" % (n, teto, direcao)).altura_da_area()
    assert h is not None, "caso de referência sem grade: %d/%d/%s" % (n, teto, direcao)
    return h


def base_sem_reserva(bancada, teto: int) -> float:
    """R1 — a altura da área lateral quando NÃO há reserva nenhuma.

    Medida em ``down`` FECHADO com o MAIOR detalhe do inventário (20 métricas): é
    o caso em que uma reserva que vazasse para ``down`` apareceria com o valor
    máximo. Contra esse número toda medida lateral é comparada.

    Este é o piso que faltava: sem ele, ``reserva == max(solo(...))`` fica
    verdadeira com ``14 == 14`` — foi o que o revert-and-test de 2026-11-04 expôs.
    """
    caso = "closed-base-down-%d" % teto
    h = snap_of(bancada, caso, "s").altura_da_area()
    assert h is not None, "caso de linha de base sem grade: %s" % caso
    return h


def exigir_reserva_real(bancada, h, teto: int, contexto: str) -> float:
    """R1 — a medida lateral tem de estar ACIMA da linha de base sem reserva.

    Devolve ``h`` para encadear a asserção específica do teste.
    """
    base = base_sem_reserva(bancada, teto)
    assert h is not None, "%s: caso sem grade" % contexto
    assert h > base + 1, (
        "%s: a área lateral mede %g px e a linha de base SEM reserva (`down` "
        "fechado, 20 métricas) mede %g: não há reserva alguma, e a comparação "
        "relativa deste teste ficaria vacuamente verdadeira"
        % (contexto, h, base))
    return h


def conferir_direcao(s: Snap, esperada: str) -> None:
    """Garante que o caso é mesmo LATERAL antes de afirmar sobre altura.

    Sem isto, uma view que cedesse para `down` (por largura, decisão T38.3) seria
    medida como se fosse lateral e uma falha de DIREÇÃO viraria falha de ALTURA.
    """
    assert s.prop("drawerDirection") == esperada, (
        "esperava direção %r na view; achei %r" % (esperada, s.prop("drawerDirection")))
    assert abs(s.prop("widthBudget") - LARGO) < 0.5, (
        "o orçamento de largura não chegou à view: %r" % (s.prop("widthBudget"),))


# --------------------------------------------------------------------------- #
# 0. A régua: ela não pode valer zero (R0)
# --------------------------------------------------------------------------- #

def test_reserva_regua_nao_e_zero(bancada):
    """R0 — o piso que impede a suíte inteira de ser relativa a zero.

    Todo o resto é comparativo: a lei do maior compara a reserva com ``solo(...)``,
    a simetria compara dois lados, os tetos comparam com ``drawerMaxHeight``. Se a
    MEDIÇÃO de referência valer o mesmo que a linha de base sem reserva, todas
    essas comparações ficam verdadeiras ao mesmo tempo — foi exatamente o que o
    revert-and-test de 2026-11-04 expôs: 56 casos específicos verdes com 14 px em
    toda parte.

    Três asserções, todas falsificáveis na base revertida:
      1. o maior detalhe medido sozinho reserva acima da linha de base;
      2. o menor detalhe também (a reserva não é só do caso extremo);
      3. detalhe maior pede reserva maior (monotonicidade mínima da régua).
    """
    base = base_sem_reserva(bancada, 480)
    grande = solo(bancada, 20, 480)
    pequeno = solo(bancada, 1, 480)
    assert grande > base + 1, (
        "a régua do maior detalhe vale %g px e a linha de base sem reserva vale "
        "%g: nenhuma reserva existe, e toda comparação relativa desta suíte "
        "ficaria vacuamente verdadeira" % (grande, base))
    assert pequeno > base + 1, (
        "a régua do menor detalhe vale %g px e a linha de base vale %g: o caso "
        "pequeno não reserva nada" % (pequeno, base))
    assert grande > pequeno + 1, (
        "20 métricas reservam %g px e 1 métrica reserva %g: a régua não distingue "
        "tamanhos de detalhe, então não pode servir de referência à lei do maior"
        % (grande, pequeno))


# --------------------------------------------------------------------------- #
# 0b. Antipassividade — nada abaixo prova nada sem isto
# --------------------------------------------------------------------------- #

def test_ctrl_artefatos_existem():
    """Falha rápido se a view ou a sonda sumiram: revert não pode virar SKIP."""
    assert (PLUGIN_DIR / "content" / "Widget.qml").is_file(), "content/Widget.qml ausente"
    assert HARNESS.is_file(), "sonda QML ausente: %s" % HARNESS


def test_ctrl_detector_de_scroll():
    """CONTROLE DE VACUIDADE do detector de scroll.

    A asserção "a área lateral não tem scroll" é uma afirmação de AUSÊNCIA. Uma
    regex quebrada a tornaria verdadeira para sempre. Aqui a mesma regex é
    aplicada aos tipos que ela PRECISA reconhecer; se ela parar de casar, este
    teste falha e o de ausência perde a garantia em vez de mentir.
    """
    for tipo in TIPOS_ROLaveis:
        assert _SCROLLER.search(tipo), (
            "o detector de scroll não reconhece %r: a asserção de ausência de "
            "scroll ficaria vacuamente verdadeira" % tipo)
    retangulo = Node(["1", "0", "QQuickRectangle", '""', "0", "0", "1", "1"])
    assert not _SCROLLER.search(retangulo.kind), (
        "o detector de scroll casa um retângulo comum: a asserção de ausência "
        "ficaria sem significado")


def test_ctrl_detector_de_contador():
    """CONTROLE DE VACUIDADE do contador de métricas omitidas.

    O contador é usado como GUARDA: em caso de estouro, a reserva só pode ser
    menor que o teto se o estouro estiver anunciado. Se a regex não casar
    ``+3 more``, a guarda sumiria em silêncio.
    """
    for texto in ("+1 more", "+3 more", "+12 MORE", " +8 more "):
        assert _COUNTER.match(texto.strip()), "o detector não reconhece %r" % texto
    for texto in ("more", "+ more", "3 more", "+3"):
        assert not _COUNTER.match(texto.strip()), "o detector casa %r por engano" % texto


def test_ctrl_view_monta_e_resolve_interface(bancada):
    """Âncora de toda a suíte: sem view montada e sem gaveta, nada abaixo prova nada.

    As propriedades conferidas são o contrato do formato único (T36–T40), não
    mecânica interna: ``columns``, ``drawerDirection``, ``drawerMaxHeight`` e
    ``openDrawerId``.
    """
    s = snap_of(bancada, "closed-solo-1-320-left", "s")
    assert s.texts, "a árvore renderizada está vazia"
    assert s.prop("columns") == 2, "a view não resolveu `columns`: %r" % (s.prop("columns"),)
    assert s.prop("drawerMaxHeight") == 320, (
        "a view não resolveu `drawerMaxHeight`: %r" % (s.prop("drawerMaxHeight"),))
    assert s.prop("openDrawerId") == "", (
        "o censo inicial deveria estar SEM gaveta; openDrawerId=%r"
        % (s.prop("openDrawerId"),))
    assert s.grade() is not None, "a seção de secundários não desenhou grade"
    # Âncora do primário: a reserva não pode apagar a outra seção da view.
    assert s.has("Pill Alpha") and s.has("ALPHA M1"), "a reserva apagou o primário"

    aberto = snap_of(bancada, "open-solo-1-320-left", "open")
    assert aberto.prop("openDrawerId") == "p01", (
        "a gaveta não abriu no provider esperado: openDrawerId=%r"
        % (aberto.prop("openDrawerId"),))
    assert aberto.has("Uni M1"), (
        "a gaveta abriu mas não expôs o detalhe do provider: %s" % aberto.texts[:12])
    assert not aberto.misses, "a sonda não conseguiu clicar: %r" % aberto.misses


# --------------------------------------------------------------------------- #
# 1. O SINTOMA: reserva desde a abertura, e NÃO o teto
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("teto", TETOS)
@pytest.mark.parametrize("n", TAMANHOS)
@pytest.mark.parametrize("direcao", ("left", "right"))
def test_reserva_desde_a_abertura(bancada, n, teto, direcao):
    """Com a gaveta FECHADA a área lateral já tem a altura reservada, e abrir não
    a muda.

    "Desde a abertura do popout" é o que a emenda pede: a altura não pode
    aparecer no clique. O censo fechado é o PRIMEIRO da montagem — nenhuma gaveta
    foi aberta antes dele neste caso.

    A asserção é dupla de propósito: ``fechada == aberta`` sozinha passaria numa
    view que reservasse 0 nas duas pontas; ``> 0`` sozinha passaria numa view que
    crescesse ao abrir. Só as duas juntas são a reserva.
    """
    fechada = snap_of(bancada, "closed-solo-%d-%d-%s" % (n, teto, direcao), "s")
    aberta = snap_of(bancada, "open-solo-%d-%d-%s" % (n, teto, direcao), "open")
    conferir_direcao(fechada, direcao)
    h0, h1 = fechada.altura_da_area(), aberta.altura_da_area()
    assert h0 is not None and h1 is not None, "caso sem grade: não há reserva a medir"
    exigir_reserva_real(bancada, h0, teto,
                        "área lateral fechada (%d métricas, %s)" % (n, direcao))
    assert abs(h1 - h0) <= 1, (
        "a altura da área lateral mudou ao abrir a gaveta (%g -> %g): "
        "redimensionamento durante o uso, proibido pela emenda" % (h0, h1))


@pytest.mark.parametrize("teto", (320, 480))
@pytest.mark.parametrize("n", (1, 2, 4))
def test_reserva_nao_e_o_teto(bancada, n, teto):
    """**A discriminação central.** Com detalhes que cabem folgados, a reserva é a
    altura que eles precisam — não o teto.

    O dono foi explícito: "não é necessariamente o próprio teto". Uma view que
    reserve ``drawerMaxHeight`` sempre passa em todos os outros testes deste
    arquivo (é ≥ o necessário, é estável, é ≤ o teto) e é justamente o
    comportamento que esta emenda remove: com dois providers pequenos e teto 480
    sobraria um vazio permanente de centenas de pixels.

    A folga exigida (> 60 px) é maior que qualquer arredondamento de layout e
    menor que a diferença real observada; não é um pixel mágico.
    """
    fechada = snap_of(bancada, "closed-solo-%d-%d-left" % (n, teto), "s")
    h = fechada.altura_da_area()
    exigir_reserva_real(bancada, h, teto, "área lateral com %d métricas" % n)
    assert h < teto - 60, (
        "com um secundário de %d métricas a área lateral reservou %g px para um "
        "teto de %d: isso é a reserva do TETO, não do maior detalhe disponível. "
        "O dono declarou que a reserva 'não é necessariamente o próprio teto'."
        % (n, h, teto))


@pytest.mark.parametrize("teto", TETOS)
@pytest.mark.parametrize("n", TAMANHOS)
def test_reserva_respeita_o_teto(bancada, n, teto):
    """A reserva nunca passa do teto, nem para detalhe muito maior que ele.

    Este é o limite superior do contrato. Sozinho ele seria fraco (reservar 0
    passaria); por isso convive com o teste do maior detalhe, que fixa o inferior.
    """
    for direcao in ("left", "right"):
        fechada = snap_of(bancada, "closed-solo-%d-%d-%s" % (n, teto, direcao), "s")
        h = fechada.altura_da_area()
        exigir_reserva_real(bancada, h, teto, "área lateral (%d métricas, %s)" % (n, direcao))
        assert h <= teto + 1, (
            "a área lateral reservou %g px com teto %d em %s: a gaveta esticaria o "
            "popout além do teto" % (h, teto, direcao))


@pytest.mark.parametrize("n,teto", ((8, 160), (20, 160), (20, 320)))
def test_reserva_estouro_anuncia_corte(bancada, n, teto):
    """Quando o detalhe não cabe, a reserva fica ABAIXO do teto e o corte é dito.

    A emenda proíbe scroll e manda cortar pela cauda com ``+N more``; a sonda do
    host mostrou que o excesso é recortado em silêncio. Logo, um detalhe que
    estoura o teto tem de produzir (i) reserva ≤ teto e (ii) o contador na
    árvore. Só (i) passaria numa view que escondesse tudo; o contador é a prova
    de que o corte foi anunciado em vez de silencioso.

    A reserva ficar ESTRITAMENTE abaixo do teto é consequência de abrir espaço
    para a linha do contador — e é o que distingue esta implementação de uma que
    apenas cortasse o conteúdo no teto.
    """
    aberta = snap_of(bancada, "open-solo-%d-%d-left" % (n, teto), "open")
    fechada = snap_of(bancada, "closed-solo-%d-%d-left" % (n, teto), "s")
    h = aberta.altura_da_area()
    h_fechada = exigir_reserva_real(bancada, fechada.altura_da_area(), teto,
                                    "reserva FECHADA do estouro de %d métricas" % n)
    contador = aberta.contador()
    assert contador, (
        "o detalhe de %d métricas não coube no teto %d mas nenhum contador '+N "
        "more' foi desenhado: o corte seria silencioso" % (n, teto))
    # A âncora acima é o estado FECHADO de propósito: no estado aberto uma view
    # sem reserva ainda desenha o painel (74 px medidos no revert), o que fica
    # acima da linha de base por acidente e esconderia a ausência da reserva. Foi
    # exatamente assim que 3 casos sobreviveram ao primeiro revert-and-test.
    assert abs(h - h_fechada) <= 1, (
        "a área aberta mede %g px e a reserva fechada do mesmo provider mede %g: "
        "abrir mudou a altura, ou a reserva não é a do provider que estourou"
        % (h, h_fechada))
    assert h <= teto + 1, "reserva %g acima do teto %d" % (h, teto)
    assert h < teto, (
        "com o corte anunciado a área lateral ainda reservou o teto inteiro (%g de "
        "%d): não sobrou espaço para a linha do contador" % (h, teto))


# --------------------------------------------------------------------------- #
# 2. A lei: MAIOR detalhe disponível (não a soma, não o primeiro)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("teto", (320, 480))
@pytest.mark.parametrize("tamanhos", CONJUNTOS)
def test_reserva_lei_do_maior_detalhe(bancada, tamanhos, teto):
    """**A lei do dono.** Com vários secundários, a reserva é o MAIOR detalhe
    entre eles — cada um medido sozinho, na mesma base.

    "Maior" tem três rivais plausíveis, e o conjunto de casos foi escolhido para
    que os três sejam números DIFERENTES: a soma dos detalhes, o detalhe do
    PRIMEIRO secundário, e o teto. A asserção é a igualdade com o máximo; as
    mensagens nomeiam os rivais para que uma falha diga qual deles foi usado.
    """
    caso = "closed-multi-%s-%d" % ("-".join(map(str, tamanhos)), teto)
    s = snap_of(bancada, caso, "s")
    reserva = s.altura_da_area()
    referencia = {n: solo(bancada, n, teto) for n in tamanhos}
    esperado = max(referencia.values())
    primeiro = referencia[tamanhos[0]]
    soma = sum(referencia.values())
    # R2: a régua tem de ser real antes de servir de referência. Sem isto,
    # `reserva == max(régua)` fica verdadeira com tudo zerado (14 == 14).
    base = base_sem_reserva(bancada, teto)
    assert esperado > base + 1, (
        "a régua desta comparação vale %g px e a linha de base sem reserva vale "
        "%g (por provider: %r): nenhum secundário reserva nada, e a igualdade "
        "abaixo seria 0 == 0" % (esperado, base, referencia))
    exigir_reserva_real(bancada, reserva, teto, "relatório %r" % (tamanhos,))
    assert abs(reserva - esperado) <= 1, (
        "reserva=%g, esperado o MAIOR detalhe disponível=%g (por provider: %r). "
        "Soma=%g, primeiro=%g, teto=%d — se a reserva for a soma, é somatório; se "
        "for o primeiro, ignora os demais."
        % (reserva, esperado, referencia, soma, primeiro, teto))


@pytest.mark.parametrize("teto", (320, 480))
@pytest.mark.parametrize("tamanhos", ((1, 8), (2, 12), (4, 20)))
def test_reserva_nao_e_a_soma(bancada, tamanhos, teto):
    """Negativo explícito: a reserva é o maior, não a soma.

    Redundante com o teste anterior por desenho — um negativo que falha sozinho
    diz QUAL erro foi cometido ("somou") sem exigir que o leitor deduza isso de
    uma igualdade quebrada. A condição exige que a diferença entre soma e maior
    seja grande o suficiente para a asserção ter conteúdo.
    """
    caso = "closed-multi-%s-%d" % ("-".join(map(str, tamanhos)), teto)
    reserva = snap_of(bancada, caso, "s").altura_da_area()
    referencia = {n: solo(bancada, n, teto) for n in tamanhos}
    soma, maior = sum(referencia.values()), max(referencia.values())
    base = base_sem_reserva(bancada, teto)
    assert maior > base + 1, (
        "a maior régua vale %g px e a linha de base sem reserva vale %g (por "
        "provider: %r): 'reserva < soma' passaria com zero em toda parte"
        % (maior, base, referencia))
    exigir_reserva_real(bancada, reserva, teto, "relatório %r" % (tamanhos,))
    if soma - maior < 8:
        pytest.skip("caso não discrimina soma de maior (diferença < 8 px)")
    assert reserva < soma - 1, (
        "reserva=%g com soma dos detalhes=%g: a área lateral reservou a SOMA dos "
        "secundários, e não o maior deles (%g)" % (reserva, soma, maior))


@pytest.mark.parametrize("quem", (1, 8))
def test_reserva_independe_do_provider_aberto(bancada, quem):
    """Abrir o MENOR não encolhe a reserva, abrir o MAIOR não a aumenta.

    O relatório é o mesmo (1 e 8 métricas) e o teto é 480, onde "maior detalhe"
    (264 px medidos) e "teto" (480) são distinguíveis. Se a reserva seguisse o
    provider ABERTO, o caso do pequeno daria ~75 e o do grande ~264.
    """
    s_fechado = snap_of(bancada, "aberto-%d-de-1-8-480" % quem, "fechado")
    s_aberto = snap_of(bancada, "aberto-%d-de-1-8-480" % quem, "open")
    h_fechado, h_aberto = s_fechado.altura_da_area(), s_aberto.altura_da_area()
    esperado = max(solo(bancada, 1, 480), solo(bancada, 8, 480))
    assert esperado > base_sem_reserva(bancada, 480) + 1, (
        "a régua desta comparação vale %g px: sem reserva em lugar nenhum a "
        "igualdade com o provider aberto seria 0 == 0" % esperado)
    exigir_reserva_real(bancada, h_aberto, 480, "provider %d aberto" % quem)
    assert abs(h_fechado - h_aberto) <= 1, (
        "abrir o provider de %d métricas mudou a reserva (%g -> %g): a reserva "
        "seguiria o provider aberto" % (quem, h_fechado, h_aberto))
    assert abs(h_aberto - esperado) <= 1, (
        "com o provider de %d métricas aberto a reserva é %g, esperado o maior "
        "detalhe disponível=%g" % (quem, h_aberto, esperado))


@pytest.mark.parametrize("teto", (320, 480))
@pytest.mark.parametrize("n", TAMANHOS)
def test_reserva_igual_nas_duas_laterais(bancada, n, teto):
    """``left`` e ``right`` reservam a MESMA altura.

    A emenda trata as duas como espelhos; uma assimetria de altura faria o popout
    mudar de tamanho ao trocar de lado. Ambas as direções são conferidas antes
    (``conferir_direcao``), para que uma queda de ``right`` para ``down`` não seja
    lida como assimetria.
    """
    esq = snap_of(bancada, "closed-solo-%d-%d-left" % (n, teto), "s")
    dir_ = snap_of(bancada, "closed-solo-%d-%d-right" % (n, teto), "s")
    conferir_direcao(esq, "left")
    conferir_direcao(dir_, "right")
    he, hd = esq.altura_da_area(), dir_.altura_da_area()
    exigir_reserva_real(bancada, he, teto, "lateral esquerda (%d métricas)" % n)
    exigir_reserva_real(bancada, hd, teto, "lateral direita (%d métricas)" % n)
    assert abs(he - hd) <= 1, (
        "a reserva difere entre as laterais: left=%g, right=%g (%d métricas, teto "
        "%d)" % (he, hd, n, teto))


# --------------------------------------------------------------------------- #
# 3. Trocar de provider mantém a altura
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("primeiro,segundo", ((1, 8), (8, 1)))
def test_reserva_troca_mantem_altura(bancada, primeiro, segundo):
    """Com a gaveta ABERTA, clicar outra pílula troca o provider e a altura NÃO muda.

    É o nome deste arquivo. O relatório não muda, logo a reserva não tem motivo
    para mudar: o maior detalhe disponível continua o mesmo (8 métricas, 264 px
    com teto 480). Uma reserva que acompanhasse o provider aberto cairia de ~264
    para ~75 na troca grande->pequeno.

    Âncora: o teste exige que a troca ACONTECEU (``openDrawerId`` mudou de fato) —
    sem isso, "a altura não mudou" seria verdade também para um clique que não
    fez nada.
    """
    caso = "troca-%d-para-%d" % (primeiro, segundo)
    aberta = snap_of(bancada, caso, "open")
    trocada = snap_of(bancada, caso, "trocado")
    id_antes = aberta.prop("openDrawerId")
    id_depois = trocada.prop("openDrawerId")
    assert id_antes == secundario(primeiro)["id"], (
        "a gaveta não abriu em %r: openDrawerId=%r"
        % (secundario(primeiro)["id"], id_antes))
    assert id_depois == secundario(segundo)["id"], (
        "o clique na outra pílula não trocou o provider (openDrawerId=%r, esperado "
        "%r): a âncora falhou antes da altura"
        % (id_depois, secundario(segundo)["id"]))
    assert trocada.has("%s M%d" % (secundario(segundo)["display_name"].split()[-1],
                                   min(8, segundo))), (
        "o detalhe do novo provider não está na árvore: %s" % trocada.texts[:12])
    h_antes, h_depois = aberta.altura_da_area(), trocada.altura_da_area()
    exigir_reserva_real(bancada, h_depois, 480,
                        "depois da troca %d->%d" % (primeiro, segundo))
    assert abs(h_depois - h_antes) <= 1, (
        "trocar do provider de %d para o de %d métricas mudou a altura reservada "
        "(%g -> %g): a altura deve ser independente do provider aberto"
        % (primeiro, segundo, h_antes, h_depois))
    esperado = max(solo(bancada, 1, 480), solo(bancada, 8, 480))
    assert abs(h_depois - esperado) <= 1, (
        "depois da troca a reserva é %g, esperado o maior detalhe do relatório=%g"
        % (h_depois, esperado))


# --------------------------------------------------------------------------- #
# 4. Relatório mudou: a reserva pode acompanhar (e então tem de valer a lei)
# --------------------------------------------------------------------------- #

def test_reserva_poll_cresce(bancada):
    """Um poll que ACRESCENTA um secundário maior eleva a reserva.

    "Pode alterar essa reserva", disse o dono. A parte que se pode exigir é a
    consequência: se a reserva ficasse no valor antigo, o provider novo seria
    aberto num espaço menor que o detalhe dele — o recorte silencioso que a
    emenda existe para evitar.

    Âncora: o poll realmente mudou o relatório (o provider novo virou pílula).
    """
    antes = snap_of(bancada, "poll-cresce", "antes")
    depois = snap_of(bancada, "poll-cresce", "depois")
    assert depois.has("Pill Oct"), (
        "o poll não acrescentou o secundário novo à view: %s" % depois.texts[:12])
    h_antes, h_depois = antes.altura_da_area(), depois.altura_da_area()
    esperado = solo(bancada, 8, 480)
    assert h_antes < esperado - 1, (
        "o estado de controle já reservava %g, e o detalhe que entra exige %g: o "
        "caso não discrimina nada" % (h_antes, esperado))
    assert h_depois >= esperado - 1, (
        "depois do poll a reserva ficou em %g, abaixo do detalhe do novo "
        "secundário (%g): ele abriria recortado" % (h_depois, esperado))
    assert abs(h_depois - esperado) <= 1, (
        "depois do poll a reserva é %g, esperado o maior detalhe disponível=%g"
        % (h_depois, esperado))


def test_reserva_poll_diminui(bancada):
    """Um poll que REMOVE o secundário maior devolve a reserva ao necessário.

    O outro lado da mesma lei: manter a reserva antiga desperdiça altura
    permanentemente, que é o vício que a emenda nomeia ("evitando redimensionar
    durante o uso" — não "reservando o máximo para sempre"). Medido na base
    atual: 264 -> 75.
    """
    antes = snap_of(bancada, "poll-diminui", "antes")
    depois = snap_of(bancada, "poll-diminui", "depois")
    assert antes.has("Pill Oct"), "o estado inicial deveria ter o secundário grande"
    assert not depois.has("Pill Oct"), (
        "o poll não removeu o secundário grande: %s" % depois.texts[:12])
    h_antes, h_depois = antes.altura_da_area(), depois.altura_da_area()
    esperado = solo(bancada, 1, 480)
    assert h_antes > esperado + 1, (
        "o estado de controle não reservava mais que %g: nada a reduzir" % esperado)
    assert abs(h_depois - esperado) <= 1, (
        "depois de o secundário grande sair a reserva é %g, esperado o maior "
        "detalhe restante=%g: altura desperdiçada" % (h_depois, esperado))


def test_reserva_poll_aberto_cresce(bancada):
    """O provider ABERTO ganha métricas no poll: a reserva acompanha.

    Difere do teste anterior: o relatório tem o MESMO número de providers e o
    MESMO id; o que muda é o tamanho do detalhe. É o caso em que uma reserva
    calculada uma vez na abertura falharia sem que nada visível mudasse de lugar.
    """
    antes = snap_of(bancada, "poll-o-aberto-cresce", "open")
    depois = snap_of(bancada, "poll-o-aberto-cresce", "depois")
    assert antes.prop("openDrawerId") == depois.prop("openDrawerId") == "p01", (
        "a gaveta deveria continuar no mesmo provider: %r -> %r"
        % (antes.prop("openDrawerId"), depois.prop("openDrawerId")))
    assert depois.has("Uni M8"), (
        "o detalhe novo não está na árvore depois do poll: %s" % depois.texts[:12])
    h_antes, h_depois = antes.altura_da_area(), depois.altura_da_area()
    esperado = solo(bancada, 8, 480)
    assert h_antes < esperado - 1, "o estado de controle já reservava %g" % h_antes
    assert h_depois >= esperado - 1, (
        "o provider aberto cresceu para %g px de detalhe e a reserva ficou em %g"
        % (esperado, h_depois))


# --------------------------------------------------------------------------- #
# 5. Sem scroll
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("teto", TETOS)
@pytest.mark.parametrize("n", TAMANHOS)
@pytest.mark.parametrize("direcao", ("left", "right"))
def test_ctrl_sem_scroll(bancada, n, teto, direcao):
    """A área lateral não contém NENHUMA superfície rolável — nem fechada, nem
    aberta, nem com detalhe que estoura o teto.

    Scroll foi vetado pelo dono com argumento de produto. A garantia só tem
    conteúdo porque o detector foi provado no controle de vacuidade
    (``test_o_detector_de_scroll_reconhece_um_scroller``).
    """
    for caso, censo in (("closed-solo-%d-%d-%s" % (n, teto, direcao), "s"),
                        ("open-solo-%d-%d-%s" % (n, teto, direcao), "open")):
        rolaveis = snap_of(bancada, caso, censo).rolaveis()
        assert not rolaveis, (
            "há superfície rolável na view (%s): %r — a emenda veta scroll na "
            "gaveta" % (caso, [(r.kind, r.h) for r in rolaveis]))


# --------------------------------------------------------------------------- #
# 6. `down` preservado
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("teto", (160, 480))
def test_ctrl_down_fechado_sem_altura_de_gaveta(bancada, teto):
    """CONTROLE (deve ficar VERDE no revert): em ``down`` fechado não há reserva de
    gaveta, e a altura não segue o tamanho do secundário.

    R4 — esta é a metade que descreve o comportamento PRESERVADO, e ela não
    depende de a emenda existir: mede ``down`` contra a própria linha de base
    (``closed-base-down``, mesmo modelo, mesmo teto) e contra o outro tamanho.
    Era a metade que faltava separar: antes, o teste misturava "``down`` não
    reserva" com "a lateral reserva", e no revert falhava pela segunda metade
    enquanto a primeira estava correta — diagnóstico errado.
    """
    pequeno = snap_of(bancada, "closed-down-1-%d" % teto, "s")
    grande = snap_of(bancada, "closed-down-1-12-%d" % teto, "s")
    conferir_direcao(pequeno, "down")
    conferir_direcao(grande, "down")
    hp, hg = pequeno.altura_da_area(), grande.altura_da_area()
    base = base_sem_reserva(bancada, teto)
    assert hp is not None and hg is not None, "caso sem grade em `down`"
    assert abs(hp - base) <= 1, (
        "em `down` FECHADO a área ocupa %g px e a linha de base sem reserva "
        "ocupa %g: `down` não deveria reservar altura de gaveta fechada"
        % (hp, base))
    assert abs(hg - hp) <= 1, (
        "em `down` FECHADO a altura da área seguiu o tamanho do secundário "
        "(%g com 1 métrica, %g com 12): isso é reserva lateral disfarçada"
        % (hp, hg))


@pytest.mark.parametrize("teto", (160, 480))
def test_reserva_down_nao_herda_a_lateral(bancada, teto):
    """EMENDA: ``down`` fechado não herda a reserva lateral — e o contraste só
    existe se a lateral reservar de verdade.

    R4 — as duas metades têm mensagens distintas e a primeira é a **âncora**
    (R1): se a lateral não reserva, a segunda metade não descreve nada. No revert
    esta falha nomeia "a lateral não reserva", não "``down`` herdou" — que é o
    diagnóstico correto.
    """
    lateral = snap_of(bancada, "closed-solo-12-%d-left" % teto, "s")
    h_lateral = exigir_reserva_real(bancada, lateral.altura_da_area(), teto,
                                    "lateral de referência com 12 métricas")
    hp = snap_of(bancada, "closed-down-1-12-%d" % teto, "s").altura_da_area()
    assert hp is not None, "caso sem grade em `down`"
    assert hp < h_lateral - 40, (
        "em `down` FECHADO a área ocupa %g px e a reserva lateral do mesmo "
        "relatório é %g: `down` herdou a reserva lateral" % (hp, h_lateral))


@pytest.mark.parametrize("teto", (160, 480))
def test_ctrl_down_empurra_ao_abrir(bancada, teto):
    """Em ``down`` a gaveta EMPURRA: a área cresce ao abrir, e não havia reserva
    antes.

    É o "comportamento atual preservado" da emenda. Sem o par (fechado pequeno,
    aberto maior) este teste seria satisfeito por uma view que não abrisse nada.
    A âncora de abertura é o contador/detalhe do provider na árvore.
    """
    fechado = snap_of(bancada, "open-down-1-%d" % teto, "fechado")
    aberto = snap_of(bancada, "open-down-1-%d" % teto, "open")
    conferir_direcao(fechado, "down")
    assert aberto.prop("openDrawerId") == "p01", (
        "a gaveta não abriu em `down`: openDrawerId=%r" % (aberto.prop("openDrawerId"),))
    assert aberto.has("Uni M1"), "o detalhe não está na árvore em `down`"
    h0, h1 = fechado.altura_da_area(), aberto.altura_da_area()
    assert h1 > h0 + 1, (
        "em `down` a gaveta não empurrou o conteúdo (área %g -> %g): o "
        "comportamento preservado é o detalhe abaixo da grade" % (h0, h1))


# --------------------------------------------------------------------------- #
# 7. Relatório truncado: o lado seguro da ambiguidade (i)
# --------------------------------------------------------------------------- #

def test_reserva_truncado(bancada):
    """Com ``maxSecondary: 1`` o secundário grande existe no relatório mas não
    vira pílula. A reserva NÃO pode ser menor que o detalhe do único VISÍVEL.

    Sob as duas leituras possíveis de "disponíveis" (ambiguidade (i) no
    cabeçalho), o valor correto é um de dois: o maior detalhe VISÍVEL ou o maior
    DO RELATÓRIO. R3 afirma essa disjunção em vez de ``≥`` — que, com a régua
    zerada, aceitava zero. A ambiguidade continua não decidida pelo teste.
    """
    s = snap_of(bancada, "truncado-maxsec1", "s")
    assert s.has("Pill Uni"), "o secundário visível não está na grade: %s" % s.texts[:12]
    assert not s.has("Pill Dod"), (
        "maxSecondary=1 não truncou a grade (o secundário grande virou pílula): a "
        "premissa do caso não vale — %s" % s.texts[:12])
    reserva = s.altura_da_area()
    visivel = solo(bancada, 1, 480)
    assert reserva is not None, "caso sem grade"
    exigir_reserva_real(bancada, reserva, 480, "relatório truncado")
    # R3: em vez de "≥" (que aceitava 0 quando a régua também era 0), a reserva
    # tem de ser UMA DAS DUAS respostas coerentes de "disponíveis": o maior
    # VISÍVEL ou o maior DO RELATÓRIO. A disjunção não decide a ambiguidade (i),
    # que o dono não assinou; só recusa um número arbitrário.
    do_relatorio = solo(bancada, 12, 480)
    assert min(abs(reserva - visivel), abs(reserva - do_relatorio)) <= 1, (
        "reserva=%g não é nem o maior detalhe VISÍVEL (%g) nem o maior DO "
        "RELATÓRIO (%g): sob qualquer leitura de 'disponíveis' o valor está errado"
        % (reserva, visivel, do_relatorio))
    assert reserva <= 480 + 1, "reserva acima do teto: %g" % reserva


def test_ctrl_sem_secundarios(bancada):
    """``showSecondaries: false`` não deixa uma área lateral vazia reservada.

    Com a seção ausente não há grade — logo não há reserva a medir, e o popout não
    pode carregar altura de gaveta que não tem o que abrir. O caso serve também de
    controle do medidor: se ele "achasse" reserva sem grade, todos os números
    acima estariam suspeitos.
    """
    s = snap_of(bancada, "sem-secundarios", "s")
    assert s.has("Pill Alpha"), "o primário deveria continuar desenhado: %s" % s.texts[:12]
    assert s.grade() is None, "a grade de secundários existe com showSecondaries=false"
    assert s.altura_da_area() is None, (
        "sem seção de secundários o medidor devolveu altura %r"
        % (s.altura_da_area(),))
    assert s.ih <= 200, (
        "o popout ficou com implicitHeight=%g sem nada a mostrar: altura de gaveta "
        "reservada para uma seção ausente" % s.ih)
