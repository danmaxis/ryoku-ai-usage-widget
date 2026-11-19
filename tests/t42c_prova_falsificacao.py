# -*- coding: utf-8 -*-
"""Prova de falsificação dos testes NOVOS de direção (T38) — T42c.

Gerado em contexto isolado (D5) — sem acesso à implementação.

NÃO é um arquivo de testes do pytest (o nome não casa ``test_*``, então a suíte
não o coleta). É o artefato que responde à pergunta do gate: "o teste novo
falharia se o defeito voltasse?".

Ele roda os testes de direção com o DADO OBSERVADO adulterado, em três frentes:

  1. DEFEITO DO DONO — injeta a árvore de ``down`` no lugar de ``left``/
     ``right``, preservando a setting. É o estado exato que o dono viu no shell
     ("a direção da gaveta não está funcionando, está sempre indo para baixo").
  2. DEFEITO NO CANAL — força ``Snap.direction_of`` a devolver "down": prova
     que a asserção depende do canal e não do acaso.
  3. SATISFAZIBILIDADE — injeta a QUEDA CORRETA (geometria de ``down`` com a
     setting ``left``) e confirma que o teste de T38.3 PASSA. Sem isto, um teste
     que falha sempre pareceria rigoroso.

Uso:  python3 tests/t42c_prova_falsificacao.py
"""
import copy as _copy
import importlib.util, sys, types
from pathlib import Path

TESTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "t42", TESTS / "test_t42_formato_unico_isolado.py")
m = importlib.util.module_from_spec(spec)
sys.modules["t42"] = m
spec.loader.exec_module(m)

# Só os casos que interessam: barato e suficiente.
NOMES = ["dir-down", "dir-left", "dir-right",
         "queda-left-larga", "queda-left-estreita",
         "queda-right-larga", "queda-right-estreita"] + \
        ["lat-%d-%s" % (c, d) for c in (2, 3, 4) for d in ("left", "right")]
CASOS = [c for c in m.CASES if c["name"] in NOMES]
assert len(CASOS) == len(NOMES), (len(CASOS), len(NOMES))

dump, raw = m._run(CASOS)
BASE = {"dumps": dump.cases, "models": dump.models, "raw": raw}


def roda(fn, *args, bancada=None):
    """Executa o teste e devolve (passou, mensagem-da-primeira-falha)."""
    m.dump = (lambda b, caso: (bancada or BASE)["dumps"][caso])
    try:
        fn(bancada or BASE, *args)
        return True, ""
    except AssertionError as exc:
        return False, str(exc).splitlines()[0][:200]


def clona(b, troca):
    """Cópia do banco com alguns snapshots SUBSTITUÍDOS (defeito injetado)."""
    dumps = {k: dict(v) for k, v in b["dumps"].items()}
    for caso, origem in troca.items():
        dumps[caso] = dumps[origem]
    return {"dumps": dumps, "models": b["models"], "raw": b["raw"]}


print("=" * 78)
print("0. CONTROLE — o dado REAL, sem adulteração")
for d in ("down", "left", "right"):
    ok, msg = roda(m.test_a_gaveta_abre_na_direcao_pedida_medida_por_geometria, d)
    print("   dir-%-5s -> %s %s" % (d, "PASSA" if ok else "FALHA", msg))
ok, msg = roda(m.test_a_gaveta_nao_abre_sempre_para_baixo)
print("   anti-colapso -> %s %s" % ("PASSA" if ok else "FALHA", msg))

print()
print("=" * 78)
print("1. DEFEITO DO DONO injetado no DADO: toda direção abre 'down'")
# A gaveta de `dir-left` passa a ser a árvore de `dir-down`: é exatamente o
# estado que o dono viu no shell (setting left, desenho down).
def com_geometria_de(b, alvo, doador):
    """Mesma SETTING, geometria trocada: isola a asserção de geometria."""
    _c = _copy.deepcopy
    dumps = {k: dict(v) for k, v in b["dumps"].items()}
    for snap_nome in dumps[alvo]:
        if snap_nome not in dumps[doador]:
            continue
        novo = _c(dumps[alvo][snap_nome])
        fonte = _c(dumps[doador][snap_nome])
        novo.nodes = fonte.nodes            # só a ÁRVORE vem do doador
        novo.finish()
        dumps[alvo][snap_nome] = novo
    return {"dumps": dumps, "models": b["models"], "raw": b["raw"]}

