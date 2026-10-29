# -*- coding: utf-8 -*-
"""Testes de comportamento de T28 — modo compacto/expandido por provider.

Gerado em contexto isolado (D5) — sem acesso à implementação.
Base: SPEC rodada 3, tarefa T28.

Contrato exercitado (bloco assinado da tarefa, itens 1–5 + semântica obrigatória)::

    compactByDefault            -> bool (deriva de pluginApi.pluginSettings.density)
    expandedIds                 -> object (set volátil)
    isExpanded(providerId)      -> bool
    toggleExpanded(providerId)  -> void
    leadingMetric(metrics)      -> a métrica de maior percent
    visibleMetrics(provider)    -> array das métricas que devem aparecer
    hiddenMetricCount(provider) -> int (0 esconde o controle)
    anyProviderExpanded         -> bool
    toggleAll()                 -> void

    1. Setting ``density`` (choice): ``expanded`` (default) × ``compact``.
    2. Em compacto, a métrica escolhida é a de MAIOR PERCENT (mesma regra do
       ``headline_metric``) — não a primeira do relatório.
    3. Controle de expandir POR PROVIDER; um expandido não expande os outros.
    4. UM botão no topo alterna tudo (expandir/recolher todos), por CLIQUE real.
    5. Estado de expansão é VOLÁTIL — não persiste.

Como o comportamento é observado sem host visual
------------------------------------------------
``quickshell`` OFFLINE (``QT_QPA_PLATFORM=offscreen``). O harness
``tests/qml/t28_density_harness.qml`` monta a view com um ``pluginApi``
sintético e faz quatro coisas, na ordem:

  a. mede o estado com a setting INICIAL (``expanded``, ``compact`` ou ausente);
  b. troca ``pluginSettings.density`` para ``compact`` e mede de novo, num ciclo
     DEPOIS (medir no mesmo handler lê o binding antigo — medido nesta base);
  c. expande o SEGUNDO provider (não o primeiro: um off-by-one no primeiro
     passaria) e compara os três;
  d. CLICA cada nó clicável, um por um, registrando quantos providers ficaram
     expandidos e QUAIS — o botão do topo é identificado por COMPORTAMENTO
     (aquele que expande todos a partir de vazio), não por nome nem posição.

O critério de done pede "modo compacto reduz a altura". ``implicitHeight`` não
resolve fora do host (medido nesta base), então a redução é provada CONTANDO os
elementos desenhados (textos e retângulos visíveis), que é a causa da altura
menor. Altura em PIXELS NÃO é medida e este arquivo não afirma que é.

Armadilhas desta base, tratadas explicitamente
---------------------------------------------
* ``objectName`` não é usado em NADA: medido que nomear um nó faz o dump do tipo
  carregar ponteiro de memória e quebrar comparações entre execuções. Por isso
  não há seletor por nome; a identificação é por comportamento.
* ``visibleMetrics`` devolve OBJETOS de métrica, não labels: a serialização lê
  ``.label`` e ``.percent`` campo a campo (``[object Object]`` não prova nada).
* Objeto/array de retorno QML pode achatar em ``JSON.stringify``; tudo é
  serializado pelo harness, índice a índice.
* Clique: disparado por ``area.clicked(Qt.point(x, y))``, a forma medida como
  funcional nesta base. Um clique que não encontra alvo é reportado como
  ``VIEW_ERR`` pelo harness, não silenciado.
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

TEST_DIR = Path(__file__).resolve().parent
#: Override por ambiente: uso EXCLUSIVO da verificação de falsificabilidade.
PLUGIN_DIR = Path(os.environ.get("T28_PLUGIN_DIR", TEST_DIR.parent))
HARNESS = TEST_DIR / "qml" / "t28_density_harness.qml"

_QUICK = shutil.which("quickshell") or shutil.which("qs")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

pytestmark = pytest.mark.skipif(
    _QUICK is None,
    reason="quickshell ausente: a view QML e as funções puras não podem ser exercitadas",
)

# --------------------------------------------------------------------------- #
# Fixture: TRÊS providers, e cada um arma uma armadilha diferente
# --------------------------------------------------------------------------- #
#
#  anthropic  3 métricas: 55, 90, 20. A líder (Weekly, 90%) NÃO é a primeira —
#             é o caso que o contrato nomeia ("não a primeira do relatório").
#  copilot    2 métricas: 12, 40. A líder (Chat, 40%) também não é a primeira:
#             um segundo caso, para o erro não passar por coincidência.
#  zai        status=error, SEM métricas. Provider em erro não tem o que mostrar,
#             e não pode virar o "oráculo do branco" (leadingMetric indefinido).
#
# O modelo tem primary + secondary + all coerentes, como o coletor entrega.

def _metric(label: str, percent, reset_at, window_secs: int = 18000,
            severity: str = "low") -> dict:
    return {
        "label": label,
        "percent": percent,
        "value": "%s%%" % percent,
        "severity": severity,
        "detail": "",
        "reset_at": reset_at,
        "window_secs": window_secs,
    }


ANTHROPIC = {
    "id": "anthropic", "display_name": "Claude", "status": "ready",
    "metrics": [
        _metric("Session (5h)", 55, "2026-11-04T22:00:00Z"),
        _metric("Weekly (7d)", 90, "2026-11-04T12:00:00Z", 604800, "critical"),
        _metric("Extra usage", 20, "2026-11-01T12:00:00Z", 86400),
    ],
}
COPILOT = {
    "id": "copilot", "display_name": "GitHub Copilot", "status": "ready",
    "metrics": [
        _metric("Premium requests", 12, "2026-12-01T00:00:00Z", 2592000),
        _metric("Chat", 40, "2026-12-01T00:00:00Z", 2592000),
    ],
}
ZAI = {"id": "zai", "display_name": "Z.AI", "status": "error", "metrics": []}

MODEL = {
    "schema": 1,
    "primary": ANTHROPIC,
    "secondary": [COPILOT, ZAI],
    "all": [ANTHROPIC, COPILOT, ZAI],
    "total_providers": 3,
    "with_issues": 1,
}

PROVIDERS = MODEL["all"]
IDS = [p["id"] for p in PROVIDERS]
LABELS = {p["id"]: [m["label"] for m in p["metrics"]] for p in PROVIDERS}
LEADER = {p["id"]: max(p["metrics"], key=lambda m: m["percent"])["label"]
          for p in PROVIDERS if p["metrics"]}

#: O provider usado na isolação. É o SEGUNDO, de propósito: expandir o primeiro
#: esconderia um off-by-one que sempre pegasse o índice 0.
ALVO = IDS[1]
OUTRO = IDS[0]


def _m(label: str, percent) -> dict:
    """Métrica mínima para os casos unitários de ``leadingMetric``."""
    return {"label": label, "percent": percent, "value": "", "severity": "low",
            "detail": "", "reset_at": None, "window_secs": 18000}


#: Casos unitários: {"name", "fn", "args"}. Os args vão direto ao QML.
#: Dicts, não tuplas: uma tupla vira ARRAY no JSON e o harness lê `cs.fn` como
#: undefined (medido — todos os casos falhavam como "função ausente").
UNIT_CASES = [
    # maior percent, não a primeira
    {"name": "lider-nao-e-a-primeira", "fn": "leadingMetric", "args": [[_m("A", 10), _m("B", 90), _m("C", 50)]]},
    {"name": "lider-no-meio", "fn": "leadingMetric", "args": [[_m("A", 10), _m("B", 90), _m("C", 50)]]},
    {"name": "lider-no-fim", "fn": "leadingMetric", "args": [[_m("A", 10), _m("B", 20), _m("C", 90)]]},
    # empate -> a PRIMEIRA na ordem
    {"name": "empate-duas", "fn": "leadingMetric", "args": [[_m("A", 50), _m("B", 50)]]},
    {"name": "empate-tres", "fn": "leadingMetric", "args": [[_m("A", 70), _m("B", 70), _m("C", 70)]]},
    {"name": "empate-com-terceira-baixa", "fn": "leadingMetric", "args": [[_m("A", 30), _m("B", 80), _m("C", 80)]]},
    # percent nulo nunca é líder
    {"name": "nulo-nao-e-lider", "fn": "leadingMetric", "args": [[_m("A", None), _m("B", 40)]]},
    {"name": "nulo-vs-zero", "fn": "leadingMetric", "args": [[_m("A", None), _m("B", 0)]]},
    {"name": "nulo-antes-do-lider", "fn": "leadingMetric", "args": [[_m("A", None), _m("B", 5), _m("C", 3)]]},
    {"name": "nulo-no-fim", "fn": "leadingMetric", "args": [[_m("A", 30), _m("B", None)]]},
    # nenhuma tem percent -> a primeira (provider nunca em branco)
    {"name": "todas-nulas", "fn": "leadingMetric", "args": [[_m("A", None), _m("B", None)]]},
    {"name": "uma-so", "fn": "leadingMetric", "args": [[_m("A", 7)]]},
    {"name": "uma-so-nula", "fn": "leadingMetric", "args": [[_m("A", None)]]},
    # bordas
    {"name": "cem", "fn": "leadingMetric", "args": [[_m("A", 100), _m("B", 99)]]},
    {"name": "acima-de-cem", "fn": "leadingMetric", "args": [[_m("A", 150), _m("B", 100)]]},
    {"name": "negativo-nao-vence", "fn": "leadingMetric", "args": [[_m("A", -5), _m("B", None)]]},
    # nenhuma métrica
    {"name": "vazio", "fn": "leadingMetric", "args": [[]]},
]

#: Providers sintéticos para as funções que recebem o provider inteiro.
PROV_A = {"id": "pa", "display_name": "PA", "status": "ready",
          "metrics": [_m("X", 80), _m("Y", 20)]}
PROV_B = {"id": "pb", "display_name": "PB", "status": "ready",
          "metrics": [_m("Z", 10)]}
PROV_VAZIO = {"id": "pv", "display_name": "PV", "status": "error", "metrics": []}

UNIT_CASES += [
    {"name": "vis-prov-a", "fn": "visibleMetrics", "args": [PROV_A]},
    {"name": "vis-prov-b", "fn": "visibleMetrics", "args": [PROV_B]},
    {"name": "vis-vazio", "fn": "visibleMetrics", "args": [PROV_VAZIO]},
    {"name": "hid-prov-a", "fn": "hiddenMetricCount", "args": [PROV_A]},
    {"name": "hid-prov-b", "fn": "hiddenMetricCount", "args": [PROV_B]},
    {"name": "hid-vazio", "fn": "hiddenMetricCount", "args": [PROV_VAZIO]},
]


# --------------------------------------------------------------------------- #
# Transporte
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


def _rodar(densidade_inicial: str = "expanded", timeout: int = 240) -> list[str]:
    assert HARNESS.is_file(), "harness QML ausente: %s" % HARNESS
    assert (PLUGIN_DIR / "content" / "Widget.qml").is_file(), "content/Widget.qml ausente"
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("WAYLAND_DISPLAY", None)
    env["T28_PLUG_DIR"] = str(PLUGIN_DIR)
    env["T28_STATE_DIR"] = "/tmp/t28-suite-state"
    env["T28_MODEL"] = json.dumps(MODEL, ensure_ascii=False)
    env["T28_CASES"] = json.dumps(UNIT_CASES, ensure_ascii=False)
    env["T28_INITIAL_DENSITY"] = densidade_inicial
    env["T28_SETTLE_MS"] = "1400"
    try:
        proc = subprocess.run([_QUICK, "-p", str(HARNESS)], capture_output=True,
                              text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        pytest.fail(
            "o harness do modo compacto não terminou em %ss — provável laço em "
            "toggleAll/toggleExpanded ou view que não monta." % timeout
        )
    regs = _limpo(proc.stdout + proc.stderr)
    assert any(r.startswith("END|") for r in regs), (
        "o harness não chegou ao fim; rc=%s\nregistros=%s\nstderr(tail)=%s"
        % (proc.returncode, regs, proc.stderr[-1500:])
    )
    return regs


def _json(txt: str, onde: str):
    try:
        return json.loads(txt)
    except json.JSONDecodeError as e:
        raise AssertionError("%s: dump não é JSON: %r (%s)" % (onde, txt, e))


class Fase:
    """O estado observado numa fase (expanded / compact / compact+1expandido)."""

    def __init__(self, nome: str):
        self.nome = nome
        self.compact_default = None
        self.any_expanded = None
        self.expanded_ids: list[str] = []
        self.providers: list[dict] = []
        self.census: dict[str, int] = {}
        self.units: dict[str, tuple[str, object]] = {}
        self.unit_throws: dict[str, str] = {}

    @property
    def textos(self) -> int:
        return self.census.get("texts", -1)

    @property
    def retangulos(self) -> int:
        return self.census.get("rects", -1)

    @property
    def metricas_desenhadas(self) -> int:
        """Rótulos de métrica desenhados (censo ancorado em CONTEÚDO)."""
        return self.census.get("metrics", -1)

    def prov(self, pid: str) -> dict:
        for p in self.providers:
            if p.get("id") == pid:
                return p
        raise AssertionError(
            "[%s] provider %r não apareceu no dump; providers=%r"
            % (self.nome, pid, self.providers)
        )

    def visiveis(self, pid: str) -> list[str]:
        p = self.prov("prov") if False else self.prov(pid)
        v = p.get("visible")
        assert isinstance(v, dict) and "$len" in v, (
            "[%s/%s] visibleMetrics não devolveu array: %r" % (self.nome, pid, v)
        )
        assert "$notArray" not in v, (
            "[%s/%s] visibleMetrics não é array: %r" % (self.nome, pid, v)
        )
        labels = []
        for item in v["items"]:
            assert isinstance(item, dict), (
                "[%s/%s] item de visibleMetrics não é objeto: %r"
                % (self.nome, pid, item)
            )
            labels.append(item.get("label"))
        return labels

    def ocultas(self, pid: str) -> int:
        h = self.prov(pid).get("hidden")
        assert isinstance(h, int), (
            "[%s/%s] hiddenMetricCount não é inteiro: %r" % (self.nome, pid, h)
        )
        return h

    def unit(self, caso: str):
        assert caso not in self.unit_throws, (
            "[%s/%s] a função lançou: %r" % (self.nome, caso, self.unit_throws[caso])
        )
        assert caso in self.units, (
            "[%s/%s] caso unitário não executado. unidades=%r"
            % (self.nome, caso, sorted(self.units))
        )
        return self.units[caso][1]

    def lider(self, caso: str) -> dict:
        d = self.unit(caso)
        assert isinstance(d, dict), (
            "[%s/%s] leadingMetric deveria devolver uma métrica; veio %r"
            % (self.nome, caso, d)
        )
        assert d.get("$null") is not True, (
            "[%s/%s] leadingMetric devolveu null (provider ficaria em branco)"
            % (self.nome, caso)
        )
        return d

    def __repr__(self) -> str:
        return "<Fase %s texts=%s rects=%s ids=%r>" % (
            self.nome, self.textos, self.retangulos, self.expanded_ids)


class Bancada:
    def __init__(self, registros: list[str]):
        self.registros = registros
        self.fases: dict[str, Fase] = {}
        self.roles: dict[str, str] = {}
        self.hosts: dict[str, str] = {}
        self.candidatos: dict[str, dict[str, bool]] = {}
        self.cliques: list[dict] = []
        self.click_cands: list[dict] = []
        self.toggle_all: dict[int, dict] = {}
        self.click_toggle: list[tuple] = []
        self.top_button = None
        self.save_keys: list[str] = []
        self.save_keys_before_remount = None
        self.remount_ids = None
        self.remount_count = None
        self.erros: list[str] = []
        fase_atual: Fase | None = None

        for r in registros:
            if r.startswith("===PHASE|"):
                nome = r.split("|", 1)[1].rstrip("=")
                fase_atual = Fase(nome)
                self.fases[nome] = fase_atual
            elif r.startswith("FN_ROLE|"):
                _t, role, nome, estado = r.split("|", 3)
                self.roles[role] = nome if estado == "present" else ""
            elif r.startswith("FN_HOST|"):
                _t, role, kind, _nome = r.split("|", 3)
                self.hosts[role] = kind
            elif r.startswith("FN_PROBE|"):
                _t, role, cand, presente = r.split("|", 3)
                self.candidatos.setdefault(role, {})[cand] = presente == "true"
            elif r.startswith("P_COMPACT_DEFAULT|"):
                if fase_atual:
                    fase_atual.compact_default = _json(r.split("|", 1)[1], "P_COMPACT_DEFAULT")
            elif r.startswith("P_ANY_EXPANDED|"):
                if fase_atual:
                    fase_atual.any_expanded = _json(r.split("|", 1)[1], "P_ANY_EXPANDED")
            elif r.startswith("EXPANDED_IDS|"):
                if fase_atual:
                    fase_atual.expanded_ids = _json(r.split("|", 1)[1], "EXPANDED_IDS")
            elif r.startswith("PROV|"):
                if fase_atual:
                    fase_atual.providers.append(_json(r.split("|", 1)[1], "PROV"))
            elif r.startswith("CENSUS|"):
                partes = r.split("|")
                acc = {}
                for i in range(1, len(partes) - 1, 2):
                    try:
                        acc[partes[i]] = int(partes[i + 1])
                    except ValueError:
                        pass
                if fase_atual:
                    fase_atual.census = acc
            elif r.startswith("UC_THROW|"):
                _t, fase, caso, msg = r.split("|", 3)
                if fase in self.fases:
                    self.fases[fase].unit_throws[caso] = msg
            elif r.startswith("UC|"):
                _t, fase, caso, tipo, bruto = r.split("|", 4)
                if fase in self.fases:
                    self.fases[fase].units[caso] = (tipo, _json(bruto, caso))
            elif r.startswith("CLICK_CAND|"):
                _t, i, kind, dim, vis, clickable = r.split("|", 5)
                self.click_cands.append({"i": int(i), "kind": kind, "dim": dim,
                                         "visible": vis, "clickable": clickable})
            elif r.startswith("CLICK|"):
                _t, i, kind, dim, antes, depois, allx, mudou, chaves = r.split("|", 8)
                self.cliques.append({
                    "i": int(i), "kind": kind, "dim": dim,
                    "antes": int(antes), "depois": int(depois),
                    "all": allx == "true", "mudou": mudou == "true",
                    "keys": _json(chaves, "CLICK keys"),
                })
            elif r.startswith("TOGGLE_ALL|"):
                _t, step, quando, n, chaves = r.split("|", 4)
                self.toggle_all.setdefault(int(step), {})[quando] = (
                    int(n), _json(chaves, "TOGGLE_ALL"))
            elif r.startswith("TOP_BUTTON|"):
                self.top_button = int(r.split("|", 1)[1])
            elif r.startswith("CLICK_TOGGLE|"):
                _t, antes, ka, depois, kd = r.split("|", 4)
                self.click_toggle.append((int(antes), _json(ka, "k1"),
                                          int(depois), _json(kd, "k2")))
            elif r.startswith("SAVE_KEYS_BEFORE_REMOUNT|"):
                self.save_keys_before_remount = _json(r.split("|", 1)[1], "SAVE_KEYS_BEFORE")
            elif r.startswith("REMOUNT_EXPANDED_IDS|"):
                self.remount_ids = _json(r.split("|", 1)[1], "REMOUNT_IDS")
            elif r.startswith("REMOUNT_COUNT|"):
                self.remount_count = int(r.split("|", 1)[1])
            elif r.startswith("SAVE_KEYS|"):
                self.save_keys = _json(r.split("|", 1)[1], "SAVE_KEYS")
            elif r.startswith("VIEW_ERR|"):
                self.erros.append(r)
        self.view_present = any(r == "VIEW_PRESENT|true" for r in registros)

    def fase(self, prefixo: str) -> Fase:
        for nome, f in self.fases.items():
            if nome.startswith(prefixo):
                return f
        raise AssertionError(
            "fase %r não foi medida; fases=%r · registros=%s"
            % (prefixo, list(self.fases), self.registros[:20])
        )


@pytest.fixture(scope="module")
def bancada() -> Bancada:
    return Bancada(_rodar("expanded"))


@pytest.fixture(scope="module")
def bancada_default(bancada) -> Bancada:
    """A mesma execução, com a setting ``density`` AUSENTE do store."""
    return Bancada(_rodar("absent"))


# --------------------------------------------------------------------------- #
# Âncora
# --------------------------------------------------------------------------- #


def test_artefatos_sob_teste_existem():
    assert HARNESS.is_file(), "harness QML ausente: %s" % HARNESS
    assert (PLUGIN_DIR / "content" / "Widget.qml").is_file(), "content/Widget.qml ausente"


def test_as_funcoes_puras_e_as_duas_propriedades_existem(bancada):
    assert bancada.view_present, (
        "a view não montou; erros=%s; nada a exercitar" % bancada.erros
    )
    faltando = [r for r in ("leadingMetric", "visibleMetrics", "hiddenMetricCount",
                            "isExpanded", "toggleExpanded", "toggleAll")
                if not bancada.roles.get(r)]
    assert not faltando, (
        "função pública ausente para o(s) papel(is) %s. O contrato exige "
        "isExpanded, toggleExpanded, leadingMetric, visibleMetrics, "
        "hiddenMetricCount e toggleAll na view montada. Sondagem=%s · hosts=%s"
        % (faltando, bancada.candidatos, bancada.hosts)
    )
    exp = bancada.fase("inicial")
    assert isinstance(exp.compact_default, bool), (
        "compactByDefault deveria ser bool; veio %r" % (exp.compact_default,)
    )
    assert isinstance(exp.any_expanded, bool), (
        "anyProviderExpanded deveria ser bool; veio %r" % (exp.any_expanded,)
    )


# --------------------------------------------------------------------------- #
# Item 1 — a setting `density` e o seu default
# --------------------------------------------------------------------------- #


def test_density_expanded_e_o_padrao(bancada):
    """``expanded`` é o default declarado; a view começa exatamente nele."""
    f = bancada.fase("inicial")
    assert f.compact_default is False, (
        "com density='expanded' (o default do contrato), compactByDefault deveria "
        "ser false; veio %r" % (f.compact_default,)
    )


def test_density_ausente_cai_no_default_expanded(bancada_default):
    """Store sem a chave ``density``: o default é ``expanded``, não compacto.

    Este é o caso de uma instalação existente, cujo ``plugins.json`` foi escrito
    antes da setting existir. Um ``compactByDefault`` que só olhasse o valor
    literal cairia em ``undefined`` e poderia recolher o popout de todo mundo.
    """
    f = bancada_default.fase("inicial")
    assert f.compact_default is False, (
        "com a chave 'density' AUSENTE do pluginSettings, compactByDefault "
        "deveria cair no default 'expanded' (false); veio %r" % (f.compact_default,)
    )
    assert [f.visiveis(pid) for pid in IDS if LABELS[pid]] == \
           [LABELS[pid] for pid in IDS if LABELS[pid]], (
        "sem a setting, todas as métricas de cada provider deveriam estar "
        "visíveis; veio %r"
        % ([(pid, f.visiveis(pid)) for pid in IDS],)
    )


def test_density_compact_encurta_o_que_e_desenhado(bancada):
    """Critério de done: "o modo compacto reduz a altura/elementos medidos".

    Duas medidas, ambas com redução ESTRITA:

    * ``visibleMetrics`` somado por provider — a contagem que o contrato define;
    * rótulos de métrica REALMENTE desenhados, contados no censo por CONTEÚDO
      (o texto é um label do fixture, sem caixa), não por total de nós.

    A segunda é a que substitui a altura: ``implicitHeight`` não resolve fora do
    host (medido nesta base). Contar TODOS os textos seria frágil — o chrome
    "+N more" e o rótulo do botão entram justamente onde saem métricas, e um
    provider de 2 métricas pode dar 2 textos em ambos os modos (medido numa
    árvore de controle: 8 vs 8). Ancorar no CONTEÚDO do rótulo elimina esse
    ruído, e é a quantidade que o objetivo descreve ("só a métrica mais
    crítica").
    """
    exp = bancada.fase("inicial")
    cmp_ = bancada.fase("compact")
    assert exp.compact_default is False and cmp_.compact_default is True, (
        "o harness deveria medir expanded e depois compact; flags=%r/%r"
        % (exp.compact_default, cmp_.compact_default)
    )
    soma_exp = sum(len(exp.visiveis(pid)) for pid in IDS)
    soma_cmp = sum(len(cmp_.visiveis(pid)) for pid in IDS)
    assert soma_cmp < soma_exp, (
        "compacto deveria expor MENOS métricas no total; expandido=%s, compacto=%s"
        % (soma_exp, soma_cmp)
    )
    assert cmp_.metricas_desenhadas < exp.metricas_desenhadas, (
        "compacto deveria DESENHAR menos rótulos de métrica; expandido=%s, "
        "compacto=%s (censo=%r / %r). É esta redução que produz a altura menor "
        "que o critério de done pede — e a altura em pixels não é medida aqui "
        "porque implicitHeight não resolve fora do host."
        % (exp.metricas_desenhadas, cmp_.metricas_desenhadas, exp.census, cmp_.census)
    )
    # Diagnóstico, não asserção: o total bruto de nós pode não cair, e é legítimo.
    assert exp.textos > 0 and cmp_.textos > 0, (
        "censo vazio: a árvore não foi percorrida (exp=%r cmp=%r)"
        % (exp.census, cmp_.census)
    )


# --------------------------------------------------------------------------- #
# Item 2 — `expanded` mostra tudo; `compact` mostra só a líder
# --------------------------------------------------------------------------- #


def test_expanded_mostra_todas_as_metricas(bancada):
    f = bancada.fase("inicial")
    for pid in IDS:
        esperado = LABELS[pid]
        assert f.visiveis(pid) == esperado, (
            "[%s] em modo expanded, visibleMetrics deveria devolver TODAS as "
            "métricas na ordem do relatório: %r; veio %r"
            % (pid, esperado, f.visiveis(pid))
        )


def test_compact_mostra_so_a_metrica_de_maior_percent(bancada):
    """O coração do item 2: a líder, não a primeira.

    Em ambos os providers com métricas, a líder declarada no fixture NÃO é a
    primeira — então "devolveu a primeira" e "devolveu a líder" dão respostas
    diferentes, e a asserção distingue as duas.
    """
    f = bancada.fase("compact")
    for pid in (ALVO, OUTRO):
        esperado = LEADER[pid]
        primeira = LABELS[pid][0]
        assert primeira != esperado, (
            "fixture inválido: em %r a líder seria a primeira e este teste não "
            "distinguiria 'maior percent' de 'primeira do relatório'" % (pid,)
        )
        obtido = f.visiveis(pid)
        assert obtido == [esperado], (
            "[%s] em compacto a única métrica visível deve ser a de MAIOR "
            "percent (%r); veio %r. Se vier %r, a view está usando a PRIMEIRA do "
            "relatório — exatamente o que o item 2 proíbe."
            % (pid, esperado, obtido, [primeira])
        )


def test_compact_nao_esvazia_um_provider_com_metricas(bancada):
    """Negativo: compacto é "só a líder", nunca "nenhuma"."""
    f = bancada.fase("compact")
    for pid in IDS:
        if not LABELS[pid]:
            continue
        assert len(f.visiveis(pid)) >= 1, (
            "[%s] em compacto o provider ficou em branco; o contrato diz 'só a "
            "métrica mais crítica', não 'nenhuma'" % (pid,)
        )


def test_provider_em_erro_continua_sem_metrica(bancada):
    """O provider sem métricas não inventa uma — e não quebra o compacto."""
    for prefixo in ("inicial", "compact"):
        f = bancada.fase(prefixo)
        assert f.visiveis("zai") == [], (
            "[%s/zai] um provider em erro sem métricas continua sem métrica; veio %r"
            % (prefixo, f.visiveis("zai"))
        )


# --------------------------------------------------------------------------- #
# leadingMetric — a regra, isolada
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("caso,esperado", [
    ("lider-nao-e-a-primeira", "B"),
    ("lider-no-fim", "C"),
    ("empate-duas", "A"),
    ("empate-tres", "A"),
    ("empate-com-terceira-baixa", "B"),
    ("nulo-nao-e-lider", "B"),
    ("nulo-vs-zero", "B"),
    ("nulo-antes-do-lider", "B"),
    ("nulo-no-fim", "A"),
    ("todas-nulas", "A"),
    ("uma-so", "A"),
    ("uma-so-nula", "A"),
    ("cem", "A"),
    ("acima-de-cem", "A"),
    ("negativo-nao-vence", "A"),
])
def test_leading_metric_escolhe_o_maior_percent_com_desempate_na_ordem(
        bancada, caso, esperado):
    """A regra inteira em uma tabela: maior percent; empate → a primeira.

    Os casos de ``percent: null`` são os que separam "não tem magnitude" de
    "vale zero": em ``nulo-vs-zero`` a resposta precisa ser a de 0%, não a nula.
    """
    f = bancada.fase("inicial")
    obtido = f.lider(caso)
    assert obtido.get("label") == esperado, (
        "[%s] leadingMetric deveria escolher %r; escolheu %r (dump=%r). Regra: "
        "maior percent; empate → a PRIMEIRA na ordem; percent nulo NUNCA é líder."
        % (caso, esperado, obtido.get("label"), obtido)
    )


def test_leading_metric_com_lista_vazia_nao_quebra(bancada):
    """Sem métricas não há líder; o que não pode é lançar.

    O construtor do dump marca ``null`` como ``{"$null": true}`` — o valor
    devolvido é observado, não presumido.
    """
    f = bancada.fase("inicial")
    d = f.unit("vazio")
    assert d is None or d == {"$null": True} or d == {}, (
        "leadingMetric([]) deveria devolver vazio/nulo; veio %r" % (d,)
    )


def test_leading_metric_do_provider_real_e_a_da_interface(bancada):
    """``visibleMetrics`` em compacto concorda com ``leadingMetric`` no provider.

    Duas funções públicas que dizem a mesma coisa não podem divergir: se
    ``leadingMetric`` escolhesse uma métrica e ``visibleMetrics`` outra, o
    cabeçalho do provider contradiria a própria barra.
    """
    f = bancada.fase("compact")
    for pid in (ALVO, OUTRO):
        p = f.prov(pid)
        assert p.get("leading") == f.visiveis(pid)[0], (
            "[%s] leadingMetric do provider (%r) diverge de visibleMetrics em "
            "compacto (%r)" % (pid, p.get("leading"), f.visiveis(pid))
        )


# --------------------------------------------------------------------------- #
# Item 3 — controle POR PROVIDER, isolação
# --------------------------------------------------------------------------- #


def test_expandir_um_provider_nao_expande_os_outros(bancada):
    """O critério de done: "expandir um provider não afeta os outros".

    Comparação antes/depois por provider: o alvo cresce, os vizinhos ficam
    idênticos. O alvo é o SEGUNDO provider, para que um `ids[0]` fixo falhe.
    """
    antes = bancada.fase("compact")
    depois = bancada.fase("compact+1expandido")
    assert depois.expanded_ids == [ALVO], (
        "depois de expandir %r, o set de expansão deveria conter só ele; veio %r. "
        "O controle é por provider, não global." % (ALVO, depois.expanded_ids)
    )
    assert antes.visiveis(ALVO) != depois.visiveis(ALVO), (
        "[%s] expandir não mudou o que ele mostra: %r em ambos os estados"
        % (ALVO, antes.visiveis(ALVO))
    )
    assert depois.visiveis(ALVO) == LABELS[ALVO], (
        "[%s] um provider expandido mostra as DEMAIS métricas; esperado %r, veio %r"
        % (ALVO, LABELS[ALVO], depois.visiveis(ALVO))
    )
    for outro in IDS:
        if outro == ALVO:
            continue
        assert antes.visiveis(outro) == depois.visiveis(outro), (
            "[%s] mudou ao expandir %r: %r → %r. Expandir um provider NÃO pode "
            "afetar os outros (item 3)."
            % (outro, ALVO, antes.visiveis(outro), depois.visiveis(outro))
        )
        assert antes.ocultas(outro) == depois.ocultas(outro), (
            "[%s] hiddenMetricCount mudou ao expandir %r: %s → %s"
            % (outro, ALVO, antes.ocultas(outro), depois.ocultas(outro))
        )


def test_a_isencao_e_simetrica_no_outro_provider(bancada):
    """O mesmo, olhando o provider que NÃO foi tocado ficar expandido."""
    antes = bancada.fase("compact")
    depois = bancada.fase("compact+1expandido")
    assert antes.prov(OUTRO)["expanded"] is False, (
        "[%s] começou expandido sem ninguém tocar nele" % (OUTRO,)
    )
    assert depois.prov(OUTRO)["expanded"] is False, (
        "[%s] passou a expandido quando o alvo foi %r" % (OUTRO, ALVO)
    )


def test_any_provider_expanded_reflete_o_estado(bancada):
    """A propriedade que decide o rótulo do botão acompanha os dois lados."""
    assert bancada.fase("compact").any_expanded is False, (
        "sem nenhum provider expandido, anyProviderExpanded deveria ser false; "
        "veio %r" % (bancada.fase("compact").any_expanded,)
    )
    assert bancada.fase("compact+1expandido").any_expanded is True, (
        "com %r expandido, anyProviderExpanded deveria ser true; veio %r"
        % (ALVO, bancada.fase("compact+1expandido").any_expanded)
    )


def test_hidden_metric_count_e_zero_em_expanded(bancada):
    """``hiddenMetricCount`` = 0 em modo expanded: não há controle para mostrar."""
    f = bancada.fase("inicial")
    for pid in IDS:
        assert f.ocultas(pid) == 0, (
            "[%s] em modo expanded hiddenMetricCount deveria ser 0; veio %s"
            % (pid, f.ocultas(pid))
        )


def test_hidden_metric_count_conta_so_o_que_esta_oculto(bancada):
    """Em compacto, é (total - 1) — e não o total nem zero."""
    f = bancada.fase("compact")
    for pid in (ALVO, OUTRO):
        esperado = len(LABELS[pid]) - 1
        assert f.ocultas(pid) == esperado, (
            "[%s] em compacto, %s métricas → %s ocultas; veio %s"
            % (pid, len(LABELS[pid]), esperado, f.ocultas(pid))
        )


def test_hidden_metric_count_e_zero_quando_o_provider_esta_expandido(bancada):
    """O item explícito da semântica: expandido → 0, mesmo em modo compacto."""
    f = bancada.fase("compact+1expandido")
    assert f.prov(ALVO)["expanded"] is True, (
        "[%s] deveria estar expandido nesta fase; dump=%r" % (ALVO, f.prov(ALVO))
    )
    assert f.ocultas(ALVO) == 0, (
        "[%s] está expandido, então nada está oculto: hiddenMetricCount deveria "
        "ser 0; veio %s. É isso que esconde o controle de expandir."
        % (ALVO, f.ocultas(ALVO))
    )


def test_provider_sem_metricas_ocultas_nao_tem_controle(bancada):
    """Um provider sem métricas não ganha um controle inerte."""
    for prefixo in ("inicial", "compact", "compact+1expandido"):
        f = bancada.fase(prefixo)
        assert f.ocultas("zai") == 0, (
            "[%s/zai] sem métricas, hiddenMetricCount deveria ser 0; veio %s"
            % (prefixo, f.ocultas("zai"))
        )


# --------------------------------------------------------------------------- #
# Item 4 — o botão do topo, por CLIQUE
# --------------------------------------------------------------------------- #


def test_existe_um_clicavel_que_expande_todos(bancada):
    """"Um botão no topo alterna tudo": tem de existir e ser um alvo real.

    A identificação é por comportamento — dos nós clicáveis, o que leva de 0 a
    TODOS os providers expandidos. Nada de seletor por ``objectName`` (medido:
    nomear um nó injeta ponteiro de memória no dump e quebra comparações).
    """
    assert bancada.top_button is not None and bancada.top_button >= 0, (
        "nenhum nó clicável levou de 'nada expandido' a 'todos expandidos'. "
        "Clicáveis vistos=%r · cliques=%r. O critério de done pede o botão do "
        "topo funcionando com clique real."
        % (bancada.click_cands, bancada.cliques)
    )
    alvo = bancada.cliques[bancada.top_button] if bancada.top_button < len(bancada.cliques) else None
    assert alvo is not None and alvo["all"], (
        "o clique %s (%r) não expandiu todos; cliques=%r"
        % (bancada.top_button, alvo, bancada.cliques)
    )


def test_o_clique_do_botao_do_topo_expande_todos_os_providers(bancada):
    """E expande TODOS os de ``model.all`` — o contrato é explícito."""
    cliques_all = [c for c in bancada.cliques if c["all"]]
    assert cliques_all, (
        "nenhum clique expandiu todos os providers; cliques=%r" % (bancada.cliques,)
    )
    for c in cliques_all:
        assert sorted(c["keys"]) == sorted(IDS), (
            "o botão do topo deveria expandir %r; expandiu %r"
            % (sorted(IDS), sorted(c["keys"]))
        )
        assert c["antes"] == 0, (
            "o harness clica esse alvo a partir de um set vazio; veio antes=%s"
            % (c["antes"],)
        )


def test_o_mesmo_botao_recolhe_tudo_no_clique_seguinte(bancada):
    """"UM botão ... (expandir/recolher todos)": o segundo clique desfaz."""
    assert bancada.click_toggle, (
        "o clique de alternância não foi medido; registros=%r" % (bancada.registros[-15:],)
    )
    antes, ka, depois, kd = bancada.click_toggle[0]
    assert antes == len(IDS) and depois == 0, (
        "clicar o botão com tudo expandido deveria recolher tudo; foi de %s (%r) "
        "para %s (%r). O contrato diz UM botão que expande E recolhe."
        % (antes, ka, depois, kd)
    )
    assert kd == [], "depois de recolher, o set de expansão deveria estar vazio: %r" % (kd,)
    antes2, ka2, depois2, kd2 = bancada.click_toggle[1]
    assert antes2 == 0 and depois2 == len(IDS), (
        "o terceiro clique (a partir de vazio) deveria expandir tudo de novo; foi "
        "de %s (%r) para %s (%r)" % (antes2, ka2, depois2, kd2)
    )


def test_toggle_all_alterna_a_partir_de_estado_vazio(bancada):
    """``toggleAll``: ``{}`` → todos → ``{}``, verificado pelo PRÓPRIO set."""
    assert 1 in bancada.toggle_all and 2 in bancada.toggle_all, (
        "o harness deveria exercitar toggleAll duas vezes; medido=%r"
        % (bancada.toggle_all,)
    )
    n0, k0 = bancada.toggle_all[1]["before"]
    n1, k1 = bancada.toggle_all[1]["after"]
    assert (n0, k0) == (0, []), "o passo 1 deveria partir de vazio; veio %r/%r" % (n0, k0)
    assert sorted(k1) == sorted(IDS), (
        "toggleAll de vazio deveria expandir todos os providers de model.all "
        "(%r); veio %r" % (sorted(IDS), k1)
    )
    n2, k2 = bancada.toggle_all[2]["after"]
    assert (n2, k2) == (0, []), (
        "chamar toggleAll de novo deveria VOLTAR a {} (recolher todos); veio %r/%r"
        % (n2, k2)
    )


def test_toggle_all_nao_alcanca_provider_fora_de_model_all(bancada):
    """``model.all`` é a lista; nada de inventar ids de outra fonte."""
    for passo in (1, 2):
        for quando in ("before", "after"):
            n, chaves = bancada.toggle_all[passo][quando]
            for k in chaves:
                assert k in IDS, (
                    "toggleAll colocou no set um id que não existe em model.all: %r "
                    "(ids=%r)" % (k, IDS)
                )


def test_o_clique_num_provider_expande_so_ele(bancada):
    """Item 3 verificado por CLIQUE, não só pela chamada de ``toggleExpanded``.

    Dos cliques que NÃO expandem todos, cada um precisa deixar no set um único
    id — o do próprio provider. Um controle que expandisse o provider errado, ou
    dois, aparece aqui.
    """
    isolados = [c for c in bancada.cliques if not c["all"] and c["mudou"]]
    assert isolados, (
        "nenhum clique por provider mudou o estado; cliques=%r" % (bancada.cliques,)
    )
    for c in isolados:
        assert len(c["keys"]) == 1, (
            "o clique %s expandiu %r — um controle por provider deve expandir "
            "EXATAMENTE um." % (c["i"], c["keys"])
        )
        assert c["keys"][0] in IDS, (
            "o clique %s expandiu %r, que não é um provider do modelo"
            % (c["i"], c["keys"])
        )


def test_nenhum_clique_expande_dois_providers_de_uma_vez(bancada):
    """Negativo do item 3: não existe clique intermediário (2 de 3).

    O único alvo que pode mexer em mais de um provider é o botão do topo. Um
    clique que deixasse o set com 2 ids e não todos seria um controle global
    parcial — o defeito que o item 3 descreve.
    """
    ofensas = [c for c in bancada.cliques
               if not c["all"] and len(c["keys"]) > 1]
    assert not ofensas, (
        "clique(s) expandiram mais de um provider sem serem o botão global: %r"
        % (ofensas,)
    )


# --------------------------------------------------------------------------- #
# Item 5 — estado VOLÁTIL
# --------------------------------------------------------------------------- #


def test_o_estado_de_expansao_nao_persiste_ao_remontar(bancada):
    """Decisão do dono (2026-10-28): o estado de expansão morre com a surface.

    Remontar a view é a aproximação observável de "reabrir o popout": um set que
    sobrevivesse a isso foi gravado em algum lugar. O harness expande tudo, joga
    a view fora, monta de novo e lê ``expandedIds`` do zero.
    """
    assert bancada.remount_ids is not None, (
        "a fase de remontagem não foi medida; erros=%s" % (bancada.erros,)
    )
    assert bancada.remount_count == 0 and bancada.remount_ids == [], (
        "depois de remontar, o set de expansão deveria estar VAZIO; veio %r (%s "
        "ids). Estado volátil não sobrevive à surface." 
        % (bancada.remount_ids, bancada.remount_count)
    )


def test_a_expansao_nao_e_gravada_como_setting(bancada):
    """A outra forma de persistir: escrever no store do host.

    ``pluginApi.saveSetting`` é o único caminho de escrita declarado (R5). A
    instrumentação do harness registra toda chamada; nenhuma pode ter acontecido
    por causa da expansão.
    """
    assert bancada.save_keys_before_remount is not None, (
        "a instrumentação de saveSetting não foi medida"
    )
    assert bancada.save_keys_before_remount == [], (
        "expandir provider(s) chamou saveSetting com %r. O estado de expansão é "
        "VOLÁTIL: não pode ser gravado." % (bancada.save_keys_before_remount,)
    )
    assert bancada.save_keys == [], (
        "chamadas a saveSetting durante a execução: %r — nenhuma é esperada do "
        "modo compacto" % (bancada.save_keys,)
    )


# --------------------------------------------------------------------------- #
# Regressão de contexto: o modelo do host não é mutado
# --------------------------------------------------------------------------- #


def test_o_modelo_recebido_nao_e_mutado_pelas_consultas(bancada):
    """``visibleMetrics`` não pode REMOVER métricas do modelo.

    Uma implementação que apagasse as métricas "ocultas" do objeto do provider
    devolveria a lista certa e destruiria o dado: o dano só apareceria ao voltar
    para expanded. Aqui os labels do modelo são comparados com os do fixture,
    depois de todas as consultas.
    """
    for prefixo in ("inicial", "compact", "compact+1expandido"):
        f = bancada.fase(prefixo)
        for pid in IDS:
            assert f.prov(pid)["allLabels"] == LABELS[pid], (
                "[%s/%s] as métricas do MODELO mudaram: %r, esperado %r"
                % (prefixo, pid, f.prov(pid)["allLabels"], LABELS[pid])
            )


# --------------------------------------------------------------------------- #
# AMBIGUIDADES do contrato (D5)
# --------------------------------------------------------------------------- #

AMBIGUIDADES = """
1. "MODO COMPACTO REDUZ A ALTURA" — MEDIDO POR CONTAGEM, NÃO POR PIXELS. O
   critério de done pede altura; `implicitHeight` não resolve no harness offline
   (medido nesta base). A suíte prova a redução do número de textos e de
   retângulos desenhados, que é a CAUSA da altura menor, e o cabeçalho declara
   esse limite. Nenhuma asserção aqui diz "N pixels a menos".

2. O BOTÃO SÓ EXISTE EM MODO COMPACTO? O contrato diz "um botão no topo alterna
   tudo" sem dizer se ele aparece também em `expanded`. Medido: na view atual ele
   só existe em compacto (em expanded há 1 nó clicável, o de atualizar; em
   compacto há 4). A suíte NÃO exige nem proíbe a presença — só exige que, quando
   existir um clique que expande todos, ele também recolha. Se o dono quiser o
   botão sempre visível, este é o ponto sem oráculo.

3. `anyProviderExpanded` CONTA PROVIDER DE `model.all` OU SÓ OS VISÍVEIS? O
   contrato define a propriedade para o rótulo do botão (expandir/recolher). Com
   `showSecondaries` falso, alguns providers não são desenhados; não é dito se um
   id expandido de um provider invisível manteria a propriedade verdadeira. A
   suíte exercita só o caso em que todos os providers estão visíveis.

4. `toggleAll` COM ALGUNS EXPANDIDOS. O contrato define dois estados: "a partir
   de vazio expande todos" e "chamado de novo recolhe todos". Não define o que
   faz com 1 de 3 expandido — expandir o resto ou recolher tudo? O oráculo
   declarado cobre apenas os dois extremos, e a suíte só os afirma. (Medido na
   view atual: de 0 vai a todos; de todos volta a 0.)

5. `visibleMetrics` DEVOLVE REFERÊNCIA OU CÓPIA? O contrato devolve "array das
   métricas que devem aparecer". A suíte não distingue: compara `label`/`percent`
   dos itens. Uma implementação que devolvesse cópias passaria igual — e está
   correto que passe, porque a diferença não é observável pelo contrato.

6. ESTADO VOLÁTIL — "NÃO PERSISTE" É VERIFICADO POR REMONTAGEM + saveSetting. A
   remontagem é a aproximação disponível de "reabrir o popout"; um estado
   guardado em `stateDir` por outro caminho (arquivo escrito à mão) não seria
   detectado. A verificação de `saveSetting` cobre o caminho declarado (R5), que é
   o único sancionado.

7. `leadingMetric` COM `percent` IGUAL MAS UM NULO. Coberto como "nulo nunca é
   líder" (`nulo-vs-zero`). NÃO coberto: dois nulos e um número — a leitura
   natural é o número vencer, mas o contrato só diz "se NENHUMA tiver percent,
   devolve a primeira"; com uma tendo, é a maior delas. O caso existe no corpus
   (`nulo-antes-do-lider`) e a suíte assere a leitura natural, que é a única
   compatível com "métrica sem percent não tem magnitude para comparar".

8. PERCENT NEGATIVO. O contrato declara `percent (null ou 0..100+)`, então
   negativo está fora do domínio. `negativo-nao-vence` espera que -5 perca para
   um nulo — isto é, que o nulo caia no fallback "primeira da lista". Se a
   implementação tratasse nulo como -Infinito e negativo como líder, a resposta
   seria a mesma por acidente (`A` é o primeiro e o negativo). O teste NÃO
   distingue os dois motivos: está asserido só o resultado, não a razão.

9. A CONTAGEM COMO PROVA DE "ENCOLHEU" É SENSÍVEL AO FIXTURE. Com 3 providers e
   5 métricas o compacto caiu de 42 para 24 textos. Um fixture com 1 provider e 2
   métricas poderia dar contagens iguais (o cabeçalho do provider e o rótulo
   "+N more" acrescentam um texto justamente onde outro sai). O teste usa o
   fixture maior de propósito, e a asserção é ESTRITA (`<`), então um compacto
   que não reduza nada falha.
"""
