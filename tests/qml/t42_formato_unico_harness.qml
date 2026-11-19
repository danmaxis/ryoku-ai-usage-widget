// -*- mode: qml -*-
// Sonda de comportamento do FORMATO ÚNICO — grade de pílulas + gaveta (Joseki D5).
//
// Gerado em contexto isolado (D5) — sem acesso a content/Widget.qml nem a
// service/Main.qml. Base: SPEC rodada 4, tarefas T33–T39 (portado em T42).
//
// O que esta sonda faz: monta APENAS content/Widget.qml num processo quickshell
// OFFLINE (QT_QPA_PLATFORM=offscreen), com um pluginApi SINTÉTICO cujo
// `mainInstance` é um serviço falso com `model`. Não executa o ai-usagebar, não
// usa rede, não escreve em config, não lê credencial. Cada caso é
// {name, settings, model, steps}: os steps rodam em sequência e cada um pode
// emitir um censo (SNAP) da ÁRVORE RENDERIZADA.
//
// Steps:
//   {"op":"snap","name":"x"}                      censo
//   {"op":"clickText","value":"Pill Beta"}        clique no nó interativo mais
//                                                 PRÓXIMO que contém esse texto
//   {"op":"ensureOpen","text":"BETA CHAT","click":"Pill Beta"}
//                                                 se o texto não está na árvore,
//                                                 clica o alvo (abre a gaveta)
//   {"op":"snapAfterOpen","name":"x","text":"..","click":".."}
//                                                 ensureOpen + censo no mesmo passo
//   {"op":"model","name":"x"}                     impressão digital do MODELO que o
//                                                 serviço entrega (JSON.stringify de
//                                                 service.model) — prova de que a
//                                                 view não mutou/reordenou nada
//   {"op":"poll","name":"x","model":{...},
//    "settings":{...}}                            simula um POLL do serviço: troca
//                                                 service.model por um objeto NOVO
//                                                 (mesmos ids) e, opcionalmente, as
//                                                 settings; censa depois de 500ms
//   {"op":"remount"}                              destrói e recria o Loader com o
//                                                 MESMO pluginApi (aproximação de
//                                                 "reabrir o popout")
//
// Saída (stdout, uma linha por registro; o consumidor parseia por prefixo):
//   VIEW_ERR|<msg>                     a view não montou ou lançou
//   CLICK|<alvo>|<tipo>|<w>x<h>|<como>  clique disparado
//   CLICK_MISS|<alvo>                  nenhum nó interativo contém o texto
//   MODEL|<nome>|<json do modelo do serviço>   impressão digital do modelo
//   SAVE_SETTING|<chave>               saveSetting chamado pela view
//   ===CASE|<nome>=== / ===CASE_END|<nome>===
//   ===SNAP|<nome>=== ... ===SNAP_END|<nome>===
//     PROP|<nome>|<tipo>|<valor json ou marcador>
//     IW|<implicitWidth>|<implicitHeight>|<width>|<height>
//     NODE|<id>|<parentId>|<tipo>|<texto json ou "">|x|y|w|h|r|a|clicked
//
// Por que NODE (árvore plana com id de pai) e não registros por tipo: as
// posições NÃO resolvem em offscreen (medido: todas as pílulas saem em x=12,
// y=10), então agrupar "o que está dentro de cada pílula" por geometria
// produziria casamentos falsos. A topologia é o dado confiável; o Python
// reconstrói a árvore e agrupa por ancestral comum — sem depender de nenhum
// nome interno de componente.
//
// Nota de medição: w/h são max(width, implicitWidth/Height) porque alguns
// `height` derivados não resolvem offline. Nada aqui depende de um pixel exato:
// a geometria serve para medir ALVO CLICÁVEL e para a largura implícita.

import QtQuick
import Quickshell

