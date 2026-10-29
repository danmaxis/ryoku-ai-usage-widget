# -*- coding: utf-8 -*-
"""Testes de comportamento de T27 — resumo operacional no topo do popout.

Gerado em contexto isolado (D5) — sem acesso à implementação.
Base: SPEC rodada 3, tarefa T27.

Contrato exercitado (bloco assinado da tarefa, itens 1–5 + semântica obrigatória)::

    countableQuotas(model) -> array de { providerId, label, metric }
    operationalSummary(model, nowEpoch)
        -> { exhausted, high, nextResetRelative, nextResetSeconds, total }
    operationalSummarySegments(model, nowEpoch) -> array de strings traduzidas

    1. Esgotado é ``percent >= 100`` na PRÓPRIA cota; o resumo conta COTAS, não
       providers.
    2. Um provider com 3 métricas acima de 80% conta 3 cotas; a MESMA janela
       repetida não pode ser colapsada — a deduplicação é por
       ``(provider, label da métrica)``, nunca por percentual.
    3. Próximo reset = a menor diferença POSITIVA entre agora e os ``reset_at``;
       omitido se não houver nenhum futuro (passado e nulo não concorrem).
    4. Zero estados: o segmento é omitido, não escrito como "0 esgotados".
    5. Usa a formatação de tempo de T23.
    * Provider com ``status === "error"`` contribui ZERO cotas.
    * ``>= 100`` → esgotado; ``> 80`` e ``< 100`` → "acima de 80%" (exclusivos).
    * Singular correto: 1 cota no singular, 2+ no plural.

Como o comportamento é observado sem host visual
------------------------------------------------
``quickshell`` OFFLINE (``QT_QPA_PLATFORM=offscreen``). O harness
``tests/qml/t27_summary_harness.qml`` monta a view com um ``pluginApi``
sintético, resolve as três funções pelo nome e as CHAMA com os modelos montados
aqui, despejando o resultado campo a campo. ``service/Main.qml`` NÃO é montado:
o resumo é aritmética sobre um modelo, e montar o coletor faria a sonda depender
de PATH, rede e estado do usuário para responder uma pergunta sobre contagem.

O oráculo é o CONTRATO. Nenhum teste aqui deriva o esperado de uma cópia do
corpo das funções; o que se compara é contagem, exclusividade de faixa, omissão
de segmento vazio e a formatação de tempo de T23 — esta última composta pela
PRÓPRIA ``resetParts`` de T23, para que a suíte nunca fixe um formato à mão.

Três armadilhas desta base, tratadas explicitamente
---------------------------------------------------
* Objeto/array devolvido por função QML pode achatar em ``JSON.stringify``. O
  harness serializa campo a campo e índice a índice; este arquivo decide
  array-ness por ``$len``, nunca por ``len(json)`` de um dump genérico.
* ``objectName`` NÃO é usado em lugar nenhum: nomear um nó faz o dump do tipo
  carregar ponteiro de memória e quebra comparações entre execuções.
* A linha RENDERIZADA usa o relógio do processo, enquanto os segmentos usam o
  ``nowEpoch`` recebido. Por isso o teste de renderização só compara os
  segmentos de CONTAGEM (que não dependem do relógio) e verifica o segmento de
  reset por prefixo; comparar a duração exata entre as duas chamadas seria
  flaky por deslocamento de relógio — medido: 1h 10min contra 1h 9min.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Localização dos artefatos (o conteúdo de Widget.qml nunca é lido)
# --------------------------------------------------------------------------- #

TEST_DIR = Path(__file__).resolve().parent            # <repo>/ai-usage/tests
#: Override por ambiente: uso EXCLUSIVO da verificação de falsificabilidade
#: desta própria suíte. O caminho de produção não o define.
PLUGIN_DIR = Path(os.environ.get("T27_PLUGIN_DIR", TEST_DIR.parent))
HARNESS = TEST_DIR / "qml" / "t27_summary_harness.qml"

_QUICK = shutil.which("quickshell") or shutil.which("qs")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

pytestmark = pytest.mark.skipif(
    _QUICK is None,
    reason="quickshell ausente: a view QML e as funções puras não podem ser exercitadas",
)

# --------------------------------------------------------------------------- #
# Instante de referência: todos os reset_at derivam dele
# --------------------------------------------------------------------------- #

NOW = int(datetime(2026, 10, 28, 18, 0, 0, tzinfo=timezone.utc).timestamp())

#: "Próximo reset em 3h" é o exemplo do objetivo; a asserção usa a MESMA
#: formatação que T23 devolve, não este literal.
RESET_3H = 3 * 3600


def iso(offset_secs: int, base: int = NOW) -> str:
    """ISO-8601 ``Z`` deslocado ``offset_secs`` do instante de referência."""
    t = datetime.fromtimestamp(base, timezone.utc) + timedelta(seconds=offset_secs)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# Construtores de fixture (espelham a forma declarada em "O modelo de dados")
# --------------------------------------------------------------------------- #


def metric(label: str, percent, reset_at=None, window_secs: int = 18000,
           severity: str = "low") -> dict:
    return {
        "label": label,
        "percent": percent,
        "value": ("%s%%" % percent) if isinstance(percent, (int, float)) else str(label),
        "severity": severity,
        "detail": "",
        "reset_at": reset_at,
        "window_secs": window_secs,
    }


def provider(pid: str, metrics: list, status: str = "ready", **extra) -> dict:
    p = {"id": pid, "display_name": pid.title(), "status": status, "metrics": metrics}
    p.update(extra)
    return p


def model(providers: list) -> dict:
    return {
        "schema": 1,
        "primary": providers[0] if providers else None,
        "secondary": providers[1:],
        "all": providers,
        "total_providers": len(providers),
        "with_issues": sum(1 for p in providers if p.get("status") == "error"),
    }


# --------------------------------------------------------------------------- #
# Corpus — cada caso é { name, fn, model, now [, resetIso] }
# --------------------------------------------------------------------------- #

CASES: list[dict] = []


def case(name: str, fn: str, mdl, now: int = NOW, reset_iso=None) -> dict:
    c = {"name": name, "fn": fn, "model": mdl, "now": now}
    if reset_iso is not None:
        c["resetIso"] = reset_iso
    return c


# --- item 2: as duas refutações explícitas do contrato --------------------- #
CASES.append(case(
    "tres-altas-no-mesmo-provider", "summary",
    model([provider("a", [metric("A", 90, iso(3600)),
                          metric("B", 95, iso(7200)),
                          metric("C", 99, iso(10800))])])))
CASES.append(case(
    "mesma-janela-repetida", "summary",
    model([provider("a", [metric("Session (5h)", 100, iso(600)),
                          metric("Session (5h)", 100, iso(600))])])))
CASES.append(case(
    "mesmo-label-em-providers-diferentes", "summary",
    model([provider("a", [metric("Session (5h)", 100, iso(60))]),
           provider("b", [metric("Session (5h)", 100, iso(120))])])))
CASES.append(case(
    "mesmo-percentual-labels-diferentes", "summary",
    model([provider("a", [metric("X", 90, iso(60)),
                          metric("Y", 90, iso(60)),
                          metric("Z", 90, iso(60))])])))

# --- fronteiras de faixa (exclusivas) ------------------------------------- #
for nome, pct in (("pct-79-9", 79.9), ("pct-80", 80), ("pct-80-1", 80.1),
                  ("pct-84-9", 84.9), ("pct-99", 99), ("pct-99-9", 99.9),
                  ("pct-100", 100), ("pct-100-5", 100.5), ("pct-150", 150)):
    CASES.append(case(nome, "summary", model([provider("a", [metric("S", pct, iso(60))])])))

# --- provider em erro ------------------------------------------------------ #
CASES.append(case(
    "provider-em-erro-com-cota-estourada", "summary",
    model([provider("a", [metric("S", 150, iso(60))], status="error")])))
CASES.append(case(
    "provider-em-erro-nao-e-oscila-o-vizinho", "summary",
    model([provider("e", [metric("S", 150, iso(30))], status="error"),
           provider("ok", [metric("T", 100, iso(900))])])))
CASES.append(case(
    "so-providers-em-erro-segmentos", "segments",
    model([provider("e", [metric("S", 100, iso(30))], status="error"),
           provider("f", [metric("T", 100, iso(60))], status="error")])))

# --- próximo reset --------------------------------------------------------- #
CASES.append(case(
    "menor-diferenca-positiva", "summary",
    model([provider("a", [metric("S", 10, iso(7200)),
                          metric("T", 10, iso(1800)),
                          metric("U", 10, iso(5400))])])))
CASES.append(case(
    "empate-de-reset", "summary",
    model([provider("a", [metric("S", 100, iso(1800))]),
           provider("b", [metric("T", 100, iso(1800))])])))
CASES.append(case(
    "empate-segments", "segments",
    model([provider("a", [metric("S", 100, iso(1800))]),
           provider("b", [metric("T", 100, iso(1800))])])))
CASES.append(case(
    "reset-no-passado", "summary",
    model([provider("a", [metric("S", 10, iso(-3600))])])))
CASES.append(case(
    "reset-no-passado-e-futuro", "summary",
    model([provider("a", [metric("S", 10, iso(-3600)),
                          metric("T", 10, iso(1200))])])))
CASES.append(case(
    "reset-exatamente-agora", "segments",
    model([provider("a", [metric("S", 100, iso(0))])])))
CASES.append(case(
    "reset-nulo-e-passado-apenas", "segments",
    model([provider("a", [metric("S", 100, None),
                          metric("T", 100, iso(-60))])])))

# ISO com offset aplicado (1800s À FRENTE, escrito em -03:00).
_OFF = (datetime.fromtimestamp(NOW, timezone.utc)
        + timedelta(seconds=1800) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")
_OFF_ISO = _OFF + "-03:00"
CASES.append(case("iso-com-offset", "summary",
                  model([provider("a", [metric("S", 10, _OFF_ISO)])]), reset_iso=_OFF_ISO))
CASES.append(case("reset-lixo", "summary",
                  model([provider("a", [metric("S", 10, "not-a-date")])])))
CASES.append(case("reset-nulo", "summary",
                  model([provider("a", [metric("S", 10, None)])])))

# --- item 5: composição com T23 ------------------------------------------- #
for nome, secs in (("t23-1min", 60), ("t23-1h1min", 3661), ("t23-4d56min", 4 * 86400 + 56 * 60),
                   ("t23-3h", RESET_3H)):
    CASES.append(case(nome, "summary",
                      model([provider("a", [metric("S", 100, iso(secs))])]),
                      reset_iso=iso(secs)))

# --- item 4 / zero estados ------------------------------------------------ #
CASES.append(case("modelo-vazio", "summary", model([])))
CASES.append(case("nada-a-dizer", "segments",
                  model([provider("a", [metric("S", 10, iso(-60))])])))
CASES.append(case("nada-a-dizer-reset-nulo", "segments",
                  model([provider("a", [metric("S", 55, None)])])))

# --- singular / plural e exclusividade nos textos ------------------------- #
CASES.append(case("seg-uma-esgotada", "segments",
                  model([provider("a", [metric("S", 100, iso(3661))])])))
CASES.append(case("seg-duas-esgotadas", "segments",
                  model([provider("a", [metric("S", 100, iso(3661)),
                                        metric("T", 100, iso(9000))])])))
CASES.append(case("seg-uma-alta", "segments",
                  model([provider("a", [metric("S", 85, iso(60))])])))
CASES.append(case("seg-duas-altas", "segments",
                  model([provider("a", [metric("S", 85, iso(60)),
                                        metric("T", 90, iso(60))])])))
CASES.append(case("seg-misto", "segments",
                  model([provider("a", [metric("S", 100, iso(1800)),
                                        metric("T", 90, iso(3600)),
                                        metric("U", 95, iso(7200))])])))
CASES.append(case("misto-summary", "summary",
                  model([provider("a", [metric("S", 100, iso(1800)),
                                        metric("T", 90, iso(3600)),
                                        metric("U", 95, iso(7200))])])))
CASES.append(case("seg-cem-e-alta", "segments",
                  model([provider("a", [metric("S", 100, iso(60)),
                                        metric("T", 100, iso(60))])])))
CASES.append(case("cem-e-alta-summary", "summary",
                  model([provider("a", [metric("S", 100, iso(60)),
                                        metric("T", 100, iso(60))])])))

# --- entradas degeneradas (não podem quebrar) ----------------------------- #
CASES.append(case("modelo-nulo", "summary", None))
CASES.append(case("modelo-sem-all", "summary",
                  {"primary": provider("a", [metric("S", 100, iso(60))]),
                   "secondary": []}))
CASES.append(case("provider-sem-metrics", "summary",
                  model([{"id": "a", "display_name": "a", "status": "ready"}])))
CASES.append(case("percent-nulo", "summary",
                  model([provider("a", [metric("S", None, iso(60))])])))
CASES.append(case("percent-nulo-contra-cem", "summary",
                  model([provider("a", [metric("S", None, iso(60)),
                                        metric("T", 100, iso(120))])])))

# --- countableQuotas ------------------------------------------------------ #
CASES.append(case("countable-modelo-nulo", "countable", None))
CASES.append(case("countable-provider-em-erro", "countable",
                  model([provider("a", [metric("S", 100)], status="error"),
                         provider("b", [metric("T", 50)])])))
CASES.append(case("countable-dedup", "countable",
                  model([provider("a", [metric("S", 90), metric("S", 90)])])))
CASES.append(case("countable-campos", "countable",
                  model([provider("a", [metric("L1", 10, None, 18000),
                                        metric("L2", 85, None, 604800)])])))
CASES.append(case("countable-zero-cotas", "countable", model([])))

#: Pares (summary, countable) com o MESMO modelo: o `total` do resumo é
#: comparado com o tamanho da lista de cotas contáveis. Ver AMBIGUIDADES item 3.
PARES_TOTAL = [
    ("tres-altas-no-mesmo-provider", "countable-tres-altas",
     model([provider("a", [metric("A", 90), metric("B", 95), metric("C", 99)])])),
    ("mesma-janela-repetida", "countable-mesma-janela",
     model([provider("a", [metric("Session (5h)", 100), metric("Session (5h)", 100)])])),
    ("provider-em-erro-com-cota-estourada", "countable-erro",
     model([provider("a", [metric("S", 150)], status="error")])),
]
for _sum_name, _cnt_name, _mdl in PARES_TOTAL:
    CASES.append(case(_cnt_name, "countable", _mdl))


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


def _rodar(env_extra: dict, timeout: int = 180) -> list[str]:
    assert HARNESS.is_file(), f"harness QML ausente: {HARNESS}"
    assert (PLUGIN_DIR / "content" / "Widget.qml").is_file(), "content/Widget.qml ausente"
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("WAYLAND_DISPLAY", None)
    env["T27_PLUG_DIR"] = str(PLUGIN_DIR)
    env["T27_STATE_DIR"] = "/tmp/t27-suite-state"
    env.update(env_extra)
    try:
        proc = subprocess.run([_QUICK, "-p", str(HARNESS)], capture_output=True,
                              text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        pytest.fail(
            "o harness do resumo não terminou em %ss — laço na contagem, ou a view "
            "não monta." % timeout
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


class Bancada:
    """Registros de uma execução, indexados por papel/caso."""

    def __init__(self, registros: list[str]):
        self.registros = registros
        self.roles: dict[str, str] = {}
        self.hosts: dict[str, str] = {}
        self.candidatos: dict[str, dict[str, bool]] = {}
        self.thresholds: dict[str, object] = {}
        self.t23: dict[str, object] = {}
        self.casos: dict[str, tuple[str, object]] = {}
        self.excecoes: dict[str, str] = {}
        self.render_segments = None
        self.render_texts: list[str] = []
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
            elif r.startswith("P_THRESHOLD|"):
                _t, nome, valor = r.split("|", 2)
                self.thresholds[nome] = _json(valor, "P_THRESHOLD " + nome)
            elif r.startswith("T23|"):
                _t, role, caso, valor = r.split("|", 3)
                self.t23["%s/%s" % (role, caso)] = _json(valor, "T23")
            elif r.startswith("FN_THROW|"):
                _t, role, caso, msg = r.split("|", 3)
                self.excecoes["%s/%s" % (role, caso)] = msg
            elif r.startswith("FN|"):
                _t, role, caso, tipo, bruto = r.split("|", 4)
                self.casos["%s/%s" % (role, caso)] = (tipo, _json(bruto, "%s/%s" % (role, caso)))
            elif r.startswith("RENDER_SEGMENTS|"):
                self.render_segments = _json(r.split("|", 1)[1], "RENDER_SEGMENTS")
            elif r.startswith("RENDER_TEXT|"):
                self.render_texts.append(_json(r.split("|", 1)[1], "RENDER_TEXT"))
            elif r.startswith("VIEW_ERR|"):
                self.erros.append(r)
        self.view_present = any(r == "VIEW_PRESENT|true" for r in registros)

    def bruto(self, role: str, caso: str):
        chave = "%s/%s" % (role, caso)
        assert chave not in self.excecoes, (
            "[%s] a função lançou exceção: %r — o contrato não prevê entrada que "
            "derrube o resumo; registros=%s" % (chave, self.excecoes[chave], self.registros)
        )
        assert chave in self.casos, (
            "[%s] caso não executado (função %r). registros=%s"
            % (chave, self.roles.get(role), self.registros)
        )
        return self.casos[chave]

    def resumo(self, caso: str) -> dict:
        tipo, dados = self.bruto("summary", caso)
        assert tipo == "object" and isinstance(dados, dict), (
            "[summary/%s] esperado objeto, veio %s (%r)" % (caso, tipo, dados)
        )
        for campo in ("exhausted", "high", "total", "nextResetSeconds", "nextResetRelative"):
            assert campo in dados, (
                "[summary/%s] campo %r ausente no retorno. A interface declara "
                "{exhausted, high, nextResetRelative, nextResetSeconds, total}. "
                "dump=%s" % (caso, campo, dados)
            )
            assert not (isinstance(dados[campo], dict) and dados[campo].get("$undefined")), (
                "[summary/%s] campo %r veio undefined. dump=%s" % (caso, campo, dados)
            )
        return dados

    def contagens(self, caso: str) -> tuple[int, int]:
        d = self.resumo(caso)
        for campo in ("exhausted", "high"):
            assert isinstance(d[campo], int), (
                "[summary/%s] %r deve ser inteiro; veio %r (%s)"
                % (caso, campo, d[campo], type(d[campo]).__name__)
            )
        return d["exhausted"], d["high"]

    def segmentos(self, caso: str) -> list[str]:
        tipo, dados = self.bruto("segments", caso)
        assert isinstance(dados, dict) and "$len" in dados, (
            "[segments/%s] esperado array de strings; veio %s (%r)" % (caso, tipo, dados)
        )
        assert "$notArray" not in dados, (
            "[segments/%s] não é array: %r" % (caso, dados)
        )
        itens = dados["items"]
        assert dados["$len"] == len(itens), (
            "[segments/%s] $len=%s não confere com %s itens: %r"
            % (caso, dados["$len"], len(itens), dados)
        )
        for i, s in enumerate(itens):
            assert isinstance(s, str), (
                "[segments/%s] item %s não é string: %r" % (caso, i, s)
            )
        return itens

    def cotas(self, caso: str) -> list[dict]:
        tipo, dados = self.bruto("countable", caso)
        assert isinstance(dados, dict) and "$len" in dados, (
            "[countable/%s] esperado array; veio %s (%r)" % (caso, tipo, dados)
        )
        assert "$notArray" not in dados, "[countable/%s] não é array: %r" % (caso, dados)
        return dados["items"]


@pytest.fixture(scope="module")
def bancada() -> Bancada:
    return Bancada(_rodar({"T27_CASES": json.dumps(CASES, ensure_ascii=False),
                           "T27_RENDER_MODEL": json.dumps(model([]))}))


# --------------------------------------------------------------------------- #
# Âncora
# --------------------------------------------------------------------------- #


def test_artefatos_sob_teste_existem():
    assert HARNESS.is_file(), f"harness QML ausente: {HARNESS}"
    assert (PLUGIN_DIR / "content" / "Widget.qml").is_file(), "content/Widget.qml ausente"


def test_as_tres_funcoes_puras_existem_na_view(bancada):
    """Sem esta âncora, todos os outros testes falhariam por atributo ausente."""
    assert bancada.view_present, (
        "a view não montou; erros=%s; nada a exercitar" % bancada.erros
    )
    faltando = [r for r in ("countable", "summary", "segments") if not bancada.roles.get(r)]
    assert not faltando, (
        "função pública ausente para o(s) papel(is) %s. O contrato exige "
        "countableQuotas(model), operationalSummary(model, nowEpoch) e "
        "operationalSummarySegments(model, nowEpoch) alcançáveis na view montada. "
        "Sondagem=%s · hosts=%s" % (faltando, bancada.candidatos, bancada.hosts)
    )


def test_os_limiares_declarados_sao_os_do_contrato(bancada):
    """``exhaustedThreshold`` = 100 e ``highWaterThreshold`` = 80.

    O contrato nomeia as duas propriedades e diz que os três limiares desta
    rodada (100/80/85) NÃO são intercambiáveis. Ler a propriedade é o que
    permite afirmar "o resumo conta em 80" sem fixar o 80 duas vezes.
    """
    ex = bancada.thresholds.get("exhaustedThreshold")
    hi = bancada.thresholds.get("highWaterThreshold")
    assert ex == 100, (
        "exhaustedThreshold deveria ser 100; veio %r. O contrato define esgotado "
        "como percent >= 100 na própria cota." % (ex,)
    )
    assert hi == 80, (
        "highWaterThreshold deveria ser 80; veio %r. O contrato diz 'acima de 80%%' "
        "(o 85 é o limiar da COR, T26, e subir este para 85 esconderia cotas 80–85)."
        % (hi,)
    )


# --------------------------------------------------------------------------- #
# Item 1 — faixas exclusivas; conta cotas, não providers
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("caso,pct,esperado", [
    ("pct-79-9", 79.9, (0, 0)),
    ("pct-80", 80.0, (0, 0)),          # o limiar é "> 80", não ">= 80"
    ("pct-80-1", 80.1, (0, 1)),
    ("pct-84-9", 84.9, (0, 1)),
    ("pct-99", 99.0, (0, 1)),
    ("pct-99-9", 99.9, (0, 1)),
    ("pct-100", 100.0, (1, 0)),        # 100 é esgotado e NÃO também "acima de 80%"
    ("pct-100-5", 100.5, (1, 0)),
    ("pct-150", 150.0, (1, 0)),
])
def test_faixas_de_esgotado_e_acima_de_80_sao_exclusivas(bancada, caso, pct, esperado):
    """Uma cota tem UM estado: esgotada (>=100) ou acima de 80% (>80 e <100).

    O caso de 100% é o que o contrato chama de exclusivo; contar 100% nos dois
    lugares faria o resumo dizer "1 esgotado · 1 acima de 80%" para uma cota só.
    """
    obtido = bancada.contagens(caso)
    assert obtido == esperado, (
        "[%s] percent=%s deveria dar (exhausted, high)=%s; veio %s. Contrato: "
        "esgotado é percent >= 100; 'acima de 80%%' é percent > 80 E < 100."
        % (caso, pct, esperado, obtido)
    )


def test_tres_metricas_acima_de_80_no_mesmo_provider_contam_tres_cotas(bancada):
    """Refutação explícita do contrato: nada de colapsar por provider.

    "Um provider com 3 métricas acima de 80% conta 3 cotas." O sintoma original
    é justamente um resumo que dizia "1" para um provider com três janelas altas.
    """
    ex, hi = bancada.contagens("tres-altas-no-mesmo-provider")
    assert (ex, hi) == (0, 3), (
        "3 métricas acima de 80%% no MESMO provider deveriam contar 3 cotas; veio "
        "(exhausted=%s, high=%s). O resumo conta cotas, não providers." % (ex, hi)
    )


def test_mesmo_percentual_com_labels_diferentes_conta_cada_cota(bancada):
    """O segundo lado da regra: a deduplicação NUNCA é por percentual.

    Três janelas diferentes com o mesmo 90% são três cotas — se a chave fosse o
    percentual, viraria 1.
    """
    ex, hi = bancada.contagens("mesmo-percentual-labels-diferentes")
    assert (ex, hi) == (0, 3), (
        "3 métricas com o MESMO percentual e labels diferentes são 3 cotas "
        "(janelas distintas); veio (exhausted=%s, high=%s). Deduplicar por "
        "percentual é exatamente o que o contrato proíbe." % (ex, hi)
    )


def test_mesma_janela_repetida_conta_uma_vez(bancada):
    """Refutação explícita do outro lado: ``(provider, label)`` deduplica.

    Duas entradas idênticas de "Session (5h)" no mesmo provider são a MESMA
    janela repetida — contam 1, não 2.
    """
    ex, hi = bancada.contagens("mesma-janela-repetida")
    assert (ex, hi) == (1, 0), (
        "a mesma janela repetida (label igual, mesmo provider) deveria contar 1 "
        "cota; veio (exhausted=%s, high=%s). A chave de deduplicação é "
        "(provider, label)." % (ex, hi)
    )


def test_mesmo_label_em_providers_diferentes_conta_duas(bancada):
    """A chave de dedup inclui o PROVIDER: "Session (5h)" em A e B são 2 cotas."""
    ex, hi = bancada.contagens("mesmo-label-em-providers-diferentes")
    assert (ex, hi) == (2, 0), (
        'o label "Session (5h)" em dois providers diferentes são 2 cotas; veio '
        "(exhausted=%s, high=%s). Deduplicar sem o provider colapsaria janelas "
        "de contas distintas." % (ex, hi)
    )


def test_percent_nulo_nao_entra_em_nenhuma_faixa(bancada):
    """Cota sem percent não é zero por cento: não é esgotada nem "acima de 80%"."""
    ex, hi = bancada.contagens("percent-nulo")
    assert (ex, hi) == (0, 0), (
        "uma cota com percent nulo não pode cair em nenhuma faixa; veio "
        "(exhausted=%s, high=%s)" % (ex, hi)
    )
    ex2, hi2 = bancada.contagens("percent-nulo-contra-cem")
    assert (ex2, hi2) == (1, 0), (
        "com uma cota de 100%% e outra sem percent, o esperado é 1 esgotada; veio "
        "(exhausted=%s, high=%s)" % (ex2, hi2)
    )


# --------------------------------------------------------------------------- #
# Semântica obrigatória — provider em erro contribui ZERO
# --------------------------------------------------------------------------- #


def test_provider_em_erro_contribui_zero_cotas(bancada):
    """``status === "error"`` → ZERO, mesmo com uma métrica de 150%.

    E não é só a contagem: ``total`` também fica 0, porque o provider em erro
    não tem cotas comparáveis.
    """
    d = bancada.resumo("provider-em-erro-com-cota-estourada")
    assert (d["exhausted"], d["high"]) == (0, 0), (
        "provider com status=error contribui ZERO cotas, mesmo com percent=150; "
        "veio exhausted=%s high=%s" % (d["exhausted"], d["high"])
    )
    assert d["total"] == 0, (
        "o provider em erro também não deve somar em total; veio total=%s" % d["total"]
    )
    assert d["nextResetSeconds"] in (None, {"$null": True}, ""), (
        "nada sobra de um provider em erro — nextResetSeconds deveria ser nulo; "
        "veio %r" % (d["nextResetSeconds"],)
    )


def test_provider_em_erro_nao_contamina_a_contagem_do_vizinho(bancada):
    """O caso misto: a cota do provider em erro NÃO entra, a do pronto entra."""
    ex, hi = bancada.contagens("provider-em-erro-nao-e-oscila-o-vizinho")
    assert (ex, hi) == (1, 0), (
        "com um provider em erro (150%%) e um pronto (100%%), o resumo deve contar "
        "1 cota; veio (exhausted=%s, high=%s). A cota de 150%% do provider em erro "
        "está sendo contada." % (ex, hi)
    )


def test_so_providers_em_erro_nao_produzem_segmento(bancada):
    """Nada a dizer = array vazio, nem "0 esgotados"."""
    segs = bancada.segmentos("so-providers-em-erro-segmentos")
    assert segs == [], (
        "dois providers em erro (uma cota de 100%% cada, ignoradas) não têm nada a "
        "dizer; os segmentos deveriam ser vazios, mas vieram %r" % (segs,)
    )


# --------------------------------------------------------------------------- #
# Item 3 — próximo reset
# --------------------------------------------------------------------------- #


def test_proximo_reset_e_a_menor_diferenca_positiva(bancada):
    """7200s, 1800s, 5400s → 1800. Não a primeira, não a última."""
    d = bancada.resumo("menor-diferenca-positiva")
    assert d["nextResetSeconds"] == 1800, (
        "o próximo reset é a MENOR diferença positiva: 1800s; veio %r. (Os resets "
        "eram 7200, 1800 e 5400.)" % (d["nextResetSeconds"],)
    )


def test_empate_de_reset_da_um_numero_unico_e_igual(bancada):
    """Dois resets no mesmo instante não podem duplicar nem virar soma."""
    d = bancada.resumo("empate-de-reset")
    assert d["nextResetSeconds"] == 1800, (
        "empate de reset (dois em 1800s) deveria dar 1800; veio %r — uma soma ou "
        "uma lista aqui significa que o empate foi mal tratado."
        % (d["nextResetSeconds"],)
    )
    segs = bancada.segmentos("empate-segments")
    assert len(segs) == 2, (
        "empate de reset: 2 cotas esgotadas + 1 reset compartilhado = 2 segmentos "
        "(um por estado + o reset); vieram %r. Uma lista ou uma soma de resets "
        "empatados aparece aqui." % (segs,)
    )


def test_reset_no_passado_nao_concorre(bancada):
    """Item 3: passado não é "próximo"; não pode aparecer como 0 nem negativo."""
    d = bancada.resumo("reset-no-passado")
    assert d["nextResetSeconds"] in (None, {"$null": True}, ""), (
        "só há um reset no passado: nextResetSeconds deveria ser nulo (omitido), "
        "nunca 0 nem negativo; veio %r" % (d["nextResetSeconds"],)
    )
    assert d["nextResetRelative"] in ("", None, {"$null": True}), (
        "sem reset futuro o texto relativo deveria estar vazio; veio %r"
        % (d["nextResetRelative"],)
    )


def test_reset_no_passado_e_futuro_o_futuro_vence(bancada):
    """A presença de um passado não pode esconder o futuro (nem vencê-lo)."""
    d = bancada.resumo("reset-no-passado-e-futuro")
    assert d["nextResetSeconds"] == 1200, (
        "com um reset em -3600s e outro em +1200s, o próximo é 1200; veio %r"
        % (d["nextResetSeconds"],)
    )


def test_reset_exatamente_agora_nao_concorre(bancada):
    """Diferença POSITIVA: zero não é positivo.

    Medido no contrato: um reset em ``now`` produz só o segmento de contagem, sem
    "próximo reset em agora".
    """
    segs = bancada.segmentos("reset-exatamente-agora")
    assert len(segs) == 1, (
        "um reset exatamente em 'agora' (diferença 0) não é positivo e não pode "
        "gerar segmento de reset; segmentos=%r" % (segs,)
    )


def test_reset_nulo_nao_concorre(bancada):
    d = bancada.resumo("reset-nulo")
    assert d["nextResetSeconds"] in (None, {"$null": True}, ""), (
        "reset_at nulo não concorre a próximo reset; veio %r" % (d["nextResetSeconds"],)
    )


def test_reset_com_lixo_nao_quebra_nem_inventa_duracao(bancada):
    """``"not-a-date"`` não pode virar NaN nem uma duração plausível."""
    d = bancada.resumo("reset-lixo")
    valor = d["nextResetSeconds"]
    assert valor in (None, {"$null": True}, ""), (
        "um reset_at ilegível não é um reset futuro; nextResetSeconds deveria ser "
        "nulo, mas veio %r" % (valor,)
    )
    assert not (isinstance(valor, dict) and valor.get("$nan")), (
        "nextResetSeconds virou NaN com um reset_at ilegível"
    )


def test_iso_com_offset_e_aplicado(bancada):
    """``...T...-03:00`` é ISO válido: o offset desloca o instante.

    O reset foi escrito 1800s à frente em -03:00; ignorar o offset daria 12600s
    de erro (3h), então este teste distingue "aplicou" de "cortou o sufixo".
    """
    d = bancada.resumo("iso-com-offset")
    assert d["nextResetSeconds"] == 1800, (
        "reset_at com offset -03:00 a 1800s de distância deveria dar 1800; veio %r. "
        "Ignorar o offset desloca o resultado em 3 horas."
        % (d["nextResetSeconds"],)
    )


# --------------------------------------------------------------------------- #
# Item 5 — a formatação é a de T23 (composta pela própria resetParts)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("caso,secs", [
    ("t23-1min", 60),
    ("t23-1h1min", 3661),
    ("t23-3h", RESET_3H),
    ("t23-4d56min", 4 * 86400 + 56 * 60),
])
def test_o_tempo_do_resumo_e_o_de_t23(bancada, caso, secs):
    """``nextResetRelative`` tem de ser EXATAMENTE o ``relative`` de T23.

    Comparação entre duas funções públicas, não contra um literal: se T23 mudar
    (e o dono já mudou essa convenção uma vez), este teste continua correto e o
    resumo que divergir é acusado.
    """
    esperado = bancada.t23.get("summary/%s" % caso)
    assert esperado is not None, (
        "[%s] não foi possível compor com T23: resetParts ausente ou lançou "
        "(papel=%r)" % (caso, bancada.roles.get("resetParts"))
    )
    assert esperado != "", f"[{caso}] resetParts devolveu relativo vazio para {secs}s"
    d = bancada.resumo(caso)
    assert d["nextResetRelative"] == esperado, (
        "[%s] contrato item 5: o resumo usa a formatação de T23. O valor de T23 "
        "para %ss é %r; o resumo escreveu %r."
        % (caso, secs, esperado, d["nextResetRelative"])
    )


def test_next_reset_seconds_e_o_mesmo_numero_que_a_formacao_descreve(bancada):
    """Os dois campos não podem divergir: o texto descreve aquele número.

    Não se exige qual formato, só que o par seja coerente — um relativo de
    "1h 1min" com 7200 segundos seria um bug de arredondamento.
    """
    d = bancada.resumo("t23-1h1min")
    seg = d["nextResetSeconds"]
    assert seg == 3661, "nextResetSeconds deveria ser 3661; veio %r" % (seg,)
    assert d["nextResetRelative"] == bancada.t23.get("summary/t23-1h1min"), (
        "o relativo (%r) divergiu de T23 (%r) para 3661s"
        % (d["nextResetRelative"], bancada.t23.get("summary/t23-1h1min"))
    )


# --------------------------------------------------------------------------- #
# Item 4 — zero estados são OMITIDOS
# --------------------------------------------------------------------------- #


def test_sem_nada_a_dizer_o_array_e_vazio(bancada):
    """Nada esgotado e nada acima de 80% e nenhum reset futuro → ``[]``.

    "array vazio = nada a dizer" (semântica obrigatória). Não pode vir
    ``["0 quotas exhausted"]`` nem ``[""]``.
    """
    for caso in ("nada-a-dizer", "nada-a-dizer-reset-nulo"):
        segs = bancada.segmentos(caso)
        assert segs == [], (
            "[%s] zero estados devem ser OMITIDOS, não escritos: veio %r"
            % (caso, segs)
        )


def test_nunca_aparece_contagem_zero_em_texto(bancada):
    """Negativo: nenhum segmento pode conter um "0" de contagem.

    Percorre todos os casos de segmento do corpus; qualquer "0 quota", "0 cotas",
    "0 limites" ou "0 esgotados" é falha, em qualquer idioma carregado.
    """
    padrao = re.compile(r"\b0\s+(quota|cota|limite|provider|provedor)s?\b",
                        re.IGNORECASE)
    ofensas = []
    for chave, (tipo, dados) in bancada.casos.items():
        role, caso = chave.split("/", 1)
        if role != "segments" or not isinstance(dados, dict):
            continue
        for s in dados.get("items", []):
            if isinstance(s, str) and padrao.search(s):
                ofensas.append("[%s] %r" % (caso, s))
    assert not ofensas, (
        "contrato item 4: um segmento de valor zero nunca aparece. Ofensas:\n"
        + "\n".join(ofensas)
    )


def test_cota_esgotada_sem_reset_futuro_mantem_so_o_segmento_de_contagem(bancada):
    """Omitir um segmento não pode omitir o outro."""
    segs = bancada.segmentos("reset-nulo-e-passado-apenas")
    assert len(segs) == 1, (
        "com uma cota esgotada e nenhum reset futuro, sobra 1 segmento (a "
        "contagem); veio %r" % (segs,)
    )


# --------------------------------------------------------------------------- #
# Singular / plural
# --------------------------------------------------------------------------- #


def _sem_digitos(s: str) -> str:
    return re.sub(r"[0-9]+", "#", s)


def test_singular_e_plural_diferem_para_esgotados(bancada):
    """1 cota e 2 cotas: o texto muda em MAIS que o dígito.

    Exigir só "são diferentes" passa em "1 quotas exhausted" vs
    "2 quotas exhausted" — exatamente o defeito que a SPEC diz ter sido medido e
    corrigido. Tirando os dígitos, o resto das duas frases tem de continuar
    diferente: é o que prova que a PALAVRA flexiona. Assim o teste não fixa a
    tradução ("quota"/"cota"/"limite" passam igual), só o plural.
    """
    uma = bancada.segmentos("seg-uma-esgotada")
    duas = bancada.segmentos("seg-duas-esgotadas")
    assert len(uma) >= 1 and len(duas) >= 1, (uma, duas)
    assert uma[0] != duas[0], (
        "1 cota e 2 cotas precisam de textos diferentes. Ambos vieram %r." % (uma[0],)
    )
    assert _sem_digitos(uma[0]) != _sem_digitos(duas[0]), (
        "o texto de 1 cota (%r) e o de 2 cotas (%r) diferem SÓ no número: a "
        "palavra não flexiona, então o usuário lê \"1 quotas exhausted\". É o "
        "defeito que o contrato nomeia. Chaves separadas de singular e plural são "
        "o que falta." % (uma[0], duas[0])
    )
    assert "1" in uma[0], (
        "o segmento de uma cota deveria carregar o número 1 (o número não pode "
        "estar fixo dentro de uma string plural): %r" % (uma[0],)
    )
    assert "2" in duas[0], (
        "o segmento de duas cotas deveria carregar o número 2: %r" % (duas[0],)
    )


def test_singular_e_plural_diferem_para_acima_de_80(bancada):
    uma = bancada.segmentos("seg-uma-alta")
    duas = bancada.segmentos("seg-duas-altas")
    assert uma[0] != duas[0], (
        "1 cota acima de 80%% e 2 cotas acima de 80%% não podem usar o mesmo "
        "texto; ambos vieram %r" % (uma[0],)
    )
    assert _sem_digitos(uma[0]) != _sem_digitos(duas[0]), (
        "os textos de 1 e de 2 cotas acima de 80%% (%r e %r) diferem só no "
        "número: a palavra não flexiona" % (uma[0], duas[0])
    )
    assert "1" in uma[0] and "2" in duas[0], (uma[0], duas[0])


def test_os_dois_estados_nao_usam_o_mesmo_texto(bancada):
    """Esgotado e "acima de 80%" são estados distintos, não sinônimos."""
    segs = bancada.segmentos("seg-misto")
    assert len(segs) == 3, (
        "1 esgotada + 2 acima de 80%% + reset futuro = 3 segmentos; veio %r" % (segs,)
    )
    assert segs[0] != segs[1], (
        "o segmento de esgotados (%r) e o de acima de 80%% (%r) são iguais — os "
        "dois estados deixariam de ser distinguíveis" % (segs[0], segs[1])
    )


def test_a_ordem_segue_o_exemplo_do_objetivo(bancada):
    """O objetivo dá a ordem: esgotados · acima de 80% · próximo reset.

    Não se fixa o separador (o contrato não o declara); fixa-se a ORDEM, que o
    exemplo assinado declara.
    """
    segs = bancada.segmentos("seg-misto")
    # O primeiro segmento é o de esgotados (contém "1"), o segundo o de >
    # 80% (contém "2"); o terceiro é o reset. Se a ordem invertesse, o texto
    # diria "2 quotas exhausted · 1 quota above 80%" — invertido.
    assert bancada.resumo("misto-summary")["exhausted"] == 1, (
        "o resumo do modelo misto deveria ter 1 cotas esgotada; veio %r"
        % (bancada.resumo("misto-summary"),)
    )
    assert bancada.resumo("misto-summary")["high"] == 2, (
        "o resumo do modelo misto deveria ter 2 cotas acima de 80%%; veio %r"
        % (bancada.resumo("misto-summary"),)
    )
    primeira_contagem = segs[0]
    segunda_contagem = segs[1]
    assert "1" in primeira_contagem and "2" in segunda_contagem, (
        "a ordem do exemplo é esgotados, depois acima de 80%%; os dois primeiros "
        "segmentos vieram %r, %r" % (primeira_contagem, segunda_contagem)
    )


# --------------------------------------------------------------------------- #
# countableQuotas
# --------------------------------------------------------------------------- #


def test_countable_quotas_devolve_os_campos_do_contrato(bancada):
    """Cada item é ``{ providerId, label, metric }`` — com o metric completo."""
    ital = bancada.cotas("countable-campos")
    assert len(ital) == 2, "o provider tem 2 métricas; countableQuotas veio %r" % (ital,)
    for it in ital:
        assert "providerId" in it and it["providerId"] == "a", (
            "cada cota precisa do providerId; veio %r" % (it,)
        )
        assert "label" in it and isinstance(it["label"], str), (
            "cada cota precisa do label da métrica; veio %r" % (it,)
        )
        m = it.get("metric")
        assert isinstance(m, dict), (
            "cada cota precisa carregar a métrica (para o reset e a severidade); "
            "veio %r" % (it,)
        )
        assert m.get("label") == it["label"], (
            "o label da cota e o label da métrica divergem: %r" % (it,)
        )
        assert "percent" in m, "a métrica da cota perdeu o percent: %r" % (m,)
    assert [i["label"] for i in ital] == ["L1", "L2"], (
        "a ordem das cotas deve seguir a ordem do relatório; veio %r"
        % ([i["label"] for i in ital],)
    )


def test_countable_quotas_exclui_provider_em_erro(bancada):
    cotas = bancada.cotas("countable-provider-em-erro")
    assert [c["providerId"] for c in cotas] == ["b"], (
        "countableQuotas não pode incluir cota de provider em erro; veio %r" % (cotas,)
    )


def test_countable_quotas_deduplica_a_mesma_janela(bancada):
    cotas = bancada.cotas("countable-dedup")
    assert len(cotas) == 1, (
        "a mesma janela repetida é UMA cota contável; veio %r" % (cotas,)
    )


def test_countable_quotas_com_modelo_nulo_devolve_array_vazio(bancada):
    assert bancada.cotas("countable-modelo-nulo") == [], (
        "model nulo não pode quebrar countableQuotas nem devolver null"
    )


def test_total_do_resumo_conta_as_cotas_contaveis(bancada):
    """``total`` é o número de cotas contáveis do modelo.

    A tabela de cenários da SPEC tem uma coluna "cotas" que, em todas as sete
    linhas, é o tamanho de ``countableQuotas(model)``. O contrato não define
    ``total`` em prosa (ver AMBIGUIDADES 3); a asserção usa essa relação, que é a
    única leitura compatível com a tabela.
    """
    pares = [("tres-altas-no-mesmo-provider", "countable-tres-altas"),
             ("mesma-janela-repetida", "countable-mesma-janela"),
             ("provider-em-erro-com-cota-estourada", "countable-erro")]
    for resumo_caso, cotas_caso in pares:
        d = bancada.resumo(resumo_caso)
        cotas = bancada.cotas(cotas_caso)
        assert d["total"] == len(cotas), (
            "[%s] total=%r mas countableQuotas devolve %s cotas (%r). A tabela da "
            "SPEC iguala as duas colunas em todos os cenários."
            % (resumo_caso, d["total"], len(cotas), cotas)
        )


# --------------------------------------------------------------------------- #
# Entradas degeneradas
# --------------------------------------------------------------------------- #


def test_modelo_nulo_nao_quebra(bancada):
    d = bancada.resumo("modelo-nulo")
    assert (d["exhausted"], d["high"]) == (0, 0), (
        "model nulo: resumo deveria ser zero; veio %r" % (d,)
    )
    assert bancada.segmentos("nada-a-dizer") == []


def test_modelo_sem_all_nao_quebra(bancada):
    """Sem ``all`` não há provider algum: zero cotas, sem lançar."""
    d = bancada.resumo("modelo-sem-all")
    assert (d["exhausted"], d["high"]) == (0, 0), (
        "modelo sem a chave 'all' não pode inventar cotas; veio %r" % (d,)
    )


def test_provider_sem_metrics_nao_quebra(bancada):
    d = bancada.resumo("provider-sem-metrics")
    assert (d["exhausted"], d["high"]) == (0, 0), (
        "provider sem o array de métricas: zero cotas; veio %r" % (d,)
    )


# --------------------------------------------------------------------------- #
# Localização dos segmentos ("já traduzidas")
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def bancada_pt() -> Bancada:
    """Mesma sonda, com o idioma da UI em pt_BR."""
    return Bancada(_rodar({
        "T27_CASES": json.dumps([
            c for c in CASES
            if c["name"] in ("seg-uma-esgotada", "seg-duas-esgotadas",
                             "seg-uma-alta", "seg-misto")
        ], ensure_ascii=False),
        "T27_LANGUAGE": "pt_BR",
        "T27_RENDER_MODEL": json.dumps(model([])),
    }))


def test_os_segmentos_chegam_traduzidos(bancada, bancada_pt):
    """Item "array de strings JÁ TRADUZIDAS": com pt_BR, o texto não é o inglês.

    O contrato não fixa a palavra; fixa que o texto é traduzido. Um resumo com
    string inglesa fixa no código falha aqui, sem que a suíte tenha de escolher
    entre "limite", "cota" ou qualquer outra tradução.
    """
    caso = "seg-duas-esgotadas"
    en = bancada.segmentos(caso)[0]
    pt = bancada_pt.segmentos(caso)[0]
    assert pt != en, (
        "com language=pt_BR o segmento de esgotados continuou em inglês (%r). O "
        "contrato diz 'array de strings já traduzidas'." % (en,)
    )
    assert "2" in pt, "o segmento traduzido perdeu o número 2: %r" % (pt,)
    # Singular e plural continuam distintos DEPOIS de traduzir — o número não
    # pode ter ficado dentro de uma string fixa no catálogo.
    pt_uma = bancada_pt.segmentos("seg-uma-esgotada")[0]
    assert pt_uma != pt, (
        "depois de traduzir, singular (%r) e plural (%r) ficaram iguais"
        % (pt_uma, pt)
    )
    assert "1" in pt_uma
    assert _sem_digitos(pt_uma) != _sem_digitos(pt), (
        "em pt_BR, o singular (%r) e o plural (%r) diferem só no número"
        % (pt_uma, pt)
    )


def test_o_segmento_de_acima_de_80_tambem_e_traduzido(bancada, bancada_pt):
    en = bancada.segmentos("seg-uma-alta")[0]
    pt = bancada_pt.segmentos("seg-uma-alta")[0]
    assert pt != en, (
        "o segmento 'acima de 80%%' não foi traduzido: %r em ambos os idiomas" % (en,)
    )


# --------------------------------------------------------------------------- #
# Renderização — a linha existe no topo e não aparece quando vazia
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def render_loud() -> tuple[Bancada, dict]:
    """Modelo barulhento, montado no topo do popout, com resets relativos a AGORA.

    Os resets são relativos ao instante do processo para que "próximo reset"
    exista de fato; as CONTAGENS (que o teste compara) não dependem do relógio.
    """
    agora = int(datetime.now(timezone.utc).timestamp())
    a = provider("a", [metric("Session (5h)", 100, iso(15240, agora)),
                       metric("Weekly (7d)", 90, iso(200000, agora)),
                       metric("Extra", 50, None)])
    b = provider("b", [metric("Premium", 100, iso(4200, agora))])
    e = provider("e", [metric("Session (5h)", 150, None)], status="error")
    m = {"schema": 1, "primary": a, "secondary": [b, e], "all": [a, b, e],
         "total_providers": 3, "with_issues": 1}
    banc = Bancada(_rodar({"T27_CASES": "[]",
                           "T27_RENDER_MODEL": json.dumps(m, ensure_ascii=False),
                           "T27_RENDER_NOW": str(agora)}))
    return banc, m


def test_a_view_monta_e_a_linha_de_resumo_e_desenhada(render_loud):
    """O objetivo é "uma linha no topo"; ela tem de chegar a um ``Text`` visível."""
    banc, m = render_loud
    assert banc.view_present, "a view não montou; erros=%s" % banc.erros
    esperado = banc.render_segments
    assert isinstance(esperado, dict) and esperado["$len"] >= 2, (
        "o modelo do teste deveria produzir pelo menos 2 segmentos; veio %r"
        % (esperado,)
    )
    textos = " ".join(banc.render_texts)
    for seg in esperado["items"]:
        if seg.startswith("next reset"):
            # A duração muda entre a chamada e o desenho (relógio); compara-se
            # o prefixo do segmento, não o número.
            prefixo = seg.split(" in ")[0]
            assert prefixo in textos, (
                "o segmento de reset (%r) não aparece na tela; textos=%r"
                % (seg, banc.render_texts)
            )
        else:
            assert seg in textos, (
                "o segmento de contagem %r não chegou a um Text visível; "
                "textos renderizados=%r" % (seg, banc.render_texts)
            )


def test_a_linha_de_resumo_fica_antes_das_barras(render_loud):
    """"No topo": o texto do resumo vem antes do primeiro provider desenhado."""
    banc, m = render_loud
    if not banc.render_segments or banc.render_segments["$len"] == 0:
        pytest.skip("sem segmentos neste modelo")
    primeiro = banc.render_segments["items"][0]
    # Medido nesta base: o resumo é desenhado como UMA string com " · " entre os
    # segmentos, não um Text por segmento. Procura-se por CONTEÚDO: o primeiro
    # segmento presente em algum texto.
    indices_resumo = [i for i, t in enumerate(banc.render_texts) if primeiro in t]
    assert indices_resumo, (
        "o primeiro segmento (%r) não aparece em nenhum texto desenhado: %r"
        % (primeiro, banc.render_texts)
    )
    i_resumo = min(indices_resumo)
    nomes = [p["display_name"] for p in m["all"]]
    indices = [i for i, t in enumerate(banc.render_texts) if t in nomes]
    assert indices, "nenhum provider foi desenhado: %r" % (banc.render_texts,)
    assert i_resumo < min(indices), (
        "o resumo (índice %s) aparece DEPOIS do primeiro provider (índice %s); o "
        "objetivo diz 'uma linha no topo ... sem percorrer as barras'"
        % (i_resumo, min(indices))
    )


def test_sem_nada_a_dizer_nenhuma_linha_de_resumo_e_desenhada():
    """Item 4 no RENDER, não só na função: nada de "0 esgotados" na tela."""
    pr = provider("a", [metric("Session (5h)", 12, None)])
    m = {"schema": 1, "primary": pr, "secondary": [], "all": [pr],
         "total_providers": 1, "with_issues": 0}
    banc = Bancada(_rodar({"T27_CASES": "[]",
                           "T27_RENDER_MODEL": json.dumps(m, ensure_ascii=False)}))
    assert banc.view_present, "a view não montou com um modelo sem nada a dizer"
    assert banc.render_segments == {"$len": 0, "items": []}, (
        "o modelo não tem cota esgotada, nem acima de 80%%, nem reset futuro: os "
        "segmentos deveriam ser vazios; vieram %r" % (banc.render_segments,)
    )
    ofensas = [t for t in banc.render_texts
               if re.search(r"\b0\b.{0,20}(quota|cota|limite|exhaust|esgotad)", t, re.I)]
    assert not ofensas, (
        "item 4: o segmento de valor zero é omitido, não escrito. A tela mostra %r"
        % (ofensas,)
    )
    # Só a FRASE DE CONTAGEM do resumo: "12% of the quota" é o detalhe de uma
    # métrica e não a linha de resumo; "(N) quota(s) exhausted / above X%"
    # (e as formas traduzidas) é o que não pode existir.
    frase_resumo = re.compile(
        r"(quota|cota|limite)s?\s+(exhaust|esgotad|above|acima)", re.IGNORECASE)
    semantica = [t for t in banc.render_texts if frase_resumo.search(t)]
    assert not semantica, (
        "sem nada a dizer, nenhuma linha de resumo deveria ser desenhada; "
        "textos com a frase de contagem do resumo na tela: %r" % (semantica,)
    )


# --------------------------------------------------------------------------- #
# AMBIGUIDADES do contrato (D5) — o que ficou sem oráculo
# --------------------------------------------------------------------------- #

AMBIGUIDADES = """
1. `total` NÃO É DEFINIDO EM PROSA. A interface lista o campo, mas o contrato
   descreve só `exhausted`, `high` e o reset. A única leitura compatível com a
   tabela de cenários da SPEC (coluna "cotas") é `total ==
   len(countableQuotas(model))`, e é isso que
   `test_total_do_resumo_conta_as_cotas_contaveis` afirma. Se o dono quis dizer
   "providers com alguma cota" ou "métricas totais, deduplicadas ou não", o
   número muda e o teste acusa. Nenhum outro teste depende de `total`.

