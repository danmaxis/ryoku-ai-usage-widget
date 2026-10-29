// -*- mode: qml -*-
// Sonda de comportamento de T16 — qual é o default EFETIVO do layout?
// (Joseki D5, contexto isolado: monta a view e mede a GEOMETRIA desenhada; não
// lê content/Widget.qml nem service/Main.qml.)
//
// Por que existe: comparar `manifest[...].default` com o literal do QML seria
// reler o manifest duas vezes e passar sem exercitar código. Aqui o valor
// efetivo é medido no nó raiz da view já montada, de modo que "store vazio"
// (entrada antiga sem a chave) possa ser comparado com "store semeado no
// default" — que é exatamente a divergência que T16 corrige.
//
// Entradas (env):
//   T16_CASES     JSON array de { "name": string, "settings": object }
//                 `settings` é o objeto entregue como pluginSettings; {} = store vazio
//   T16_PLUG_DIR  pasta do plugin sob teste
//   T16_STATE_DIR stateDir sintético
//   T16_SETTLE_MS espera por caso antes de despejar (default 1600)
//
// Saída (stdout, um registro por linha; o consumidor parseia por prefixo):
//   ===CASE_START|<name>===   /   ===CASE_END|<name>===
//   VIEW_PRESENT|<true|false>
//   LPAD|<n>                        `pad` público da view, se existir
//   ROOT_GEOM|<x>,<y>|<w>x<h>       geometria do nó raiz da view
//   SPACING|<tipo>|<spacing>|d<depth>
//   TEXT|<texto>
//   VIEW_ERR|<mensagem>  /  WATCHDOG_ABORT|<name>

import QtQuick
import Quickshell

ShellRoot {
    id: root

    property var cases: JSON.parse(Quickshell.env("T16_CASES") || "[]")
    property string plugDir: Quickshell.env("T16_PLUG_DIR") || ""
    property int settleMs: parseInt(Quickshell.env("T16_SETTLE_MS") || "1600")
    property int idx: 0

    // Forma do api do host (PluginPopouts.qml:195 é `property var pluginSettings`):
    // uma propriedade QML com sinal de notificação, não um objeto JS cru.
    QtObject {
        id: apiObj
        property var mainInstance: null
        property var pluginSettings: ({})
        property string pluginDir: root.plugDir
        property string stateDir: Quickshell.env("T16_STATE_DIR") || "/tmp/t16-state"
        property bool panelOpen: false
        function saveSetting(k, v) {}
        function saveSettings() {}
        function openPanel() {}
        function closePanel() {}
        function togglePanel() {}
    }

    function esc(s) {
        return String(s === undefined || s === null ? "" : s)
            .replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/\r/g, "\\r")
    }
    function kindOf(it) { return String(it).replace(/\(0x[0-9a-f]+\)/, "") }
    function poolOf(it) {
        try { return it.data || [] } catch (e) { return it.children || [] }
    }

    Loader {
        id: mainL
        active: false
        onLoaded: {
            try { item.pluginApi = apiObj; apiObj.mainInstance = item } catch (e) {}
            viewL.setSource(root.plugDir + "/content/Widget.qml")
            viewL.active = true
        }
    }

    Loader {
        id: viewL
        active: false
        onLoaded: {
            try {
                item.pluginApi = apiObj
                item.s = 1
                item.active = true
                item.density = "full"
                item.widthBudget = 900
            } catch (e) { console.log("VIEW_ERR|view: " + e) }
            settle.restart()
        }
    }

    function walk(it, depth) {
        if (!it || depth > 16) return
        try {
            if (it.spacing !== undefined)
                console.log("SPACING|" + root.kindOf(it) + "|" + it.spacing + "|d" + depth)
            if (typeof it.text === "string" && it.text.length > 0)
                console.log("TEXT|" + root.esc(it.text))
        } catch (e) { console.log("VIEW_ERR|walk: " + e) }
        var pool = root.poolOf(it)
        for (var i = 0; i < pool.length; i++) root.walk(pool[i], depth + 1)
    }

    function emit(name) {
        console.log("===CASE_START|" + name + "===")
        var v = null
        try { v = viewL.item } catch (e) { v = null }
        console.log("VIEW_PRESENT|" + (v !== null && v !== undefined))
        if (v === null || v === undefined) {
            console.log("VIEW_ERR|a view não montou")
        } else {
            try { if (v.pad !== undefined) console.log("LPAD|" + v.pad) } catch (e) {}
            try {
                console.log("ROOT_GEOM|" + v.x + "," + v.y + "|" + v.width + "x" + v.height)
            } catch (e) {}
            try { root.walk(v, 0) } catch (e) { console.log("VIEW_ERR|emit: " + e) }
        }
        console.log("===CASE_END|" + name + "===")
    }

    function beginCase() {
        if (root.idx >= root.cases.length) { Qt.quit(); return }
        apiObj.pluginSettings = root.cases[root.idx].settings || {}
        viewL.active = false; viewL.setSource("")
        mainL.active = false; mainL.setSource("")
        mainL.source = root.plugDir + "/service/Main.qml"
        mainL.active = true
        watchdog.restart()
    }

    Timer { id: boot; interval: 400; running: true; onTriggered: root.beginCase() }

    Timer {
        id: settle; interval: root.settleMs; repeat: false
        onTriggered: {
            watchdog.stop()
            root.emit(root.cases[root.idx].name)
            viewL.active = false; viewL.setSource("")
            mainL.active = false; mainL.setSource("")
            root.idx++
            nextCase.restart()
        }
    }
    Timer { id: nextCase; interval: 250; repeat: false; onTriggered: root.beginCase() }

    Timer {
        id: watchdog
        interval: 15000
        repeat: false
        onTriggered: {
            console.log("===CASE_START|" + root.cases[root.idx].name + "===")
            console.log("VIEW_ERR|não montou em 15s")
            console.log("WATCHDOG_ABORT|" + root.cases[root.idx].name)
            console.log("===CASE_END|" + root.cases[root.idx].name + "===")
            Qt.quit()
        }
    }
}
