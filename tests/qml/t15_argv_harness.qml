// -*- mode: qml -*-
// Sonda de comportamento de T15 — a setting chega ao argv do coletor?
// (Joseki D5, contexto isolado: não lê a implementação, só observa o efeito.)
//
// Monta um `service/Main.qml` com um `pluginApi` SINTÉTICO e despeja:
//   (a) os campos públicos da instância principal que dizem "houve erro?" e
//   (b) só o que foi RENDERIZADO (textos de nós visíveis).
//
// O ARGV do coletor não é observado aqui: quem o registra é o binário que ocupa
// o lugar do coletor na árvore passada em T15_PLUG_DIR (um gravador instalado
// pelo teste em uma CÓPIA da pasta do plugin). O harness só monta; o teste lê o
// arquivo de registro depois que o processo termina.
//
// Entradas (env):
//   T15_PLUG_DIR    pasta do plugin sob teste (na prática, a CÓPIA com o gravador)
//   T15_SETTINGS    JSON das settings
//   T15_STATE_DIR   stateDir sintético
//   T15_SETTLE_MS   espera antes de despejar (default 3000)
//
// Saída (stdout, um registro por linha; o consumidor parseia por prefixo):
//   MAIN_PRESENT|<true|false>
//   MAIN_ERRORKIND|<valor>|<absent>|<undef>
//   MAIN_LASTERROR|<texto>            (\n escapado)
//   MAIN_LOADING|<true|false>
//   MAIN_MODEL_NULL|<true|false>
//   VIEW_PRESENT|<true|false>
//   TEXT|<texto>
//   VIEW_ERR|<mensagem>
//   END|<motivo>

import QtQuick
import Quickshell

ShellRoot {
    id: root

    property string plugDir: Quickshell.env("T15_PLUG_DIR") || ""
    property int settleMs: parseInt(Quickshell.env("T15_SETTLE_MS") || "3000")
    property var api: null
    property var subject: null
    property bool done: false

    function esc(s) {
        return String(s === undefined || s === null ? "" : s)
            .replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/\r/g, "\\r")
    }

    function mkApi() {
        return {
            pluginSettings: JSON.parse(Quickshell.env("T15_SETTINGS") || "{}"),
            pluginDir: root.plugDir,
            stateDir: Quickshell.env("T15_STATE_DIR") || "/tmp/t15-state",
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

    // `data` inclui children + resources; iterar só `data` visita cada objeto uma vez.
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
            console.log("MAIN_LASTERROR|")
            console.log("MAIN_LOADING|")
            console.log("MAIN_MODEL_NULL|")
            return
        }
        var hasKind = false
        try { hasKind = ("errorKind" in m) } catch (e) { hasKind = false }
        if (!hasKind) console.log("MAIN_ERRORKIND|<undef>")
        else console.log("MAIN_ERRORKIND|" + root.esc(m.errorKind))
        console.log("MAIN_LASTERROR|" + root.esc(m.lastError))
        try { console.log("MAIN_LOADING|" + m.loading) } catch (e) { console.log("MAIN_LOADING|") }
        var mv = null
        try { mv = m.model } catch (e) { mv = null }
        console.log("MAIN_MODEL_NULL|" + (mv === null || mv === undefined || mv === ""))
        // Ordem efetiva dos ids no modelo (canal de OBSERVAÇÃO, só leitura).
        // Sem isto um teste chamado "respeita a ordem" só conseguia provar
        // "não deu erro" — a ordem era invisível para o harness.
        var ordem = ""
        try {
            var all = mv && mv.all ? mv.all : []
            var ids = []
            for (var k = 0; k < all.length; k++) ids.push(String(all[k].id))
            ordem = ids.join(",")
        } catch (e) { ordem = "" }
        console.log("MAIN_ORDER|" + root.esc(ordem))
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

    Timer { id: settle; interval: root.settleMs; repeat: false; onTriggered: root.finish("settle") }
    Timer {
        id: watchdog
        interval: root.settleMs + 12000
        repeat: false
        running: true
        onTriggered: root.finish("watchdog")
    }

    Component.onCompleted: {
        root.api = root.mkApi()
        mainL.source = root.plugDir + "/service/Main.qml"
        mainL.active = true
    }
}
