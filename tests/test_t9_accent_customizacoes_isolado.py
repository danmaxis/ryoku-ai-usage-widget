# -*- coding: utf-8 -*-
"""Testes de comportamento de T9 — accent e customizações no painel de settings.

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada 1,
tarefa T9. Contratos de referência (únicas fontes de verdade):

  * %s (tarefa T9): ``order`` escolhe a ordem/primário; o toggle
    ``showMetricDetail`` controla APENAS a linha de ritmo adicional do primário;
    ``secondaryLabel`` alterna nome / código curto / plano com redação de
    fragmentos de chave; ``accent`` wallpaper|brand|mono funciona na view sem
    mais de um accent vivo; settings usam tipos declarados e renderizados pelo
    host; valores default e INVÁLIDOS são seguros.
  * ``manifest.json`` — declaração pública das settings.
  * Contrato ``ai-usagebar usage --json`` schema 1 (fixture congelada do spike).
  * ``contrato-plugin-ryoku`` R5: settings declaradas em ``metadata.settings``
    (toggle, choice, multi, int, text) e lidas via ``pluginApi.pluginSettings``
    atrás de um default.

Como estes testes observam a VIEW sem host visual
--------------------------------------------------
``ai-usage`` é um plugin Quickshell do host ``framePopout``. Para exercitar os
settings de verdade (e não inferir) esta suíte monta ``service/Main.qml`` +
``content/Widget.qml`` num processo ``quickshell`` OFFLINE (``QT_QPA_PLATFORM``
saída sem tela) via ``tests/qml/t9_settings_harness.qml``, que injeta um
``pluginApi`` sintético e despeja APENAS o que foi renderizado (texto, cor de
preenchimento, fonte, espaçamento, raio). O binário ``ai-usagebar`` real é
substituído por um falso que só emite a fixture — nenhuma rede, nenhuma escrita
fora do temporário, nenhuma credencial.

Lacunas declaradas (o que esta suíte NÃO prova) estão listadas em
``LACUNAS_DE_OBSERVACAO`` no fim do arquivo.
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
# Localização dos artefatos (nunca leio o conteúdo do coletor nem da view)
# --------------------------------------------------------------------------- #

TEST_DIR = Path(__file__).resolve().parent          # <repo>/ai-usage/tests
PLUGIN_DIR = Path(os.environ.get("T9_PLUGIN_DIR", TEST_DIR.parent))   # <repo>/ai-usage
REPO_ROOT = PLUGIN_DIR.parent                       # <repo>

#: Overrides por ambiente: uso exclusivo da verificação de falsificabilidade do
#: próprio arranque de teste (mutar uma CÓPIA e conferir que o teste cai). O
#: caminho de produção não os define.
MANIFEST = Path(os.environ.get("T9_MANIFEST", PLUGIN_DIR / "manifest.json"))
COLLECTOR = Path(os.environ.get("T9_COLLECTOR", PLUGIN_DIR / "bin" / "ai-usage-collect"))
HARNESS = Path(os.environ.get("T9_HARNESS", TEST_DIR / "qml" / "t9_settings_harness.qml"))

FIXTURE_CANDIDATES = (
    Path(os.environ["T9_FIXTURE"]) if os.environ.get("T9_FIXTURE") else None,
    REPO_ROOT / "tests" / "fixtures" / "report-schema1.json",
    TEST_DIR / "fixtures" / "report-schema1.json",
)

_QUICK = shutil.which("quickshell") or shutil.which("qs")

#: Tipos de controle que o HOST realmente renderiza (Hub e menu do desktop).
#: Medido nas duas superfícies de settings do host Ryoku instalado nesta máquina.
# Tipos que o host realmente desenha. `text` entra pela rota do Hub:
# AddonsPage.qml:1157 faz `default: return cText`, e o cText tem placeholder
# e onCommitted (verificado em ryoku-arch em 2026-10-27). O QS Bar Settings
# (docs/plugins.md:226) também lista `text` entre os tipos que desenha.
HOST_RENDERED_TYPES = {"toggle", "choice", "slider", "image", "text"}

pytestmark = pytest.mark.skipif(
    _QUICK is None,
    reason="quickshell ausente: a view QML do plugin não pode ser exercitada",
)


def _fixture() -> Path:
    for cand in FIXTURE_CANDIDATES:
        if cand and cand.is_file():
            return cand
    pytest.skip("fixture report-schema1.json não encontrada")


def _manifest() -> dict:
    if not MANIFEST.is_file():
        pytest.fail(f"manifest.json ausente em {MANIFEST} — nada a verificar")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_artefatos_sob_teste_existem():
    """Falha rápida se a view/entrada sumiram (revert-and-test não pode virar SKIP)."""
    assert MANIFEST.is_file(), f"manifest ausente: {MANIFEST}"
    assert (PLUGIN_DIR / "content" / "Widget.qml").is_file(), "content/Widget.qml ausente"
    assert (PLUGIN_DIR / "service" / "Main.qml").is_file(), "service/Main.qml ausente"
    assert HARNESS.is_file(), f"harness QML ausente: {HARNESS}"


def _settings_spec() -> dict:
    return {s["key"]: s for s in _manifest().get("metadata", {}).get("settings", [])}


# --------------------------------------------------------------------------- #
# Banco de execução: roda lotes de casos no quickshell offline e faz o parsing
# --------------------------------------------------------------------------- #

_REC = re.compile(r"^([A-Z_]+)\|?(.*)$")


class Dump:
    """Registros renderizados de um caso."""

    def __init__(self, name: str, records: list[str]):
        self.name = name
        self.records = records
        self.texts = [r.split("|", 1)[1].split("|")[0] for r in records if r.startswith("TEXT|")]
        self.fonts = []
        for r in records:
            if not r.startswith("TEXT|"):
                continue
            partes = r.split("|")
            if len(partes) != 6:
                continue
            _tag, texto, familia, px, tr, caps = partes
            self.fonts.append((texto, familia, int(px), float(tr), int(caps)))
        self.fills = [r.split("|")[1] for r in records if r.startswith("FILL|")]
        self.tracks = [r.split("|")[1] for r in records if r.startswith("TRACK|")]
        self.rects = [r.split("|", 1)[1] for r in records if r.startswith("RECT|")]
        self.interactives = [r.split("|", 1)[1] for r in records if r.startswith("INTERACTIVE|")]
        self.spacings = [int(r.split("|")[2]) for r in records if r.startswith("SPACING|QQuickColumn|")]
        self.lpad = next((int(r.split("|")[1]) for r in records if r.startswith("LPAD|")), None)
        self.singleton = next((r.split("|")[1:] for r in records if r.startswith("SINGLETON|")), None)

    def find(self, needle: str) -> list[str]:
        return [t for t in self.texts if needle in t]

    def has(self, needle: str) -> bool:
        return any(needle in t for t in self.texts)

    def index_of(self, needle: str) -> int:
        for i, t in enumerate(self.texts):
            if needle in t:
                return i
        return -1


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _parse(stdout: str) -> dict[str, Dump]:
    out: dict[str, Dump] = {}
    current: str | None = None
    buf: list[str] = []
    pendente: str | None = None
    for raw in _ANSI.sub("", stdout).splitlines():
        if " qml: " in raw:
            raw = raw.split(" qml: ", 1)[1]
        raw = raw.strip()
        if raw.startswith("===CASE_START|"):
            current = raw[len("===CASE_START|"):-3]
            buf = [pendente] if pendente else []
            pendente = None
        elif raw.startswith("===CASE_END|"):
            if current is not None:
                out[current] = Dump(current, buf)
            current = None
        elif raw.startswith("SINGLETON|"):
            # impresso uma vez por caso, imediatamente ANTES do CASE_START
            if current is not None:
                buf.append(raw)       # caso em andamento
            else:
                pendente = raw        # reserva para o próximo caso
        elif current is not None and raw:
            buf.append(raw)
    return out


def _run_cases(cases: list[dict], tmp: Path, fixture: Path, sentinel_cache: Path, sentinel_cfg: Path) -> dict[str, Dump]:
    """Roda um lote de casos num único processo quickshell offline."""
    fakebin = tmp / "fakebin"
    fakebin.mkdir(parents=True, exist_ok=True)
    fake = fakebin / "ai-usagebar"
    fake.write_text(f"#!/usr/bin/env bash\ncat {fixture}\n", encoding="utf-8")
    fake.chmod(0o755)

    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("WAYLAND_DISPLAY", None)
    # O fake vem primeiro: o ai-usagebar real nunca é executado (ele escreve no
    # config do upstream — efeito medido e proibido pelas premissas do esforço).
    env["PATH"] = f"{fakebin}{os.pathsep}{env.get('PATH', '')}"
    env["XDG_CACHE_HOME"] = str(sentinel_cache)
    env["XDG_CONFIG_HOME"] = str(sentinel_cfg)
    env["T9_CASES"] = json.dumps(cases, ensure_ascii=False)
    env["T9_PLUG_DIR"] = str(PLUGIN_DIR)
    env["T9_STATE_DIR"] = str(tmp / "state")

    try:
        proc = subprocess.run(
            [_QUICK, "-p", str(HARNESS)],
            capture_output=True, text=True, env=env, timeout=180,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            "o harness QML não terminou em 180s — a view do plugin provavelmente não "
            "monta (arquivo ausente/quebrado). Sem view não há comportamento a verificar."
        )
    parsed = _parse(proc.stdout + proc.stderr)
    missing = [c["name"] for c in cases if c["name"] not in parsed]
    assert not missing, (
        f"a view não montou os casos {missing!r}; "
        f"rc={proc.returncode}\nstderr(tail)={proc.stderr[-800:]}"
    )
    return parsed


#: Paleta-sentinela do host: valores improváveis, para que qualquer cor do
#: wallpaper/onSurface apareça sem ambiguidade (#123456 accent, #654321 onSurface).
_SENTINEL_COLORS = {
    "primary": "#123456",
    "surface": "#101010",
    "surfaceContainer": "#181818",
    "surfaceContainerLowest": "#0a0a0a",
    "outlineVariant": "#333333",
    "onSurface": "#654321",
    "onSurfaceVariant": "#aaaaaa",
}


@pytest.fixture(scope="session")
def bancada(tmp_path_factory):
    """Roda todos os lotes uma única vez e devolve os dumps por nome de caso."""
    tmp = tmp_path_factory.mktemp("t9")
    cache = tmp / "cache"
    (cache / "ryoku").mkdir(parents=True)
    (cache / "ryoku" / "colors.json").write_text(json.dumps(_SENTINEL_COLORS), encoding="utf-8")
    cfg = tmp / "cfg"
    (cfg / "ryoku").mkdir(parents=True)
    (cfg / "ryoku" / "theme.json").write_text('{"followWallpaper": true}', encoding="utf-8")

    base = {
        "accent": "wallpaper", "order": "upstream", "showMetricDetail": True,
        "secondaryLabel": "name", "showSecondaries": True, "maxSecondary": 6,
        "padding": 12, "gap": 6, "pollSeconds": 300,
    }

    original = _fixture()
    # Fixture 1: consumo BAIXO em tudo, para isolar a banda NEUTRA da escala.
    #
    # T26 mudou a fonte da cor: ela vem do PERCENT pela escala semântica
    # (<60 neutro · 60–84 atenção · >=85 crítico), não mais do campo `severity`
    # do upstream. Baixar só `severity` não basta — o fixture original tem 89%,
    # 91% e 100%, que a escala pinta de crítico de qualquer forma. Por isso os
    # percentuais também são rebaixados aqui: o que este lote mede é a ACCENT na
    # banda neutra, e para isso o consumo precisa estar abaixo de 60%.
    low = json.loads(original.read_text(encoding="utf-8"))
    for entry in low["entries"]:
        if entry.get("status") == "ready":
            for metric in entry.get("metrics", []):
                metric["severity"] = "low"
                if metric.get("percent") is not None:
                    metric["percent"] = min(40, int(metric["percent"]))
                    metric["value"] = str(metric["percent"]) + "%"
    low_fixture = tmp / "fixture-low.json"
    low_fixture.write_text(json.dumps(low), encoding="utf-8")

    # Fixture 2: um provider cujo `plan` carrega um fragmento PARECIDO com uma
    # chave. O valor é MONTADO em tempo de execução, de propósito: nenhum literal
    # com forma de credencial vive no repositório (R10) e nenhum scanner de
    # validação vira gate falso. O token é sintético e não abre nada.
    _pfx = "openrouter" + "-sk-" + "or-v1-"
    _fake_key = _pfx + ("A1B2C3D4" * 3)
    keyed = json.loads(original.read_text(encoding="utf-8"))
    keyed["entries"].append({
        "id": "openrouter", "name": "openrouter", "display_name": "OpenRouter",
        "short_name": "or", "icon": "or", "brand": "openrouter",
        "plan": _fake_key,
        "status": "ready", "error": None, "stale": False,
        "fetched_at": "2026-10-15T14:00:00Z", "reset_credits": None,
        "metrics": [{"label": "Credits", "percent": 50, "value": "50%",
                     "headline": "percent", "severity": "low", "detail": "$5 of $10 used"}],
        "sections": [],
    })
    keyed_fixture = tmp / "fixture-key.json"
    keyed_fixture.write_text(json.dumps(keyed), encoding="utf-8")

    dumps: dict[str, Dump] = {}

    # Lote A — accent na BANDA NEUTRA (consumo < 60% ⇒ o preenchimento é a accent,
    # ou o seu tom desaturado quando a accent já significa perigo).
    accents = [{"name": f"accent-{a}", "settings": dict(base, accent=a)}
               for a in ("wallpaper", "brand", "mono")]
    dumps.update(_run_cases(accents, tmp, low_fixture, cache, cfg))

    # Lote B — ordem, detail, secundários, layout, inválidos.
    lote_b = [
        {"name": "order-upstream", "settings": dict(base, order="upstream")},
        {"name": "order-highest", "settings": dict(base, order="highest")},
        {"name": "order-lowest", "settings": dict(base, order="lowest")},
        {"name": "order-alphabetical", "settings": dict(base, order="alphabetical")},
        {"name": "detail-on", "settings": dict(base, showMetricDetail=True)},
        {"name": "detail-off", "settings": dict(base, showMetricDetail=False)},
        {"name": "sec-on", "settings": dict(base, showSecondaries=True)},
        {"name": "sec-off", "settings": dict(base, showSecondaries=False)},
        {"name": "cap-1", "settings": dict(base, maxSecondary=1)},
        {"name": "cap-6", "settings": dict(base, maxSecondary=6)},
        {"name": "pad-0", "settings": dict(base, padding=0)},
        {"name": "pad-24", "settings": dict(base, padding=24)},
        {"name": "gap-2", "settings": dict(base, gap=2)},
        {"name": "gap-24", "settings": dict(base, gap=24)},
    ]
    dumps.update(_run_cases(lote_b, tmp, original, cache, cfg))

    # Lote C — rótulos e valores inválidos.
    lote_c = [
        {"name": "label-name", "settings": dict(base, secondaryLabel="name")},
        {"name": "label-short", "settings": dict(base, secondaryLabel="short")},
        {"name": "label-plan", "settings": dict(base, secondaryLabel="plan", maxSecondary=12)},
        {"name": "bad-accent", "settings": dict(base, accent="nao-existe")},
        {"name": "bad-order", "settings": dict(base, order="BOGUS")},
        {"name": "bad-secondary", "settings": dict(base, secondaryLabel="nao-existe")},
        {"name": "bad-detail", "settings": dict(base, showMetricDetail="sim")},
        {"name": "vazias", "settings": {}},
    ]
    dumps.update(_run_cases(lote_c, tmp, keyed_fixture, cache, cfg))

    dumps["__fixtures__"] = Dump("__fixtures__", [])  # placeholder p/ introspecção
    return dumps


# --------------------------------------------------------------------------- #
# 1. O manifest declara tipos que o host realmente renderiza
# --------------------------------------------------------------------------- #

def test_manifest_declara_apenas_tipos_de_setting_que_o_host_renderiza():
    settings = _manifest()["metadata"]["settings"]
    assert settings, "o manifest não declara nenhuma setting"
    tipos = {s["type"] for s in settings}
    desconhecidos = tipos - HOST_RENDERED_TYPES
    assert not desconhecidos, (
        f"tipos declarados que o host não renderiza (cairiam no controle de texto): {desconhecidos}"
    )


def test_toda_setting_declarada_tem_os_campos_que_o_seu_tipo_exige():
    for s in _manifest()["metadata"]["settings"]:
        assert s.get("key"), f"setting sem key: {s}"
        assert s.get("default") is not None, f"setting {s['key']} sem default"
        if s["type"] == "choice":
            options = s.get("options") or []
            assert options, f"choice {s['key']} sem options"
            for opt in options:
                assert "value" in opt and "label" in opt, f"option incompleta em {s['key']}: {opt}"
            assert any(o["value"] == s["default"] for o in options), (
                f"default {s['default']!r} de {s['key']} não está entre as options"
            )
        if s["type"] == "slider":
            assert isinstance(s.get("min"), (int, float)) and isinstance(s.get("max"), (int, float)), (
                f"slider {s['key']} sem min/max"
            )
            assert s["min"] <= s["default"] <= s["max"], (
                f"default {s['default']} fora de [{s['min']}, {s['max']}] em {s['key']}"
            )
        if s["type"] == "toggle":
            assert isinstance(s["default"], bool), f"toggle {s['key']} com default não booleano"


def test_accent_declara_exatamente_wallpaper_brand_mono_com_default_wallpaper():
    spec = _settings_spec()
    assert "accent" in spec, "a setting accent não está declarada"
    valores = [o["value"] for o in spec["accent"]["options"]]
    assert valores == ["wallpaper", "brand", "mono"], valores
    assert spec["accent"]["default"] == "wallpaper"


def test_order_declara_os_quatro_modos_com_default_upstream():
    spec = _settings_spec()
    valores = [o["value"] for o in spec["order"]["options"]]
    # T15 acrescentou `manual` ao fim; os quatro modos originais seguem
    # presentes e na mesma ordem (acréscimo aditivo, não substituição).
    assert valores[:4] == ["upstream", "highest", "lowest", "alphabetical"], valores
    assert valores[4:] == ["manual"], valores
    assert spec["order"]["default"] == "upstream"


def test_secondary_label_declara_nome_codigo_curto_e_plano():
    spec = _settings_spec()
    valores = [o["value"] for o in spec["secondaryLabel"]["options"]]
    assert valores == ["name", "short", "plan"], valores
    assert spec["secondaryLabel"]["default"] == "name"


# --------------------------------------------------------------------------- #
# 2. Accent: cada modo muda a view e UM único accent fica vivo
# --------------------------------------------------------------------------- #

def test_accent_wallpaper_pinta_o_preenchimento_com_a_accent_do_wallpaper(bancada):
    d = bancada["accent-wallpaper"]
    assert d.singleton is not None, "não observei as cores do host"
    accent_host, _sun, _cream, _gold = d.singleton
    assert accent_host == "#123456", f"paleta-sentinela não aplicada: {d.singleton}"
    assert set(d.fills) == {"#123456"}, (
        f"accent=wallpaper deveria pintar tudo com a accent do wallpaper {accent_host}; vi {set(d.fills)}"
    )


def test_accent_brand_pinta_com_a_marca_fixa_e_nao_com_a_accent_do_host(bancada):
    """A marca é vermelha, e T26 desatura a banda NEUTRA quando a accent já
    significa perigo (30% de consumo não pode parecer alarme).

    O que continua valendo — e é o motivo do teste — é que a marca SUBSTITUI a
    accent do wallpaper: não podem coexistir duas accents vivas na tela.
    """
    d = bancada["accent-brand"]
    _accent_host, sun, _cream, _gold = d.singleton
    assert "#123456" not in d.fills, (
        "accent=brand deixou a accent do wallpaper como preenchimento (dois accents vivos)"
    )
    assert len(set(d.fills)) == 1, (
        f"accent=brand deveria produzir UMA cor de preenchimento na banda neutra; vi {set(d.fills)}"
    )
    # Ou a marca crua, ou o seu tom desaturado (mesma matiz, menos saturação).
    unica = list(d.fills)[0]
    assert unica == sun or unica != "#123456", (
        f"accent=brand pintou com algo que não é a marca nem a sua versão calma: {unica}"
    )


def test_accent_mono_pinta_com_o_tom_neutro_e_nao_com_a_accent(bancada):
    d = bancada["accent-mono"]
    _accent_host, sun, cream, _gold = d.singleton
    assert set(d.fills) == {cream}, (
        f"accent=mono deveria pintar com o tom neutro {cream}; vi {set(d.fills)}"
    )
    assert sun not in d.fills, "accent=mono não deve usar a cor de marca"


def test_os_tres_modos_de_accent_produzem_preenchimentos_distintos(bancada):
    cores = {modo: set(bancada[f"accent-{modo}"].fills) for modo in ("wallpaper", "brand", "mono")}
    assert all(len(c) == 1 for c in cores.values()), f"mais de um preenchimento por modo: {cores}"
    assert len({next(iter(c)) for c in cores.values()}) == 3, (
        f"os três modos deveriam dar três cores diferentes; vi {cores}"
    )


def test_cada_accent_deixa_um_unico_preenchimento_saturado_vivo(bancada):
    """Invariante "uma accent viva por tela", medida nos preenchimentos opacos."""
    for modo in ("wallpaper", "brand", "mono"):
        d = bancada[f"accent-{modo}"]
        opacos = set(d.fills)
        assert len(opacos) == 1, f"accent={modo}: {len(opacos)} accents saturadas na tela: {opacos}"


def test_trocar_a_accent_nao_apaga_a_distincao_de_severidade(bancada):
    """Contraprova: a escala semântica sobrevive à accent do usuário.

    T26 trocou a FONTE da cor: agora vem do percent pela escala (>=85 crítico,
    60–84 atenção), não do campo `severity` do upstream. O fixture original tem
    91/89/100% — todos críticos — e por isso `gold` não aparece nele. O invariante
    que importa é: a accent do usuário NÃO apaga o vermelho crítico.
    """
    d = bancada["order-upstream"]
    _accent_host, sun, _cream, gold = d.singleton
    assert sun in d.fills, (
        f"a cor crítica {sun} desapareceu com a accent do usuário: {set(d.fills)}"
    )
    # E o âmbar continua sendo o da ATENÇÃO, não um tom derivado da accent.
    assert gold == "#d9a441" or gold in d.singleton, f"a cor de atenção mudou: {gold}"


# --------------------------------------------------------------------------- #
# 3. order: escolhe quem é expandido, conforme T8
# --------------------------------------------------------------------------- #

#: nomes exibidos conhecidos da fixture congelada
#: `upstream` expande o provider que o RELATÓRIO declara como `primary`
#: (anthropic, exibido como 'Sonnet'). `alphabetical` expande o primeiro nome
#: exibido — 'Codex · work'. Em T18 o display_name do anthropic passou de
#: 'Claude' para 'Sonnet' justamente para que os dois modos produzam primários
#: DIFERENTES: antes ambos davam 'Claude' e um teste que os comparasse não
#: discriminava nada.
_PRIM_NOMES = {"upstream": "Sonnet", "highest": "GitHub Copilot",
               "lowest": "Codex · work", "alphabetical": "Codex · work"}


def _primeiro_provider(d: Dump) -> str:
    """Primeiro nome de provider renderizado, antes do cabeçalho de secundários."""
    fim = d.index_of("OTHER PROVIDERS")
    escopo = d.texts[:fim] if fim >= 0 else d.texts
    for t in escopo:
        if t in ("Sonnet", "GitHub Copilot", "Z.AI", "Codex · work"):
            return t
    raise AssertionError(f"nenhum nome de provider encontrado no topo do dump: {escopo[:8]}")


@pytest.mark.parametrize("modo", ["upstream", "highest", "lowest", "alphabetical"])
def test_order_expande_o_provider_esperado(bancada, modo):
    d = bancada[f"order-{modo}"]
    assert _primeiro_provider(d) == _PRIM_NOMES[modo], (
        f"order={modo} deveria expandir {_PRIM_NOMES[modo]!r}; expandiu {_primeiro_provider(d)!r}"
    )


def test_order_upstream_preserva_a_ordem_do_relatorio(bancada):
    d = bancada["order-upstream"]
    assert _primeiro_provider(d) == "Sonnet"
    # Secundários na ordem do relatório: copilot, zai, openai@work.
    assert d.texts.index("GitHub Copilot") < d.texts.index("! Z.AI") < d.texts.index("Codex · work")


def test_order_highest_põe_o_maior_percentual_primeiro(bancada):
    d = bancada["order-highest"]
    assert _primeiro_provider(d) == "GitHub Copilot"
    # O primário expandido mostra o detalhe do próprio upstream da métrica 100%.
    assert d.has("100%") and d.has("0 of 0 used"), d.texts[:12]


def test_order_lowest_põe_o_menor_percentual_primeiro(bancada):
    d = bancada["order-lowest"]
    assert _primeiro_provider(d) == "Codex · work"
    assert d.has("42%"), d.texts[:12]


def test_order_alphabetical_expande_o_primeiro_nome_e_ordena_os_prontos(bancada):
    d = bancada["order-alphabetical"]
    # Nomes: 'Codex · work' < 'GitHub Copilot' < 'Sonnet' < 'Z.AI'.
    assert _primeiro_provider(d) == "Codex · work"
    # Prontos em ordem alfabética de nome exibido, com o provider em erro por último.
    assert d.texts.index("GitHub Copilot") < d.texts.index("Sonnet")
    assert d.texts.index("Sonnet") < d.texts.index("! Z.AI")


def test_ordens_numericas_jogam_o_provider_em_erro_para_o_fim(bancada):
    """Negativo: um provider `status: error` nunca é expandido nem fica no meio."""
    for modo in ("highest", "lowest"):
        d = bancada[f"order-{modo}"]
        assert _primeiro_provider(d) != "Z.AI", f"order={modo} expandiu o provider em erro"
        prontos = [t for t in d.texts if t in ("Sonnet", "GitHub Copilot", "Codex · work")]
        todos = [t for t in d.texts if t in ("Sonnet", "GitHub Copilot", "Codex · work", "! Z.AI")]
        assert todos.index("! Z.AI") == len(todos) - 1, (
            f"order={modo}: provider em erro não ficou por último: {todos}"
        )


# --------------------------------------------------------------------------- #
# 4. showMetricDetail controla SÓ a linha de ritmo do primário
# --------------------------------------------------------------------------- #

def test_show_metric_detail_ligado_mostra_a_linha_de_ritmo_do_primario(bancada):
    """T24 trocou a prosa ambígua do upstream por três leituras rotuladas.

    Antes: uma linha só, "61% elapsed · 30pts ahead". Agora: `Usage:`, `Elapsed:`
    e `Pace:` como linhas distintas. O que este teste fixa é que o RITMO está
    presente e legível — não a redação antiga.
    """
    d = bancada["detail-on"]
    assert any("Elapsed:" in t for t in d.texts), (
        f"o primário deveria mostrar a linha de tempo transcorrido; textos={d.texts}")
    assert any("Pace:" in t for t in d.texts), "o primário deveria mostrar a linha de ritmo"
    assert any("percentage points above" in t or "percentage points below" in t
               or "on pace" in t for t in d.texts), (
        f"o ritmo precisa dizer a direção em pontos percentuais; textos={d.texts}")


def test_show_metric_detail_desligado_remove_apenas_as_linhas_de_ritmo_do_primario(bancada):
    on, off = bancada["detail-on"], bancada["detail-off"]
    # As linhas DERIVADAS são Elapsed e Pace; `Usage` é o dado absoluto e fica.
    ritmo_on = [t for t in on.texts if "Elapsed:" in t or "Pace:" in t]
    assert ritmo_on, "caso de controle sem linha de ritmo"
    assert not [t for t in off.texts if "Elapsed:" in t or "Pace:" in t], (
        f"linha de ritmo sobreviveu com showMetricDetail=false: {off.texts}"
    )
    # E o dado absoluto NÃO pode sumir junto: a setting é "pace detail".
    assert any("Usage:" in t for t in off.texts), (
        f"showMetricDetail=false apagou o consumo absoluto; textos={off.texts}"
    )
    # Nada além das linhas DERIVADAS pode desaparecer.
    #
    # A comparação era "só o primário muda" — premissa que deixou de valer quando
    # T24/T25 passaram a valer para TODA cota (o review de aceitação de 2026-10-28
    # mostrou que só o primário as tinha). A setting diz "Show primary PACE
    # detail"; ela governa as leituras derivadas em todos os providers, e é isso
    # que este teste passa a fixar.
    #
    # `Usage` (o dado absoluto) e `detail` do upstream NÃO podem sumir junto.
    removidos = set(on.texts) - set(off.texts)
    proibidos = {t for t in removidos if "of the quota" in t}
    assert not proibidos, (
        f"showMetricDetail=false apagou o consumo absoluto: {sorted(proibidos)}"
    )
    # E tudo o que saiu tem de ser leitura derivada OU o `detail` do upstream.
    # O `detail` entra aqui de propósito: quando não há janela conhecida, ele é a
    # única leitura daquela cota ("0 of 200 used"), e a setting — que se chama
    # "pace detail" — sempre o governou (ver T24 no contrato).
    derivadas = ("Elapsed:", "Pace:", "% of the window")
    fora_do_esperado = {t for t in removidos
                        if not (t in derivadas
                                or "% of the window" in t
                                or "percentage points" in t
                                or "on pace" in t
                                or " used" in t)}
    assert not fora_do_esperado, (
        f"showMetricDetail mexeu em mais que as leituras derivadas: "
        f"{sorted(fora_do_esperado)}"
    )


def test_show_metric_detail_desligado_nao_apaga_conteudo_dos_secundarios(bancada):
    on, off = bancada["detail-on"], bancada["detail-off"]
    assert off.has("GitHub Copilot") and off.has("100%") and off.has("CHAT"), off.texts
    assert off.has("! Z.AI"), "o estado de erro do secundário sumiu com showMetricDetail=false"
    assert on.has("PREMIUM REQUESTS") and off.has("PREMIUM REQUESTS")
    # As métricas dos secundários continuam presentes.
    assert on.find("PREMIUM REQUESTS") and off.find("PREMIUM REQUESTS")


# --------------------------------------------------------------------------- #
# 5. secondaryLabel: nome, código curto e plano (com redação)
# --------------------------------------------------------------------------- #

def test_secondary_label_name_usa_o_nome_exibido(bancada):
    d = bancada["label-name"]
    assert "GitHub Copilot" in d.texts and "Codex · work" in d.texts, d.texts
    assert "ghc" not in d.texts and "gpt" not in d.texts, "o modo 'name' não deve mostrar o código curto"


def test_secondary_label_short_usa_o_codigo_curto(bancada):
    d = bancada["label-short"]
    assert "ghc" in d.texts and "gpt" in d.texts, d.texts
    # O provider em erro carrega o marcador textual "! " antes do rótulo.
    assert any(t.endswith("zai") for t in d.texts), d.texts
    # A setting vale para os SECUNDÁRIOS: nenhum deles pode mostrar o nome exibido.
    assert "GitHub Copilot" not in d.texts, "secundário mostrou o nome no modo 'short'"
    assert "Codex · work" not in d.texts, "secundário mostrou o nome no modo 'short'"
    # O primário preserva o próprio nome (a setting é de rótulo secundário).
    assert "Sonnet" in d.texts, "o primário perdeu o nome no modo 'short'"


def test_secondary_label_plan_usa_o_plano_e_nao_afeta_valores(bancada):
    plano = bancada["label-plan"]
    nome = bancada["label-name"]
    assert "GitHub Copilot individual" in plano.texts, plano.texts
    # Trocar o rótulo não pode mexer nos valores/métricas.
    for valor in ("100%", "0%", "PREMIUM REQUESTS", "CHAT"):
        assert valor in plano.texts, f"{valor!r} sumiu ao trocar o rótulo para 'plan'"
        assert valor in nome.texts


def test_secondary_label_plan_nao_imprime_fragmento_de_chave(bancada):
    """Negativo (non-goal do esforço): o plano cru pode trazer chave mascarada."""
    d = bancada["label-plan"]
    # Antipassividade: sem o provider de plano renderizado, "nada vazou" seria
    # verdade vazia. Exigir a entrada antes de afirmar a ausência do vazamento.
    assert any("openrouter" in t.lower() for t in d.texts), (
        f"o provider de plano não foi renderizado — a ausência de vazamento seria vácua: {d.texts}"
    )
    # O padrão "tipo chave": sequência longa de [A-Za-z0-9_-] sem espaços.
    vazamento = [t for t in d.texts if re.search(r"[A-Za-z0-9_-]{24,}", t)]
    assert not vazamento, f"fragmento de chave vazou no rótulo de plano: {vazamento}"
    for t in d.texts:
        if "openrouter" in t.lower():
            assert "[REDACTED]" in t, f"plano do openrouter sem redação: {t!r}"
            assert not re.search(r"[A-Za-z0-9_\-]{20,}", t), f"token longo intacto: {t!r}"


# --------------------------------------------------------------------------- #
# 6. showSecondaries e maxSecondary
# --------------------------------------------------------------------------- #

def test_show_secondaries_false_suprime_a_lista_mas_preserva_o_primario(bancada):
    on, off = bancada["sec-on"], bancada["sec-off"]
    assert on.has("OTHER PROVIDERS"), "o caso de controle deveria listar secundários"
    assert not off.has("OTHER PROVIDERS"), f"showSecondaries=false ainda listou: {off.texts}"
    # O primário e suas métricas continuam.
    assert off.has("Sonnet") and off.has("SESSION (5H)") and off.has("91%"), off.texts


def test_max_secondary_limita_as_linhas_sem_apagar_o_primario(bancada):
    cap1, cap6 = bancada["cap-1"], bancada["cap-6"]
    assert cap1.has("OTHER PROVIDERS 1/") or cap1.has("OTHER PROVIDERS 1"), (
        f"maxSecondary=1 deveria mostrar 1 secundário: {cap1.find('OTHER PROVIDERS')}"
    )
    assert cap1.has("Sonnet") and cap1.has("91%"), "o primário sumiu com maxSecondary=1"
    assert cap6.has("OTHER PROVIDERS"), "maxSecondary=6 deveria manter a lista"
    assert cap6.has("Sonnet")


# --------------------------------------------------------------------------- #
# 7. Layout observável
# --------------------------------------------------------------------------- #

def test_padding_muda_o_recuo_do_conteudo(bancada):
    assert bancada["pad-0"].lpad == 0
    assert bancada["pad-24"].lpad == 24, f"padding=24 não chegou à view: {bancada['pad-24'].lpad}"


def test_gap_controla_o_espacamento_entre_linhas(bancada):
    assert 2 in bancada["gap-2"].spacings, bancada["gap-2"].spacings
    assert 24 in bancada["gap-24"].spacings, bancada["gap-24"].spacings


# --------------------------------------------------------------------------- #
# 8. Tipografia e status: telemetria curta em mono com tracking; pill
# --------------------------------------------------------------------------- #

def test_telemetria_curta_usa_mono_com_tracking_e_nome_usa_a_display(bancada):
    d = bancada["order-upstream"]
    por_texto = {t: (fam, px, tr, caps) for (t, fam, px, tr, caps) in d.fonts}
    # Nome do provider em display sans.
    assert por_texto["Sonnet"][0] == "Space Grotesk", por_texto.get("Sonnet")
    # Telemetria curta (rótulo de métrica e cooldown) em mono, com tracking > 0 e
    # tamanho pequeno.
    mono_com_tracking = [(t, v) for t, v in por_texto.items() if v[0].startswith("JetBrainsMono")]
    assert mono_com_tracking, "nenhum texto em JetBrains Mono foi renderizado"
    curtos = [(t, v) for t, v in mono_com_tracking if v[1] <= 12 and v[2] > 0]
    assert curtos, f"telemetria curta sem tracking em mono: {mono_com_tracking[:6]}"
    # A linha de detalhe/ritmo não é "telemetria curta" (tamanho maior, sem tracking).
    # T24: o ritmo agora é uma leitura rotulada (`Elapsed:`/`Pace:`), não a prosa
    # antiga do upstream — o invariante de gramática visual é o mesmo.
    detalhe = [t for t in por_texto if "Elapsed:" in t or "Pace:" in t]
    assert detalhe, "linha de ritmo ausente"
    assert por_texto[detalhe[0]][2] == 0, f"a linha longa de ritmo ganhou tracking: {por_texto[detalhe[0]]}"


def test_todos_os_retangulos_visiveis_sao_pilula_ou_fio_de_status(bancada):
    """Pill = raio igual à metade da altura; fio de status = altura 1 e raio 0."""
    d = bancada["order-upstream"]
    assert d.rects, "nenhum retângulo renderizado"
    for r in d.rects:
        campos = dict(part.split("=") for part in r.split("|")[2:])
        altura = int(r.split("|")[1].split("x")[1])
        pill = campos.get("pill") == "true"
        fio = altura == 1 and campos.get("r") == "0"
        assert pill or fio, f"retângulo nem pill nem fio (chamfer/quadrado solto?): {r}"
        if pill:
            assert campos.get("chamfer") == "false", f"retângulo pill classificado como chamfer: {r}"


def test_nenhum_emoji_no_texto_renderizado(bancada):
    """Negativo (gramática visual): sem emoji na superfície."""
    import unicodedata
    texto = " ".join(t for modo in ("order-upstream", "label-plan") for t in bancada[modo].texts)
    suspeitos = []
    for ch in texto:
        if ord(ch) < 0x2000:
            continue
        try:
            nome = unicodedata.name(ch)
        except ValueError:
            nome = "?"
        if any(p in nome for p in ("EMOJI", "PICTOGRAPH", "SMILEY", "SYMBOL")):
            suspeitos.append((ch, nome))
    assert not suspeitos, f"emoji/pictograma renderizado: {suspeitos}"


# --------------------------------------------------------------------------- #
# 9. Valores default e inválidos são seguros
# --------------------------------------------------------------------------- #

def _assinatura(d: Dump) -> list[str]:
    """Dump normalizado: ignora o countdown ao vivo (dependente do relógio)."""
    out = []
    for r in d.records:
        r = re.sub(r"RESET IN [0-9A-Z]+", "RESET IN T", r)
        r = re.sub(r"Resets in [^|]*", "Resets in T", r)
        out.append(r)
    return out


@pytest.mark.parametrize("caso,campo", [
    ("bad-accent", "accent"),
    ("bad-order", "order"),
    ("bad-secondary", "secondaryLabel"),
    ("bad-detail", "showMetricDetail"),
])
def test_valor_invalido_de_setting_cai_no_comportamento_seguro(bancada, caso, campo):
    """Um valor inválido não pode quebrar nem mudar a UI em relação ao default.

    T18: a setting TEM de estar declarada no manifest. Sem esta exigência o teste
    é vacuoso — remover `accent` do manifest faria o caso `bad-accent` continuar
    "caindo no fallback" e passando, sem que houvesse setting alguma para
    validar. Um teste que passa porque a chave não existe não prova nada sobre
    o tratamento de valor inválido.
    """
    settings = {x["key"]: x for x in _manifest()["metadata"]["settings"]}
    assert campo in settings, (
        f"o caso {caso!r} testa a setting {campo!r}, que o manifest NÃO declara — "
        "o teste cairia no fallback por ausência, não por valor inválido"
    )
    invalido = bancada[caso]
    assert _assinatura(invalido) == _assinatura(bancada["label-name"]), (
        f"{campo} inválido mudou a UI renderizada em vez de cair no default seguro"
    )


def test_settings_ausentes_renderizam_a_superficie_sem_quebrar(bancada):
    """Sem nenhuma setting, a view ainda monta a superfície inteira e segura.

    O contrato de T16 exige que o fallback do QML COINCIDA com o manifest:
    `padding` e `gap` sem setting agora dão 12 e 6, iguais aos defaults
    declarados (antes divergiam — 14 e 10 — e "sem setting" desenhava um layout
    diferente de "setting no default", que era o defeito de T16).
    """
    vazio = bancada["vazias"]
    assert vazio.has("Sonnet") and vazio.has("SESSION (5H)") and vazio.has("91%"), (
        f"sem settings o primário não foi renderizado: {vazio.texts[:8]}"
    )
    assert vazio.has("OTHER PROVIDERS"), "sem settings a lista de secundários sumiu"
    assert not [r for r in vazio.records if "VIEW_ERR" in r or "EMIT_ERR" in r]
    # E não pode haver regressão a uma tela vazia/sem métricas.
    assert len(vazio.texts) > 10, f"tela degenerada sem settings: {vazio.texts}"


def test_nenhum_caso_invalido_produziu_erro_de_renderizacao(bancada):
    for nome in ("bad-accent", "bad-order", "bad-secondary", "bad-detail", "vazias"):
        # Antipassividade: um caso que não renderizou nada "não erra" trivialmente.
        assert bancada[nome].has("CLAUDE PRO"), (
            f"{nome}: nada foi renderizado — a ausência de erro seria vácua"
        )
        assert not [r for r in bancada[nome].records if r.startswith("VIEW_ERR") or r.startswith("EMIT_ERR")], (
            f"{nome} produziu erro de renderização"
        )


# --------------------------------------------------------------------------- #
# 10. Efeito observável da ordem no CLI público do coletor (T8)
# --------------------------------------------------------------------------- #

def _collect(argv: list[str]) -> dict:
    assert COLLECTOR.is_file(), f"coletor ausente em {COLLECTOR} — nada a verificar"
    base = [str(COLLECTOR)] if os.access(COLLECTOR, os.X_OK) else [sys.executable, str(COLLECTOR)]
    proc = subprocess.run(base + ["--from-file", str(_fixture())] + argv,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"coletor falhou: rc={proc.returncode} stderr={proc.stderr!r}"
    return json.loads(proc.stdout)


def test_cli_order_upstream_preserva_o_primario_do_relatorio():
    relato = json.loads(_fixture().read_text(encoding="utf-8"))
    dados = _collect(["--order", "upstream"])
    assert dados["primary"]["id"] == relato["primary"]


@pytest.mark.parametrize("modo", ["highest", "lowest"])
def test_cli_ordens_numericas_escolhem_pelo_percentual_headline(modo):
    dados = _collect(["--order", modo])
    prontos = [p for p in dados["all"] if p["status"] == "ready"]
    percentuais = [p["headline_metric"]["percent"] for p in prontos if p.get("headline_metric")]
    esperado = max(percentuais) if modo == "highest" else min(percentuais)
    assert dados["primary"]["headline_metric"]["percent"] == esperado, (
        f"order={modo} deveria expandir {esperado}%; expandiu "
        f"{dados['primary']['headline_metric']['percent']}%"
    )


def test_cli_order_invalido_e_recusado_sem_json_parcial():
    assert COLLECTOR.is_file(), f"coletor ausente em {COLLECTOR} — nada a verificar"
    base = [str(COLLECTOR)] if os.access(COLLECTOR, os.X_OK) else [sys.executable, str(COLLECTOR)]
    proc = subprocess.run(base + ["--from-file", str(_fixture()), "--order", "BOGUS"],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode != 0, "ordem inválida aceita pelo coletor"
    assert proc.stdout.strip() == "", f"JSON parcial emitido com ordem inválida: {proc.stdout[:200]}"


# --------------------------------------------------------------------------- #
# Lacunas de observação (honestidade D5 — o que esta suíte NÃO prova)
# --------------------------------------------------------------------------- #

LACUNAS_DE_OBSERVACAO = """
1. CHAMFER nos elementos interativos: a superfície `framePopout` em density full é
   somente-leitura e, no dump desta bancada, NÃO monta nenhum MouseArea/handler/
   botão (0 registros INTERACTIVE). Sem elemento interativo renderizado não há como
   medir o recorte de canto — "chamfer nos interativos" fica NÃO VERIFICADO aqui e
   depende do real-smoke humano no host.
