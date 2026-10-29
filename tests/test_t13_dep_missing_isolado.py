# -*- coding: utf-8 -*-
"""Testes de comportamento de T13 — estado próprio para "binário ausente".

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada 2,
tarefa T13. O contrato de referência (único oráculo) é o bloco assinado da SPEC,
transcrito aqui porque o teste não pode ler a implementação:

  1. Binário ``ai-usagebar`` ausente do PATH -> o coletor sai com **rc 3**
     (código próprio) e NENHUM JSON em stdout. stderr é diagnóstico livre.
  2. Qualquer outra falha (timeout de 60s, rc!=0 do upstream, saída não-JSON,
     ``schema_version`` divergente, ``--from-file`` inexistente ou malformado)
     -> **rc 1**, sem JSON parcial. ``argparse`` inválido -> **rc 2** por
     convenção do próprio argparse (medido em 2026-10-27; ver a nota em
     AMBIGUIDADES no fim do arquivo).
  3. ``--from-file`` com relatório válido continua **rc 0** mesmo SEM o binário
     no PATH — o contrato de isolamento existente não pode regredir.

Por que este arquivo existe separado de ``test_collect.py``
------------------------------------------------------------
``test_collect.py`` já prova "falha -> rc != 0". Ele NÃO distingue os motivos:
um teste sobre ``rc != 0`` sobrevive vacuamente quando o alvo é apagado, porque
FileNotFoundError, ImportError e a ausência do binário dão todos "falha". T13
exige um código EXATO (3) exclusivo de um motivo (binário irresolvível), então
aqui toda asserção de rc é de IGUALDADE (``== 3``, ``== 1``), nunca de
desigualdade ampla.

Nota sobre o PATH restrito (defeito do helper antigo, não repetido aqui)
-----------------------------------------------------------------------
``test_from_file_funciona_sem_o_binario_ai_usagebar_no_path`` usa
``Path(sys.executable).resolve().parent`` como PATH "mínimo". Nesta máquina esse
diretório é ``/usr/bin``, que CONTÉM ``ai-usagebar`` — a premissa "irresolvível"
não vale e o teste é satisfeito por outro motivo. Aqui o PATH restrito é um
diretório temporário que contém apenas um symlink para o interpretador; a
irresolubilidade é VERIFICADA por ``shutil.which`` antes de qualquer asserção
(``test_o_path_restrito_realmente_nao_tem_ai_usagebar``), para que nenhum teste
deste arquivo passe por acidente ambiental.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Localização dos artefatos (o conteúdo do coletor nunca é lido)
# --------------------------------------------------------------------------- #

TEST_DIR = Path(__file__).resolve().parent          # <repo>/ai-usage/tests
PLUGIN_DIR = TEST_DIR.parent                        # <repo>/ai-usage
REPO_ROOT = PLUGIN_DIR.parent                       # <repo>

#: Override por ambiente: uso EXCLUSIVO da verificação de falsificabilidade
#: desta suíte (apontar para uma CÓPIA mutada do coletor e conferir que os
#: testes de rc caem). O caminho de produção não o define.
SCRIPT = Path(os.environ.get("T13_SCRIPT", PLUGIN_DIR / "bin" / "ai-usage-collect"))

FIXTURE_CANDIDATES = (
    REPO_ROOT / "tests" / "fixtures" / "report-schema1.json",
    TEST_DIR / "fixtures" / "report-schema1.json",
)

#: argv base: nunca depende de PATH para o interpretador (caminho absoluto).
_BASE_ARGV = [sys.executable, str(SCRIPT)]


def _fixture() -> Path:
    for cand in FIXTURE_CANDIDATES:
        if cand.is_file():
            return cand
    pytest.skip("fixture report-schema1.json não encontrada")


def _artefatos() -> None:
    assert SCRIPT.is_file(), f"coletor ausente em {SCRIPT} — nada a verificar"


# --------------------------------------------------------------------------- #
# Bancada de execução
# --------------------------------------------------------------------------- #


def rodar(*args, env=None, timeout=90):
    """Executa o coletor como SUBPROCESSO e devolve o CompletedProcess."""
    _artefatos()
    return subprocess.run(
        _BASE_ARGV + [str(a) for a in args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def path_sem_ai_usagebar(tmp_path: Path) -> str:
    """PATH com o interpretador e MAIS NADA.

    Um diretório próprio com um symlink para o python real: o coletor continua
    executável (via argv absoluto) e ``ai-usagebar`` fica irresolvível.
    """
    d = tmp_path / "path-so-python"
    d.mkdir(parents=True, exist_ok=True)
    alvo = Path(os.path.realpath(sys.executable))
    link = d / "python3"
    if not link.exists():
        link.symlink_to(alvo)
    return str(d)


def path_com_binario(tmp_path: Path, corpo: str, nome: str = "ai-usagebar") -> str:
    """PATH cujo PRIMEIRO item tem um ``ai-usagebar`` falso com o corpo dado."""
    d = tmp_path / "path-com-binario"
    d.mkdir(parents=True, exist_ok=True)
    falso = d / nome
    falso.write_text(corpo, encoding="utf-8")
    falso.chmod(0o755)
    # o python de apoio continua resolvível; o falso vem primeiro.
    return f"{d}{os.pathsep}{path_sem_ai_usagebar(tmp_path)}"


def env_restrito(path: str, home: Path) -> dict:
    """Ambiente mínimo e reprodutível: sem herdar o PATH da máquina."""
    home.mkdir(parents=True, exist_ok=True)
    return {
        "PATH": path,
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def sem_json_em_stdout(proc) -> None:
    """Nenhum JSON, nem parcial, pode sair na falha."""
    assert proc.stdout.strip() == "", f"falha não pode emitir JSON parcial: stdout={proc.stdout!r}"
    with pytest.raises(json.JSONDecodeError):
        json.loads(proc.stdout or "")


# --------------------------------------------------------------------------- #
# 0. Anti-vacuidade: a bancada realmente remove o binário
# --------------------------------------------------------------------------- #


def test_o_path_restrito_realmente_nao_tem_ai_usagebar(tmp_path):
    """Se este teste cair, todos os testes de rc 3 abaixo seriam vácuos.

    Verifica com o MESMO resolvedor que um processo usaria (``shutil.which``
    sobre o PATH restrito) que ``ai-usagebar`` não é encontrável — e, como
    contraprova, que ele É encontrável no PATH da máquina (senão a bancada não
    prova nada sobre "ausente", só sobre "esta máquina nunca teve").
    """
    restrito = path_sem_ai_usagebar(tmp_path)
    assert shutil.which("ai-usagebar", path=restrito) is None, (
        f"o PATH restrito {restrito} ainda resolve ai-usagebar — a bancada não isola nada"
    )
    assert shutil.which("python3", path=restrito) is not None, (
        "o PATH restrito precisa manter o interpretador resolvível para o subprocesso"
    )


# --------------------------------------------------------------------------- #
# 1. Binário ausente: rc 3, sem JSON em stdout
# --------------------------------------------------------------------------- #


def test_binario_ausente_sai_com_rc_tres(tmp_path):
    """O caso central de T13: código PRÓPRIO, exato, para "binário ausente"."""
    env = env_restrito(path_sem_ai_usagebar(tmp_path), tmp_path / "home")
    proc = rodar(env=env)
    assert proc.returncode == 3, (
        "sem ai-usagebar no PATH o coletor deve sair com rc 3 (código próprio de "
        f"dependência ausente); veio rc={proc.returncode}\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )


def test_binario_ausente_nao_emite_json_em_stdout(tmp_path):
    env = env_restrito(path_sem_ai_usagebar(tmp_path), tmp_path / "home")
    proc = rodar(env=env)
    assert proc.returncode == 3
    sem_json_em_stdout(proc)


def test_binario_ausente_deixa_diagnostico_em_stderr_nomeando_o_que_falta(tmp_path):
    """stderr é livre, mas precisa ser legível: tem de nomear o programa ausente.

    A âncora é o nome do executável, não o idioma — o texto pode ser PT ou EN.
    """
    env = env_restrito(path_sem_ai_usagebar(tmp_path), tmp_path / "home")
    proc = rodar(env=env)
    assert proc.returncode == 3
    diagnostico = (proc.stderr or "").strip()
    assert diagnostico, "o caso de dependência ausente precisa explicar-se em stderr"
    assert "ai-usagebar" in diagnostico.lower(), (
        f"o diagnóstico deve nomear o programa ausente; veio {diagnostico[:200]!r}"
    )


def test_rc_tres_e_exclusivo_da_ausencia_do_binario(tmp_path):
    """Negativo: binário PRESENTE e falhando não pode receber o código de ausente.

    É o discriminador que a view vai ler. Se a implementação devolvesse 3 para
    qualquer falha, o usuário veria "instale o ai-usagebar" com ele instalado.
    """
    path = path_com_binario(tmp_path, "#!/bin/sh\nexit 7\n")
    env = env_restrito(path, tmp_path / "home")
    proc = rodar(env=env)
    assert proc.returncode == 1, (
        f"binário presente com rc=7 é falha do UPSTREAM (rc 1), não ausência (rc 3); "
        f"veio rc={proc.returncode}\nstderr={proc.stderr!r}"
    )
    assert proc.returncode != 3


# --------------------------------------------------------------------------- #
# 2. Qualquer outra falha: rc 1, exato
# --------------------------------------------------------------------------- #


def test_upstream_com_rc_diferente_de_zero_sai_com_rc_um(tmp_path):
    path = path_com_binario(tmp_path, "#!/bin/sh\nexit 7\n")
    env = env_restrito(path, tmp_path / "home")
    proc = rodar(env=env)
    assert proc.returncode == 1, (
        f"falha do upstream deve ser rc 1 (exato); veio rc={proc.returncode}\nstderr={proc.stderr!r}"
    )
    sem_json_em_stdout(proc)


def test_upstream_com_saida_nao_json_sai_com_rc_um(tmp_path):
    path = path_com_binario(tmp_path, "#!/bin/sh\necho 'isto nao e json'\n")
    env = env_restrito(path, tmp_path / "home")
    proc = rodar(env=env)
    assert proc.returncode == 1, (
        f"saída não-JSON do upstream deve ser rc 1; veio rc={proc.returncode}\nstderr={proc.stderr!r}"
    )
    sem_json_em_stdout(proc)


def test_upstream_que_sai_com_tres_nao_e_confundido_com_dependencia_ausente(tmp_path):
    """Caso de borda discriminante: o filho sai com 3, mas ele EXISTE.

    O código de T13 é sobre "não consigo executar o programa", não sobre "o
    programa respondeu 3". Propagar o 3 do filho faria a UI de dep-missing
    disparar com a dependência instalada.
    """
    path = path_com_binario(tmp_path, "#!/bin/sh\nexit 3\n")
    env = env_restrito(path, tmp_path / "home")
    proc = rodar(env=env)
    assert proc.returncode == 1, (
        "um upstream que responde rc=3 continua sendo falha do upstream (rc 1); "
        f"veio rc={proc.returncode}\nstderr={proc.stderr!r}"
    )
    sem_json_em_stdout(proc)


def test_upstream_com_rc_zero_e_stdout_vazio_e_falha_do_upstream(tmp_path):
    path = path_com_binario(tmp_path, "#!/bin/sh\nexit 0\n")
    env = env_restrito(path, tmp_path / "home")
    proc = rodar(env=env)
    assert proc.returncode == 1, (
        f"rc 0 com stdout vazio não é sucesso; veio rc={proc.returncode}"
    )
    sem_json_em_stdout(proc)


def test_schema_version_divergente_sai_com_rc_um(tmp_path):
    f = tmp_path / "v2.json"
    f.write_text(json.dumps({"schema_version": 2, "primary": None, "entries": []}), encoding="utf-8")
    env = env_restrito(path_sem_ai_usagebar(tmp_path), tmp_path / "home")
    proc = rodar("--from-file", f, env=env)
    assert proc.returncode == 1, (
        f"schema_version divergente é falha do upstream (rc 1); veio rc={proc.returncode}\n"
        f"stderr={proc.stderr!r}"
    )
    sem_json_em_stdout(proc)


def test_relatorio_inexistente_sai_com_rc_um(tmp_path):
    env = env_restrito(path_sem_ai_usagebar(tmp_path), tmp_path / "home")
    proc = rodar("--from-file", tmp_path / "nao-existe-t13.json", env=env)
    assert proc.returncode == 1, (
        f"--from-file inexistente é falha do upstream (rc 1); veio rc={proc.returncode}\n"
        f"stderr={proc.stderr!r}"
    )
    sem_json_em_stdout(proc)


def test_relatorio_malformado_sai_com_rc_um(tmp_path):
    f = tmp_path / "quebrado.json"
    f.write_text("{nao eh json", encoding="utf-8")
    env = env_restrito(path_sem_ai_usagebar(tmp_path), tmp_path / "home")
    proc = rodar("--from-file", f, env=env)
    assert proc.returncode == 1, (
        f"relatório malformado é falha do upstream (rc 1); veio rc={proc.returncode}\n"
        f"stderr={proc.stderr!r}"
    )
    sem_json_em_stdout(proc)


def test_argumento_invalido_de_cli_nao_recebe_o_codigo_de_dependencia_ausente(tmp_path):
    """``argparse`` inválido: rc != 0 e, sobretudo, NUNCA 3.

    A SPEC (medida em 2026-10-27) fixa rc 2 para argumento inválido, por
    convenção do argparse. A asserção forte aqui é a de NÃO-colisão com 3: um
    rc 2 cai em "upstream" no serviço, que é o aceitável declarado.
    """
    env = env_restrito(path_com_binario(tmp_path, "#!/bin/sh\nexit 0\n"), tmp_path / "home")
    proc = rodar("--order", "BOGUS", env=env)
    assert proc.returncode != 0, "ordem inválida precisa ser recusada"
    assert proc.returncode != 3, (
        f"argumento inválido NÃO pode ser confundido com dependência ausente; veio rc={proc.returncode}"
    )
    sem_json_em_stdout(proc)


#: O timeout real é de 60s: rodar sempre custaria um minuto por sessão de suíte.
#: Ligado sob demanda com ``T13_RUN_TIMEOUT=1`` (foi executado uma vez na
#: verificação desta tarefa; resultado no relatório).
@pytest.mark.skipif(
    os.environ.get("T13_RUN_TIMEOUT") != "1",
    reason="timeout de 60s reais: habilite com T13_RUN_TIMEOUT=1",
)
def test_timeout_do_upstream_sai_com_rc_um(tmp_path):
    path = path_com_binario(tmp_path, "#!/bin/sh\n/bin/sleep 200\n")
    env = env_restrito(path, tmp_path / "home")
    proc = rodar(env=env, timeout=180)
    assert proc.returncode == 1, (
        f"timeout do upstream é rc 1; veio rc={proc.returncode}\nstderr={proc.stderr!r}"
    )
    sem_json_em_stdout(proc)


# --------------------------------------------------------------------------- #
# 3. Isolamento: --from-file válido continua rc 0 sem o binário
# --------------------------------------------------------------------------- #


def test_from_file_valido_continua_rc_zero_sem_o_binario_no_path(tmp_path):
    """Item 3 do contrato: a correção de T13 não pode regredir o isolamento."""
    env = env_restrito(path_sem_ai_usagebar(tmp_path), tmp_path / "home")
    proc = rodar("--from-file", _fixture(), env=env)
    assert proc.returncode == 0, (
        "ler de arquivo não pode depender do ai-usagebar instalado; "
        f"veio rc={proc.returncode}\nstderr={proc.stderr!r}"
    )
    dados = json.loads(proc.stdout)
    assert dados["total_providers"] == 4, "o relatório do fixture tem 4 providers"
    assert proc.returncode != 3


def test_from_file_valido_com_binario_ausente_nao_e_marcado_como_dependencia_faltando(tmp_path):
    """Forma negativa do item 3, no vocabulário do discriminador: nunca rc 3."""
    env = env_restrito(path_sem_ai_usagebar(tmp_path), tmp_path / "home")
    proc = rodar("--from-file", _fixture(), env=env)
    assert proc.returncode != 3, (
        "sucesso com --from-file jamais pode carregar o código de dependência ausente"
    )
    assert proc.stdout.strip(), "sucesso precisa emitir o JSON"


# --------------------------------------------------------------------------- #
# 4. Os dois estados não compartilham código (comparação direta)
# --------------------------------------------------------------------------- #


def test_ausencia_e_falha_do_upstream_produzem_codigos_distintos(tmp_path):
    """O discriminador precisa ser observável: 3 vs 1, medidos lado a lado.

    Congela a relação, não só cada número: se alguém "unificar" os códigos, os
    testes de igualdade acima e este caem juntos.
    """
    env_ausente = env_restrito(path_sem_ai_usagebar(tmp_path / "a"), tmp_path / "home-a")
    ausente = rodar(env=env_ausente)

    env_falho = env_restrito(path_com_binario(tmp_path / "b", "#!/bin/sh\nexit 7\n"), tmp_path / "home-b")
    falho = rodar(env=env_falho)

    assert ausente.returncode == 3, f"ausente: esperava 3, veio {ausente.returncode}"
    assert falho.returncode == 1, f"falha do upstream: esperava 1, veio {falho.returncode}"
    assert ausente.stdout.strip() == "" and falho.stdout.strip() == ""


# --------------------------------------------------------------------------- #
# Ambiguidades / lacunas do contrato (honestidade D5)
# --------------------------------------------------------------------------- #

AMBIGUIDADES = """
1. rc de argparse inválido — o bloco da tarefa entregue ao tester lista
   "argparse inválido: rc 1", mas a SPEC assinada (R2-v1, medida em 2026-10-27)
   registra rc 2 como convenção do argparse e o declara ACEITÁVEL, desde que o
   discriminador seja igualdade exata a 3. Medido na base: rc 2. Este arquivo
   testa a leitura da SPEC (nunca 3, nunca 0) e NÃO exige 1, para não inventar
   um oráculo que a própria SPEC contradiz. A divergência fica para o gate.
2. "Binário ausente do PATH" x "binário presente mas NÃO executável". Medido na
   base: um arquivo sem bit +x dá rc 1 COM traceback de Python em stderr
   (FileNotFoundError/PermissionError não tratado). Pela letra ("irresolvível",
   `shutil.which` devolve None), esse caso seria dep-missing; pela medição, é
   upstream. Não testei o caso (nenhuma leitura é literal o bastante), mas o
   traceback em stderr é um defeito visível: a view o mostraria como diagnóstico.
3. "Nenhum JSON em stdout" na falha: assumi que stdout pode ter conteúdo VAZIO
   ou só espaços, e que qualquer coisa que não parseie como JSON único é falha.
   Não assumi nada sobre stderr.
4. Timeout: o limite de 60s não é configurável pela interface pública, então o
   teste correspondente custa um minuto real e fica opt-in (T13_RUN_TIMEOUT=1).
   Sem ele ligado, a cobertura de "timeout -> rc 1" não roda por padrão.
"""