adiagn = {
    "dir-left": "dir-down",
    "dir-right": "dir-down",
}
adulterado = com_geometria_de(
    com_geometria_de(BASE, "dir-left", "dir-down"), "dir-right", "dir-down")
for d in ("left", "right"):
    ok, msg = roda(m.test_a_gaveta_abre_na_direcao_pedida_medida_por_geometria, d,
                   bancada=adulterado)
    print("   dir-%-5s com defeito -> %s" % (d, "PASSA (RUIM!)" if ok else "FALHA (bom)"))
    if not ok:
        print("      %s" % msg)
ok, msg = roda(m.test_a_gaveta_nao_abre_sempre_para_baixo, bancada=adulterado)
print("   anti-colapso com defeito -> %s" % ("PASSA (RUIM!)" if ok else "FALHA (bom)"))
if not ok:
    print("      %s" % msg)

print()
print("=" * 78)
print("2. DEFEITO injetado no CANAL: direction_of() devolve 'down' sempre")
orig = m.Snap.direction_of
m.Snap.direction_of = lambda self, marker: "down"
try:
    for d in ("left", "right"):
        ok, msg = roda(m.test_a_gaveta_abre_na_direcao_pedida_medida_por_geometria, d)
        print("   dir-%-5s -> %s" % (d, "PASSA (RUIM!)" if ok else "FALHA (bom)"))
    ok, msg = roda(m.test_a_gaveta_nao_abre_sempre_para_baixo)
    print("   anti-colapso -> %s" % ("PASSA (RUIM!)" if ok else "FALHA (bom)"))
finally:
    m.Snap.direction_of = orig

print()
print("=" * 78)
print("3. T38.3 — a queda: o teste PASSA quando a queda é CORRETA?")
# Injeta a queda correta: a árvore de `down` no lugar da lateral estreita.
# `dir-down` é largura 900; para ser justo, injeta `down` na MESMA largura
# estreita rodando um caso extra.
extra = [{"name": "queda-left-estreita",
          "settings": m.st(columns=2, drawerDirection="left"),
          "widthBudget": 300, "model": m.THREE_MODEL,
          "steps": [m.open_drawer("open", "TAU ALPHA", "Pill Tau")]},
         {"name": "down-estreita-300",
          "settings": m.st(columns=2, drawerDirection="down"),
          "widthBudget": 300, "model": m.THREE_MODEL,
          "steps": [m.open_drawer("open", "TAU ALPHA", "Pill Tau")]}]
d2, raw2 = m._run(extra)
com_queda = {"dumps": {**BASE["dumps"], **d2.cases}, "models": BASE["models"], "raw": raw2}
# Injeta a QUEDA mantendo a setting `left`: copia a árvore de `down` (só a
# geometria) e devolve o `drawerDirection` = 'left'. Sem isso a âncora dispararia
# por motivo alheio ao teste (a setting teria "mudado"), que não é a hipótese.
_queda = d2.cases["down-estreita-300"]["open"]
import copy as _copy
_queda = _copy.deepcopy(_queda)
_queda.props["drawerDirection"] = ("string", "left")
com_queda["dumps"]["queda-left-estreita"] = {"open": _queda}
ok, msg = roda(m.test_a_lateral_que_nao_cabe_abre_para_baixo, "left", bancada=com_queda)
print("   queda CORRETA injetada -> %s %s" % ("PASSA (bom — o teste é satisfazível)" if ok else "FALHA (RUIM)", msg))
ok, msg = roda(m.test_a_lateral_que_nao_cabe_abre_para_baixo, "left")
print("   dado REAL (sem queda em left) -> %s %s" % ("PASSA (RUIM!)" if ok else "FALHA (bom — é o defeito)", msg))
if not ok:
    print("      %s" % msg)

print()
print("=" * 78)
print("4. T38.2 — columns x lateral: as seis combinações no dado REAL")
for c in (2, 3, 4):
    for d in ("left", "right"):
        ok, msg = roda(m.test_a_lateral_abre_nas_tres_contagens_de_coluna, c, d)
        print("   cols=%d %-5s -> %s %s" % (c, d, "PASSA" if ok else "FALHA", msg))
