# -*- coding: utf-8 -*-
"""Testes de comportamento de T61 — fonte embutida do Ryoku.

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada 7,
tarefa T61. O único oráculo é o bloco assinado da SPEC e o contrato passado pelo
orquestrador, transcritos aqui porque o teste não pode ler a implementação:

  ``ai-usage-collect --source ryoku --ryoku-cache-dir DIR`` lê, em DIR, até três
  arquivos (``claude-usage.json``, ``codex-usage.json``, ``opencode-usage.json``)
  e devolve o MESMO modelo de saída da fonte ``ai-usagebar``. Só leitura.

   1. ``source == "ryoku"``.
   2. Claude -> id ``anthropic`` / ``Claude``; Codex -> ``openai`` / ``Codex``;
      OpenCode -> ``opencode`` / ``OpenCode``. Ordem em ``all``: essa.
   3. Claude: ``Session (5h)`` (janela 18000 s) e ``Weekly (7d)`` (604800 s),
      ``reset_at`` = epoch em ISO-8601 UTC com ``Z``; ``percent`` = fração x 100
      arredondada e limitada a 0-100; ``value`` = ``"<percent>%"``; ``headline``
      ``percent``; ``kind`` ``bar``.
   4. Codex v3: uma métrica por janela de ``windows``; 300 e 10080 minutos
      recebem ``Session (5h)`` e ``Weekly (7d)``; ``window_secs`` = minutos x 60;
      ``plan`` = ``_plan``. Codex legado (sem ``schemaVersion``): igual ao Claude.
   5. OpenCode: percentuais, ``reset_at`` e ``window_secs`` nulos, plano
      ``local estimate``.
   6. Utilização vazia ou ausente = sem dado: métrica omitida ou com ``percent``
      nulo. Nunca 0%.
   7. Arquivo ausente -> provider ausente; ``total_providers`` conta os presentes.
   8. ``_source: "stale"`` ou arquivo com mais de 15 min -> ``stale`` verdadeiro.
   9. JSON inválido (ou que não é objeto) -> aquele provider com ``status``
      ``error``, ``error`` não vazio, ``metrics`` vazia; os outros normais; rc 0.
  10. Nenhum dos três arquivos -> rc 3 e stderr cita ``Ryoku``.
  11. Claude presente e pronto -> é o primário.
  12. ``with_issues`` conta providers em erro ou stale.

  Seleção ``auto`` (padrão): usa o ``ai-usagebar`` se estiver no PATH, senão a
  fonte embutida; as fontes não se misturam; nenhuma fonte -> rc 3 com stderr
  que cita ``ai-usagebar`` e ``Ryoku``. ``--source ai-usagebar`` sem o binário
  -> rc 3 mesmo com caches presentes.

Bancada
-------
Caixa-preta por ``subprocess`` com ``sys.executable``. PATH mínimo (symlink do
interpretador e mais nada), HOME temporário, e SEMPRE ``--ryoku-cache-dir``
apontando para dentro de ``tmp_path``: nenhum cache real da máquina é lido.
Todas as fixtures são sintéticas, com valores inventados.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Localização dos artefatos (o conteúdo do coletor nunca é lido)
# --------------------------------------------------------------------------- #

TEST_DIR = Path(__file__).resolve().parent          # <repo>/ai-usage/tests
PLUGIN_DIR = TEST_DIR.parent                        # <repo>/ai-usage
REPO_ROOT = PLUGIN_DIR.parent                       # <repo>

#: Override por ambiente: uso EXCLUSIVO da verificação de falsificabilidade.
SCRIPT = Path(os.environ.get("T61_SCRIPT", PLUGIN_DIR / "bin" / "ai-usage-collect"))

_BASE_ARGV = [sys.executable, str(SCRIPT)]

ARQ_CLAUDE = "claude-usage.json"
ARQ_CODEX = "codex-usage.json"
ARQ_OPENCODE = "opencode-usage.json"

SESSAO = "Session (5h)"
SEMANA = "Weekly (7d)"

#: Epochs inventados, no futuro em relação a qualquer execução plausível.
RESET_5H = 1900000000
RESET_7D = 1900400000

RELATORIO_MINIMO = '{"schema_version":1,"primary":null,"entries":[]}'


# --------------------------------------------------------------------------- #
# Fixtures sintéticas
# --------------------------------------------------------------------------- #


def claude(**troca) -> dict:
    d = {
        "5h-utilization": "0.4200",
        "5h-reset": str(RESET_5H),
        "7d-utilization": "0.6300",
        "7d-reset": str(RESET_7D),
        "updated_at": "12:00:00",
        "_source": "oauth",
        "status": "allowed",
    }
    d.update(troca)
    return d


def _janelas_codex() -> list:
    return [
        {"kind": "primary", "label": "5h", "minutes": 300, "reset": RESET_5H, "utilization": 0.35},
        {"kind": "secondary", "label": "7d", "minutes": 10080, "reset": RESET_7D, "utilization": 0.5},
    ]


def codex_v3(janelas=None, **troca) -> dict:
    janelas = _janelas_codex() if janelas is None else janelas
    d = {
        "schemaVersion": 3,
        "buckets": [
            {"id": "geral", "isGeneral": True, "label": "Geral", "plan": "Demo", "windows": janelas},
        ],
        "windows": janelas,
        "5h-utilization": "",
        "5h-reset": "",
        "7d-utilization": "",
        "7d-reset": "",
        "_source": "app-server",
        "_plan": "Demo",
    }
    d.update(troca)
    return d


def codex_legado(**troca) -> dict:
    d = {
        "5h-utilization": "0.2100",
        "5h-reset": str(RESET_5H),
        "7d-utilization": "0.7700",
        "7d-reset": str(RESET_7D),
        "_source": "app-server",
        "_plan": "Demo",
    }
    d.update(troca)
    return d


def opencode(**troca) -> dict:
    d = {
        "5h-utilization": "0.1200",
        "5h-reset": "0",
        "7d-utilization": "0.0800",
        "7d-reset": "0",
        "_source": "storage",
        "_plan": "local messages",
    }
    d.update(troca)
    return d


# --------------------------------------------------------------------------- #
# Bancada de execução
# --------------------------------------------------------------------------- #


def _artefatos() -> None:
    assert SCRIPT.is_file(), f"coletor ausente em {SCRIPT} — nada a verificar"


def path_sem_ai_usagebar(tmp_path: Path) -> str:
    """PATH com um symlink para o interpretador e MAIS NADA."""
    d = tmp_path / "path-so-python"
    d.mkdir(parents=True, exist_ok=True)
    link = d / "python3"
    if not link.exists():
        link.symlink_to(Path(os.path.realpath(sys.executable)))
    return str(d)


def path_com_ai_usagebar_falso(tmp_path: Path, corpo: str | None = None) -> str:
    """PATH cujo primeiro item tem um ``ai-usagebar`` falso (relatório mínimo)."""
    d = tmp_path / "path-com-falso"
    d.mkdir(parents=True, exist_ok=True)
    if corpo is None:
        corpo = f"import sys\nsys.stdout.write({RELATORIO_MINIMO!r})\n"
    falso = d / "ai-usagebar"
    falso.write_text(f"#!{sys.executable}\n{corpo}", encoding="utf-8")
    falso.chmod(0o755)
    return f"{d}{os.pathsep}{path_sem_ai_usagebar(tmp_path)}"


def _env(path: str, tmp_path: Path) -> dict:
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    return {"PATH": path, "HOME": str(home), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}


def montar_cache(tmp_path: Path, **arquivos) -> Path:
    """Cria DIR com os arquivos dados.

    Chaves: ``claude``, ``codex``, ``opencode``. Valor ``dict`` vira JSON;
    ``str`` é gravada crua (para conteúdo inválido).
    """
    nomes = {"claude": ARQ_CLAUDE, "codex": ARQ_CODEX, "opencode": ARQ_OPENCODE}
    d = tmp_path / "cache-ryoku"
    d.mkdir(parents=True, exist_ok=True)
    for chave, conteudo in arquivos.items():
        texto = conteudo if isinstance(conteudo, str) else json.dumps(conteudo)
        (d / nomes[chave]).write_text(texto, encoding="utf-8")
    return d


def cache_completo(tmp_path: Path) -> Path:
    return montar_cache(tmp_path, claude=claude(), codex=codex_v3(), opencode=opencode())


def rodar(tmp_path: Path, *args, path: str | None = None):
    _artefatos()
    env = _env(path if path is not None else path_sem_ai_usagebar(tmp_path), tmp_path)
    return subprocess.run(
        _BASE_ARGV + [str(a) for a in args],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=60,
    )


def coletar_ryoku(tmp_path: Path, cache: Path, *extra) -> dict:
    """Roda com a fonte embutida e devolve o JSON; rc 0 é exigido."""
    proc = rodar(tmp_path, "--source", "ryoku", "--ryoku-cache-dir", cache, *extra)
    assert proc.returncode == 0, f"rc={proc.returncode} stderr={proc.stderr!r}"
    dados = json.loads(proc.stdout)
    assert isinstance(dados, dict), f"stdout não é um objeto JSON: {proc.stdout!r}"
    return dados


def ids(dados: dict) -> list:
    return [p["id"] for p in dados["all"]]


def provider(dados: dict, pid: str) -> dict:
    achados = [p for p in dados["all"] if p["id"] == pid]
    assert len(achados) == 1, f"esperava exatamente um provider {pid!r} em all: {ids(dados)}"
    return achados[0]


def metrica(prov: dict, rotulo: str):
    """A métrica com esse rótulo, ou ``None`` se ausente."""
    achadas = [m for m in prov["metrics"] if m["label"] == rotulo]
    assert len(achadas) <= 1, f"rótulo {rotulo!r} repetido em {prov['id']}"
    return achadas[0] if achadas else None


def metrica_obrigatoria(prov: dict, rotulo: str) -> dict:
    m = metrica(prov, rotulo)
    assert m is not None, (
        f"{prov['id']} sem a métrica {rotulo!r}; tem {[x['label'] for x in prov['metrics']]}"
    )
    return m


def instante(reset_at) -> datetime:
    """Converte ``reset_at`` exigindo o sufixo ``Z`` (UTC) do contrato."""
    assert isinstance(reset_at, str), f"reset_at deveria ser string ISO, veio {reset_at!r}"
    assert reset_at.endswith("Z"), f"reset_at deve terminar em Z (UTC): {reset_at!r}"
    return datetime.fromisoformat(reset_at[:-1] + "+00:00")


def utc(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def fotografia(d: Path) -> dict:
    """Nome -> (bytes, mtime_ns) de tudo o que existe em DIR."""
    return {
        p.name: (p.read_bytes() if p.is_file() else None, p.stat().st_mtime_ns)
        for p in sorted(d.iterdir())
    }


def envelhecer(arquivo: Path, minutos: float) -> None:
    quando = time.time() - minutos * 60
    os.utime(arquivo, (quando, quando))


# --------------------------------------------------------------------------- #
# 0. Anti-vacuidade da bancada
# --------------------------------------------------------------------------- #


def test_o_path_restrito_realmente_nao_tem_ai_usagebar(tmp_path):
    """Se cair, os testes de ``auto`` e de rc 3 abaixo seriam vácuos."""
    restrito = path_sem_ai_usagebar(tmp_path)
    assert shutil.which("ai-usagebar", path=restrito) is None
    assert shutil.which("python3", path=restrito) is not None
    com_falso = path_com_ai_usagebar_falso(tmp_path)
    achado = shutil.which("ai-usagebar", path=com_falso)
    assert achado is not None and Path(achado).parent == tmp_path / "path-com-falso"


# --------------------------------------------------------------------------- #
# 1-2. Envelope, fonte declarada, ids, nomes e ordem
# --------------------------------------------------------------------------- #


def test_fonte_ryoku_declara_source_ryoku_no_modelo_de_saida(tmp_path):
    dados = coletar_ryoku(tmp_path, cache_completo(tmp_path))
    assert dados["source"] == "ryoku"
    assert dados["schema"] == 1
    for chave in ("primary", "secondary", "all", "total_providers", "with_issues"):
        assert chave in dados, f"falta a chave {chave!r} do modelo de saída"
    assert isinstance(dados["secondary"], list)
    assert isinstance(dados["all"], list)


def test_tres_caches_viram_tres_providers_na_ordem_anthropic_openai_opencode(tmp_path):
    dados = coletar_ryoku(tmp_path, cache_completo(tmp_path))
    assert ids(dados) == ["anthropic", "openai", "opencode"]
    assert dados["total_providers"] == 3


def test_nomes_de_exibicao_sao_claude_codex_e_opencode(tmp_path):
    dados = coletar_ryoku(tmp_path, cache_completo(tmp_path))
    assert provider(dados, "anthropic")["display_name"] == "Claude"
    assert provider(dados, "openai")["display_name"] == "Codex"
    assert provider(dados, "opencode")["display_name"] == "OpenCode"


def test_providers_saudaveis_saem_prontos_sem_erro_e_sem_pendencias(tmp_path):
    dados = coletar_ryoku(tmp_path, cache_completo(tmp_path))
    for p in dados["all"]:
        assert p["status"] == "ready", f"{p['id']}: status={p['status']!r} error={p.get('error')!r}"
        assert p["stale"] is False, f"{p['id']} recém-gravado não pode sair stale"
        assert isinstance(p["metrics"], list) and p["metrics"], f"{p['id']} sem métricas"
    assert dados["with_issues"] == 0


# --------------------------------------------------------------------------- #
# 3. Claude
# --------------------------------------------------------------------------- #


def test_claude_tem_exatamente_as_metricas_de_sessao_e_de_semana(tmp_path):
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, claude=claude()))
    prov = provider(dados, "anthropic")
    assert [m["label"] for m in prov["metrics"]] == [SESSAO, SEMANA]


def test_claude_sessao_converte_fracao_em_percentual_com_janela_e_reset(tmp_path):
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, claude=claude()))
    m = metrica_obrigatoria(provider(dados, "anthropic"), SESSAO)
    assert m["percent"] == 42
    assert m["value"] == "42%"
    assert m["window_secs"] == 18000
    assert instante(m["reset_at"]) == utc(RESET_5H)


def test_claude_semana_converte_fracao_em_percentual_com_janela_e_reset(tmp_path):
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, claude=claude()))
    m = metrica_obrigatoria(provider(dados, "anthropic"), SEMANA)
    assert m["percent"] == 63
    assert m["value"] == "63%"
    assert m["window_secs"] == 604800
    assert instante(m["reset_at"]) == utc(RESET_7D)


def test_metricas_da_fonte_ryoku_tem_headline_percent_e_kind_bar(tmp_path):
    dados = coletar_ryoku(tmp_path, cache_completo(tmp_path))
    vistas = 0
    for p in dados["all"]:
        for m in p["metrics"]:
            vistas += 1
            assert m["headline"] == "percent", f"{p['id']}/{m['label']}"
            assert m["kind"] == "bar", f"{p['id']}/{m['label']}"
            assert isinstance(m["percent"], int) and not isinstance(m["percent"], bool)
            assert m["value"] == f"{m['percent']}%"
    assert vistas >= 6, f"esperava ao menos 2 métricas por provider, vi {vistas}"


@pytest.mark.parametrize(
    "fracao, esperado",
    [
        ("0.4260", 43),     # arredonda para cima
        ("0.4240", 42),     # arredonda para baixo
        ("0.0000", 0),      # zero MEDIDO é dado, e é 0%
        ("1.0000", 100),
        ("1.2500", 100),    # limitado em cima
        ("-0.1000", 0),     # limitado embaixo
    ],
)
def test_percentual_e_fracao_vezes_cem_arredondada_e_limitada(tmp_path, fracao, esperado):
    cache = montar_cache(tmp_path, claude=claude(**{"5h-utilization": fracao}))
    m = metrica_obrigatoria(provider(coletar_ryoku(tmp_path, cache), "anthropic"), SESSAO)
    assert m["percent"] == esperado
    assert m["value"] == f"{esperado}%"


# --------------------------------------------------------------------------- #
# 4. Codex
# --------------------------------------------------------------------------- #


def test_codex_v3_tem_uma_metrica_por_janela_com_os_rotulos_de_sessao_e_semana(tmp_path):
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, codex=codex_v3()))
    prov = provider(dados, "openai")
    assert len(prov["metrics"]) == 2
    sessao = metrica_obrigatoria(prov, SESSAO)
    semana = metrica_obrigatoria(prov, SEMANA)
    assert (sessao["percent"], sessao["value"]) == (35, "35%")
    assert (semana["percent"], semana["value"]) == (50, "50%")


def test_codex_v3_janela_em_segundos_e_reset_vem_de_cada_janela(tmp_path):
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, codex=codex_v3()))
    prov = provider(dados, "openai")
    sessao = metrica_obrigatoria(prov, SESSAO)
    semana = metrica_obrigatoria(prov, SEMANA)
    assert sessao["window_secs"] == 300 * 60
    assert semana["window_secs"] == 10080 * 60
    assert instante(sessao["reset_at"]) == utc(RESET_5H)
    assert instante(semana["reset_at"]) == utc(RESET_7D)


def test_codex_v3_usa_o_plano_declarado_no_cache(tmp_path):
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, codex=codex_v3(_plan="Plano Inventado")))
    assert provider(dados, "openai")["plan"] == "Plano Inventado"


def test_codex_v3_com_janela_extra_ganha_uma_metrica_a_mais(tmp_path):
    """Borda: "uma métrica por janela" vale para janela que não é 5h nem 7d."""
    janelas = _janelas_codex() + [
        {"kind": "extra", "label": "30d", "minutes": 43200, "reset": RESET_7D, "utilization": 0.17},
    ]
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, codex=codex_v3(janelas)))
    prov = provider(dados, "openai")
    assert len(prov["metrics"]) == 3
    extras = [m for m in prov["metrics"] if m["window_secs"] == 43200 * 60]
    assert len(extras) == 1, f"janela de 43200 min sem métrica própria: {prov['metrics']}"
    assert extras[0]["percent"] == 17
    assert extras[0]["label"] not in (SESSAO, SEMANA)
    assert metrica_obrigatoria(prov, SESSAO)["percent"] == 35
    assert metrica_obrigatoria(prov, SEMANA)["percent"] == 50


def test_codex_v3_com_uma_so_janela_tem_uma_so_metrica(tmp_path):
    janelas = _janelas_codex()[1:]
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, codex=codex_v3(janelas)))
    prov = provider(dados, "openai")
    assert [m["label"] for m in prov["metrics"]] == [SEMANA]
    assert prov["metrics"][0]["percent"] == 50


def test_codex_legado_se_comporta_como_o_claude(tmp_path):
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, codex=codex_legado()))
    prov = provider(dados, "openai")
    assert prov["display_name"] == "Codex"
    assert [m["label"] for m in prov["metrics"]] == [SESSAO, SEMANA]
    sessao, semana = prov["metrics"]
    assert (sessao["percent"], sessao["value"], sessao["window_secs"]) == (21, "21%", 18000)
    assert (semana["percent"], semana["value"], semana["window_secs"]) == (77, "77%", 604800)
    assert instante(sessao["reset_at"]) == utc(RESET_5H)
    assert instante(semana["reset_at"]) == utc(RESET_7D)


# --------------------------------------------------------------------------- #
# 5. OpenCode
# --------------------------------------------------------------------------- #


def test_opencode_tem_percentuais_sem_reset_e_sem_janela(tmp_path):
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, opencode=opencode()))
    prov = provider(dados, "opencode")
    percentuais = sorted(m["percent"] for m in prov["metrics"])
    assert percentuais == [8, 12]
    for m in prov["metrics"]:
        assert m["reset_at"] is None, f"OpenCode não tem reset: {m!r}"
        assert m["window_secs"] is None, f"OpenCode não tem janela: {m!r}"
        assert m["value"] == f"{m['percent']}%"


def test_opencode_tem_plano_local_estimate(tmp_path):
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, opencode=opencode()))
    assert provider(dados, "opencode")["plan"] == "local estimate"


# --------------------------------------------------------------------------- #
# 6. Utilização vazia ou ausente = sem dado, nunca 0%
# --------------------------------------------------------------------------- #


def _sem_dado(prov: dict, rotulo: str) -> None:
    m = metrica(prov, rotulo)
    if m is not None:
        assert m["percent"] is None, f"utilização sem dado virou {m['percent']}% em {rotulo!r}"
        assert m.get("value") != "0%", f"utilização sem dado exibida como 0%: {m!r}"


@pytest.mark.parametrize("modo", ["vazia", "ausente"])
def test_utilizacao_semanal_sem_dado_nao_vira_zero_por_cento(tmp_path, modo):
    conteudo = claude()
    if modo == "vazia":
        conteudo["7d-utilization"] = ""
    else:
        del conteudo["7d-utilization"]
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, claude=conteudo))
    prov = provider(dados, "anthropic")
    _sem_dado(prov, SEMANA)
    # a outra janela, que TEM dado, continua inteira
    assert metrica_obrigatoria(prov, SESSAO)["percent"] == 42


@pytest.mark.parametrize("modo", ["vazia", "ausente"])
def test_provider_sem_nenhuma_utilizacao_nao_exibe_zero_por_cento(tmp_path, modo):
    conteudo = opencode()
    for chave in ("5h-utilization", "7d-utilization"):
        if modo == "vazia":
            conteudo[chave] = ""
        else:
            del conteudo[chave]
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, claude=claude(), opencode=conteudo))
    # o provider com dado garante que a execução produziu algo
    assert metrica_obrigatoria(provider(dados, "anthropic"), SESSAO)["percent"] == 42
    for p in dados["all"]:
        if p["id"] != "opencode":
            continue
        for m in p["metrics"]:
            assert m["percent"] is None, f"OpenCode sem dado virou {m['percent']}%"
            assert m.get("value") != "0%"


def test_chaves_legadas_vazias_do_codex_v3_nao_apagam_as_janelas(tmp_path):
    """No v3 as chaves ``5h-*``/``7d-*`` vêm vazias; o dado está em ``windows``."""
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, codex=codex_v3()))
    prov = provider(dados, "openai")
    assert sorted(m["percent"] for m in prov["metrics"]) == [35, 50]


# --------------------------------------------------------------------------- #
# 7. Arquivo ausente -> provider ausente
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "presentes, esperados",
    [
        (("claude",), ["anthropic"]),
        (("codex",), ["openai"]),
        (("opencode",), ["opencode"]),
        (("claude", "opencode"), ["anthropic", "opencode"]),
        (("codex", "opencode"), ["openai", "opencode"]),
    ],
)
def test_arquivo_ausente_deixa_o_provider_fora_e_a_contagem_acompanha(tmp_path, presentes, esperados):
    fabrica = {"claude": claude, "codex": codex_v3, "opencode": opencode}
    cache = montar_cache(tmp_path, **{k: fabrica[k]() for k in presentes})
    dados = coletar_ryoku(tmp_path, cache)
    assert ids(dados) == esperados
    assert dados["total_providers"] == len(esperados)


def test_arquivo_estranho_no_diretorio_nao_vira_provider(tmp_path):
    cache = montar_cache(tmp_path, claude=claude())
    (cache / "gemini-usage.json").write_text(json.dumps(claude()), encoding="utf-8")
    dados = coletar_ryoku(tmp_path, cache)
    assert ids(dados) == ["anthropic"]
    assert dados["total_providers"] == 1


# --------------------------------------------------------------------------- #
# 8. Stale
# --------------------------------------------------------------------------- #


def test_source_stale_marca_o_provider_como_stale(tmp_path):
    cache = montar_cache(tmp_path, claude=claude(_source="stale"), codex=codex_v3())
    dados = coletar_ryoku(tmp_path, cache)
    assert provider(dados, "anthropic")["stale"] is True
    assert provider(dados, "openai")["stale"] is False


def test_arquivo_com_mais_de_quinze_minutos_marca_o_provider_como_stale(tmp_path):
    cache = montar_cache(tmp_path, claude=claude(), codex=codex_v3(), opencode=opencode())
    envelhecer(cache / ARQ_CODEX, 20)
    dados = coletar_ryoku(tmp_path, cache)
    assert provider(dados, "openai")["stale"] is True
    assert provider(dados, "anthropic")["stale"] is False
    assert provider(dados, "opencode")["stale"] is False


def test_arquivo_com_dez_minutos_ainda_nao_e_stale(tmp_path):
    cache = montar_cache(tmp_path, claude=claude())
    envelhecer(cache / ARQ_CLAUDE, 10)
    dados = coletar_ryoku(tmp_path, cache)
    assert provider(dados, "anthropic")["stale"] is False


def test_provider_stale_continua_mostrando_as_metricas(tmp_path):
    cache = montar_cache(tmp_path, claude=claude(_source="stale"))
    dados = coletar_ryoku(tmp_path, cache)
    prov = provider(dados, "anthropic")
    assert prov["stale"] is True
    assert metrica_obrigatoria(prov, SESSAO)["percent"] == 42


# --------------------------------------------------------------------------- #
# 9. JSON inválido -> só aquele provider em erro
# --------------------------------------------------------------------------- #

_INVALIDOS = {
    "json_quebrado": "{isto nao e json",
    "lista": "[1, 2, 3]",
    "numero": "42",
    "vazio": "",
}


@pytest.mark.parametrize("ruim, id_ruim", [("claude", "anthropic"), ("codex", "openai"), ("opencode", "opencode")])
@pytest.mark.parametrize("conteudo", list(_INVALIDOS.values()), ids=list(_INVALIDOS))
def test_arquivo_invalido_poe_so_aquele_provider_em_erro(tmp_path, ruim, id_ruim, conteudo):
    arquivos = {"claude": claude(), "codex": codex_v3(), "opencode": opencode()}
    arquivos[ruim] = conteudo
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, **arquivos))  # rc 0 exigido

    assert ids(dados) == ["anthropic", "openai", "opencode"]
    quebrado = provider(dados, id_ruim)
    assert quebrado["status"] == "error"
    assert isinstance(quebrado["error"], str) and quebrado["error"].strip() != ""
    assert quebrado["metrics"] == []

    for p in dados["all"]:
        if p["id"] == id_ruim:
            continue
        assert p["status"] == "ready", f"{p['id']} contaminado pelo erro de {id_ruim}"
        assert p["metrics"], f"{p['id']} perdeu as métricas por causa de {id_ruim}"


def test_unico_arquivo_presente_invalido_ainda_e_rc_zero_com_provider_em_erro(tmp_path):
    """Arquivo presente e ilegível é provider em erro, não "nenhuma fonte"."""
    dados = coletar_ryoku(tmp_path, montar_cache(tmp_path, codex="{quebrado"))
    assert ids(dados) == ["openai"]
    assert provider(dados, "openai")["status"] == "error"
    assert dados["total_providers"] == 1


# --------------------------------------------------------------------------- #
# 10. Nenhum arquivo -> rc 3
# --------------------------------------------------------------------------- #


def test_diretorio_sem_nenhum_dos_tres_arquivos_sai_com_rc_tres_citando_ryoku(tmp_path):
    cache = montar_cache(tmp_path)
    (cache / "outro.json").write_text("{}", encoding="utf-8")
    proc = rodar(tmp_path, "--source", "ryoku", "--ryoku-cache-dir", cache)
    assert proc.returncode == 3, f"rc={proc.returncode} stderr={proc.stderr!r}"
    assert "ryoku" in proc.stderr.lower(), f"stderr não cita Ryoku: {proc.stderr!r}"
    assert proc.stdout.strip() == "", f"falha não pode emitir JSON: {proc.stdout!r}"


def test_diretorio_inexistente_sai_com_rc_tres_citando_ryoku(tmp_path):
    proc = rodar(tmp_path, "--source", "ryoku", "--ryoku-cache-dir", tmp_path / "nao-existe")
    assert proc.returncode == 3, f"rc={proc.returncode} stderr={proc.stderr!r}"
    assert "ryoku" in proc.stderr.lower(), f"stderr não cita Ryoku: {proc.stderr!r}"
    assert not (tmp_path / "nao-existe").exists(), "o coletor criou o diretório de cache"


# --------------------------------------------------------------------------- #
# 11-12. Primário e contagem de pendências
# --------------------------------------------------------------------------- #


def test_claude_presente_e_pronto_e_o_primario(tmp_path):
    dados = coletar_ryoku(tmp_path, cache_completo(tmp_path))
    assert isinstance(dados["primary"], dict), f"primary={dados['primary']!r}"
    assert dados["primary"]["id"] == "anthropic"
    assert dados["primary"]["display_name"] == "Claude"
    assert "anthropic" not in [p["id"] for p in dados["secondary"]]


def test_with_issues_conta_provider_em_erro_e_provider_stale(tmp_path):
    cache = montar_cache(tmp_path, claude=claude(_source="stale"), codex="{quebrado", opencode=opencode())
    dados = coletar_ryoku(tmp_path, cache)
    assert dados["total_providers"] == 3
    assert dados["with_issues"] == 2


def test_with_issues_conta_um_quando_so_um_provider_esta_stale(tmp_path):
    cache = montar_cache(tmp_path, claude=claude(), codex=codex_v3(), opencode=opencode())
    envelhecer(cache / ARQ_OPENCODE, 45)
    dados = coletar_ryoku(tmp_path, cache)
    assert dados["with_issues"] == 1


# --------------------------------------------------------------------------- #
# Só leitura
# --------------------------------------------------------------------------- #


def test_coleta_nao_altera_conteudo_nem_mtime_nem_cria_arquivo_no_cache(tmp_path):
    cache = cache_completo(tmp_path)
    envelhecer(cache / ARQ_CLAUDE, 3)
    antes = fotografia(cache)
    dados = coletar_ryoku(tmp_path, cache)
    assert dados["total_providers"] == 3
    assert fotografia(cache) == antes


def test_coleta_com_arquivo_invalido_e_arquivo_velho_tambem_nao_escreve_no_cache(tmp_path):
    cache = montar_cache(tmp_path, claude="{quebrado", codex=codex_v3(), opencode=opencode())
    envelhecer(cache / ARQ_CODEX, 20)
    antes = fotografia(cache)
    coletar_ryoku(tmp_path, cache)
    assert fotografia(cache) == antes


def test_falha_por_falta_de_arquivos_nao_escreve_no_diretorio(tmp_path):
    cache = montar_cache(tmp_path)
    proc = rodar(tmp_path, "--source", "ryoku", "--ryoku-cache-dir", cache)
    assert proc.returncode == 3
    assert list(cache.iterdir()) == []


# --------------------------------------------------------------------------- #
# Seleção da fonte
# --------------------------------------------------------------------------- #


def test_source_ryoku_explicita_ignora_o_ai_usagebar_presente_no_path(tmp_path):
    cache = cache_completo(tmp_path)
    proc = rodar(
        tmp_path, "--source", "ryoku", "--ryoku-cache-dir", cache,
        path=path_com_ai_usagebar_falso(tmp_path),
    )
    assert proc.returncode == 0, f"rc={proc.returncode} stderr={proc.stderr!r}"
    dados = json.loads(proc.stdout)
    assert dados["source"] == "ryoku"
    assert ids(dados) == ["anthropic", "openai", "opencode"]


@pytest.mark.parametrize("args", [(), ("--source", "auto")], ids=["padrao", "auto_explicito"])
def test_auto_prefere_o_ai_usagebar_e_nao_mistura_os_caches(tmp_path, args):
    cache = cache_completo(tmp_path)
    proc = rodar(
        tmp_path, *args, "--ryoku-cache-dir", cache,
        path=path_com_ai_usagebar_falso(tmp_path),
    )
    assert proc.returncode == 0, f"rc={proc.returncode} stderr={proc.stderr!r}"
    dados = json.loads(proc.stdout)
    assert dados["source"] == "ai-usagebar"
    # o falso relata zero providers: qualquer provider aqui veio dos caches
    assert dados["all"] == []
    assert dados["total_providers"] == 0
    assert dados["primary"] is None


@pytest.mark.parametrize("args", [(), ("--source", "auto")], ids=["padrao", "auto_explicito"])
def test_auto_sem_ai_usagebar_usa_a_fonte_embutida(tmp_path, args):
    cache = cache_completo(tmp_path)
    proc = rodar(tmp_path, *args, "--ryoku-cache-dir", cache)
    assert proc.returncode == 0, f"rc={proc.returncode} stderr={proc.stderr!r}"
    dados = json.loads(proc.stdout)
    assert dados["source"] == "ryoku"
    assert ids(dados) == ["anthropic", "openai", "opencode"]


def test_auto_sem_ai_usagebar_e_sem_caches_sai_com_rc_tres_nomeando_as_duas_saidas(tmp_path):
    proc = rodar(tmp_path, "--source", "auto", "--ryoku-cache-dir", montar_cache(tmp_path))
    assert proc.returncode == 3, f"rc={proc.returncode} stderr={proc.stderr!r}"
    assert "ai-usagebar" in proc.stderr, f"stderr não cita ai-usagebar: {proc.stderr!r}"
    assert "ryoku" in proc.stderr.lower(), f"stderr não cita Ryoku: {proc.stderr!r}"
    assert proc.stdout.strip() == "", f"falha não pode emitir JSON: {proc.stdout!r}"


def test_source_ai_usagebar_sem_o_binario_sai_com_rc_tres_mesmo_com_caches(tmp_path):
    cache = cache_completo(tmp_path)
    proc = rodar(tmp_path, "--source", "ai-usagebar", "--ryoku-cache-dir", cache)
    assert proc.returncode == 3, f"rc={proc.returncode} stderr={proc.stderr!r}"
    assert proc.stdout.strip() == "", f"não pode cair na fonte embutida: {proc.stdout!r}"


def test_source_ai_usagebar_com_o_binario_declara_a_fonte_ai_usagebar(tmp_path):
    cache = cache_completo(tmp_path)
    proc = rodar(
        tmp_path, "--source", "ai-usagebar", "--ryoku-cache-dir", cache,
        path=path_com_ai_usagebar_falso(tmp_path),
    )
    assert proc.returncode == 0, f"rc={proc.returncode} stderr={proc.stderr!r}"
    dados = json.loads(proc.stdout)
    assert dados["source"] == "ai-usagebar"
    assert dados["all"] == []
