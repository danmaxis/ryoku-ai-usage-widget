# -*- coding: utf-8 -*-
"""Behavior tests for T23 — one single convention for reset time.

Gerado em contexto isolado (D5) — sem acesso à implementação.
Base: SPEC rodada 3, tarefa T23.

Contract transcribed (the block signed by the owner):

  * Every reset duration uses the SAME shape. Before: ``3h 22m``, ``3H18``,
    ``4D56`` and ``5D`` coexisted — four shapes for one datum.
  * Units always abbreviated, lowercase, with a space between the two groups:
    ``h``, ``d``, ``min``.
  * At most two units: ``3d 4h``, never ``3d 4h 12min``.
  * Under one minute → ``agora`` (``now`` in the English UI).
  * The exact clock time comes AFTER the relative part, separated by `` · ``,
    and is omitted when it adds nothing (e.g. a reset more than 7 days out).
  * Localized formatting (T22): ``Hoje/Amanhã`` translate, the hour pattern
    follows the locale.
  * Done-criterion: a PURE formatting function with boundary tests
    (0s, 59s, 59min, 1h, 23h59, 1d, 7d, 30d).

The public interface exercised here (as decided in the task block):

    resetParts(resetAt, nowEpoch) -> object

    resetAt  : ISO-8601 string, or null / "" / garbage
    nowEpoch : number, seconds since the epoch (may be fractional)

    valid   -> { valid: true, seconds, days, hours, minutes, relative }
    invalid -> { valid: false }

    seconds          = max(0, round(resetAt - nowEpoch))     (never negative)
    days             = floor(seconds / 86400)
    hours            = floor((seconds % 86400) / 3600)
    minutes          = floor((seconds % 3600) / 60)
    relative:
        seconds <   60  -> "now"
        seconds < 3600  -> "<M>min"
        seconds < 86400 -> "<H>h <M>min"   (ALWAYS both parts)
        seconds >=86400 -> "<D>d <H>h"     (both parts; " <H>h" omitted iff hours == 0)

How behavior is observed without a visual host
----------------------------------------------
``quickshell`` OFFLINE (``QT_QPA_PLATFORM=offscreen``) mounts the view and CALLS
the function with inputs chosen here, dumping the raw result
(``tests/qml/t23_reset_parts_harness.qml``). ``content/Widget.qml`` is never
read, and no assertion is derived from it: the oracle is the contract above,
transcribed independently into ``_relativo_esperado`` and into the property
checks. The two texts never share code.

Why ``relative`` is judged against a literal oracle
---------------------------------------------------
Unlike T19 ("cut at a word" had to be tested as a property because the contract
said "something like"), T23's contract is literal about the string: ``now``,
``<M>min``, ``<H>h <M>min``, ``<D>d <H>h``. So the boundaries are compared
literally; the sweep adds structural properties (lowercase, at most two units,
canonical decomposition) for values where the branch matters less.

What is NOT tested, and why (see ``AMBIGUIDADES`` at the end)
------------------------------------------------------------
The exact clock time (``Hoje, 18:33`` / ``Amanhã, 09:10`` / ``12/nov, 14:00``)
is localized, while ``resetParts`` is declared locale-free and ``tr()``-free, so
its localization cannot be exercised through this function. Only the NEGATIVE
claim is pinned: the locale-free part does not smuggle the clock suffix in.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Artifact locations (the content of Widget.qml is never read)
# --------------------------------------------------------------------------- #

TEST_DIR = Path(__file__).resolve().parent            # <repo>/ai-usage/tests
#: Environment override: EXCLUSIVE to falsifiability checks of this suite
#: (point it at a control tree). The production path does not set it.
PLUGIN_DIR = Path(os.environ.get("T23_PLUGIN_DIR", TEST_DIR.parent))
HARNESS = TEST_DIR / "qml" / "t23_reset_parts_harness.qml"

_QUICK = shutil.which("quickshell") or shutil.which("qs")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

pytestmark = pytest.mark.skipif(
    _QUICK is None,
    reason="quickshell ausente: a view QML e a função pura não podem ser exercitadas",
)

#: The one accepted name (the interface above). The spelling probes exist only
#: so the failure message says WHAT was found; they never substitute for it.
NOME_CONTRATO = "resetParts"

#: The function T23 replaces — finding it without ``resetParts`` is the exact
#: "not implemented yet" signature and must be named in the failure.
NOME_ANTIGO = "cooldown"

#: Reference instant for every relative case. All epochs derive from it, so no
#: assertion depends on the machine clock.
RESET_ISO = "2026-10-28T18:33:00Z"
RESET_EPOCH = int(datetime(2026, 10, 28, 18, 33, 0, tzinfo=timezone.utc).timestamp())

MINUTO = 60
HORA = 3600
DIA = 86400

#: The ONLY allowed shapes for ``relative``. Anything else — ``3H18``, ``4D56``,
#: ``3h 22m``, ``3h22min``, ``3d 4h 12min`` — fails to match. ``1h 0min`` and
#: ``1min`` are legal, so the "always both parts" rule is not smuggled in here.
_UNIDADES_OK = re.compile(r"^(?:now|\d+min|\d+h \d+min|\d+d(?: \d+h)?)$")


# --------------------------------------------------------------------------- #
# Artifacts
# --------------------------------------------------------------------------- #


def _artefatos() -> None:
    assert HARNESS.is_file(), f"harness QML ausente: {HARNESS}"
    assert (PLUGIN_DIR / "content" / "Widget.qml").is_file(), "content/Widget.qml ausente"


def test_artefatos_sob_teste_existem():
    """Fail fast if harness or view vanished (revert-and-test must not SKIP)."""
    _artefatos()


# --------------------------------------------------------------------------- #
# Transport: run the harness once, parse its records
# --------------------------------------------------------------------------- #


def _limpo(stdout: str) -> list[str]:
    """quickshell log lines, without ANSI escapes and without the ``qml:`` tag."""
    saida: list[str] = []
    for linha in _ANSI.sub("", stdout).splitlines():
        if " qml: " in linha:
            linha = linha.split(" qml: ", 1)[1]
        linha = linha.strip()
        if linha:
            saida.append(linha)
    return saida


class Caso:
    """One call of the pure function: what it returned, uninterpreted."""

    def __init__(self, nome: str, tipo: str, normalizado: str, bruto: str):
        self.nome = nome
        self.tipo = tipo
        self.normalizado = normalizado
        self.bruto = bruto

    @property
    def dados(self) -> dict:
        try:
            valor = json.loads(self.normalizado)
        except json.JSONDecodeError:            # pragma: no cover - diagnostic
            pytest.fail(f"[{self.nome}] retorno não é JSON legível: {self.normalizado!r}")
        assert isinstance(valor, dict), (
            f"[{self.nome}] a função deve devolver um OBJETO; devolveu {self.tipo} "
            f"{self.bruto!r}"
        )
        return valor

    def __repr__(self) -> str:
        return f"<Caso {self.nome}: {self.bruto}>"


class Bancada:
    def __init__(self, registros: list[str]):
        self.registros = registros
        self.nome_fn = None
        self.estado_fn = None
        self.host = None
        self.no_raiz = None
        self.sondagem: dict[str, bool] = {}
        self.casos: dict[str, Caso] = {}
        self.excecoes: dict[str, str] = {}
        for r in registros:
            if r.startswith("FN_NAME|"):
                _tag, nome, estado = r.split("|", 2)
                self.nome_fn, self.estado_fn = nome, estado
            elif r.startswith("FN_PROBE|"):
                _tag, nome, presente = r.split("|", 2)
                self.sondagem[nome] = presente == "true"
            elif r.startswith("FN_HOST|"):
                self.host = r.split("|", 1)[1]
            elif r.startswith("FN_ON_ROOT|"):
                self.no_raiz = r.split("|", 1)[1] == "true"
            elif r.startswith("FN_THROW|"):
                _tag, nome, msg = r.split("|", 2)
                self.excecoes[nome] = msg
            elif r.startswith("FN|"):
                _tag, nome, tipo, norm, bruto = r.split("|", 4)
                self.casos[nome] = Caso(nome, tipo, norm, bruto)
        self.view_present = any(r == "VIEW_PRESENT|true" for r in registros)
        self.terminou = any(r.startswith("END|") for r in registros)

    def __call__(self, nome: str) -> dict:
        _exigir_funcao(self)
        assert nome not in self.excecoes, (
            f"[{nome}] {NOME_CONTRATO} lançou exceção: {self.excecoes[nome]!r}. "
            "Entrada lixo (null / \"\" / texto) precisa devolver {valid:false}, "
            "não lançar."
        )
        assert nome in self.casos, (
            f"[{nome}] caso não executado; registros={self.registros}"
        )
        return self.casos[nome].dados

    def __repr__(self) -> str:
        return (f"<Bancada fn={self.nome_fn!r} host={self.host!r} "
                f"casos={sorted(self.casos)}>")


def _exigir_funcao(b: Bancada) -> None:
    """The anchor assertion, with a message that names the REAL state.

    Without it every test would fail as "NoneType is not callable" and the
    report would not say "there is no pure reset-time function" — the very
    defect T23 exists to remove.
    """
    assert b.view_present, "a view não montou; nada a exercitar"
    encontrados = [n for n, ok in b.sondagem.items() if ok] or "nenhum"
    assert b.estado_fn == "present", (
        f"não há função pura {NOME_CONTRATO}(resetAt, nowEpoch) alcançável na view "
        f"montada.\n  encontrados na sondagem: {encontrados}"
        f"\n  antiga {NOME_ANTIGO!r} presente: {b.sondagem.get(NOME_ANTIGO, 'não sondada')}"
        f"\n  o contrato de T23 exige {NOME_CONTRATO} — o formato antigo de reset "
        "(3H18 / 4D56 / 3h 22m) não serve."
    )


def _rodar(casos: list[dict], tmp: Path, *, rotulo: str) -> Bancada:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("WAYLAND_DISPLAY", None)
    env["T23_PLUG_DIR"] = str(PLUGIN_DIR)
    env["T23_STATE_DIR"] = str(tmp / "state")
    env["T23_FN_CASES"] = json.dumps(casos, ensure_ascii=False)
    env["T23_SETTLE_MS"] = "1200"

    try:
        proc = subprocess.run(
            [_QUICK, "-p", str(HARNESS)],
            capture_output=True, text=True, env=env, timeout=180,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"[{rotulo}] o harness não terminou em 180s — view que não monta ou "
            f"{NOME_CONTRATO} que não retorna (laço)."
        )

    b = Bancada(_limpo(proc.stdout + proc.stderr))
    assert b.terminou, (
        f"[{rotulo}] o harness não chegou ao fim; rc={proc.returncode}\n"
        f"registros={b.registros}\nstderr(tail)={proc.stderr[-800:]}"
    )
    return b


# --------------------------------------------------------------------------- #
# The contract, transcribed as an INDEPENDENT oracle (never a copy of code)
# --------------------------------------------------------------------------- #


def _relativo_esperado(segundos: int) -> str:
    """``relative`` straight from the interface's four branches."""
    if segundos < MINUTO:
        return "now"
    if segundos < HORA:
        return f"{segundos // MINUTO}min"
    if segundos < DIA:
        return f"{segundos // HORA}h {(segundos % HORA) // MINUTO}min"
    dias = segundos // DIA
    horas = (segundos % DIA) // HORA
    return f"{dias}d" + (f" {horas}h" if horas else "")


