# -*- coding: utf-8 -*-
"""Contrato de COMPORTAMENTO de T15, item 7 — a setting chega ao argv do coletor.

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada 2,
tarefa T15. Contrato transcrito (item 7):

    ``service/Main.qml`` encaminha ``--order manual --sequence <valor da setting>``
    quando a setting ``order`` vale ``manual``, com o texto de ``orderSequence``.
    Setting ``orderSequence`` ausente ou vazia com ``order: manual`` → NÃO passa
    ``--sequence``; o coletor trata como sequência vazia. Não pode virar erro de uso.

Método (nenhuma leitura de fonte)
---------------------------------
1. Copia a pasta do plugin para um diretório temporário e substitui o
   ``bin/ai-usage-collect`` da CÓPIA por um GRAVADOR: ele anota o próprio argv
   (uma linha JSON por invocação) e responde um JSON no formato do contrato.
2. Monta o ``service/Main.qml`` da CÓPIA num ``quickshell`` offline
   (``QT_QPA_PLATFORM=offscreen``) via ``tests/qml/t15_argv_harness.qml``, com um
   ``pluginApi`` sintético que injeta as settings do caso.
3. Lê o registro e verifica o ARGV que o serviço realmente montou.
4. Prova de efeito: roda o COLETOR DE VERDADE (o do repositório, intocado) com o
   argv registrado + ``--from-file`` da fixture própria, exigindo rc 0. Isso é o
   que transforma "o argv parece certo" em "o argv não é erro de uso e produz a
   ordem pedida" — a metade que o item 7 nomeia explicitamente.

Ambiguidade resolvida por ABERTURA, não por invenção
----------------------------------------------------
O item 1 exige rc 2 para ``--order manual`` SEM ``--sequence``; o item 7 proíbe
virar erro de uso quando ``orderSequence`` está vazia. As duas frases não podem
valer para o mesmo argv. Por isso os casos de sequência vazia/ausente aceitam
DUAS formas — flag ausente, ou ``--sequence ""`` (que o item 2 declara válida) —
e exigem apenas o que ambos os itens concordam: rc 0 e a ordem do relatório.
Ver ``AMBIGUIDADES``.
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
# Localização dos artefatos (o conteúdo de Main.qml nunca é lido)
# --------------------------------------------------------------------------- #

TEST_DIR = Path(__file__).resolve().parent          # <repo>/ai-usage/tests
PLUGIN_DIR = Path(os.environ.get("T15_PLUGIN_DIR", TEST_DIR.parent))   # <repo>/ai-usage
REPO_ROOT = PLUGIN_DIR.parent                       # <repo>
HARNESS = Path(os.environ.get("T15_HARNESS", TEST_DIR / "qml" / "t15_argv_harness.qml"))

#: O coletor de verdade: é ele que julga se o argv produzido é erro de uso.
COLETOR_REAL = Path(os.environ.get("T15_COLLECTOR", PLUGIN_DIR / "bin" / "ai-usage-collect"))

_QUICK = shutil.which("quickshell") or shutil.which("qs")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

pytestmark = pytest.mark.skipif(
    _QUICK is None,
    reason="quickshell ausente: o serviço QML não pode ser exercitado",
)

# --------------------------------------------------------------------------- #
# Fixture própria (ordem do relatório deliberadamente não trivial)
# --------------------------------------------------------------------------- #

ORDEM_RELATORIO = ["zulu", "alpha", "mike", "kilo", "echo", "whiskey", "openai@work"]


def _metrica(percent=10) -> dict:
    return {
        "label": "Session (5h)", "percent": percent, "value": f"{percent}%",
        "headline": "percent", "severity": "low", "detail": "d",
        "reset_at": "2026-11-01T00:00:00Z", "window_secs": 18000,
    }


def _entrada(pid, *, status="ready", metrics=None) -> dict:
    vendor = pid.split("@", 1)[0]
    return {
        "id": pid, "name": vendor, "display_name": pid, "short_name": vendor[:3],
        "icon": "i", "brand": vendor, "plan": None, "status": status,
        "error": "sem credencial (fixture)" if status == "error" else None,
        "stale": False,
        "fetched_at": "2026-10-15T12:00:00Z" if status == "ready" else None,
        "reset_credits": None,
        "metrics": [_metrica()] if metrics is None else metrics,
        "sections": [],
    }


@pytest.fixture(scope="module")
def fixture_relatorio(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("t15argv-fixture")
    payload = {"schema_version": 1, "primary": "alpha", "entries": [
        _entrada("zulu"),
        _entrada("alpha"),
        _entrada("mike", status="error", metrics=[]),
        _entrada("kilo", metrics=[]),
        _entrada("echo"),
        _entrada("whiskey"),
        _entrada("openai@work"),
    ]}
    destino = tmp / "relatorio.json"
    destino.write_text(json.dumps(payload), encoding="utf-8")
    return destino


# --------------------------------------------------------------------------- #
# O gravador: ocupa o lugar do coletor na CÓPIA do plugin
# --------------------------------------------------------------------------- #

_GRAVADOR = r'''#!{python}
# Gravador de argv instalado por ai-usage/tests/test_t15_setting_argv_isolado.py.
# Não é o coletor: anota o próprio argv e devolve um JSON no formato do contrato.
import json, os, sys

registro = os.environ.get("T15_ARGV_LOG") or ""
if registro:
    with open(registro, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd()}}) + "\n")

provider = {{
    "id": "zulu", "vendor": "zulu", "account": None, "display_name": "zulu",
    "short_name": "zul", "icon": "i", "plan": "", "status": "ready",
    "stale": False, "fetched_at": None, "error": "", "metrics": [],
    "headline_metric": None, "has_reset_credits": False,
}}
out = {{
    "schema": 1,
    "primary": provider,
    "secondary": [],
    "all": [provider],
    "total_providers": 1,
    "with_issues": 0,
}}
sys.stdout.write(json.dumps(out) + "\n")
'''


def _copia_com_gravador(tmp: Path) -> tuple[Path, Path]:
    """Copia a árvore do plugin e troca o coletor pelo gravador. Devolve (cópia, log)."""
    destino = tmp / "plugin"
    shutil.copytree(PLUGIN_DIR, destino,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    log = tmp / "argv.log"
    coletor = destino / "bin" / "ai-usage-collect"
    coletor.parent.mkdir(parents=True, exist_ok=True)
    coletor.write_text(_GRAVADOR.format(python=sys.executable), encoding="utf-8")
    coletor.chmod(0o755)
    return destino, log


# --------------------------------------------------------------------------- #
# Observação
# --------------------------------------------------------------------------- #


class Invocacao:
    def __init__(self, argv: list[str]):
        self.argv = argv

    def valor(self, flag: str):
        """Valor de uma flag, ou ``None`` se ausente. Aceita ``--flag=valor``."""
        for i, a in enumerate(self.argv):
            if a == flag:
                return self.argv[i + 1] if i + 1 < len(self.argv) else ""
            if a.startswith(flag + "="):
                return a.split("=", 1)[1]
        return None

    def tem(self, flag: str) -> bool:
        return self.valor(flag) is not None

    def __repr__(self) -> str:
        return f"<argv {self.argv}>"


class Servico:
    """Resultado de um caso: invocações observadas + o que a instância reportou."""

    def __init__(self, nome: str, invocacoes: list[Invocacao], registros: list[str]):
        self.nome = nome
        self.invocacoes = invocacoes
        self.registros = registros
        self.textos = [r.split("|", 1)[1] for r in registros if r.startswith("TEXT|")]
        self.erros = [r for r in registros if r.startswith("VIEW_ERR|")]

        def campo(tag):
            for r in registros:
                if r.startswith(tag + "|"):
                    return r.split("|", 1)[1]
            return None

        self.main_present = campo("MAIN_PRESENT") == "true"
        self.error_kind = campo("MAIN_ERRORKIND")
        self.last_error = campo("MAIN_LASTERROR") or ""
        self.model_null = campo("MAIN_MODEL_NULL")
        self.order = [x for x in (campo("MAIN_ORDER") or "").split(",") if x]
        self.view_present = campo("VIEW_PRESENT") == "true"
        self.ended = any(r.startswith("END|") for r in registros)

    @property
    def primeira(self) -> Invocacao:
        assert self.invocacoes, (
            f"[{self.nome}] o coletor da cópia nunca foi invocado — sem argv não há "
            f"nada a verificar. registros={self.registros[-6:]}"
        )
        return self.invocacoes[0]


def _parse(stdout: str) -> list[str]:
    registros = []
    for raw in _ANSI.sub("", stdout).splitlines():
        if " qml: " in raw:
            raw = raw.split(" qml: ", 1)[1]
        raw = raw.strip()
        if raw:
            registros.append(raw)
    return registros


def _rodar(
    nome: str,
    settings: dict,
    tmp: Path,
    *,
    ordem_cfg: dict | None = None,
) -> Servico:
    """Um processo quickshell offline por caso (a config do processo muda a cada caso)."""
    copia, log = _copia_com_gravador(tmp)
    log.write_text("", encoding="utf-8")

    # ai-usagebar falso: se algo além do coletor procurar o binário, ele responde
    # a fixture. Nenhum processo do upstream real é executado.
    fakebin = tmp / "fakebin"
    fakebin.mkdir(parents=True, exist_ok=True)
    falso = fakebin / "ai-usagebar"
    falso.write_text(f"#!{sys.executable}\nprint('{{}}')\n", encoding="utf-8")
    falso.chmod(0o755)

    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("WAYLAND_DISPLAY", None)
    env["PATH"] = f"{fakebin}{os.pathsep}{env.get('PATH', '')}"
    env["XDG_CACHE_HOME"] = str(tmp / "cache")
    env["XDG_CONFIG_HOME"] = str(tmp / "cfg")
    env["XDG_STATE_HOME"] = str(tmp / "xdgstate")
    env["T15_ARGV_LOG"] = str(log)
    env["T15_PLUG_DIR"] = str(copia)
    env["T15_SETTINGS"] = json.dumps(settings, ensure_ascii=False)
    env["T15_STATE_DIR"] = str(tmp / "state")

    try:
        proc = subprocess.run([_QUICK, "-p", str(HARNESS)],
                              capture_output=True, text=True, env=env, timeout=180)
    except subprocess.TimeoutExpired:
        pytest.fail(f"[{nome}] o harness QML não terminou em 180s — o serviço não montou")

    registros = _parse(proc.stdout + proc.stderr)
    invocacoes = []
    for linha in log.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            invocacoes.append(Invocacao(json.loads(linha)["argv"]))
        except (json.JSONDecodeError, KeyError):  # pragma: no cover
            pytest.fail(f"[{nome}] registro de argv ilegível: {linha!r}")
    return Servico(nome, invocacoes, registros)


def _argv_para_o_coletor_real(invocacao: Invocacao, fixture: Path):
    """Roda o coletor DE VERDADE com o argv registrado (+ --from-file)."""
    assert COLETOR_REAL.is_file(), f"coletor ausente em {COLETOR_REAL}"
    args = list(invocacao.argv)
    # o serviço roda sem --from-file (relatório real); aqui a entrada é a fixture
    if "--from-file" in args:
        i = args.index("--from-file")
        args[i + 1] = str(fixture)
    else:
        args = ["--from-file", str(fixture)] + args
    return subprocess.run([sys.executable, str(COLETOR_REAL)] + args,
                          capture_output=True, text=True, timeout=60)


def _ordem_efetiva(invocacao, fixture: Path) -> list[str]:
    proc = _argv_para_o_coletor_real(invocacao, fixture)
    assert proc.returncode == 0, (
        f"o argv que o serviço montou é ERRO DE USO para o coletor "
        f"(rc={proc.returncode}) — item 7 diz que não pode.\n"
        f"argv={invocacao.argv}\nstderr={proc.stderr!r}"
    )
    return [p["id"] for p in json.loads(proc.stdout)["all"]]


_BASE = {
    "accent": "wallpaper", "order": "upstream", "showMetricDetail": True,
    "secondaryLabel": "name", "showSecondaries": True, "maxSecondary": 6,
    "padding": 12, "gap": 6, "pollSeconds": 300,
}


# --------------------------------------------------------------------------- #
# 0. Anti-vacuidade da bancada
# --------------------------------------------------------------------------- #


#: Flags que o coletor declara em ``--help`` — o gravador só deve receber estas.
FLAGS_CONHECIDAS = {"--from-file", "--primary", "--order", "--sequence", "--max-secondary", "-h", "--help"}


def test_o_gravador_ocupa_o_lugar_do_coletor_e_registra_o_argv(tmp_path):
    """Se o gravador não for invocado, todos os testes abaixo seriam vácuos."""
    s = _rodar("sanity", dict(_BASE), tmp_path / "a")
    assert s.main_present, f"o serviço não montou: {s.registros[-8:]}"
    assert s.invocacoes, "o coletor da cópia nunca foi chamado — a bancada não observa nada"
    # O argv observado é do COLETOR (flags dele), não do ai-usagebar.
    for a in s.primeira.argv:
        if a.startswith("-"):
            assert a in FLAGS_CONHECIDAS, (
                f"argv com flag que não é do coletor: {a!r} em {s.primeira.argv}"
            )
    assert s.primeira.valor("--sequence") is None, (
        f"o caso base (order=upstream) não declara sequência; argv={s.primeira.argv}"
    )


def test_a_bancada_realmente_usa_a_copia_e_nao_o_coletor_do_repositorio(tmp_path):
    copia, log = _copia_com_gravador(tmp_path / "b")
    assert (copia / "bin" / "ai-usage-collect").read_text(encoding="utf-8").startswith("#!"), (
        "o coletor da cópia deveria ser o gravador"
    )
    assert copia.resolve() != PLUGIN_DIR.resolve()


# --------------------------------------------------------------------------- #
# 1. order=manual + orderSequence preenchida -> --order manual --sequence <valor>
# --------------------------------------------------------------------------- #


def test_order_manual_encaminha_a_sequencia_da_setting(tmp_path, fixture_relatorio):
    s = _rodar("manual-sequencia", dict(_BASE, order="manual", orderSequence="echo,zulu"),
               tmp_path / "c")
    inv = s.primeira
    assert inv.valor("--order") == "manual", (
        f"com order=manual o argv precisa levar ``--order manual``; argv={inv.argv}"
    )
    assert inv.valor("--sequence") == "echo,zulu", (
        f"a setting orderSequence deve chegar verbatim em ``--sequence``; argv={inv.argv}"
    )
    assert _ordem_efetiva(inv, fixture_relatorio) == [
        "echo", "zulu", "alpha", "mike", "kilo", "whiskey", "openai@work"
    ], "a sequência não produziu a ordem esperada no coletor real"


def test_a_sequencia_preserva_os_ids_na_ordem_declarada(tmp_path):
    """O que precisa sobreviver é a ORDEM dos ids, não a fiação exata da string.

    (Observado, e por isso não exigido: o serviço apara os espaços das PONTAS do
    valor antes de encaminhar — ``"  Echo , ZULU  "`` chega como ``"Echo , ZULU"``.
    Como o coletor também apara cada id, o efeito é idêntico; exigir o texto cru
    seria inventar oráculo. O que NÃO pode acontecer é reordenar, juntar, cortar
    ou descartar ids.)
    """
    bruto = "  Echo , ZULU  "
    s = _rodar("manual-bruto", dict(_BASE, order="manual", orderSequence=bruto), tmp_path / "d")
    valor = s.primeira.valor("--sequence")
    assert valor is not None, f"order=manual com sequência precisa encaminhar --sequence; argv={s.primeira.argv}"
    encaminhados = [t.strip().lower() for t in valor.split(",") if t.strip()]
    assert encaminhados == ["echo", "zulu"], (
        f"os ids declarados (na ordem declarada) precisam chegar intactos; veio {encaminhados!r}"
    )


def test_sequencia_de_um_id_so_chega_inteira(tmp_path, fixture_relatorio):
    s = _rodar("manual-um", dict(_BASE, order="manual", orderSequence="whiskey"), tmp_path / "e")
    assert s.primeira.valor("--sequence") == "whiskey", s.primeira.argv
    assert _ordem_efetiva(s.primeira, fixture_relatorio)[0] == "whiskey"


# --------------------------------------------------------------------------- #
# 2. orderSequence ausente/vazia com order=manual -> sem erro de uso
# --------------------------------------------------------------------------- #


def _sem_sequencia_significativa(inv: Invocacao) -> bool:
    """Aceita as duas formas que os itens 1 e 7 deixam abertas."""
    valor = inv.valor("--sequence")
    return valor is None or valor.strip() == ""


def test_order_manual_com_sequencia_ausente_nao_vira_erro_de_uso(tmp_path, fixture_relatorio):
    settings = dict(_BASE, order="manual")          # sem a chave orderSequence
    s = _rodar("manual-sem-setting", settings, tmp_path / "f")
    assert s.primeira.valor("--order") == "manual", (
        f"order=manual precisa continuar indo como manual; argv={s.primeira.argv}"
    )
    assert _sem_sequencia_significativa(s.primeira), (
        f"sem orderSequence o serviço não pode mandar uma sequência inventada; argv={s.primeira.argv}"
    )
    assert _ordem_efetiva(s.primeira, fixture_relatorio) == ORDEM_RELATORIO, (
        "sequência vazia equivale à ordem do relatório (item 2)"
    )


def test_order_manual_com_sequencia_vazia_nao_vira_erro_de_uso(tmp_path, fixture_relatorio):
    s = _rodar("manual-vazia", dict(_BASE, order="manual", orderSequence=""), tmp_path / "g")
    assert s.primeira.valor("--order") == "manual", s.primeira.argv
    assert _sem_sequencia_significativa(s.primeira), (
        f"orderSequence vazia não pode virar sequência arbitrária; argv={s.primeira.argv}"
    )
    assert _ordem_efetiva(s.primeira, fixture_relatorio) == ORDEM_RELATORIO


def test_order_manual_com_sequencia_so_de_espacos_nao_vira_erro_de_uso(tmp_path, fixture_relatorio):
    s = _rodar("manual-espacos", dict(_BASE, order="manual", orderSequence="   "), tmp_path / "h")
    assert _sem_sequencia_significativa(s.primeira), (
        f"só espaços equivale a vazio (item 2); argv={s.primeira.argv}"
    )
    assert _ordem_efetiva(s.primeira, fixture_relatorio) == ORDEM_RELATORIO


def test_order_manual_sem_sequencia_nao_deixa_o_servico_em_estado_de_erro(tmp_path, fixture_relatorio):
    """O caminho do item 7 não pode terminar em erro visível para o usuário.

    Duas camadas, porque o gravador sempre responde rc 0 (ele não julga a CLI):
    (a) o argv registrado, submetido ao coletor REAL, precisa dar rc 0 — é o que
    decide se o usuário vê erro; (b) nenhum texto de erro é renderizado.
    """
    settings = dict(_BASE, order="manual")
    s = _rodar("manual-estado", settings, tmp_path / "i")
    proc = _argv_para_o_coletor_real(s.primeira, fixture_relatorio)
    assert proc.returncode == 0, (
        "order=manual sem orderSequence produziu um argv que o coletor real recusa "
        f"(rc={proc.returncode}) — item 7: 'não pode virar erro de uso'.\n"
        f"argv={s.primeira.argv}\nstderr={proc.stderr!r}"
    )
    assert s.error_kind in ("", None), (
        f"order=manual sem sequência não pode produzir estado de erro; errorKind={s.error_kind!r} "
        f"lastError={s.last_error!r}"
    )
    assert not [e for e in s.erros], s.erros


# --------------------------------------------------------------------------- #
# 2b. Fim a fim: o COLETOR DE VERDADE, sem gravador (prova do defeito visível)
# --------------------------------------------------------------------------- #


def _rodar_fim_a_fim(nome: str, settings: dict, tmp: Path, fixture: Path) -> Servico:
    """Monta o plugin REAL (coletor de verdade) contra um ``ai-usagebar`` falso.

    Nada é substituído na árvore: o serviço chama o coletor do repositório, que
    chama o ``ai-usagebar`` falso (primeiro do PATH) e lê o relatório da fixture.
    É a única forma de ver o rc do coletor virar estado na tela.
    """
    fakebin = tmp / "fakebin"
    fakebin.mkdir(parents=True, exist_ok=True)
    falso = fakebin / "ai-usagebar"
    falso.write_text(
        f"#!{sys.executable}\nimport sys\nsys.stdout.write(open({str(fixture)!r}, encoding='utf-8').read())\n",
        encoding="utf-8",
    )
    falso.chmod(0o755)

    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("WAYLAND_DISPLAY", None)
    env["PATH"] = f"{fakebin}{os.pathsep}{env.get('PATH', '')}"
    env["XDG_CACHE_HOME"] = str(tmp / "cache")
    env["XDG_CONFIG_HOME"] = str(tmp / "cfg")
    env["XDG_STATE_HOME"] = str(tmp / "xdgstate")
    env["T15_PLUG_DIR"] = str(PLUGIN_DIR)
    env["T15_SETTINGS"] = json.dumps(settings, ensure_ascii=False)
    env["T15_STATE_DIR"] = str(tmp / "state")

    try:
        proc = subprocess.run([_QUICK, "-p", str(HARNESS)],
                              capture_output=True, text=True, env=env, timeout=180)
    except subprocess.TimeoutExpired:
        pytest.fail(f"[{nome}] o harness QML não terminou em 180s")
    return Servico(nome, [], _parse(proc.stdout + proc.stderr))


def test_fim_a_fim_order_upstream_carrega_o_relatorio(tmp_path, fixture_relatorio):
    """ANTI-VACUIDADE do fim a fim: no caminho feliz o modelo precisa CHEGAR.

    Sem isso, um ``errorKind`` vazio no caso de manual poderia significar apenas
    "o serviço nunca coletou nada".
    """
    s = _rodar_fim_a_fim("e2e-upstream", dict(_BASE, order="upstream"), tmp_path / "e2e-a", fixture_relatorio)
    assert s.main_present, s.registros[-8:]
    assert s.error_kind == "", f"upstream não deveria errar; errorKind={s.error_kind!r} err={s.last_error!r}"
    assert s.model_null == "false", (
        f"o modelo não chegou à instância — a bancada fim a fim não observa nada: {s.registros[-8:]}"
    )
    assert s.textos, f"a view não renderizou nada: {s.registros[-8:]}"


def test_fim_a_fim_order_manual_sem_sequencia_nao_produz_erro(tmp_path, fixture_relatorio):
    """O item 7 na pele do usuário: `order: manual` com `orderSequence` vazia.

    Hoje o serviço manda ``--order manual`` sem ``--sequence``; o coletor (item 1)
    responde rc 2 e o usuário recebe estado de erro em vez da ordem do relatório.
    É o defeito que o contrato proíbe explicitamente.
    """
    settings = dict(_BASE, order="manual", orderSequence="")
    s = _rodar_fim_a_fim("e2e-manual-vazia", settings, tmp_path / "e2e-b", fixture_relatorio)
    assert s.error_kind == "", (
        "order=manual com orderSequence vazia NÃO pode virar erro de uso (item 7); "
        f"errorKind={s.error_kind!r} lastError={s.last_error!r}"
    )
    assert s.model_null == "false", (
        f"com sequência vazia o modelo precisa vir do relatório; registros={s.registros[-8:]}"
    )


def test_fim_a_fim_order_manual_com_sequencia_respeita_a_ordem(tmp_path, fixture_relatorio):
    """Contraprova: com sequência preenchida o caminho funciona (senão o caso acima
    poderia estar falhando por outro motivo)."""
    settings = dict(_BASE, order="manual", orderSequence="echo,zulu")
    s = _rodar_fim_a_fim("e2e-manual-cheia", settings, tmp_path / "e2e-c", fixture_relatorio)
    assert s.error_kind == "", f"errorKind={s.error_kind!r} err={s.last_error!r}"
    assert s.model_null == "false", s.registros[-8:]
    # O nome do teste promete a ORDEM — e antes só verificava "não deu erro",
    # então passava até com `manual` degradando para `upstream`. Agora verifica.
    assert s.order[:2] == ["echo", "zulu"], (
        f"a sequência declarada tem de abrir a lista; ordem={s.order} "
        f"registros={s.registros[-6:]}"
    )


# --------------------------------------------------------------------------- #
# 3. Fora do manual, `--sequence` NUNCA é encaminhada (item 1, lado do serviço)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("modo", ["upstream", "highest", "lowest", "alphabetical"])
def test_fora_do_manual_o_servico_nao_encaminha_sequence(tmp_path, fixture_relatorio, modo):
    """Se o serviço mandasse ``--sequence`` aqui, o coletor devolveria rc 2 (item 1).

    A asserção é a IGUALDADE com a linha de base (mesma setting, sem
    ``orderSequence``): assim o teste não fixa como cada modo é escrito no argv
    (``upstream``, sendo o default, legitimamente não vira flag) e ainda pega
    qualquer vazamento da sequência.
    """
    com = _rodar(f"{modo}-com-sequence", dict(_BASE, order=modo, orderSequence="echo,zulu"),
                 tmp_path / f"{modo}-com").primeira
    sem = _rodar(f"{modo}-sem-sequence", dict(_BASE, order=modo),
                 tmp_path / f"{modo}-sem").primeira
    assert not com.tem("--sequence"), (
        f"order={modo} com orderSequence preenchida não pode encaminhar --sequence; argv={com.argv}"
    )
    assert com.argv == sem.argv, (
        f"order={modo}: orderSequence alterou o argv (deveria ser ignorada)\n"
        f"com={com.argv}\nsem={sem.argv}"
    )
    proc = _argv_para_o_coletor_real(com, fixture_relatorio)
    assert proc.returncode == 0, (
        f"o argv de order={modo} é erro de uso no coletor real; argv={com.argv}\n"
        f"stderr={proc.stderr!r}"
    )


def test_mudar_a_sequencia_nao_muda_o_argv_fora_do_manual(tmp_path):
    """Contraprova: a setting é ignorada por completo quando order != manual."""
    a = _rodar("ignora-a", dict(_BASE, order="highest", orderSequence="echo"), tmp_path / "j")
    b = _rodar("ignora-b", dict(_BASE, order="highest"), tmp_path / "k")
    assert a.primeira.argv == b.primeira.argv, (
        "orderSequence vazou para o argv em order=highest\n"
        f"com setting={a.primeira.argv}\nsem setting={b.primeira.argv}"
    )


def test_o_argv_do_manual_e_observavel_e_distinto_do_upstream(tmp_path):
    """Discriminador: o efeito de T15 tem de existir no argv, não só na setting."""
    man = _rodar("dif-manual", dict(_BASE, order="manual", orderSequence="echo"), tmp_path / "l").primeira
    up = _rodar("dif-upstream", dict(_BASE, order="upstream"), tmp_path / "m").primeira
    assert man.valor("--order") == "manual", f"manual precisa ir como --order manual; argv={man.argv}"
    assert man.valor("--sequence") == "echo", f"a sequência precisa ir junto; argv={man.argv}"
    assert man.argv != up.argv, "order=manual produziu o mesmo argv que upstream"
    assert not up.tem("--sequence"), (
        f"upstream não pode receber --sequence (seria rc 2 no coletor); argv={up.argv}"
    )


# --------------------------------------------------------------------------- #
# Ambiguidades / lacunas do contrato (honestidade D5)
# --------------------------------------------------------------------------- #

AMBIGUIDADES = """
1. A contradição itens 1 x 7 (a mesma registrada no arquivo do coletor). Este
   arquivo evita fixar o mecanismo: aceita "flag ausente" OU "--sequence ''" para
   o caso de orderSequence ausente/vazia, e exige o que ambos os itens concordam
   (rc 0 + ordem do relatório). Se o dono decidir "o serviço sempre passa
   --sequence, possivelmente vazio", o teste continua verde; se decidir "nunca
   passa", também. Um teste que exigisse uma das duas formas inventaria oráculo.
