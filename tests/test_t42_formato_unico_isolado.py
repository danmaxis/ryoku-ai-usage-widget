# -*- coding: utf-8 -*-
"""Contratos de comportamento do FORMATO ÚNICO (grade de pílulas + gaveta).

Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC rodada 4,
tarefas T33–T39 (portado em T42); rodada 5, emenda assinada a T38 (2026-10-30).

O que esta suíte prova, e por qual caminho
------------------------------------------
Nenhum arquivo de implementação foi lido: nem ``content/Widget.qml`` nem
``service/Main.qml``. As únicas fontes são o bloco T33–T39 da SPEC, as
premissas do esforço e o MODELO DE TRANSPORTE dos testes anteriores (como montar
a view offline, ``pluginApi`` sintético, parsing de stdout).

``tests/qml/t42_formato_unico_harness.qml`` monta ``content/Widget.qml`` num
processo ``quickshell`` OFFLINE (``QT_QPA_PLATFORM=offscreen``) com um
``pluginApi`` sintético cujo ``mainInstance`` é um serviço falso contendo o
``model`` que cada caso define. O ``ai-usagebar`` NUNCA roda (nenhuma rede,
nenhuma credencial, nenhuma escrita em config). A sonda despeja a ÁRVORE
RENDERIZADA (nó, pai, tipo, texto, geometria) e o Python reconstrói a árvore.

Duas limitações de medição, medidas nesta base e declaradas de propósito
------------------------------------------------------------------------
1. **Posições não resolvem em offscreen.** Toda pílula sai em x=12, y=10; toda
   linha sai com a largura do contêiner. Portanto "ordem de leitura
   esquerda→direita, cima→baixo" NÃO é provada por coordenada: é provada pela
   ORDEM DE INSERÇÃO na grade (``QQuickGrid`` insere as células na ordem do
   modelo, e a ordem da árvore é a ordem de leitura de uma grade preenchida por
   linha). Isso é declarado em ``LACUNAS_DE_OBSERVACAO``.
2. **Altura de alvo é medida, altura de conteúdo não.** ``height`` derivado de
   conteúdo não resolve offline; a pílula expõe ``44`` no nó interativo, o que
   é a medida do ALVO. O teto da gaveta em pixels não é afirmado (só o corte,
   que é observável em texto), ver lacunas.

Onde a SPEC permite duas leituras, o teste escrito é o MAIS EXIGENTE e a
ambiguidade fica registrada na docstring do próprio teste — nenhum oráculo foi
inventado em silêncio.

SEGUNDA PASSADA (T42b) — as três garantias que sobreviveram de T28
------------------------------------------------------------------
Três garantias do arquivo antigo de densidade continuam válidas no formato
único, mas a superfície que as expunha mudou de lugar; foram canceladas lá com
``@pytest.mark.skip`` e vivem de novo aqui:

(i)   o MODELO do serviço não é mutado nem reordenado por consultar a view;
(ii)  a gaveta x poll: identidade pelo id COMPLETO (com conta), sobrevive a um
      poll do mesmo provider e NÃO é transferida ao novo ocupante da célula,
      nem sobrevive ao provider virar primário / sair da lista, nem à
      remontagem da surface;
(iii) no máximo UMA gaveta aberta, afirmado NUMERICAMENTE (N=1 e N=3).

A superfície nova é a impressão digital do modelo (``MODEL|nome|<json>``) e os
passos ``poll``/``remount`` da sonda. O serviço falso continua sendo a única
fonte do ``model``, e a sonda o serializa ANTES e DEPOIS das interações — isso
mede mutação no objeto do serviço, exatamente onde o dado seria destruído.

QUARTA PASSADA — EMENDA ASSINADA DE T38 (2026-10-30)
----------------------------------------------------
A emenda assinada por Danilo Heroso muda o desenho das laterais: o detalhe
deixa de recobrir a grade e passa a ocupar a área liberada ao lado dela, com as
pílulas deslocadas no sentido oposto; o controle de recolher da lateral passa a
ser uma seta (``→`` com as pílulas à direita, ``←`` com elas à esquerda) e
``down`` fica intacto. Consequências medidas nesta base, e o que este arquivo
faz com elas:

* detalhe e grade passam a viver numa FAIXA comum — a busca do "irmão da grade"
  media a topologia revogada e virou ``Snap.band`` + ``Snap.drawer_panel``. A
  direção continua sendo medida por GEOMETRIA, agora expressa como "o detalhe
  encosta na grade pelo lado pedido, sem sobrepor".
* a queda de lateral para ``down`` está explicitamente em revisão na emenda; as
  asserções que a fixavam foram CANCELADAS, com o motivo escrito na seção 6
  junto do teste que as substitui.
* o botão lateral "Collapse" deixou de existir: as duas parametrizações que o
  exigiam foram canceladas e a seta é provada por glifo + comportamento.

Nenhum comportamento de ``down`` foi afrouxado: os testes da gaveta vertical
seguem com as mesmas asserções de antes.

Isolamento (D5) mantido nesta passada: nem ``content/Widget.qml`` nem
``service/Main.qml`` foram lidos. As únicas fontes são o bloco T38 + a emenda
assinada na SPEC, o PIN, e a medição da ÁRVORE RENDERIZADA pela própria sonda.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Localização dos artefatos (o conteúdo da view nunca é lido)
# --------------------------------------------------------------------------- #

TEST_DIR = Path(__file__).resolve().parent            # <repo>/ai-usage/tests
PLUGIN_DIR = Path(os.environ.get("T42_PLUG_DIR", TEST_DIR.parent))
HARNESS = TEST_DIR / "qml" / "t42_formato_unico_harness.qml"

_QUICK = shutil.which("quickshell") or shutil.which("qs")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

pytestmark = pytest.mark.skipif(
    _QUICK is None,
    reason="quickshell ausente: a view QML não pode ser exercitada",
)

#: Caractere de ausência de percentual exigido por T34/T30.
DASH = "\u2014"


def _nome(texto: str) -> str:
    """Normaliza um texto para comparação de NOME de provider.

    Marcadores de estado são prefixados ao nome por texto (medido: o provider em
    erro aparece como ``! Zeta``), então o marcador é removido ANTES de comparar.
    Comparar sem isso confundiria "nome com marcador" com "provider diferente" —
    e o teste mediria a coisa errada.
    """
    return re.sub(r"^[^\w]+", "", texto.strip()).strip()


# --------------------------------------------------------------------------- #
# Fixtures de modelo (a forma que a view consome; nada de dado real)
# --------------------------------------------------------------------------- #

def metric(label: str, percent, detail: str = "") -> dict:
    return {
        "label": label,
        "percent": percent,
        "value": ("%s%%" % percent) if isinstance(percent, (int, float)) else "",
        "severity": "low",
        "detail": detail,
        "reset_at": None,
        "window_secs": 18000,
    }


def provider(pid: str, name: str, metrics: list, status: str = "ready",
             stale: bool = False) -> dict:
    return {
        "id": pid,
        "display_name": name,
        "short_name": pid[:3],
        "plan": pid + "-plan",
        "status": status,
        "stale": stale,
        "metrics": metrics,
        "error": None,
        "account": None,
    }


def model_of(providers: list) -> dict:
    return {
        "schema": 1,
        "primary": providers[0] if providers else None,
        "secondary": providers[1:],
        "all": providers,
        "total_providers": len(providers),
        "with_issues": sum(1 for p in providers if p["status"] == "error"),
    }


#: Primário sempre com TRÊS métricas: é o que T36 promete desenhar inteiro,
#: sem clique. Nomes distintos para nenhuma asserção casar por acidente.
PRIMARY = provider("alpha", "Pill Alpha", [
    metric("Alpha Session", 40), metric("Alpha Weekly", 70), metric("Alpha Monthly", 12),
])

#: Um secundário por ESTADO de T34, cada um com nome e métrica exclusivos.
S_BETA = provider("beta", "Pill Beta", [metric("Beta Chat", 55), metric("Beta Weekly", 64)])
#: Uma métrica SÓ, em 0: a pílula desenha a métrica LÍDER (a de maior
#: percentual, medido nesta base). Com uma segunda métrica em 22% a líder seria
#: 22% e o caso de 0% nunca seria exercitado.
S_ZERO = provider("gamma", "Pill Gamma", [metric("Gamma Chat", 0)])
S_NULL = provider("delta", "Pill Delta", [metric("Delta Chat", None)])
S_STALE = provider("epsilon", "Pill Epsilon", [metric("Eps Chat", 90)], stale=True)
S_ERROR = provider("zeta", "Pill Zeta", [metric("Zeta Chat", 30)], status="error")
S_NODATA = provider("eta", "Pill Eta", [])

#: Seis secundários, ordem do relatório deliberadamente NÃO alfabética.
STATES_MODEL = model_of([PRIMARY, S_BETA, S_ZERO, S_NULL, S_STALE, S_ERROR, S_NODATA])

#: Provider de SEIS métricas para o corte da gaveta (T37). Os rótulos M1..M6 são
#: únicos no relatório inteiro: contá-los na árvore conta linhas de métrica.
OMEGA = provider("omega", "Pill Omega", [metric("Omega M%d" % i, i * 10) for i in range(1, 7)])
THREE = provider("tau", "Pill Tau", [
    metric("Tau Alpha", 10), metric("Tau Beta", 20), metric("Tau Gamma", 30)])
#: Nome deliberadamente NÃO-prefixo de "Pill Tau": com nomes aninhados uma
#: asserção por substring casaria as duas pílulas e mediria a coisa errada.
TAU_BETA = provider("sigma", "Pill Sigma", [metric("Sigma Chat", 44)])

SIX_MODEL = model_of([PRIMARY, OMEGA, TAU_BETA])
THREE_MODEL = model_of([PRIMARY, THREE, TAU_BETA])

#: Base de settings. Defaults do manifest, segundo T40: columns 2, gaveta 320.
BASE = {
    "showSecondaries": True,
    "maxSecondary": 12,
    "secondaryLabel": "name",
    "showMetricDetail": True,
    "drawerDirection": "down",
    "drawerMaxHeight": 320,
    "accent": "wallpaper",
    "language": "en",
}


def st(**kw) -> dict:
    d = dict(BASE)
    d.update(kw)
    return d


# --------------------------------------------------------------------------- #
# Casos: cada um é (settings, model, steps). Steps são executados pela sonda.
# --------------------------------------------------------------------------- #

def snap(name: str) -> dict:
    return {"op": "snap", "name": name}


def open_drawer(name: str, marker: str, click: str) -> dict:
    """Clica a pílula ``click`` se o marcador ``marker`` (texto exclusivo da
    gaveta) ainda não está na árvore, e censa."""
    return {"op": "snapAfterOpen", "name": name, "text": marker, "click": click}


CASES: list[dict] = [
    # ---- T33: width derived from the column count -------------------------
    {"name": "cols-2", "settings": st(columns=2), "model": STATES_MODEL, "steps": [snap("s")]},
    {"name": "cols-3", "settings": st(columns=3), "model": STATES_MODEL, "steps": [snap("s")]},
    {"name": "cols-4", "settings": st(columns=4), "model": STATES_MODEL, "steps": [snap("s")]},
    {"name": "cols-1", "settings": st(columns=1), "model": STATES_MODEL, "steps": [snap("s")]},
    {"name": "cols-9", "settings": st(columns=9), "model": STATES_MODEL, "steps": [snap("s")]},
    {"name": "cols-abc", "settings": st(columns="nao-e-numero"), "model": STATES_MODEL,
     "steps": [snap("s")]},
    {"name": "cols-absent", "settings": {k: v for k, v in st().items() if k != "columns"},
     "model": STATES_MODEL, "steps": [snap("s")]},

    # ---- T34/T35: estados das pílulas, e a grade em 2/3/4 -----------------
    {"name": "states-2", "settings": st(columns=2), "model": STATES_MODEL,
     "steps": [snap("s")]},
    {"name": "states-3", "settings": st(columns=3), "model": STATES_MODEL,
     "steps": [snap("s")]},
    {"name": "states-4", "settings": st(columns=4), "model": STATES_MODEL,
     "steps": [snap("s")]},
    {"name": "sec-off", "settings": st(columns=2, showSecondaries=False),
     "model": STATES_MODEL, "steps": [snap("s")]},
    {"name": "cap-model-1", "settings": st(columns=2, maxSecondary=1),
     "model": model_of([PRIMARY, S_BETA]), "steps": [snap("s")]},
    {"name": "cap-6", "settings": st(columns=2, maxSecondary=6),
     "model": model_of([PRIMARY, S_BETA, S_ZERO, S_NULL]), "steps": [snap("s")]},

    # ---- T36: o primário desenha tudo, e nada é gravado -------------------
    {"name": "primary-all", "settings": st(columns=2), "model": STATES_MODEL,
     "steps": [{"op": "probeSave"}, snap("s")]},

    # ---- T37: gaveta fechada, conteúdo, teto, corte -----------------------
    {"name": "drawer-closed", "settings": st(columns=2, maxSecondary=12),
     "model": THREE_MODEL, "steps": [snap("closed")]},
    {"name": "drawer-open", "settings": st(columns=2),
     "model": THREE_MODEL, "steps": [open_drawer("open", "TAU ALPHA", "Pill Tau")]},
    {"name": "drawer-toggle", "settings": st(columns=2), "model": THREE_MODEL,
     "steps": [snap("before"),
               open_drawer("opened", "TAU ALPHA", "Pill Tau"),
               {"op": "clickText", "value": "Pill Tau"},
               snap("reclosed")]},
    {"name": "drawer-accordion", "settings": st(columns=2), "model": THREE_MODEL,
     "steps": [open_drawer("tau", "TAU ALPHA", "Pill Tau"),
               open_drawer("tau2", "SIGMA CHAT", "Pill Sigma")]},
    {"name": "drawer-6-small", "settings": st(columns=2, drawerMaxHeight=160),
     "model": SIX_MODEL, "steps": [open_drawer("open", "OMEGA M3", "Pill Omega")]},
    {"name": "drawer-6-generous", "settings": st(columns=2, drawerMaxHeight=480),
     "model": SIX_MODEL, "steps": [open_drawer("open", "OMEGA M3", "Pill Omega")]},
    {"name": "drawer-3-generous", "settings": st(columns=2, drawerMaxHeight=480),
     "model": THREE_MODEL, "steps": [open_drawer("open", "TAU ALPHA", "Pill Tau")]},

    # ---- T38: as três direções e o controle de recolher -------------------
    # `widthBudget` é declarado POR CASO: é o único jeito de medir "a lateral
    # cabe?" em duas larguras dentro do mesmo processo. 900 é folgado de
    # propósito — nestes casos a pergunta é "a direção pedida aconteceu?", não
    # "coube?". A queda para `down` tem casos próprios mais abaixo.
    {"name": "dir-down", "settings": st(columns=2, drawerDirection="down"),
     "widthBudget": 900,
     "model": THREE_MODEL, "steps": [open_drawer("open", "TAU ALPHA", "Pill Tau")]},
    {"name": "dir-left", "settings": st(columns=2, drawerDirection="left"),
     "widthBudget": 900,
     "model": THREE_MODEL, "steps": [open_drawer("open", "TAU ALPHA", "Pill Tau")]},
    {"name": "dir-right", "settings": st(columns=2, drawerDirection="right"),
     "widthBudget": 900,
     "model": THREE_MODEL, "steps": [open_drawer("open", "TAU ALPHA", "Pill Tau")]},
    {"name": "dir-bogus", "settings": st(columns=2, drawerDirection="diagonal"),
     "widthBudget": 900,
     "model": THREE_MODEL, "steps": [open_drawer("open", "TAU ALPHA", "Pill Tau")]},

    # ---- T38.3 (EMENDADO): a MESMA setting, dois orçamentos de largura ----
    # A emenda assinada em 2026-10-30 revoga a "queda para down quando a lateral
    # não cabe": o detalhe passa a ocupar a área liberada e as pílulas deslizam
    # no sentido oposto, sem mudar a largura do popout nem `columns`. Os casos
    # `estreita-*` sobrevivem para MEDIR o orçamento apertado — o teste que os
    # consome afirma apenas o que continua assinado. O critério novo de fallback
    # lateral segue em aberto: LACUNAS_DE_OBSERVACAO item 18.
    {"name": "estreita-left", "settings": st(columns=2, drawerDirection="left"),
     "widthBudget": 300,
     "model": THREE_MODEL, "steps": [open_drawer("open", "TAU ALPHA", "Pill Tau")]},
    {"name": "estreita-right", "settings": st(columns=2, drawerDirection="right"),
     "widthBudget": 300,
     "model": THREE_MODEL, "steps": [open_drawer("open", "TAU ALPHA", "Pill Tau")]},
    # Controle do negativo "a seta não vaza para down": `down` no MESMO
    # orçamento apertado das laterais acima, para que a ausência de seta seja
    # afirmada em duas larguras e não duas vezes na mesma.
    {"name": "estreita-down", "settings": st(columns=2, drawerDirection="down"),
     "widthBudget": 300,
     "model": THREE_MODEL, "steps": [open_drawer("open", "TAU ALPHA", "Pill Tau")]},
]

#: T38.2 nas TRÊS contagens de coluna, nas duas laterais. Largura folgada para
#: que "não abriu a lateral" signifique a direção, nunca o orçamento.
#:
#: A variante `lat-<n>-down` existe como CONTROLE da emenda "sem alterar a
#: largura do popout": é o mesmo modelo, a mesma contagem de colunas e a gaveta
#: ABERTA, mudando só a direção — então a largura implícita das duas tem de
#: coincidir. Sem esse controle, comparar lateral aberta com grade fechada
#: mediria outra coisa.
for _cols in (2, 3, 4):
    for _dir in ("left", "right", "down"):
        CASES.append({
            "name": "lat-%d-%s" % (_cols, _dir),
            "settings": st(columns=_cols, drawerDirection=_dir),
            "widthBudget": 900,
            "model": THREE_MODEL,
            "steps": [open_drawer("open", "TAU ALPHA", "Pill Tau")],
        })

#: Altura da faixa em três tetos, nas três direções. A emenda manda RESERVAR
#: desde a abertura a altura da maior área lateral permitida pelo teto, e manda
#: preservar em `down` o comportamento anterior (que não reserva).
for _mh in (160, 320, 480):
    for _dir in ("down", "left", "right"):
        CASES.append({
            "name": "altura-%d-%s" % (_mh, _dir),
            "settings": st(columns=2, drawerDirection=_dir, drawerMaxHeight=_mh),
            "widthBudget": 900,
            "model": THREE_MODEL,
            "steps": [open_drawer("open", "TAU ALPHA", "Pill Tau")],
        })

#: A reserva de altura não pode depender do provider ABERTO (emenda T38): mesmo
#: teto e mesmo modelo, dois providers de tamanhos diferentes. Tau tem 3
#: métricas, Sigma tem 1 — se a faixa mudasse de altura entre os dois, o popout
#: se redimensionaria ao trocar de provider.
for _mh in (160, 320, 480):
    for _dir in ("left", "right"):
        for _tag, _marca, _clique in (("tau", "TAU ALPHA", "Pill Tau"),
                                      ("sigma", "SIGMA CHAT", "Pill Sigma")):
            CASES.append({
                "name": "reserva-%d-%s-%s" % (_mh, _dir, _tag),
                "settings": st(columns=2, drawerDirection=_dir, drawerMaxHeight=_mh),
                "widthBudget": 900,
                "model": THREE_MODEL,
                "steps": [open_drawer("open", _marca, _clique)],
            })

#: O corte `+N more` (T37.3) tem de SOBREVIVER à lateral — a emenda lista teto e
#: `+N more` entre o que se preserva. Seis métricas com teto pequeno.
for _dir in ("left", "right"):
    CASES.append({
        "name": "corte-%s" % _dir,
        "settings": st(columns=2, drawerDirection=_dir, drawerMaxHeight=160),
        "widthBudget": 900,
        "model": SIX_MODEL,
        "steps": [open_drawer("open", "OMEGA M1", "Pill Omega")],
    })

#: Casos que exercitam o RECOLHER em `down`, que a emenda declarou INTACTO. A
#: sonda abre a gaveta e clica cada nó interativo que NÃO pertence a uma pílula,
#: censando após cada clique: o controle é identificado por COMPORTAMENTO, nunca
#: pelo rótulo.
#:
#: `left`/`right` NÃO entram aqui: na lateral o controle é a seta, que vive
#: DENTRO do painel do detalhe — e esse painel repete o nome do provider, de modo
#: que o classificador da sonda (que sobe até 3 ancestrais em busca do nome)
#: descarta a seta como "dentro de pílula". A cobertura lateral é feita clicando
#: o GLIFO por texto nos casos `seta-*` abaixo. Ver o bloco de cancelamentos da
#: seção 6.
COLLAPSE_NAMES = ["Pill Tau", "Pill Sigma"]
CASES.append({
    "name": "collapse-down",
    "settings": st(columns=2, drawerDirection="down"),
    "model": THREE_MODEL,
    "steps": [
        open_drawer("open", "TAU ALPHA", "Pill Tau"),
        {"op": "expandClosers", "names": COLLAPSE_NAMES,
         "openText": "TAU ALPHA", "openClick": "Pill Tau", "prefix": "closer"},
    ],
})

#: A SETA de retorno (emenda T38). Numa lateral o controle de recolher é uma
#: faixa alta na ponta do detalhe, rotulada `→` quando as pílulas foram para a
#: direita e `←` quando foram para a esquerda; clicar retorna à grade. Cada
#: lado é exercitado em orçamento FOLGADO e APERTADO: o retorno não pode depender
#: de a lateral ter "cabido".
GLIFO_DO_LADO = {"left": "→", "right": "←"}
for _dir, _seta in GLIFO_DO_LADO.items():
    for _tag, _wb in (("folgado", 900), ("estreito", 300)):
        CASES.append({
            "name": "seta-%s-%s" % (_dir, _tag),
            "settings": st(columns=2, drawerDirection=_dir),
            "widthBudget": _wb,
            "model": THREE_MODEL,
            "steps": [open_drawer("open", "TAU ALPHA", "Pill Tau"),
                      {"op": "clickText", "value": _seta},
                      snap("volta")],
        })

#: Com a lateral aberta, clicar uma pílula ainda VISÍVEL troca o provider
#: selecionado: o detalhe passa a ser o do clicado e o anterior sai.
for _dir in ("left", "right"):
    for _tag, _wb in (("folgado", 900), ("estreito", 300)):
        CASES.append({
            "name": "troca-%s-%s" % (_dir, _tag),
            "settings": st(columns=2, drawerDirection=_dir),
            "widthBudget": _wb,
            "model": THREE_MODEL,
            "steps": [open_drawer("open", "TAU ALPHA", "Pill Tau"),
                      open_drawer("troca", "SIGMA CHAT", "Pill Sigma")],
        })


# --------------------------------------------------------------------------- #
# SEGUNDA PASSADA — fixtures e casos (T42b)
# --------------------------------------------------------------------------- #
#
# Nomes e rótulos deliberadamente exclusivos: nenhum rótulo de detalhe é prefixo
# de outro, para que `has()` não case o provider errado. Todo provider tem DUAS
# métricas (o primário tem seis), porque a pílula desenha só a LÍDER — assim um
# rótulo de métrica que aparece na árvore é prova de GAVETA, nunca de pílula.

def _mk(pid: str, name: str, labels: list) -> dict:
    return provider(pid, name, [metric(l, 20 + 10 * i) for i, l in enumerate(labels)])


#: Primário de SEIS métricas: é o lado que a tentação de "esconder o que não
#: couber" atacaria primeiro (T36 manda desenhar tudo sem clique).
VET = _mk("vet", "Pill Vet", ["Vet A1", "Vet A2", "Vet A3", "Vet A4", "Vet A5", "Vet A6"])
OVEN = _mk("omega", "Pill Omega", ["Omega M%d" % i for i in range(1, 7)])

#: MESMO VENDOR, CONTAS DIFERENTES. Este par é o que separa "id completo" de
#: "vendor": abrir `openai@work` não pode abrir `openai`.
WORK = _mk("openai@work", "Pill Work", ["Work Alpha", "Work Beta"])
HOME = _mk("openai", "Pill Home", ["Home Alpha", "Home Beta"])

BETA = _mk("beta", "Pill Beta", ["Beta Alpha", "Beta Beta"])
DELTA = _mk("delta", "Pill Delta", ["Delta Alpha", "Delta Beta"])
EPS = _mk("eps", "Pill Eps", ["Eps Alpha", "Eps Beta"])

#: Cópias de OBJETOS NOVOS com os MESMOS ids e rótulos trocados: é o que o
#: serviço entrega a cada poll. Se a gaveta exibisse o rótulo velho, ela estaria
#: guardando o objeto antigo em vez de reler o modelo.
VET2 = _mk("vet", "Pill Vet", ["Vet A1", "Vet A2", "Vet A3", "Vet A4", "Vet A5", "Vet A6"])
WORK2 = _mk("openai@work", "Pill Work", ["Work Zeta", "Work Eta"])
DELTA2 = _mk("delta", "Pill Delta", ["Delta Alpha", "Delta Beta"])
EPS2 = _mk("eps", "Pill Eps", ["Eps Alpha", "Eps Beta"])

#: `all` continua com WORK, mas `secondary` já não o contém: é a forma que o
#: serviço produz quando `maxSecondary` encolhe (o limite é aplicado lá, T35.3).
TETO_MODEL = {
    "schema": 1, "primary": VET, "secondary": [DELTA],
    "all": [VET, WORK, DELTA], "total_providers": 3, "with_issues": 0,
}

CASES += [
    # ---- (i) o modelo do serviço não é mutado nem reordenado ---------------
    # Teto pequeno de propósito: é aqui que "esvaziar o que não couber" seria
    # mais tentador. A sonda fotografa o modelo ANTES de montar e depois de cada
    # abertura/fechamento.
    {"name": "b-mut", "settings": st(columns=2, drawerMaxHeight=110),
     "model": model_of([VET, OVEN, WORK]),
     "steps": [{"op": "model", "name": "m-pre"}, snap("fechada"),
               open_drawer("omega-aberta", "OMEGA M1", "Pill Omega"),
               {"op": "model", "name": "m-omega-aberta"},
               {"op": "clickText", "value": "Pill Omega"},
               snap("omega-fechada"),
               {"op": "model", "name": "m-omega-fechada"},
               open_drawer("work-aberta", "WORK ALPHA", "Pill Work"),
               {"op": "model", "name": "m-work-aberta"},
               {"op": "model", "name": "m-fim"}]},

    # ---- (ii.1) a gaveta sobrevive a um poll do MESMO provider ------------
    {"name": "b-poll-mesmo", "settings": st(columns=2),
     "model": model_of([VET, WORK, DELTA]),
     "steps": [open_drawer("aberta", "WORK ALPHA", "Pill Work"),
               {"op": "poll", "name": "depois",
                "model": model_of([VET2, WORK2, DELTA2])}]},

    # ---- (ii.2) a gaveta NÃO é transferida ao novo ocupante da célula -----
    {"name": "b-poll-ocupante", "settings": st(columns=2),
     "model": model_of([VET, WORK, DELTA]),
     "steps": [open_drawer("aberta", "WORK ALPHA", "Pill Work"),
               {"op": "poll", "name": "depois",
                "model": model_of([VET2, EPS2, DELTA2])}]},
    {"name": "b-ctl-ocupante", "settings": st(columns=2),
     "model": model_of([VET, EPS, DELTA]), "steps": [snap("fresca")]},

    # ---- (ii.2) o provider aberto VIROU PRIMÁRIO --------------------------
    {"name": "b-poll-primario", "settings": st(columns=2),
     "model": model_of([VET, WORK, DELTA]),
     "steps": [open_drawer("aberta", "WORK ALPHA", "Pill Work"),
               {"op": "poll", "name": "depois",
                "model": model_of([WORK2, VET2, DELTA2])}]},
    {"name": "b-ctl-primario", "settings": st(columns=2),
     "model": model_of([WORK2, VET2, DELTA2]), "steps": [snap("fresca")]},

    # ---- (ii.2) o provider aberto saiu por showSecondaries: false ---------
    {"name": "b-poll-setting", "settings": st(columns=2),
     "model": model_of([VET, WORK, DELTA]),
     "steps": [open_drawer("aberta", "WORK ALPHA", "Pill Work"),
               {"op": "poll", "name": "depois",
                "settings": st(columns=2, showSecondaries=False),
                "model": model_of([VET, WORK, DELTA])}]},
    {"name": "b-ctl-setting", "settings": st(columns=2, showSecondaries=False),
     "model": model_of([VET, WORK, DELTA]), "steps": [snap("fresca")]},

    # ---- (ii.2) o provider aberto saiu por teto (maxSecondary menor) ------
    {"name": "b-poll-teto", "settings": st(columns=2),
     "model": model_of([VET, WORK, DELTA]),
     "steps": [open_drawer("aberta", "WORK ALPHA", "Pill Work"),
               {"op": "poll", "name": "depois", "model": TETO_MODEL}]},
    {"name": "b-ctl-teto", "settings": st(columns=2),
     "model": TETO_MODEL, "steps": [snap("fresca")]},

    # ---- (ii.3) a gaveta não persiste em lugar nenhum (remontagem) --------
    {"name": "b-remontar", "settings": st(columns=2),
     "model": model_of([VET, WORK, DELTA]),
     "steps": [open_drawer("aberta", "WORK ALPHA", "Pill Work"),
               {"op": "remount"}, snap("depois")]},
    {"name": "b-ctl-remontar", "settings": st(columns=2),
     "model": model_of([VET, WORK, DELTA]), "steps": [snap("fresca")]},

    # ---- (ii) identidade pelo id COMPLETO (vendor + conta) ----------------
    {"name": "b-contas", "settings": st(columns=2),
     "model": model_of([VET, WORK, HOME]),
     "steps": [snap("fechada"),
               {"op": "ensureOpen", "text": "WORK ALPHA", "click": "Pill Work"},
               snap("aberta-work"),
               {"op": "snapAfterOpen", "name": "aberta-home",
                "text": "HOME ALPHA", "click": "Pill Home"}]},

    # ---- (iii) no máximo UMA gaveta aberta, em números -------------------
    {"name": "b-uma-n3", "settings": st(columns=2),
     "model": model_of([VET, BETA, DELTA, EPS]),
     "steps": [snap("fechada"),
               open_drawer("b", "BETA ALPHA", "Pill Beta"),
               open_drawer("d", "DELTA ALPHA", "Pill Delta"),
               open_drawer("e", "EPS ALPHA", "Pill Eps")]},
    {"name": "b-uma-n1", "settings": st(columns=2),
     "model": model_of([VET, BETA]),
     "steps": [snap("fechada"),
               open_drawer("b", "BETA ALPHA", "Pill Beta")]},
]


# --------------------------------------------------------------------------- #
# Banco: um único processo quickshell para todos os casos
# --------------------------------------------------------------------------- #

class Node:
    __slots__ = ("id", "parent", "kind", "text", "x", "y", "w", "h", "radius",
                 "alpha", "interactive")

    def __init__(self, fields: list[str]):
        self.id = int(fields[0])
        self.parent = int(fields[1])
        self.kind = fields[2]
        self.text = json.loads(fields[3])
        self.x = float(fields[4])
        self.y = float(fields[5])
        self.w = float(fields[6])
        self.h = float(fields[7])
        self.radius = float(fields[8])
        self.alpha = float(fields[9])
        self.interactive = fields[10] == "true"


class Snap:
    """Censo de um estado da view."""

    def __init__(self, name: str):
        self.name = name
        self.props: dict[str, tuple[str, object]] = {}
        self.saves: list[str] = []
        self.iw = self.ih = self.w = self.h = None
        self.nodes: list[Node] = []
        self._by_id: dict[int, Node] = {}
        self._kids: dict[int, list[int]] = {}

    # -- montagem ---------------------------------------------------------
    def finish(self):
        self._by_id = {n.id: n for n in self.nodes}
        self._kids = {}
        for n in self.nodes:
            self._kids.setdefault(n.parent, []).append(n.id)
        return self

    # -- leitura ----------------------------------------------------------
    @property
    def texts(self) -> list[str]:
        """Textos na ordem da árvore (ordem de leitura de uma grade)."""
        return [n.text for n in self.nodes if n.text]

    def has(self, needle: str) -> bool:
        up = needle.upper()
        return any(up in t.upper() for t in self.texts)

    def find(self, needle: str) -> list[str]:
        up = needle.upper()
        return [t for t in self.texts if up in t.upper()]

    def prop(self, name: str):
        """(typeof, valor). ``("undefined", ...)`` quando a propriedade não existe."""
        return self.props.get(name, ("undefined", None))

    def children(self, nid: int) -> list[Node]:
        return [self._by_id[k] for k in self._kids.get(nid, [])]

    def subtree(self, nid: int) -> list[Node]:
        out = [self._by_id[nid]]
        for k in self._kids.get(nid, []):
            out.extend(self.subtree(k))
        return out

    def subtree_texts(self, nid: int) -> list[str]:
        return [n.text for n in self.subtree(nid) if n.text]

    def ancestors(self, nid: int) -> list[Node]:
        out = []
        cur = self._by_id[nid].parent
        while cur and cur in self._by_id and len(out) < 40:
            out.append(self._by_id[cur])
            cur = self._by_id[cur].parent
        return out

    def grids(self) -> list[Node]:
        return [n for n in self.nodes if n.kind == "QQuickGrid"]

    def cells(self) -> list[Node]:
        """Células VISUAIS da grade de pílulas.

        Filhas imediatas do ``QQuickGrid`` menos os recursos não visuais: o
        ``data`` de um Grid inclui ``Repeater``/``Timer``/handlers, que não são
        células. Filtrar por "não é recurso" é estrutural; filtrar por tamanho
        seria frágil, e filtrar por tipo de componente seria olhar a
        implementação.
        """
        cells: list[Node] = []
        for g in self.grids():
            for child in self.children(g.id):
                if re.search(r"Repeater|Timer|Handler|Behavior|Animation|Transition|"
                             r"Instantiator|Delegate", child.kind):
                    continue
                cells.append(child)
        return cells

    def pill_texts(self, cell: Node) -> list[str]:
        return self.subtree_texts(cell.id)

    def pill_bars(self, cell: Node) -> list[Node]:
        """Retângulos pintados dentro da pílula: trilho (alpha baixo) e
        preenchimento (alpha alto). Retângulo de alpha 0 não é barra visível."""
        return [n for n in self.subtree(cell.id)
                if n.kind.startswith("QQuickRectangle") and n.alpha > 0.05]

    def cell_named(self, name: str) -> Node:
        """A pílula que carrega EXATAMENTE este texto de nome.

        Igualdade exata de propósito: `in` casaria "Pill Tau" dentro de
        "Pill Sigma" se os nomes fossem aninhados, e o teste mediria a pílula
        errada sem falhar de forma legível.
        """
        alvo = _nome(name).upper()
        hits = [c for c in self.cells()
                if any(_nome(t).upper() == alvo for t in self.pill_texts(c))]
        assert len(hits) == 1, (
            f"esperava UMA pílula com {name!r}; achei {len(hits)}: "
            f"{[self.pill_texts(c) for c in hits]}")
        return hits[0]

    def interactives(self) -> list[Node]:
        return [n for n in self.nodes if n.interactive]

    # -- geometria da GAVETA (medida, não inferida) -----------------------
    #
    # Posição de PÍLULA não resolve em offscreen (toda célula sai em x=12,y=10),
    # mas a posição do PAINEL DO DETALHE e a da GRADE resolvem — e de forma
    # determinística (medido em duas execuções independentes e em quatro atrasos
    # de censo). A direção é, por isso, medida por GEOMETRIA.
    #
    # EMENDA T38 (2026-10-30): o painel deixou de ser IRMÃO da grade. Detalhe e
    # grade passam a viver numa FAIXA comum; dentro dela o detalhe ocupa a área
    # liberada de um lado e a grade fica do outro. Achar o painel por irmandade
    # media a topologia REVOGADA — foi o que produziu 13 das falhas do arquivo
    # antigo. A busca agora é: ancestral comum da grade e do texto-marcador
    # (a faixa) e, dentro dela, o galho que carrega o marcador e NÃO contém a
    # grade.

    #: Recursos não visuais que podem aparecer na faixa.
    _NAO_VISUAL = re.compile(
        r"Repeater|Timer|Handler|Behavior|Animation|Transition|Instantiator|Delegate")

    def grid(self) -> Node:
        """A grade de pílulas. Exige UMA só: duas grades seria outra view."""
        gs = self.grids()
        assert len(gs) == 1, f"esperava UMA grade; achei {len(gs)}"
        return gs[0]

    def marker_node(self, marker: str) -> Node:
        """O nó de TEXTO que carrega ``marker`` (rótulo exclusivo de uma métrica
        do provider aberto: existe na gaveta e nunca na pílula)."""
        alvo = marker.upper()
        hits = [n for n in self.nodes if alvo in n.text.upper()]
        assert hits, f"o marcador {marker!r} não está na árvore"
        return hits[0]

    def band(self, marker: str) -> Node:
        """O contêiner que abriga a GRADE e o DETALHE (a faixa da emenda T38).

        É o ancestral comum mais próximo entre a grade e o texto-marcador. Não
        supõe nome de componente nem que o detalhe seja irmão da grade; só que
        os dois estão sob o mesmo pai, que é o que a emenda afirma.
        """
        grid = self.grid()
        alvo = self.marker_node(marker)
        antepassados: list[int] = []
        cur = grid.id
        while cur and cur in self._by_id:
            antepassados.append(cur)
            cur = self._by_id[cur].parent
        cur = alvo.id
        for _ in range(40):
            if cur in antepassados:
                no = self._by_id[cur]
                assert no.id != grid.id, (
                    f"o marcador {marker!r} está DENTRO da grade: o detalhe não "
                    f"existe como área separada")
                return no
            cur = self._by_id[cur].parent
        assert False, f"a grade e {marker!r} não têm ancestral comum"

    def _contem(self, nid: int, needle: str) -> bool:
        up = needle.upper()
        return any(up in t.upper() for t in self.subtree_texts(nid))

    def drawer_panel(self, marker: str) -> Node:
        """O contêiner do DETALHE aberto, achado por FAIXA + CONTEÚDO.

        É o galho da faixa que carrega ``marker`` e não engole a grade. Procura
        primeiro entre as filhas diretas da faixa e só desce se necessário — a
        mesma forma serve para as três direções, que é o ponto: a sonda não
        sabe (e não precisa saber) em que lado o detalhe foi desenhado.
        """
        faixa = self.band(marker)
        grade = self.grid()
        na_grade = {n.id for n in self.subtree(grade.id)}
        candidatos: list[Node] = []
        fila = [ch for ch in self.children(faixa.id)
                if not self._NAO_VISUAL.search(ch.kind)]
        while fila:
            ch = fila.pop(0)
            # O galho que contém a grade não pode conter o detalhe: a faixa é o
            # ANCESTRAL COMUM MÍNIMO entre os dois, então essa separação é
            # garantida por construção. Descer nele só procuraria o que não há.
            if ch.id in na_grade:
                continue
            if self._contem(ch.id, marker):
                # Candidato: o PRIMEIRO galho que carrega o marcador. Não se
                # desce nele — descer acharia também os netos e quebraria a
                # unicidade da asserção.
                candidatos.append(ch)
                continue
            fila.extend(k for k in self.children(ch.id)
                        if not self._NAO_VISUAL.search(k.kind))
        assert len(candidatos) == 1, (
            f"esperava UM painel de detalhe na faixa carregando {marker!r}; "
            f"achei {len(candidatos)}: "
            f"{[(c.kind, c.x, c.y, c.w, c.h) for c in candidatos]}")
        return candidatos[0]

    #: Glifos da SETA de retorno (emenda T38). Texto exato: qualquer outra seta
    #: decorativa na view faria um `in` casar duas coisas diferentes.
    SETA_PILULAS_A_DIREITA = "\u2192"
    SETA_PILULAS_A_ESQUERDA = "\u2190"
    SETAS = (SETA_PILULAS_A_DIREITA, SETA_PILULAS_A_ESQUERDA)

    def arrow_strip(self, marker: str) -> tuple[Node, str]:
        """(faixa-alta-da-seta, glifo) dentro do painel do detalhe.

        A emenda manda a seta na PONTA do detalhe. Aqui a seta é achada pelo
        glifo que ela exibe; o controle é o ancestral mais próximo que tenha um
        descendente interativo — a faixa que o usuário clica.
        """
        painel = self.drawer_panel(marker)
        glifos = [n for n in self.subtree(painel.id) if n.text in self.SETAS]
        assert len(glifos) == 1, (
            f"esperava UMA seta dentro do detalhe; achei {len(glifos)}: "
            f"{[(g.text, g.x, g.y, g.w, g.h) for g in glifos]}")
        glifo = glifos[0]
        up = glifo
        for _ in range(6):
            if up is None:
                break
            if any(n.interactive for n in self.subtree(up.id)):
                return up, glifo.text
            up = self._by_id.get(up.parent)
        assert False, f"a seta {glifo.text!r} não tem alvo clicável (controle morto)"

    def direction_of(self, marker: str) -> str:
        """A direção EFETIVA do detalhe, derivada da geometria de faixa.

        ``down``   -> o painel começa ABAIXO do topo da grade e ocupa a MESMA
                      coluna horizontal dela (largura igual, x igual).
        ``left``   -> o painel encosta na grade pela BORDA ESQUERDA desta
                      (painel.x + painel.w == grade.x): ocupa a área liberada à
                      esquerda, sem sobrepor a grade.
        ``right``  -> o mesmo pela borda direita (painel.x == grade.x + grade.w).

        Devolve ``"?"`` quando não se encaixa em nenhum dos três: um layout
        inesperado NÃO pode ser arredondado para o valor esperado.
        """
        eps = 0.75
        grid = self.grid()
        painel = self.drawer_panel(marker)
        # `down`: mesma coluna da grade, começando nela ou abaixo.
        if abs(painel.x - grid.x) <= eps and abs(painel.w - grid.w) <= eps \
                and painel.y >= grid.y - eps:
            return "down"
        # Lateral: o painel está INTEIRO de um dos lados, sem invadir a grade.
        # Comparação por lado (e não por encosto exato) para que uma folga de
        # layout não seja confundida com "layout inesperado".
        if painel.x + painel.w <= grid.x + eps:
            return "left"
        if painel.x >= grid.x + grid.w - eps:
            return "right"
        return "?"

    def drawer_geometry(self, marker: str) -> tuple:
        """(grade, painel) — para mensagens de falha legíveis."""
        return self.grid(), self.drawer_panel(marker)


class Dump:
    """Saída de uma execução da sonda: censos + impressões digitais do modelo."""

    def __init__(self):
        self.cases: dict[str, dict[str, Snap]] = {}
        self.models: dict[str, dict[str, str]] = {}


def _parse(stdout: str) -> Dump:
    d = Dump()
    out = d.cases
    case = snap = None
    for raw in _ANSI.sub("", stdout).splitlines():
        if " qml: " in raw:
            raw = raw.split(" qml: ", 1)[1]
        line = raw.strip()
        if line.startswith("===CASE|"):
            case = line[len("===CASE|"):-3]
            out.setdefault(case, {})
            d.models.setdefault(case, {})
        elif line.startswith("===CASE_END|"):
            case = None
            snap = None
        elif line.startswith("MODEL|") and case is not None:
            _, nome, fp = line.split("|", 2)
            d.models[case][nome] = fp
        elif line.startswith("===SNAP|"):
            assert case is not None, "SNAP fora de um CASE"
            snap = Snap(line[len("===SNAP|"):-3])
            out[case][snap.name] = snap
        elif line.startswith("===SNAP_END|"):
            assert snap is not None, "SNAP_END sem SNAP"
            snap.finish()
            snap = None
        elif snap is not None and line:
            _feed(snap, line)
    return d


def _feed(snap: Snap, line: str):
    if line.startswith("SAVES|"):
        try:
            snap.saves = json.loads(line.split("|", 1)[1])
        except ValueError:
            snap.saves = ["<ilegível>"]
    elif line.startswith("PROP|"):
        _, name, typeof, value = line.split("|", 3)
        parsed = None
        if typeof in ("number", "string", "boolean"):
            try:
                parsed = json.loads(value)
            except ValueError:
                parsed = value
        snap.props[name] = (typeof, parsed)
    elif line.startswith("IW|"):
        partes = line.split("|")
        snap.iw, snap.ih, snap.w, snap.h = (
            float(partes[1]), float(partes[2]), float(partes[3]), float(partes[4]))
    elif line.startswith("NODE|"):
        snap.nodes.append(Node(line.split("|")[1:]))


def _run(cases: list[dict]) -> tuple[Dump, str]:
    brute = ""
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("WAYLAND_DISPLAY", None)
    env["T42_PLUG_DIR"] = str(PLUGIN_DIR)
    # Cada caso vai em PARTES de <=60000 chars: um único valor de ambiente
    # acima de MAX_ARG_STRLEN (128 KiB) impede o processo de iniciar.
    payload = json.dumps(cases, ensure_ascii=False)
    partes = [payload[i:i + 60000] for i in range(0, len(payload), 60000)] or ["[]"]
    for k, parte in enumerate(partes):
        env["T42_CASES_%d" % k] = parte
    env["T42_CASES_PARTS"] = str(len(partes))
    # stateDir ÚNICO por execução: um caminho fixo compartilhado entre dois
    # processos quickshell simultâneos (suítes em paralelo, ou um run anterior
    # que não terminou) cria interferência cruzada e faz um teste alheio falhar
    # por motivo que não é o dele. Medido nesta base: com `/tmp/t42-state` fixo,
    # uma execução da suíte inteira acusou 4 falhas em test_t9 que não se
    # reproduzem isoladas.
    env["T42_STATE_DIR"] = tempfile.mkdtemp(prefix="t42-state-")
    try:
        proc = subprocess.run(
            [_QUICK, "-p", str(HARNESS)],
            capture_output=True, text=True, env=env, timeout=420,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            "o harness QML não terminou em 420s — a view provavelmente não monta "
            "(arquivo ausente/quebrado). Sem view não há comportamento a verificar.")
    parsed = _parse(proc.stdout + proc.stderr)
    brute = proc.stdout + proc.stderr
    missing = [c["name"] for c in cases if c["name"] not in parsed.cases]
    assert not missing, (
        f"a sonda não montou os casos {missing!r}; rc={proc.returncode}\n"
        f"stderr(tail)={proc.stderr[-1200:]}")
    return parsed, brute


@pytest.fixture(scope="session")
def bancada():
    parsed, brute = _run(CASES)
    return {"dumps": parsed.cases, "models": parsed.models, "raw": brute}


def dump(bancada, case: str) -> dict[str, Snap]:
    return bancada["dumps"][case]


def models(bancada, case: str) -> dict[str, str]:
    """Impressões digitais do ``service.model``, por momento do caso."""
    return bancada["models"][case]


# --------------------------------------------------------------------------- #
# 0. Antipassividade: os artefatos sob teste existem
# --------------------------------------------------------------------------- #

def test_artefatos_sob_teste_existem():
    """Falha rápido se a view/harness sumiram — revert não pode virar SKIP."""
    assert (PLUGIN_DIR / "content" / "Widget.qml").is_file(), "content/Widget.qml ausente"
    assert HARNESS.is_file(), f"harness QML ausente: {HARNESS}"


def test_a_view_monta_e_desenha_o_primario(bancada):
    """Âncora de toda a suíte: sem primário na árvore, nada abaixo prova nada."""
    s = dump(bancada, "primary-all")["s"]
    assert s.texts, "a árvore renderizada está vazia"
    # Âncora de formato: `columns` e `openDrawerId` são propriedades do formato
    # ÚNICO. Sem elas a view não é a que este arquivo contrata.
    assert s.prop("columns")[0] == "number", "a view não expõe `columns` (formato duplo?)"
    assert s.prop("openDrawerId")[0] == "string", "a view não expõe `openDrawerId`"
    for esperado in ("Pill Alpha", "ALPHA SESSION", "ALPHA WEEKLY", "ALPHA MONTHLY"):
        assert s.has(esperado), f"primário incompleto: {esperado!r} não renderizou; {s.texts}"
    bruto = bancada["raw"]
    assert not [l for l in bruto.splitlines() if "VIEW_ERR|props" in l], (
        "a view lançou ao receber as propriedades do host")


# --------------------------------------------------------------------------- #
# 1. T33 — largura derivada das colunas
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("caso,esperado", [
    ("cols-absent", 2),   # ausente cai em 2
    ("cols-abc", 2),      # não numérico cai em 2
    ("cols-1", 2),        # abaixo da faixa é preso em 2
    ("cols-9", 4),        # acima da faixa é preso em 4
    ("cols-2", 2),
    ("cols-3", 3),
    ("cols-4", 4),
])
def test_columns_cai_sempre_dentro_de_2_a_4(bancada, caso, esperado):
    """Contrato T33.1: ``columns`` é uma setting 2..4 com fallback e trava.

    A asserção olha a PROPRIEDADE ``columns`` da view (o valor efetivo que ela
    usa) e a largura implícita correspondente — não a leitura da setting.
    """
    s = dump(bancada, caso)["s"]
    tipo, valor = s.prop("columns")
    assert tipo == "number", (
        f"{caso}: `columns` não resolveu para um número (typeof={tipo}); "
        f"nenhuma trava de faixa é observável")
    assert valor == esperado, f"{caso}: columns efetivo {valor!r}, esperado {esperado}"


def test_implicit_width_cresce_estritamente_com_as_colunas(bancada):
    """T33.1/T33 objetivo: a largura do popout é derivada da grade.

    Estritamente crescente — ``igual`` significaria que a setting não chega ao
    layout, o defeito que o teste existe para pegar.
    """
    larguras = {}
    for cols in (2, 3, 4):
        s = dump(bancada, f"cols-{cols}")["s"]
        assert s.iw is not None, f"cols-{cols}: implicitWidth não observável"
        larguras[cols] = s.iw
    assert larguras[2] < larguras[3] < larguras[4], (
        f"implicitWidth não cresce com columns: {larguras}")
    # A largura do popout precisa caber as pílulas: crescer menos que uma
    # coluna por passo significaria corte silencioso.
    passo_23 = larguras[3] - larguras[2]
    passo_34 = larguras[4] - larguras[3]
    assert passo_23 > 0 and passo_34 > 0, f"passos não positivos: {larguras}"


def test_colunas_acima_da_faixa_nao_alarga_mais_que_quatro(bancada):
    """Negativo de T33: valor fora da faixa não pode criar uma quinta coluna."""
    quatro = dump(bancada, "cols-4")["s"]
    nove = dump(bancada, "cols-9")["s"]
    assert quatro.iw is not None and nove.iw is not None
    # Âncoras: sem `columns` resolvido as duas larguras seriam iguais por
    # AUSÊNCIA de grade, e o teste passaria sem testar a trava.
    assert quatro.prop("columns")[0] == "number", "columns não resolveu no caso 4"
    assert nove.prop("columns")[0] == "number", "columns não resolveu no caso 9"
    assert quatro.iw > 0 and nove.iw > 0, f"larguras não medidas: {quatro.iw}, {nove.iw}"
    assert nove.iw == quatro.iw, (
        f"columns=9 deveria ser preso em 4; largura 9={nove.iw} vs 4={quatro.iw}")


# --------------------------------------------------------------------------- #
# 2. T34 — a pílula: nome + barra + percentual, e quatro estados por TEXTO
# --------------------------------------------------------------------------- #

def test_toda_pilula_carrega_nome_percentual_e_barra(bancada):
    """T34/objetivo: a pílula desenha nome, barra e percentual — nenhum dos três
    é opcional quando há percentual.

    Esta asserção é feita nas pílulas com percentual conhecido (Beta 64% líder,
    Gamma 0%, Epsilon 90%). As sem percentual são o caso de borda seguinte.
    """
    s = dump(bancada, "states-2")["s"]
    for nome, pct in (("Pill Beta", "64%"), ("Pill Gamma", "0%"), ("Pill Epsilon", "90%")):
        cell = s.cell_named(nome)
        textos = s.pill_texts(cell)
        assert nome in textos, f"{nome}: a pílula não carrega o TEXTO do nome; {textos}"
        assert pct in textos, f"{nome}: a pílula não carrega o TEXTO do percentual; {textos}"
        barras = s.pill_bars(cell)
        assert barras, f"{nome}: a pílula não desenha barra (nenhum retângulo visível)"
        trilhos = [b for b in barras if b.alpha < 0.5]
        assert trilhos, f"{nome}: a pílula não desenha TRILHO (só preenchimento)"


def test_estado_erro_mostra_ERROR_e_esconde_o_percentual(bancada):
    """T34.2 (mandato): provider ``status: error`` anuncia ``ERROR`` por TEXTO e
    NÃO mostra o percentual.

    O erro tem de ser distinguível sem cor: um daltoniano lê ``ERROR``. Aqui o
    percentual do erro é 30% — se ele aparecesse, ``30%`` estaria na árvore.
    """
    s = dump(bancada, "states-2")["s"]
    cell = s.cell_named("Pill Zeta")
    textos = s.pill_texts(cell)
    assert any("ERROR" in t.upper() for t in textos), (
        f"provider em erro sem o texto ERROR: {textos}")
    assert not any("30%" in t for t in textos), (
        f"provider em erro ainda mostra o percentual: {textos}")


def test_estado_stale_mostra_STALE_e_mantem_o_percentual(bancada):
    """T34.2: ``stale`` é um aviso AO LADO do dado, não no lugar dele."""
    s = dump(bancada, "states-2")["s"]
    cell = s.cell_named("Pill Epsilon")
    textos = s.pill_texts(cell)
    assert any("STALE" in t.upper() for t in textos), (
        f"provider stale sem o texto STALE: {textos}")
    assert "90%" in textos, f"provider stale perdeu o percentual: {textos}"


def test_percentual_zero_desenha_trilho_vazio_e_mostra_0(bancada):
    """T34.1: ``0%`` é dado, não ausência — trilho desenhado, largura zero."""
    s = dump(bancada, "states-2")["s"]
    cell = s.cell_named("Pill Gamma")
    textos = s.pill_texts(cell)
    assert "0%" in textos, f"métrica com percent 0 não mostra '0%': {textos}"
    barras = s.pill_bars(cell)
    assert barras, "métrica com percent 0 não desenha trilho (confundida com ausência)"
    preenchimentos = [b for b in barras if b.alpha >= 0.5]
    assert preenchimentos, "métrica com percent 0 não desenhou preenchimento (largura zero)"
    assert all(b.w == 0 for b in preenchimentos), (
        f"preenchimento de 0% deveria ter largura zero; vi "
        f"{[b.w for b in preenchimentos]}")


def test_percentual_ausente_mostra_travessao_e_nao_desenha_trilho(bancada):
    """T34.1/T30: ausência de percentual é ``—`` e NENHUM trilho.

    Distinguir 0 de ausente é o ponto: se os dois desenhassem trilho, a tela
    mentiria dizendo "zero usado" quando na verdade não há dado.
    """
    s = dump(bancada, "states-2")["s"]
    cell = s.cell_named("Pill Delta")
    textos = s.pill_texts(cell)
    assert DASH in textos, f"métrica sem percentual não mostra {DASH!r}: {textos}"
    assert not any("%" in t for t in textos), (
        f"métrica sem percentual inventou um percentual: {textos}")
    assert not s.pill_bars(cell), (
        "métrica sem percentual desenhou barra/trilho — indistinguível de 0%: "
        f"{[(b.w, b.alpha) for b in s.pill_bars(cell)]}")


def test_provider_pronto_sem_metrica_mostra_NO_DATA(bancada):
    """T34.2: pronto e vazio não pode virar pílula em branco."""
    s = dump(bancada, "states-2")["s"]
    cell = s.cell_named("Pill Eta")
    textos = s.pill_texts(cell)
    assert any("NO DATA" in t.upper() for t in textos), (
        f"provider pronto sem métricas não anuncia NO DATA: {textos}")


def test_os_quatro_estados_sao_distinguiveis_so_por_texto(bancada):
    """T34/objetivo: nenhum estado depende exclusivamente de cor.

    Reúne os quatro textos de estado numa única asserção: se dois estados
    colapsarem no mesmo texto, o usuário sem cor não os separa.
    """
    s = dump(bancada, "states-2")["s"]
    por_estado = {
        "erro": s.pill_texts(s.cell_named("Pill Zeta")),
        "stale": s.pill_texts(s.cell_named("Pill Epsilon")),
        "zero": s.pill_texts(s.cell_named("Pill Gamma")),
        "ausente": s.pill_texts(s.cell_named("Pill Delta")),
        "sem-dado": s.pill_texts(s.cell_named("Pill Eta")),
    }
    marcas = {
        "erro": any("ERROR" in t.upper() for t in por_estado["erro"]),
        "stale": any("STALE" in t.upper() for t in por_estado["stale"]),
        "zero": "0%" in por_estado["zero"],
        "ausente": DASH in por_estado["ausente"],
        "sem-dado": any("NO DATA" in t.upper() for t in por_estado["sem-dado"]),
    }
    assert all(marcas.values()), f"estados sem marca textual: {marcas} / {por_estado}"


def test_alvo_clicavel_da_pilula_tem_no_minimo_24px_logicos(bancada):
    """T34.4: alvo mínimo 24×24 em ``s`` = 1.

    O alvo é o nó INTERATIVO dentro da célula (o que recebe o clique), não o
    cartão que o envolve: um MouseArea de 12 px dentro de um cartão de 44 px
    continua sendo um alvo de 12 px.
    """
    s = dump(bancada, "states-2")["s"]
    medidos = []
    for cell in s.cells():
        alvos = [n for n in s.subtree(cell.id) if n.interactive]
        if not alvos:
            continue
        for a in alvos:
            medidos.append((s.pill_texts(cell), a.kind, a.w, a.h))
    assert medidos, "nenhuma pílula tem nó interativo — a grade não é clicável"
    pequenos = [(n, k, w, h) for (n, k, w, h) in medidos if h < 24 or w < 24]
    assert not pequenos, f"alvo clicável abaixo de 24×24 px lógicos: {pequenos}"


# --------------------------------------------------------------------------- #
# 3. T35 — a grade: contagem e ORDEM de model.secondary
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("cols", [2, 3, 4])
def test_a_grade_desenha_uma_pilula_por_secundario(bancada, cols):
    """T35.3: o número de pílulas é sempre o de ``model.secondary``.

    A ordem do relatório é deliberadamente não alfabética e os sete providers
    cobrem os quatro estados — um grid que reordenasse ou deduplicasse por
    estado apareceria aqui.
    """
    s = dump(bancada, f"states-{cols}")["s"]
    esperados = [p["display_name"] for p in STATES_MODEL["secondary"]]
    assert len(esperados) == 6, "o fixture de ordem deveria ter 6 secundários"
    cells = s.cells()
    assert len(cells) == len(esperados), (
        f"columns={cols}: {len(cells)} pílulas para {len(esperados)} secundários; "
        f"células={[s.pill_texts(c) for c in cells]}")
    nomes = []
    for c in cells:
        textos = [_nome(t).upper() for t in s.pill_texts(c)]
        nomes.append(next((n for n in esperados if _nome(n).upper() in textos),
                          "<desconhecido>"))
    assert nomes == esperados, (
        f"columns={cols}: ordem da grade diferente da de model.secondary; "
        f"vi {nomes}, esperava {esperados}")


def test_show_secondaries_false_nao_desenha_nenhuma_pilula(bancada):
    """T35.3: ``showSecondaries: false`` esconde a seção inteira.

    Âncora: o mesmo modelo, com a setting ligada, desenha 6 pílulas.
    """
    on = dump(bancada, "states-2")["s"]
    off = dump(bancada, "sec-off")["s"]
    assert len(on.cells()) == 6, "o caso de controle deveria ter 6 pílulas"
    assert len(off.cells()) == 0, (
        f"showSecondaries=false ainda desenhou {len(off.cells())} pílulas: "
        f"{[off.pill_texts(c) for c in off.cells()]}")
    # E o primário sobrevive à remoção da seção.
    assert off.has("Pill Alpha") and off.has("ALPHA SESSION"), (
        f"showSecondaries=false apagou o primário: {off.texts}")


def test_a_view_nao_desenha_mais_pilulas_do_que_o_modelo_entrega(bancada):
    """T35.3/T33: a grade não inventa secundários.

    ``maxSecondary`` é aplicado pelo SERVIÇO antes de serializar (T35.3), então
    o teste entrega o modelo JÁ limitado a 1 — reproduzindo o que a view recebe
    em produção — e exige exatamente uma pílula, a primeira da lista.
    """
    s = dump(bancada, "cap-model-1")["s"]
    cells = s.cells()
    assert len(cells) == 1, (
        f"modelo com 1 secundário rendeu {len(cells)} pílulas: "
        f"{[s.pill_texts(c) for c in cells]}")
    assert "Pill Beta" in s.pill_texts(cells[0]), (
        f"a pílula desenhada não é a do modelo: {s.pill_texts(cells[0])}")


def test_a_view_nao_desenha_mais_pilulas_do_que_o_modelo_entrega_cap_6(bancada):
    """Contraprova do anterior com teto folgado: 3 no modelo, 3 na grade."""
    s = dump(bancada, "cap-6")["s"]
    cells = s.cells()
    assert len(cells) == 3, (
        f"modelo com 3 secundários rendeu {len(cells)} pílulas: "
        f"{[s.pill_texts(c) for c in cells]}")


# --------------------------------------------------------------------------- #
# 4. T36 — o formato duplo morreu
# --------------------------------------------------------------------------- #

#: Identificadores que T36.1 manda remover. Este é o ÚNICO teste que olha nomes
#: de propriedade, e olha pela AUSÊNCIA — é o contrato da remoção.
PROPS_MORTAS = [
    "compactMode",
    "densityOverride",
    "compactByDefault",
    "visibleMetrics",
    "toggleAll",
    "anyProviderExpanded",
    "hiddenMetricCount",
    "hiddenMetricCountForLabel",
    "canToggleProvider",
    "modeButtonLabel",
    "modeButtonAction",
    "canToggleAny",
    "isExpanded",
    "toggleExpanded",
]


@pytest.mark.parametrize("nome", PROPS_MORTAS)
def test_a_view_nao_tem_mais_as_propriedades_do_formato_duplo(bancada, nome):
    """T36.1: o formato duplo não existe mais na view.

    Antipassividade: as propriedades VIVAS (``columns``, ``openDrawerId``) são
    afirmadas presentes no mesmo censo, então "undefined" aqui significa
    removida — não significa "a sonda leu um objeto vazio".
    """
    s = dump(bancada, "primary-all")["s"]
    tipo, _ = s.prop("columns")
    assert tipo == "number", "a sonda não leu as propriedades da view — a ausência seria vácua"
    tipo_open, _ = s.prop("openDrawerId")
    assert tipo_open == "string", "a sonda não leu openDrawerId — a ausência seria vácua"
    tipo, valor = s.prop(nome)
    assert tipo == "undefined", (
        f"a propriedade {nome!r} do formato duplo ainda existe na view "
        f"(typeof={tipo}, valor={valor!r})")


def test_o_primario_desenha_todas_as_metricas_sem_clique(bancada):
    """T36.2: sem nenhum clique, as 3 métricas do primário estão na árvore.

    A armadilha do formato antigo era o primário "compacto" esconder métricas
    atrás de um controle. A âncora é o caso sem clique algum.
    """
    s = dump(bancada, "primary-all")["s"]
    assert s.prop("openDrawerId")[1] == "", (
        "o caso de controle deveria estar sem gaveta aberta para provar 'sem clique'")
    for rotulo in ("ALPHA SESSION", "ALPHA WEEKLY", "ALPHA MONTHLY"):
        assert s.has(rotulo), f"métrica {rotulo!r} do primário não foi desenhada; {s.texts}"


def test_a_view_nunca_grava_setting(bancada):
    """T36.3/R5: a view não persiste nada.

    Controle de vacuidade embutido: no MESMO caso a sonda dispara
    ``apiObj.saveSetting`` uma vez de propósito (``SAVE_PROBE_OK``). Se o gancho
    estivesse quebrado, "a view não gravou" passaria sem testar nada.
    """
    raw = bancada["raw"]
    assert "SAVE_PROBE_OK|1" in raw, (
        "o controle da sonda não disparou: o gancho saveSetting sintético está "
        "quebrado e a asserção de vacuidade seria falsa")
    # O controle positivo tem de aparecer no censo do caso que o disparou.
    assert "T42_PROBE_CONTROL" in dump(bancada, "primary-all")["s"].saves, (
        "o controle positivo não chegou ao censo — a leitura de SAVES não funciona")
    for caso in ("primary-all", "drawer-open", "drawer-6-small", "sec-off"):
        for nome, snap_ in dump(bancada, caso).items():
            gravadas = [k for k in snap_.saves if k != "T42_PROBE_CONTROL"]
            assert not gravadas, (
                f"{caso}/{nome}: a view gravou settings {gravadas!r} (R5: a view "
                f"não persiste; o Hub é o único lugar de escrita)")


# --------------------------------------------------------------------------- #
# 5. T37 — a gaveta: fechada por padrão, conteúdo, teto e corte
# --------------------------------------------------------------------------- #

def test_gaveta_fechada_por_padrao_nao_expoe_detalhe(bancada):
    """T37.1 / T33: antes de qualquer clique o detalhe de um secundário não
    está na árvore — só a pílula.

    O marcador é o RÓTULO de uma métrica do secundário: ele existe apenas na
    gaveta, nunca na pílula (que mostra o líder e o percentual).
    """
    s = dump(bancada, "drawer-closed")["closed"]
    assert len(s.cells()) >= 1, "o caso de controle deveria ter pílulas"
    assert not s.has("TAU ALPHA"), (
        f"gaveta fechada já expõe a métrica do secundário: {s.texts}")
    tipo, valor = s.prop("openDrawerId")
    assert tipo == "string" and valor == "", (
        f"o caso de controle deveria começar sem gaveta; openDrawerId={valor!r}")


def test_abrir_a_gaveta_expoe_as_metricas_DESSE_secundario(bancada):
    """T37.1: o clique na pílula abre as métricas dela e só dela."""
    s = dump(bancada, "drawer-open")["open"]
    assert s.has("TAU ALPHA") and s.has("TAU BETA") and s.has("TAU GAMMA"), (
        f"a gaveta não expôs as métricas do provider aberto: {s.texts}")
    assert not s.has("SIGMA CHAT"), (
        f"a gaveta expôs métricas de OUTRO secundário: {s.texts}")
    # E o primário continua intacto (a gaveta não substitui o primário).
    assert s.has("ALPHA SESSION"), "a gaveta apagou o primário"


def test_o_contador_mais_N_more_conta_as_metricas_omitidas(bancada):
    """T37.3: acima do teto a gaveta corta e anuncia ``+N more``, com N igual ao
    de métricas NÃO desenhadas.

    O número não é fixado no teste: ele é COMPARADO com o censo. Assim o teste
    continua válido com qualquer altura que o layout escolha, mas quebra se o
    contador mentir — que é o defeito perigoso, porque o host recorta o excesso
    em silêncio e o texto é o único aviso.
    """
    s = dump(bancada, "drawer-6-small")["open"]
    rotulos = ["OMEGA M%d" % i for i in range(1, 7)]
    desenhadas = [r for r in rotulos if s.has(r)]
    assert desenhadas, "a gaveta não desenhou NENHUMA métrica com teto pequeno"
    assert len(desenhadas) < 6, (
        f"com drawerMaxHeight pequeno as 6 métricas couberam — o corte não foi "
        f"exercitado; {s.texts}")
    contadores = [t for t in s.texts if re.fullmatch(r"\+\d+\s+more", t.strip(), re.I)]
    assert contadores, f"gaveta cortada sem o anúncio '+N more': {s.texts}"
    numero = int(re.search(r"\d+", contadores[0]).group())
    assert numero == 6 - len(desenhadas), (
        f"o contador diz {numero} omitidas, mas {6 - len(desenhadas)} foram "
        f"omitidas (desenhadas: {desenhadas})")


def test_com_teto_generoso_nao_aparece_contador(bancada):
    """T37.3 (negativo): sem estouro, nenhum ``+N more``.

    Âncora: no MESMO modelo e com teto pequeno o contador aparece — senão "não
    apareceu" poderia ser só um contador que nunca é desenhado.
    """
    generoso = dump(bancada, "drawer-6-generous")["open"]
    pequeno = dump(bancada, "drawer-6-small")["open"]
    # Âncora: "não há contador" só é verdade útil com a gaveta ABERTA. Fechada,
    # a ausência do contador é trivial.
    assert generoso.prop("openDrawerId")[1] == "omega", (
        f"a gaveta não abriu no caso de teto generoso: "
        f"{generoso.prop('openDrawerId')}")
    assert [t for t in pequeno.texts if re.fullmatch(r"\+\d+\s+more", t.strip(), re.I)], (
        "o caso de controle (teto pequeno) não tem contador — o negativo seria vácuo")
    assert generoso.has("OMEGA M1") and generoso.has("OMEGA M6"), (
        f"com teto generoso a gaveta não desenhou as 6 métricas: {generoso.texts}")
    assert not [t for t in generoso.texts
                if re.fullmatch(r"\+\d+\s+more", t.strip(), re.I)], (
        f"contador apareceu sem corte: {generoso.texts}")


def test_com_tres_metricas_e_teto_generoso_nao_ha_corte(bancada):
    """T37: o provider de 3 métricas do critério de done não pode cortar."""
    s = dump(bancada, "drawer-3-generous")["open"]
    assert s.prop("openDrawerId")[1] == "tau", (
        f"a gaveta não abriu — 'sem corte' seria vácuo: {s.prop('openDrawerId')}")
    for rotulo in ("TAU ALPHA", "TAU BETA", "TAU GAMMA"):
        assert s.has(rotulo), f"{rotulo!r} sumiu com teto generoso: {s.texts}"
    assert not [t for t in s.texts if re.fullmatch(r"\+\d+\s+more", t.strip(), re.I)], (
        f"contador apareceu sem estouro: {s.texts}")


def test_o_contador_mais_N_more_e_inerte(bancada):
    """T37.5: ``+N more`` não é controle e não pode ser um.

    A prova é estrutural: nenhum ANCESTRAL do texto é MouseArea/Button/TapHandler.
    Se o contador fosse clicável, o usuário tentaria usá-lo e nada aconteceria.
    """
    s = dump(bancada, "drawer-6-small")["open"]
    contadores = [n for n in s.nodes
                  if re.fullmatch(r"\+\d+\s+more", n.text.strip(), re.I)]
    assert contadores, f"o caso de controle não tem contador: {s.texts}"
    for no in contadores:
        ancestrais = s.ancestors(no.id)
        culpados = [a.kind for a in ancestrais
                    if re.search(r"MouseArea|AbstractButton|Button|TapHandler|Handler", a.kind)]
        assert not culpados, (
            f"'+N more' está dentro de um controle {culpados} — deixou de ser inerte")
        # E o próprio nó do contador não é interativo.
        assert not no.interactive, "'+N more' foi marcado como nó interativo"


# --------------------------------------------------------------------------- #
# 6. T38 — as três direções, a SETA de retorno e o recolher
# --------------------------------------------------------------------------- #
#
# EMENDA ASSINADA (2026-10-30) — o que mudou de contrato, e o que este arquivo
# faz com as asserções antigas:
#
# | asserção antiga                              | destino                    |
# |----------------------------------------------|----------------------------|
# | "a gaveta é IRMÃ da grade" (topologia)       | ADAPTADA — `Snap.band`     |
# | "lateral que não cabe abre para baixo"       | CANCELADA  (ver abaixo)    |
# | "a queda não reduz o orçamento da grade"     | SUBSTITUÍDA pelos dois     |
# |                                              | negativos assinados        |
# | "botão lateral Collapse fecha a lateral"     | SUBSTITUÍDA pela seta      |
# | "a pílula ``Pill Tau`` continua na grade"    | MANTIDA (ancora a direção) |
#
# Por que as duas famílias foram canceladas em vez de afrouxadas: a emenda
# revoga a queda de lateral para `down` e troca o controle lateral por uma seta.
# Manter aquelas asserções exigiria fixar um desenho que o dono já retirou; e
# afrouxá-las até passarem deixaria testes que não afirmam nada. Os substitutos
# abaixo afirmam o que a emenda ASSINA, e o critério novo de "e quando a lateral
# não cabe?" fica declarado como aberto (LACUNAS, item 18) em vez de inventado
# como oráculo.

def _detalha(s: Snap, marker: str = "TAU ALPHA") -> str:
    """Geometria grade x detalhe, para a mensagem de falha dizer o que se viu."""
    try:
        grade, painel = s.drawer_geometry(marker)
    except AssertionError as exc:
        return f"<sem painel: {exc}>"
    return (
        f"grade(x={grade.x:g} y={grade.y:g} w={grade.w:g} h={grade.h:g}) "
        f"detalhe(x={painel.x:g} y={painel.y:g} w={painel.w:g} h={painel.h:g})")


@pytest.mark.parametrize("direcao", ["down", "left", "right"])
def test_a_gaveta_abre_na_direcao_pedida_medida_por_geometria(bancada, direcao):
    """T38.1 + emenda: a gaveta abre NA DIREÇÃO PEDIDA — medido por geometria.

    O canal é GEOMETRIA, não a string da setting: medir a string não distingue
    ``down`` de ``left`` e foi assim que ``left``/``right`` já passaram como
    settings mortas.

    Leitura da emenda: em ``down`` o detalhe fica ABAIXO e na mesma coluna da
    grade; em ``left``/``right`` ele ocupa a ÁREA LIBERADA de um lado — encosta
    na borda correspondente da grade e não a sobrepõe.

    `widthBudget` = 900 aqui: folgado de propósito, para que uma falha signifique
    "a direção não foi respeitada" e não "faltou espaço".
    """
    caso = "dir-" + direcao
    s = dump(bancada, caso)["open"]

    # Âncora 1 — a setting chegou. Sem isto, a geometria poderia estar medindo
    # o default e o teste passaria pelo motivo errado.
    tipo, valor = s.prop("drawerDirection")
    assert tipo == "string", f"a view não expõe drawerDirection (typeof={tipo})"
    assert valor == direcao, (
        f"a setting drawerDirection={direcao!r} não chegou à view; efetivo={valor!r}")

    # Âncora 2 — o detalhe ABRIU. Sem isto, "não está ao lado" seria verdade
    # porque não há detalhe nenhum.
    assert s.has("TAU ALPHA"), (
        f"{caso}: a gaveta não abriu (conteúdo ausente); {s.texts}")

    # O que o teste existe para afirmar: a direção EFETIVA.
    efetiva = s.direction_of("TAU ALPHA")
    assert efetiva == direcao, (
        f"{caso}: a setting pede {direcao!r} mas a gaveta abriu em {efetiva!r}. "
        f"Geometria: {_detalha(s)}")

    # E a pílula do provider continua na grade: o detalhe não a engoliu.
    assert s.cell_named("Pill Tau") is not None


def test_a_gaveta_nao_abre_sempre_para_baixo(bancada):
    """T38.1 (negativo do defeito do dono): as três direções NÃO colapsam.

    O defeito relatado no shell não era "falta uma direção" — era "todas as
    direções dão no mesmo desenho". Uma igualdade entre as três geometrias
    reprova este teste mesmo que cada uma "abra".

    As três direções compartilham modelo, colunas e orçamento de largura, então
    a única variável é a setting.
    """
    geo = {}
    for direcao in ("down", "left", "right"):
        s = dump(bancada, "dir-" + direcao)["open"]
        assert s.has("TAU ALPHA"), f"dir-{direcao}: a gaveta não abriu — comparação vácua"
        efetiva = s.direction_of("TAU ALPHA")
        assert efetiva == direcao, (
            f"dir-{direcao}: direção efetiva {efetiva!r}; {_detalha(s)}")
        _, painel = s.drawer_geometry("TAU ALPHA")
        geo[direcao] = (round(painel.x, 1), round(painel.y, 1), round(painel.w, 1))

    assert len({v for v in geo.values()}) == 3, (
        f"duas direções desenharam a MESMA geometria — é o defeito 'sempre para "
        f"baixo' (ou 'sempre o mesmo lado'): {geo}")
    # E os três lados são de fato distintos, na leitura humana do contrato.
    # EMENDA T38: a ordenação por `y` entre `down` e as laterais deixou de
    # valer — a lateral vive numa FAIXA com altura reservada, então o painel
    # dela não fica na mesma linha da grade. A distinção que continua sendo
    # contrato é a HORIZONTAL, que é a que o usuário usa para dizer o lado.
    assert geo["left"][0] < geo["right"][0], (
        f"`left` deveria ficar à esquerda de `right`: {geo}")
    assert geo["left"][0] + geo["left"][2] <= geo["down"][0] + 0.75, (
        f"`left` deveria terminar antes de a coluna de `down` começar: {geo}")
    assert geo["right"][0] >= geo["down"][0] + geo["down"][2] - 0.75, (
        f"`right` deveria começar depois de a coluna de `down` terminar: {geo}")


@pytest.mark.parametrize("lado", ["left", "right"])
def test_as_pilulas_e_o_detalhe_nao_se_sobrepoem_na_lateral(bancada, lado):
    """Emenda T38 (asserção CENTRAL): o detalhe ocupa a área LIBERADA.

    O smoke do dono reprovou exatamente a sobreposição da gaveta sobre as
    pílulas. O contrato da emenda é: mantendo a largura do popout, o detalhe
    aparece com suas bordas ao lado da grade, e as pílulas são deslocadas no
    sentido oposto. A prova disponível desta side é a não-sobreposição: o
    retângulo do detalhe termina onde a grade começa (``left``) ou começa onde a
    grade termina (``right``), e ambos têm largura positiva.

    NÃO é provado aqui que as pílulas DENTRO da grade deslizaram: em offscreen
    as células não publicam posição (LACUNAS, item 1). O que se prova é que o
    espaço não é compartilhado — que é o defeito que o dono viu.
    """
    s = dump(bancada, "dir-" + lado)["open"]
    eps = 0.75
    grade, painel = s.drawer_geometry("TAU ALPHA")
    assert grade.w > 0 and painel.w > 0, (
        f"{lado}: detalhe ou grade com largura zero; {_detalha(s)}")
    if lado == "left":
        assert painel.x + painel.w <= grade.x + eps, (
            f"left: o detalhe INVADE a grade (borda direita do detalhe em "
            f"{painel.x + painel.w:g} > início da grade em {grade.x:g}); "
            f"{_detalha(s)}")
        assert painel.x < grade.x, f"left: o detalhe não está à esquerda; {_detalha(s)}"
    else:
        assert painel.x >= grade.x + grade.w - eps, (
            f"right: o detalhe INVADE a grade (início do detalhe em {painel.x:g} "
            f"< fim da grade em {grade.x + grade.w:g}); {_detalha(s)}")
        assert painel.x > grade.x, f"right: o detalhe não está à direita; {_detalha(s)}"


@pytest.mark.parametrize("lado", ["left", "right"])
def test_a_lateral_estreita_nao_desaparece_nem_troca_de_lado(bancada, lado):
    """Emenda T38.3 (EMENDADA): orçamento apertado NÃO pode sumir com a lateral.

    A redação anterior deste teste cobrava a queda para ``down``. A emenda
    assinada em 2026-10-30 revoga essa queda ("sem alterar a largura do popout,
    o detalhe entra pelo lado e as pílulas deslizam no sentido oposto"), então a
    cobrança de ``down`` foi CANCELADA — ver o bloco de cancelamentos no fim
    desta seção. O que continua afirmado, e é contrato literal:

      * a mesma setting ``left``/``right`` abre o detalhe NAS DUAS larguras
        (nem some, nem fica fechada);
      * ela NÃO troca de lado em silêncio (o contrato proíbe explicitamente);
      * ``columns`` não é reduzido como efeito colateral;
      * o detalhe continua encostado na grade pelo lado pedido.

    O que a emenda NÃO resolve — "e quando não cabe de jeito nenhum?" — fica
    registrado como lacuna aberta para o gate, não fixado como oráculo.
    """
    folgado = dump(bancada, "dir-" + lado)["open"]
    estreito = dump(bancada, "estreita-" + lado)["open"]

    for nome, s in (("folgado", folgado), ("estreito", estreito)):
        tipo, valor = s.prop("drawerDirection")
        assert tipo == "string" and valor == lado, (
            f"caso {nome}: a setting deveria ser {lado!r}, veio {valor!r}")
        assert s.has("TAU ALPHA"), (
            f"caso {nome}: o detalhe não abriu — 'não trocou de lado' seria "
            f"vácua; {s.texts}")

    efetiva_estreita = estreito.direction_of("TAU ALPHA")
    assert efetiva_estreita == lado, (
        f"com orçamento apertado o detalhe de {lado!r} abriu em "
        f"{efetiva_estreita!r} — sumiu ou trocou de lado em silêncio; "
        f"{_detalha(estreito)}")

    # Negativo do negativo: não virou o lado oposto.
    assert efetiva_estreita != ("right" if lado == "left" else "left"), (
        f"a lateral {lado!r} trocou de lado em silêncio quando o orçamento apertou")

    cols_folgado, cols_estreito = folgado.prop("columns")[1], estreito.prop("columns")[1]
    assert cols_folgado == cols_estreito == 2, (
        f"o orçamento apertado alterou as colunas: "
        f"folgado={cols_folgado!r}, estreito={cols_estreito!r}")

    # E o detalhe continua encostado na grade pelo lado pedido.
    grade, painel = estreito.drawer_geometry("TAU ALPHA")
    if lado == "left":
        encosta = abs((painel.x + painel.w) - grade.x) <= 0.75
    else:
        encosta = abs(painel.x - (grade.x + grade.w)) <= 0.75
    assert encosta, (
        f"no orçamento apertado o detalhe de {lado!r} deixou de encostar na "
        f"grade; {_detalha(estreito)}")


def test_a_lateral_nao_muda_a_largura_do_popout(bancada):
    """Emenda T38: "sem alterar a largura do popout".

    O controle é o MESMO caso (modelo, colunas, orçamento) com a gaveta ABERTA
    em ``down``: a única variável é a direção. A largura implícita da view tem de
    coincidir com a das duas laterais — e ser estritamente positiva, senão a
    igualdade seria entre dois zeros.
    """
    larguras = {}
    for direcao in ("down", "left", "right"):
        s = dump(bancada, "dir-" + direcao)["open"]
        assert s.has("TAU ALPHA"), f"dir-{direcao}: a gaveta não abriu"
        assert s.iw is not None and s.iw > 0, (
            f"dir-{direcao}: implicitWidth não medido ({s.iw!r}) — a comparação "
            f"seria vácua")
        larguras[direcao] = s.iw
    assert larguras["left"] == larguras["down"] == larguras["right"], (
        f"a direção mudou a largura do popout: {larguras} (a emenda manda manter)")
    # E a largura NÃO é derivada do orçamento: com orçamento apertado a lateral
    # mantém a mesma largura implícita.
    estreito = dump(bancada, "estreita-left")["open"]
    assert estreito.iw == larguras["left"], (
        f"o orçamento mudou a largura do popout: {estreito.iw!r} vs "
        f"{larguras['left']!r}")


@pytest.mark.parametrize("cols", [2, 3, 4])
@pytest.mark.parametrize("lado", ["left", "right"])
def test_a_lateral_abre_nas_tres_contagens_de_coluna(bancada, cols, lado):
    """T38.2: ``left``/``right`` abrem em ``columns`` = 2, 3 e 4.

    A largura do painel entra no orçamento de T33, e o número de colunas muda a
    largura da grade — então a pergunta "a lateral ainda cabe?" depende dos dois.
    Se em alguma contagem a lateral não abrir, o teste FALHA: é informação para o
    gate, não motivo para afrouxar a asserção.

    `widthBudget` = 900 nas três: folgado de propósito, para que a falha seja da
    direção e não do orçamento.
    """
    caso = "lat-%d-%s" % (cols, lado)
    s = dump(bancada, caso)["open"]
    assert s.prop("columns")[1] == cols, (
        f"{caso}: a view resolveu columns={s.prop('columns')[1]!r}, esperado {cols}")
    assert s.has("TAU ALPHA"), (
        f"{caso}: a gaveta não abriu — asserção de direção seria vácua; {s.texts}")
    efetiva = s.direction_of("TAU ALPHA")
    assert efetiva == lado, (
        f"{caso}: com orçamento folgado a gaveta deveria abrir em {lado!r}, "
        f"abriu em {efetiva!r}; {_detalha(s)}")
    # A lateral não pode reduzir as colunas para caber (decisão do dono, T38.3):
    # o valor EFETIVO tem de continuar sendo o pedido.
    assert s.prop("columns")[1] == cols, (
        f"{caso}: a lateral mudou `columns` para {s.prop('columns')[1]!r}")


def test_a_lateral_deixa_o_titulo_dos_secundarios_no_lugar(bancada):
    """Emenda T38: "manter fixo o título 'Other Providers'".

    Fixo significa que ele não se desloca com o detalhe: em ``down`` e nas duas
    laterais o título fica na MESMA faixa da árvore (mesmo ``y``). As três
    direções compartilham modelo, colunas e orçamento, então a única variável é
    a direção.
    """
    posicoes = {}
    for direcao in ("down", "left", "right"):
        s = dump(bancada, "dir-" + direcao)["open"]
        nos = [n for n in s.nodes if "OTHER PROVIDERS" in n.text.upper()]
        assert nos, f"dir-{direcao}: o título dos secundários sumiu; {s.texts}"
        posicoes[direcao] = round(nos[0].y, 1)
    assert len(set(posicoes.values())) == 1, (
        f"o título 'Other Providers' mudou de lugar conforme a direção: {posicoes}")


def test_direcao_invalida_cai_em_down_e_ainda_assim_abre(bancada):
    """T38.2/T40.3: valor inválido é seguro — não pode quebrar a gaveta."""
    valido = dump(bancada, "dir-down")["open"]
    invalido = dump(bancada, "dir-bogus")["open"]
    assert valido.has("TAU ALPHA"), "o caso de controle (down) não abriu a gaveta"
    assert invalido.has("TAU ALPHA"), (
        f"drawerDirection inválido deixou a gaveta sem abrir: {invalido.texts}")
    # Âncora: comparar dois `undefined` daria "igual" sem testar o fallback.
    assert valido.prop("drawerDirection")[0] == "string", (
        "drawerDirection não resolveu no caso de controle")
    assert invalido.prop("drawerDirection")[0] == "string", (
        "drawerDirection inválido não caiu em nenhum valor — não há fallback observável")
    assert invalido.prop("drawerDirection")[1] == valido.prop("drawerDirection")[1], (
        f"valor inválido não caiu no default: "
        f"{invalido.prop('drawerDirection')} vs {valido.prop('drawerDirection')}")
    # E o fallback é o DESENHO de `down`, não só a string.
    assert invalido.direction_of("TAU ALPHA") == "down", (
        f"valor inválido não desenhou a gaveta para baixo: "
        f"{invalido.direction_of('TAU ALPHA')!r}; {_detalha(invalido)}")


# --------------------------------------------------------------------------- #
# 6b. A SETA de retorno (emenda T38) e o recolher em `down` (inalterado)
# --------------------------------------------------------------------------- #

#: Glifo esperado por lado, segundo a emenda: `→` quando as pílulas foram para a
#: DIREITA (o detalhe entrou pela esquerda), `←` quando foram para a ESQUERDA.
#: Um glifo por lado, direto do fixture de casos — não repetido aqui, para não
#: haver duas verdades sobre qual seta corresponde a qual lado.
GLIFO_ESPERADO = GLIFO_DO_LADO


@pytest.mark.parametrize("lado", ["left", "right"])
def test_a_seta_da_ponta_aponta_no_sentido_do_deslocamento(bancada, lado):
    """Emenda T38: a seta diz para onde as pílulas foram.

    ``→`` quando elas foram para a direita (``left``), ``←`` quando foram para a
    esquerda (``right``). Trocar o sentido é o defeito que o usuário sente como
    "o botão mente"; por isso o glifo é comparado ao LADO, não só afirmado
    presente.
    """
    s = dump(bancada, "dir-" + lado)["open"]
    assert s.has("TAU ALPHA"), f"{lado}: o detalhe não abriu; {s.texts}"
    faixa, glifo = s.arrow_strip("TAU ALPHA")
    esperado = GLIFO_ESPERADO[lado]
    assert glifo == esperado, (
        f"{lado}: a seta exibe {glifo!r}, esperado {esperado!r} — o rótulo não "
        f"corresponde ao sentido em que as pílulas foram")
    # Existe UMA seta só: as duas ao mesmo tempo seriam ambíguas.
    outra = Snap.SETA_PILULAS_A_DIREITA if esperado == Snap.SETA_PILULAS_A_ESQUERDA \
        else Snap.SETA_PILULAS_A_ESQUERDA
    assert not s.has(outra), (
        f"{lado}: a árvore mostra as DUAS setas ({esperado!r} e {outra!r})")


@pytest.mark.parametrize("lado", ["left", "right"])
def test_a_seta_fica_na_ponta_do_detalhe(bancada, lado):
    """Emenda T38: o retorno é "uma faixa alta na PONTA do detalhe".

    A ponta é o lado do detalhe que encontra a grade. Uma seta no meio do
    detalhe, ou fora dele, desmente o desenho assinado — e o usuário procura o
    retorno onde ele não está.
    """
    s = dump(bancada, "dir-" + lado)["open"]
    faixa, _ = s.arrow_strip("TAU ALPHA")
    grade, painel = s.drawer_geometry("TAU ALPHA")
    eps = 0.75
    if lado == "left":
        assert abs((faixa.x + faixa.w) - painel.x - painel.w) <= eps, (
            f"left: a seta não está na ponta direita do detalhe "
            f"(seta termina em {faixa.x + faixa.w:g}, detalhe em "
            f"{painel.x + painel.w:g}); {_detalha(s)}")
    else:
        assert abs(faixa.x - painel.x) <= eps, (
            f"right: a seta não está na ponta esquerda do detalhe "
            f"(seta começa em {faixa.x:g}, detalhe em {painel.x:g}); {_detalha(s)}")
    # "Faixa ALTA": a emenda pede uma faixa, não uma setinha solta — o alvo tem
    # de cobrir a altura útil do detalhe.
    assert faixa.h >= 0.5 * painel.h, (
        f"{lado}: a faixa da seta tem altura {faixa.h:g} para um detalhe de "
        f"{painel.h:g} — deixou de ser a faixa alta assinada")


@pytest.mark.parametrize("lado", ["left", "right"])
@pytest.mark.parametrize("tag", ["folgado", "estreito"])
def test_clicar_a_seta_retorna_a_grade(bancada, lado, tag):
    """Emenda T38: clicar a seta RETORNA à grade.

    O caso censa antes (detalhe aberto) e depois do clique no glifo. Exigir que
    ``TAU ALPHA`` saia da árvore e ``openDrawerId`` volte a vazio significa que o
    clique FAZ algo — uma seta decorativa falha aqui.

    Nos dois orçamentos: o retorno não pode depender de a lateral ter "cabido".
    """
    caso = dump(bancada, "seta-%s-%s" % (lado, tag))
    aberto, volta = caso["open"], caso["volta"]
    # Âncoras: havia o que recolher, e o clique de fato foi disparado.
    assert aberto.has("TAU ALPHA"), (
        f"{lado}/{tag}: o detalhe não estava aberto — 'retornou' seria vácuo; "
        f"{aberto.texts}")
    assert aberto.prop("openDrawerId")[1] == "tau", (
        f"{lado}/{tag}: a gaveta não estava aberta em Tau: "
        f"{aberto.prop('openDrawerId')}")
    assert not volta.has("TAU ALPHA"), (
        f"{lado}/{tag}: a seta não recolheu o detalhe; "
        f"{[t for t in volta.texts if t.startswith('TAU')]}")
    assert volta.prop("openDrawerId")[1] == "", (
        f"{lado}/{tag}: openDrawerId não voltou a vazio: "
        f"{volta.prop('openDrawerId')}")
    # O que NÃO deve acontecer: recolher apaga a pílula ou a grade.
    assert volta.cell_named("Pill Tau") is not None, (
        f"{lado}/{tag}: recolher a lateral apagou a pílula do provider")
    assert len(volta.cells()) == len(aberto.cells()), (
        f"{lado}/{tag}: recolher mudou o número de pílulas "
        f"({len(aberto.cells())} -> {len(volta.cells())})")


@pytest.mark.parametrize("lado", ["left", "right"])
@pytest.mark.parametrize("tag", ["folgado", "estreito"])
def test_pilula_visivel_com_a_lateral_aberta_troca_o_provider(bancada, lado, tag):
    """Emenda T38: pílulas que permanecem visíveis (inteiras OU parciais) são
    clicáveis e trocam o provider selecionado.

    O caso abre Tau, depois clica Sigma. A prova é dupla: o detalhe passou a ser
    o de Sigma E o de Tau saiu — a troca não pode "abrir os dois" (o acordeão
    continua valendo) nem deixar o detalhe antigo na tela.
    """
    caso = dump(bancada, "troca-%s-%s" % (lado, tag))
    aberto, troca = caso["open"], caso["troca"]
    assert aberto.prop("openDrawerId")[1] == "tau", (
        f"{lado}/{tag}: o caso não começou com Tau aberto: "
        f"{aberto.prop('openDrawerId')}")
    assert aberto.has("TAU ALPHA"), f"{lado}/{tag}: o detalhe de Tau não abriu"
    assert troca.prop("openDrawerId")[1] == "sigma", (
        f"{lado}/{tag}: clicar a pílula com a lateral aberta não trocou o "
        f"provider; openDrawerId={troca.prop('openDrawerId')!r}")
    assert troca.has("SIGMA CHAT"), (
        f"{lado}/{tag}: o detalhe do provider clicado não apareceu; {troca.texts}")
    assert not troca.has("TAU ALPHA"), (
        f"{lado}/{tag}: o detalhe anterior sobreviveu à troca — duas gavetas ao "
        f"mesmo tempo; {[t for t in troca.texts if t.startswith('TAU')]}")
    # E a grade não foi consumida pela interação.
    assert len(troca.cells()) == len(aberto.cells()), (
        f"{lado}/{tag}: a troca mudou o número de pílulas "
        f"({len(aberto.cells())} -> {len(troca.cells())})")


@pytest.mark.parametrize("tag", ["folgado", "estreito"])
def test_a_seta_nao_aparece_em_down(bancada, tag):
    """Negativo da emenda: em ``down`` NADA das laterais aparece.

    A emenda diz "em ``down``, preservar o comportamento atual da gaveta". Se a
    seta vazasse para a vertical, o desenho assinado como intacto teria mudado.

    Cada orçamento confronta o MESMO orçamento: `folgado` compara a lateral a
    900 com ``dir-down`` (900), e `estreito` compara a lateral a 300 com
    ``estreita-down`` (300). Comparar sempre com o mesmo `down` faria das duas
    parametrizações a mesma asserção.
    """
    lateral = dump(bancada, "seta-left-%s" % tag)["open"]
    down = dump(bancada, "dir-down" if tag == "folgado" else "estreita-down")["open"]

    # Controle positivo: a seta EXISTE na lateral deste orçamento — sem ele, a
    # ausência em `down` seria uma asserção sobre nada.
    assert lateral.has("TAU ALPHA"), f"{tag}: o caso lateral não abriu"
    _, glifo = lateral.arrow_strip("TAU ALPHA")
    assert glifo in Snap.SETAS, f"{tag}: a lateral não mostra seta — controle inválido"
    # E o `down` do mesmo orçamento abriu, senão "não tem seta" seria vácuo.
    assert down.has("TAU ALPHA"), f"{tag}: o caso down não abriu"
    assert down.prop("drawerDirection")[1] == "down", (
        f"{tag}: o controle não está em down: {down.prop('drawerDirection')}")
    for glifo_proibido in Snap.SETAS:
        assert not down.has(glifo_proibido), (
            f"{tag}: o glifo {glifo_proibido!r} da lateral vazou para `down`; "
            f"{down.texts}")


def test_existe_controle_de_recolher_em_down_e_ele_fecha_a_gaveta(bancada):
    """T38.4 (INALTERADO em ``down``): há um controle próprio, e ele fecha.

    O controle é achado por COMPORTAMENTO: a sonda clica cada nó interativo que
    não pertence a uma pílula e censa. Exigir que o detalhe saia da árvore
    significa que o clique faz algo — um "botão" decorativo falha aqui.

    Esta é a versão que sobreviveu: as parametrizações ``left``/``right`` foram
    CANCELADAS porque o controle lateral deixou de ser este botão e passou a ser
    a seta (provada em ``test_clicar_a_seta_retorna_a_grade``). Ver o bloco de
    cancelamentos no fim da seção.
    """
    caso = dump(bancada, "collapse-down")
    aberto = caso["open"]
    # Âncora: `openDrawerId` nomeia o provider aberto. Olhar só o texto "TAU
    # ALPHA" deixaria passar uma view em que a métrica está na LISTA, não na
    # gaveta — e aí "recolher" testaria outra coisa.
    assert aberto.prop("openDrawerId")[1] == "tau", (
        f"down: a gaveta não está aberta em Tau: {aberto.prop('openDrawerId')}")
    assert aberto.has("TAU ALPHA"), (
        f"down: a gaveta não abriu — nada a recolher; {aberto.texts}")
    candidatos = {k: v for k, v in caso.items() if k.startswith("closer")}
    assert candidatos, (
        f"down: a sonda não achou nenhum nó interativo fora das pílulas — "
        f"não existe controle de recolher; {aberto.texts}")
    fecharam = [k for k, v in candidatos.items() if not v.has("TAU ALPHA")]
    assert fecharam, (
        f"down: nenhum dos {len(candidatos)} controles não-pílula fechou a "
        f"gaveta; {[(k, [t for t in v.texts if 'TAU' in t]) for k, v in candidatos.items()]}")
    # O que NÃO deve acontecer: fechar a gaveta não pode apagar a pílula.
    depois = candidatos[fecharam[0]]
    assert depois.has("Pill Tau"), "recolher a gaveta apagou a pílula do provider"


# --------------------------------------------------------------------------- #
# 6c. Altura reservada e corte, que a emenda manda PRESERVAR/ANTECIPAR
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("mh", [160, 320, 480])
def test_a_lateral_reserva_altura_que_nao_depende_do_provider_aberto(bancada, mh):
    """Emenda T38 + esclarecimento do dono: a lateral RESERVA altura, e a reserva
    é a maior altura necessária entre os secundários, limitada pelo teto.

    Testar "faixa == teto" seria errado pelo próprio esclarecimento: a reserva
    não é necessariamente o teto. O que se pode afirmar, e que é o efeito que a
    emenda quer ("evitando redimensionar durante o uso"), é a INVARIÂNCIA: com o
    MESMO teto e o MESMO modelo, abrir o detalhe de um provider de 1 métrica e
    de um de 3 métricas tem de produzir a MESMA altura de faixa. Se a reserva
    fosse a altura do conteúdo, os dois divergiriam e o popout se redimensionaria
    ao trocar de provider — que é exatamente o que a emenda proíbe.

    NÃO se afirma que a reserva é igual ao teto nem que é maior que `down`: o
    esclarecimento pós-assinatura admite que a reserva acompanhe o maior detalhe
    disponível e que uma atualização do relatório a altere.
    """
    for lado in ("left", "right"):
        alturas = {}
        for tag, marcador in (("tau", "TAU ALPHA"), ("sigma", "SIGMA CHAT")):
            s = dump(bancada, "reserva-%d-%s-%s" % (mh, lado, tag))["open"]
            # Âncora: o detalhe DAQUELE provider está aberto — senão a altura
            # medida seria a de uma faixa qualquer.
            assert s.has(marcador), (
                f"{lado}/{mh}/{tag}: o detalhe de {tag} não abriu; {s.texts}")
            teto = s.prop("drawerMaxHeight")[1]
            assert isinstance(teto, (int, float)) and teto > 0, (
                f"{lado}/{mh}/{tag}: drawerMaxHeight não resolveu ({teto!r})")
            faixa = s.band(marcador)
            assert faixa.h <= float(teto) + 0.75, (
                f"{lado}/{mh}/{tag}: a faixa reservou {faixa.h:g}, acima do teto "
                f"{teto:g} — a reserva ignorou o limite")
            alturas[tag] = round(faixa.h, 1)
        assert alturas["tau"] == alturas["sigma"], (
            f"{lado}/{mh}: a altura reservada depende do provider aberto "
            f"(Tau com 3 métricas = {alturas['tau']:g}, Sigma com 1 = "
            f"{alturas['sigma']:g}) — o popout redimensionaria ao trocar de "
            f"provider, que é o que a emenda manda evitar")


def test_down_preserva_a_altura_do_conteudo_e_nao_reserva(bancada):
    """Emenda T38: "em ``down``, preservar o comportamento atual da gaveta".

    O comportamento preservado é o de T37: ``down`` cresce com o CONTEÚDO, não
    com o teto. A âncora é que o mesmo modelo com três tetos diferentes desenha a
    MESMA altura de faixa — se a reserva das laterais tivesse vazado para a
    vertical, os três valores divergiriam.
    """
    alturas = {}
    for teto in (160, 320, 480):
        s = dump(bancada, "altura-%d-down" % teto)["open"]
        assert s.has("TAU ALPHA"), f"down/{teto}: a gaveta não abriu; {s.texts}"
        assert s.prop("drawerMaxHeight")[1] == teto, (
            f"down/{teto}: a setting não chegou à view "
            f"({s.prop('drawerMaxHeight')!r})")
        alturas[teto] = round(s.band("TAU ALPHA").h, 1)
    assert len(set(alturas.values())) == 1, (
        f"em `down` a altura da faixa mudou com o TETO, o que é a reserva "
        f"lateral vazando para a vertical: {alturas}")
    # E a faixa de `down` não é a área reservada: o conteúdo de 3 métricas cabe
    # em muito menos que o menor teto.
    assert alturas[160] < 160, (
        f"em `down` a faixa ocupa o teto inteiro ({alturas[160]:g}) — passou a "
        f"reservar como nas laterais")


@pytest.mark.parametrize("lado", ["left", "right"])
def test_a_lateral_preserva_o_corte_mais_N_more(bancada, lado):
    """Emenda T38 manda PRESERVAR teto e ``+N more`` — inclusive na lateral.

    A conta é a mesma de T37.3: o número anunciado tem de ser igual ao de
    métricas NÃO desenhadas. Um contador que mentisse seria pior que o corte,
    porque o host recorta o excesso em silêncio.
    """
    s = dump(bancada, "corte-" + lado)["open"]
    rotulos = ["OMEGA M%d" % i for i in range(1, 7)]
    desenhadas = [r for r in rotulos if s.has(r)]
    assert desenhadas, f"{lado}: a lateral não desenhou NENHUMA métrica"
    assert len(desenhadas) < 6, (
        f"{lado}: com teto pequeno as 6 métricas couberam — o corte não foi "
        f"exercitado; {s.texts}")
    contadores = [t for t in s.texts if re.fullmatch(r"\+\d+\s+more", t.strip(), re.I)]
    assert contadores, f"{lado}: a lateral cortada não anuncia '+N more': {s.texts}"
    numero = int(re.search(r"\d+", contadores[0]).group())
    assert numero == 6 - len(desenhadas), (
        f"{lado}: o contador diz {numero} omitidas, mas {6 - len(desenhadas)} "
        f"foram omitidas (desenhadas: {desenhadas})")
    # O corte não é desculpa para sumir com o detalhe nem com a grade.
    assert s.prop("openDrawerId")[1] == "omega", (
        f"{lado}: o detalhe não está aberto em Omega: {s.prop('openDrawerId')}")
    assert s.cell_named("Pill Omega") is not None, (
        f"{lado}: a pílula de Omega sumiu com o detalhe aberto")


# --------------------------------------------------------------------------- #
# 6d. CANCELAMENTOS EXPLÍCITOS (emenda T38, 2026-10-30)
# --------------------------------------------------------------------------- #
#
# As três asserções abaixo foram CANCELADAS porque a emenda assinada revogou o
# desenho que elas fixavam. Elas ficam no arquivo (em vez de apagadas) para que o
# gate veja o que deixou de ser cobrado e por quê — teste apagado some do diff, e
# então "cobertura de T38" passaria a significar outra coisa sem ninguém notar.
#
# Repostas, em ordem:
#   1. queda para `down` em `left`/`right` -> test_a_lateral_estreita_nao_desaparece_nem_troca_de_lado
#   2. largura da grade na queda            -> test_a_lateral_nao_muda_a_largura_do_popout
#   3. botão "Collapse" na lateral          -> test_a_seta_da_ponta_aponta_no_sentido_do_deslocamento
#                                              + test_clicar_a_seta_retorna_a_grade
#
# O que NÃO foi cancelado e continua valendo: `down` inteiro (abre abaixo, na
# largura da grade, com botão próprio no rodapé), as três direções, o fallback de
# setting inválida, a abertura da lateral em 2/3/4 colunas, o teto e o `+N more`.

CANCELAMENTOS_T38 = """
Cancelado (emenda T38, 2026-10-30): "a lateral que não cabe abre para baixo".
  A emenda assinada revoga a queda: em `left`/`right` o detalhe ocupa a área
  liberada e as pílulas deslizam no sentido oposto, sem alterar a largura do
  popout. Cobrar `down` aqui seria cobrar o desenho retirado pelo dono.
  Substituto: `test_a_lateral_estreita_nao_desaparece_nem_troca_de_lado` (a
  lateral continua abrindo, do mesmo lado, sem reduzir colunas).
  EM ABERTO para o gate: o critério de fallback lateral quando o orçamento não
  comporta o detalhe de jeito nenhum. Ver LACUNAS_DE_OBSERVACAO item 18.

Cancelado (emenda T38, 2026-10-30): "a queda para baixo não reduz o orçamento
  da grade". A asserção era condicional a uma queda que não existe mais.
  Substituto: `test_a_lateral_nao_muda_a_largura_do_popout`, que afirma os dois
  invariantes assinados — largura do popout e colunas não mudam — comparando
  lateral contra lateral e lateral contra o controle `down`.

Cancelado (emenda T38, 2026-10-30): "existe botão de recolher em left/right e
  ele fecha a gaveta" (o botão rotulado "Collapse" na ponta do lado expandido).
  A emenda substitui esse botão pela SETA (`→`/`←`).
  Substitutos: `test_a_seta_da_ponta_aponta_no_sentido_do_deslocamento`,
  `test_a_seta_fica_na_ponta_do_detalhe` e
  `test_clicar_a_seta_retorna_a_grade` (folgado e estreito).
  A versão de `down` do mesmo teste FOI MANTIDA sem afrouxamento.
"""


#: Uma entrada por asserção retirada, com o trecho literal que a identifica no
#: bloco acima e o nome do teste que a substitui.
CANCELADAS = [
    ("a lateral que não cabe abre para baixo",
     "test_a_lateral_estreita_nao_desaparece_nem_troca_de_lado"),
    ("a queda para baixo não reduz o orçamento",
     "test_a_lateral_nao_muda_a_largura_do_popout"),
    ('existe botão de recolher em left/right',
     "test_clicar_a_seta_retorna_a_grade"),
]


@pytest.mark.parametrize("retirada,substituto", CANCELADAS)
def test_cancelamento_esta_documentado(retirada, substituto):
    """Toda asserção cancelada tem de estar NOMEADA, e com substituto EXISTENTE.

    Teste de documentação, de propósito: o risco desta emenda não é o código,
    é a cobertura encolher em silêncio. Ele exige três coisas — o cancelamento
    nomeado no bloco, o nome do teste substituto ali, e o substituto realmente
    existindo neste módulo. Um substituto que fosse só promessa passaria na
    primeira e falharia na terceira.
    """
    assert retirada in CANCELAMENTOS_T38, (
        f"o cancelamento {retirada!r} não está documentado — cobertura de T38 "
        f"teria encolhido sem registro")
    assert substituto in CANCELAMENTOS_T38, (
        f"o cancelamento {retirada!r} não nomeia o substituto {substituto!r}")
    assert callable(globals().get(substituto)), (
        f"o substituto declarado {substituto!r} não existe neste módulo — o "
        f"cancelamento estaria sem cobertura")


# --------------------------------------------------------------------------- #
# 7. T39 — identidade: acordeão e toggle
# --------------------------------------------------------------------------- #

def test_abrir_um_segundo_secundario_fecha_o_primeiro_acordeao(bancada):
    """T39/D3: uma gaveta por vez. Abrir B fecha A — as métricas de A saem."""
    caso = dump(bancada, "drawer-accordion")
    tau = caso["tau"]
    dois = caso["tau2"]
    assert tau.prop("openDrawerId")[1] == "tau", (
        f"a primeira gaveta não abriu em Tau: {tau.prop('openDrawerId')}")
    assert tau.has("TAU ALPHA"), f"a primeira gaveta não abriu: {tau.texts}"
    assert dois.prop("openDrawerId")[1] == "sigma", (
        f"a segunda gaveta não abriu em Sigma: {dois.prop('openDrawerId')}")
    assert dois.has("SIGMA CHAT"), (
        f"a segunda gaveta não abriu — o acordeão não foi exercitado: {dois.texts}")
    assert not dois.has("TAU ALPHA"), (
        f"as métricas de A sobreviveram à abertura de B (acordeão quebrado): "
        f"{[t for t in dois.texts if t.startswith('TAU')]}")


def test_dois_cliques_na_mesma_pilula_fecham_a_gaveta(bancada):
    """T39/T38: o clique na pílula é toggle.

    Âncora: o estado do meio tem de estar ABERTO — senão "fechou" seria verdade
    porque nunca abriu. E o terceiro estado não pode ser uma gaveta vazia que
    ainda expõe o plano (o detalhe volta a não estar na árvore).
    """
    caso = dump(bancada, "drawer-toggle")
    antes, aberto, depois = caso["before"], caso["opened"], caso["reclosed"]
    assert not antes.has("TAU ALPHA"), "o caso começou com a gaveta aberta"
    assert aberto.has("TAU ALPHA"), (
        f"o primeiro clique não abriu a gaveta: {aberto.texts}")
    assert not depois.has("TAU ALPHA"), (
        f"o segundo clique não fechou a gaveta: {[t for t in depois.texts if 'TAU' in t]}")
    assert depois.prop("openDrawerId")[1] == "", (
        f"openDrawerId não voltou a vazio: {depois.prop('openDrawerId')}")
    # E a pílula continua lá, clicável de novo.
    assert depois.cell_named("Pill Tau") is not None


# --------------------------------------------------------------------------- #
# SEGUNDA PASSADA (T42b) — (i) o modelo do serviço não é mutado
# --------------------------------------------------------------------------- #
#
# A sonda serializa `service.model` ANTES de a view montar ("mount") e depois de
# cada interação. A comparação é feita em dois níveis, de propósito:
#   * TEXTO — ``JSON.stringify`` do modelo inteiro. Pega remoção, inserção,
#     reordenação e troca de tipo, inclusive dentro de um array de métricas.
#   * ESTRUTURA — (id, [labels]) por provider, para que a falha DIGA qual
#     provider e qual lista mudaram, em vez de despejar 4 kB de JSON.

def _assinatura(fp: str) -> dict:
    """(id, [labels]) do primário e de cada secundário, na ordem do modelo."""
    m = json.loads(fp)
    def um(p):
        if p is None:
            return ("<sem-primario>", [])
        return (p.get("id"), [x.get("label") for x in (p.get("metrics") or [])])
    return {
        "primary": um(m.get("primary")),
        "secondary": [um(p) for p in (m.get("secondary") or [])],
        "all": [um(p) for p in (m.get("all") or [])],
    }


def _fase_modelo(bancada, caso: str) -> dict:
    fps = models(bancada, caso)
    assert "m-pre" in fps, (
        f"{caso}: a sonda não fotografou o modelo antes das interações; "
        f"fases={sorted(fps)}")
    return fps


def test_o_modelo_do_servico_nao_muda_ao_montar_a_view(bancada):
    """(i) O PRIMEIRO render não pode mexer no modelo do serviço.

    "mount" é impresso ANTES de o Loader carregar a view; "pre" é impresso
    depois do primeiro desenho. Comparar os dois isola o efeito de MONTAR — o
    momento em que uma view que "prepara" as métricas para a pílula as apagaria.
    """
    fps = _fase_modelo(bancada, "b-mut")
    assert "mount" in fps, f"a sonda não fotografou o modelo no mount; {sorted(fps)}"
    antes, depois = _assinatura(fps["mount"]), _assinatura(fps["m-pre"])
    assert len(depois["secondary"]) == 2, (
        f"o fixture deveria ter 2 secundários; a asserção seria vácua: {depois}")
    assert antes == depois, (
        f"montar a view mudou o modelo.\n  antes={antes}\n  depois={depois}")
    assert fps["mount"] == fps["m-pre"], (
        "o JSON do modelo mudou entre o mount e o primeiro desenho (remoção, "
        "inserção, reordenação ou troca de tipo em algum nível)")
    # O primário tem SEIS métricas: é o candidato natural a "esconder o que não
    # couber", então a contagem dele é afirmada explicitamente.
    assert depois["primary"][1] == ["Vet A%d" % i for i in range(1, 7)], (
        f"as métricas do primário não estão inteiras/na ordem: {depois['primary']}")


def test_consultar_a_gaveta_nao_muta_nem_reordena_o_modelo(bancada):
    """(i) Abrir, alternar (toggle) e trocar de gaveta (acordeão) não alteram
    o modelo — nem o primário, nem secundário algum.

    O caso usa ``drawerMaxHeight: 110``: a gaveta CORTA o que não couber (o
    ``+N more`` do caso aparece). É exatamente aí que "esvaziar as métricas
    ocultas para desenhar menos" destruiria o dado — e o dano só apareceria no
    poll seguinte, ou ao abrir outra gaveta. A ordem das fases do caso é:
    fechada -> Omega aberta -> Omega fechada (toggle) -> Work aberta (acordeão).
    """
    fps = _fase_modelo(bancada, "b-mut")
    fases = ["m-omega-aberta", "m-omega-fechada", "m-work-aberta", "m-fim"]
    faltando = [f for f in fases if f not in fps]
    assert not faltando, f"a sonda não fotografou as fases {faltando}; tem {sorted(fps)}"

    base = _assinatura(fps["m-pre"])
    assert len(base["secondary"]) == 2 and len(base["primary"][1]) == 6, (
        f"fixture inesperado — a comparação seria vácua: {base}")
    esperado = {
        "vet": ["Vet A%d" % i for i in range(1, 7)],
        "omega": ["Omega M%d" % i for i in range(1, 7)],
        "openai@work": ["Work Alpha", "Work Beta"],
    }
    for fase in fases:
        atual = _assinatura(fps[fase])
        for campo in ("primary", "secondary", "all"):
            assert atual[campo] == base[campo], (
                f"[{fase}] o modelo do serviço mudou em `{campo}` ao consultar a "
                f"view.\n  antes={base[campo]}\n  agora={atual[campo]}")
        # Controle positivo: os rótulos do fixture continuam sendo os do fixture.
        for pid, labels in esperado.items():
            achado = [x for x in atual["all"] if x[0] == pid]
            assert achado == [(pid, labels)], (
                f"[{fase}] as métricas de {pid!r} deixaram de ser {labels}: {achado}")

    # Ancoragem de que as interações ACONTECERAM: sem isso, "não mutou" seria
    # verdade só porque nenhuma gaveta abriu.
    caso = dump(bancada, "b-mut")
    assert caso["omega-aberta"].has("OMEGA M1"), "a gaveta de Omega não abriu — fase vácua"
    assert not caso["omega-fechada"].has("OMEGA M1"), "o toggle não fechou a gaveta"
    assert caso["work-aberta"].has("WORK ALPHA"), "a gaveta de Work não abriu — fase vácua"
    assert not caso["work-aberta"].has("OMEGA M1"), (
        "o acordeão não fechou Omega — a fase 'work-aberta' não exercitou a troca")
    # E a gaveta cortou: o "esconder o que não couber" é o defeito sob teste.
    assert any(re.fullmatch(r"\+\d+\s+more", t.strip(), re.I)
               for t in caso["omega-aberta"].texts), (
        f"o teto pequeno não cortou a gaveta — a fase mais perigosa não foi "
        f"exercitada: {caso['omega-aberta'].texts}")


def test_abrir_a_gaveta_de_um_secundario_nao_toca_nas_metricas_dos_outros(bancada):
    """(i) Isolamento: a lista do PRIMÁRIO e a do OUTRO secundário sobrevivem
    intactas à abertura de uma gaveta.

    Este é o negativo do defeito mais danoso: uma implementação que filtrasse
    ``provider.metrics`` para desenhar a pílula de um provider poderia destruir
    a lista de todos ao mesmo tempo. A âncora é que a gaveta ABRIU.
    """
    caso = dump(bancada, "b-mut")
    assert caso["work-aberta"].has("WORK ALPHA"), (
        "a gaveta de Work não abriu — asserção vácua")
    fps = _fase_modelo(bancada, "b-mut")
    pre, depois = _assinatura(fps["m-pre"]), _assinatura(fps["m-work-aberta"])
    por_id = lambda a: {x[0]: x[1] for x in a["all"]}
    antes, agora = por_id(pre), por_id(depois)
    for pid, labels in antes.items():
        assert agora.get(pid) == labels, (
            f"abrir a gaveta de 'openai@work' mexeu nas métricas de {pid!r}: "
            f"antes={labels}, agora={agora.get(pid)}")
    assert pre["primary"] == depois["primary"], (
        f"abrir a gaveta de um secundário mudou o PRIMÁRIO: "
        f"{pre['primary']} -> {depois['primary']}")
    assert [x[0] for x in depois["secondary"]] == [x[0] for x in pre["secondary"]], (
        f"a ORDEM dos secundários mudou: {pre['secondary']} -> {depois['secondary']}")


# --------------------------------------------------------------------------- #
# SEGUNDA PASSADA (T42b) — (ii) a gaveta x poll
# --------------------------------------------------------------------------- #

def test_a_gaveta_do_mesmo_provider_continua_aberta_depois_do_poll(bancada):
    """(ii.1) Um poll troca o ``model`` INTEIRO (objetos novos, mesmos ids).

    A gaveta do mesmo provider tem de continuar aberta: sem isso, um poll de
    300s fecharia a gaveta de quem está lendo. A identidade é o id, não a
    posição nem a referência do objeto.
    """
    caso = dump(bancada, "b-poll-mesmo")
    antes, depois = caso["aberta"], caso["depois"]
    assert antes.has("WORK ALPHA"), f"a gaveta não abriu antes do poll: {antes.texts}"
    assert depois.has("WORK ZETA"), (
        f"a gaveta fechou no poll do MESMO provider — quem está lendo perde o "
        f"lugar a cada 300s; {depois.texts}")
    # Ancoragem: o poll de fato aconteceu e o provider continua na grade.
    assert depois.cell_named("Pill Work") is not None, (
        f"o provider sumiu da grade — o poll não foi o caso esperado: {depois.texts}")
    assert depois.has("OTHER PROVIDERS"), (
        f"a seção de secundários não foi desenhada após o poll: {depois.texts}")


def test_a_gaveta_rele_o_modelo_novo_depois_do_poll(bancada):
    """(ii.1, leitura ESTRITA) Depois do poll a gaveta mostra os dados NOVOS.

    Uma gaveta que guardasse o OBJETO antigo continuaria "aberta" exibindo
    números velhos — pior que fechar, porque o usuário não vê que envelheceu.
    Medido nesta base: os rótulos novos substituem os velhos. Registrado como
    leitura mais exigente do mesmo contrato.
    """
    caso = dump(bancada, "b-poll-mesmo")
    depois = caso["depois"]
    assert depois.has("WORK ZETA") and depois.has("WORK ETA"), (
        f"a gaveta não releu as métricas do modelo novo: {depois.texts}")
    assert not depois.has("WORK ALPHA"), (
        f"a gaveta ainda exibe o rótulo do modelo ANTERIOR ao poll: {depois.texts}")


def _mesmo_que_montagem_fresca(bancada, caso: str, controle: str, marcador: str,
                               marcador_controle: str = None):
    """Prova que o estado pós-poll é IDÊNTICO a montar a view com o modelo novo.

    Comparar o MULTICONJUNTO de textos é o oráculo mais forte disponível: cobre
    "a gaveta está fechada", "nada do ocupante anterior ficou" e "nada do novo
    ocupante vazou" de uma vez — sem consultar propriedade privada alguma.

    Vacuidade é controlada em três pontos, porque uma igualdade entre duas
    árvores vazias também passaria:
      1. ANTES do poll a gaveta estava ABERTA (``marcador`` presente);
      2. a montagem fresca é não vazia;
      3. o estado de referência não contém o detalhe de gaveta. Quando o
         provider promovido a primário passa a desenhar as métricas como
         primário, ``marcador_controle`` troca o rótulo por um marcador que só
         existe DENTRO de uma gaveta aberta ("Collapse") — assim a comparação
         continua exigente em vez de ser afrouxada.
    """
    depois = sorted(dump(bancada, caso)["depois"].texts)
    fresca = sorted(dump(bancada, controle)["fresca"].texts)
    assert fresca, f"{controle}: a montagem de controle está VAZIA — igualdade vácua"
    assert dump(bancada, caso)["aberta"].has(marcador), (
        f"{caso}: a gaveta não estava aberta antes do poll — asserção vácua")
    proibido = marcador_controle or marcador
    assert proibido not in fresca, (
        f"{controle}: o controle não deveria conter o detalhe de {proibido!r}")
    assert depois != sorted(dump(bancada, caso)["aberta"].texts), (
        f"{caso}: o estado depois do poll é idêntico ao de ANTES — o poll não "
        f"foi aplicado e a comparação seria vácua")
    assert depois == fresca, (
        f"{caso}: o estado depois do poll difere de uma montagem fresca do mesmo "
        f"modelo.\n  só no pós-poll: {[t for t in depois if t not in fresca]}\n"
        f"  só na fresca:   {[t for t in fresca if t not in depois]}")


def test_o_novo_ocupante_da_celula_nao_herda_a_gaveta(bancada):
    """(ii.2) Provider aberto SAI, outro entra na MESMA posição do grid.

    A gaveta tem de estar FECHADA: mostrar os números do novo ocupante porque
    ele caiu no mesmo índice seria vazar dado de um provider sob o nome de
    outro. O oráculo é a igualdade com uma montagem fresca do modelo novo.
    """
    _mesmo_que_montagem_fresca(bancada, "b-poll-ocupante", "b-ctl-ocupante",
                               "WORK ALPHA")
    depois = dump(bancada, "b-poll-ocupante")["depois"]
    assert depois.cell_named("Pill Eps") is not None, (
        f"o novo ocupante não entrou na célula — o caso não foi exercitado: {depois.texts}")
    assert not depois.has("EPS ALPHA"), (
        f"o novo ocupante ABRIU com a gaveta herdada: {depois.texts}")


def test_o_provider_promovido_a_primario_nao_leva_a_gaveta(bancada):
    """(ii.2) O provider aberto VIROU PRIMÁRIO: a gaveta de secundário morre.

    O primário desenha as métricas sem clique por outro caminho (T36.2); uma
    gaveta de secundário apontando para ele duplicaria o detalhe.
    """
    _mesmo_que_montagem_fresca(bancada, "b-poll-primario", "b-ctl-primario",
                               "WORK ALPHA", marcador_controle="Collapse")
    depois = dump(bancada, "b-poll-primario")["depois"]
    # O promovido desenha as métricas como PRIMÁRIO (T36.2) — isso é correto.
    assert depois.has("WORK ZETA") and depois.has("WORK ETA"), (
        f"o promovido a primário não desenhou as próprias métricas: {depois.texts}")
    # O que NÃO pode existir é a GAVETA de secundário apontando para ele. O
    # controle "Collapse" só existe dentro de uma gaveta aberta (medido nos
    # casos de gaveta desta suíte); a montagem fresca não o tem.
    assert not depois.has("Collapse"), (
        f"sobrou o controle da gaveta de secundário no provider promovido: "
        f"{depois.texts}")
    assert depois.has("OTHER PROVIDERS"), (
        f"a seção de secundários não foi redesenhada: {depois.texts}")


def test_desligar_show_secondaries_fecha_a_gaveta_sem_deixar_detalhe(bancada):
    """(ii.2) O provider aberto sai por ``showSecondaries: false``.

    Com a seção inteira escondida, nenhum detalhe de secundário pode restar na
    árvore — nem o do provider que estava aberto. A igualdade com a montagem
    fresca cobre também o primário (que tem de continuar intacto).
    """
    _mesmo_que_montagem_fresca(bancada, "b-poll-setting", "b-ctl-setting",
                               "WORK ALPHA")
    depois = dump(bancada, "b-poll-setting")["depois"]
    assert len(depois.cells()) == 0, (
        f"showSecondaries=false ainda desenhou pílulas: "
        f"{[depois.pill_texts(c) for c in depois.cells()]}")
    assert depois.has("Vet A1"), (
        f"desligar os secundários apagou o primário: {depois.texts}")


def test_o_provider_que_sai_por_teto_nao_deixa_detalhe(bancada):
    """(ii.2) O provider aberto sai de ``secondary`` porque ``maxSecondary``
    encolheu (ele continua em ``model.all``).

    Este é o caminho mais traiçoeiro: o provider EXISTE no modelo, então uma
    gaveta guardada por id continuaria "válida" — mas ele não tem mais célula.
    Nenhum detalhe dele pode estar na árvore.
    """
    _mesmo_que_montagem_fresca(bancada, "b-poll-teto", "b-ctl-teto", "WORK ALPHA")
    depois = dump(bancada, "b-poll-teto")["depois"]
    assert not depois.has("WORK ZETA"), (
        f"o provider fora do teto ainda desenha detalhe: {depois.texts}")
    assert depois.cell_named("Pill Delta") is not None, (
        f"o sobrevivente do teto não está na grade — caso não exercitado: {depois.texts}")


def test_remontar_a_surface_fecha_a_gaveta(bancada):
    """(ii.3a) Remontar a view é a aproximação observável de "reabrir o popout".

    A view é destruída e recriada com o MESMO ``pluginApi`` (mesma instância de
    serviço, mesmo modelo). Se a gaveta voltasse aberta, o estado teria sido
    gravado em algum lugar — o oposto de volátil.
    """
    _mesmo_que_montagem_fresca(bancada, "b-remontar", "b-ctl-remontar", "WORK ALPHA")
    depois = dump(bancada, "b-remontar")["depois"]
    assert not depois.has("WORK ZETA"), (
        f"a gaveta sobreviveu à remontagem da surface: {depois.texts}")
    assert depois.cell_named("Pill Work") is not None, (
        f"a pílula não voltou depois de remontar: {depois.texts}")


def test_a_sequencia_abrir_fechar_remontar_nao_grava_setting(bancada):
    """(ii.3b) Reforço sobre R5: abrir, fechar e remontar não persistem nada.

    ``saveSetting`` é o único caminho de escrita declarado. O controle de
    vacuidade é global (o caso ``primary-all`` dispara o gancho de propósito e
    ``SAVE_PROBE_OK|1`` prova que ele funciona); aqui se afirma que NENHUM censo
    de caso de poll/remontagem registrou uma chave.
    """
    assert "SAVE_PROBE_OK|1" in bancada["raw"], (
        "o gancho sintético de saveSetting não responde — a ausência de gravação "
        "seria falsa")
    for caso in ("b-poll-mesmo", "b-poll-ocupante", "b-poll-primario",
                 "b-poll-setting", "b-poll-teto", "b-remontar", "b-contas",
                 "b-mut", "b-uma-n3", "b-uma-n1"):
        for nome, s in dump(bancada, caso).items():
            assert s.saves == [], (
                f"{caso}/{nome}: a view gravou settings {s.saves!r} numa sequência "
                f"de gaveta/poll/remontagem — o estado deveria ser VOLÁTIL")
    # E o caso de controle de gaveta aberta também não gravou (não é só o poll).
    aberto = dump(bancada, "b-poll-mesmo")["aberta"]
    assert aberto.has("WORK ALPHA") and aberto.saves == [], (
        f"abrir a gaveta gravou {aberto.saves!r}")


# --------------------------------------------------------------------------- #
# SEGUNDA PASSADA (T42b) — (ii) identidade pelo id COMPLETO
# --------------------------------------------------------------------------- #

def test_a_identidade_da_gaveta_e_o_id_completo_incluindo_a_conta(bancada):
    """(ii) ``openai@work`` e ``openai`` no MESMO modelo são providers distintos.

    Este é o caso que separa "id completo" de "vendor": se a gaveta fosse
    indexada só pelo vendor, abrir uma conta abriria a outra. As métricas dos
    dois têm rótulos exclusivos, então o conteúdo diz QUAL abriu.
    """
    caso = dump(bancada, "b-contas")
    fechada, work, home = caso["fechada"], caso["aberta-work"], caso["aberta-home"]
    # Âncoras: o modelo foi montado com os DOIS providers do mesmo vendor.
    assert fechada.cell_named("Pill Work") is not None
    assert fechada.cell_named("Pill Home") is not None
    assert not fechada.has("WORK ALPHA") and not fechada.has("HOME ALPHA"), (
        f"o caso começou com gaveta aberta: {fechada.texts}")

    assert work.has("WORK ALPHA") and work.has("WORK BETA"), (
        f"abrir a conta @work não expôs as métricas dela: {work.texts}")
    assert not work.has("HOME ALPHA"), (
        f"abrir 'openai@work' abriu TAMBÉM 'openai' — a identidade é o vendor, "
        f"não o id completo: {work.texts}")

    assert home.has("HOME ALPHA") and home.has("HOME BETA"), (
        f"abrir a conta sem sufixo não expôs as métricas dela: {home.texts}")
    assert not home.has("WORK ALPHA"), (
        f"as duas contas ficaram abertas ao mesmo tempo (ou a errada): {home.texts}")


# --------------------------------------------------------------------------- #
# SEGUNDA PASSADA (T42b) — (iii) no máximo UMA gaveta aberta, em números
# --------------------------------------------------------------------------- #

#: Rótulos que existem SÓ na gaveta do provider (a pílula desenha o nome e o
#: percentual da métrica líder, nunca o rótulo). Contar quantos estão na árvore
#: conta gavetas abertas SEM consultar nome de propriedade privada.
DETALHES = {"Pill Beta": "BETA ALPHA", "Pill Delta": "DELTA ALPHA",
            "Pill Eps": "EPS ALPHA"}


def _gavetas_abertas(s: Snap) -> list[str]:
    return [nome for nome, marca in DETALHES.items() if s.has(marca)]


def test_com_tres_secundarios_ha_sempre_exatamente_uma_gaveta_aberta(bancada):
    """(iii) Versão NUMÉRICA do acordeão: nunca 0 depois de abrir, nunca 2.

    Depois de abrir a gaveta de cada um de três secundários em sequência, o
    número de gavetas abertas é SEMPRE exatamente 1, e é a do provider clicado.
    A contagem é feita pelos rótulos de detalhe (ver ``DETALHES``), não por
    ``openDrawerId``.
    """
    caso = dump(bancada, "b-uma-n3")
    fechada = caso["fechada"]
    # Âncora: os três secundários existem como pílula e nenhum detalhe está
    # visível antes de qualquer clique.
    for nome in DETALHES:
        assert fechada.cell_named(nome) is not None, (
            f"{nome} não está na grade — a contagem seria vácua: {fechada.texts}")
    assert _gavetas_abertas(fechada) == [], (
        f"gaveta aberta antes de qualquer clique: {_gavetas_abertas(fechada)}")

    for fase, esperada in (("b", "Pill Beta"), ("d", "Pill Delta"), ("e", "Pill Eps")):
        s = caso[fase]
        abertas = _gavetas_abertas(s)
        assert len(abertas) == 1, (
            f"[{fase}] {len(abertas)} gavetas abertas ({abertas}); o contrato é "
            f"exatamente 1. Árvore: {s.texts}")
        assert abertas == [esperada], (
            f"[{fase}] abriu {abertas}, esperava só {esperada}")


def test_com_um_secundario_a_unica_gaveta_abre(bancada):
    """(iii) N=1: abrir a única gaveta abre UMA — nem 0, nem 2.

    Sem este caso, "no máximo uma" passaria com uma view que nunca abre nada.
    """
    caso = dump(bancada, "b-uma-n1")
    fechada, aberta = caso["fechada"], caso["b"]
    assert fechada.cell_named("Pill Beta") is not None, (
        f"o único secundário não está na grade: {fechada.texts}")
    assert len(fechada.cells()) == 1, (
        f"o caso deveria ter exatamente 1 secundário; tem {len(fechada.cells())}")
    assert _gavetas_abertas(fechada) == [], "o caso começou com gaveta aberta"
    abertas = _gavetas_abertas(aberta)
    assert len(abertas) == 1, (
        f"N=1: {len(abertas)} gavetas abertas ({abertas}); o esperado é 1. "
        f"Árvore: {aberta.texts}")
    assert abertas == ["Pill Beta"], f"N=1 abriu a gaveta errada: {abertas}"


# --------------------------------------------------------------------------- #
# Lacunas de observação (honestidade D5 — o que esta suíte NÃO prova)
# --------------------------------------------------------------------------- #

LACUNAS_DE_OBSERVACAO = """
1. ORDEM DE LEITURA por coordenada: em QT_QPA_PLATFORM=offscreen as posições não
   resolvem (toda pílula sai em x=12, y=10). A ordem é provada pela ordem de
   INSERÇÃO na QQuickGrid (ordem da árvore), não por (x, y). É equivalente para
   uma grade preenchida por linha, mas NÃO prova que a view usa Grid em vez de
   Row — só que a sequência desenhada é a do modelo. A armadilha "Row não
   reflui quando um filho muda visible" (T35.2) fica fora desta suíte.
2. TETO EM PIXELS da gaveta: o corte é observado em TEXTO (+N more com o número
   correto), o que cobre o efeito perigoso (recorte silencioso do host). A altura
   renderizada da gaveta não é afirmada: `height` derivado não resolve offline.
3. POSIÇÃO — o que É e o que NÃO É medido (atualizado em T42c).
   EMENDA: a redação anterior dizia que a posição relativa da gaveta "não
   resolve offline". Isso era verdade para as PÍLULAS (toda célula sai em
   x=12,y=10) e FALSO para a gaveta. Medido nesta base: o painel da gaveta e a
   grade são IRMÃOS no mesmo contêiner e ambos publicam x/y/width estáveis e
   determinísticos (duas execuções independentes deram a mesma geometria, e
   quatro atrasos de censo — 250ms a 3s — deram o mesmo resultado, então não é
   quadro de animação). Por isso T38.1, T38.2 e T38.3 passaram a ser medidos
   por geometria em ``Snap.direction_of``.

   O que continua NÃO medido por posição:
   a) posição de PÍLULA (célula), e portanto qualquer asserção do tipo "a
      pílula A está à esquerda da pílula B";
   b) ANCORAGEM NA BASE em pixels (T38.2 fala em ``anchors.bottom``): o teste
      prova que a lateral começa na MESMA faixa vertical da grade, não que o
      rodapé dela coincide com o rodapé do popout. A igualdade de ``y`` é o
      proxy disponível; "ancorado embaixo" no sentido estrito não é afirmado;
   c) o que o usuário vê quando a gaveta ESTOURA o popout: em alguns casos
      medidos o painel fica mais largo que a grade (x negativo ou passando da
      borda). O dump não recorta; a existência do estouro é visível na
      geometria, a quantidade de pixels realmente VISÍVEL não é.
