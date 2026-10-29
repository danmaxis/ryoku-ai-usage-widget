# -*- coding: utf-8 -*-
"""Contrato de COMPORTAMENTO de T16, itens 4 e 5 — `--primary` e a recarga.

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada
corrente, tarefa T16. Contrato transcrito:

    4. Encaminhamento de ``--primary``: vale em TODOS os modos (é ortogonal à
       ordem). Campo vazio NÃO vira flag — ``--primary ""`` não aparece no argv.
    5. Recarga: mudar ``primary`` SEMPRE re-coleta; mudar ``orderSequence`` só
       re-coleta quando ``order == "manual"``.

Método (nenhuma leitura de fonte)
---------------------------------
1. Copia a pasta do plugin para um diretório temporário e substitui o
   ``bin/ai-usage-collect`` da CÓPIA por um GRAVADOR: ele anota o próprio argv
   (uma linha JSON por invocação) e responde um JSON no formato do contrato.
2. Monta o ``service/Main.qml`` da CÓPIA num ``quickshell`` offline
   (``QT_QPA_PLATFORM=offscreen``) via ``tests/qml/t16_argv_harness.qml``, com um
   ``pluginApi`` sintético no formato do host (``property var pluginSettings``).
3. Lê o registro e verifica o ARGV EXATO que o serviço montou.
4. Prova de efeito: roda o COLETOR DE VERDADE (o do repositório, intocado) com o
   argv registrado + ``--from-file`` da fixture própria, exigindo rc 0 e o
   provider escolhido como primário. Isso transforma "o argv parece certo" em
   "o argv produz o destaque pedido".

Recarga (item 5)
----------------
O único canal honesto para "re-coletou" é a CONTAGEM de invocações do coletor:
comparada com a linha de base sem mutação, no mesmo processo. Para a assimetria,
o caso de ``orderSequence`` fora de ``manual`` exige a IGUALDADE de contagem com
a linha de base; o caso de ``primary`` exige ESTRITAMENTE MAIOR.

Divergência medida (não asserida aqui — ver ``AMBIGUIDADES``): a re-coleta
disparada pela troca de ``primary`` carrega o valor ANTERIOR, não o novo. É o
"settings congelados" que a SPEC casa com T17; o item 5 desta tarefa fala da
CONTAGEM, e é só isso que esta suíte exige.
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
# Localização (o conteúdo de Main.qml/Widget.qml nunca é lido)
# --------------------------------------------------------------------------- #

TEST_DIR = Path(__file__).resolve().parent
PLUGIN_DIR = Path(os.environ.get("T16_PLUGIN_DIR", TEST_DIR.parent))
REPO_ROOT = PLUGIN_DIR.parent
HARNESS = Path(os.environ.get("T16_HARNESS_ARGV", TEST_DIR / "qml" / "t16_argv_harness.qml"))

#: O coletor de verdade julga se o argv produzido é erro de uso.
COLETOR_REAL = Path(os.environ.get("T16_COLLECTOR", PLUGIN_DIR / "bin" / "ai-usage-collect"))

_QUICK = shutil.which("quickshell") or shutil.which("qs")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

pytestmark = pytest.mark.skipif(
    _QUICK is None,
    reason="quickshell ausente: o serviço QML não pode ser exercitado",
)

#: Flags que o coletor declara: o gravador não deve receber outra coisa.
FLAGS_CONHECIDAS = {"--from-file", "--primary", "--order", "--sequence", "--max-secondary", "-h", "--help"}

#: Ids da fixture, na ordem do relatório (deliberadamente não alfabética).
ORDEM_RELATORIO = ["zulu", "alpha", "mike", "kilo", "echo", "whiskey", "openai@work"]


# --------------------------------------------------------------------------- #
# Fixture própria
# --------------------------------------------------------------------------- #

def _metrica(percent: int = 10) -> dict:
    return {
        "label": "Session (5h)", "percent": percent, "value": f"{percent}%",
        "headline": "percent", "severity": "low", "detail": "d",
        "reset_at": "2026-11-01T00:00:00Z", "window_secs": 18000,
    }


def _entrada(pid: str, *, status: str = "ready") -> dict:
    vendor = pid.split("@", 1)[0]
    return {
        "id": pid, "name": vendor, "display_name": pid, "short_name": vendor[:3],
        "icon": "i", "brand": vendor, "plan": None, "status": status,
        "error": "sem credencial (fixture)" if status == "error" else None,
        "stale": False,
        "fetched_at": "2026-10-15T12:00:00Z" if status == "ready" else None,
        "reset_credits": None,
        "metrics": [_metrica()] if status == "ready" else [],
        "sections": [],
    }


@pytest.fixture(scope="module")
def fixture_relatorio(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("t16argv-fixture")
    payload = {"schema_version": 1, "primary": "alpha", "entries": [
        _entrada("zulu"),
        _entrada("alpha"),
        _entrada("mike", status="error"),
        _entrada("kilo"),
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
# Gravador de argv instalado por ai-usage/tests/test_t16_primary_argv_isolado.py.
# Não é o coletor: anota o próprio argv e devolve um JSON no formato do contrato.
import json, os, sys

registro = os.environ.get("T16_ARGV_LOG") or ""
if registro:
    with open(registro, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"argv": sys.argv[1:]}}) + "\n")

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
    destino = tmp / "plugin"
    shutil.copytree(PLUGIN_DIR, destino,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    log = tmp / "argv.log"
    coletor = destino / "bin" / "ai-usage-collect"
    coletor.parent.mkdir(parents=True, exist_ok=True)
    coletor.write_text(_GRAVADOR.format(python=sys.executable), encoding="utf-8")
    coletor.chmod(0o777)
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

    @property
    def flags(self) -> list[str]:
        return [a for a in self.argv if a.startswith("-")]

    def __repr__(self) -> str:
        return f"<argv {self.argv}>"


class Servico:
    def __init__(self, nome: str, invocacoes: list[Invocacao], registros: list[str]):
        self.nome = nome
        self.invocacoes = invocacoes
        self.registros = registros
        self.textos = [r[len("TEXT|"):] for r in registros if r.startswith("TEXT|")]
        self.erros = [r for r in registros if r.startswith("VIEW_ERR|")]

        def campo(tag):
            for r in registros:
                if r.startswith(tag + "|"):
                    return r[len(tag) + 1:]
            return None

        self.mounted = campo("MOUNTED") == "true"
        self.textos_antes = (campo("BEFORE_TEXTS") or "").split("\u001f")
        self.textos_depois = (campo("AFTER_TEXTS") or "").split("\u001f")
        self.ended = any(r.startswith("END|") for r in registros)

    @property
    def n(self) -> int:
        return len(self.invocacoes)

    @property
    def primeira(self) -> Invocacao:
        assert self.invocacoes, (
            f"[{self.nome}] o coletor da cópia nunca foi invocado — sem argv não há "
            f"nada a verificar. registros={self.registros[-6:]}"
        )
        return self.invocacoes[0]


def _parse(stdout: str) -> list[str]:
    out = []
    for raw in _ANSI.sub("", stdout).splitlines():
        if " qml: " in raw:
            raw = raw.split(" qml: ", 1)[1]
        raw = raw.strip()
        if raw and not raw.startswith(("TICK|",)):
            out.append(raw)
    return out


def _rodar(nome: str, settings: dict, tmp: Path, *,
           patches: list[dict] | None = None,
           settle_ms: int = 3000, first_ms: int = 3000) -> Servico:
    copia, log = _copia_com_gravador(tmp)
    log.write_text("", encoding="utf-8")

    # ai-usagebar falso: nenhum processo do upstream real é executado.
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
    env["T16_ARGV_LOG"] = str(log)
    env["T16_PLUG_DIR"] = str(copia)
    env["T16_SETTINGS"] = json.dumps(settings, ensure_ascii=False)
    env["T16_PATCHES"] = json.dumps(patches or [], ensure_ascii=False)
    env["T16_STATE_DIR"] = str(tmp / "state")
    env["T16_SETTLE_MS"] = str(settle_ms)
    env["T16_FIRST_MS"] = str(first_ms)

    try:
        proc = subprocess.run([_QUICK, "-p", str(HARNESS)],
                              capture_output=True, text=True, env=env, timeout=240)
    except subprocess.TimeoutExpired:
        pytest.fail(f"[{nome}] o harness QML não terminou em 240s")

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


def _rodar_no_coletor_real(invocacao: Invocacao, fixture: Path):
    """Submete o argv registrado ao COLETOR DE VERDADE (+ --from-file)."""
    assert COLETOR_REAL.is_file(), f"coletor ausente em {COLETOR_REAL}"
    args = list(invocacao.argv)
    if "--from-file" in args:
        i = args.index("--from-file")
        args[i + 1] = str(fixture)
    else:
        args = ["--from-file", str(fixture)] + args
    return subprocess.run([sys.executable, str(COLETOR_REAL)] + args,
                          capture_output=True, text=True, timeout=60)


def _primario_efetivo(invocacao: Invocacao, fixture: Path) -> str:
    proc = _rodar_no_coletor_real(invocacao, fixture)
    assert proc.returncode == 0, (
        f"o argv que o serviço montou é ERRO DE USO para o coletor (rc={proc.returncode}).\n"
        f"argv={invocacao.argv}\nstderr={proc.stderr!r}"
    )
    return json.loads(proc.stdout)["primary"]["id"]


_BASE = {
    "accent": "wallpaper", "order": "upstream", "showMetricDetail": True,
    "secondaryLabel": "name", "showSecondaries": True, "maxSecondary": 6,
    "padding": 12, "gap": 6, "pollSeconds": 3600, "primary": "",
}


# --------------------------------------------------------------------------- #
# 0. Anti-vacuidade da bancada
# --------------------------------------------------------------------------- #

def test_o_gravador_ocupa_o_lugar_do_coletor_e_registra_o_argv(tmp_path):
    """Se o gravador não for invocado, todos os testes abaixo seriam vácuos."""
    s = _rodar("sanity", dict(_BASE), tmp_path)
    assert s.mounted, f"o serviço não montou: {s.registros[-8:]}"
    assert s.n >= 1, "o coletor da cópia nunca foi chamado — a bancada não observa nada"
    assert not s.erros, s.erros
    for a in s.primeira.flags:
        assert a in FLAGS_CONHECIDAS, (
            f"argv com flag que não é do coletor: {a!r} em {s.primeira.argv}"
        )


def test_primary_vazio_nao_produz_flag_nenhuma_no_caso_base(tmp_path):
    """O caso base é o controle de todos os contrastes de `--primary`."""
    s = _rodar("base-vazio", dict(_BASE), tmp_path)
    assert not s.primeira.tem("--primary"), (
        f"com primary='' o argv não pode conter --primary; argv={s.primeira.argv}"
    )


# --------------------------------------------------------------------------- #
# 1. ITEM 4 — `--primary` chega ao coletor em TODOS os modos
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("modo", ["upstream", "highest", "lowest", "alphabetical"])
def test_primary_chega_ao_argv_em_todos_os_modos_de_ordem(tmp_path, fixture_relatorio, modo):
    """`primary` é ortogonal à ordem: nenhum modo pode engoli-la."""
    s = _rodar(f"primary-{modo}", dict(_BASE, order=modo, primary="openai@work"), tmp_path)
    inv = s.primeira
    assert inv.valor("--primary") == "openai@work", (
        f"order={modo}: a setting primary precisa chegar em --primary; argv={inv.argv}"
    )
    # O PAR exato: a flag seguida do valor, sem vírgula/aspas espúrias.
    assert ["--primary", "openai@work"] == inv.argv[
        inv.argv.index("--primary"):inv.argv.index("--primary") + 2
    ], f"o par --primary/valor não está adjacente; argv={inv.argv}"
    assert _primario_efetivo(inv, fixture_relatorio) == "openai@work", (
        f"order={modo}: o argv não produziu o destaque pedido no coletor real"
    )


def test_primary_chega_ao_argv_no_modo_manual_junto_com_a_sequencia(tmp_path, fixture_relatorio):
    """T15 e T16 na mesma invocação: ordem manual + destaque escolhido."""
    s = _rodar("primary-manual", dict(_BASE, order="manual", orderSequence="echo,zulu",
                                      primary="openai@work"), tmp_path)
    inv = s.primeira
    assert inv.valor("--order") == "manual", inv.argv
    assert inv.valor("--sequence") == "echo,zulu", inv.argv
    assert inv.valor("--primary") == "openai@work", (
        f"--primary sumiu quando --order manual e --sequence estão presentes; argv={inv.argv}"
    )
    assert _primario_efetivo(inv, fixture_relatorio) == "openai@work"


def test_primary_aceita_id_com_conta(tmp_path, fixture_relatorio):
    """O id composto `vendor@conta` é a forma real (fixture: openai@work)."""
    s = _rodar("primary-conta", dict(_BASE, primary="openai@work"), tmp_path)
    assert s.primeira.valor("--primary") == "openai@work"
    assert _primario_efetivo(s.primeira, fixture_relatorio) == "openai@work"


def test_primary_preenchida_sozinha_ja_muda_o_argv(tmp_path):
    """Discriminador: o efeito de T16 tem de existir no argv, não só na setting."""
    com = _rodar("dif-com", dict(_BASE, primary="copilot"), tmp_path / "a").primeira
    sem = _rodar("dif-sem", dict(_BASE), tmp_path / "b").primeira
    assert com.valor("--primary") == "copilot", com.argv
    assert com.argv != sem.argv, (
        f"primary preenchida produziu o mesmo argv que primary vazia: {com.argv}"
    )
    assert not sem.tem("--primary"), sem.argv


# --------------------------------------------------------------------------- #
# 2. ITEM 4 — campo vazio NÃO vira flag (nem `--primary ""`)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("vazio", ["", "   ", "\t", "\n"])
def test_primary_em_branco_nao_aparece_no_argv(tmp_path, vazio):
    """`--primary ""` não é id; o contrato manda OMITIR o par, não mandá-lo vazio.

    Antipassividade: um serviço que NUNCA encaminha ``--primary`` passaria este
    teste por vacuidade. Por isso o mesmo caminho é exercido com valor
    preenchido primeiro — se a flag não aparece nem ali, o canal está morto e o
    teste falha por isso, não por acerto.
    """
    # (a) o canal tem de estar vivo: valor preenchido produz o par.
    vivo = _rodar(f"canal-{ord(vazio[0]) if vazio else 0}", dict(_BASE, primary="copilot"),
                  tmp_path / "vivo").primeira
    assert vivo.valor("--primary") == "copilot", (
        "o canal de --primary não está vivo (valor preenchido não chegou ao argv); "
        f"a ausência com valor vazio seria vácua. argv={vivo.argv}"
    )
    # (b) e com valor em branco o par NÃO pode existir.
    s = _rodar(f"branco-{len(vazio)}-{ord(vazio[0]) if vazio else 0}",
               dict(_BASE, primary=vazio), tmp_path)
    inv = s.primeira
    assert not inv.tem("--primary"), (
        f"primary={vazio!r} não pode gerar --primary (nem --primary ''); argv={inv.argv}"
    )
    # Caso negativo explícito: o par vazio é o defeito que o contrato nomeia.
    assert "--primary" not in inv.argv, f"a flag apareceu sem valor: {inv.argv}"


def test_primary_ausente_da_setting_comporta_como_vazia(tmp_path):
    """Entrada antiga sem a chave: mesmo argv de `primary: ""`.

    Antipassividade: exige antes que o preenchido DIVIRJA do vazio, senão
    "iguais" seria verdade mesmo com o canal morto.
    """
    preenchido = _rodar("chave-cheia", dict(_BASE, primary="copilot"), tmp_path / "p").primeira
    com_chave = _rodar("chave-vazia", dict(_BASE, primary=""), tmp_path / "a").primeira
    sem_chave = _rodar("sem-chave", dict(_BASE), tmp_path / "b").primeira
    assert preenchido.argv != com_chave.argv, (
        "o argv não muda entre primary preenchida e vazia — o canal está morto e "
        f"a igualdade abaixo seria vácua. preenchido={preenchido.argv} vazio={com_chave.argv}"
    )
    assert com_chave.argv == sem_chave.argv, (
        f"primary='' e primary ausente precisam dar o mesmo argv\n"
        f"com={com_chave.argv}\nsem={sem_chave.argv}"
    )
    assert not sem_chave.tem("--primary"), sem_chave.argv


# --------------------------------------------------------------------------- #
# 3. ITEM 5 — a assimetria da recarga
# --------------------------------------------------------------------------- #

def test_mudar_primary_re_coleta(tmp_path):
    """Item 5, lado positivo: mudar `primary` SEMPRE re-coleta."""
    base = _rodar("recoleta-base", dict(_BASE), tmp_path / "a")
    mutado = _rodar("recoleta-primary", dict(_BASE), tmp_path / "b",
                    patches=[{"primary": "copilot"}])
    assert mutado.n > base.n, (
        f"mudar primary não re-coletou: base={base.n} invocação(ões), "
        f"após mutação={mutado.n}. O usuário trocaria o destaque e a tela não mudaria."
    )


@pytest.mark.parametrize("modo", ["upstream", "highest", "lowest", "alphabetical"])
def test_mudar_order_sequence_fora_do_manual_nao_re_coleta(tmp_path, modo):
    """Item 5, lado negativo: fora de `manual` a sequência não tem efeito.

    Antipassividade embutida: a igualdade de contagem só é evidência se o canal
    de recarga estiver VIVO neste mesmo modo — daí a âncora com ``primary``, que
    deve re-coletar aqui. Sem ela, um serviço que nunca re-coleta nada passaria.
    """
    base = _rodar(f"seq-base-{modo}", dict(_BASE, order=modo), tmp_path / "a")
    mutado = _rodar(f"seq-mut-{modo}", dict(_BASE, order=modo), tmp_path / "b",
                    patches=[{"orderSequence": "echo,zulu"}])
    ancora = _rodar(f"seq-ancora-{modo}", dict(_BASE, order=modo), tmp_path / "c",
                    patches=[{"primary": "copilot"}])
    assert ancora.n > base.n, (
        f"order={modo}: o canal de recarga não está vivo (mudar primary não "
        f"re-coletou: base={base.n}, após={ancora.n}) — a igualdade abaixo seria vácua"
    )
    assert mutado.n == base.n, (
        f"order={modo}: mudar orderSequence re-coletou embora não tenha efeito "
        f"(base={base.n}, após={mutado.n}) — desperdício, e o contrato proíbe"
    )
    assert not mutado.primeira.tem("--sequence"), (
        f"order={modo}: a sequência vazou para o argv; argv={mutado.primeira.argv}"
    )


def test_mudar_order_sequence_em_manual_re_coleta(tmp_path):
    """Contraprova do caso acima: em `manual` a MESMA mutação re-coleta.

    Sem esta metade, 'não re-coleta' poderia ser verdade porque nada re-coleta.
    """
    base = _rodar("seqm-base", dict(_BASE, order="manual"), tmp_path / "a")
    mutado = _rodar("seqm-mut", dict(_BASE, order="manual"), tmp_path / "b",
                    patches=[{"orderSequence": "echo,zulu"}])
    assert mutado.n > base.n, (
        f"order=manual: mudar orderSequence deveria re-coletar (base={base.n}, "
        f"após={mutado.n}); é o único modo em que a setting tem efeito"
    )


def test_a_assimetria_acontece_no_mesmo_servico(tmp_path):
    """A prova mais dura do item 5: duas mutações, uma ordem, contagens distintas.

    Patch 1 troca `orderSequence` (fora do manual: deve ser inerte).
    Patch 2 troca `primary` (deve re-coletar).
    Medir no MESMO processo elimina a variação de arranque entre processos.
    """
    s = _rodar(
        "assimetria", dict(_BASE, order="highest"),
        tmp_path,
        patches=[{"orderSequence": "echo,zulu"}, {"primary": "copilot"}],
        settle_ms=3000, first_ms=3000,
    )
    # Sem mutação alguma o serviço já invoca uma vez; a sequência não pode somar.
    controle = _rodar("assimetria-controle", dict(_BASE, order="highest"), tmp_path / "c")
    apenas_primaria = _rodar(
        "assimetria-only-primary", dict(_BASE, order="highest"),
        tmp_path / "d", patches=[{"primary": "copilot"}],
    )
    assert s.n == apenas_primaria.n, (
        f"a mutação de orderSequence (inerte fora do manual) somou invocações: "
        f"com sequência+primary={s.n}, só primary={apenas_primaria.n}"
    )
    assert s.n > controle.n, (
        f"nenhuma re-coleta aconteceu: controle={controle.n}, após mutações={s.n}"
    )


def test_nenhuma_re_coleta_vira_erro_de_uso(tmp_path, fixture_relatorio):
    """Depois de trocar `primary`, o argv do coletor continua válido."""
    s = _rodar("pos-mutacao-valido", dict(_BASE), tmp_path,
               patches=[{"primary": "copilot"}])
    assert not s.erros, s.erros
    for inv in s.invocacoes:
        proc = _rodar_no_coletor_real(inv, fixture_relatorio)
        assert proc.returncode == 0, (
            f"a invocação {inv.argv} é erro de uso no coletor real "
            f"(rc={proc.returncode}, stderr={proc.stderr!r})"
        )


# --------------------------------------------------------------------------- #
# Divergências medidas (honestidade D5 — o que NÃO foi asserido, e por quê)
# --------------------------------------------------------------------------- #

AMBIGUIDADES = """
1. A re-coleta disparada pela troca de `primary` carrega o valor ANTERIOR, não o
   novo (medido em HEAD, repro abaixo). O item 5 fala de CONTAGEM — "sempre
   re-coleta" — e ela acontece; o efeito, porém, é uma coleta inútil para o novo
   valor. A SPEC casa esse sintoma ("settings congelados") com T17, então esta
   suíte NÃO o transforma em falha de T16: exigir o valor novo aqui seria puxar
   oráculo de outra tarefa. Repro:
       settings {primary: "copilot"} + patches [{primary:"zai"},{primary:"kilo"}]
       -> argvs observados: [--primary copilot], [--primary copilot],
                            [--primary zai], [--primary kilo]
   (a coleta disparada pelo patch N usa o valor de N-1; a do poll seguinte acerta)
   Confirmado com o COLETOR REAL: os textos renderizados antes e depois da
   mutação são idênticos — o provider expandido continua o antigo.
