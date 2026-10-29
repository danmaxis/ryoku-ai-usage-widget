// -*- mode: qml -*-
// Sonda de comportamento de T16 — o argv que o SERVIÇO monta para o coletor,
// e o que muda quando uma setting muda com o serviço VIVO.
// (Joseki D5, contexto isolado: não lê service/Main.qml nem content/Widget.qml.)
//
// Dois canais, ambos de observação:
//   (a) ARGV — quem registra é o GRAVADOR que o teste instala no lugar de
//       `bin/ai-usage-collect` na CÓPIA do plugin; esta sonda só monta a árvore.
//       Uma linha JSON por invocação, com `n` = ordinal da invocação.
//   (b) VIEW — os textos efetivamente renderizados ANTES e DEPOIS da mutação,
//       para que "re-coletou" possa ser conferido no que o usuário vê.
//
// Entradas (env):
//   T16_PLUG_DIR    pasta do plugin sob teste (na prática, a CÓPIA com o gravador)
//   T16_SETTINGS    JSON das settings iniciais
//   T16_PATCHES     JSON array de patches aplicados em sequência ("" = nenhum)
//   T16_STATE_DIR   stateDir sintético
//   T16_FIRST_MS    espera antes da 1ª mutação (default 2600)
//   T16_SETTLE_MS   espera depois de CADA mutação (default 3000)
//
// Saída (stdout, um registro por linha):
//   MOUNTED|<true|false>
//   BEFORE_MUTATE|<ms>            /  AFTER_MUTATE|<ms>
//   BEFORE_SETTINGS|<json>        /  AFTER_SETTINGS|<json>
//   BEFORE_TEXTS|<textos>         /  AFTER_TEXTS|<textos>   (\u001f separa)
//   PATCHED|<ordinal>|<json>
//   VIEW_ERR|<mensagem>   /  END|<motivo>

import QtQuick
import Quickshell

ShellRoot {
    id: root

    property string plugDir: Quickshell.env("T16_PLUG_DIR") || ""
    property var settings: JSON.parse(Quickshell.env("T16_SETTINGS") || "{}")
    property var patches: JSON.parse(Quickshell.env("T16_PATCHES") || "[]")
    property int patchIdx: 0
    property int firstMs: parseInt(Quickshell.env("T16_FIRST_MS") || "2600")
    property int settleMs: parseInt(Quickshell.env("T16_SETTLE_MS") || "3000")
    property var t0: Date.now()
    property bool done: false

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
        }
    }

    function esc(s) {
        return String(s === undefined || s === null ? "" : s)
            .replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/\r/g, "\\r")
    }
    function poolOf(it) {
        try { return it.data || [] } catch (e) { return it.children || [] }
    }
    function collect(it, depth, acc) {
        if (!it || depth > 16) return
        try {
            if (it.visible !== false && it.opacity !== 0
                    && typeof it.text === "string" && it.text.length > 0)
                acc.push(it.text)
        } catch (e) {}
        var pool = root.poolOf(it)
        for (var i = 0; i < pool.length; i++) root.collect(pool[i], depth + 1, acc)
    }

    // Canais de observação da view, sem julgar nada.
    function dumpView(tag) {
        var v = null
        try { v = viewL.item } catch (e) { v = null }
        if (v === null || v === undefined) {
            console.log(tag + "_TEXTS|<nomount>")
            return
        }
        var acc = []
        try { root.collect(v, 0, acc) } catch (e) { console.log("VIEW_ERR|collect: " + e) }
        console.log(tag + "_TEXTS|" + root.esc(acc.join("\u001f")))
    }

    function merged(patch) {
        var out = {}
        var atual = apiObj.pluginSettings || {}
        for (var k in atual) out[k] = atual[k]
        for (var j in patch) out[j] = patch[j]
        return out
    }

    function afterFirstSettle() {
        console.log("MOUNTED|" + (mainL.item !== null && mainL.item !== undefined))
        console.log("BEFORE_MUTATE|" + (Date.now() - root.t0))
        console.log("BEFORE_SETTINGS|" + JSON.stringify(apiObj.pluginSettings))
        root.dumpView("BEFORE")
        if (root.patches.length === 0) { root.finish("sem-mutacao"); return }
        root.nextPatch()
    }

    function nextPatch() {
        if (root.patchIdx >= root.patches.length) {
            console.log("AFTER_MUTATE|" + (Date.now() - root.t0))
            console.log("AFTER_SETTINGS|" + JSON.stringify(apiObj.pluginSettings))
            root.dumpView("AFTER")
            root.finish("patches-fim")
            return
        }
        var patch = root.patches[root.patchIdx]
        root.patchIdx++
        // Referência NOVA, como o host entrega quando plugins.json muda
        // (`pluginSettings` re-deriva de `place.settings`).
        apiObj.pluginSettings = root.merged(patch)
        console.log("PATCHED|" + root.patchIdx + "|" + JSON.stringify(apiObj.pluginSettings))
        patchTimer.restart()
    }

    function finish(reason) {
        if (root.done) return
        root.done = true
        console.log("END|" + reason)
        Qt.quit()
    }

    Timer { id: boot; interval: 400; running: true; onTriggered: root.start() }

    function start() {
        apiObj.pluginSettings = root.settings
        mainL.source = root.plugDir + "/service/Main.qml"
        mainL.active = true
        first.restart()
    }

    Timer { id: first; interval: root.firstMs; repeat: false; onTriggered: root.afterFirstSettle() }
    Timer { id: patchTimer; interval: root.settleMs; repeat: false; onTriggered: root.nextPatch() }

    Timer {
        id: watchdog
        interval: root.firstMs + root.settleMs * Math.max(1, root.patches.length) + 20000
        repeat: false
        running: true
        onTriggered: root.finish("watchdog")
    }
}
