# Gerado em contexto isolado (D5) -- sem acesso a implementacao.
# Base: SPEC rodada 1, tarefa T8.
#
# Escopo: INTERFACE PUBLICA do coletor `ai-usage/bin/ai-usage-collect`
# (CLI + JSON de saida), alimentado por fixtures JSON proprias via
# `--from-file` (opcao documentada no --help). Nenhum teste le o codigo-fonte,
# chama funcao interna, invoca o binario `ai-usagebar` real ou abre rede.
#
# Sintoma coberto: escolher o provider expandido pela setting `order`; mostrar
# todas as metricas (incluindo janelas semanal/mensal) com label, valor,
# medidor so quando `headline` e percentual e reset so quando ha `reset_at`,
# sem recalcular nada. Casos negativos: erro/ausente nunca ocupa a posicao
# expandida nas ordens numericas; a lista completa nunca perde providers.
#
# NOTA DE INTERFACE (ver rodape): o coletor NAO le stdin e NAO possui o
# subcomando `normalizar` citado no texto da tarefa. A entrada publica e
# `--from-file <arquivo>`. Os testes usam essa via; a divergencia esta
# reportada no fim do arquivo.

import json
import subprocess
from pathlib import Path

import pytest

COLETOR = Path(__file__).resolve().parents[1] / "bin" / "ai-usage-collect"
MANIFEST = Path(__file__).resolve().parents[1] / "manifest.json"


def _metrica(label, percent, valor, headline, severity, detail,
             reset_at=None, window_secs=None):
    return {
        "label": label, "percent": percent, "value": valor,
        "headline": headline, "severity": severity, "detail": detail,
        "reset_at": reset_at, "window_secs": window_secs,
    }


def _pronto(id_, percent, display=None, short=None, plan=None, **extra):
    m = _metrica("Session (5h)", percent, "%d%%" % percent, "percent",
                 "low", "Resets in 1h", "2026-01-01T05:00:00Z", 18000)
    e = {
        "id": id_, "name": id_,
        "display_name": display or id_,
        "short_name": short or id_[:3],
        "icon": "?",
        "plan": plan if plan is not None else (id_ + " Plan"),
        "status": "ready", "error": None, "stale": False,
        "fetched_at": "2026-01-01T00:00:00Z",
        "reset_credits": None, "metrics": [m],
    }
    e.update(extra)
    return e


def _com_metricas(id_, display, metricas, plan=None, **extra):
    e = {
        "id": id_, "name": id_, "display_name": display,
        "short_name": id_[:3], "icon": "?",
        "plan": plan if plan is not None else (id_ + " Plan"),
        "status": "ready", "error": None, "stale": False,
        "fetched_at": "2026-01-01T00:00:00Z",
        "reset_credits": None, "metrics": metricas,
    }
    e.update(extra)
    return e


def _em_erro(id_, display=None):
    return {
        "id": id_, "name": id_, "display_name": display or id_,
        "short_name": id_[:3], "icon": "?", "plan": None,
        "status": "error", "error": "sem credencial (fixture)",
        "stale": False, "fetched_at": None, "reset_credits": None,
        "metrics": [],
    }


def _relatorio(entries, primary=None):
    return {"schema_version": 1, "primary": primary, "entries": entries}


def _escreve(tmp_path, nome, relatorio):
    arq = tmp_path / nome
    arq.write_text(json.dumps(relatorio), encoding="utf-8")
    return str(arq)


def _coletar(arquivo, *args):
    return subprocess.run(
        [str(COLETOR), "--from-file", arquivo, *args],
        capture_output=True, text=True,
    )


def _normalizado(arquivo, *args):
    res = _coletar(arquivo, *args)
    assert res.returncode == 0, "coletor falhou: %s" % res.stderr
    return json.loads(res.stdout)


# ==========================================================================
# 1. Superficie unica: somente framePopout / density full
# ==========================================================================

