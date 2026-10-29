// -*- mode: qml -*-
// Behavior probe for T23 — the PURE reset-time formatting function.
//
// Gerado em contexto isolado (D5) — sem acesso à implementação.
// Base: SPEC rodada 3, tarefa T23.
//
// Why this exists: the T23 done-criterion asks for a PURE formatting function
// exercised at its boundaries (0s, 59s, 59min, 1h, 23h59, 1d, 7d, 30d), not for
// text scraped off the screen. Here the function is CALLED with inputs chosen by
// the test and the RAW result is dumped, so "which branch ran", "was the
// decomposition canonical" and "did it go negative" are observable without ever
// looking at the function body.
//
// service/Main.qml is deliberately NOT mounted: a pure time formatter has
// nothing to do with the collector, and mounting it would make this probe
// depend on PATH, the network and the user's state to answer a question about
// arithmetic over a timestamp.
//
// Inputs (env):
//   T23_PLUG_DIR    plugin folder under test
//   T23_FN_CASES    JSON array of { "name": string, "args": array }
//                   marker {"$null": true}  becomes `null`
//                   marker {"$undef": true} becomes `undefined`
//                   marker {"$num": n}      becomes the number n
//   T23_STATE_DIR   synthetic stateDir
//   T23_SETTLE_MS   wait before calling (default 1200)
//   T23_WIDTH       host widthBudget (default 240)
//
// Output (stdout, one record per line; the consumer parses by prefix):
//   VIEW_PRESENT|<true|false>
//   FN_PROBE|<name>|<true|false>     spelling probe — DIAGNOSTIC ONLY
//   FN_NAME|resetParts|<present|absent>
//   FN_ON_ROOT|<true|false>          the contract says "root Item of the view"
//   FN_HOST|<kind of the object>|<name>
//   FN|<case>|<typeof>|<normalized JSON>|<raw JSON.stringify>
//   FN_THROW|<case>|<message>
//   VIEW_ERR|<message>
//   END|<reason>
//
// The normalized JSON always carries the six contract fields (valid, seconds,
// days, hours, minutes, relative) plus `$keys`, so a QML-declared return object
// (which JSON.stringify flattens to {}) is still observable field by field.
// A field that reads as `undefined` is reported as {"$undefined": true} and a
// NaN as {"$nan": true} — never silently as null.

import QtQuick
import Quickshell