ShellRoot {
    id: root

    readonly property string plugDir: Quickshell.env("T42_PLUG_DIR") || ""
    // Os casos viajam por variável de ambiente em PARTES: um único valor
    // acima de MAX_ARG_STRLEN (128 KiB no Linux) faz o processo nem iniciar —
    // medido nesta base ao chegar a 43 casos. Emendar as partes evita depender
    // de leitura de arquivo por QML.
    function casePayload() {
        try {
            var n = parseInt(Quickshell.env("T42_CASES_PARTS") || "0")
            if (n <= 0) return Quickshell.env("T42_CASES") || "[]"
            var acc = ""
            for (var i = 0; i < n; i++) acc += (Quickshell.env("T42_CASES_" + i) || "")
            return acc
        } catch (e) { return "[]" }
    }
    property var cases: {
        try { return JSON.parse(root.casePayload()) } catch (e) { return [] }
    }
    property int idx: 0
    property bool done: false
    property var saves: []
    property var settings: ({})
    property var steps: []
    property int si: 0
    property var caseName: ""
    property int nodeId: 0
    property string pendingSnap: ""
    property var activeCase: null

    // Serviço falso: exatamente a forma que a view lê de pluginApi.mainInstance.
    QtObject {
        id: service
        property var model: null
        property bool loading: false
        property string lastError: ""
        property string errorKind: ""
        property real lastSuccessEpoch: 0
        function refresh() {}
    }

    QtObject {
        id: apiObj
        property var mainInstance: service
        property var pluginSettings: root.settings
        property string pluginDir: root.plugDir
        property string stateDir: Quickshell.env("T42_STATE_DIR") || "/tmp/t42-state"
        property bool panelOpen: false
        property bool panelAvailable: false
        function saveSetting(k, v) {
            root.saves.push(String(k))
            console.log("SAVE_SETTING|" + String(k))
        }
        function saveSettings() {}
        function openPanel() {}
        function closePanel() {}
        function togglePanel() {}
    }

    Loader {
        id: viewL
        active: false
        onLoaded: {
            try {
                item.pluginApi = apiObj
                item.s = 1
                item.active = true
                // Por CASO quando o caso declara `widthBudget`; senão o env de
                // sempre. É o único jeito de medir "a lateral cabe?" em duas
                // larguras no MESMO processo.
                item.widthBudget = (root.activeCase && root.activeCase.widthBudget)
                    ? root.activeCase.widthBudget
                    : parseInt(Quickshell.env("T42_WIDTH") || "460")
                item.density = "full"
            } catch (e) { console.log("VIEW_ERR|props: " + e) }
            mount.restart()
        }
        onStatusChanged: {
            if (status === Loader.Status.Error || status === 3)
                console.log("VIEW_ERR|o Loader não carregou a view (status " + status + ")")
        }
    }

    // ---------------------------------------------------------------- utils
    function kindOf(it) {
        try { return String(it).replace(/\(0x[0-9a-f]+\)/, "").split("_QML")[0] }
        catch (e) { return "<?" + e + ">" }
    }
    function poolOf(it) { try { return it.data || [] } catch (e) { return [] } }
    function visibleOf(it) {
        try { return (it.visible !== false && it.opacity !== 0) } catch (e) { return true }
    }
    function nodeW(n) {
        try { return Math.max(n.width || 0, n.implicitWidth || 0) } catch (e) { return 0 }
    }
    function nodeH(n) {
        try { return Math.max(n.height || 0, n.implicitHeight || 0) } catch (e) { return 0 }
    }
    function absPos(it) {
        try {
            var v = viewL.item
            if (v && it.mapToItem) { var p = it.mapToItem(v, 0, 0); return { x: p.x, y: p.y } }
        } catch (e) {}
        return { x: 0, y: 0 }
    }
    function alphaOf(it) {
        try { return (it.color && it.color.a !== undefined) ? it.color.a : 1 } catch (e) { return 1 }
    }
    function hasClicked(it) {
        try { return (typeof it.clicked === "function") } catch (e) { return false }
    }
    function isInteractive(it) {
        var k = root.kindOf(it)
        if (/MouseArea|TapHandler|HoverHandler|DragHandler|WheelHandler|AbstractButton|QQuickButton|QQuickControl|QQuickSwitch|QQuickCheckBox/.test(k))
            return true
        return root.hasClicked(it)
    }

    // ------------------------------------------------- impressão digital do modelo
    // O model é entregue pelo SERVIÇO e a view o recebe por referência. Se a view
    // remover/inserir/reordenar itens em provider.metrics (a tentação de
    // "esvaziar o que não couber"), o dano aparece AQUI, no objeto do serviço —
    // e o dano só seria visível ao usuário no poll seguinte. `mount` é impresso
    // ANTES de a view montar, então mutação no primeiro render também é pega.
    function emitModel(name) {
        var fp = "<throw>"
        try { fp = JSON.stringify(service.model) } catch (e) { fp = "<throw:" + e + ">" }
        console.log("MODEL|" + name + "|" + fp)
    }

    // -------------------------------------------------------------- census
    function emitTree(it, depth, parentId) {
        if (!it || depth > 30) return
        root.nodeId++
        var myId = root.nodeId
        if (root.visibleOf(it)) {
            var p = root.absPos(it)
            var txt = ""
            try {
                if (typeof it.text === "string" && it.text.length > 0) txt = it.text
            } catch (e) {}
            var r = 0
            try { r = (it.radius === undefined ? 0 : it.radius) } catch (e) {}
            console.log("NODE|" + myId + "|" + parentId + "|" + root.kindOf(it) + "|"
                + JSON.stringify(String(txt)) + "|" + p.x + "|" + p.y + "|"
                + root.nodeW(it) + "|" + root.nodeH(it) + "|" + r + "|"
                + root.alphaOf(it) + "|" + root.isInteractive(it))
        }
        var pool = root.poolOf(it)
        for (var m = 0; m < pool.length; m++) root.emitTree(pool[m], depth + 1, myId)
    }

    function propValue(v) {
        if (v === undefined) return "{\"$undefined\":true}"
        if (v === null) return "null"
        var t = typeof v
        if (t === "number") { if (isNaN(v)) return "{\"$nan\":true}"; return String(v) }
        if (t === "string" || t === "boolean") return JSON.stringify(v)
        return "{\"$type\":\"" + t + "\"}"
    }

    function emitSnap(name) {
        console.log("===SNAP|" + name + "===")
        console.log("SAVES|" + JSON.stringify(root.saves))
        var v = viewL.item
        if (v === null || v === undefined) {
            console.log("PROP|<noview>|object|null")
            console.log("===SNAP_END|" + name + "===")
            return
        }
        var props = ["columns", "density", "drawerDirection", "openDrawerId",
                     "pad", "gap",
                     // Larguras/alturas que a view RESOLVE (públicas). Servem para
                     // medir a direção por GEOMETRIA: a lateral nasce daqui.
                     "available", "contentWidth", "baseWidth", "widthBudget",
                     "drawerPanelWidth", "drawerMetricBudget",
                     "drawerHeaderHeight", "drawerMaxHeight",
                     "compactMode", "densityOverride", "compactByDefault",
                     "visibleMetrics", "toggleAll", "anyProviderExpanded",
                     "hiddenMetricCount", "hiddenMetricCountForLabel",
                     "canToggleProvider", "modeButtonLabel", "modeButtonAction",
                     "canToggleAny", "isExpanded", "toggleExpanded"]
        for (var i = 0; i < props.length; i++) {
            var tv = "undefined", vv = "{\"$undefined\":true}"
            try { var got = v[props[i]]; tv = typeof got; vv = root.propValue(got) }
            catch (e) { tv = "<throw>" }
            console.log("PROP|" + props[i] + "|" + tv + "|" + vv)
        }
        var iw = 0, ih = 0, w = 0, h = 0
        try { iw = v.implicitWidth } catch (e) {}
        try { ih = v.implicitHeight } catch (e) {}
        try { w = v.width } catch (e) {}
        try { h = v.height } catch (e) {}
        console.log("IW|" + iw + "|" + ih + "|" + w + "|" + h)
        root.nodeId = 0
        try { root.emitTree(v, 0, 0) } catch (e2) { console.log("VIEW_ERR|censo: " + e2) }
        console.log("===SNAP_END|" + name + "===")
    }

    // ------------------------------------------------------------- clicks
    function subtreeTexts(it, depth, acc) {
        if (!it || depth > 22) return acc
        try {
            if (typeof it.text === "string" && it.text.length > 0) acc.push(String(it.text))
        } catch (e) {}
        var pool = root.poolOf(it)
        for (var i = 0; i < pool.length; i++) root.subtreeTexts(pool[i], depth + 1, acc)
        return acc
    }

    // Alvo do clique identificado por COMPORTAMENTO: sobe do texto até o
    // primeiro ancestral (ou ele mesmo) que seja interativo OU cuja subárvore
    // contenha um nó com sinal `clicked`. Sem objectName, sem offset de layout.
    function enclosingControl(it) {
        var up = it
        for (var d = 0; d < 10 && up; d++) {
            if (root.hasClicked(up)) return up
            var all = root.collectAll(up, 0, [])
            var nFound = 0
            for (var i = 0; i < all.length; i++) if (root.hasClicked(all[i])) nFound++
            if (nFound === 1 && d > 0) return up
            if (nFound > 1) return up
            try { up = up.parent } catch (e) { return null }
        }
        return null
    }

    function collectAll(it, depth, out) {
        if (!it || depth > 30) return out
        if (root.visibleOf(it)) out.push(it)
        var pool = root.poolOf(it)
        for (var i = 0; i < pool.length; i++) root.collectAll(pool[i], depth + 1, out)
        return out
    }

    function hasTextNow(needle) {
        var v = viewL.item
        if (!v) return false
        var n = String(needle).toUpperCase()
        var all = root.collectAll(v, 0, [])
        for (var i = 0; i < all.length; i++) {
            try {
                if (typeof all[i].text === "string" &&
                    all[i].text.toUpperCase().indexOf(n) >= 0) return true
            } catch (e) {}
        }
        return false
    }

    function deepestClicked(it, depth) {
        if (!it || depth > 30) return null
        if (root.hasClicked(it)) return it
        var pool = root.poolOf(it)
        for (var i = 0; i < pool.length; i++) {
            var r = root.deepestClicked(pool[i], depth + 1)
            if (r) return r
        }
        return null
    }

    // Nós interativos VISÍVEIS na ordem da árvore (esquerda→direita/cima→baixo
    // para uma grade, porque o Grid insere os filhos nessa ordem).
    function visibleInteractive() {
        var v = viewL.item
        if (!v) return []
        var all = root.collectAll(v, 0, [])
        var out = []
        for (var i = 0; i < all.length; i++) if (root.hasClicked(all[i])) out.push(all[i])
        return out
    }

    function clickTarget(c) {
        var target = root.hasClicked(c) ? c : root.deepestClicked(c, 0)
        if (target === null) {
            console.log("CLICK_MISS|nenhum nó com sinal clicked")
            return
        }
        var tw = Math.max(1, root.nodeW(target)), th = Math.max(1, root.nodeH(target))
        try {
            target.clicked(Qt.point(tw / 2, th / 2))
            console.log("CLICK|" + root.kindOf(c) + "|" + root.kindOf(target) + "|"
                + Math.round(tw) + "x" + Math.round(th) + "|clicked")
        } catch (e) {
            console.log("CLICK|" + root.kindOf(c) + "|" + root.kindOf(target) + "|"
                + Math.round(tw) + "x" + Math.round(th) + "|throw:" + e)
        }
    }

    // Clica o controle mais PRÓXIMO do texto dado. Com várias ocorrências
    // (p. ex. o nome do provider aparece na pílula E na gaveta), prefere o
    // controle MENOR — a pílula — porque é ela que alterna a gaveta.
    function clickByText(value) {
        var needle = String(value).toUpperCase()
        var v = viewL.item
        if (!v) { console.log("CLICK_MISS|sem view"); return }
        var all = root.collectAll(v, 0, [])
        var best = null, bestArea = -1
        for (var i = 0; i < all.length; i++) {
            var own = ""
            try { if (typeof all[i].text === "string") own = all[i].text.toUpperCase() } catch (e) {}
            if (own.indexOf(needle) < 0) continue
            var c = root.enclosingControl(all[i])
            if (c === null) continue
            var area = root.nodeW(c) * root.nodeH(c)
            if (best === null || (area > 0 && (bestArea <= 0 || area < bestArea))) {
                best = c
                bestArea = area
            }
        }
        if (best === null) { console.log("CLICK_MISS|" + value); return }
        // Guarda contra clique no ALVO ERRADO (medido nesta base: pedir clique no
        // texto do PRIMÁRIO resolvia para um ancestral que continha várias
        // pílulas, e o clique caía numa pílula de OUTRO provider — o teste
        // passaria medindo outra coisa). O alvo válido é o controle cuja
        // subárvore contém o texto pedido e cujo nome de pílula é um só.
        var nomes = {}
        var ts = root.subtreeTexts(best, 0, [])
        for (var j = 0; j < ts.length; j++) {
            var tt = ts[j].trim()
            if (/^Pill /.test(tt)) nomes[tt] = true
        }
        var temTexto = false
        for (var q = 0; q < ts.length; q++)
            if (ts[q].toUpperCase().indexOf(needle) >= 0) { temTexto = true; break }
        var distintos = 0
        for (var kk in nomes) distintos++
        if (!temTexto || distintos > 1) {
            console.log("CLICK_MISS|ambíguo: " + value + " (nomes=" + distintos + ")")
            return
        }
        root.clickTarget(best)
    }

    // Um nó interativo é "pílula" quando algum ancestral dele contém o texto do
    // nome de um secundário. Assim os candidatos a controle de RECOLHER são os
    // interativos que NÃO são pílula — identificados por estrutura e texto, sem
    // objectName e sem supor quantos controles existem.
    function ancestorHasAnyText(it, names) {
        var up = it
        // Profundidade LIMITADA de propósito: subir até a raiz alcançaria a
        // view inteira (que contém todos os nomes) e classificaria TODO nó
        // interativo como pílula. A pílula é o interativo cujo pai (a célula)
        // carrega o nome; o botão de recolher não tem nome de provider perto.
        for (var d = 0; d < 3 && up; d++) {
            var ts = root.subtreeTexts(up, 0, [])
            for (var i = 0; i < ts.length; i++) {
                var t = ts[i].toUpperCase()
                for (var j = 0; j < names.length; j++)
                    if (t.indexOf(String(names[j]).toUpperCase()) >= 0) return true
            }
            try { up = up.parent } catch (e) { return false }
        }
        return false
    }

    function expandClosers(st) {
        var names = st.names || []
        var list = root.visibleInteractive()
        var extra = []
        for (var i = 0; i < list.length; i++) {
            if (root.ancestorHasAnyText(list[i], names)) continue
            var slot = i
            extra.push({ op: "ensureOpen", text: st.openText, click: st.openClick })
            extra.push({ op: "clickIx", index: slot, label: st.prefix + slot })
            extra.push({ op: "snap", name: st.prefix + slot })
        }
        if (extra.length === 0)
            console.log("VIEW_ERR|nenhum controle não-pílula na árvore")
        root.steps = root.steps.slice(0, root.si).concat(extra, root.steps.slice(root.si))
    }

    // ------------------------------------------------------- step engine
    function tick() {
        if (root.si >= root.steps.length) { root.endCase(); return }
        var st = root.steps[root.si]
        root.si++
        try {
            if (st.op === "snap") {
                root.emitSnap(st.name)
            } else if (st.op === "snapAfterOpen") {
                if (!root.hasTextNow(st.text)) root.clickByText(st.click)
                root.emitSnap(st.name)
            } else if (st.op === "clickText") {
                root.clickByText(st.value)
            } else if (st.op === "ensureOpen") {
                if (!root.hasTextNow(st.text)) root.clickByText(st.click)
            } else if (st.op === "clickIx") {
                var ixs = root.visibleInteractive()
                if (st.index < 0 || st.index >= ixs.length)
                    console.log("CLICK_MISS|índice " + st.index + " de " + ixs.length)
                else {
                    console.log("CLICK_IX|" + st.label + "|" + st.index)
                    root.clickTarget(ixs[st.index])
                }
            } else if (st.op === "expandClosers") {
                root.expandClosers(st)
            } else if (st.op === "probeSave") {
                // Controle de vacuidade: prova que o gancho saveSetting do
                // pluginApi sintético FUNCIONA. Se ele estivesse quebrado, o
                // "a view nunca chama saveSetting" passaria sem testar nada.
                apiObj.saveSetting("T42_PROBE_CONTROL", true)
                console.log("SAVE_PROBE_OK|1")
            } else if (st.op === "model") {
                root.emitModel(st.name)
            } else if (st.op === "poll") {
                // Um poll do serviço: o model é trocado INTEIRO. Objetos novos,
                // mesmos ids. Nenhum id de provider é reaproveitado por índice.
                if (st.settings) root.settings = st.settings
                service.model = st.model
                root.pendingSnap = st.name || "poll"
                pollT.restart()
                return
            } else if (st.op === "remount") {
                // Mesmo pluginApi, mesma instância de serviço: só a SURFACE morre.
                // onLoaded() do Loader retoma os steps via `mount`.
                viewL.active = false
                viewL.setSource("")
                viewL.setSource(root.plugDir + "/content/Widget.qml")
                viewL.active = true
                return
            } else if (st.op === "snapIfOpen") {
                if (!root.hasTextNow(st.text)) root.clickByText(st.closeText)
                root.emitSnap(st.name)
            } else {
                console.log("VIEW_ERR|step desconhecido: " + st.op)
            }
        } catch (e2) {
            console.log("VIEW_ERR|step " + st.op + ": " + e2)
        }
        next.restart()
    }

    function startCase() {
        if (root.idx >= root.cases.length) { root.finish(); return }
        var c = root.cases[root.idx]
        root.activeCase = c
        root.caseName = String(c.name)
        root.saves = []
        root.settings = c.settings || {}
        root.steps = c.steps || []
        root.si = 0
        service.model = c.model
        console.log("===CASE|" + root.caseName + "===")
        root.emitModel("mount")
        viewL.active = false
        viewL.setSource("")
        viewL.setSource(root.plugDir + "/content/Widget.qml")
        viewL.active = true
        watchdog.restart()
    }

    function endCase() {
        watchdog.stop()
        console.log("===CASE_END|" + root.caseName + "===")
        viewL.active = false
        viewL.setSource("")
        root.idx++
        nextCase.restart()
    }

    function finish() {
        if (root.done) return
        root.done = true
        console.log("END")
        Qt.quit()
    }

    Timer { id: mount; interval: 700; repeat: false; onTriggered: root.tick() }
    Timer { id: next; interval: 260; repeat: false; onTriggered: root.tick() }
    Timer {
        id: pollT; interval: 500; repeat: false
        onTriggered: {
            if (root.pendingSnap !== "") root.emitSnap(root.pendingSnap)
            root.pendingSnap = ""
            next.restart()
        }
    }
    Timer { id: nextCase; interval: 200; repeat: false; onTriggered: root.startCase() }
    Timer { id: boot; interval: 300; running: true; repeat: false; onTriggered: root.startCase() }
    Timer {
        id: watchdog; interval: 20000; repeat: false
        onTriggered: {
            console.log("VIEW_ERR|watchdog no caso " + root.caseName)
            root.endCase()
        }
    }
}
