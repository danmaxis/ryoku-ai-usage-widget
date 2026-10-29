# -*- coding: utf-8 -*-
"""Contrato de COMPORTAMENTO de T15 — ordem manual dos providers (itens 1-6).

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada 2,
tarefa T15. O oráculo é o bloco do contrato fixado em 2026-10-27 ANTES da
implementação, transcrito aqui porque o teste não pode (e não deve) ler o código:

  1. Flags: ``--order manual`` exige ``--sequence IDS``. ``--order manual`` SEM
     ``--sequence``, ou ``--sequence`` com ``--order`` diferente de ``manual``,
     é erro de uso: **rc 2** e nada em stdout.
  2. Parsing: vírgula; espaços em volta removidos; comparação case-insensitive;
     entrada vazia/só espaços = sequência vazia VÁLIDA (= ordem do relatório);
     duplicata → a PRIMEIRA ocorrência manda.
  3. Ordenação: citados primeiro na ordem da sequência; NÃO citados depois,
     preservando a ordem do relatório (estável); ids inexistentes ignorados em
     silêncio (não criam provider, não quebram).
  4. Destaque: o primeiro provider ``status == "ready"`` E ``headline_metric``
     não-nulo na ORDEM RESULTANTE é o ``primario``. Citado em ``error`` é pulado
     no destaque mas continua em ``todos`` na sua posição.
  5. ``--primary`` explícito vence a ordem manual se o provider estiver pronto.
     Sem ``--primary``, o ``primary`` do RELATÓRIO é ignorado em ``manual``.
  6. Nada disso muda ``upstream``/``alphabetical``/``highest``/``lowest``.

O coletor é invocado como SUBPROCESSO (nunca importado) e sempre com
``--from-file``: nenhum teste toca o binário ``ai-usagebar`` real, a rede ou o
config do upstream.

Fixture própria, e por que ela é PRÓPRIA
----------------------------------------
O fixture compartilhado (``tests/fixtures/report-schema1.json``) tem
``anthropic, copilot, zai, openai@work`` — ordem que coincide parcialmente com a
alfabética e com a de percentual, então um teste de ordem montado sobre ele pode
passar por acidente. Aqui a ordem do relatório é deliberadamente "anti-todo-mundo":

    índice  id            estado                   percent
    1       zulu          ready                    10
    2       alpha         ready                    80   (e é o `primary` do relatório)
    3       mike          error                    —
    4       kilo          ready, metrics []        (headline_metric null)
    5       echo          ready                    30
    6       whiskey       ready                    50
    7       openai@work   ready                    42

Nem alfabética, nem por percentual, nem com o erro no fim: qualquer reordenação
acidental (sort estável mal feito, fallback alfabético, "prontos primeiro")
aparece na comparação de lista completa.

Divergência de contrato registrada (NÃO inventada aqui): ver ``AMBIGUIDADES``.
"""

from __future__ import annotations

import json
import os
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
#: (apontar para uma CÓPIA mutada). O caminho de produção não o define.
SCRIPT = Path(os.environ.get("T15_SCRIPT", PLUGIN_DIR / "bin" / "ai-usage-collect"))

#: argv base: interpretador por caminho absoluto, nunca via PATH.
_BASE_ARGV = [sys.executable, str(SCRIPT)]

#: ordem do relatório da fixture própria (ver docstring do módulo)
ORDEM_RELATORIO = ["zulu", "alpha", "mike", "kilo", "echo", "whiskey", "openai@work"]

#: ``primary`` declarado DENTRO do relatório da fixture própria
PRIMARY_DO_RELATORIO = "alpha"


# --------------------------------------------------------------------------- #
# Bancada
# --------------------------------------------------------------------------- #


