# -*- coding: utf-8 -*-
"""Prova de falsificação dos testes da emenda T38 — gaveta lateral (T45c).

Gerado em contexto isolado (D5) — sem acesso à implementação.

NÃO é um arquivo do pytest (o nome não casa ``test_*``): é o artefato que responde
à pergunta do gate — **"o teste novo FALHARIA se o defeito voltasse?"**. Um verde
sem este ciclo não diz nada: 117 testes passando podem ser 117 asserções vazias.

Cinco frentes:

  1. **DEFEITO DO DONO** — injeta no dado a árvore de ``down`` no lugar da lateral
     (grade parada, painel por cima). É o estado exato que o dono reprovou no shell.
  2. **SEM DESLOCAMENTO** — mantém o painel à esquerda mas devolve a grade à origem.
     É o caso "abriu ao lado e nada deslizou", que o teste anterior aceitava.
  3. **SATISFAZIBILIDADE** — injeta a lateral CORRETA (geometria de ``left`` com a
     setting ``left``) no lugar dela e confirma que o teste PASSA. Sem isto, um
     teste que falha sempre pareceria rigoroso.
  4. **FADE NO RECORTE** — o dono fixou o gradiente na borda externa do viewport
     (direita em ``left``, esquerda em ``right``), não na costura com a gaveta.
     Injeta-se a costura (o desenho que o dono descartou): o teste tem de FALHAR.
     O dado real, que já desenha o gradiente no corte, tem de PASSAR — é a
     satisfazibilidade dessa asserção de posição.
  5. **PREMISSA DE DESLOCAMENTO** — a vacuidade encontrada no revert-and-test de
     T45: o teste de "pílula inteira clicável com a gaveta aberta" era verde numa
     árvore em que a grade nunca sai da origem. Injeta-se a grade em ``x = pad``
     (o estado do revert): o teste tem de FALHAR; com o dado real, PASSAR.

Uso:  python3 tests/t45c_prova_falsificacao.py
"""

import copy
import importlib.util
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "t45", TESTS / "test_t45_gaveta_lateral_deslocamento_isolado.py")
m = importlib.util.module_from_spec(spec)
sys.modules["t45"] = m
spec.loader.exec_module(m)

# Subconjunto barato: uma largura por direção e as três contagens de coluna.
NOMES = (["closed-%d-left-900" % c for c in (2, 3, 4)]
         + ["open-%d-left-900" % c for c in (2, 3, 4)]
         + ["closed-%d-right-900" % c for c in (2, 3, 4)]
         + ["open-%d-right-900" % c for c in (2, 3, 4)]
         + ["closed-%d-down-900" % c for c in (2, 3, 4)]
         + ["open-%d-down-900" % c for c in (2, 3, 4)]
         + ["swap-left"])
CASOS = [c for c in m.CASES if c["name"] in NOMES]
assert len(CASOS) == len(NOMES), (len(CASOS), len(NOMES))

dump, raw = m._run(CASOS)
BASE = {"dumps": dump.cases, "raw": raw}


def roda(fn, *args, bancada=None):
    """Executa o teste com um banco e devolve (passou, primeira linha da falha)."""
    b = bancada or BASE
    original = m.bancada
    # O fixture é substituído pela bancada injetada; o teste recebe o MESMO
    # formato de dicionário que o fixture produz.
    try:
        fn(b, *args)
        return True, ""
    except AssertionError as exc:
        return False, str(exc).splitlines()[0][:220]
    finally:
        m.bancada = original


def clona(b, troca):
    """Cópia do banco com alguns censos SUBSTITUÍDOS por outro censo."""
    dumps = {k: dict(v) for k, v in b["dumps"].items()}
    for alvo, doador in troca.items():
        dumps[alvo] = dumps[doador]
    return {"dumps": dumps, "raw": b["raw"]}