def test_superficie_unica_e_framepopout_density_full():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert m["hosts"] == ["framePopout"], (
        "T8 exige superficie unica no host framePopout; hosts=%r" % m["hosts"])
    assert m["capabilities"]["densities"] == ["full"], (
        "T8 exige density full; densities=%r" % m["capabilities"]["densities"])


def test_ordem_e_o_criterio_do_provider_expandido_declarado_no_manifest():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    settings = {s["key"]: s for s in m["metadata"]["settings"]}
    assert "order" in settings, "a setting `order` precisa existir"
    assert settings["order"]["default"] == "upstream"
    valores = [o["value"] for o in settings["order"]["options"]]
    # T15 acrescentou `manual` ao fim; os quatro modos originais seguem
    # presentes e na mesma ordem (acréscimo aditivo, não substituição).
    assert valores[:4] == ["upstream", "highest", "lowest", "alphabetical"], valores
    assert valores[4:] == ["manual"], valores


# ==========================================================================
# 2. Ordem escolhe quem ocupa a posicao expandida (o objetivo central de T8)
# ==========================================================================

def _fixture_ordem(tmp_path):
    # Report order: zzz(erro), delta(20), alpha(80), mid(50)
    entries = [
        _em_erro("zzz"),
        _pronto("delta", 20, display="Delta"),
        _pronto("alpha", 80, display="Alpha"),
        _pronto("mid", 50, display="Mid"),
    ]
    return _escreve(tmp_path, "ordem.json", _relatorio(entries, primary="mid"))


def test_ordem_upstream_preserva_o_primario_do_relatorio(tmp_path):
    arq = _fixture_ordem(tmp_path)
    d = _normalizado(arq, "--order", "upstream")
    assert d["primary"]["id"] == "mid", (
        "`upstream` deve preservar o primario do relatorio (mid)")


def test_ordem_highest_expande_o_maior_percentual(tmp_path):
    arq = _fixture_ordem(tmp_path)
    d = _normalizado(arq, "--order", "highest")
    assert d["primary"]["id"] == "alpha", (
        "`highest` deve expandir alpha (80%%)")


def test_ordem_lowest_expande_o_menor_percentual(tmp_path):
    arq = _fixture_ordem(tmp_path)
    d = _normalizado(arq, "--order", "lowest")
    assert d["primary"]["id"] == "delta", (
        "`lowest` deve expandir delta (20%%)")


def test_ordem_alphabetical_expande_o_primeiro_alfabetico(tmp_path):
    arq = _fixture_ordem(tmp_path)
    d = _normalizado(arq, "--order", "alphabetical")
    assert d["primary"]["id"] == "alpha", (
        "`alphabetical` deve expandir o primeiro nome (Alpha)")


def test_o_expandido_e_uma_posicao_pronta_em_toda_ordem(tmp_path):
    arq = _fixture_ordem(tmp_path)
    for ordem in ("upstream", "highest", "lowest", "alphabetical"):
        d = _normalizado(arq, "--order", ordem)
        assert d["primary"]["status"] == "ready", (
            "ordem %s expandiu provider nao-pronto" % ordem)
        assert d["primary"]["id"] != "zzz", (
            "ordem %s expandiu o provider em erro" % ordem)


def test_o_expandido_nunca_aparece_entre_os_secundarios(tmp_path):
    arq = _fixture_ordem(tmp_path)
    for ordem in ("upstream", "highest", "lowest", "alphabetical"):
        d = _normalizado(arq, "--order", ordem)
        ids_sec = [s["id"] for s in d["secondary"]]
        assert d["primary"]["id"] not in ids_sec, (
            "ordem %s duplicou o primario nos secundarios" % ordem)


# ==========================================================================
# 3. Ordem numerica: erro/ausente DEPOIS dos prontos; desempate estavel
# ==========================================================================

