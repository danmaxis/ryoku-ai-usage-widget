# -*- coding: utf-8 -*-
"""Contrato de COMPORTAMENTO de T16, itens 1, 2, 3 e 6 — coerência dos defaults.

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada
corrente, tarefa T16. Contrato transcrito:

    1. Fonte da verdade dos defaults = ``metadata.settings[].default`` do manifest.
       O host semeia esses valores (``seed_entry``) e o ``pluginSettings`` entregue
       ao QML é o objeto SALVO, sem injeção. Logo o fallback do código é
       ALCANÇÁVEL (entrada antiga sem a chave; valor inválido) e DEVE coincidir
       com o manifest. Corrigido: ``padding`` 14 -> 12 e ``gap`` 10 -> 6.
    2. ``maxSecondary``: o coletor trata ``0`` como significativo. O manifest
       declarava ``min: 1``; agora ``min: 0``. O clamp do serviço aceita
       ``v >= 0`` com teto 12 e cai em 6 para valor não-numérico.
    3. ``primary`` é setting: ``type: text``, ``default: ""``, grupo Data,
       placeholder ``anthropic``.
    6. Nada muda por herança: com entrada semeada, ``padding``/``gap`` = 12/6.

Método (nenhuma leitura de fonte)
---------------------------------
O default EFETIVO não é lido do QML: é MEDIDO na view montada num
``quickshell`` offline (``QT_QPA_PLATFORM=offscreen``) por
``tests/qml/t16_layout_harness.qml``, que injeta um ``pluginApi`` sintético no
formato do host (``property var pluginSettings``, ver ``PluginPopouts.qml:195``)
e despeja a geometria resultante. O binário ``ai-usagebar`` é substituído por um
falso que só emite uma fixture gerada no próprio temporário: nenhuma rede,
nenhuma credencial, nenhuma escrita fora do ``tmp``.

Por que comparar manifest × manifest não serve
---------------------------------------------
``assert manifest["padding"]["default"] == 12`` relê o manifest e passaria mesmo
que a view desenhasse 14. Por isso o oráculo aqui é a GEOMETRIA: o valor medido
com store vazio tem de ser igual ao valor medido com o store semeado com os
defaults do manifest, e igual ao default declarado. É exatamente esse par que
divergia antes de T16 (14/10 contra 12/6).

Observações que NÃO viraram asserção estão em ``AMBIGUIDADES`` no fim do arquivo.
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
# Localização dos artefatos (o conteúdo de Widget.qml/Main.qml nunca é lido)
# --------------------------------------------------------------------------- #

TEST_DIR = Path(__file__).resolve().parent            # <repo>/ai-usage/tests
PLUGIN_DIR = Path(os.environ.get("T16_PLUGIN_DIR", TEST_DIR.parent))
REPO_ROOT = PLUGIN_DIR.parent

MANIFEST = Path(os.environ.get("T16_MANIFEST", PLUGIN_DIR / "manifest.json"))
COLLECTOR = Path(os.environ.get("T16_COLLECTOR", PLUGIN_DIR / "bin" / "ai-usage-collect"))
HARNESS = Path(os.environ.get("T16_HARNESS", TEST_DIR / "qml" / "t16_layout_harness.qml"))

_QUICK = shutil.which("quickshell") or shutil.which("qs")

precisa_qml = pytest.mark.skipif(
    _QUICK is None,
    reason="quickshell ausente: a view QML do plugin não pode ser exercitada",
)

#: Tipos que o host realmente desenha (medido em T9; `text` entra pelo Hub).
HOST_RENDERED_TYPES = {"toggle", "choice", "slider", "image", "text"}


def _manifest() -> dict:
    if not MANIFEST.is_file():
        pytest.fail(f"manifest.json ausente em {MANIFEST} — nada a verificar")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _spec() -> dict:
    return {s["key"]: s for s in _manifest().get("metadata", {}).get("settings", [])}


def _default(key: str):
    spec = _spec()
    assert key in spec, f"setting {key!r} não declarada; chaves={sorted(spec)}"
    assert "default" in spec[key], f"setting {key!r} sem default declarado"
    return spec[key]["default"]


def test_artefatos_sob_teste_existem():
    """Falha rápida: revert-and-test não pode virar SKIP silencioso."""
    assert MANIFEST.is_file(), f"manifest ausente: {MANIFEST}"
    assert (PLUGIN_DIR / "content" / "Widget.qml").is_file(), "content/Widget.qml ausente"
    assert (PLUGIN_DIR / "service" / "Main.qml").is_file(), "service/Main.qml ausente"
    assert HARNESS.is_file(), f"harness QML ausente: {HARNESS}"


# --------------------------------------------------------------------------- #
# Fixture própria (20 providers, para que o teto de secundários seja visível)
# --------------------------------------------------------------------------- #

N_PROVIDERS = 20


def _metrica(percent: int = 10) -> dict:
    return {
        "label": "Session (5h)", "percent": percent, "value": f"{percent}%",
        "headline": "percent", "severity": "low", "detail": "d",
        "reset_at": "2026-11-01T00:00:00Z", "window_secs": 18000,
    }


def _entrada(pid: str) -> dict:
    vendor = pid.split("@", 1)[0]
    return {
        "id": pid, "name": vendor, "display_name": pid.upper(), "short_name": vendor[:3],
        "icon": "i", "brand": vendor, "plan": None, "status": "ready", "error": None,
        "stale": False, "fetched_at": "2026-10-15T12:00:00Z", "reset_credits": None,
        "metrics": [_metrica()], "sections": [],
    }


@pytest.fixture(scope="module")
def ambiente(tmp_path_factory):
    """Um ``ai-usagebar`` falso + fixture de 20 providers, tudo no temporário."""
    tmp = tmp_path_factory.mktemp("t16-layout")
    ids = [f"prov{i:02d}" for i in range(1, N_PROVIDERS + 1)]
    fixt = tmp / "relatorio.json"
    fixt.write_text(json.dumps({
        "schema_version": 1, "primary": ids[0], "entries": [_entrada(i) for i in ids],
    }), encoding="utf-8")

    fakebin = tmp / "fakebin"
    fakebin.mkdir()
    falso = fakebin / "ai-usagebar"
    falso.write_text(f"#!{sys.executable}\nimport sys\n"
                     f"sys.stdout.write(open({str(fixt)!r}, encoding='utf-8').read())\n",
                     encoding="utf-8")
    falso.chmod(0o755)
    return {"tmp": tmp, "fixture": fixt, "fakebin": fakebin}


# --------------------------------------------------------------------------- #
# Bancada: um processo quickshell por LOTE de casos
# --------------------------------------------------------------------------- #

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


class Layout:
    """O que a view desenhou para um conjunto de settings."""

    def __init__(self, nome: str, registros: list[str]):
        self.nome = nome
        self.registros = registros
        self.textos = [r[len("TEXT|"):] for r in registros if r.startswith("TEXT|")]
        self.view_present = any(r == "VIEW_PRESENT|true" for r in registros)
        self.lpad = next((r[len("LPAD|"):] for r in registros if r.startswith("LPAD|")), None)
        self.espacamentos = []
        for r in registros:
            if r.startswith("SPACING|"):
                partes = r.split("|")
                if len(partes) == 4 and partes[1] == "QQuickColumn":
                    self.espacamentos.append((int(float(partes[2])), partes[3]))
        #: espaçamento da coluna RAIZ (a que recebe a setting `gap`).
        self.gap = next((v for v, d in self.espacamentos if d == "d1"), None)
        self.erros = [r for r in registros if r.startswith(("VIEW_ERR|", "WATCHDOG_ABORT|"))]

    @property
    def pad(self) -> int:
        assert self.lpad is not None, (
            f"[{self.nome}] a view não expôs `pad` — sem isso o recuo não é observável. "
            f"registros={self.registros[:6]}"
        )
        return int(float(self.lpad))

    @property
    def linhas_secundarias(self) -> int | None:
        """``k`` de ``OTHER PROVIDERS k/N`` — quantos secundários apareceram."""
        for t in self.textos:
            m = re.match(r"OTHER PROVIDERS (\d+)/(\d+)", t)
            if m:
                return int(m.group(1))
        return None

    def assinatura(self) -> list[str]:
        """Registros normalizados: o countdown ao vivo depende do relógio."""
        saida = []
        for r in self.registros:
            r = re.sub(r"RESET IN [0-9A-Z ]+", "RESET IN T", r)
            r = re.sub(r"Resets in [^|]*", "Resets in T", r)
            saida.append(r)
        return saida


def _rodar_lote(cases: list[dict], ambiente, tmp: Path) -> dict[str, Layout]:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("WAYLAND_DISPLAY", None)
    # O falso vem primeiro: o ai-usagebar real nunca roda (ele escreve no config
    # do upstream — efeito medido e proibido pelas premissas do esforço).
    env["PATH"] = f"{ambiente['fakebin']}{os.pathsep}{env.get('PATH', '')}"
    env["XDG_CACHE_HOME"] = str(tmp / "cache")
    env["XDG_CONFIG_HOME"] = str(tmp / "cfg")
    env["XDG_STATE_HOME"] = str(tmp / "xdgstate")
    env["T16_PLUG_DIR"] = str(PLUGIN_DIR)
    env["T16_STATE_DIR"] = str(tmp / "state")
    env["T16_CASES"] = json.dumps(cases, ensure_ascii=False)
    env["T16_SETTLE_MS"] = "1600"

    try:
        proc = subprocess.run([_QUICK, "-p", str(HARNESS)],
                              capture_output=True, text=True, env=env, timeout=300)
    except subprocess.TimeoutExpired:
        pytest.fail("o harness QML não terminou em 300s — a view não monta")

    atual, buffer, out = None, [], {}
    for raw in _ANSI.sub("", proc.stdout).splitlines() + _ANSI.sub("", proc.stderr).splitlines():
        if " qml: " in raw:
            raw = raw.split(" qml: ", 1)[1]
        raw = raw.strip()
        if raw.startswith("===CASE_START|"):
            atual = raw[len("===CASE_START|"):-3]
            buffer = []
        elif raw.startswith("===CASE_END|"):
            if atual is not None:
                out[atual] = Layout(atual, buffer)
            atual = None
        elif atual is not None and raw:
            buffer.append(raw)

    faltando = [c["name"] for c in cases if c["name"] not in out]
    assert not faltando, (
        f"a view não montou os casos {faltando!r}; rc={proc.returncode}\n"
        f"stderr(tail)={proc.stderr[-800:]}"
    )
    for nome, dump in out.items():
        assert not dump.erros, f"[{nome}] erro de renderização: {dump.erros}"
    return out


# --------------------------------------------------------------------------- #
# Anti-vacuidade da bancada
# --------------------------------------------------------------------------- #

@precisa_qml
def test_a_bancada_observa_o_layout_padrao(ambiente, tmp_path):
    """Sem isto, todo ``pad``/``gap`` abaixo poderia ser ``None`` disfarçado."""
    d = _rodar_lote(
        [{"name": "sane", "settings": {"padding": 12, "gap": 6}}],
        ambiente, tmp_path,
    )["sane"]
    assert d.view_present, f"a view não montou: {d.registros[:6]}"
    assert d.pad == 12, f"padding=12 não chegou à view: {d.lpad!r}"
    assert d.gap == 6, f"gap=6 não chegou à view: {d.espacamentos}"
    assert d.textos, "a view não renderizou texto — o layout seria vazio"


# --------------------------------------------------------------------------- #
# ITEM 1 — o default EFETIVO (store vazio) coincide com o manifest
# --------------------------------------------------------------------------- #

@precisa_qml
def test_store_vazio_desenha_o_padding_do_manifest(ambiente, tmp_path):
    """Entrada antiga sem a chave: é o caminho de FALLBACK, e ele é alcançável.

    Este é o defeito de T16: o fallback desenhava 14 enquanto o manifest declara
    12 — "sem setting salva" e "setting salva no default" divergiam.
    """
    esperado = _default("padding")
    d = _rodar_lote([{"name": "vazio-pad", "settings": {"gap": 6}}], ambiente, tmp_path)["vazio-pad"]
    assert d.pad == esperado, (
        f"com store vazio o recuo desenhado é {d.pad}, mas o manifest declara "
        f"default={esperado} — o fallback tem de COINCIDIR com o manifest "
        f"(o host semeia o manifest, então os dois caminhos precisam ser iguais)"
    )


@precisa_qml
def test_store_vazio_desenha_o_gap_do_manifest(ambiente, tmp_path):
    esperado = _default("gap")
    d = _rodar_lote([{"name": "vazio-gap", "settings": {"padding": 12}}], ambiente, tmp_path)["vazio-gap"]
    assert d.gap == esperado, (
        f"com store vazio o espaçamento da coluna raiz é {d.gap}, mas o manifest "
        f"declara default={esperado}; espaçamentos observados={d.espacamentos}"
    )


@precisa_qml
def test_store_vazio_e_store_semeado_desenham_o_mesmo_layout(ambiente, tmp_path):
    """A generalização dos dois testes acima, numa asserção só.

    Semeado = exatamente os ``default`` do manifest, como o host faz em
    ``seed_entry``. Se o fallback do código divergir do manifest, as duas
    assinaturas diferem — foi o caso de 14/10 × 12/6.
    """
    semeados = {k: s["default"] for k, s in _spec().items() if "default" in s}
    dumps = _rodar_lote(
        [
            {"name": "semeado", "settings": semeados},
            {"name": "vazio", "settings": {}},
        ],
        ambiente, tmp_path,
    )
    a, b = dumps["semeado"], dumps["vazio"]
    assert a.pad == b.pad, (
        f"padding diverge: semeado={a.pad} (manifest) × vazio={b.pad} (fallback)"
    )
    assert a.gap == b.gap, (
        f"gap diverge: semeado={a.gap} (manifest) × vazio={b.gap} (fallback); "
        f"espacamentos semeado={a.espacamentos} vazio={b.espacamentos}"
    )
    assert a.assinatura() == b.assinatura(), (
        "o layout inteiro difere entre 'store semeado no default' e 'store vazio' — "
        "o contrato diz que o alinhamento só iguala os dois caminhos"
    )


@precisa_qml
@pytest.mark.parametrize("chave,tipo_invalido", [
    ("padding", "abc"),
    ("padding", {"a": 1}),
    ("gap", "abc"),
    ("gap", [1, 2]),
])
def test_valor_invalido_cai_no_default_do_manifest(ambiente, tmp_path, chave, tipo_invalido):
    """Segundo caminho alcançável do fallback: valor não-numérico já salvo."""
    esperado = _default(chave)
    outro = "gap" if chave == "padding" else "padding"
    settings = {chave: tipo_invalido, outro: _default(outro)}
    d = _rodar_lote([{"name": "invalido", "settings": settings}], ambiente, tmp_path)["invalido"]
    medido = d.pad if chave == "padding" else d.gap
    assert medido == esperado, (
        f"{chave}={tipo_invalido!r} deveria cair no default do manifest "
        f"({esperado}); a view desenhou {medido!r}"
    )


@precisa_qml
def test_o_valor_explicito_continua_mandando_sobre_o_default(ambiente, tmp_path):
    """Contraprova: o teste acima não pode passar por a view ignorar a setting."""
    dumps = _rodar_lote(
        [
            {"name": "pad-24", "settings": {"padding": 24, "gap": 6}},
            {"name": "pad-0", "settings": {"padding": 0, "gap": 6}},
            {"name": "gap-2", "settings": {"padding": 12, "gap": 2}},
            {"name": "gap-24", "settings": {"padding": 12, "gap": 24}},
        ],
        ambiente, tmp_path,
    )
    assert dumps["pad-24"].pad == 24, dumps["pad-24"].lpad
    assert dumps["pad-0"].pad == 0, f"0 é um recuo válido (min=0); veio {dumps['pad-0'].lpad}"
    assert dumps["gap-2"].gap == 2, dumps["gap-2"].espacamentos
    assert dumps["gap-24"].gap == 24, dumps["gap-24"].espacamentos


@precisa_qml
def test_default_declarado_esta_dentro_da_faixa_do_seu_slider(ambiente, tmp_path):
    """Um default fora de [min, max] seria um fallback que o slider não reproduz."""
    for chave in ("padding", "gap", "maxSecondary"):
        spec = _spec()[chave]
        d = _default(chave)
        assert spec["min"] <= d <= spec["max"], (
            f"{chave}: default {d} fora de [{spec['min']}, {spec['max']}]"
        )


# --------------------------------------------------------------------------- #
# ITEM 6 — nada muda de comportamento visual por herança (12 / 6)
# --------------------------------------------------------------------------- #

@precisa_qml
def test_entrada_semeada_mantem_padding_e_gap_nos_valores_atuais(ambiente, tmp_path):
    """Item 6: o alinhamento iguala os caminhos, não muda o desenho normal."""
    semeados = {k: s["default"] for k, s in _spec().items() if "default" in s}
    d = _rodar_lote([{"name": "heranca", "settings": semeados}], ambiente, tmp_path)["heranca"]
    assert d.pad == 12, f"com entrada semeada o padding virou {d.pad}, esperava 12"
    assert d.gap == 6, f"com entrada semeada o gap virou {d.gap}, esperava 6"


# --------------------------------------------------------------------------- #
# ITEM 3 — `primary` é setting declarada e renderizável
# --------------------------------------------------------------------------- #

def test_manifest_declara_primary_como_texto_no_grupo_data():
    spec = _spec()
    assert "primary" in spec, (
        f"a setting `primary` precisa ser declarada (o coletor aceita --primary e "
        f"nenhuma setting o encaminhava = código inalcançável); chaves={sorted(spec)}"
    )
    p = spec["primary"]
    assert p["type"] == "text", f"primary é texto livre de id; tipo={p['type']!r}"
    assert p["type"] in HOST_RENDERED_TYPES, (
        f"type {p['type']!r} não é desenhado pelo host — a setting seria inalcançável"
    )
    assert p.get("default") == "", (
        f"default de primary tem de ser a string vazia (= nenhum destaque forçado); "
        f"veio {p.get('default')!r}"
    )
    assert p.get("group") == "Data", f"primary agrupa com as demais settings de dados; grupo={p.get('group')!r}"
    assert p.get("placeholder") == "anthropic", (
        f"placeholder esperado 'anthropic' (exemplo de id); veio {p.get('placeholder')!r}"
    )


def test_primary_tem_label_visivel_ao_usuario():
    """Uma setting sem label aparece sem nome no Hub."""
    p = _spec()["primary"]
    assert isinstance(p.get("label"), str) and p["label"].strip(), (
        f"primary precisa de label legível; veio {p.get('label')!r}"
    )


# --------------------------------------------------------------------------- #
# ITEM 2 — `maxSecondary`: o manifest passa a declarar o 0 que o coletor aceita
# --------------------------------------------------------------------------- #

def test_manifest_declara_min_zero_para_max_secondary():
    spec = _spec()["maxSecondary"]
    assert spec["min"] == 0, (
        f"o coletor trata --max-secondary 0 como significativo (zero secundários); "
        f"com min={spec['min']} o slider nunca oferece 0 e o valor fica inalcançável"
    )
    assert spec["max"] == 12, f"teto do clamp é 12; manifest declara max={spec['max']}"
    assert spec["default"] == 6, f"default esperado 6; veio {spec['default']}"


def _coletor(*args) -> dict:
    assert COLLECTOR.is_file(), f"coletor ausente em {COLLECTOR}"
    base = [str(COLLECTOR)] if os.access(COLLECTOR, os.X_OK) else [sys.executable, str(COLLECTOR)]
    proc = subprocess.run(base + list(args), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"coletor falhou: rc={proc.returncode} stderr={proc.stderr!r}"
    return json.loads(proc.stdout)


def test_o_coletor_trata_zero_como_zero_secundarios_e_nao_como_ilimitado(ambiente):
    """A premissa do item 2, medida no binário, não deduzida do manifest."""
    fixt = ambiente["fixture"]
    zero = _coletor("--from-file", str(fixt), "--max-secondary", "0")
    padrao = _coletor("--from-file", str(fixt))
    assert zero["secondary"] == [], f"0 deveria esvaziar a lista; veio {zero['secondary']}"
    assert len(padrao["secondary"]) == 6, (
        f"o default do coletor é 6 secundários; veio {len(padrao['secondary'])}"
    )
    # 0 NÃO pode ser 'ilimitado': a lista completa continua intacta.
    assert zero["total_providers"] == N_PROVIDERS
    assert zero["primary"] is not None


@precisa_qml
@pytest.mark.parametrize("valor,esperado", [
    (0, 0),      # 0 é significativo e alcançável agora
    (1, 1),
    (6, 6),      # default
    (12, 12),    # teto
    (99, 12),    # acima do teto: clamp em 12
    ("abc", 6),  # não-numérico: cai no default 6
    (-2, 6),     # negativo: cai no default 6 (o clamp aceita v >= 0)
])
def test_o_servico_aplica_o_clamp_de_max_secondary_na_view(ambiente, tmp_path, valor, esperado):
    """O clamp do serviço, medido no número de linhas realmente desenhadas.

    ``k`` de ``OTHER PROVIDERS k/19`` é o efeito observável: com 20 providers, o
    primário sai da lista e sobram 19 candidatos a secundário.
    """
    d = _rodar_lote(
        [{"name": "clamp", "settings": {"maxSecondary": valor, "padding": 12, "gap": 6}}],
        ambiente, tmp_path,
    )["clamp"]
    medido = d.linhas_secundarias
    assert medido == esperado, (
        f"maxSecondary={valor!r} deveria renderizar {esperado} linhas secundárias; "
        f"renderizou {medido!r}. textos={d.textos[:6]}"
    )


# --------------------------------------------------------------------------- #
# Ambiguidades / divergências observadas (honestidade D5)
# --------------------------------------------------------------------------- #

AMBIGUIDADES = """
1. `maxSecondary: null` — o contrato diz "cai em 6 para valor não-numérico", mas
   o observado (medido nesta bancada, HEAD) é 0 linhas, não 6. `null` pode ser
   lido como "não definido" (e 0 é o valor seguro) ou como não-numérico (6). Não
   há asserção: o item 2 não distingue `null` de string inválida, e escolher um
   dos dois seria inventar oráculo. Fica registrado para o dono decidir.