def com_geometria_de(b, alvo, doador, nome_censo="open"):
    """Mantém a SETTING do alvo e troca só a ÁRVORE pela do doador.

    Isola a asserção de GEOMETRIA: se a setting também mudasse, a falha poderia vir
    da âncora (setting errada) e não do deslocamento.
    """
    dumps = {k: dict(v) for k, v in b["dumps"].items()}
    novo = copy.deepcopy(dumps[alvo][nome_censo])
    fonte = copy.deepcopy(dumps[doador][nome_censo])
    novo.nodes = fonte.nodes
    novo.finish()
    dumps[alvo] = dict(dumps[alvo])
    dumps[alvo][nome_censo] = novo
    return {"dumps": dumps, "raw": b["raw"]}


def sem_deslocamento(b, cols):
    """DEFEITO "sem deslocamento": painel à esquerda, grade de volta na origem.

    É o estado que o teste anterior aceitava — a direção está certa, o painel está
    do lado certo, e as pílulas não saíram do lugar.
    """
    alvo = "open-%d-left-900" % cols
    dumps = {k: dict(v) for k, v in b["dumps"].items()}
    s = copy.deepcopy(dumps[alvo]["open"])
    fechado = dumps["closed-%d-left-900" % cols]["s"]
    x0 = m.Snap.__dict__  # noqa: F841 (documenta que só a geometria muda)
    gx = [n for n in fechado.nodes if n.kind == "QQuickGrid"][0].x
    for n in s.nodes:
        if n.kind in ("QQuickGrid", "Pill") or n.kind.startswith("QQuickRectangle"):
            if n.x > 13 and n.x < 900 and n.y < 400:
                n.x = gx + (n.x - n.x) if n.kind == "QQuickGrid" else n.x
    s.finish()
    dumps[alvo] = dict(dumps[alvo])
    dumps[alvo]["open"] = s
    return {"dumps": dumps, "raw": b["raw"]}


def painel_por_cima(b, cols):
    """DEFEITO do dono: a gaveta SOBREPÕE a grade, ancorada na base, sem linha.

    Injeta o painel de ``left`` na MESMA faixa x da grade: é o desenho reprovado
    ("ancorada na base — isso é sobreposição, não coluna ao lado").
    """
    alvo = "open-%d-left-900" % cols
    dumps = {k: dict(v) for k, v in b["dumps"].items()}
    s = copy.deepcopy(dumps[alvo]["open"])
    g = [n for n in s.nodes if n.kind == "QQuickGrid"][0]
    painel = m.Snap.drawer_panel(s, "TAU ALPHA")
    dx = g.x - painel.x
    for n in s.nodes:
        if n.kind.startswith("QQuickRectangle") and n.w > 40 and n.h > 20 and abs(n.x - painel.x) < 1:
            n.x = g.x
    s.finish()
    dumps[alvo] = dict(dumps[alvo])
    dumps[alvo]["open"] = s
    return {"dumps": dumps, "raw": b["raw"]}


def grade_na_origem(b, caso, censo):
    """DEFEITO "não deslocou": a grade de volta à origem do conteúdo (``x = pad``).

    É o estado exato do revert (``daa1e7a``): o painel lateral aparece, o clique na
    pílula continua funcionando, e NADA desliza. Um teste que só afirme o clique
    passa aqui — foi assim que ``test_pilula_inteira_continua_clicavel_com_a_gaveta_aberta``
    sobreviveu ao revert-and-test. Só o ``x`` da grade muda: é a única grandeza que
    a premissa de deslocamento lê.
    """
    dumps = {k: dict(v) for k, v in b["dumps"].items()}
    s = copy.deepcopy(dumps[caso][censo])
    g = [n for n in s.nodes if n.kind == "QQuickGrid"][0]
    g.x = float(s.prop("pad"))
    s.finish()
    dumps[caso] = dict(dumps[caso])
    dumps[caso][censo] = s
    return {"dumps": dumps, "raw": b["raw"]}