2. `reset_at` DE UMA MÉTRICA SEM `percent` CONCORRE AO PRÓXIMO RESET. O item 3
   diz "a menor diferença positiva entre agora e os `reset_at`", sem exigir
   percent; medido, uma métrica com `percent: null` e reset futuro VENCE o
   próximo reset. A suíte NÃO afirma nem nega isso (seria inventar oráculo): o
   caso existe no corpus como diagnóstico. Se a intenção for só cotas
   comparáveis, este é o ponto a decidir.

3. `reset_at` DE PROVIDER EM ERRO. "Contribui ZERO cotas" fala de cotas, não de
   resets. Medido: o reset de um provider em erro NÃO concorre ao próximo reset
   (ele é ignorado junto com o provider). A suíte só afirma o caso em que não há
   ambiguidade — todos os providers em erro → zero segmentos — e deixa o caso
   misto fora das asserções.

4. `status` FORA DE "error"/"ready". O contrato fixa `status === "error"` →
   zero. Não diz o que fazer com `status` ausente ou com "ERROR" em maiúsculas.
   Medido: `status` ausente CONTA e "ERROR" maiúsculo também (a comparação é
   literal). Nenhum dos dois é asserido — decidir se a comparação deve ser
   normalizada é do dono.

5. `percent` COMO STRING. Medido: `percent: "100"` (string) conta como
   esgotado. O contrato fala de `percent (null ou 0..100+)`, isto é, número; não
   define coerção. Sem asserção.