2. ONDE a setting é lida: item 7 fala de ``service/Main.qml`` e de "a setting
   chega ao argv". O nome da setting é ``orderSequence`` (texto), mas o
   ``manifest.json`` atual NÃO declara essa chave — nenhum teste aqui exige a
   declaração; o harness injeta ``pluginSettings.orderSequence`` diretamente,
   que é a forma pública de leitura (R5). Verificar a declaração é
   ``test_manifest_declara_order_manual_e_order_sequence``, que falha hoje e fica
   registrado como pendência de T15/T16, não como ambiguidade.
3. Não testei se o serviço RECARREGA o modelo quando ``orderSequence`` muda sem
   trocar ``order``. A letra do item 7 é sobre o argv, não sobre reação a
   mudança; a recarga é T17.
4. Ignorei o número de invocações: o serviço pode rodar o coletor mais de uma vez
   (poll + primeira carga). Asserções usam a PRIMEIRA invocação; se alguma
   invocação divergir, nenhum teste detecta. Deliberado — o contrato não fala de
   repetição, e exigir igualdade entre invocações criaria oráculo sobre o poll.
5. `--from-file` nunca é passado pelo serviço em produção; para provar o efeito
   no coletor real o teste injeta `--from-file <fixture>` no argv registrado. Isso
   assume que o serviço não passa `--from-file` — se passasse, o teste o
   substituiria silenciosamente (o valor é trocado, não duplicado).
