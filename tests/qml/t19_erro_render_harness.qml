// -*- mode: qml -*-
// Sonda de comportamento de T19 — o texto de erro que CHEGA a um `Text`
// visível, e se a altura do popout muda por causa dele.
// (Joseki D5, contexto isolado: monta a view; não lê content/Widget.qml.)
//
// Monta service/Main.qml + content/Widget.qml de verdade, com um `pluginApi`
// sintético. O `ai-usagebar` do PATH é um FAKE instalado pelo teste: ele decide
// se a sessão termina em relatório (erro POR PROVIDER na tela) ou em falha
// (a linha "NO DATA · <diagnóstico>"). Assim as duas superfícies nomeadas no
// contrato são observadas pelo caminho real, sem depender do upstream.
//
// Um processo por caso, de propósito: o PATH e o relatório são do PROCESSO.
//
// Entradas (env):
//   T19R_PLUG_DIR   pasta do plugin sob teste
//   T19R_STATE_DIR  stateDir sintético
//   T19R_WIDTH      widthBudget do host (default 260)
//   T19R_SETTLE_MS  espera antes de despejar (default 3500)
//
// Saída (stdout, um registro por linha; o consumidor parseia por prefixo):
//   VIEW_PRESENT|<true|false>
//   ROOT_H|<height>|<implicitHeight>          nó raiz da view
//   TEXTOBJ|<JSON>                            um por `Text` com texto não vazio
//        {text,width,height,implicitWidth,implicitHeight,lineCount,wrapMode,
//         elide,pixelSize,truncated,kind}
//   VIEW_ERR|<mensagem>  /  END|<motivo>

import QtQuick
import Quickshell

ShellRoot {
    id: root

    property string plugDir: Quickshell.env("T19R_PLUG_DIR") || ""
    property int settleMs: parseInt(Quickshell.env("T19R_SETTLE_MS") || "3500")
    property int widthBudget: parseInt(Quickshell.env("T19R_WIDTH") || "260")
    property bool done: false

    QtObject {
        id: apiObj
        property var mainInstance: null
        property var pluginSettings: ({
            "accent": "wallpaper", "order": "upstream", "showMetricDetail": true,
            "secondaryLabel": "name", "showSecondaries": true, "maxSecondary": 6,
            "padding": 12, "gap": 6, "pollSeconds": 300
        })
        property string pluginDir: root.plugDir
        property string stateDir: Quickshell.env("T19R_STATE_DIR") || "/tmp/t19r-state"
        property bool panelOpen: false
        function saveSetting(k, v) {}
        function openPanel() {}
        function closePanel() {}
        function togglePanel() {}
    }

    Loader {
        id: mainL
        active: false
        onLoaded: {
            try {
                item.pluginApi = apiObj
                apiObj.mainInstance = item
            } catch (e) { console.log("VIEW_ERR|main: " + e) }
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
                item.widthBudget = root.widthBudget
            } catch (e) { console.log("VIEW_ERR|view: " + e) }
            settle.restart()
        }
    }

    function kindOf(it) { return String(it).replace(/\(0x[0-9a-f]+\)/, "").split("_QML")[0] }
    function poolOf(it) {
        try { return it.data || [] } catch (e) { return it.children || [] }
    }

    function walk(it, depth) {
        if (!it || depth > 18) return
        try {
            if (typeof it.text === "string" && it.text.length > 0) {
                var f = it.font || {}
                console.log("TEXTOBJ|" + JSON.stringify({
                    text: it.text,
                    width: Math.round(it.width * 100) / 100,
                    height: Math.round(it.height * 100) / 100,
                    implicitWidth: Math.round(it.implicitWidth * 100) / 100,
                    implicitHeight: Math.round(it.implicitHeight * 100) / 100,
                    lineCount: (it.lineCount === undefined ? -1 : it.lineCount),
                    wrapMode: (it.wrapMode === undefined ? -1 : it.wrapMode),
                    elide: (it.elide === undefined ? -1 : it.elide),
                    pixelSize: (f.pixelSize === undefined ? -1 : f.pixelSize),
                    truncated: (it.truncated === undefined ? null : it.truncated),
                    kind: root.kindOf(it)
                }))
            }
        } catch (e) { console.log("VIEW_ERR|walk: " + e) }
        var pool = root.poolOf(it)
        for (var i = 0; i < pool.length; i++) root.walk(pool[i], depth + 1)
    }

    function finish(reason) {
        if (root.done) return
        root.done = true
        var v = null
        try { v = viewL.item } catch (e) { v = null }
        console.log("VIEW_PRESENT|" + (v !== null && v !== undefined))
        if (v === null || v === undefined) {
            console.log("VIEW_ERR|a view não montou")
        } else {
            try {
                console.log("ROOT_H|" + (Math.round(v.height * 100) / 100) + "|" +
                    (Math.round((v.implicitHeight === undefined ? -1 : v.implicitHeight) * 100) / 100))
            } catch (e) { console.log("ROOT_H||") }
            try { root.walk(v, 0) } catch (e) { console.log("VIEW_ERR|emit: " + e) }
        }
        console.log("END|" + reason)
        Qt.quit()
    }

    Timer { id: settle; interval: root.settleMs; repeat: false; onTriggered: root.finish("settle") }
    Timer {
        id: watchdog
        interval: root.settleMs + 15000
        repeat: false
        running: true
        onTriggered: root.finish("watchdog")
    }

    Component.onCompleted: {
        mainL.source = root.plugDir + "/service/Main.qml"
        mainL.active = true
    }
}