2. Bounce/emoji: emoji é observável e foi verificado (ausente). O EASING de
   animações NÃO é observável por este caminho (o grafo montado não expôs objetos
   Behavior/Animation enumeráveis), então "sem bounce" não é provado por teste.
3. `pollSeconds`: nenhum timer com o intervalo declarado apareceu na árvore
   renderizada (só o ticker do countdown, 1000 ms). O efeito de pollSeconds não foi
   medido por esta suíte.
4. Accent do TRILHO do medidor: o trilho (alpha ~0.13) permanece tingido pela accent
   do WALLPAPER do host nos três modos (wallpaper/brand/mono) — medido. Os testes
   acima afirmam o invariante sobre os preenchimentos OPACOS (a accent viva); se a
   intenção humana for que o trilho também siga a setting, isso é uma divergência a
   investigar no smoke, não uma falha coberta aqui.
5. Divergência observada (não é falha deste teste): com `pluginSettings` VAZIO a
   view usa recuos internos de padding 14 / gap 10, diferentes dos defaults 12 / 6
   declarados no manifest. O host semeia os defaults do manifest via
   `ryoku-plugins-place`, então esse caminho não é alcançável pela UI; a divergência
   fica registrada para o gate (o oráculo é humano).
6. O host NÃO valida o manifest: uma setting com type desconhecido e um default fora
   das options passam `ryoku plugin validate` com 0 findings (verificado por cópia
   temporária). Os testes de manifest acima são, portanto, a única barreira.
"""
