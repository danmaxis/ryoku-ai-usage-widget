// -*- mode: qml -*-
// Sonda de comportamento de T13 — estado "binário ausente" vs falha do upstream.
// (Joseki D5, contexto isolado: não lê a implementação, só observa o que renderiza.)
//
// Monta service/Main.qml + content/Widget.qml com um `pluginApi` sintético e
// despeja (a) o que a VIEW renderiza e (b) os campos públicos da instância
// principal (`errorKind`, `lastError`, `loading`, `model`), que são o contrato
// declarado da tarefa.
//
// UM processo quickshell por caso, de propósito: o PATH que decide se o
// `ai-usagebar` existe é do PROCESSO, não do QML — cada caso precisa do seu.
//
// Entradas (env):
//   T13_PLUG_DIR    pasta do plugin sob teste
//   T13_MODE        "real" (monta Main.qml, deixa o coletor de verdade rodar)
//                   | "stub" (injeta um mainInstance sintético)
//   T13_SETTINGS    JSON das settings
//   T13_STATE_DIR   stateDir sintético
//   T13_MODEL       JSON do model (só no modo stub; "" => null)
//   T13_LOADING     "1"/"0" (só no modo stub)
//   T13_ERRORKIND   valor de errorKind injetado (só no modo stub)
//   T13_LASTERROR   valor de lastError injetado (só no modo stub)
//   T13_SETTLE_MS   tempo de espera antes de despejar (default 2500)
//
// Saída (stdout, um registro por linha; o consumidor parseia por prefixo):
//   MAIN_PRESENT|<true|false>
//   MAIN_ERRORKIND|<valor>            (ou <undef> se a propriedade não existe)
//   MAIN_ERRORKIND_TYPE|<qml type>
//   MAIN_LASTERROR|<texto>            (\n escapado)
//   MAIN_LOADING|<true|false>
//   MAIN_MODEL_NULL|<true|false>
//   VIEW_PRESENT|<true|false>
//   VIEW_ERR|<mensagem>               (erro de montagem/renderização)
//   TEXT|<texto>                      (texto realmente renderizado)
//   END|<motivo>

import QtQuick
import Quickshell

ShellRoot {
    id: root

    property string plugDir: Quickshell.env("T13_PLUG_DIR") || ""
    property string mode: Quickshell.env("T13_MODE") || "real"
    property int settleMs: parseInt(Quickshell.env("T13_SETTLE_MS") || "2500")
    property var api: null
    property var subject: null      // instância principal observada (real ou stub)
    property bool done: false

    function esc(s) {
        return String(s === undefined || s === null ? "" : s)
            .replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/\r/g, "\\r")
    }

    function mkApi() {
        return {
            pluginSettings: JSON.parse(Quickshell.env("T13_SETTINGS") || "{}"),
            pluginDir: root.plugDir,
            stateDir: Quickshell.env("T13_STATE_DIR") || "/tmp/t13-state",
            saveSetting: function (k, v) {},
            panelOpen: false,
            openPanel: function () {},
            closePanel: function () {},
            togglePanel: function () {}
        }
    }

    Loader {
        id: mainL
        active: false
        onLoaded: {
            try {
                item.pluginApi = root.api
                root.api.mainInstance = item
                root.subject = item
            } catch (e) { console.log("VIEW_ERR|main pluginApi: " + e) }
            viewL.setSource(root.plugDir + "/content/Widget.qml")
            viewL.active = true
        }
    }

    Loader {
        id: viewL
        active: false
        onLoaded: {
            try {
                item.pluginApi = root.api
                item.s = 1
                item.active = true
                item.density = "full"
                item.widthBudget = 900
            } catch (e) { console.log("VIEW_ERR|view: " + e) }
            settle.restart()
        }
    }

    // Percorre a árvore montada e despeja só o que foi RENDERIZADO.
    // `data` já inclui children (visuais) + resources; iterar só `data` visita
    // cada objeto uma vez.
    function walk(it, depth) {
        if (!it || depth > 20) return
        try {
            if (it.visible !== false && it.opacity !== 0) {
                if (typeof it.text === "string" && it.text.length > 0)
                    console.log("TEXT|" + root.esc(it.text))
            }
        } catch (e) { console.log("VIEW_ERR|walk: " + e) }
        var pool = []
        try { pool = it.data || it.children || [] } catch (e) { pool = [] }
        for (var i = 0; i < pool.length; i++) root.walk(pool[i], depth + 1)
    }

    function dumpMain() {
        var m = root.subject
        console.log("MAIN_PRESENT|" + (m !== null && m !== undefined))
        if (m === null || m === undefined) {
            console.log("MAIN_ERRORKIND|<nomains>")
            console.log("MAIN_ERRORKIND_TYPE|<nomains>")
            console.log("MAIN_LASTERROR|")
            console.log("MAIN_LOADING|")
            console.log("MAIN_MODEL_NULL|")
            return
        }
        var hasKind = false
        try { hasKind = ("errorKind" in m) } catch (e) { hasKind = false }
        if (!hasKind) {
            console.log("MAIN_ERRORKIND|<undef>")
            console.log("MAIN_ERRORKIND_TYPE|<absent>")
        } else {
            console.log("MAIN_ERRORKIND|" + root.esc(m.errorKind))
            console.log("MAIN_ERRORKIND_TYPE|" + typeof m.errorKind)
        }
        console.log("MAIN_LASTERROR|" + root.esc(m.lastError))
        console.log("MAIN_LOADING|" + m.loading)
        var mv = null
        try { mv = m.model } catch (e) { mv = null }
        console.log("MAIN_MODEL_NULL|" + (mv === null || mv === undefined || mv === ""))
    }

    function finish(reason) {
        if (root.done) return
        root.done = true
        root.dumpMain()
        var v = null
        try { v = viewL.item } catch (e) { v = null }
        console.log("VIEW_PRESENT|" + (v !== null && v !== undefined))
        if (v === null || v === undefined) {
            console.log("VIEW_ERR|a view não montou")
        } else {
            try { root.walk(v, 0) } catch (e) { console.log("VIEW_ERR|emit: " + e) }
        }
        console.log("END|" + reason)
        Qt.quit()
    }

    Timer {
        id: settle
        interval: root.settleMs
        repeat: false
        onTriggered: root.finish("settle")
    }

    // Watchdog: um caso que não monta precisa FALHAR rápido, não pendurar.
    Timer {
        id: watchdog
        interval: root.settleMs + 12000
        repeat: false
        running: true
        onTriggered: root.finish("watchdog")
    }

    Component.onCompleted: {
        root.api = root.mkApi()
        if (root.mode === "stub") {
            var raw = Quickshell.env("T13_MODEL") || ""
            var mv = null
            try { mv = raw === "" ? null : JSON.parse(raw) } catch (e) { mv = null }
            root.api.mainInstance = {
                model: mv,
                loading: (Quickshell.env("T13_LOADING") || "0") === "1",
                lastError: Quickshell.env("T13_LASTERROR") || "",
                errorKind: Quickshell.env("T13_ERRORKIND") || ""
            }
            root.subject = root.api.mainInstance
            viewL.setSource(root.plugDir + "/content/Widget.qml")
            viewL.active = true
        } else {
            mainL.source = root.plugDir + "/service/Main.qml"
            mainL.active = true
        }
    }
}
