// -*- mode: qml -*-
// Sonda de comportamento de settings do plugin ai-usage (Joseki D5, contexto isolado).
//
// Monta service/Main.qml + content/Widget.qml com um `pluginApi` SINTÉTICO e
// despeja somente o que a view RENDERIZA, para cada conjunto de settings. Não lê
// nem depende de detalhe interno: observa o resultado montado (texto, cor,
// fonte, espaçamento, geometria).
//
// Entradas (env):
//   T9_CASES      JSON array de { "name": string, "settings": object }
//   T9_PLUG_DIR   pasta do plugin (o avaliador aponta para a árvore sob teste)
//   T9_STATE_DIR  stateDir sintético (default /tmp/t9-state)
//
// Saída (stdout, uma linha por registro; o consumidor parseia por prefixo):
//   SINGLETON|<accent>|<sun>|<cream>|<gold>     cores do host no momento do caso
//   ===CASE_START|<name>=== / ===CASE_END|<name>===
//   LPAD|<n>                                     padding do nó raiz da view
//   SPACING|<tipo>|<spacing>
//   TEXT|<texto>|<família>|<pixelSize>|<letterSpacing>|<capitalization>
//   FILL|<#rrggbb>|<alpha>|<tipo>|<radius>       preenchimento (alpha >= 0.99)
//   TRACK|<#rrggbb>|<alpha>|<tipo>|<radius>      trilho (0.05 < alpha < 0.25)
//   HAIR|<#rrggbb>|<alpha>|<tipo>|<radius>       fio (0.25 <= alpha < 0.5)
//   RECT|<tipo>|<w>x<h>|r=<radius>|pill=<bool>|chamfer=<bool>|a=<alpha>
//   INTERACTIVE|<tipo>|<w>x<h>|r=<radius>        MouseArea/Handler/Botão na árvore
//   KIND|<tipo>|<n>                              censo de tipos montados

import QtQuick
import Quickshell
import Ryoku.PluginKit.Singletons

