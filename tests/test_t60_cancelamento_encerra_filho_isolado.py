# -*- coding: utf-8 -*-
"""Testes de comportamento de T60 — cancelar o coletor encerra o ``ai-usagebar``.

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada 7,
tarefa T60. O único oráculo é o bloco assinado da SPEC e o contrato passado pelo
orquestrador, transcritos aqui porque o teste não pode ler a implementação:

  Sintoma (achado de revisão): o coletor inicia ``ai-usagebar usage --json``; se
  o coletor recebe SIGTERM enquanto espera, o ``ai-usagebar`` continua vivo,
  órfão.

  Contrato: ao receber SIGTERM, SIGINT ou SIGHUP enquanto espera o
  ``ai-usagebar``, o coletor encerra o ``ai-usagebar`` (e os descendentes dele)
  e sai com rc diferente de 0, tudo em até 5 s. Vale também quando o
  ``ai-usagebar`` ignora SIGTERM (ele é morto à força). A saída e os códigos de
  retorno do caminho feliz não mudam.

Bancada
-------
O coletor é uma caixa-preta executada por ``subprocess`` com ``sys.executable``.
O ``ai-usagebar`` é um executável FALSO num diretório temporário posto na frente
de um PATH mínimo (o falso + um symlink para o interpretador, mais nada). O
falso grava o próprio PID (e o do neto, quando há) num arquivo e dorme 120 s.
O teste espera o arquivo, confere que tudo está vivo (anti-vacuidade), manda o
sinal ao coletor e mede: o coletor saiu, com rc != 0, e os PIDs deixaram de
existir — tudo dentro do prazo de 5 s contado a partir do sinal.

"Deixou de existir" = ``os.kill(pid, 0)`` levanta ``ProcessLookupError`` OU o
processo é um zumbi (já morreu; só falta ser colhido por quem o adotou).

Por que os testes de sinal NÃO passam ``--source``
--------------------------------------------------
O critério de done de T60 é "falha contra ``c3bf23f`` e passa depois". Naquele
commit ``--source`` ainda não existe (é de T61); com ele o teste cairia por
"argumento desconhecido", que não é o sintoma. Então os testes de sinal usam o
padrão (``auto``), que com o falso no PATH tem de usar o ``ai-usagebar``; o HOME
é um diretório temporário vazio, de modo que nenhum cache real é alcançável.
Uma variante explícita com ``--source ai-usagebar`` cobre o caminho pedido.

Toda execução limpa no ``finally``: o que sobrar vivo é morto à força, para o
teste não deixar processo para trás justamente quando falha.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Localização dos artefatos (o conteúdo do coletor nunca é lido)
# --------------------------------------------------------------------------- #

TEST_DIR = Path(__file__).resolve().parent          # <repo>/ai-usage/tests
PLUGIN_DIR = TEST_DIR.parent                        # <repo>/ai-usage
REPO_ROOT = PLUGIN_DIR.parent                       # <repo>

#: Override por ambiente: uso EXCLUSIVO da verificação de falsificabilidade
#: (apontar para uma cópia do coletor de outro commit). Produção não o define.
SCRIPT = Path(os.environ.get("T60_SCRIPT", PLUGIN_DIR / "bin" / "ai-usage-collect"))

_BASE_ARGV = [sys.executable, str(SCRIPT)]

#: Prazo do contrato, em segundos, contado a partir do envio do sinal.
PRAZO = 5.0
#: Quanto se espera o falso gravar o arquivo de PIDs (partida do coletor).
PRAZO_PARTIDA = 15.0

RELATORIO_MINIMO = '{"schema_version":1,"primary":null,"entries":[]}'

_DORMIR = "import time; time.sleep(120)"


# --------------------------------------------------------------------------- #
# Bancada
# --------------------------------------------------------------------------- #


def _artefatos() -> None:
    assert SCRIPT.is_file(), f"coletor ausente em {SCRIPT} — nada a verificar"


def _dir_so_python(tmp_path: Path) -> Path:
    """Diretório com um symlink para o interpretador e MAIS NADA."""
    d = tmp_path / "path-so-python"
    d.mkdir(parents=True, exist_ok=True)
    link = d / "python3"
    if not link.exists():
        link.symlink_to(Path(os.path.realpath(sys.executable)))
    return d


def _instalar_falso(tmp_path: Path, corpo: str) -> str:
    """Grava o ``ai-usagebar`` falso e devolve o PATH com ele em primeiro."""
    d = tmp_path / "path-com-falso"
    d.mkdir(parents=True, exist_ok=True)
    falso = d / "ai-usagebar"
    falso.write_text(f"#!{sys.executable}\n{corpo}", encoding="utf-8")
    falso.chmod(0o755)
    return f"{d}{os.pathsep}{_dir_so_python(tmp_path)}"


def _env(path: str, tmp_path: Path) -> dict:
    """Ambiente mínimo: sem o PATH da máquina e com HOME temporário vazio."""
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    return {"PATH": path, "HOME": str(home), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}


def _corpo_falso_que_dorme(arq_pids: Path, *, ignora_sigterm: bool, com_neto: bool) -> str:
    """Falso que registra PIDs (escrita atômica) e dorme 120 s.

    A ordem importa: o SIGTERM é ignorado e o neto é criado ANTES de o arquivo
    aparecer, para o teste só sinalizar com o cenário inteiro montado.
    """
    linhas = [
        "import json, os, signal, subprocess, sys, time",
    ]
    if ignora_sigterm:
        linhas.append("signal.signal(signal.SIGTERM, signal.SIG_IGN)")
    linhas.append("pids = {'filho': os.getpid()}")
    if com_neto:
        linhas.append(f"neto = subprocess.Popen([{sys.executable!r}, '-c', {_DORMIR!r}])")
        linhas.append("pids['neto'] = neto.pid")
    linhas += [
        f"destino = {str(arq_pids)!r}",
        "with open(destino + '.tmp', 'w') as fh:",
        "    json.dump(pids, fh)",
        "os.replace(destino + '.tmp', destino)",
        "time.sleep(120)",
        "",
    ]
    return "\n".join(linhas)


def vivo(pid: int) -> bool:
    """True se o processo ainda existe e NÃO é zumbi."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    try:
        return stat.rsplit(")", 1)[1].split()[0] != "Z"
    except IndexError:
        return True