def _decomposicao_esperada(segundos: int) -> tuple[int, int, int]:
    return segundos // DIA, (segundos % DIA) // HORA, (segundos % HORA) // MINUTO


def _caso(nome: str, segundos: float) -> dict:
    """A case stated as "the reset happens ``segundos`` from now".

    The epoch arithmetic lives here, once, so no test hand-computes a timestamp.
    ``nowEpoch`` is fractional whenever ``segundos`` is.
    """
    return {"name": nome, "args": [RESET_ISO, RESET_EPOCH - segundos]}


#: The done-criterion boundaries plus their two neighbours in each branch.
#: ``segundos`` is exact, so ``seconds`` must come back equal to it and the
#: branch under test is unambiguous.
FRONTEIRAS: list[tuple[str, int]] = [
    ("zero", 0),
    ("59s", 59),
    ("60s", 60),
    ("59min", 59 * MINUTO),
    ("1h", HORA),
    ("23h59", 23 * HORA + 59 * MINUTO),
    ("1d", DIA),
    ("7d", 7 * DIA),
    ("30d", 30 * DIA),
    # exactly hours == 0 at >= 1 day: the "<D>d" shape, no trailing " 0h"
    ("5d-exato", 5 * DIA),
    ("31d-exato", 31 * DIA),
    # hours != 0 at >= 1 day: the "<D>d <H>h" shape
    ("1d12h", DIA + 12 * HORA),
    ("5d3h", 5 * DIA + 3 * HORA),
    # the day branch's own minute boundary, with hours != 0
    ("4d1h", 4 * DIA + HORA),
]