def _fixture_tiering(tmp_path):
    # Report order proposital: pct(40), nom(sem metricas), val(headline=value), err
    entries = [
        _pronto("mid", 40, display="Mid"),
        _com_metricas("nom", "Nom", []),
        _com_metricas("val", "Val", [
            _metrica("Balance", 0, "$5", "value", "low", "saldo", None, None)]),
        _em_erro("err"),
    ]
    return _escreve(tmp_path, "tier.json", _relatorio(entries, primary="mid"))


def test_ordens_numericas_jogam_erro_e_ausente_para_o_fim(tmp_path):
    arq = _fixture_tiering(tmp_path)
    for ordem in ("highest", "lowest"):
        d = _normalizado(arq, "--order", ordem)
        ids = [t["id"] for t in d["all"]]
        # erro e sem-metricas tem de ficar depois de qualquer pronto com percent
        assert ids.index("mid") < ids.index("nom"), (
            "%s pos a lista de `todos` errada: %r" % (ordem, ids))
        assert ids.index("mid") < ids.index("err"), (
            "%s pos o erro antes de um pronto: %r" % (ordem, ids))
        assert ids[-1] == "err", (
            "%s nao deixou o erro por ultimo: %r" % (ordem, ids))


def test_empate_numerico_desempata_pela_ordem_do_relatorio(tmp_path):
    entries = [
        _pronto("primeiro", 50, display="Primeiro"),
        _pronto("segundo", 50, display="Segundo"),
        _pronto("terceiro", 50, display="Terceiro"),
    ]
    arq = _escreve(tmp_path, "empate.json", _relatorio(entries))
    d = _normalizado(arq, "--order", "highest")
    ids = [t["id"] for t in d["all"]]
    assert ids == ["primeiro", "segundo", "terceiro"], (
        "empate deve preservar a ordem do relatorio; veio %r" % ids)


def test_todas_em_erro_nao_expande_ninguem(tmp_path):
    entries = [_em_erro("a"), _em_erro("b")]
    arq = _escreve(tmp_path, "tudo_erro.json", _relatorio(entries))
    d = _normalizado(arq, "--order", "highest")
    assert d["primary"] is None, (
        "sem nenhum provider pronto nao pode haver expandido")
    assert len(d["all"]) == 2, "os providers devem continuar listados"


def test_ordem_numerica_prefere_pronto_a_provider_em_erro_com_metricas(tmp_path):
    # Caso hostil: um provider em erro traz metricas; mesmo assim nao expande.
    entries = [
        _pronto("ok", 10, display="Ok"),
        _com_metricas("errwm", "ErrWM",
                      [_metrica("S", 99, "99%", "percent", "critical",
                                "d", None, None)]),
    ]
    entries[1]["status"] = "error"
    arq = _escreve(tmp_path, "erro_com_metricas.json", _relatorio(entries))
    d = _normalizado(arq, "--order", "highest")
    assert d["primary"]["id"] == "ok", (
        "provider em erro nao pode ocupar a posicao expandida mesmo com metricas")


# ==========================================================================
# 4. Todas as metricas fornecidas, sem recalculo, com janelas preservadas
# ==========================================================================

def _fixture_metricas(tmp_path):
    metricas = [
        _metrica("Session (5h)", 10, "10%", "percent", "low",
                 "Resets in 4h 12m", "2026-01-01T05:00:00Z", 18000),
        _metrica("Weekly (7d)", 20, "20%", "percent", "low",
                 "Resets in 3d", "2026-01-08T00:00:00Z", 604800),
        _metrica("Monthly", 30, "30%", "percent", "high",
                 "Resets in 20d", "2026-02-01T00:00:00Z", 2592000),
        _metrica("Credit balance", 5, "$1.90", "value", "high",
                 "saldo restante", None, None),
    ]
    e = _com_metricas("multi", "Multi", metricas)
    return _escreve(tmp_path, "metricas.json", _relatorio([e], primary="multi"))


def test_todas_as_metricas_fornecidas_aparecem_na_saida(tmp_path):
    arq = _fixture_metricas(tmp_path)
    d = _normalizado(arq)
    labels = [m["label"] for m in d["primary"]["metrics"]]
    assert labels == ["Session (5h)", "Weekly (7d)", "Monthly",
                      "Credit balance"], labels


