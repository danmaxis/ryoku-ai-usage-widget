// -*- mode: qml -*-
// Sonda de comportamento da EMENDA T38 — ALTURA LATERAL RESERVADA (Joseki D5).
//
// Gerado em contexto isolado (D5) — sem acesso a content/Widget.qml nem a
// service/Main.qml. Base: SPEC rodada 4, emenda T38 assinada em 2026-10-30 e o
// esclarecimento posterior do dono ("a altura lateral reservada desde a abertura
// é a maior altura necessária entre os detalhes dos secundários disponíveis,
// limitada pelo teto; não é necessariamente o próprio teto. Uma atualização do
// relatório pode alterar essa reserva").
//
// Instrumento PRÓPRIO (não reusa a sonda de T45): a medida que este arquivo
// precisa — a altura que a seção de secundários ocupa, fechada e aberta, sob
// diferentes relatórios — é independente da sonda de deslocamento, e um teste
// não deve herdar silenciosamente o instrumento de outro teste.
//
// O que faz: monta APENAS content/Widget.qml num processo quickshell OFFLINE
// (QT_QPA_PLATFORM=offscreen) com pluginApi SINTÉTICO. Não roda o ai-usagebar,
// não usa rede, não lê credencial, não escreve em config.
//
// Entrada: T46_PLUG_DIR + T46_CASES_<i>/T46_CASES_PARTS (JSON), cada caso
//   {name, settings, model, widthBudget, epoch, steps:[...]}
// Steps:
//   {"op":"snap","name":"x"}                  censo da árvore
//   {"op":"wait","ms":N,"name":"x"}           espera N ms e censa
//   {"op":"clickText","value":"Pill S1"}      clica o controle daquele texto
//   {"op":"openDrawer","text":"S1 M1",
//    "click":"Pill S1","name":"x"}            abre se o marcador não está na
//                                             árvore, espera e censa
//   {"op":"poll","model":{...},"name":"x"}    troca o relatório e censa
//
// Saída (stdout; prefixos estáveis):
//   VIEW_ERR|<msg> · CLICK|<alvo> · CLICK_MISS|<alvo> · MODEL|<nome>|<json>
//   ===CASE|<nome>=== / ===CASE_END|<nome>===
//   ===SNAP|<nome>===
//     PROP|<nome>|<tipo>|<valor>|<…|IW|iw|ih|w|h>
//     NODE|<id>|<pai>|<tipo>|<texto json>|x|y|w|h|clip|clicável
//   ===SNAP_END|<nome>===
//
// LIMITAÇÃO DECLARADA: `height` derivado de conteúdo do popout não resolve
// offline (o item não é dimensionado pelo host: implicitHeight fica no valor
// mínimo). O que resolve — e é o que se mede — é a altura do CONTÊINER da seção
// de secundários, que é o bloco que a view reserva dentro da coluna raiz. Nada
// aqui depende de objectName nem de nome de componente: os alvos são achados por
// tipo, por pai/filho e por texto.

import QtQuick
import Quickshell

