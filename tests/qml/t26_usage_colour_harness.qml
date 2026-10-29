// -*- mode: qml -*-
// Behavior probe for T26 — the PURE semantic colour scale (usageColour et al.).
//
// Gerado em contexto isolado (D5) — sem acesso à implementação.
// Base: SPEC rodada 3, tarefa T26.
//
// Why this exists: the T26 done-criterion asks for a pure function exercised at
// its band boundaries (0, 59, 60, 84, 85, 99, 100, >100), for an invalid percent
// and an invalid/absurd accent, and for the "a pastel peach is NOT an alarm"
// rule. None of that is readable off the screen, and none of it may be judged by
// reading the function body. Here the functions are CALLED with inputs chosen by
// the Python test and the RAW result is dumped, so band membership, channel
// finiteness, hue/saturation and "did it throw" are observable without ever
// looking at content/Widget.qml.
//
// service/Main.qml is deliberately NOT mounted: a pure colour function has
// nothing to do with the collector, and mounting it would make this probe depend
// on PATH, the network and the user's state to answer a question about colours.
//
// Inputs (env):
//   T26_PLUG_DIR    plugin folder under test
//   T26_CASES       JSON array of { "name": string, "role": string, "args": array }
//                   role: "usage" | "danger" | "neutral" | "valid" | "dangerOfUsage"
//                   ("dangerOfUsage" is COMPOSED: isDangerHue(usageColour(p, accent)),
//                    i.e. "would the colour the bar paints for this usage be read
//                    as an alarm by the same module?". Without it the question
//                    could only be answered by copying the band colours here.)
//                   argument markers (a bare object with the marker key):
//                     {"$null": true}      ->`null`
//                     {"$undef": true}     ->`undefined`
//                     {"$nan": true}       ->`NaN`
//                     {"$num": n}          -> the number n
//                     {"$color": "#rrggbb"}-> a REAL QML colour object (Qt.rgba)
//                     {"$hsla": [h,s,l,a]} -> a REAL QML colour object (Qt.hsla)
//                   anything else is passed through as-is (a JSON string stays a
//                   JS string on purpose: the contract says a string accent must
//                   be treated as an INVALID accent).
//   T26_STATE_DIR   synthetic stateDir
//   T26_SETTLE_MS   wait before calling (default 1200)
//   T26_WIDTH       host widthBudget (default 240)
//
// Output (stdout, one record per line; the consumer parses by prefix):
//   VIEW_PRESENT|<true|false>
//   FN_PROBE|<role>|<candidate spelling>|<true|false>   DIAGNOSTIC ONLY
//   FN_ROLE|<role>|<name found or <absent>>|<present|absent>
//   FN_HOST|<role>|<kind of the hosting object>|<name>
//   FN|<role>|<case>|<typeof result>|<normalized JSON>
//   FN_THROW|<role>|<case>|<message>
//   VIEW_ERR|<message>
//   END|<reason>
//
// Why the normalized JSON and not JSON.stringify(result) alone: a QML `color`
// is not a plain JS object in every Qt build — in some it stringifies to `{}`.
// The normalizer therefore reads r/g/b/a, the HSL/HSV components, `valid` and
// `String(c)` ONE AT A TIME, and reports a non-number/NaN/undefined channel as a
// marker instead of silently printing `null`. `$type` and `$keys` are kept so the
// report says what the value actually was.

import QtQuick
import Quickshell

