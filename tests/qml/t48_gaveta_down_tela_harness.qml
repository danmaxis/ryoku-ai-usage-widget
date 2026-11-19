// -*- mode: qml -*-
// Sonda de comportamento de T48/T49 — GAVETA `down` LIMITADA À TELA e `+N more`
// NUNCA RECORTADO (Joseki D5).
//
// Gerado em contexto isolado (D5) — sem acesso à implementação. Base: SPEC
// rodada 5, tarefas T48 e T49. Nem content/Widget.qml nem service/ foram lidos.
//
// Instrumento PRÓPRIO (o transporte é o da sonda de T46: casos por variável de
// ambiente, censo da árvore por stdout). Duas diferenças, as duas exigidas pelo
// contrato desta rodada:
//
//   1. A view é montada DENTRO DE UMA JANELA (QtQuick Window, offscreen). Sem
//      janela não há entrega de evento de ponteiro, e o item 5 do contrato de
//      T48 ("clique sobre o painel não atravessa para a pílula de baixo") só é
//      observável com um clique REAL em coordenada — chamar `clicked()` num
//      controle escolhido pela sonda não prova quem recebe o evento.
//   2. A sonda informa `heightBudget` (e `s`) por caso. Se a view não tiver a
//      propriedade, a sonda diz `HB_UNSUPPORTED` e segue: as demais propriedades
//      são aplicadas do mesmo jeito, para que a base anterior seja MEDIDA em vez
//      de quebrar a montagem.
//
// O que faz: monta APENAS content/Widget.qml num processo quickshell OFFLINE
// (QT_QPA_PLATFORM=offscreen) com pluginApi SINTÉTICO. Não roda o ai-usagebar,
// não usa rede, não lê credencial, não escreve em config.
//
// Entrada: T48_PLUG_DIR + T48_CASES_<i>/T48_CASES_PARTS (JSON), cada caso
//   {name, settings, model, widthBudget, heightBudget?, s?, epoch, steps:[...]}
// Steps:
//   {"op":"snap","name":"x"}                  censo da árvore
//   {"op":"wait","ms":N,"name":"x"}           espera N ms e censa
//   {"op":"clickText","value":"Pill S1"}      clica o controle daquele texto
//                                             (sinal `clicked`, como em T46)
//   {"op":"openDrawer","text":"S1 M1",
//    "click":"Pill S1","name":"x"}            abre se o marcador não está na
//                                             árvore, espera e censa
//   {"op":"mouseAt","x":X,"y":Y,"name":"x"}   clique REAL do ponteiro na
//                                             coordenada (da view), espera e censa
//   {"op":"mouseText","value":"T","name":"x"} clique REAL no centro do item de
//                                             texto exato T, espera e censa
//   {"op":"mouseOnControl","value":"T",
//    "fx":0.5,"fy":0.9,"name":"x"}            clique REAL na fração (fx,fy) do
//                                             menor controle que contém o texto T
//   {"op":"setHeightBudget","value":H,
//    "name":"x"}                              muda o orçamento e censa
//   {"op":"poll","model":{...},"name":"x"}    troca o relatório e censa
//
// Saída (stdout; prefixos estáveis):
//   VIEW_ERR|<msg> · CLICK|<alvo> · CLICK_MISS|<alvo> · MOUSE|x|y · MOUSE_ERR|…
//   HB_SET|<valor> · HB_UNSUPPORTED|<motivo>
//   ===CASE|<nome>=== / ===CASE_END|<nome>===
//   ===SNAP|<nome>===
//     PROP|<nome>|<tipo>|<valor>|<…|IW|iw|ih|w|h>
//     NODE|<id>|<pai>|<tipo>|<texto json>|x|y|w|h|clip|clicável|cor|opacidade
//   ===SNAP_END|<nome>===
//
// Geometria: x/y são relativos à raiz da view, em pixels REAIS (já escalados).
// `ih` é o implicitHeight da raiz, que o contrato declara em unidades NÃO
// escaladas: a altura real ocupada é ih * s. Nada aqui depende de objectName
// nem de nome de componente: os alvos são achados por tipo, pai/filho e texto.

