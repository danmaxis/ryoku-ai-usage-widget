"""T18 — o fixture compartilhado discrimina os modos de ordem.

Por que este arquivo existe: o `report-schema1.json` é usado por dezenas de
testes como se fosse um oráculo. Se dois modos de `--order` produzirem o MESMO
primário com ele, todo teste que compara esses modos passa sem discriminar
nada — foi o que aconteceu até 2026-10-27: `upstream` e `alphabetical` davam
ambos `anthropic`, porque o `display_name` do anthropic era `Claude`, o primeiro
em ordem alfabética entre `Claude/Codex · work/GitHub Copilot/Z.AI`.

Estes testes são a GUARDA da propriedade. Não testam o coletor: testam que o
fixture continua servindo de oráculo. Se alguém renomear um provider de volta
para um nome que restaure a coincidência, isto falha e diz por quê.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Path discovery that works in BOTH trees: the development repository (where the
# plugin sits in `ai-usage/` next to a shared `tests/fixtures/`) and the PUBLISHED
# artefact (where the plugin folder IS the root). Hardcoding `parents[2]/ai-usage`
# worked only in development and made the published suite fail 9 tests — external
# review, 2026-10-28.
_TEST_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _TEST_DIR.parent


def _primeiro(candidatos):
    for c in candidatos:
        if c.is_file():
            return c
    return candidatos[-1]


COLETOR = _primeiro([
    _PLUGIN_ROOT / "bin" / "ai-usage-collect",
    _PLUGIN_ROOT.parent / "ai-usage" / "bin" / "ai-usage-collect",
])
FIXTURE = _primeiro([
    _TEST_DIR / "fixtures" / "report-schema1.json",
    _PLUGIN_ROOT.parent / "tests" / "fixtures" / "report-schema1.json",
])


def _rodar(*args: str) -> dict:
    proc = subprocess.run([sys.executable, str(COLETOR), "--from-file", str(FIXTURE), *args],
                          capture_output=True, text=True)
    assert proc.returncode == 0, f"coletor falhou (rc={proc.returncode}): {proc.stderr}"
    return json.loads(proc.stdout)


def _primario_id(dados: dict) -> str | None:
    p = dados.get("primary")
    return p["id"] if p else None


def test_o_fixture_existe_no_caminho_que_os_testes_usam():
    assert FIXTURE.is_file(), f"fixture ausente: {FIXTURE}"


def test_upstream_e_alphabetical_elegem_primarios_diferentes():
    """A propriedade central de T18.

    `upstream` expande o provider que o relatório declara em `primary`;
    `alphabetical` expande o primeiro `display_name`. Se esses dois coincidirem,
    qualquer teste que compare os dois modos é vacuoso.
    """
    a = _primario_id(_rodar("--order", "upstream"))
    b = _primario_id(_rodar("--order", "alphabetical"))
    assert a is not None and b is not None
    assert a != b, (
        "upstream e alphabetical elegem o MESMO primário "
        f"({a!r}) — o fixture deixou de discriminar os modos. A causa histórica "
        "foi o display_name do provider do `primary` ser o primeiro em ordem "
        "alfabética; ajuste o fixture para que não seja."
    )


def test_upstream_expande_o_primary_declarado_no_relatorio():
    relato = json.loads(FIXTURE.read_text(encoding="utf-8"))
    declarado = relato.get("primary")
    assert declarado, "o fixture precisa declarar `primary` para exercitar a regra"
    assert _primario_id(_rodar("--order", "upstream")) == declarado


def test_alphabetical_expande_o_primeiro_display_name_dos_prontos():
    dados = _rodar("--order", "alphabetical")
    prontos = [p for p in dados["all"] if p["status"] == "ready"]
    assert prontos, "o fixture precisa de ao menos um provider pronto"
    esperado = min(prontos, key=lambda p: p["display_name"].casefold())
    assert _primario_id(dados) == esperado["id"], (
        f"alphabetical deveria expandir {esperado['display_name']!r} "
        f"({esperado['id']!r})"
    )


@pytest.mark.parametrize("modo", ["upstream", "alphabetical", "highest", "lowest"])
def test_todo_modo_elege_um_provider_pronto_com_headline(modo):
    """Invariante comum: o expandido nunca está em `error` nem sem métrica."""
    dados = _rodar("--order", modo)
    prim = dados["primary"]
    assert prim is not None, f"{modo} não elegeu primário"
    assert prim["status"] == "ready", f"{modo} expandiu provider em {prim['status']}"
    assert prim["headline_metric"] is not None, f"{modo} expandiu provider sem headline"


def test_os_quatro_modos_nao_colapsam_em_dois_primarios():
    """Guarda contra um fixture degenerado: esperamos VARIEDADE entre os modos.

    Não exige quatro valores distintos (há empate legítimo de percentual), mas
    exige ao menos três — se dois ou mais modos colapsarem, o oráculo perde
    poder de discriminação.
    """
    ids = {m: _primario_id(_rodar("--order", m))
           for m in ("upstream", "alphabetical", "highest", "lowest")}
    assert len(set(ids.values())) >= 3, (
        f"modos colapsaram em poucos primários: {ids} — o fixture não discrimina"
    )