ShellRoot {
    id: root

    property string plugDir: Quickshell.env("T26_PLUG_DIR") || ""
    property var cases: JSON.parse(Quickshell.env("T26_CASES") || "[]")
    property int settleMs: parseInt(Quickshell.env("T26_SETTLE_MS") || "1200")
    property int widthBudget: parseInt(Quickshell.env("T26_WIDTH") || "240")
    property bool done: false

    //: The spellings accepted per role. The interface block names the functions
    //: in English (`usageColour`, `isDangerHue`, `neutralColour`, `validColour`)
    //: while the SPEC's done-criterion line still says `corDoUso` — both are
    //: probed and the one that EXISTS is reported, never accepted silently: the
    //: suite requires at least one and prints which answered.
    property var roleCandidates: ({
        "usage": ["usageColour", "usageColor", "corDoUso", "corDeUso", "colourForUsage", "usageColourFor"],
        "danger": ["isDangerHue", "isDangerColour", "isDangerColor", "isDanger", "dangerHue", "ehCorDePerigo", "corDePerigo"],
        "neutral": ["neutralColour", "neutralColor", "corNeutra", "corNeutro"],
        "valid": ["validColour", "validColor", "corValida", "corValido", "isValidColour", "isValidColor"],
        //: Same spellings as "danger": the composed role reuses isDangerHue.
        "dangerOfUsage": ["isDangerHue", "isDangerColour", "isDangerColor", "isDanger", "dangerHue", "ehCorDePerigo", "corDePerigo"]
    })

    property var roles: ["usage", "danger", "neutral", "valid", "dangerOfUsage"]
    property var resolved: ({})     // role -> { owner, name }

    // Synthetic pluginApi: the view must instantiate without the real host.
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
        property string stateDir: Quickshell.env("T26_STATE_DIR") || "/tmp/t26-state"
        property bool panelOpen: false
        function saveSetting(k, v) {}
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
        try {
            return String(it).replace(/\(0x[0-9a-f]+\)/, "").split("_QML")[0]
        } catch (e) { return "<?" + e + ">" }
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

    // A REAL QML colour object from "#rrggbb" / "#rrggbbaa": channels are handed
    // to Qt.rgba, so the value is a colour — unlike the raw string, which the
    // contract says must be treated as an invalid accent.
    function hexToColour(h) {
        var s = String(h).replace("#", "")
        if (s.length === 3)
            s = s[0] + s[0] + s[1] + s[1] + s[2] + s[2]
        var a = 1
        if (s.length === 8) { a = parseInt(s.substring(6, 8), 16) / 255; s = s.substring(0, 6) }
        if (s.length !== 6) return null
        return Qt.rgba(parseInt(s.substring(0, 2), 16) / 255,
                       parseInt(s.substring(2, 4), 16) / 255,
                       parseInt(s.substring(4, 6), 16) / 255,
                       a)
    }

    function buildArgs(raw) {
        var out = []
        var list = raw || []
        for (var i = 0; i < list.length; i++) {
            var a = list[i]
            if (a !== null && typeof a === "object") {
                if (a.$undef === true) { out.push(undefined); continue }
                if (a.$null === true) { out.push(null); continue }
                if (a.$nan === true) { out.push(NaN); continue }
                if (a.$num !== undefined) { out.push(Number(a.$num)); continue }
                if (a.$color !== undefined) { out.push(root.hexToColour(a.$color)); continue }
                if (a.$hsla !== undefined) {
                    var p = a.$hsla
                    out.push(Qt.hsla(p[0], p[1], p[2], p.length > 3 ? p[3] : 1))
                    continue
                }
            }
            out.push(a)
        }
        return out
    }

    function numOf(v) {
        if (typeof v !== "number") return { "$notNumber": typeof v }
        if (isNaN(v)) return { "$nan": true }
        if (!isFinite(v)) return { "$infinity": true }
        return v
    }

    // Reads a colour ONE FIELD AT A TIME — never trusting JSON.stringify alone.
    function normalize(res) {
        var out = { "$type": typeof res }
        if (res === undefined) { out["$undefined"] = true; return out }
        if (res === null) { out["$null"] = true; return out }
        if (typeof res === "string") { out["$string"] = res; return out }
        if (typeof res === "boolean") { out["$value"] = res; return out }
        if (typeof res === "number") { out["$value"] = root.numOf(res); return out }
        if (typeof res !== "object") { out["$value"] = String(res); return out }

        var chans = ["r", "g", "b", "a"]
        for (var i = 0; i < chans.length; i++) {
            var k = chans[i]
            var vCard = null
            try { vCard = res[k] } catch (e) { out[k] = { "$throws": String(e) }; continue }
            out[k] = root.numOf(vCard)
        }
        var meta = ["hslHue", "hslSaturation", "hslLightness",
                    "hsvHue", "hsvSaturation", "hsvValue", "valid"]
        for (var j = 0; j < meta.length; j++) {
            var m = meta[j]
            var mv = null
            try { mv = res[m] } catch (e) { out[m] = { "$throws": String(e) }; continue }
            out[m] = root.numOf(mv)
        }
        try { out["$hex"] = String(res) } catch (e) { out["$hex"] = "<String() falhou>" }
        try { out["$keys"] = Object.keys(res) } catch (e) { out["$keys"] = null }
        return out
    }

    function line(rec) {
        var s = ""
        try { s = JSON.stringify(rec) } catch (e) { s = "{\"$stringify\":\"" + e + "\"}" }
        return s
    }

    function resolveAll(v) {
        for (var i = 0; i < root.roles.length; i++) {
            var role = root.roles[i]
            var cands = root.roleCandidates[role] || []
            var found = null
            for (var c = 0; c < cands.length; c++) {
                var hit = root.search(v, cands[c], 0)
                console.log("FN_PROBE|" + role + "|" + cands[c] + "|" + (hit !== null))
                if (hit !== null && found === null) found = hit
            }
            root.resolved[role] = found
            if (found === null) {
                console.log("FN_ROLE|" + role + "|<absent>|absent")
            } else {
                console.log("FN_ROLE|" + role + "|" + found.name + "|present")
                console.log("FN_HOST|" + role + "|" + root.kindOf(found.owner) + "|" + found.name)
            }
        }
    }

    function run() {
        var v = null
        try { v = viewL.item } catch (e) { v = null }
        console.log("VIEW_PRESENT|" + (v !== null && v !== undefined))
        if (v === null || v === undefined) {
            console.log("VIEW_ERR|a view não montou")
            finish("sem view")
            return
        }
        root.resolveAll(v)

        for (var i = 0; i < root.cases.length; i++) {
            var cs = root.cases[i]
            var hit = root.resolved[cs.role]
            if (hit === null || hit === undefined) {
                console.log("FN_THROW|" + cs.role + "|" + cs.name + "|função ausente")
                continue
            }
            var args = root.buildArgs(cs.args)
            var res
            try {
                if (cs.role === "dangerOfUsage") {
                    // Compose through the PUBLIC functions only: no band colour
                    // is copied into this harness.
                    var uso = root.resolved["usage"]
                    if (uso === null || uso === undefined)
                        throw new Error("usageColour ausente: não há como compor")
                    args = [uso.owner[uso.name].apply(uso.owner, args)]
                }
                res = hit.owner[hit.name].apply(hit.owner, args)
            } catch (e) {
                console.log("FN_THROW|" + cs.role + "|" + cs.name + "|" + String(e))
                continue
            }
            console.log("FN|" + cs.role + "|" + cs.name + "|" + typeof res + "|" + root.line(root.normalize(res)))
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
        interval: root.settleMs + 25000
        repeat: false
        running: true
        onTriggered: {
            console.log("VIEW_ERR|watchdog: a view não montou")
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