def test_janelas_semanal_e_mensal_sao_preservadas(tmp_path):
    arq = _fixture_metricas(tmp_path)
    d = _normalizado(arq)
    por_label = {m["label"]: m for m in d["primary"]["metrics"]}
    assert por_label["Weekly (7d)"]["window_secs"] == 604800
    assert por_label["Monthly"]["window_secs"] == 2592000
    # metrica sem janela nao ganha uma inventada
    assert por_label["Credit balance"]["window_secs"] is None


def test_medidor_vem_do_headline_e_nao_de_valor_recalculado(tmp_path):
    arq = _fixture_metricas(tmp_path)
    d = _normalizado(arq)
    por_label = {m["label"]: m for m in d["primary"]["metrics"]}
    assert por_label["Session (5h)"]["kind"] == "bar", (
        "headline percent -> medidor")
    assert por_label["Credit balance"]["kind"] == "text", (
        "headline value -> sem medidor")
    assert por_label["Credit balance"]["value"] == "$1.90", (
        "o valor exibido e o do relatorio, nao recalculado")


def test_reset_aparece_so_quando_o_relatorio_fornece_reset_at(tmp_path):
    arq = _fixture_metricas(tmp_path)
    d = _normalizado(arq)
    por_label = {m["label"]: m for m in d["primary"]["metrics"]}
    assert por_label["Session (5h)"]["reset_at"] == "2026-01-01T05:00:00Z"
    assert por_label["Monthly"]["reset_at"] == "2026-02-01T00:00:00Z"
    assert por_label["Credit balance"]["reset_at"] is None, (
        "metrica sem reset_at nao pode ganhar reset inventado")


def test_percent_severity_e_detail_sao_herdados_sem_alteracao(tmp_path):
    arq = _fixture_metricas(tmp_path)
    d = _normalizado(arq)
    m = {x["label"]: x for x in d["primary"]["metrics"]}["Monthly"]
    assert m["percent"] == 30
    assert m["severity"] == "high"
    assert m["detail"] == "Resets in 20d"


def test_nenhuma_metrica_e_recalculada_em_qualquer_posicao(tmp_path):
    # O non-goal assinado exige percent/severity/value/detail HERDADOS.
    # Compara cada metrica de entrada contra a de saida, campo a campo e
    # posicao a posicao: um recalculo em QUALQUER metrica reprova.
    arq = _fixture_metricas(tmp_path)
    entrada = json.loads(Path(arq).read_text())["entries"][0]["metrics"]
    saida = _normalizado(arq)["primary"]["metrics"]
    assert len(saida) == len(entrada)
    for i, (e, s_) in enumerate(zip(entrada, saida)):
        for campo in ("label", "percent", "value", "headline",
                      "severity", "detail"):
            assert s_[campo] == e[campo], (
                "metrica %d campo %r foi alterado: %r -> %r"
                % (i, campo, e[campo], s_[campo]))


def test_o_primario_expoe_o_detail_do_upstream(tmp_path):
    arq = _fixture_metricas(tmp_path)
    d = _normalizado(arq)
    detalhes = [m["detail"] for m in d["primary"]["metrics"]]
    assert "Resets in 4h 12m" in detalhes, (
        "o primario deve carregar o `detail` calculado pelo upstream")


def test_metricas_de_saldo_sem_window_secs_nao_quebram(tmp_path):
    metricas = [_metrica("Premium requests", 100, "100%", "percent",
                         "critical", "0 of 0 used", "2026-11-01T00:00:00Z", None)]
    e = _com_metricas("cop", "Copilot", metricas)
    arq = _escreve(tmp_path, "saldo.json", _relatorio([e], primary="cop"))
    d = _normalizado(arq)
    m = d["primary"]["metrics"][0]
    assert m["reset_at"] == "2026-11-01T00:00:00Z"
    assert m["window_secs"] is None