#: The one value where the two authoritative texts DISAGREE (see AMBIGUIDADES
#: item 1): the owner's convention example is ``4d 56min``, while the interface
#: rule "omit `` <H>h`` only when hours == 0" yields ``4d``. It is kept OUT of
#: FRONTEIRAS and FRONTEIRAS is swept by property tests, so the dispute is
#: confined to ONE named test instead of polluting the whole suite.
SEGUNDOS_EXEMPLO_DONO = 4 * DIA + 56 * MINUTO        # 348960 -> "4d 56min"


@pytest.fixture(scope="module")
def fronteiras(tmp_path_factory) -> Bancada:
    _artefatos()
    tmp = tmp_path_factory.mktemp("t23-fronteiras")
    return _rodar([_caso(n, s) for n, s in FRONTEIRAS], tmp, rotulo="fronteiras")


# --------------------------------------------------------------------------- #
# Anchor
# --------------------------------------------------------------------------- #


def test_funcao_pura_de_reset_existe_e_e_alcancavel(fronteiras):
    """The pure function exists, is callable, and lives where the contract says."""
    _exigir_funcao(fronteiras)
    assert fronteiras.host is not None, "o harness não relatou quem hospeda a função"
    assert fronteiras.no_raiz is True, (
        f"{NOME_CONTRATO} foi encontrada, mas não no Item raiz da view "
        f"(host={fronteiras.host!r}). O contrato a declara no Item raiz."
    )


# --------------------------------------------------------------------------- #
# The boundaries, literally
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("nome,segundos", FRONTEIRAS, ids=[n for n, _ in FRONTEIRAS])
def test_fronteira_de_tempo_de_reset_formata_segundo_a_convencao(fronteiras, nome, segundos):
    """Each boundary: ``seconds`` exact, decomposition canonical, ``relative`` literal.

    The sub-assertions are separate so a failure says WHICH part of the contract
    broke. ``relative`` is literal here because the contract is literal here.
    """
    d = fronteiras(nome)
    seg = d.get("seconds")

    assert d.get("valid") is True, (
        f"[{nome}] com {segundos}s no futuro o retorno precisa ser valid:true; "
        f"obtido={d}"
    )
    assert isinstance(seg, int) and not isinstance(seg, bool), (
        f"[{nome}] seconds deve ser INTEIRO; obtido {type(seg).__name__} {seg!r}"
    )
    assert seg == segundos, (
        f"[{nome}] seconds deve ser o arredondamento exato ({segundos}); "
        f"obtido={seg!r}"
    )
    assert (d.get("days"), d.get("hours"), d.get("minutes")) == _decomposicao_esperada(segundos), (
        f"[{nome}] decomposição canônica errada para {segundos}s: esperado "
        f"days/hours/minutes={_decomposicao_esperada(segundos)}, "
        f"obtido={(d.get('days'), d.get('hours'), d.get('minutes'))}"
    )
    assert d.get("relative") == _relativo_esperado(segundos), (
        f"[{nome}] relative fora da convenção para {segundos}s: "
        f"esperado {_relativo_esperado(segundos)!r}, obtido {d.get('relative')!r}"
    )