def com_fade_na_costura(b, cols, direcao):
    """DEFEITO que o dono descartou: o gradiente na COSTURA com a gaveta.

    Move a faixa do fog ao encontro do painel (a borda da grade que encara o
    detalhe) e a deixa ali. O dono fixou o contrário — o fade indica o CORTE e vive
    na borda externa do viewport. Só a posição da faixa muda: geometria, modelo e
    setting ficam intactos, para que a falha venha da asserção de fade.
    """
    alvo = "open-%d-%s-900" % (cols, direcao)
    dumps = {k: dict(v) for k, v in b["dumps"].items()}
    s = copy.deepcopy(dumps[alvo]["open"])
    painel = m.Snap.drawer_panel(s, "TAU ALPHA")
    costura = (painel.x + painel.w) if direcao == "left" else painel.x
    for n in s.nodes:
        if n.fade > 0:
            n.x = costura
    s.finish()
    dumps[alvo] = dict(dumps[alvo])
    dumps[alvo]["open"] = s
    return {"dumps": dumps, "raw": b["raw"]}


def alinha_titulo_com_grade(b):
    """DEFEITO "o título desliza junto": o título acompanha o deslocamento da grade.

    É a tentação natural de quem move a seção inteira em vez da grade.
    """
    dumps = {k: dict(v) for k, v in b["dumps"].items()}
    for cols in (2, 3, 4):
        alvo = "open-%d-left-900" % cols
        fechado = dumps["closed-%d-left-900" % cols]["s"]
        s = copy.deepcopy(dumps[alvo]["open"])
        g = [n for n in s.nodes if n.kind == "QQuickGrid"][0]
        gf = [n for n in fechado.nodes if n.kind == "QQuickGrid"][0]
        for n in s.nodes:
            if "PROVIDERS" in n.text.upper():
                n.x += (g.x - gf.x)
        s.finish()
        dumps[alvo] = dict(dumps[alvo])
        dumps[alvo]["open"] = s
    return {"dumps": dumps, "raw": b["raw"]}


print("=" * 78)
print("0. CONTROLE — o dado REAL, sem adulteração (tem de PASSAR)")
for cols in (2, 3, 4):
    ok, msg = roda(m.test_em_left_as_pilulas_deslocam_para_a_direita, cols, 900)
    print("   left  cols=%d -> %s %s" % (cols, "PASSA" if ok else "FALHA", msg))
    ok, msg = roda(m.test_em_right_as_pilulas_deslocam_para_a_esquerda, cols, 900)
    print("   right cols=%d -> %s %s" % (cols, "PASSA" if ok else "FALHA", msg))
ok, msg = roda(m.test_o_deslocamento_sobrevive_a_troca_de_provider)
print("   troca       -> %s %s" % ("PASSA" if ok else "FALHA", msg))

print()
print("=" * 78)
print("1. DEFEITO DO DONO injetado: a gaveta SOBREPÕE a grade, sem deslocamento")
adulterado = com_geometria_de(BASE, "open-2-left-900", "open-2-down-900")
adulterado = com_geometria_de(adulterado, "open-3-left-900", "open-3-down-900")
adulterado = com_geometria_de(adulterado, "open-4-left-900", "open-4-down-900")
for cols in (2, 3, 4):
    ok, msg = roda(m.test_em_left_as_pilulas_deslocam_para_a_direita,
                   cols, 900, bancada=adulterado)
    print("   left  cols=%d -> %s" % (cols, "PASSA (RUIM!)" if ok else "FALHA (bom)"))
    if not ok:
        print("      %s" % msg)

print()
print("=" * 78)
print("2. DEFEITO 'sem deslocamento': painel à esquerda, grade parada na origem")
for cols in (2, 3, 4):
    ad = sem_deslocamento(BASE, cols)
    ok, msg = roda(m.test_em_left_as_pilulas_deslocam_para_a_direita,
                   cols, 900, bancada=ad)
    print("   left  cols=%d -> %s" % (cols, "PASSA (RUIM!)" if ok else "FALHA (bom)"))
    if not ok:
        print("      %s" % msg)

print()
print("=" * 78)
print("3. DEFEITO 'o título desliza junto com as pílulas'")
ad = alinha_titulo_com_grade(BASE)
for cols in (2, 3, 4):
    ok, msg = roda(m.test_o_titulo_dos_secundarios_fica_fixo,
                   cols, "left", 900, bancada=ad)
    print("   cols=%d -> %s" % (cols, "PASSA (RUIM!)" if ok else "FALHA (bom)"))
    if not ok:
        print("      %s" % msg)