def _matar(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _esperar_pids(arq_pids: Path, coletor: subprocess.Popen, saida: Path, erro: Path) -> dict:
    limite = time.monotonic() + PRAZO_PARTIDA
    while time.monotonic() < limite:
        if arq_pids.is_file():
            return json.loads(arq_pids.read_text())
        if coletor.poll() is not None:
            pytest.fail(
                "o coletor saiu antes de iniciar o ai-usagebar falso — o cenário de "
                f"cancelamento não chegou a existir: rc={coletor.returncode} "
                f"stdout={saida.read_text()!r} stderr={erro.read_text()!r}"
            )
        time.sleep(0.02)
    pytest.fail(f"o ai-usagebar falso não foi iniciado em {PRAZO_PARTIDA}s")


def _sobreviventes(pids: dict, limite: float) -> dict:
    """Faz polling até ``limite``; devolve os PIDs que continuam vivos."""
    while True:
        restam = {nome: pid for nome, pid in pids.items() if vivo(pid)}
        if not restam or time.monotonic() >= limite:
            return restam
        time.sleep(0.02)


def cancelar_e_medir(tmp_path, sinal, *, ignora_sigterm=False, com_neto=False, args=()):
    """Monta o cenário, sinaliza o coletor e devolve o que foi observado.

    Devolve ``(rc, sobreviventes, saiu_no_prazo)``. A limpeza é incondicional.
    """
    _artefatos()
    arq_pids = tmp_path / "pids.json"
    corpo = _corpo_falso_que_dorme(arq_pids, ignora_sigterm=ignora_sigterm, com_neto=com_neto)
    env = _env(_instalar_falso(tmp_path, corpo), tmp_path)
    saida, erro = tmp_path / "coletor.stdout", tmp_path / "coletor.stderr"

    pids: dict = {}
    # stdout/stderr vão para arquivos: um órfão que herdasse um pipe seguraria a
    # leitura e o teste mediria o pipe, não a saída do coletor. Sessão própria:
    # o sinal vai só ao PID do coletor, e a limpeza pode varrer o grupo.
    with open(saida, "w") as fo, open(erro, "w") as fe:
        coletor = subprocess.Popen(
            _BASE_ARGV + [str(a) for a in args],
            cwd=str(REPO_ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=fo,
            stderr=fe,
            start_new_session=True,
        )
    try:
        pids = _esperar_pids(arq_pids, coletor, saida, erro)

        # Anti-vacuidade: antes do sinal, tudo está de pé.
        for nome, pid in pids.items():
            assert vivo(pid), f"bancada inválida: {nome} (pid {pid}) já não existe antes do sinal"
        assert coletor.poll() is None, "bancada inválida: o coletor já saiu antes do sinal"

        inicio = time.monotonic()
        coletor.send_signal(sinal)
        try:
            rc = coletor.wait(timeout=PRAZO)
            saiu_no_prazo = True
        except subprocess.TimeoutExpired:
            rc = None
            saiu_no_prazo = False
        restam = _sobreviventes(pids, inicio + PRAZO)
        return rc, restam, saiu_no_prazo
    finally:
        try:
            os.killpg(coletor.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        if coletor.poll() is None:
            coletor.kill()
        try:
            coletor.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        if not pids and arq_pids.is_file():
            try:
                pids = json.loads(arq_pids.read_text())
            except ValueError:
                pids = {}
        for pid in pids.values():
            _matar(pid)


def _conferir(rc, restam, saiu_no_prazo, sinal) -> None:
    nome = signal.Signals(sinal).name
    assert saiu_no_prazo, f"o coletor não terminou em {PRAZO}s depois de {nome}"
    assert not restam, (
        f"{PRAZO}s depois de {nome} no coletor ainda há processo órfão vivo: {restam}"
    )
    assert rc != 0, f"coletor cancelado por {nome} não pode sair com rc 0 (sucesso)"


SINAIS = [signal.SIGTERM, signal.SIGINT, signal.SIGHUP]
_IDS = [s.name for s in SINAIS]


# --------------------------------------------------------------------------- #
# 0. Anti-vacuidade da bancada
# --------------------------------------------------------------------------- #


def test_o_path_da_bancada_so_resolve_o_ai_usagebar_falso(tmp_path):
    """Se cair, os testes abaixo poderiam estar exercitando o binário real."""
    so_python = str(_dir_so_python(tmp_path))
    assert shutil.which("ai-usagebar", path=so_python) is None
    path = _instalar_falso(tmp_path, "raise SystemExit(0)\n")
    achado = shutil.which("ai-usagebar", path=path)
    assert achado is not None and Path(achado).parent == tmp_path / "path-com-falso"


def test_vivo_distingue_processo_de_pe_de_processo_encerrado():
    """O detector de órfão usado nas asserções tem de poder dar os dois valores."""
    p = subprocess.Popen([sys.executable, "-c", _DORMIR])
    try:
        assert vivo(p.pid) is True
        p.kill()
        # morto e ainda não colhido = zumbi: conta como "não existe mais"
        limite = time.monotonic() + 5
        while vivo(p.pid) and time.monotonic() < limite:
            time.sleep(0.02)
        assert vivo(p.pid) is False
    finally:
        p.kill()
        p.wait()
    assert vivo(p.pid) is False


# --------------------------------------------------------------------------- #
# 1. O sintoma: sinal no coletor não deixa o ai-usagebar órfão
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("sinal", SINAIS, ids=_IDS)
def test_sinal_no_coletor_encerra_o_ai_usagebar(tmp_path, sinal):
    """O caso central: SIGTERM/SIGINT/SIGHUP no coletor -> filho deixa de existir."""
    rc, restam, saiu = cancelar_e_medir(tmp_path, sinal)
    _conferir(rc, restam, saiu, sinal)


@pytest.mark.parametrize("sinal", SINAIS, ids=_IDS)
def test_sinal_no_coletor_mata_a_forca_o_ai_usagebar_que_ignora_sigterm(tmp_path, sinal):
    """Borda: o filho ignora SIGTERM; mesmo assim some dentro do prazo."""
    rc, restam, saiu = cancelar_e_medir(tmp_path, sinal, ignora_sigterm=True)
    _conferir(rc, restam, saiu, sinal)


@pytest.mark.parametrize("sinal", SINAIS, ids=_IDS)
def test_sinal_no_coletor_encerra_tambem_o_neto(tmp_path, sinal):
    """Borda: o filho iniciou um descendente; nenhum dos dois pode sobrar."""
    rc, restam, saiu = cancelar_e_medir(tmp_path, sinal, com_neto=True)
    _conferir(rc, restam, saiu, sinal)


def test_sigterm_encerra_filho_que_ignora_sigterm_e_o_neto_dele(tmp_path):
    """Borda combinada: filho surdo a SIGTERM e com descendente."""
    rc, restam, saiu = cancelar_e_medir(
        tmp_path, signal.SIGTERM, ignora_sigterm=True, com_neto=True
    )
    _conferir(rc, restam, saiu, signal.SIGTERM)


def test_sigterm_encerra_o_filho_com_a_fonte_ai_usagebar_explicita(tmp_path):
    """O mesmo contrato vale com ``--source ai-usagebar`` pedido na linha de comando."""
    rc, restam, saiu = cancelar_e_medir(
        tmp_path, signal.SIGTERM, com_neto=True, args=("--source", "ai-usagebar")
    )
    _conferir(rc, restam, saiu, signal.SIGTERM)


# --------------------------------------------------------------------------- #
# 2. Timeout do coletor (objetivo verificável da SPEC) — opcional, lento
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    os.environ.get("T60_TESTAR_TIMEOUT") != "1",
    reason="leva ~60 s (timeout real do coletor); rode com T60_TESTAR_TIMEOUT=1",
)
def test_timeout_do_coletor_encerra_o_ai_usagebar_e_o_neto(tmp_path):
    """Sem sinal algum: o coletor desiste sozinho e não deixa descendente vivo.

    O timeout de 60 s e o rc 1 vêm do contrato de T13 (rodada 2), que T60 diz
    não mudar.
    """
    _artefatos()
    arq_pids = tmp_path / "pids.json"
    corpo = _corpo_falso_que_dorme(arq_pids, ignora_sigterm=True, com_neto=True)
    env = _env(_instalar_falso(tmp_path, corpo), tmp_path)
    saida, erro = tmp_path / "coletor.stdout", tmp_path / "coletor.stderr"
    pids: dict = {}
    with open(saida, "w") as fo, open(erro, "w") as fe:
        coletor = subprocess.Popen(
            _BASE_ARGV, cwd=str(REPO_ROOT), env=env, stdin=subprocess.DEVNULL,
            stdout=fo, stderr=fe, start_new_session=True,
        )
    try:
        pids = _esperar_pids(arq_pids, coletor, saida, erro)
        try:
            rc = coletor.wait(timeout=80)
        except subprocess.TimeoutExpired:
            pytest.fail("o coletor não desistiu em 80 s (timeout contratado: 60 s)")
        restam = _sobreviventes(pids, time.monotonic() + PRAZO)
        assert not restam, f"depois do timeout do coletor ainda há processo vivo: {restam}"
        assert rc == 1, f"timeout é falha comum (rc 1), veio rc={rc}"
    finally:
        try:
            os.killpg(coletor.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        if coletor.poll() is None:
            coletor.kill()
            coletor.wait(timeout=5)
        for pid in pids.values():
            _matar(pid)


# --------------------------------------------------------------------------- #
# 3. Caminho feliz e caso negativo: sem sinal, nada é cancelado
# --------------------------------------------------------------------------- #


def _rodar(tmp_path, corpo, *args):
    _artefatos()
    env = _env(_instalar_falso(tmp_path, corpo), tmp_path)
    return subprocess.run(
        _BASE_ARGV + [str(a) for a in args],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=60,
    )


def test_caminho_feliz_devolve_relatorio_da_fonte_ai_usagebar(tmp_path):
    """Falso que responde na hora -> rc 0, JSON do modelo, ``source`` declarada."""
    corpo = f"import sys\nsys.stdout.write({RELATORIO_MINIMO!r})\n"
    proc = _rodar(tmp_path, corpo, "--source", "ai-usagebar")
    assert proc.returncode == 0, f"rc={proc.returncode} stderr={proc.stderr!r}"
    dados = json.loads(proc.stdout)
    assert dados["source"] == "ai-usagebar"
    assert dados["schema"] == 1
    assert dados["primary"] is None
    assert dados["all"] == []
    assert dados["total_providers"] == 0


def test_filho_lento_que_termina_sozinho_nao_e_cancelado(tmp_path):
    """Negativo: sem sinal, o coletor ESPERA o filho e entrega o relatório dele.

    Um conserto que matasse o ``ai-usagebar`` cedo demais (ou que tratasse a
    espera como cancelamento) cairia aqui: o falso só imprime depois de 1,5 s.
    """
    marca = tmp_path / "filho-terminou"
    corpo = (
        "import sys, time\n"
        "time.sleep(1.5)\n"
        f"sys.stdout.write({RELATORIO_MINIMO!r})\n"
        "sys.stdout.flush()\n"
        f"open({str(marca)!r}, 'w').close()\n"
    )
    proc = _rodar(tmp_path, corpo)
    assert proc.returncode == 0, f"rc={proc.returncode} stderr={proc.stderr!r}"
    assert marca.is_file(), "o ai-usagebar falso foi interrompido antes de terminar"
    dados = json.loads(proc.stdout)
    assert dados["schema"] == 1
    assert dados["all"] == []


def test_falha_do_ai_usagebar_continua_sendo_rc_um(tmp_path):
    """Negativo: rc != 0 do upstream segue sendo falha comum (rc 1), sem JSON."""
    proc = _rodar(tmp_path, "import sys\nsys.exit(7)\n")
    assert proc.returncode == 1, f"rc={proc.returncode} stderr={proc.stderr!r}"
    assert proc.stdout.strip() == ""