def test_menos_de_um_minuto_e_now_e_60s_nao_e(fronteiras):
    """Contract 3: under one minute → ``now`` (the English UI wording).

    Both halves matter: 59s is ``now`` AND 60s is not — otherwise "now under a
    minute" and "now always" would be indistinguishable.
    """
    for nome in ("zero", "59s"):
        assert fronteiras(nome)["relative"] == "now", (
            f"[{nome}] abaixo de 1 minuto o relativo deve ser 'now'; "
            f"obtido {fronteiras(nome)['relative']!r}"
        )
    assert fronteiras("60s")["relative"] != "now", (
        "60s é o primeiro segundo de '1min'; devolver 'now' apaga a fronteira"
    )


def test_uma_hora_exata_mostra_as_duas_partes(fronteiras):
    """``<H>h <M>min`` ALWAYS carries both parts — 1h is ``1h 0min``, not ``1h``.

    This is where a "prettify the zero away" implementation drifts from the
    decided convention; the interface says "sempre as DUAS partes" for this
    branch, and says the opposite (omit) for the day branch — so the two
    branches are pinned separately here and in the next test.
    """
    assert fronteiras("1h")["relative"] == "1h 0min", (
        f"1h exato deve ser '1h 0min' (duas partes no ramo < 1 dia); "
        f"obtido {fronteiras('1h')['relative']!r}"
    )
    assert fronteiras("23h59")["relative"] == "23h 59min", (
        f"23h59 deve ser '23h 59min'; obtido {fronteiras('23h59')['relative']!r}"
    )
    assert fronteiras("59min")["relative"] == "59min", (
        f"59min é o teto do ramo de minutos, sem parte de horas; "
        f"obtido {fronteiras('59min')['relative']!r}"
    )


def test_dia_exato_omite_a_parte_de_horas(fronteiras):
    """``>= 1 dia`` omits `` <H>h`` ONLY when ``hours == 0``: 1d, 5d, 7d, 30d.

    The old ``5D`` had no space and an uppercase unit; here the requirement is
    the lowercase ``5d`` — same datum, one convention.
    """
    for nome, esperado in (("1d", "1d"), ("5d-exato", "5d"),
                           ("7d", "7d"), ("30d", "30d"), ("31d-exato", "31d")):
        obtido = fronteiras(nome)["relative"]
        assert obtido == esperado, (
            f"[{nome}] dia exato (hours==0) deve ser {esperado!r}; obtido {obtido!r}"
        )


def test_dia_com_horas_mostra_as_duas_partes_e_nunca_tres_unidades(fronteiras):
    """``<D>d <H>h``: days plus the second unit, and the second unit is the LAST."""
    for nome in ("1d12h", "5d3h", "4d1h"):
        obtido = fronteiras(nome)["relative"]
        assert obtido == _relativo_esperado(dict(FRONTEIRAS)[nome]), (
            f"[{nome}] esperado {_relativo_esperado(dict(FRONTEIRAS)[nome])!r}; "
            f"obtido {obtido!r}"
        )
        tokens = [t for t in obtido.split(" ") if re.search(r"[a-z]", t)]
        assert len(tokens) == 2, (
            f"[{nome}] o ramo de dias com hours != 0 exibe DUAS unidades; "
            f"obtido {obtido!r}"
        )
        assert tokens[0].endswith("d") and tokens[1].endswith("h"), (
            f"[{nome}] as duas unidades do ramo de dias são 'd' e 'h'; "
            f"obtido {obtido!r}"
        )