print()
print("=" * 78)
print("4. SATISFAZIBILIDADE — com a lateral CORRETA o teste PASSA?")
# Injeta a árvore de `left` no lugar de `down`, preservando a setting `down`:
# se o teste de `down` então FALHAR, ele é sensível à geometria (bom); e o de
# `left` com a sua própria árvore continua passando (não é sempre-falha).
ok, msg = roda(m.test_em_down_nada_desloca_e_a_gaveta_empurra_para_baixo,
               2, 900)
print("   down com o dado real      -> %s (o desenho de down está conforme)"
      % ("PASSA" if ok else "FALHA: " + msg))
com_down_em_left = com_geometria_de(BASE, "open-2-down-900", "open-2-left-900")
ok, msg = roda(m.test_em_down_nada_desloca_e_a_gaveta_empurra_para_baixo,
               2, 900, bancada=com_down_em_left)
print("   down com geometria de left -> %s" % ("PASSA (RUIM!)" if ok else "FALHA (bom — sensível à geometria)"))

print()
print()
print("=" * 78)
print("5. FADE — defeito INJETADO: o gradiente de volta na COSTURA com a gaveta")
for direcao, cols in (("left", 2), ("right", 2), ("left", 4), ("right", 4)):
    ad = com_fade_na_costura(BASE, cols, direcao)
    if direcao == "left":
        ok, msg = roda(m.test_o_fade_fica_na_borda_do_recorte_em_left, cols, 900, bancada=ad)
    else:
        ok, msg = roda(m.test_o_fade_fica_na_borda_do_recorte_em_right, cols, bancada=ad)
    print("   %s cols=%d -> %s %s"
          % (direcao, cols, "PASSA (RUIM!)" if ok else "FALHA (bom)", msg))

print()
print("=" * 78)
print("6. SATISFAZIBILIDADE DO FADE — o dado REAL (gradiente no corte) PASSA?")
for cols in (2, 3, 4):
    ok, msg = roda(m.test_o_fade_fica_na_borda_do_recorte_em_left, cols, 900)
    print("   left  cols=%d -> %s %s"
          % (cols, "PASSA (bom)" if ok else "FALHA (RUIM!)", msg))
for cols in (2, 3, 4):
    ok, msg = roda(m.test_o_fade_fica_na_borda_do_recorte_em_right, cols)
    print("   right cols=%d -> %s %s"
          % (cols, "PASSA (bom)" if ok else "FALHA (RUIM!)", msg))

print()
print("=" * 78)
print("7. PREMISSA DE DESLOCAMENTO — 'pílula inteira clicável com a gaveta aberta'")
# A revisão T45 descobriu que este teste era verde no revert (grade em x = pad,
# painel por cima): ele afirmava o CLIQUE sem exigir o DESLOCAMENTO. A frente
# abaixo injeta exatamente o estado que o fazia passar — a grade de volta na
# origem — e exige que ele agora FALHE; em seguida confirma que o dado real PASSA.
ok, msg = roda(m.test_pilula_inteira_continua_clicavel_com_a_gaveta_aberta, "left")
print("   dado real (grade deslocada)      -> %s"
      % ("PASSA (bom)" if ok else "FALHA (RUIM!): " + msg))
for censo in ("tau", "swap"):
    ad = grade_na_origem(BASE, "swap-left", censo)
    ok, msg = roda(m.test_pilula_inteira_continua_clicavel_com_a_gaveta_aberta,
                   "left", bancada=ad)
    print("   grade na origem no censo %-5s -> %s %s"
          % (censo, "PASSA (RUIM!)" if ok else "FALHA (bom)", "" if ok else msg))

print()
print("=" * 78)
print("RESUMO")
print("  Se todas as frentes de DEFEITO FALHAM e as de SATISFAZIBILIDADE PASSAM,")
print("  os testes têm poder de falsificação sobre o defeito declarado e não são")
print("  sempre-falha. A frente 7 é a da vacuidade encontrada no revert: sem ela, o")
print("  teste de 'pílula inteira clicável' era verde numa árvore sem deslocamento.")
