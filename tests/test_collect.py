# -*- coding: utf-8 -*-
"""Testes de comportamento de ``ai-usage/bin/ai-usage-collect``.

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada 1,
tarefa T3. O script é invocado como SUBPROCESSO (não é importado como módulo) e
todo teste usa ``--from-file``, nunca o binário ``ai-usagebar``.

Contrato de referência (única fonte de verdade):
  * sucesso  -> rc 0, um único JSON em stdout;
  * falha    -> rc != 0 e NENHUM JSON parcial em stdout;
  * ``headline_metric`` = metric de maior ``percent`` (null se nenhum tem percent);
  * ``kind`` = "bar" se ``headline == "percent"``, senão "text";
  * ``plan``/``error`` null viram string vazia;
  * ``openai@work`` -> vendor "openai", conta "work"; sem "@" -> conta null;
  * ``com_problema`` = quantos providers têm ``status: "error"`` OU ``stale: true``.

Comportamentos que o contrato deixava em aberto foram OBSERVADOS por execução e
estão marcados no docstring do teste como "(observado)" — nenhum oráculo foi
inventado sem execução de apoio.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Localização dos artefatos (não leio o conteúdo do script)
# --------------------------------------------------------------------------- #

TEST_DIR = Path(__file__).resolve().parent          # <repo>/ai-usage/tests
PLUGIN_DIR = TEST_DIR.parent                        # <repo>/ai-usage
REPO_ROOT = PLUGIN_DIR.parent                       # <repo>

SCRIPT = PLUGIN_DIR / "bin" / "ai-usage-collect"

# O contrato nomeia o fixture relativo à RAIZ do projeto; a cópia local do diretório
# de testes é o fallback (mesmo conteúdo congelado).
FIXTURE_CANDIDATES = (
    REPO_ROOT / "tests" / "fixtures" / "report-schema1.json",
    TEST_DIR / "fixtures" / "report-schema1.json",
)


def _fixture() -> Path:
    for cand in FIXTURE_CANDIDATES:
        if cand.is_file():
            return cand
    pytest.skip("fixture report-schema1.json não encontrada")


#: argv base do script: executa pelo shebang quando o bit +x está posto.
_BASE_ARGV = [str(SCRIPT)] if os.access(SCRIPT, os.X_OK) else [sys.executable, str(SCRIPT)]


def rodar(*args, cwd=None, env=None, timeout=30):
    """Executa o coletor e devolve o CompletedProcess (texto, sem shell)."""
    proc = subprocess.run(
        _BASE_ARGV + [str(a) for a in args],
        cwd=str(cwd or REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc


def rodar_ok(*args, **kw):
    """Caminho feliz: rc 0 + stdout JSON. Devolve o dict já parseado."""
    proc = rodar(*args, **kw)
    assert proc.returncode == 0, (
        f"esperava rc 0, veio {proc.returncode}\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - só em falha real
        pytest.fail(f"stdout não é JSON parseável: {exc}\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}")


def provider(dados: dict, pid: str) -> dict:
    """Acha um provider por id em ``todos`` (falha descritiva se ausente)."""
    achados = [p for p in dados["all"] if p["id"] == pid]
    assert achados, f"provider {pid!r} ausente de todos: {[p['id'] for p in dados['all']]}"
    return achados[0]


def escrever_fixture(tmp_path: Path, nome: str, payload: dict) -> Path:
    destino = tmp_path / nome
    destino.write_text(json.dumps(payload), encoding="utf-8")
    return destino


def entrada(
    pid: str,
    *,
    status: str = "ready",
    stale: bool = False,
    metrics=None,
    plan=None,
    error=None,
    nome=None,
    fetched_at="2026-10-15T12:00:00Z",
    reset_credits=None,
) -> dict:
    """Entry do schema v1, mínima mas completa nos campos obrigatórios."""
    vendor = pid.split("@", 1)[0]
    return {
        "id": pid,
        "name": nome or vendor,
        "display_name": pid.upper(),
        "short_name": vendor[:3],
        "icon": "i",
        "brand": vendor,
        "plan": plan,
        "status": status,
        "error": error,
        "stale": stale,
        "fetched_at": fetched_at,
        "reset_credits": reset_credits,
        "metrics": list(metrics or []),
        "sections": [],
    }


def metrica(label, *, percent=None, headline="percent", severity="low", value=None, **extra) -> dict:
    m = {
        "label": label,
        "percent": percent,
        "value": value if value is not None else (f"{percent}%" if percent is not None else label),
        "headline": headline,
        "severity": severity,
        "detail": f"detail de {label}",
    }
    m.update(extra)
    return m


# --------------------------------------------------------------------------- #
# 1. Sucesso: rc 0 e stdout JSON
# --------------------------------------------------------------------------- #


def test_sucesso_retorna_rc_zero_e_stdout_json_em_linha_unica():
    proc = rodar("--from-file", _fixture())
    assert proc.returncode == 0
    dados = json.loads(proc.stdout)
    assert isinstance(dados, dict)
    # uma linha só: sem pretty-print, sem lixo antes/depois
    assert proc.stdout.count("\n") == 1
    assert proc.stdout.endswith("\n")
    for chave in ("schema", "primary", "secondary", "all", "total_providers", "with_issues"):
        assert chave in dados, f"chave {chave!r} ausente da saída"


def test_schema_do_top_level_ecoa_a_versao_do_relatorio():
    dados = rodar_ok("--from-file", _fixture())
    assert dados["schema"] == 1


def test_todos_traz_todos_os_providers_na_ordem_do_relatorio():
    dados = rodar_ok("--from-file", _fixture())
    esperado = ["anthropic", "copilot", "zai", "openai@work"]
    assert [p["id"] for p in dados["all"]] == esperado
    assert dados["total_providers"] == len(esperado) == len(dados["all"])


def test_provider_expoe_exatamente_os_campos_do_contrato():
    dados = rodar_ok("--from-file", _fixture())
    esperado = {
        "id", "vendor", "account", "display_name", "short_name", "icon", "plan",
        "status", "stale", "fetched_at", "error", "metrics", "headline_metric",
        "has_reset_credits",
    }
    assert set(dados["primary"].keys()) == esperado


def test_metric_normalizada_expoe_exatamente_os_campos_do_contrato():
    dados = rodar_ok("--from-file", _fixture())
    esperado = {
        "label", "headline", "kind", "percent", "value", "severity", "detail",
        "reset_at", "window_secs",
    }
    assert set(dados["primary"]["metrics"][0].keys()) == esperado


# --------------------------------------------------------------------------- #
# 2. Os quatro casos do fixture
# --------------------------------------------------------------------------- #


def test_entry_1_ready_com_metrics_e_reset_credits():
    dados = rodar_ok("--from-file", _fixture())
    p = provider(dados, "anthropic")
    assert p["status"] == "ready"
    assert p["stale"] is False
    assert p["plan"] == "Claude Pro"
    # o display_name do anthropic é 'Sonnet' desde T18 (era 'Claude', que
    # ordenava antes dos demais e mascarava a diferença upstream × alphabetical)
    assert p["display_name"] == "Sonnet"
    assert p["short_name"] == "cld"
    assert len(p["metrics"]) == 2
    assert [m["label"] for m in p["metrics"]] == ["Session (5h)", "Weekly (7d)"]
    assert [m["percent"] for m in p["metrics"]] == [91, 89]
    # reset_credits vem do relatório -> sinalizado, sem vazar o conteúdo cru
    assert p["has_reset_credits"] is True


def test_entry_2_ready_com_metric_sem_window_secs():
    """Entry 'copilot': os dois metrics do fixture NÃO têm ``window_secs``.

    Ausência do campo é normalizada para null (não explode, não inventa número),
    e ``reset_at`` (presente) é preservado.
    """
    dados = rodar_ok("--from-file", _fixture())
    p = provider(dados, "copilot")
    assert p["status"] == "ready"
    assert len(p["metrics"]) == 2
    for m in p["metrics"]:
        assert m["window_secs"] is None, f"window_secs ausente deveria virar null, veio {m['window_secs']!r}"
        assert m["reset_at"] == "2026-11-01T00:00:00Z"
    # caso negativo: sem window_secs não pode virar 0 nem string
    assert all(m["window_secs"] != 0 for m in p["metrics"])
    assert p["has_reset_credits"] is False


def test_entry_2_window_secs_presente_e_preservado():
    """Contraste obrigatório do caso acima: quando o campo EXISTE, o número passa."""
    dados = rodar_ok("--from-file", _fixture())
    p = provider(dados, "anthropic")
    assert p["metrics"][0]["window_secs"] == 18000
    assert p["metrics"][1]["window_secs"] == 604800


def test_entry_3_error_com_metrics_vazio_e_estado_legitimo():
    """``status: error`` + ``metrics: []`` não é falha do coletor: rc 0 e o provider
    aparece normalmente, com ``erro`` preenchido e ``metrics`` vazio."""
    proc = rodar("--from-file", _fixture())
    assert proc.returncode == 0
    dados = json.loads(proc.stdout)

    p = provider(dados, "zai")
    assert p["status"] == "error"
    assert p["metrics"] == []
    assert p["headline_metric"] is None
    assert p["fetched_at"] is None
    assert isinstance(p["error"], str) and p["error"].strip(), "erro de um provider em error não pode vir vazio"
    assert "zai" in p["error"]  # o texto do relatório atravessa
    assert p["has_reset_credits"] is False


def test_entry_4_stale_com_conta_nomeada():
    """``openai@work``: separação vendor/conta e propagação do estado stale."""
    dados = rodar_ok("--from-file", _fixture())
    p = provider(dados, "openai@work")
    assert p["id"] == "openai@work"          # o id composto é preservado
    assert p["vendor"] == "openai"           # sem a conta
    assert p["account"] == "work"
    assert p["stale"] is True
    assert p["status"] == "ready"

    # caso negativo: o id cru não pode vazar para o campo vendor
    assert p["vendor"] != "openai@work"
    assert "@" not in p["vendor"]


# --------------------------------------------------------------------------- #
# 3. Separação vendor@account (contrato explícito)
# --------------------------------------------------------------------------- #


def test_sem_arroba_nao_tem_conta():
    dados = rodar_ok("--from-file", _fixture())
    for pid in ("anthropic", "copilot", "zai"):
        p = provider(dados, pid)
        assert p["account"] is None, f"{pid} não tem conta nomeada, veio {p['account']!r}"
        assert p["vendor"] == pid


def test_id_com_arroba_duplo_quebra_na_primeira_ocorrencia(tmp_path):
    """(observado) ``openai@work@x`` -> vendor ``openai``, conta ``work@x``."""
    f = escrever_fixture(tmp_path, "multi.json", {
        "schema_version": 1,
        "primary": None,
        "entries": [entrada("openai@work@x", metrics=[metrica("m", percent=3)])],
    })
    p = provider(rodar_ok("--from-file", f), "openai@work@x")
    assert p["vendor"] == "openai"
    assert p["account"] == "work@x"


# --------------------------------------------------------------------------- #
# 4. headline_metric
# --------------------------------------------------------------------------- #


def test_headline_metric_escolhe_o_maior_percent(tmp_path):
    """O maior percent está no MEIO, e com percent empatado-descendente — para não
    passar por acidente de 'pegar o primeiro'."""
    f = escrever_fixture(tmp_path, "ordem.json", {
        "schema_version": 1,
        "primary": "p",
        "entries": [entrada("p", metrics=[
            metrica("baixa", percent=20),
            metrica("alta", percent=87),
            metrica("media", percent=50),
        ])],
    })
    p = provider(rodar_ok("--from-file", f), "p")
    assert p["headline_metric"]["label"] == "alta"
    assert p["headline_metric"]["percent"] == 87


def test_headline_metric_do_fixture_por_provider():
    dados = rodar_ok("--from-file", _fixture())
    casos = {
        "anthropic": ("Session (5h)", 91),   # 91 > 89
        "copilot": ("Premium requests", 100),  # 100 > 0
        "openai@work": ("Codex 5h", 42),
    }
    for pid, (label, percent) in casos.items():
        hm = provider(dados, pid)["headline_metric"]
        assert hm is not None, f"{pid} deveria ter headline_metric"
        assert hm["label"] == label
        assert hm["percent"] == percent


def test_headline_metric_e_o_proprio_objeto_do_metric_escolhido():
    """Não é um resumo achatado: os campos restantes do metric vencedor viajam juntos."""
    dados = rodar_ok("--from-file", _fixture())
    p = provider(dados, "anthropic")
    vencedor = max(p["metrics"], key=lambda m: m["percent"])
    assert p["headline_metric"] == vencedor


def test_headline_metric_e_null_quando_nenhum_metric_tem_percent(tmp_path):
    f = escrever_fixture(tmp_path, "sempct.json", {
        "schema_version": 1,
        "primary": "sem",
        "entries": [entrada("sem", metrics=[
            metrica("saldo", percent=None, headline="value", value="$12.34"),
            metrica("cota", percent=None, headline="value", value="ilimitado"),
        ])],
    })
    p = provider(rodar_ok("--from-file", f), "sem")
    assert p["headline_metric"] is None
    # caso negativo: null de verdade, não um dict vazio nem a primeira métrica
    assert p["headline_metric"] != {}
    assert all(m["percent"] is None for m in p["metrics"])


def test_headline_metric_ignora_percent_para_max_quando_null_esta_presente(tmp_path):
    """(observado) percent null é DESCARTADO; o maior entre os não-null vence."""
    f = escrever_fixture(tmp_path, "mistura.json", {
        "schema_version": 1,
        "primary": "m",
        "entries": [entrada("m", metrics=[
            metrica("nula", percent=None, headline="value", value="n/a"),
            metrica("vinte", percent=20),
            metrica("quarenta", percent=40),
        ])],
    })
    p = provider(rodar_ok("--from-file", f), "m")
    assert p["headline_metric"]["label"] == "quarenta"


# --------------------------------------------------------------------------- #
# 5. kind: bar x text
# --------------------------------------------------------------------------- #


def test_kind_bar_para_headline_percent_e_text_para_headline_value(tmp_path):
    f = escrever_fixture(tmp_path, "kind.json", {
        "schema_version": 1,
        "primary": "k",
        "entries": [entrada("k", metrics=[
            metrica("barra", percent=30, headline="percent"),
            metrica("texto", percent=None, headline="value", value="$8.00"),
        ])],
    })
    p = provider(rodar_ok("--from-file", f), "k")
    por_label = {m["label"]: m for m in p["metrics"]}
    assert por_label["barra"]["kind"] == "bar"
    assert por_label["texto"]["kind"] == "text"


def test_kind_depende_do_headline_nao_do_percent(tmp_path):
    """(observado) ``headline: value`` COM percent preenchido continua ``kind: text`` —
    é o relatório que decide o desenho, não o percent."""
    f = escrever_fixture(tmp_path, "kind2.json", {
        "schema_version": 1,
        "primary": "k2",
        "entries": [entrada("k2", metrics=[
            metrica("valor", percent=77, headline="value", value="77 de 100"),
        ])],
    })
    p = provider(rodar_ok("--from-file", f), "k2")
    assert p["metrics"][0]["kind"] == "text"
    assert p["metrics"][0]["percent"] == 77  # o percent não é zerado, só não vira barra


def test_kind_bar_nunca_aparece_sem_headline_percent(tmp_path):
    """Caso negativo: nenhuma métrica com headline 'value' pode sair como barra."""
    f = escrever_fixture(tmp_path, "kind3.json", {
        "schema_version": 1,
        "primary": "k3",
        "entries": [entrada("k3", metrics=[
            metrica("a", percent=10, headline="value", value="a"),
            metrica("b", percent=None, headline="value", value="b"),
        ])],
    })
    p = provider(rodar_ok("--from-file", f), "k3")
    assert [m["kind"] for m in p["metrics"]] == ["text", "text"]


def test_kind_do_fixture_real_e_bar_para_os_metrics_percent():
    dados = rodar_ok("--from-file", _fixture())
    for p in dados["all"]:
        for m in p["metrics"]:
            assert m["headline"] == "percent"
            assert m["kind"] == "bar"


# --------------------------------------------------------------------------- #
# 6. plan / error null -> string vazia
# --------------------------------------------------------------------------- #


def test_plan_null_vira_string_vazia():
    dados = rodar_ok("--from-file", _fixture())
    p = provider(dados, "zai")  # plan: null no fixture
    assert p["plan"] == ""
    assert p["plan"] is not None


def test_erro_null_vira_string_vazia_e_nunca_none():
    dados = rodar_ok("--from-file", _fixture())
    for p in dados["all"]:
        assert isinstance(p["plan"], str), f"{p['id']}: plan deve ser str, veio {type(p['plan']).__name__}"
        assert isinstance(p["error"], str), f"{p['id']}: erro deve ser str, veio {type(p['error']).__name__}"
    # provider pronto: erro do relatório é null -> ""
    assert provider(dados, "anthropic")["error"] == ""
    assert provider(dados, "copilot")["error"] == ""


def test_plan_e_erro_nunca_saem_como_null_no_json():
    """Caso negativo no texto cru: nenhum ``"plan": null`` / ``"error": null`` na saída.

    Endurecido: o `json.loads` + a checagem de providers são a âncora. Um
    stdout vazio também não teria `"plan": null`, então sem parsear e exigir
    providers, o teste sobrevive à remoção do coletor — vacivamente.
    """
    proc = rodar("--from-file", _fixture())
    modelo = json.loads(proc.stdout)
    assert modelo["all"], "o fixture tem 4 providers; saída vazia não é evidência"
    texto = proc.stdout
    assert '"plan": null' not in texto
    assert '"error": null' not in texto


# --------------------------------------------------------------------------- #
# 7. com_problema
# --------------------------------------------------------------------------- #


def test_com_problema_soma_error_e_stale():
    """Fixture: zai (error) + openai@work (stale) = 2; anthropic e copilot limpos."""
    dados = rodar_ok("--from-file", _fixture())
    assert dados["with_issues"] == 2
    assert dados["total_providers"] == 4


def test_provider_simultaneamente_error_e_stale_conta_uma_vez(tmp_path):
    """(observado) error E stale juntos contam 1, não 2."""
    f = escrever_fixture(tmp_path, "ambos.json", {
        "schema_version": 1,
        "primary": None,
        "entries": [
            entrada("ambos", status="error", stale=True, error="boom"),
            entrada("limpo", metrics=[metrica("m", percent=5)]),
        ],
    })
    dados = rodar_ok("--from-file", f)
    assert dados["with_issues"] == 1
    assert dados["total_providers"] == 2


def test_com_problema_zero_quando_todos_limpos(tmp_path):
    """Caso negativo: stale=false e status=ready não podem inflar a contagem."""
    f = escrever_fixture(tmp_path, "limpos.json", {
        "schema_version": 1,
        "primary": "a",
        "entries": [
            entrada("a", metrics=[metrica("m", percent=1)]),
            entrada("b", metrics=[metrica("m", percent=2)]),
        ],
    })
    dados = rodar_ok("--from-file", f)
    assert dados["with_issues"] == 0


def test_stale_sozinho_conta_mesmo_com_status_ready(tmp_path):
    f = escrever_fixture(tmp_path, "stale.json", {
        "schema_version": 1,
        "primary": None,
        "entries": [entrada("s", stale=True, metrics=[metrica("m", percent=9)])],
    })
    dados = rodar_ok("--from-file", f)
    assert dados["with_issues"] == 1
    assert provider(dados, "s")["status"] == "ready"


# --------------------------------------------------------------------------- #
# 8. secundarios x --max-secondary
# --------------------------------------------------------------------------- #


def test_secundarios_default_traz_tres_sem_o_primario():
    dados = rodar_ok("--from-file", _fixture())
    assert [p["id"] for p in dados["secondary"]] == ["copilot", "zai", "openai@work"]
    assert dados["primary"]["id"] == "anthropic"
    assert all(p["id"] != dados["primary"]["id"] for p in dados["secondary"])
    assert len(dados["secondary"]) == 3


def test_max_secondary_um_traz_exatamente_um_e_o_primeiro_da_ordem():
    dados = rodar_ok("--from-file", _fixture(), "--max-secondary", "1")
    ids = [p["id"] for p in dados["secondary"]]
    assert ids == ["copilot"]
    # caso negativo: truncar secundários NÃO pode truncar todos
    assert dados["total_providers"] == 4
    assert len(dados["all"]) == 4


def test_max_secondary_tres_igual_ao_default():
    explicito = rodar_ok("--from-file", _fixture(), "--max-secondary", "3")
    implicito = rodar_ok("--from-file", _fixture())
    assert [p["id"] for p in explicito["secondary"]] == ["copilot", "zai", "openai@work"]
    assert explicito["secondary"] == implicito["secondary"]


def test_max_secondary_zero_esvazia_secundarios_sem_perder_todos():
    """Caso de borda: 0 significa NENHUM secundário, não 'ilimitado'."""
    dados = rodar_ok("--from-file", _fixture(), "--max-secondary", "0")
    assert dados["secondary"] == []
    assert len(dados["all"]) == 4
    assert dados["primary"]["id"] == "anthropic"


def test_max_secondary_maior_que_o_disponivel_nao_inventa_provider():
    dados = rodar_ok("--from-file", _fixture(), "--max-secondary", "99")
    ids = [p["id"] for p in dados["secondary"]]
    assert ids == ["copilot", "zai", "openai@work"]  # só os 3 que sobram
    assert len(ids) == len(set(ids))


def test_secundarios_preservam_a_ordem_do_relatorio():
    dados = rodar_ok("--from-file", _fixture(), "--primary", "openai@work")
    assert [p["id"] for p in dados["secondary"]] == ["anthropic", "copilot", "zai"]


# --------------------------------------------------------------------------- #
# 9. --primary sobrescreve
# --------------------------------------------------------------------------- #


def test_primary_sobrescreve_o_destaque_e_o_remove_dos_secundarios():
    dados = rodar_ok("--from-file", _fixture(), "--primary", "copilot")
    assert dados["primary"]["id"] == "copilot"
    assert [p["id"] for p in dados["secondary"]] == ["anthropic", "zai", "openai@work"]
    assert dados["primary"]["id"] not in [p["id"] for p in dados["secondary"]]
    # a lista completa não muda com o destaque
    assert [p["id"] for p in dados["all"]] == ["anthropic", "copilot", "zai", "openai@work"]


def test_primary_aceita_id_com_conta():
    dados = rodar_ok("--from-file", _fixture(), "--primary", "openai@work")
    assert dados["primary"]["id"] == "openai@work"
    assert dados["primary"]["account"] == "work"
    assert dados["primary"]["vendor"] == "openai"


def test_primary_inexistente_cai_no_primeiro_pronto_do_relatorio(tmp_path):
    """(observado) ``--primary`` inexistente -> primeiro provider ``status: ready``
    na ORDEM DO RELATÓRIO — não o campo ``primary`` do relatório.

    Fixture discriminante: a ordem é [zai(error), copilot(ready), anthropic(ready)]
    e o relatório declara ``primary: anthropic``. O fallback tem de dar ``copilot``:
    se o coletor apenas ecoasse o campo ``primary``, o teste falharia com anthropic.
    """
    f = escrever_fixture(tmp_path, "disc.json", {
        "schema_version": 1,
        "primary": "anthropic",
        "entries": [
            entrada("zai", status="error", error="boom"),
            entrada("copilot", metrics=[metrica("m", percent=10)]),
            entrada("anthropic", metrics=[metrica("m", percent=50)]),
        ],
    })
    dados = rodar_ok("--from-file", f, "--primary", "nao-existe")
    assert dados["primary"]["id"] == "copilot"
    # o provider em error nunca vira destaque pelo fallback
    assert dados["primary"]["status"] == "ready"
    assert [p["id"] for p in dados["secondary"]] == ["zai", "anthropic"]


def test_primario_null_no_relatorio_cai_no_primeiro_pronto(tmp_path):
    """Sem ``primary`` no relatório e sem flag, o destaque é o primeiro pronto."""
    f = escrever_fixture(tmp_path, "sempri.json", {
        "schema_version": 1,
        "primary": None,
        "entries": [
            entrada("err", status="error", error="boom"),
            entrada("pronto", metrics=[metrica("m", percent=12)]),
        ],
    })
    dados = rodar_ok("--from-file", f)
    assert dados["primary"]["id"] == "pronto"


# --------------------------------------------------------------------------- #
# 10. Nada pronto e estados degenerados
# --------------------------------------------------------------------------- #


def test_relatorio_sem_entries_nao_e_falha_e_primario_e_null(tmp_path):
    f = escrever_fixture(tmp_path, "vazio.json",
                         {"schema_version": 1, "primary": None, "entries": []})
    proc = rodar("--from-file", f)
    assert proc.returncode == 0, f"rc={proc.returncode} stderr={proc.stderr!r}"
    dados = json.loads(proc.stdout)
    assert dados["primary"] is None
    assert dados["secondary"] == []
    assert dados["all"] == []
    assert dados["total_providers"] == 0
    assert dados["with_issues"] == 0


def test_todos_em_error_nao_elegem_primario_mas_aparecem_em_todos(tmp_path):
    f = escrever_fixture(tmp_path, "todoserro.json", {
        "schema_version": 1,
        "primary": None,
        "entries": [
            entrada("e1", status="error", error="a"),
            entrada("e2", status="error", stale=True, error="b"),
        ],
    })
    dados = rodar_ok("--from-file", f)
    assert dados["primary"] is None
    assert dados["total_providers"] == 2
    assert dados["with_issues"] == 2
    assert [p["id"] for p in dados["secondary"]] == ["e1", "e2"]


# --------------------------------------------------------------------------- #
# 11. Falhas: rc != 0 e nenhum JSON parcial
# --------------------------------------------------------------------------- #


def _sem_json_parcial(proc):
    assert proc.stdout.strip() == "", f"falha não pode emitir JSON parcial, stdout={proc.stdout!r}"
    with pytest.raises(json.JSONDecodeError):
        json.loads(proc.stdout)


# Âncoras de MOTIVO. Revert-and-test: um teste negativo que só checa `rc != 0`
# sobrevive vacivamente quando o alvo é apagado (FileNotFoundError também é
# falha). Exigir a âncora torna o teste sensível ao MOTIVO, não à existência.
# Cada âncora é parte da frase que o coletor emite para aquele erro.
def _falha_com_motivo(proc, motivo: str):
    assert proc.returncode != 0, f"esperava falha com motivo {motivo!r}"
    texto = (proc.stderr or "") + (proc.stdout or "")
    assert motivo.lower() in texto.lower(), \
        f"a saída de erro deve nomear o motivo {motivo!r}, veio: {texto.strip()[:200]!r}"
    _sem_json_parcial(proc)


def test_schema_version_diferente_de_um_falha(tmp_path):
    f = escrever_fixture(tmp_path, "v2.json", {"schema_version": 2, "primary": None, "entries": []})
    proc = rodar("--from-file", f)
    _falha_com_motivo(proc, "schema_version")


def test_schema_version_ausente_falha(tmp_path):
    f = escrever_fixture(tmp_path, "semversao.json", {"primary": None, "entries": []})
    proc = rodar("--from-file", f)
    _falha_com_motivo(proc, "schema_version")


def test_from_file_inexistente_falha():
    proc = rodar("--from-file", "/tmp/definitivamente-nao-existe-ai-usage.json")
    _falha_com_motivo(proc, "cannot read the report")


def test_json_malformado_falha_sem_json_parcial(tmp_path):
    f = tmp_path / "quebrado.json"
    f.write_text("{nao eh json", encoding="utf-8")
    proc = rodar("--from-file", f)
    _falha_com_motivo(proc, "is not valid JSON")


def test_max_secondary_nao_numerico_falha():
    """Caso negativo de CLI: valor inválido não pode virar 0 silencioso."""
    proc = rodar("--from-file", _fixture(), "--max-secondary", "tres")
    _falha_com_motivo(proc, "max-secondary")


def test_relatorio_sem_entries_falha_com_motivo(tmp_path):
    """Entrada sem `entries[]` nomeia o campo ausente, não só 'falha'."""
    f = escrever_fixture(tmp_path, "sementries.json", {"schema_version": 1, "primary": None})
    proc = rodar("--from-file", f)
    _falha_com_motivo(proc, "entries")


# --------------------------------------------------------------------------- #
# 12. Isolamento: --from-file não depende do binário ai-usagebar
# --------------------------------------------------------------------------- #


def test_from_file_funciona_sem_o_binario_ai_usagebar_no_path():
    """O contrato promete ler de arquivo SEM o ai-usagebar instalado.

    PATH restrito ao diretório do interpretador: ``ai-usagebar`` é irresolvível.
    Se o coletor dependesse dele, este teste falharia.
    """
    # a máquina pode ter o binário; o PATH abaixo o torna irresolvível de propósito
    path_minimo = str(Path(sys.executable).resolve().parent)
    env = dict(os.environ)
    env["PATH"] = path_minimo
    proc = rodar("--from-file", _fixture(), env=env)
    assert proc.returncode == 0, f"rc={proc.returncode} stderr={proc.stderr!r}"
    dados = json.loads(proc.stdout)
    assert dados["total_providers"] == 4


def test_sucesso_nao_escreve_nada_em_stderr():
    proc = rodar("--from-file", _fixture())
    assert proc.returncode == 0
    assert proc.stderr == "", f"stderr deveria estar limpo em sucesso, veio {proc.stderr!r}"