def rodar(*args, timeout=60):
    """Executa o coletor como SUBPROCESSO e devolve o CompletedProcess."""
    assert SCRIPT.is_file(), f"coletor ausente em {SCRIPT} — nada a verificar"
    return subprocess.run(
        _BASE_ARGV + [str(a) for a in args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def rodar_ok(*args, **kw):
    """Caminho feliz: rc 0 + stdout JSON único. Devolve o dict parseado."""
    proc = rodar(*args, **kw)
    assert proc.returncode == 0, (
        f"esperava rc 0, veio {proc.returncode}\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - só em falha real
        pytest.fail(f"stdout não é JSON parseável: {exc}\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}")


def erro_de_uso(proc) -> None:
    """Item 1: rc EXATO 2 e stdout vazio (nenhum JSON parcial)."""
    assert proc.returncode == 2, (
        f"erro de uso deve sair com rc 2 (exato), veio rc={proc.returncode}\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    assert proc.stdout.strip() == "", (
        f"erro de uso não pode emitir nada em stdout, veio {proc.stdout!r}"
    )


def ids(dados) -> list[str]:
    return [p["id"] for p in dados["all"]]


def provider(dados, pid: str) -> dict:
    achados = [p for p in dados["all"] if p["id"] == pid]
    assert achados, f"provider {pid!r} ausente de todos: {ids(dados)}"
    return achados[0]


# --------------------------------------------------------------------------- #
# Fixture própria
# --------------------------------------------------------------------------- #


def metrica(label="Session (5h)", percent=10, headline="percent", severity="low") -> dict:
    return {
        "label": label,
        "percent": percent,
        "value": f"{percent}%",
        "headline": headline,
        "severity": severity,
        "detail": f"detail de {label}",
        "reset_at": "2026-11-01T00:00:00Z",
        "window_secs": 18000,
    }


def entrada(pid: str, *, status="ready", metrics=None, error=None, display=None) -> dict:
    vendor = pid.split("@", 1)[0]
    return {
        "id": pid,
        "name": vendor,
        "display_name": display or pid,
        "short_name": vendor[:3],
        "icon": "i",
        "brand": vendor,
        "plan": None,
        "status": status,
        "error": error,
        "stale": False,
        "fetched_at": "2026-10-15T12:00:00Z" if status == "ready" else None,
        "reset_credits": None,
        "metrics": list(metrics) if metrics is not None else [metrica()],
        "sections": [],
    }


def escrever_fixture(tmp_path: Path, nome: str, payload: dict) -> Path:
    destino = tmp_path / nome
    destino.write_text(json.dumps(payload), encoding="utf-8")
    return destino


@pytest.fixture()
def fixture_ordem(tmp_path) -> Path:
    """A fixture discriminante descrita no docstring do módulo."""
    entries = [
        entrada("zulu", metrics=[metrica(percent=10)], display="Zulu"),
        entrada("alpha", metrics=[metrica(percent=80)], display="Alpha"),
        entrada("mike", status="error", error="sem credencial (fixture)", display="Mike"),
        entrada("kilo", metrics=[], display="Kilo"),          # ready, headline null
        entrada("echo", metrics=[metrica(percent=30)], display="Echo"),
        entrada("whiskey", metrics=[metrica(percent=50)], display="Whiskey"),
        entrada("openai@work", metrics=[metrica(percent=42)], display="Codex · work"),
    ]
    return escrever_fixture(
        tmp_path,
        "t15-ordem.json",
        {"schema_version": 1, "primary": PRIMARY_DO_RELATORIO, "entries": entries},
    )


def manual(fixture: Path, sequencia: str, *extra):
    """Atalho do caminho feliz do modo manual."""
    return rodar_ok("--from-file", fixture, "--order", "manual", "--sequence", sequencia, *extra)


# --------------------------------------------------------------------------- #
# 0. Anti-vacuidade: a fixture é o que o docstring promete
# --------------------------------------------------------------------------- #


def test_fixture_tem_ordem_propria_distinta_de_alfabetica_e_de_percentual(fixture_ordem):
    """Se a fixture "colapsar" numa ordem trivial, os testes de ordem ficam vácuos.

    Prova, sobre a SAÍDA do modo ``upstream`` (que ecoa a ordem do relatório),
    que a ordem esperada não é nem a alfabética nem a de percentual decrescente.
    """
    d = rodar_ok("--from-file", fixture_ordem, "--order", "upstream")
    saida = ids(d)
    assert saida == ORDEM_RELATORIO, f"upstream deve ecoar a ordem do relatório; veio {saida}"
    assert saida != sorted(saida), "a fixture não pode estar em ordem alfabética"
    assert saida != ["alpha", "whiskey", "openai@work", "echo", "zulu", "kilo", "mike"], (
        "a fixture não pode estar ordenada por percentual"
    )
    assert saida[-1] != "mike", "a fixture não pode deixar o provider em erro por último"


# --------------------------------------------------------------------------- #
# 1. Flags: rc EXATO 2 para combinação inválida
# --------------------------------------------------------------------------- #


def test_order_manual_sem_sequence_e_erro_de_uso_rc_dois(fixture_ordem):
    """Item 1, caso central. ``rc == 2`` EXATO: != 0 aceitaria rc 1 (upstream)."""
    erro_de_uso(rodar("--from-file", fixture_ordem, "--order", "manual"))


def test_order_manual_sem_sequence_nao_emite_json(fixture_ordem):
    """Repetido como asserção própria para que a falha aponte o stdout, não o rc."""
    proc = rodar("--from-file", fixture_ordem, "--order", "manual")
    assert proc.returncode == 2, f"veio rc={proc.returncode}"
    assert proc.stdout.strip() == ""
    with pytest.raises(json.JSONDecodeError):
        json.loads(proc.stdout or "")


@pytest.mark.parametrize("modo", ["upstream", "highest", "lowest", "alphabetical"])
def test_sequence_com_order_diferente_de_manual_e_erro_de_uso(fixture_ordem, modo):
    """Item 1: ``--sequence`` só faz sentido em ``manual``; nos outros, rc 2."""
    erro_de_uso(rodar("--from-file", fixture_ordem, "--order", modo, "--sequence", "zulu,alpha"))


def test_sequence_sem_order_nenhum_e_erro_de_uso(fixture_ordem):
    """Sem ``--order`` o default é ``upstream`` — que não é ``manual`` (item 1)."""
    erro_de_uso(rodar("--from-file", fixture_ordem, "--sequence", "zulu,alpha"))


def test_sequence_vazia_com_outro_order_tambem_e_erro_de_uso(fixture_ordem):
    """Caso de borda do item 1: a presença da FLAG basta para o erro, mesmo vazia."""
    erro_de_uso(rodar("--from-file", fixture_ordem, "--order", "highest", "--sequence", ""))


def test_o_par_valido_de_flags_nao_e_erro_de_uso(fixture_ordem):
    """ANTI-VACUIDADE do item 1.

    Sem este teste, os rc 2 acima sobreviveriam se ``manual`` simplesmente não
    existisse como escolha de ``--order`` (todo argv com ``manual`` daria rc 2
    por motivo errado). Aqui o par válido precisa dar rc 0.
    """
    proc = rodar("--from-file", fixture_ordem, "--order", "manual", "--sequence", "zulu")
    assert proc.returncode == 0, (
        f"``--order manual --sequence zulu`` é o par válido do contrato; veio rc={proc.returncode}\n"
        f"stderr={proc.stderr!r}"
    )
    dados = json.loads(proc.stdout)
    assert ids(dados) == ORDEM_RELATORIO


# --------------------------------------------------------------------------- #
# 2. Parsing da sequência
# --------------------------------------------------------------------------- #


def test_espacos_em_volta_dos_ids_sao_removidos(fixture_ordem):
    canonico = manual(fixture_ordem, "zulu,alpha")
    com_espacos = manual(fixture_ordem, "  zulu ,  alpha  ")
    assert com_espacos == canonico, (
        "espaços em volta dos ids não podem mudar a saída\n"
        f"canônico={ids(canonico)}\ncom espaços={ids(com_espacos)}"
    )
    assert ids(com_espacos) == ["zulu", "alpha", "mike", "kilo", "echo", "whiskey", "openai@work"]


def test_espaco_dentro_do_id_nao_e_id_valido(fixture_ordem):
    """Caso negativo do parsing: só as PONTAS são aparadas.

    ``"zul u"`` não é ``zulu``; o id inexistente é ignorado em silêncio (item 3),
    então a ordem volta a ser a do relatório. Se o parser removesse espaços
    internos, ``zulu`` subiria e o teste falharia.
    """
    d = manual(fixture_ordem, "zul u,alpha")
    assert ids(d) == ["alpha", "zulu", "mike", "kilo", "echo", "whiskey", "openai@work"], ids(d)


def test_comparacao_e_case_insensitive(fixture_ordem):
    canonico = manual(fixture_ordem, "zulu,alpha")
    maiusculo = manual(fixture_ordem, "ZULU,Alpha")
    assert maiusculo == canonico, (
        "'ZULU,Alpha' deve casar com 'zulu,alpha'\n"
        f"canônico={ids(canonico)}\nmaiúsculo={ids(maiusculo)}"
    )
    assert ids(maiusculo)[:2] == ["zulu", "alpha"], (
        f"os ids devem sair na grafia do RELATÓRIO, na ordem da sequência; veio {ids(maiusculo)[:2]}"
    )


def test_entrada_vazia_e_sequencia_vazia_valida(fixture_ordem):
    """Item 2: vazio é VÁLIDO e equivale à ordem do relatório (rc 0, não erro)."""
    d = manual(fixture_ordem, "")
    assert ids(d) == ORDEM_RELATORIO, ids(d)
    assert d["primary"]["id"] == "zulu", (
        f"com sequência vazia o destaque é o primeiro pronto do relatório; veio {d['primary']['id']}"
    )
    assert d["total_providers"] == len(ORDEM_RELATORIO)


def test_entrada_so_com_espacos_equivale_a_sequencia_vazia(fixture_ordem):
    vazia = manual(fixture_ordem, "")
    espacos = manual(fixture_ordem, "   ")
    assert espacos == vazia, (
        "entrada só de espaços deve ser sequência vazia\n"
        f"vazia={ids(vazia)}\nespaços={ids(espacos)}"
    )


def test_duplicata_mantem_a_primeira_ocorrencia(fixture_ordem):
    """Item 2: a PRIMEIRA ocorrência manda; a repetição é ignorada."""
    d = manual(fixture_ordem, "alpha,zulu,alpha")
    assert ids(d) == ["alpha", "zulu", "mike", "kilo", "echo", "whiskey", "openai@work"], ids(d)
    assert ids(d).count("alpha") == 1, f"provider duplicado na lista: {ids(d)}"


def test_duplicata_nao_move_o_id_para_a_posicao_da_repeticao(fixture_ordem):
    """Caso negativo: se a última ocorrência vencesse, ``echo`` iria para o fim."""
    d = manual(fixture_ordem, "echo,alpha,echo")
    assert ids(d).index("echo") == 0, (
        f"a repetição de 'echo' no fim da sequência não pode mover o provider; veio {ids(d)}"
    )
    assert ids(d) == ["echo", "alpha", "zulu", "mike", "kilo", "whiskey", "openai@work"], ids(d)


# --------------------------------------------------------------------------- #
# 3. Ordenação estável dos NÃO citados
# --------------------------------------------------------------------------- #


def test_citados_vem_primeiro_na_ordem_da_sequencia(fixture_ordem):
    d = manual(fixture_ordem, "echo,zulu")
    assert ids(d) == ["echo", "zulu", "alpha", "mike", "kilo", "whiskey", "openai@work"], ids(d)


def test_nao_citados_preservam_a_ordem_do_relatorio(fixture_ordem):
    """PROVA DE ESTABILIDADE (item 3).

    Os quatro não citados estão numa ordem reconhecível (``alpha, mike, kilo,
    openai@work`` — nem alfabética no geral, nem "prontos antes do erro": ``mike``
    em erro vem ANTES de dois prontos). Se a implementação ordenasse os não
    citados por qualquer outro critério (alfabético, status, percentual,
    dicionário de ids), esta lista mudaria.
    """
    d = manual(fixture_ordem, "echo,zulu")
    nao_citados = ids(d)[2:]
    assert nao_citados == ["alpha", "mike", "kilo", "whiskey", "openai@work"], (
        f"não citados devem manter a ordem do relatório; veio {nao_citados}"
    )
    # âncoras: o erro está no meio dos prontos e o alfabeto não governa
    assert nao_citados.index("mike") < nao_citados.index("kilo")
    assert nao_citados != sorted(nao_citados)


def test_citar_so_o_ultimo_do_relatorio_nao_reordena_os_demais(fixture_ordem):
    """Segunda prova de estabilidade, com o citado no FIM da ordem do relatório."""
    d = manual(fixture_ordem, "openai@work")
    assert ids(d) == ["openai@work", "zulu", "alpha", "mike", "kilo", "echo", "whiskey"], ids(d)


def test_citar_todos_inverte_para_a_sequencia_declarada(fixture_ordem):
    """Contraprova: com TODOS citados, a ordem é exatamente a sequência."""
    d = manual(fixture_ordem, "openai@work,kilo,echo,whiskey,alpha,mike,zulu")
    assert ids(d) == ["openai@work", "kilo", "echo", "whiskey", "alpha", "mike", "zulu"], ids(d)


def test_id_inexistente_e_ignorado_em_silencio(fixture_ordem):
    """Item 3: id desconhecido não cria provider, não quebra, não aparece."""
    proc = rodar("--from-file", fixture_ordem, "--order", "manual", "--sequence", "ghost,zulu")
    assert proc.returncode == 0, f"id inexistente é ignorado em silêncio; veio rc={proc.returncode}"
    d = json.loads(proc.stdout)
    assert "ghost" not in ids(d), f"id inexistente criou provider: {ids(d)}"
    assert d["total_providers"] == len(ORDEM_RELATORIO), (
        f"total_providers não pode mudar por id desconhecido; veio {d['total_providers']}"
    )
    assert ids(d) == ["zulu", "alpha", "mike", "kilo", "echo", "whiskey", "openai@work"], ids(d)


def test_sequencia_so_de_ids_inexistentes_equivale_a_sequencia_vazia(fixture_ordem):
    """Caso de borda: nada citado existe ⇒ ordem do relatório, ainda rc 0."""
    d = manual(fixture_ordem, "ghost,phantom")
    assert ids(d) == ORDEM_RELATORIO, ids(d)
    assert d["primary"]["id"] == "zulu"


# --------------------------------------------------------------------------- #
# 4. Destaque: o primeiro PRONTO na ordem resultante
# --------------------------------------------------------------------------- #


def test_primeiro_id_da_sequencia_em_erro_e_pulado_e_o_segundo_vira_primario(fixture_ordem):
    """O TESTE CENTRAL do item 4 (a decisão do dono).

    Sequência ``mike,alpha``: ``mike`` está em ``status: error``. O destaque tem
    de ser ``alpha`` — não ``mike``, e não o ``primary`` do relatório (que também
    é ``alpha`` aqui, por isso a asserção de POSIÇÃO é indispensável: ``mike``
    precisa continuar em ``todos[0]``, provando que o destaque pulou ele na
    ordem resultante).
    """
    d = manual(fixture_ordem, "mike,alpha")
    assert d["primary"]["id"] == "alpha", (
        f"o primeiro citado (mike) está em error; o destaque deve ser o segundo (alpha); "
        f"veio {d['primary']['id']!r}"
    )
    assert d["primary"]["status"] == "ready"
    assert ids(d)[:2] == ["mike", "alpha"], f"mike não ficou na sua posição: {ids(d)}"
    assert provider(d, "mike")["status"] == "error", "mike deve continuar listado como error"
    assert "mike" in [p["id"] for p in d["secondary"]], "mike sumiu dos secundários"


def test_primeiro_citado_pronto_porem_sem_headline_metric_e_pulado(fixture_ordem):
    """Item 4 exige ``ready`` E ``headline_metric`` não-nulo.

    ``kilo`` é ready mas não traz métricas: pode liderar a LISTA, não o destaque.
    """
    d = manual(fixture_ordem, "kilo,echo")
    assert provider(d, "kilo")["headline_metric"] is None, "premissa do teste: kilo sem headline"
    assert ids(d)[0] == "kilo", f"kilo deveria liderar a lista; veio {ids(d)}"
    assert d["primary"]["id"] == "echo", (
        f"primeiro ready COM headline_metric deveria ser echo; veio {d['primary']['id']!r}"
    )


def test_todos_os_citados_em_erro_nao_impedem_o_destaque(fixture_ordem):
    """Caso de borda: só um citado e ele está em erro ⇒ segue a ordem do resto."""
    d = manual(fixture_ordem, "mike")
    assert ids(d)[0] == "mike", ids(d)
    assert d["primary"]["id"] == "zulu", (
        f"sem citado pronto, o destaque é o primeiro pronto do resto (zulu); veio {d['primary']['id']!r}"
    )
    assert d["primary"]["status"] == "ready"


def test_o_primario_do_modo_manual_nunca_esta_em_error(fixture_ordem):
    """Invariante negativo, varrendo várias sequências."""
    for seq in ("mike", "mike,kilo", "mike,whiskey", "", "ghost,mike"):
        d = manual(fixture_ordem, seq)
        if d["primary"] is None:
            continue
        assert d["primary"]["status"] == "ready", f"sequência {seq!r} destacou provider não-pronto"
        assert d["primary"]["headline_metric"] is not None, (
            f"sequência {seq!r} destacou provider sem headline_metric"
        )


def test_o_primario_nunca_aparece_entre_os_secundarios(fixture_ordem):
    d = manual(fixture_ordem, "whiskey,echo")
    assert d["primary"]["id"] == "whiskey"
    assert d["primary"]["id"] not in [p["id"] for p in d["secondary"]]
    assert len(d["secondary"]) == len(ORDEM_RELATORIO) - 1


# --------------------------------------------------------------------------- #
# 5. --primary explícito e o primary do relatório
# --------------------------------------------------------------------------- #


def test_primary_explicito_vence_a_sequencia(fixture_ordem):
    """Item 5: ``--primary`` pronto vence a ordem manual (aqui, o 6º do relatório)."""
    d = manual(fixture_ordem, "echo,zulu", "--primary", "whiskey")
    assert d["primary"]["id"] == "whiskey", (
        f"--primary deve vencer a sequência; veio {d['primary']['id']!r}"
    )
    # ...sem mexer na ORDEM da lista.
    assert ids(d) == ["echo", "zulu", "alpha", "mike", "kilo", "whiskey", "openai@work"], ids(d)
    assert "whiskey" not in [p["id"] for p in d["secondary"]]


def test_primary_do_relatorio_e_ignorado_no_modo_manual(fixture_ordem):
    """Item 5, segunda metade: em ``manual`` o `primary` do relatório não vale.

    O relatório declara ``primary: alpha``. Sem ``--primary``, o destaque é o
    primeiro pronto da SEQUÊNCIA (``echo``) — comparado lado a lado com
    ``upstream`` na MESMA fixture, onde ``alpha`` vale.
    """
    m = manual(fixture_ordem, "echo,zulu")
    up = rodar_ok("--from-file", fixture_ordem, "--order", "upstream")
    assert up["primary"]["id"] == PRIMARY_DO_RELATORIO, "premissa: upstream honra o primary do relatório"
    assert m["primary"]["id"] == "echo", (
        f"em manual o primary do relatório deve ser ignorado; veio {m['primary']['id']!r}"
    )
    assert m["primary"]["id"] != up["primary"]["id"]


def test_primary_apontando_para_provider_em_erro_nao_vira_destaque(fixture_ordem):
    """Item 5 é condicional: "se esse provider estiver pronto"."""
    d = manual(fixture_ordem, "echo,zulu", "--primary", "mike")
    assert provider(d, "mike")["status"] == "error", "premissa: mike está em error"
    assert d["primary"]["status"] == "ready"
    assert d["primary"]["id"] == "echo", (
        "com --primary não-pronto, o destaque volta ao primeiro pronto da ordem "
        f"manual (echo); veio {d['primary']['id']!r}"
    )


def test_primary_inexistente_cai_no_primeiro_pronto_da_ordem_manual(fixture_ordem):
    d = manual(fixture_ordem, "whiskey", "--primary", "nao-existe")
    assert d["primary"]["id"] == "whiskey", (
        f"fallback do --primary inexistente segue a ordem manual; veio {d['primary']['id']!r}"
    )


# --------------------------------------------------------------------------- #
# 6. Não-regressão dos outros modos (MESMA fixture dos testes de manual)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("modo,esperado", [
    ("upstream", "alpha"),      # primary do relatório
    ("highest", "alpha"),       # 80%
    ("lowest", "zulu"),         # 10%
    ("alphabetical", "alpha"),  # "Alpha" < "Codex · work" < ...
])
def test_modos_existentes_mantem_o_destaque_na_mesma_fixture(fixture_ordem, modo, esperado):
    d = rodar_ok("--from-file", fixture_ordem, "--order", modo)
    assert d["primary"]["id"] == esperado, (
        f"order={modo} deveria destacar {esperado!r}; veio {d['primary']['id']!r}"
    )


def test_upstream_continua_byte_a_byte_a_ordem_do_relatorio(fixture_ordem):
    d = rodar_ok("--from-file", fixture_ordem, "--order", "upstream")
    assert ids(d) == ORDEM_RELATORIO, ids(d)
    assert d["total_providers"] == len(ORDEM_RELATORIO)


def test_highest_e_lowest_continuam_ordenando_por_percentual(fixture_ordem):
    alto = rodar_ok("--from-file", fixture_ordem, "--order", "highest")
    baixo = rodar_ok("--from-file", fixture_ordem, "--order", "lowest")
    assert ids(alto)[0] == "alpha" and ids(alto)[1] == "whiskey", ids(alto)
    assert provider(alto, "alpha")["headline_metric"]["percent"] == 80
    assert ids(baixo)[0] == "zulu", ids(baixo)
    assert provider(baixo, "zulu")["headline_metric"]["percent"] == 10


def test_alphabetical_continua_ordenando_por_nome_exibido(fixture_ordem):
    d = rodar_ok("--from-file", fixture_ordem, "--order", "alphabetical")
    lista = ids(d)
    assert lista.index("echo") < lista.index("whiskey"), f"E antes de W: {lista}"
    assert lista.index("kilo") < lista.index("mike"), f"K antes de M: {lista}"
    assert lista[0] == "alpha", f"'Alpha' é o primeiro nome; veio {lista[0]!r}"


def test_manual_difere_dos_outros_modos_na_mesma_fixture(fixture_ordem):
    """Assimetria explícita: se ``manual`` fosse ignorado, esta comparação cairia."""
    up = rodar_ok("--from-file", fixture_ordem, "--order", "upstream")
    man = manual(fixture_ordem, "echo")
    assert up["primary"]["id"] == "alpha"
    assert man["primary"]["id"] == "echo"
    assert ids(up) != ids(man), "a ordem de `manual` não pode ser igual à do relatório aqui"
    assert set(ids(up)) == set(ids(man)), "os dois modos listam os MESMOS providers"


def test_modos_existentes_nao_aceitam_sequence_e_nao_mudam_por_causa_dele(fixture_ordem):
    """Item 6 na forma negativa: sem ``--sequence``, os 4 modos seguem válidos."""
    for modo in ("upstream", "highest", "lowest", "alphabetical"):
        proc = rodar("--from-file", fixture_ordem, "--order", modo)
        assert proc.returncode == 0, f"order={modo} sem --sequence deve continuar válido"


# --------------------------------------------------------------------------- #
# Ambiguidades / lacunas do contrato (honestidade D5)
# --------------------------------------------------------------------------- #

AMBIGUIDADES = """
1. CONTRADIÇÃO REAL entre os itens 1 e 7 (precisa de decisão humana).
   Item 1: "``--order manual`` sem ``--sequence`` é erro de uso: rc 2".
   Item 7: "``orderSequence`` ausente ou vazia com ``order: manual`` → NÃO passa
   ``--sequence``; o coletor trata como sequência vazia. Não pode virar erro de
   uso."
   As duas frases não podem valer ao mesmo tempo com a MESMA linha de argv: se o
   serviço não passa ``--sequence`` e passa ``--order manual``, o item 1 manda
   rc 2 e o item 7 proíbe. A única leitura que concilia é "NÃO passa --sequence"
   significar "não passa um valor significativo" — isto é, o serviço pode
   encaminhar ``--sequence ""`` (vazio é VÁLIDO pelo item 2). Este arquivo NÃO
   fixa o mecanismo: testa o item 1 literalmente (flag AUSENTE ⇒ rc 2) e o item 7
   pelo efeito (sequência vazia configurada ⇒ nenhum erro de uso ponta a ponta;
   ver ``test_t15_setting_argv_isolado.py``). Quem decide é o dono.
2. ``--sequence`` SEM ``--order`` nenhum: assumi erro de uso (rc 2), porque o
   default de ``--order`` é ``upstream`` e o item 1 diz "com ``--order``
   diferente de ``manual``". Um argv sem ``--order`` não TEM ``--order``, então a
   letra admite as duas leituras; testei a que preserva a intenção (a flag só
   existe em manual). Se a decisão humana for "só erra quando --order é passado
   explicitamente", o teste ``test_sequence_sem_order_nenhum_e_erro_de_uso`` cai.
3. Sequência feita só de vírgulas (``","``, ``",,"``) não é "vazia" nem "só
   espaços" pela letra do item 2. Não testei: não invento oráculo. Nota: a
   implementação aparentemente descarta tokens vazios (``test_espacos_em_volta``
   e ``test_entrada_so_com_espacos`` passam com a leitura de tokens não-vazios),
   mas o caso puro de vírgulas fica NÃO VERIFICADO.
4. "Espaços em volta" — não especificado para tabs/quebras de linha. Testei só
   espaço U+0020. ``test_espaco_dentro_do_id_nao_e_id_valido`` fixa que só as
   PONTAS são aparadas (espaço interno NÃO é removido), o que é a leitura
   literal de "em volta".
5. Item 5, fallback: "``--primary`` explícito vence a ordem manual se esse
   provider estiver pronto" não diz onde cair quando ele NÃO está pronto. Assumi
   "primeiro pronto da ordem MANUAL" (item 4 aplicado à ordem já reordenada +
   comportamento já observado no modo upstream: fallback = primeiro pronto da
   ordem resultante). É a leitura que mantém um único oráculo, mas é inferência,
   não transcrição.
6. ``secundarios`` num modo com provider em ``error``: assumi que continua sendo
   "todos menos o primário, na ordem resultante" (comportamento já provado pela
   suíte anterior no modo upstream). Nenhum teste aqui exige que provider em
   error saia dos secundários; um deles EXIGE que ele permaneça.
7. Item 6 diz "byte a byte"; comparei LISTAS de ids e o destaque, não o stdout
   cru. O stdout carrega campos que dependem do relógio? Não para estas fixtures
   (``fetched_at`` é fixo, nada é recalculado aqui), mas comparar bytes entre dois
   modos diferentes não faria sentido — a garantia testada é a mesma que a suíte
   anterior já usa: ordem + destaque.
"""