6. SINGULAR/PLURAL É VERIFICADO POR RELAÇÃO, NÃO POR PALAVRA. O contrato exige
   "singular correto" e um segmento "já traduzido", mas não fixa o vocabulário.
   A suíte exige: (a) os textos de 1 e de 2 cotas são DIFERENTES, (b) carregam o
   número, (c) em pt_BR diferem do inglês. Um catálogo que escrevesse
   "1 cotas" com o número substituído passaria — porque distinguir "cotas" de
   "cota" exigiria fixar a tradução, que o contrato não dá.

7. O SEPARADOR DA LINHA. O exemplo do objetivo usa " · ", mas o contrato só
   define o ARRAY de segmentos. A suíte nunca exige " · " no array (o array é de
   segmentos, não de uma linha única) e, no render, verifica a presença de cada
   segmento em vez da string concatenada. A ORDEM (esgotados, acima de 80%,
   reset) é asserida porque o exemplo a declara.

8. O TEXTO DO RESET NO RENDER É COMPARADO POR PREFIXO. `operationalSummarySegments`
   recebe `nowEpoch`; a linha desenhada usa o relógio do processo. Medido: 1h
   10min na função e 1h 9min na tela, no mesmo processo. Comparar a duração
   exata entre as duas superfícies seria um teste flaky por construção, então o
   render só confirma o prefixo ("next reset in") e o par
   seconds/relative é verificado na função pura.