ShellRoot {
    id: root

    property string plugDir: Quickshell.env("T23_PLUG_DIR") || ""
    property var cases: JSON.parse(Quickshell.env("T23_FN_CASES") || "[]")
    property int settleMs: parseInt(Quickshell.env("T23_SETTLE_MS") || "1200")
    property int widthBudget: parseInt(Quickshell.env("T23_WIDTH") || "240")
    property bool done: false

    //: The ONE accepted name, as decided by the interface in the task block.
    property string contractName: "resetParts"

    //: Spellings probed so the report says what WAS found when the contract
    //: name is missing. `cooldown` is the function T23 replaces: finding it and
    //: not `resetParts` is the exact "not implemented yet" signature, and the
    //: failure must say so instead of "NoneType is not callable".
    property var probeNames: [
        "resetParts", "resetTimeParts", "resetBreakdown", "resetRelative",
        "formatReset", "formatResetParts", "resetPartes", "partesReset",
        "partesDoReset", "tempoDeReset", "cooldown", "formatCooldown"
    ]

    // Synthetic pluginApi: the view must be able to instantiate without the real
    // host. Anything the view reads behind a default is fine to omit; what it
    // cannot be is absent.
    QtObject {
        id: apiObj
        property var mainInstance: null
        property var pluginSettings: ({
            "accent": "wallpaper",
            "language": "en",
            "showMetricDetail": true,
            "showSecondaries": true
        })
        property string pluginDir: root.plugDir
        property string stateDir: Quickshell.env("T23_STATE_DIR") || "/tmp/t23-state"
        property bool panelOpen: false
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
                item.density = "full"
                item.widthBudget = root.widthBudget
            } catch (e) { console.log("VIEW_ERR|view: " + e) }
            settle.restart()
        }
        onStatusChanged: {
            if (status === Loader.Error)
                console.log("VIEW_ERR|o Loader não conseguiu carregar a view")
        }
    }

    function kindOf(it) {
        return String(it).replace(/\(0x[0-9a-f]+\)/, "").split("_QML")[0]
    }

    function poolOf(it) {
        try { return it.data || [] } catch (e) { return it.children || [] }
    }

    function findFn(obj, name) {
        try {
            if (obj !== null && obj !== undefined && typeof obj[name] === "function")
                return { owner: obj, name: name }
        } catch (e) {}
        return null
    }

    function search(it, name, depth) {
        if (!it || depth > 12) return null
        var hit = root.findFn(it, name)
        if (hit) return hit
        var pool = root.poolOf(it)
        for (var i = 0; i < pool.length; i++) {
            var r = root.search(pool[i], name, depth + 1)
            if (r) return r
        }
        return null
    }

    function buildArgs(raw) {
        var out = []
        var list = raw || []
        for (var i = 0; i < list.length; i++) {
            var a = list[i]
            if (a !== null && typeof a === "object") {
                if (a.$undef === true) { out.push(undefined); continue }
                if (a.$null === true) { out.push(null); continue }
                if (a.$num !== undefined) { out.push(Number(a.$num)); continue }
            }
            out.push(a)
        }
        return out
    }

    // Reads the six contract fields defensively, so a QML object return value
    // (opaque to JSON.stringify) is still reported field by field.
    function normalize(res) {
        var out = {}
        var fields = ["valid", "seconds", "days", "hours", "minutes", "relative"]
        for (var i = 0; i < fields.length; i++) {
            var k = fields[i]
            var v = undefined
            try { v = res[k] } catch (e) { out[k] = { "$throws": String(e) }; continue }
            if (v === undefined) out[k] = { "$undefined": true }
            else if (typeof v === "number" && isNaN(v)) out[k] = { "$nan": true }
            else out[k] = v
        }
        try { out["$keys"] = Object.keys(res) } catch (e) { out["$keys"] = null }
        return out
    }

    function run() {
        var v = null
        try { v = viewL.item } catch (e) { v = null }
        console.log("VIEW_PRESENT|" + (v !== null && v !== undefined))
        if (v === null || v === undefined) {
            console.log("FN_PROBE|" + root.contractName + "|false")
            console.log("FN_NAME|" + root.contractName + "|absent")
            console.log("FN_ON_ROOT|false")
            console.log("VIEW_ERR|a view não montou")
            finish("sem view")
            return
        }

        // Spelling probe: reported, never accepted in place of the contract name.
        for (var c = 0; c < root.probeNames.length; c++) {
            var found = root.search(v, root.probeNames[c], 0)
            console.log("FN_PROBE|" + root.probeNames[c] + "|" + (found !== null))
        }

        var onRoot = root.findFn(v, root.contractName) !== null
        console.log("FN_ON_ROOT|" + onRoot)

        var hit = root.search(v, root.contractName, 0)
        if (hit === null) {
            console.log("FN_NAME|" + root.contractName + "|absent")
            finish("função ausente")
            return
        }
        console.log("FN_HOST|" + root.kindOf(hit.owner) + "|" + hit.name)
        console.log("FN_NAME|" + root.contractName + "|present")

        for (var i = 0; i < root.cases.length; i++) {
            var cs = root.cases[i]
            var args = root.buildArgs(cs.args)
            var res = undefined
            try {
                res = hit.owner[hit.name].apply(hit.owner, args)
            } catch (e) {
                console.log("FN_THROW|" + cs.name + "|" + String(e))
                continue
            }
            var raw = ""
            try { raw = JSON.stringify(res) } catch (e) { raw = "<stringify falhou>" }
            var norm = ""
            try { norm = JSON.stringify(root.normalize(res)) } catch (e) { norm = "<normalize falhou>" }
            console.log("FN|" + cs.name + "|" + typeof res + "|" + norm + "|" + raw)
        }
        finish("casos")
    }

    function finish(reason) {
        if (root.done) return
        root.done = true
        console.log("END|" + reason)
        Qt.quit()
    }

    Timer { id: settle; interval: root.settleMs; repeat: false; onTriggered: root.run() }

    Timer {
        id: watchdog
        interval: root.settleMs + 20000
        repeat: false
        running: true
        onTriggered: {
            console.log("VIEW_ERR|watchdog: a view não montou")
            console.log("FN_NAME|" + root.contractName + "|absent")
            root.finish("watchdog")
        }
    }

    Component.onCompleted: {
        // Synthetic main instance: no model, no error, no collector.
        apiObj.mainInstance = {
            model: null, loading: false, lastError: "", errorKind: ""
        }
        viewL.setSource(root.plugDir + "/content/Widget.qml")
        viewL.active = true
    }
}