def test_dia_com_minutos_residuais_nao_perde_a_decomposicao(tmp_path_factory):
    """DISPUTED CASE — days >= 1 with ``hours == 0`` and ``minutes > 0``.

    The two authoritative texts CONTRADICT each other here, so no string oracle
    is invented (see AMBIGUIDADES 1):

      * the owner's convention example lists ``4d 56min``;
      * the interface rule says the ``<D>d`` branch omits `` <H>h`` when
        ``hours == 0``, which prints ``4d`` for the same instant.

    What IS asserted is only what both readings agree on: the arithmetic
    (``seconds`` and the canonical decomposition) and the shape family — two
    units at most, no lost day count, lowercase units. Anything the contract
    clearly forbids (``4D56``, ``4d 0h 56min``, ``4d 56m``) fails here.
    The choice between ``4d`` and ``4d 56min`` is a question for the owner, and
    it is reported in the test's own message rather than decided by the test.
    """
    _artefatos()
    tmp = tmp_path_factory.mktemp("t23-exemplo-dono")
    b = _rodar([_caso("4d56min", SEGUNDOS_EXEMPLO_DONO)], tmp, rotulo="exemplo-dono")
    d = b("4d56min")
    obtido = d.get("relative")

    assert d.get("seconds") == SEGUNDOS_EXEMPLO_DONO, (
        f"âncora: {SEGUNDOS_EXEMPLO_DONO}s deveria ser seconds; obtido {d.get('seconds')!r}"
    )
    assert (d.get("days"), d.get("hours"), d.get("minutes")) == (4, 0, 56), (
        f"âncora: decomposição esperada (4, 0, 56); "
        f"obtido {(d.get('days'), d.get('hours'), d.get('minutes'))}"
    )
    assert obtido in ("4d", "4d 56min"), (
        f"para 4d 56min o contrato admite DUAS leituras e nenhuma outra: "
        f"'4d 56min' (exemplo do dono) ou '4d' (regra da interface, ao pé da "
        f"letra). Obtido {obtido!r}.\n  Formas proibidas em qualquer leitura: "
        "'4D56' (maiúscula/colado), '4d 0h 56min' (três unidades), '4d 56m' "
        "('m' solto), '4d 0h' (hora zero explícita)."
    )
    assert obtido.startswith("4d"), (
        f"o ramo de dias começa em '<D>d'; obtido {obtido!r}"
    )
    assert _UNIDADES_OK.match(obtido) or obtido == "4d 56min", (
        f"forma fora da convenção em qualquer das duas leituras: {obtido!r}"
    )


def test_unidades_sempre_minusculas_e_com_espaco_entre_grupos(fronteiras):
    """Contract 1: ``h``/``d``/``min`` lowercase, space BETWEEN the two groups.

    The number stays glued to its own unit (``3h``, ``22min`` is correct); what
    the contract forbids is the old shape, which glued two groups together
    (``3H18``), upper-cased the unit (``4D56``) or used a bare ``m`` (``3h 22m``).
    The canonical regex encodes exactly the allowed shapes, so any resurrected
    variant fails here with its own string in the message.
    """
    for nome, _segundos in FRONTEIRAS:
        obtido = fronteiras(nome)["relative"]
        assert obtido == obtido.lower(), (
            f"[{nome}] unidade em maiúscula (formato antigo '3H18'/'4D56'); "
            f"obtido {obtido!r}"
        )
        assert _UNIDADES_OK.match(obtido), (
            f"[{nome}] forma fora da convenção (esperado numero+unidade, com "
            f"espaço entre os dois grupos); obtido {obtido!r}"
        )
        assert not re.search(r"\d+m(?!in)", obtido), (
            f"[{nome}] 'm' solto no lugar de 'min' (formato antigo '3h 22m'); "
            f"obtido {obtido!r}"
        )


# --------------------------------------------------------------------------- #
# Past reset, rounding, ISO offset — edges the boundaries do not reach
# --------------------------------------------------------------------------- #

PASSADO_E_ARREDONDAMENTO: list[tuple[str, float]] = [
    # a reset instant already behind us: saturates at 0, never negative
    ("passado-30s", -30.0),
    ("passado-1d", -float(DIA)),
    # Math.round, not ceil/floor: 59.4 -> 59 stays "now"; 59.6 -> 60 becomes "1min"
    ("arredonda-59-4", 59.4),
    ("arredonda-59-6", 59.6),
    # 3599.6 -> 3600 crosses into the hour branch: "1h 0min", not "59min"
    ("arredonda-3599-6", 3599.6),
    # 86399.6 -> 86400 crosses into the day branch: "1d", not "23h 59min"
    ("arredonda-86399-6", 86399.6),
    # fractional nowEpoch (12380.4 -> 12380) must still yield an INT seconds
    ("fracionario-12380-4", 12380.4),
]


@pytest.fixture(scope="module")
def passado(tmp_path_factory) -> Bancada:
    _artefatos()
    tmp = tmp_path_factory.mktemp("t23-passado")
    return _rodar([_caso(n, s) for n, s in PASSADO_E_ARREDONDAMENTO],
                  tmp, rotulo="passado")


def test_reset_no_passado_nao_produz_segundos_negativos(passado):
    """A reset instant already in the past is ``0`` seconds and ``now``.

    Never a negative ``seconds``: a ``-3600`` would leak into any downstream
    ``%``/``//`` and turn the display into ``-1d -1h``.
    """
    for nome in ("passado-30s", "passado-1d"):
        d = passado(nome)
        assert d.get("valid") is True, (
            f"[{nome}] um timestamp válido no passado continua sendo entrada "
            f"válida; obtido={d}"
        )
        assert d.get("seconds") == 0, (
            f"[{nome}] reset no passado deve saturar em 0, nunca negativo; "
            f"obtido={d.get('seconds')!r}"
        )
        assert (d.get("days"), d.get("hours"), d.get("minutes")) == (0, 0, 0), (
            f"[{nome}] com seconds=0 a decomposição é 0/0/0; "
            f"obtido={(d.get('days'), d.get('hours'), d.get('minutes'))}"
        )
        assert d.get("relative") == "now", (
            f"[{nome}] com 0s o relativo deve ser 'now'; obtido {d.get('relative')!r}"
        )