# ==========================================================================
# 5. Conta/vendor e estado stale herdados
# ==========================================================================

def test_conta_e_extraida_do_id_vendor_arroba_conta(tmp_path):
    entries = [
        _pronto("openai@work", 42, display="Codex · work"),
        _pronto("openai@home", 11, display="Codex · home"),
    ]
    arq = _escreve(tmp_path, "contas.json",
                   _relatorio(entries, primary="openai@work"))
    d = _normalizado(arq)
    assert d["primary"]["vendor"] == "openai"
    assert d["primary"]["account"] == "work"
    contas = {s["id"]: s["account"] for s in d["secondary"]}
    assert contas["openai@home"] == "home"


def test_stale_e_herdado_e_nao_decidido_pelo_coletor(tmp_path):
    entries = [
        _pronto("fresco", 10, stale=False),
        _pronto("velho", 90, stale=True),
    ]
    arq = _escreve(tmp_path, "stale.json",
                   _relatorio(entries, primary="fresco"))
    d = _normalizado(arq, "--order", "highest")
    assert d["primary"]["id"] == "velho", "maior percent continua expandindo"
    assert d["primary"]["stale"] is True, "stale deve vir do relatorio"


def test_provider_em_erro_mantem_o_status_e_a_mensagem(tmp_path):
    entries = [_pronto("ok", 10), _em_erro("zai", display="Z.AI")]
    arq = _escreve(tmp_path, "erro.json", _relatorio(entries, primary="ok"))
    d = _normalizado(arq)
    erro = [s for s in d["secondary"] if s["id"] == "zai"]
    assert len(erro) == 1, "o provider em erro deve continuar listado"
    assert erro[0]["status"] == "error"
    assert erro[0]["error"], "a mensagem de erro nao pode ser engolida"
    assert erro[0]["metrics"] == [], "erro sem metricas deve ser tolerado"


# ==========================================================================
# 6. Limite de secundarios e lista completa
# ==========================================================================

def _fixture_muitos(tmp_path, n=8):
    entries = [_pronto("p%02d" % i, (i * 7) % 100, display="P%02d" % i)
               for i in range(n)]
    return _escreve(tmp_path, "muitos.json",
                    _relatorio(entries, primary="p00"))


def test_limite_de_secundarios_corta_sem_perder_o_total(tmp_path):
    arq = _fixture_muitos(tmp_path, 8)
    d = _normalizado(arq, "--max-secondary", "3")
    assert len(d["secondary"]) == 3
    assert d["all"] and len(d["all"]) == 8, (
        "a lista completa deve manter todos os providers do relatorio")


def test_limite_grande_mostra_todos_os_restantes(tmp_path):
    arq = _fixture_muitos(tmp_path, 8)
    d = _normalizado(arq, "--max-secondary", "12")
    assert len(d["secondary"]) == 7, (
        "com teto alto, todos os nao-primarios devem aparecer")


def test_limite_zero_nao_expande_erro_e_nao_quebra(tmp_path):
    arq = _fixture_muitos(tmp_path, 5)
    d = _normalizado(arq, "--max-secondary", "0")
    assert d["secondary"] == []
    assert d["primary"]["id"] == "p00", "o primario sobrevive ao limite 0"


# ==========================================================================
# 7. Casos negativos / honestidade
# ==========================================================================

def test_o_coletor_nao_inventa_metricas_quando_o_relatorio_nao_traz(tmp_path):
    e = _com_metricas("vazio", "Vazio", [])
    arq = _escreve(tmp_path, "vazio.json", _relatorio([e], primary="vazio"))
    d = _normalizado(arq)
    assert d["primary"]["metrics"] == [], (
        "sem metricas no relatorio, o coletor nao pode fabricar nenhuma")