4. `maxSecondary` COMO TETO NA VIEW: T35.3 diz que o limite é aplicado pelo
   serviço antes de serializar; esta suíte entrega o modelo já limitado (como em
   produção) e prova que a grade não inventa pílulas. Um caso com 3 secundários
   no modelo e `maxSecondary: 1` NÃO é afirmado: seria entrada que a produção não
   produz. Observação registrada para o gate: nesse cenário a view desenhou as 3
   pílulas enquanto o cabeçalho contou "3/1" — se o dono decidir que a view
   também deve cortar, isso vira defeito, não ambiguidade.
5. GUARDA-CHUVA DO ERRO: T34.2 diz "ERROR no lugar da barra". A pílula em erro
   desenha ERROR no texto E um trilho com preenchimento de 30%. A leitura
   estrita ("nenhuma barra no estado de erro") NÃO é afirmada porque o mandato
   desta suíte é o texto (ERROR presente, percentual ausente). Divergência
   registrada para o gate.
6. AUSÊNCIA DE CHIP/CURSOR NO '+N more' (T37.5, "sem borda de chip, sem cursor de
   mão"): a inércia é provada por estrutura (nenhum ancestral interativo). Borda
   e cursor não são observáveis neste dump.
7. CHAMFER/cantos, animação e foco de teclado continuam fora de escopo offline
   (mesma lacuna dos testes anteriores).

--- Segunda passada (T42b) -------------------------------------------------
8. MUTAÇÃO DO MODELO: a sonda serializa o OBJETO DO SERVIÇO (``JSON.stringify``
   de ``service.model``) antes e depois das interações. Isso pega remoção,
   inserção, reordenação e troca de tipo. NÃO pega mutação de um objeto que a
   view tenha recebido por CÓPIA PROFUNDA: nesse caso o modelo do serviço
   ficaria intacto e o defeito (se houver) viveria na cópia. Um deep copy antes
   de desenhar é a estratégia CORRETA para não mutar, e esta suíte a aprova.
9. "UM POLL" É SIMULADO trocando ``service.model`` por um objeto novo (mesmos
   ids), que é o que o serviço faz. NÃO é medido o ciclo real de refresh do
   serviço (timer de 300s, rede, falha de coleta). O que esta suíte prova é a
   VIEW sob troca de modelo — que é onde a garantia (ii) vive.
10. EXTRAÇÃO DE TEXTO DA GAVETA: o rótulo de métrica aparece na árvore apenas
   quando a gaveta desenha a linha correspondente. Por isso "detalhe presente"
   = "gaveta aberta daquele provider". Uma gaveta aberta mas COMPLETAMENTE
   vazia (zero linhas desenhadas, sem "+N more") não seria contada — cenário que
   não ocorre nos fixtures (todo provider tem 2+ métricas).
11. LEITURA MAIS EXIGENTE EM (ii.1): ``test_a_gaveta_rele_o_modelo_novo`` exige
   que a gaveta aberta exiba os RÓTULOS DO MODELO NOVO, não só que continue
   aberta. O mandato fala apenas em "continuar aberta"; a leitura estrita é a
   única que impede a gaveta de exibir números velhos como se fossem atuais.
   Se o dono decidir que "aberta com o último dado conhecido" é aceitável, este
   é o único teste a revisar — a asserção de permanência está no teste anterior.
12. O MARCADOR "Collapse" (controle de recolher da gaveta, em inglês) é usado
   como sinal de "existe gaveta aberta" no caso de provider promovido a
   primário. Ele é observado nesta base com ``language: "en"``; um fixture em
   outro idioma precisaria do rótulo correspondente.

--- Terceira passada (T42c) — SUBSTITUÍDA pela quarta, mantida como história -
--- (os itens 13–16 descrevem a queda para `down`, REVOGADA pela emenda) --------
13. [REVOGADO] ACHADO EM ABERTO (T38.3, `left`): com orçamento estreito a gaveta `left`
    NÃO cai para `down`. Medido por geometria, de forma determinística:
      widthBudget 240..320 -> painel em x NEGATIVO (ex. wb=300: x=-112, w=400,
      grade w=276), ANCHADO abaixo da grade mas 124px mais largo que ela. Ou
      seja: não é `down` (a largura não é a da grade) e não é `left` (começa
      fora do popout, à esquerda). `right` no MESMO orçamento cai limpo para
      `down` (x=12, y=16, w=grade). A assimetria é o achado: a queda existe e
      funciona em `right`, e em `left` produz um estado intermediário.
    O teste `test_a_lateral_que_nao_cabe_abre_para_baixo[left]` FALHA por isso,
    de propósito: a asserção não foi afrouxada. É informação para o gate, não
    ambiguidade — o contrato diz "não troca de lado em silêncio" e "abre para
    baixo", e o desenho medido não é nenhum dos dois.
14. [REVOGADO] A LARGURA DO PAINEL `left` NÃO SEGUE o orçamento: medido 400 constante para
    widthBudget 330..1400, enquanto `right` acompanha `drawerPanelWidth`
    (196 @460, 394 @900, 619 @1400). Em wb=900 o painel `left` (400) é menos da
    metade de `right` (394)... e em wb=1400, 400 vs 619. Pode ser intencional
    (largura fixa de leitura) ou o mesmo defeito de orçamento; registrado, não
    afirmado — a suíte não fixa o número 400.
15. O TESTE NOVO NÃO OLHA A SETTING, OLHA O DESENHO. Ele continua afirmando que
    `drawerDirection` chegou à view (âncora 1), mas a asserção que importa é a
    geometria. Uma view que ignorasse a setting e desenhasse certo passaria na
    geometria e falharia na âncora; uma view que aceitasse a setting e
    desenhasse sempre `down` passa a falhar — que é o defeito do dono.
16. PROVA DE FALSIFICAÇÃO (executada, fora da suíte): com a árvore de `dir-down`
    injetada no lugar de `dir-left`/`dir-right`, os três testes novos FALHAM
    ("a setting pede 'left' mas a gaveta abriu em 'down'"). Com
    ``direction_of`` forçado a devolver "down", também FALHAM. Com a QUEDA
    CORRETA injetada (geometria de `down` preservando a setting `left`),
    ``test_a_lateral_que_nao_cabe_abre_para_baixo[left]`` PASSA — ou seja, o
    teste é satisfazível e não é uma parede.
    teste é satisfazível e não é uma parede.

--- Quarta passada — EMENDA ASSINADA DE T38 (2026-10-30) --------------------
17. A TOPOLOGIA MUDOU E O TESTE ACOMPANHOU. A emenda põe a grade e o detalhe
    numa FAIXA comum, lado a lado, em vez de o detalhe recobrir a grade. A busca
    do painel passou de "irmão da grade" para "galho da faixa comum que carrega
    o marcador e não contém a grade" (``Snap.band``/``Snap.drawer_panel``). Isso
    NÃO é afrouxamento: a asserção de direção continua sendo geométrica e
    continua exigindo encosto na borda correta da grade. O que se perdeu foi a
    exigência de IRMANDADE, que era detalhe de implementação, não de desenho.
18. ABERTO PARA O GATE — CRITÉRIO DE FALLBACK LATERAL. A emenda diz que o
    detalhe ocupa a área liberada e que a largura do popout não muda, mas NÃO
    diz o que acontece quando o orçamento não comporta o detalhe de jeito
    nenhum. A redação antiga ("lateral que não cabe abre para baixo") foi
    revogada e a suíte NÃO inventa um substituto: afirma só o que está
    assinado (a lateral continua abrindo, do mesmo lado, sem reduzir colunas).
    Medido nesta base com `widthBudget` 240–300: o detalhe continua sendo
    desenhado do lado pedido, com a borda de encosto correta; o que NÃO é
    medido é quanto dele fica DENTRO do popout (ver item 19). Quando o dono
    fechar o critério, esta é a lacuna a converter em asserção.
19. ESTOURO DO POPOUT NÃO É MEDIDO EM PIXELS VISÍVEIS — E O ACHADO É MAIOR QUE
    "orçamento apertado". Medido nesta base, com `columns: 2` e o mesmo modelo de
    3 secundários, em TODOS os orçamentos testados (240, 300, 460, 700, 900,
    1400), a GRADE mantém a largura inteira de `contentWidth` e o painel do
    detalhe é desenhado INTEIRO FORA dela (x negativo em `left`, x além do fim
    em `right`):

        wb= 900  grade 12..888 (w=876)  detalhe -382..12   soma 1270
        wb= 300  grade 12..288 (w=276)  detalhe -168..12   soma  456
        wb= 460  grade 12..448 (w=436)  detalhe -184..12   soma 632

    Ou seja: `contentWidth == grade.w` em todas as direções, e o detalhe não
    "ocupa a área liberada" DENTRO do popout — não há área liberada, porque a
    grade não encolhe. Combinado com a premissa da própria emenda ("o host
    recorta o conteúdo na superfície do popout"), o desenho medido implica que
    o detalhe seria recortado pela borda do popout.
    A suíte NÃO fixa um oráculo para isso: a emenda não quantifica a divisão de
    largura entre grade e detalhe, e inventar "grade + detalhe <= contentWidth"
    seria inventar o contrato. Fica como INFORMAÇÃO PARA O GATE, com números.
    O que a suíte afirma é o que está assinado e é observável: não há
    sobreposição (item 20), o lado é o pedido, e a largura do popout/colunas não
    mudam. A leitura "o usuário VÊ o detalhe com suas bordas" precisa do smoke
    real — é exatamente o ponto que o dono reprovou antes e que o offline não
    pode fechar.
20. DESLOCAMENTO DAS PÍLULAS NÃO É MEDIDO POR COORDENADA. A emenda diz que as
    pílulas "deslizam no sentido oposto". Em offscreen toda célula publica
    x=12,y=10 (item 1), então o deslocamento DENTRO da grade não é afirmado. O
    que se afirma é o invariante equivalente e observável: o detalhe ocupa área
    que a grade não ocupa (sem sobreposição) e a grade mantém o mesmo número de
    pílulas e a mesma largura de faixa. Se a animação de deslizamento regredir
    sem mudar a geometria final, esta suíte não vê — é smoke humano.
    Pelo mesmo motivo, "pílula PARCIALMENTE cortada é clicável" (emenda) não é
    provado como PARCIAL: o recorte pela borda do painel não é observável no
    dump. `test_pilula_visivel_com_a_lateral_aberta_troca_o_provider` prova que
    uma pílula AINDA NA ÁRVORE é clicável e troca o provider, nos dois
    orçamentos (folgado e estreito) — a metade "parcial" precisa de smoke.
    Idem para "pílulas parcialmente cortadas recebem sombra ou fade na borda do
    recorte": nem sombra nem alpha de recorte são mensuráveis aqui.
21. A SETA É PROVADA POR GLIFO + COMPORTAMENTO, NÃO POR RÓTULO SEMÂNTICO. A
    emenda descreve a seta pelo que ela FAZ (retorna à grade) e pelo sentido do
    deslocamento (`→`/`←`). O glifo é usado como identidade porque é o único
    canal de texto que a árvore expõe para o controle; o rótulo acessível
    (T25/Att1, "nomear a ação") NÃO é observável neste dump e fica como lacuna —
    um leitor de tela sem nome na seta passaria aqui e falharia no smoke.
22. A ALTURA RESERVADA É PROVADA POR INVARIÂNCIA, NÃO POR VALOR. O
    esclarecimento posterior do dono (na SPEC, após a assinatura) diz que a
    reserva lateral é a MAIOR altura necessária entre os secundários, limitada
    pelo teto, e que uma atualização do relatório pode alterá-la. Por isso a
    asserção é: (a) a faixa não passa do teto, e (b) a altura é a MESMA para
    providers de tamanhos diferentes no mesmo teto. NÃO se afirma "faixa == teto"
    (o esclarecimento nega) nem "a reserva é o maior detalhe DISPONÍVEL" — este
    último exigiria conhecer o modelo inteiro e a regra de composição, que a
    emenda não fixa. Consequência: uma view que reservasse um valor fixo pequeno
    e constante passaria; isso é fiel ao contrato, não buraco de teste.
23. O CLASSIFICADOR DE "CONTROLE NÃO-PÍLULA" DA SONDA NÃO ALCANÇA A SETA. O
    painel do detalhe repete o nome do provider, e a sonda sobe só 3 ancestrais
    ao procurar nome de pílula; por isso a seta é contada como "dentro de
    pílula" e não entra em `expandClosers`. Consequência assumida: o recolher
    lateral é exercitado clicando o GLIFO por texto, e a cobertura "existe um
    controle não-pílula que fecha" ficou só em `down`. Não se corrigiu a sonda
    (o harness está fora do escopo desta emenda).
"""