def test_arredondamento_e_round_e_muda_de_ramo_na_fronteira(passado):
    """``seconds = max(0, round(delta))``: 59.4 stays ``now``, 59.6 becomes ``1min``.

    Both directions are pinned, because ``ceil`` and ``floor`` each pass one of
    them and fail the other; the two branch crossings pin that rounding happens
    BEFORE the branch is chosen.
    """
    assert passado("arredonda-59-4")["relative"] == "now", (
        f"59.4s arredonda para 59 e continua 'now'; "
        f"obtido {passado('arredonda-59-4')['relative']!r} "
        f"(seconds={passado('arredonda-59-4')['seconds']!r})"
    )
    assert passado("arredonda-59-6")["relative"] == "1min", (
        f"59.6s arredonda para 60 e cai no ramo de minutos: '1min'; "
        f"obtido {passado('arredonda-59-6')['relative']!r} "
        f"(seconds={passado('arredonda-59-6')['seconds']!r})"
    )
    assert passado("arredonda-3599-6")["relative"] == "1h 0min", (
        f"3599.6s -> 3600s cruza para o ramo de horas: '1h 0min'; "
        f"obtido {passado('arredonda-3599-6')['relative']!r} "
        f"(seconds={passado('arredonda-3599-6')['seconds']!r})"
    )
    assert passado("arredonda-86399-6")["relative"] == "1d", (
        f"86399.6s -> 86400s cruza para o ramo de dias: '1d'; "
        f"obtido {passado('arredonda-86399-6')['relative']!r} "
        f"(seconds={passado('arredonda-86399-6')['seconds']!r})"
    )


def test_now_epoch_fracionario_ainda_produz_segundos_inteiros(passado):
    """``nowEpoch`` may be fractional; ``seconds`` must not be."""
    d = passado("fracionario-12380-4")
    seg = d.get("seconds")
    assert isinstance(seg, int) and not isinstance(seg, bool), (
        f"seconds deve ser INTEIRO mesmo com nowEpoch fracionário; "
        f"obtido {type(seg).__name__} {seg!r} (retorno={d})"
    )
    assert seg == 12380, f"12380.4s deve arredondar para 12380; obtido {seg!r}"
    assert d.get("relative") == "3h 26min", (
        f"12380s = 3h 26min; obtido {d.get('relative')!r}"
    )


def test_reset_iso_com_offset_e_honrado(tmp_path_factory):
    """``15:33-03:00`` IS ``18:33Z``: an ISO-8601 offset must be applied.

    Negative case for string-slicing: reading the first 19 characters as if they
    were UTC would invent 10800 extra seconds (``6h 26min`` instead of
    ``3h 26min``) — a three-hour lie on every reset in a UTC-3 locale.
    """
    _artefatos()
    tmp = tmp_path_factory.mktemp("t23-offset")
    casos = [
        {"name": "offset-z", "args": [RESET_ISO, RESET_EPOCH - 12380]},
        {"name": "offset-menos-3",
         "args": ["2026-10-28T15:33:00-03:00", RESET_EPOCH - 12380]},
    ]
    b = _rodar(casos, tmp, rotulo="offset")
    z = b("offset-z")
    off = b("offset-menos-3")

    assert z.get("seconds") == 12380, f"âncora: o caso Z deveria dar 12380s; obtido {z}"
    assert off.get("valid") is True, (
        f"timestamp ISO com offset é entrada válida; obtido={off}"
    )
    assert off.get("seconds") == z.get("seconds"), (
        "o mesmo instante grafado com offset (-03:00) e com Z deve dar os mesmos "
        f"segundos; Z={z.get('seconds')!r}, -03:00={off.get('seconds')!r}"
    )
    assert off.get("relative") == "3h 26min", (
        f"com o offset aplicado, 12380s é '3h 26min'; obtido {off.get('relative')!r}"
    )


# --------------------------------------------------------------------------- #
# Invalid input — must be ``{ valid: false }`` and must not throw
# --------------------------------------------------------------------------- #

INVALIDOS: list[tuple[str, object, str]] = [
    ("nulo", {"$null": True}, "null"),
    ("vazio", "", "string vazia"),
    ("espacos", "   ", "só espaços"),
    ("lixo", "not-a-timestamp", "texto qualquer"),
    ("lixo-iso", "2026-99-99T99:99:99Z", "data impossível"),
]


@pytest.fixture(scope="module")
def invalidos(tmp_path_factory) -> Bancada:
    _artefatos()
    tmp = tmp_path_factory.mktemp("t23-invalidos")
    casos = [{"name": n, "args": [v, RESET_EPOCH]} for n, v, _ in INVALIDOS]
    return _rodar(casos, tmp, rotulo="invalidos")


def test_entrada_invalida_devolve_valid_false_sem_lancar(invalidos):
    """``null`` / ``""`` / garbage → ``{ valid: false }``; never a throw."""
    _exigir_funcao(invalidos)
    for nome, _valor, descricao in INVALIDOS:
        assert nome not in invalidos.excecoes, (
            f"[{nome}] {descricao} não pode LANÇAR: o contrato manda devolver "
            f"{{valid:false}}; exceção={invalidos.excecoes.get(nome)!r}"
        )
        d = invalidos(nome)
        assert d.get("valid") is False, (
            f"[{nome}] {descricao} deve devolver {{valid:false}}; obtido={d}"
        )