def test_a_saida_e_um_unico_json_consumivel(tmp_path):
    arq = _fixture_mordem_simples(tmp_path)
    res = _coletar(arq)
    assert res.returncode == 0
    d = json.loads(res.stdout)  # levanta se nao for JSON puro
    for campo in ("primary", "secondary", "all"):
        assert campo in d, "campo de contrato ausente: %s" % campo
    # a saida tem de refletir a ENTRADA, nao um esqueleto vazio
    assert d["primary"] is not None, "primario nao pode sumir com entrada pronta"
    assert d["primary"]["id"] == "a", (
        "upstream deve preservar o primario `a`; veio %r" % d["primary"]["id"])
    assert [t["id"] for t in d["all"]] == ["a", "b"], (
        "a lista completa deve refletir o relatorio; veio %r"
        % [t["id"] for t in d["all"]])


def _fixture_mordem_simples(tmp_path):
    entries = [_pronto("a", 10), _pronto("b", 20)]
    return _escreve(tmp_path, "simples.json", _relatorio(entries, primary="a"))


# ==========================================================================
# 8. Default de secundarios (contrato: seis por padrao, ajustavel)
# ==========================================================================

def test_default_de_secundarios_e_seis_no_manifest():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    settings = {s["key"]: s for s in m["metadata"]["settings"]}
    assert "maxSecondary" in settings, "T8 exige o slider de secundarios"
    cfg = settings["maxSecondary"]
    assert cfg["default"] == 6, (
        "o padrao de secundarios deve ser seis; veio %r" % cfg["default"])
    assert cfg["min"] <= 1 and cfg["max"] >= 12, (
        "o slider deve ser ajustavel (1..12); veio %r..%r" % (cfg["min"], cfg["max"]))


def test_sem_flag_de_limite_o_default_limita_a_seis(tmp_path):
    arq = _fixture_muitos(tmp_path, 8)
    d = _normalizado(arq, "--order", "upstream")
    assert len(d["secondary"]) == 6, (
        "sem --max-secondary, o detalhe mostra seis secundarios por padrao")


# ==========================================================================
# 9. Plan: herdado do relatorio, nao recalculado pelo coletor
# ==========================================================================

def test_plan_e_herdado_do_relatorio_sem_recalculo(tmp_path):
    e = _com_metricas("or", "OpenRouter",
                      [_metrica("Credit balance", 87, "$1.90", "percent",
                                "high", "d", None, None)],
                      plan="OpenRouter Plan X")
    arq = _escreve(tmp_path, "plan.json", _relatorio([e], primary="or"))
    d = _normalizado(arq)
    assert d["primary"]["plan"] == "OpenRouter Plan X", (
        "o coletor nao recalcula nem reescreve o plano do relatorio")


# ==========================================================================
# RODAPE -- divergencias de interface observadas (NAO testadas, reportadas)
# ==========================================================================
#
# 1. `stdin`: o texto de T8 cita "entradas JSON via stdin/fixture". A CLI
#    publica NAO le stdin: sem `--from-file` o coletor invoca o binario
#    `ai-usagebar` e le o relatorio real. Por isso todos os testes usam
#    `--from-file <arquivo>`, a unica entrada JSON deterministica. Sem fixture,
#    um teste dependeria da maquina -- logo nao ha teste de stdin aqui.
#
# 2. `normalizar`: o texto de T8 cita o subcomando `normalizar`, que nao
#    existe no `--help` do coletor (`unrecognized arguments: normalizar`).
#    A normalizacao e o comportamento padrao da CLI (JSON normalizado em
#    stdout), exercitado por todos os testes acima.
#
# 3. Redacao de `plan` cru: a tarefa pede "sem ... imprimir `plan` cru". O
#    coletor, porem, faz passthrough verbatim do `plan` do relatorio
#    (observado: fragmento parecido com chave `sk-or-v1-...` sai intacto).
#    Como o escopo de redacao do README parece ser a camada de view (T9,
#    `secondaryLabel`), NAO ha assercao de redacao aqui: o oraculo e ambiguo
#    (coletor x view) e inventa-lo violaria o contrato de isolamento.
#    DECISAO HUMANA NECESSARIA: quem redige -- coletor ou view?