ShellRoot {
    id: root

    property var cases: JSON.parse(Quickshell.env("T9_CASES") || "[]")
    property string plugDir: Quickshell.env("T9_PLUG_DIR") || ""
    property int idx: 0
    property var api: null

    function mkApi(st) {
        return {
            pluginSettings: st,
            pluginDir: root.plugDir,
            stateDir: Quickshell.env("T9_STATE_DIR") || "/tmp/t9-state",
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
            try { item.pluginApi = root.api; root.api.mainInstance = item } catch (e) {}
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
            } catch (e) { console.log("VIEW_ERR|" + e) }
            settle.restart()
        }
    }

    function beginCase() {
        if (root.idx >= root.cases.length) { Qt.quit(); return }
        root.api = root.mkApi(root.cases[root.idx].settings)
        viewL.active = false; viewL.setSource("")
        mainL.active = false; mainL.setSource("")
        mainL.source = root.plugDir + "/service/Main.qml"
        mainL.active = true
        watchdog.restart()
    }

    Timer { id: boot; interval: 350; running: true; onTriggered: root.beginCase() }

    Timer {
        id: settle; interval: 950; repeat: false
        onTriggered: {
            watchdog.stop()
            root.emit(root.cases[root.idx].name)
            viewL.active = false; viewL.setSource("")
            mainL.active = false; mainL.setSource("")
            root.idx++
            nextCase.restart()
        }
    }
    Timer { id: nextCase; interval: 180; repeat: false; onTriggered: root.beginCase() }

    // Watchdog: um caso que não monta (entrada ausente no caminho revertido, por
    // exemplo) precisa FALHAR rápido, não pendurar o processo até o timeout.
    Timer {
        id: watchdog
        interval: 8000
        repeat: false
        onTriggered: {
            console.log("===CASE_START|" + root.cases[root.idx].name + "===")
            console.log("VIEW_ERR|não montou em 8s (entrada ausente ou quebrada)")
            console.log("===CASE_END|" + root.cases[root.idx].name + "===")
            console.log("WATCHDOG_ABORT|" + root.cases[root.idx].name)
            Qt.quit()
        }
    }

    function hex(c) {
        if (c === undefined || c === null) return ""
        if (typeof c === "string") return c
        if (c.r !== undefined) {
            function q(v) { var n = Math.round(v * 255).toString(16); return n.length < 2 ? "0" + n : n }
            return "#" + q(c.r) + q(c.g) + q(c.b)
        }
        return String(c)
    }

    function kindOf(it) { return String(it).replace(/\(0x[0-9a-f]+\)/, "") }
    function alphaOf(it) {
        try { return (it.color && it.color.a !== undefined) ? it.color.a : 1 } catch (e) { return 1 }
    }

    // Em QML, `data` JÁ inclui `children` (visuais) + resources (não visuais:
    // Behavior, Timer). Iterar só `data` percorre cada objeto exatamente uma vez.
    function poolOf(it) {
        try { return it.data || [] } catch (e) { return it.children || [] }
    }

    function walk(it, depth) {
        if (!it || depth > 16) return
        try {
            if (it.visible !== false && it.opacity !== 0) {
                var kind = root.kindOf(it)
                if (typeof it.text === "string" && it.text.length > 0) {
                    var f = it.font || {}
                    console.log("TEXT|" + it.text + "|" + (f.family === undefined ? "" : f.family)
                        + "|" + (f.pixelSize === undefined ? "" : f.pixelSize)
                        + "|" + (f.letterSpacing === undefined ? 0 : f.letterSpacing)
                        + "|" + (f.capitalization === undefined ? 0 : f.capitalization))
                }
                if (kind.indexOf("Rectangle") >= 0 && it.radius !== undefined) {
                    var a = root.alphaOf(it)
                    console.log("RECT|" + kind + "|" + Math.round(it.width) + "x" + Math.round(it.height)
                        + "|r=" + it.radius + "|pill=" + (it.height > 0 && Math.abs(it.radius - it.height / 2) < 0.01)
                        + "|chamfer=" + (it.radius > 0 && it.height > 0 && it.radius < it.height / 2)
                        + "|a=" + a.toFixed(2))
                    if (it.color !== undefined) {
                        var line = "|" + root.hex(it.color) + "|" + a.toFixed(2) + "|" + kind + "|" + it.radius
                        if (a >= 0.99) console.log("FILL" + line)
                        else if (a > 0.05 && a < 0.25) console.log("TRACK" + line)
                        else if (a >= 0.25 && a < 0.5) console.log("HAIR" + line)
                    }
                }
                if (it.spacing !== undefined) console.log("SPACING|" + kind + "|" + it.spacing)
                if (kind.indexOf("Timer") >= 0) console.log("TIMER|" + kind + "|interval=" + it.interval + "|running=" + it.running + "|repeat=" + it.repeat)
                if (/MouseArea|TapHandler|HoverHandler|AbstractButton|DragHandler|WheelHandler/.test(kind))
                    console.log("INTERACTIVE|" + kind + "|" + Math.round(it.width) + "x" + Math.round(it.height) + "|r=" + it.radius)
            }
        } catch (e) {}
        var pool = root.poolOf(it)
        for (var m = 0; m < pool.length; m++) root.walk(pool[m], depth + 1)
    }

    function census(it, depth, acc) {
        if (!it || depth > 16) return
        var k = root.kindOf(it)
        acc[k] = (acc[k] || 0) + 1
        var pool = root.poolOf(it)
        for (var m = 0; m < pool.length; m++) root.census(pool[m], depth + 1, acc)
    }

    function emit(name) {
        console.log("SINGLETON|" + root.hex(Theme.accent) + "|" + root.hex(Theme.sun)
            + "|" + root.hex(Theme.cream) + "|" + root.hex(Theme.gold))
        console.log("===CASE_START|" + name + "===")
        try {
            var v = viewL.item
            if (v && v.pad !== undefined) console.log("LPAD|" + v.pad)
            var acc = {}
            root.census(v, 0, acc)
            for (var k in acc) console.log("KIND|" + k + "|" + acc[k])
            root.walk(v, 0)
        } catch (e) { console.log("EMIT_ERR|" + e) }
        console.log("===CASE_END|" + name + "===")
    }
}