def test_entrada_invalida_nao_inventa_duracao(invalidos):
    """Case NEGATIVE: an invalid input must not come back with a plausible ``relative``.

    A stub that defaults ``seconds`` to 0 would answer ``"now"`` for garbage —
    indistinguishable, on screen, from a reset that is about to happen.
    """
    _exigir_funcao(invalidos)
    for nome, _valor, descricao in INVALIDOS:
        d = invalidos(nome)
        rel = d.get("relative")
        assert rel is None or rel == "" or rel == {"$undefined": True}, (
            f"[{nome}] entrada inválida não pode produzir um relativo "
            f"({descricao}); obtido relative={rel!r} no retorno {d}"
        )


# --------------------------------------------------------------------------- #
# Sweep — structure over many values
# --------------------------------------------------------------------------- #

#: Deliberately avoids the disputed region (days >= 1 with hours == 0 and
#: minutes > 0), which belongs to the single test above.
VARREDURA_SEGUNDOS: list[int] = [
    0, 1, 30, 59, 60, 61, 119, 120, 599, 3599, 3600, 3601, 5400, 7199, 7200,
    86339, 86340, 86341, 86399, 86400, 86401, 90061, 129600, 172799, 172800,
    259199, 259200, 432000, 604800, 604801, 2678400, 9999999,
]


@pytest.fixture(scope="module")
def varredura(tmp_path_factory) -> Bancada:
    _artefatos()
    tmp = tmp_path_factory.mktemp("t23-varredura")
    return _rodar(
        [_caso(f"varredura-{s:07d}", s) for s in VARREDURA_SEGUNDOS],
        tmp, rotulo="varredura",
    )


def test_varredura_respeita_forma_decomposicao_e_ramo(varredura):
    """32 values: shape, canonical decomposition and branch — collected, then reported.

    Failures accumulate so the report shows the WHOLE pattern (e.g. "every day
    value prints a trailing 0h") instead of only the first one.
    """
    _exigir_funcao(varredura)
    falhas: list[str] = []
    for s in VARREDURA_SEGUNDOS:
        d = varredura(f"varredura-{s:07d}")
        rel = d.get("relative")
        if d.get("valid") is not True:
            falhas.append(f"[{s}s] valid != true (retorno={d})")
            continue
        if d.get("seconds") != s:
            falhas.append(f"[{s}s] seconds={d.get('seconds')!r}")
            continue
        esperado = _decomposicao_esperada(s)
        obtido = (d.get("days"), d.get("hours"), d.get("minutes"))
        if obtido != esperado:
            falhas.append(f"[{s}s] decomposição {obtido} != {esperado}")
        if not isinstance(rel, str):
            falhas.append(f"[{s}s] relative não é string: {rel!r}")
            continue
        if not _UNIDADES_OK.match(rel):
            falhas.append(f"[{s}s] forma fora da convenção: {rel!r}")
        elif rel != _relativo_esperado(s):
            falhas.append(f"[{s}s] esperado {_relativo_esperado(s)!r}, veio {rel!r}")
        if rel.count(" ") > 1:
            falhas.append(f"[{s}s] mais de duas unidades: {rel!r}")
        if rel != rel.lower():
            falhas.append(f"[{s}s] unidade em maiúscula: {rel!r}")
    assert not falhas, "violações da convenção na varredura:\n" + "\n".join(falhas)


def test_nunca_tres_unidades_em_nenhum_ramo(varredura):
    """Contract 2, standalone: no output may carry three unit tokens.

    The forbidden example is ``3d 4h 12min`` — three unit tokens. ``1h 0min``
    is legal (hours branch, ALWAYS both parts); the two branches are told apart
    by the unit itself, not by counting spaces.
    """
    _exigir_funcao(varredura)
    for s in VARREDURA_SEGUNDOS:
        rel = varredura(f"varredura-{s:07d}").get("relative")
        if not isinstance(rel, str):
            continue
        tokens = [t for t in rel.split(" ") if re.search(r"[a-z]", t)]
        assert len(tokens) <= 2, (
            f"[{s}s] três unidades em {rel!r} (proibido: '3d 4h 12min')"
        )
        unidades = [re.sub(r"\d+", "", t) for t in tokens]
        assert len(set(unidades)) == len(unidades), (
            f"[{s}s] unidade repetida em {rel!r}"
        )