9. `high` CONTA A PARTIR DE QUANTAS CASAS? O contrato diz `> 80` e `< 100`. A
   suíte assere 80.1 e 99.9 (dentro) e 80 e 100 (fora), sem arredondar, na
   leitura literal. Se a implementação arredondasse o percent antes de comparar,
   99.9 viraria 100 e mudaria de faixa — o teste acusaria, e a divergência seria
   sobre arredondamento, não sobre a intenção.

10. "PRÓXIMO RESET EM 3H" DO OBJETIVO x A FORMA DE T23. O exemplo do objetivo
    escreve "em 3h", mas o item 5 manda usar T23, cuja convenção (assinada) é
    "3h 22min"/"1h 0min". A suíte segue o item 5 e compara com a saída REAL de
    `resetParts` — medido: 10800s → "3h 0min", não "3h". Se o exemplo do
    objetivo for a fonte de verdade para o formato, o teste de T23 é o que
    precisa mudar, não o resumo.

11. O QUE É UMA "JANELA REPETIDA". A chave de dedup declarada é
    `(provider, label)`; a suíte verifica que dois labels iguais no mesmo
    provider somam 1 e que o mesmo label em dois providers soma 2. NÃO verifica
    se duas métricas com labels diferentes mas `window_secs` igual são "a mesma
    janela" — o contrato diz explicitamente que são janelas distintas, e o caso
    `mesmo-percentual-labels-diferentes` cobre a forma segura dessa leitura.
"""