ShellRoot {
    id: root

    readonly property string plugDir: Quickshell.env("T46_PLUG_DIR") || ""

    function casePayload() {
        try {
            var n = parseInt(Quickshell.env("T46_CASES_PARTS") || "0")
            if (n <= 0) return Quickshell.env("T46_CASES") || "[]"
            var acc = ""
            for (var i = 0; i < n; i++) acc += (Quickshell.env("T46_CASES_" + i) || "")
            return acc
        } catch (e) { return "[]" }
    }

    property var cases: { try { return JSON.parse(root.casePayload()) } catch (e) { return [] } }
    property int idx: 0
    property bool done: false
    property var settings: ({})
    property var steps: []
    property int si: 0
    property string caseName: ""
    property int nodeId: 0
    property string pendingSnap: ""
    property var activeCase: null

    // Serviço falso: a forma que a view lê de pluginApi.mainInstance.
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
        property string stateDir: Quickshell.env("T46_STATE_DIR") || "/tmp/t46-state"
        property bool panelOpen: false
        property bool panelAvailable: false
        function saveSetting(k, v) {}
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
                item.widthBudget = (root.activeCase && root.activeCase.widthBudget)
                    ? root.activeCase.widthBudget
                    : parseInt(Quickshell.env("T46_WIDTH") || "460")
            } catch (e) { console.log("VIEW_ERR|props: " + e) }
            mount.restart()
        }
        onStatusChanged: {
            if (status === Loader.Error || status === 3)
                console.log("VIEW_ERR|o Loader não carregou a view (status " + status + ")")
        }
    }

    // ------------------------------------------------------------- estrutura
    function kindOf(it) {
        try { return String(it).replace(/\(0x[0-9a-f]+\)/, "").split("_QML")[0] }
        catch (e) { return "<?>" }
    }
    function poolOf(it) { try { return it.data || [] } catch (e) { return [] } }
    function visibleOf(it) {
        try { return (it.visible !== false && it.opacity !== 0) } catch (e) { return true }
    }
    function nodeW(n) { try { return Math.max(n.width || 0, n.implicitWidth || 0) } catch (e) { return 0 } }
    function nodeH(n) { try { return Math.max(n.height || 0, n.implicitHeight || 0) } catch (e) { return 0 } }
    function absPos(it) {
        try {
            var v = viewL.item
            if (v && it.mapToItem) { var p = it.mapToItem(v, 0, 0); return { x: p.x, y: p.y } }
        } catch (e) {}
        return { x: 0, y: 0 }
    }
    function hasClicked(it) { try { return (typeof it.clicked === "function") } catch (e) { return false } }
    function isInteractive(it) {
        var k = root.kindOf(it)
        if (/MouseArea|TapHandler|HoverHandler|DragHandler|WheelHandler|AbstractButton|QQuickButton|QQuickControl/.test(k))
            return true
        return root.hasClicked(it)
    }
    function collectAll(it, depth, out) {
        if (!it || depth > 30) return out
        if (root.visibleOf(it)) out.push(it)
        var pool = root.poolOf(it)
        for (var i = 0; i < pool.length; i++) root.collectAll(pool[i], depth + 1, out)
        return out
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
    function enclosingControl(it) {
        var up = it
        for (var d = 0; d < 10 && up; d++) {
            if (root.hasClicked(up)) return up
            var all = root.collectAll(up, 0, [])
            for (var i = 0; i < all.length; i++) if (root.hasClicked(all[i])) return up
            try { up = up.parent } catch (e) { return null }
        }
        return null
    }
    // Clica o MENOR controle cujo texto é exatamente o pedido: a pílula, não o
    // contêiner que a envolve (clicar o contêiner erra o provider).
    function clickExact(value) {
        var v = viewL.item
        if (!v) { console.log("CLICK_MISS|sem view"); return false }
        var all = root.collectAll(v, 0, [])
        var alvo = null
        for (var i = 0; i < all.length; i++) {
            var tx = ""
            try { if (typeof all[i].text === "string") tx = all[i].text } catch (e) {}
            if (tx.trim().toUpperCase() !== String(value).toUpperCase()) continue
            var c = root.enclosingControl(all[i])
            if (c === null) continue
            if (alvo === null || root.nodeW(c) * root.nodeH(c) < root.nodeW(alvo) * root.nodeH(alvo))
                alvo = c
        }
        if (alvo === null) { console.log("CLICK_MISS|" + value); return false }
        var ctl = root.hasClicked(alvo) ? alvo : root.deepestClicked(alvo, 0)
        if (ctl === null) { console.log("CLICK_MISS|sem sinal clicked: " + value); return false }
        try {
            ctl.clicked(Qt.point(Math.max(1, root.nodeW(ctl)) / 2, Math.max(1, root.nodeH(ctl)) / 2))
            console.log("CLICK|" + value + "|" + root.kindOf(ctl))
            return true
        } catch (e) { console.log("CLICK_MISS|throw: " + value + " " + e); return false }
    }
    function hasTextNow(needle) {
        var v = viewL.item
        if (!v) return false
        var n = String(needle).toUpperCase()
        var all = root.collectAll(v, 0, [])
        for (var i = 0; i < all.length; i++) {
            try {
                if (typeof all[i].text === "string" && all[i].text.toUpperCase().indexOf(n) >= 0) return true
            } catch (e) {}
        }
        return false
    }

    // ---------------------------------------------------------------- censo
    function propValue(v) {
        if (v === undefined) return "{\"$undefined\":true}"
        if (v === null) return "null"
        var t = typeof v
        if (t === "number") { if (isNaN(v)) return "{\"$nan\":true}"; return String(v) }
        if (t === "string" || t === "boolean") return JSON.stringify(v)
        return "{\"$type\":\"" + t + "\"}"
    }
    function emitTree(it, depth, parentId) {
        if (!it || depth > 30) return
        root.nodeId++
        var myId = root.nodeId
        if (root.visibleOf(it)) {
            var p = root.absPos(it)
            var txt = ""
            try { if (typeof it.text === "string" && it.text.length > 0) txt = it.text } catch (e) {}
            var clip = 0
            try { clip = (it.clip === true) ? 1 : 0 } catch (e2) {}
            console.log("NODE|" + myId + "|" + parentId + "|" + root.kindOf(it) + "|"
                + JSON.stringify(txt) + "|" + p.x + "|" + p.y + "|"
                + root.nodeW(it) + "|" + root.nodeH(it) + "|" + clip + "|"
                + root.isInteractive(it))
        }
        var pool = root.poolOf(it)
        for (var m = 0; m < pool.length; m++) root.emitTree(pool[m], depth + 1, myId)
    }
    function emitSnap(name) {
        console.log("===SNAP|" + name + "===")
        var v = viewL.item
        if (v === null || v === undefined) {
            console.log("PROP|<noview>|object|null")
            console.log("===SNAP_END|" + name + "===")
            return
        }
        var props = ["columns", "drawerDirection", "openDrawerId", "contentWidth",
                     "widthBudget", "drawerMaxHeight", "pad", "gap"]
        for (var i = 0; i < props.length; i++) {
            var tv = "undefined", vv = "{\"$undefined\":true}"
            try { var got = v[props[i]]; tv = typeof got; vv = root.propValue(got) } catch (e) { tv = "<throw>" }
            var extra = (i === props.length - 1)
                ? "|IW|" + v.implicitWidth + "|" + v.implicitHeight + "|" + v.width + "|" + v.height : ""
            console.log("PROP|" + props[i] + "|" + tv + "|" + vv + extra)
        }
        root.nodeId = 0
        try { root.emitTree(v, 0, 0) } catch (e2) { console.log("VIEW_ERR|censo: " + e2) }
        console.log("===SNAP_END|" + name + "===")
    }

    // --------------------------------------------------------- motor de passos
    function later(ms, snapName) {
        root.pendingSnap = snapName || ""
        waitT.interval = ms || 700
        waitT.restart()
    }
    function tick() {
        if (root.si >= root.steps.length) { root.endCase(); return }
        var st = root.steps[root.si]
        root.si++
        try {
            if (st.op === "snap") {
                root.emitSnap(st.name)
            } else if (st.op === "wait") {
                later(st.ms || 600, st.name); return
            } else if (st.op === "clickText") {
                root.clickExact(st.value)
            } else if (st.op === "openDrawer") {
                if (!root.hasTextNow(st.text)) root.clickExact(st.click)
                later(st.ms || 900, st.name || "open"); return
            } else if (st.op === "poll") {
                service.model = st.model
                later(st.ms || 1200, st.name || "poll"); return
            } else {
                console.log("VIEW_ERR|step desconhecido: " + st.op)
            }
        } catch (e2) { console.log("VIEW_ERR|step " + st.op + ": " + e2) }
        next.restart()
    }

    function startCase() {
        if (root.idx >= root.cases.length) { root.finish(); return }
        var c = root.cases[root.idx]
        root.activeCase = c
        root.caseName = String(c.name)
        root.settings = c.settings || {}
        root.steps = c.steps || []
        root.si = 0
        service.model = c.model
        service.lastSuccessEpoch = (c.epoch === undefined) ? 0 : c.epoch
        console.log("===CASE|" + root.caseName + "===")
        console.log("MODEL|mount|" + JSON.stringify(c.model))
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
    Timer { id: next; interval: 240; repeat: false; onTriggered: root.tick() }
    Timer {
        id: waitT; repeat: false
        onTriggered: {
            if (root.pendingSnap !== "") root.emitSnap(root.pendingSnap)
            root.pendingSnap = ""
            next.restart()
        }
    }
    Timer { id: nextCase; interval: 200; repeat: false; onTriggered: root.startCase() }
    Timer { id: boot; interval: 300; running: true; repeat: false; onTriggered: root.startCase() }
    Timer {
        id: watchdog; interval: 25000; repeat: false
        onTriggered: {
            console.log("VIEW_ERR|watchdog no caso " + root.caseName)
            root.endCase()
        }
    }
}