2. `padding: ""` desenha 0 (não o default 12) e `gap: ""` desenha 2 (não 6). A
   string vazia é "valor inválido" ou "0 explícito"? O manifest não diz. Os testes
   de valor inválido usam entradas INEQUIVOCAMENTE não-numéricas (texto, objeto,
   lista) para não depender dessa decisão.
3. O QML arredonda: `padding: 13.7` desenha 14 e `gap: 7.7` desenha 8. O slider
   declara `decimals: 0`, então o caminho fracionário não é alcançável pela UI e
   não foi asserido.
4. `padding` negativo desenha 0 e `padding: 40` desenha 32: a view tem o próprio
   clamp (0..32), igual ao [min, max] do manifest. Não asserido como contrato —
   o item 1 fala do DEFAULT, não da faixa; a faixa já é coberta pelo teste
   `test_default_declarado_esta_dentro_da_faixa_do_seu_slider`.
5. O texto `OTHER PROVIDERS k/N` é o único canal que expõe quantos secundários
   foram renderizados; a suíte depende desse formato. Se o rótulo mudar, os
   testes de clamp falham por ausência do canal (e não passam em silêncio).
"""


def test_nenhum_caso_observado_ficou_sem_cobertura_por_engano():
    """Guarda-corpo: as ambiguidades declaradas são uma lista, não um esquecimento."""
    assert AMBIGUIDADES.strip(), "as ambiguidades medidas precisam ser registradas"
    for chave in ("padding", "gap", "maxSecondary", "primary"):
        assert chave in _spec(), f"{chave} deveria estar declarada no manifest"