import QtQuick
import QtQuick.Window
import QtTest
import Quickshell

ShellRoot {
    id: root

    readonly property string plugDir: Quickshell.env("T48_PLUG_DIR") || ""

    function casePayload() {
        try {
            var n = parseInt(Quickshell.env("T48_CASES_PARTS") || "0")
            if (n <= 0) return Quickshell.env("T48_CASES") || "[]"
            var acc = ""
            for (var i = 0; i < n; i++) acc += (Quickshell.env("T48_CASES_" + i) || "")
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
        property string stateDir: Quickshell.env("T48_STATE_DIR") || "/tmp/t48-state"
        property bool panelOpen: false
        property bool panelAvailable: false
        function saveSetting(k, v) {}
        function saveSettings() {}
        function openPanel() {}
        function closePanel() {}
        function togglePanel() {}
    }

    TestEvent { id: pointer }

    // Janela de palco: grande o bastante para qualquer caso, para que NENHUM
    // recorte observado venha da janela — só os da própria view.
    Window {
        id: win
        visible: true
        width: 2400
        height: 6400
        color: "black"

        Loader {
            id: viewL
            x: 0
            y: 0
            active: false
            onLoaded: {
                var c = root.activeCase || {}
                try { item.pluginApi = apiObj } catch (e) { console.log("VIEW_ERR|pluginApi: " + e) }
                try { item.s = (c.s === undefined) ? 1 : c.s } catch (e1) { console.log("VIEW_ERR|s: " + e1) }
                try { item.active = true } catch (e2) { console.log("VIEW_ERR|active: " + e2) }
                try { item.widthBudget = c.widthBudget ? c.widthBudget : 460 }
                catch (e3) { console.log("VIEW_ERR|widthBudget: " + e3) }
                if (c.heightBudget !== undefined) root.applyHeightBudget(c.heightBudget)
                mount.restart()
            }
            onStatusChanged: {
                if (status === Loader.Error)
                    console.log("VIEW_ERR|o Loader não carregou a view (status " + status + ")")
            }
        }
    }

    function applyHeightBudget(v) {
        var it = viewL.item
        if (!it) { console.log("HB_UNSUPPORTED|sem view"); return }
        var has = false
        try { has = (it.heightBudget !== undefined) } catch (e) { has = false }
        if (!has) { console.log("HB_UNSUPPORTED|a view não tem a propriedade heightBudget"); return }
        try { it.heightBudget = v; console.log("HB_SET|" + v) }
        catch (e2) { console.log("HB_UNSUPPORTED|" + e2) }
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
    function nodeW(n) { try { return n.width || 0 } catch (e) { return 0 } }
    function nodeH(n) { try { return n.height || 0 } catch (e) { return 0 } }
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
        if (!root.visibleOf(it)) return out          // subárvore invisível não conta
        out.push(it)
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
    function textItems(value) {
        var v = viewL.item
        var out = []
        if (!v) return out
        var all = root.collectAll(v, 0, [])
        for (var i = 0; i < all.length; i++) {
            var tx = ""
            try { if (typeof all[i].text === "string") tx = all[i].text } catch (e) {}
            if (tx.trim().toUpperCase() === String(value).toUpperCase()) out.push(all[i])
        }
        return out
    }
    // Clica o MENOR controle cujo texto é exatamente o pedido (a pílula, não o
    // contêiner que a envolve). Usa o sinal `clicked`, como a sonda de T46.
    function clickExact(value) {
        var hits = root.textItems(value)
        var alvo = null
        for (var i = 0; i < hits.length; i++) {
            var c = root.enclosingControl(hits[i])
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
    // Clique REAL: o evento entra pela janela e o Qt decide quem o recebe.
    function mouseAt(x, y) {
        var v = viewL.item
        if (!v) { console.log("MOUSE_ERR|sem view"); return false }
        try {
            var ok = pointer.mouseClick(v, x, y, Qt.LeftButton, Qt.NoModifier, -1)
            console.log("MOUSE|" + x + "|" + y + "|" + ok)
            return true
        } catch (e) { console.log("MOUSE_ERR|" + e); return false }
    }
    function mouseText(value) {
        var hits = root.textItems(value)
        if (hits.length === 0) { console.log("MOUSE_ERR|texto ausente: " + value); return false }
        var it = hits[hits.length - 1]
        var p = root.absPos(it)
        return root.mouseAt(p.x + root.nodeW(it) / 2, p.y + root.nodeH(it) / 2)
    }
    // Clique REAL numa fração (fx, fy) do MENOR controle que contém o texto: é
    // como se mira "a parte de baixo da pílula", que é onde a gaveta sobreposta
    // passa por cima. Quem recebe o evento é decisão do Qt, não da sonda.
    function mouseOnControl(value, fx, fy) {
        var hits = root.textItems(value)
        var alvo = null
        for (var i = 0; i < hits.length; i++) {
            var c = root.enclosingControl(hits[i])
            if (c === null) continue
            if (alvo === null || root.nodeW(c) * root.nodeH(c) < root.nodeW(alvo) * root.nodeH(alvo))
                alvo = c
        }
        if (alvo === null) { console.log("MOUSE_ERR|controle ausente: " + value); return false }
        var p = root.absPos(alvo)
        return root.mouseAt(p.x + root.nodeW(alvo) * fx, p.y + root.nodeH(alvo) * fy)
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
        if (!root.visibleOf(it)) return               // invisível: nem ele nem os filhos
        root.nodeId++
        var myId = root.nodeId
        var p = root.absPos(it)
        var txt = ""
        try { if (typeof it.text === "string" && it.text.length > 0) txt = it.text } catch (e) {}
        var clip = 0
        try { clip = (it.clip === true) ? 1 : 0 } catch (e2) {}
        var cor = ""
        try { if (it.color !== undefined && typeof it.text !== "string") cor = String(it.color) } catch (e3) {}
        var op = 1
        try { if (typeof it.opacity === "number") op = it.opacity } catch (e4) {}
        console.log("NODE|" + myId + "|" + parentId + "|" + root.kindOf(it) + "|"
            + JSON.stringify(txt) + "|" + p.x + "|" + p.y + "|"
            + root.nodeW(it) + "|" + root.nodeH(it) + "|" + clip + "|"
            + root.isInteractive(it) + "|" + cor + "|" + op)
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
                     "widthBudget", "heightBudget", "s", "drawerMaxHeight", "pad", "gap"]
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
                later(st.ms || 700, st.name || "open"); return
            } else if (st.op === "mouseAt") {
                root.mouseAt(st.x, st.y)
                later(st.ms || 600, st.name || "mouse"); return
            } else if (st.op === "mouseText") {
                root.mouseText(st.value)
                later(st.ms || 600, st.name || "mouse"); return
            } else if (st.op === "mouseOnControl") {
                root.mouseOnControl(st.value, st.fx === undefined ? 0.5 : st.fx,
                                    st.fy === undefined ? 0.5 : st.fy)
                later(st.ms || 600, st.name || "mouse"); return
            } else if (st.op === "setHeightBudget") {
                root.applyHeightBudget(st.value)
                later(st.ms || 700, st.name || "hb"); return
            } else if (st.op === "poll") {
                service.model = st.model
                later(st.ms || 900, st.name || "poll"); return
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

    Timer { id: mount; interval: 500; repeat: false; onTriggered: root.tick() }
    Timer { id: next; interval: 120; repeat: false; onTriggered: root.tick() }
    Timer {
        id: waitT; repeat: false
        onTriggered: {
            if (root.pendingSnap !== "") root.emitSnap(root.pendingSnap)
            root.pendingSnap = ""
            next.restart()
        }
    }
    Timer { id: nextCase; interval: 100; repeat: false; onTriggered: root.startCase() }
    Timer { id: boot; interval: 300; running: true; repeat: false; onTriggered: root.startCase() }
    Timer {
        id: watchdog; interval: 25000; repeat: false
        onTriggered: {
            console.log("VIEW_ERR|watchdog no caso " + root.caseName)
            root.endCase()
        }
    }
}