2. O item 4 diz "campo vazio NÃO vira flag", mas não define o que é "vazio".
   Medi que espaços/tab/nova linha são aparados e o par é omitido; a suíte exige
   apenas o que o contrato afirma — o par AUSENTE — e aceita qualquer apara
   interna, que é invisível no argv.
3. O argv não revela a ORDEM das flags. As asserções comparam o PAR
   `--primary <valor>` e o conjunto de flags, nunca a posição relativa a
   `--order`/`--sequence` (o contrato não a fixa).
4. Ignorei diferenças de N (contagem) entre execuções não relacionadas à
   mutação: cada comparação usa o seu próprio par base×mutado. O único caso que
   compara três é `test_a_assimetria_acontece_no_mesmo_servico`, e ali a
   igualdade exigida é entre duas execuções que diferem por UMA mutação inerte.
5. `--from-file` nunca é passado pelo serviço em produção; para provar o efeito
   no coletor real o teste injeta `--from-file <fixture>` no argv registrado.
"""


def test_as_divergencias_medidas_estao_registradas():
    """Guarda-corpo: a divergência do item 1 é uma decisão, não um esquecimento."""
    assert "T17" in AMBIGUIDADES, (
        "a divergência de valor defasado precisa apontar a tarefa que a cobre"
    )


# --------------------------------------------------------------------------- #
# 8. A re-coleta disparada pela mudança usa o valor NOVO (defeito medido)
# --------------------------------------------------------------------------- #

def test_a_recoleta_disparada_pela_mudanca_ja_usa_o_valor_novo(tmp_path):
    """A coleta que a mudança de setting dispara não pode usar o valor ANTERIOR.

    Defeito medido em 2026-10-27 (não é hipótese): com `primary` indo de
    "copilot" para "zai", a sonda viu DUAS invocações e AMBAS com
    `--primary copilot` — o valor novo só valeria no poll seguinte (até 300 s
    depois). Causa: os handlers `onXChanged` do QML disparam DURANTE a mudança,
    quando o binding `Process.command: svc.collectorCmd` ainda não reavaliou;
    arrancar o processo ali usa o comando velho.

    O contrato do item 5 fala de CONTAGEM ("mudar primary sempre re-coleta") e a
    contagem acontecia — por isso o defeito passou despercebido. Este teste fixa
    o que o usuário sente: depois de mudar a setting, a próxima coleta reflete o
    valor NOVO.

    Não exige quantas coletas: exige que a ÚLTIMA carregue o valor novo.
    """
    s = _rodar("primary-defasado", dict(_BASE, primary="copilot"), tmp_path,
               patches=[{"primary": "zai"}])
    assert len(s.invocacoes) >= 2, (
        f"esperava ao menos a coleta inicial e a da mudança; "
        f"vi {len(s.invocacoes)}: {[i.argv for i in s.invocacoes]}"
    )
    valores = [i.valor("--primary") for i in s.invocacoes]
    assert valores[-1] == "zai", (
        "a última coleta ainda usou o valor ANTERIOR — a mudança de setting não "
        f"chegou ao argv. valores observados={valores}"
    )
    assert "copilot" not in valores[1:], (
        f"alguma coleta POSTERIOR à mudança ainda mandou o valor antigo: {valores}"
    )