"""


# --------------------------------------------------------------------------- #
# Declaração pública da setting (manifest) — falha hoje, é a metade declarativa
# --------------------------------------------------------------------------- #


def _manifest() -> dict:
    caminho = PLUGIN_DIR / "manifest.json"
    assert caminho.is_file(), f"manifest ausente em {caminho}"
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_manifest_declara_order_manual_e_order_sequence():
    """Item 7 pressupõe as duas chaves; sem elas a setting é inalcançável pela UI.

    O manifest é declaração PÚBLICA (não é implementação): é o contrato que o Hub
    renderiza. Este teste é o que impede ``order: manual`` de existir no coletor
    e não existir para o usuário.
    """
    settings = {s["key"]: s for s in _manifest()["metadata"]["settings"]}
    assert "order" in settings, "a setting order precisa existir"
    valores = [o["value"] for o in settings["order"]["options"]]
    assert "manual" in valores, (
        f"a opção 'manual' precisa estar declarada em order; veio {valores}"
    )
    assert "orderSequence" in settings, (
        f"a setting orderSequence precisa ser declarada; chaves={sorted(settings)}"
    )
    assert settings["orderSequence"]["type"] == "text", (
        f"orderSequence é texto livre de ids; tipo declarado={settings['orderSequence']['type']!r}"
    )
    assert isinstance(settings["orderSequence"].get("default"), str), (
        "orderSequence precisa de default string (vazio é a sequência vazia válida)"
    )