def test_o_relativo_nao_carrega_o_horario_localizado(varredura):
    """``resetParts`` is locale-free by contract: no ``Hoje/Amanhã``, no clock.

    The exact time (``Hoje, 18:33`` / ``Amanhã, 09:10`` / ``12/nov, 14:00``) is
    localized and comes AFTER the relative part, so it cannot be produced by a
    function declared free of locale and ``tr()``. Only the NEGATIVE claim is
    pinned here — that the suffix was not smuggled into ``relative``.
    """
    _exigir_funcao(varredura)
    for s in VARREDURA_SEGUNDOS:
        rel = varredura(f"varredura-{s:07d}").get("relative")
        if not isinstance(rel, str):
            continue
        assert " · " not in rel, (
            f"[{s}s] ' · ' é o separador do horário localizado, que não pertence "
            f"ao retorno de {NOME_CONTRATO}; obtido {rel!r}"
        )
        assert not re.search(r"\d{1,2}:\d{2}", rel), (
            f"[{s}s] horário de relógio dentro do relativo (o padrão de hora "
            f"segue o locale, e a função é locale-free); obtido {rel!r}"
        )
        assert not re.search(r"(?i)hoje|amanh[aã]|today|tomorrow", rel), (
            f"[{s}s] rótulo de dia relativo dentro de {NOME_CONTRATO}; "
            f"obtido {rel!r}"
        )


# --------------------------------------------------------------------------- #
# AMBIGUIDADES do contrato (assumidas, não inventadas)
# --------------------------------------------------------------------------- #
AMBIGUIDADES = """
1. CONTRADIÇÃO REAL, e a mais importante: o exemplo do dono lista ``4d 56min``,
   mas a regra da interface ("omitir ' <H>h' apenas quando hours == 0") imprime
   ``4d`` para esse mesmo instante — os 56 minutos somem. Como ``4d 56min`` só é
   imprimível se o resíduo do dia usar UMA unidade extra, seja 'h' seja 'min',
   os testes fixam o EXEMPLO DO DONO (decisão humana) em um único teste nomeado
   (``test_dia_com_minutos_residuais_segue_o_exemplo_do_dono``) e mantêm essa
   região FORA da varredura, para que a disputa não contamine a suíte inteira.
   Se a implementação seguir a interface ao pé da letra, aquele teste fica
   vermelho de propósito: é pergunta ao dono, não defeito de código.

2. O horário exato (``Hoje, 18:33`` / ``Amanhã, 09:10`` / ``12/nov, 14:00``) NÃO
   é testado. ``resetParts`` é declarada pura, sem locale e sem ``tr()``, mas o
   contrato 4/5 exige que o sufixo traduza e siga o padrão de hora do locale. As
   duas afirmações só são compatíveis se o sufixo for montado FORA da função
   (numa segunda etapa, na view). Fixa-se apenas a metade verificável: o
   ``relative`` não contém `` · ``, horário nem ``Hoje/Amanhã``. Se o desenho
   decidido for outro (a função recebendo locale), esse teste fica vermelho por
   um motivo legítimo, e a divergência se resolve no contrato.

3. "Omitido quando não acrescenta (ex.: reset a mais de 7 dias)" não define o
   LIMITE: é ``> 7d``, ``>= 7d`` ou um número de horas? Como o sufixo não é
   produzido por ``resetParts`` (item 2), a regra não é testável aqui. Nada é
   assumido sobre ela.

4. ``{ valid: false }`` é descrito só com ``valid``. Não há asserção sobre quais
   OUTRAS chaves existem no retorno inválido. Assume-se apenas o que o contrato
   diz: ``valid`` é literalmente ``false`` e nenhum ``relative`` utilizável o
   acompanha (caso negativo). Se a implementação devolver ``seconds: 0`` junto,
   o teste ainda passa — de propósito, porque o contrato não proíbe.

5. "Formatação localizada" convive mal com as "unidades em inglês" do retorno:
   o contrato de UI manda ``agora`` em português, e a interface devolve ``now``.
   Os testes exigem ``now`` (a interface é explícita), o que fixa a UI inglesa
   como fonte e deixa a tradução para a camada de ``tr()``. Um contrato que
   esperasse ``agora`` aqui tornaria a função dependente de locale, contra a
   própria assinatura.

6. ISO-8601 "com offset" não é exemplificado (a interface só mostra ``Z``).
   Assumi que ``-03:00`` é aceito e aplicado, porque ISO-8601 o inclui e a view
   recebe ``reset_at`` de um upstream que pode emitir offset. Se o contrato
   quisesse aceitar SOMENTE ``Z``, esse teste seria exigência a mais — declarado.

7. ``nowEpoch`` "pode ser fracionário" e ``seconds`` é ``Math.round``, mas não é
   dito se ``resetAt`` pode ter fração de segundo (``.500Z``): não há caso para
   isso. Também não é dito o que acontece com ``nowEpoch`` ausente/``undefined``
   — fora do contrato por omissão, não testado.

8. ``Math.round`` em JS arredonda ``-0.5`` para ``-0``, e ``-0`` exibe como
   ``0``. O contrato diz ``max(0, round(...))``; os testes usam ``-0.4`` e
   ``-30``, evitando depender dessa borda exata.

9. "Nada na UI escapa dela" (critério de done) não é verificável por uma função
   pura: exigiria inspecionar TODA superfície que desenha reset. Fora deste
   arquivo; é trabalho de um harness de render, não deste.

10. O nome ``resetParts`` é uma decisão da interface. O harness SONDA dez
    grafias alternativas (inclusive a antiga ``cooldown``) e RELATA o que achou,
    mas o teste aceita SÓ ``resetParts``: uma função com outro nome reprova com
    a lista do que existe — falha ruidosa, nunca silenciosa.
"""
