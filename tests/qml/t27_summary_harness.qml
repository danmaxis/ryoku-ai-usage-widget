// -*- mode: qml -*-
// Behavior probe for T27 — the PURE operational summary at the top of the popout.
//
// Gerado em contexto isolado (D5) — sem acesso à implementação.
// Base: SPEC rodada 3, tarefa T27.
//
// Why this exists: the T27 done-criterion asks for a PURE summary function with
// fixtures (nothing exhausted, everything exhausted, reset tie, repeated
// metrics, error provider), and the contract's refutations are about COUNTS
// ("3 metrics above 80% in ONE provider count 3", "the same window repeated
// counts 1"). Neither is readable off the screen: the counts are the answer.
// Here the functions are CALLED with models chosen by the Python test and the
// raw result is dumped field by field, so the counts, the reset arithmetic and
// the omitted (zero) segments are observable without ever reading
// content/Widget.qml.
//
// service/Main.qml is deliberately NOT mounted: the summary is arithmetic over
// a model object. Mounting the collector would make this probe depend on PATH,
// the network and the user's state to answer a question about counting.
//
// Inputs (env):
//   T27_PLUG_DIR   plugin folder under test
//   T27_CASES      JSON array of
//                    { "name": string,
//                      "fn": "countable" | "summary" | "segments",
//                      "model": <model object>,
//                      "now": <number, seconds since epoch> }
//                  "countable" calls countableQuotas(model);
//                  "summary"   calls operationalSummary(model, now);
//                  "segments"  calls operationalSummarySegments(model, now).
//   T27_STATE_DIR  synthetic stateDir
//   T27_SETTLE_MS  wait before calling (default 1200)
//   T27_WIDTH      host widthBudget (default 320)
//   T27_LANGUAGE   language handed to the view (default "en")
//   T27_RENDER_MODEL  model fed to the mounted view (default: first case's model)
//   T27_RENDER_NOW    epoch fed to the mounted view's summary, if it reads one
//                     (informational; the rendered text uses the view's own clock)
//
// Output (stdout, one record per line; the consumer parses by prefix):
//   VIEW_PRESENT|<true|false>
//   FN_PROBE|<role>|<candidate spelling>|<true|false>     DIAGNOSTIC ONLY
//   FN_ROLE|<role>|<name found or <absent>>|<present|absent>
//   FN_HOST|<role>|<kind of the hosting object>|<name>
//   P_THRESHOLD|<name>|<value or marker>
//   T23|<role>|<case>|<relative>   resetParts(iso, now).relative, when the case
//                                  carries a "resetIso" — the contract's item 5
//                                  says the summary uses T23's formatting, so the
//                                  expected text is taken FROM T23, not typed here.
//   RENDER_TEXT|<text>             a rendered, visible text of the mounted view
//   RENDER_SEGMENTS|<json>         operationalSummarySegments on the render model
//   FN|<role>|<case>|<typeof>|<normalized JSON>
//   FN_THROW|<role>|<case>|<message>
//   VIEW_ERR|<message>
//   END|<reason>
//
// Why the results are serialized BY HAND and not with JSON.stringify(json):
// this base has measured that objects/arrays returned from a QML function can
// flatten to `{}` / `[]` under stringify (a `color` becomes `{}`, and a QML
// `var` property that holds a JS object created inside the view is not always a
// plain JS object to the JS engine). Every field the contract names is
// therefore read ONE AT A TIME, index by index, and emitted as JSON *text*
// assembled here. A field that reads as `undefined` is reported as
// {"$undefined":true}, a NaN as {"$nan":true} — never silently as null.

import QtQuick
import Quickshell

ShellRoot {
    id: root

    property string plugDir: Quickshell.env("T27_PLUG_DIR") || ""
    property var cases: JSON.parse(Quickshell.env("T27_CASES") || "[]")
    property int settleMs: parseInt(Quickshell.env("T27_SETTLE_MS") || "1200")
    property int widthBudget: parseInt(Quickshell.env("T27_WIDTH") || "320")
    property bool done: false

    //: The spellings the interface block names, plus a few near-misses so that a
    //: missing function reports WHAT WAS THERE instead of just "absent".
    property var roleCandidates: ({
        "countable": ["countableQuotas", "cotasContaveis", "countableWindows", "countableLimits"],
        "summary": ["operationalSummary", "resumoOperacional", "summary", "operationalResumo"],
        "segments": ["operationalSummarySegments", "segmentsDoResumo", "summarySegments",
                     "operationalSummarySegmentos", "resumoSegmentos"]
    })

    property var roles: ["countable", "summary", "segments"]
    property var resetParts: null
    property var renderModel: null
    property int renderNow: parseInt(Quickshell.env("T27_RENDER_NOW") || "0")
    property var resolved: ({})

    // Synthetic pluginApi: the view must instantiate without the real host.
    // `language` is pinned to "en" so the rendered catalogs are deterministic
    // if the view decides to translate anything at mount time.
    QtObject {
        id: apiObj
        property var mainInstance: null
        property var pluginSettings: ({
            "accent": "wallpaper",
            "language": Quickshell.env("T27_LANGUAGE") || "en",
            "showMetricDetail": true,
            "showSecondaries": true
        })
        property string pluginDir: root.plugDir
        property string stateDir: Quickshell.env("T27_STATE_DIR") || "/tmp/t27-state"
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

    // NOTE: named `viewItem`, not `view` — ShellRoot already has a `view`
    // property in Quickshell, and shadowing it makes the call throw
    // "Property 'view' ... is not a function" (measured while building this
    // probe).
    function viewItem() {
        var v = null
        try { v = viewL.item } catch (e) { v = null }
        return (v === undefined ? null : v)
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

    // ---- primitive-safe serialization -------------------------------------
    // One value at a time; never trusts a nested JSON.stringify.
    function jv(v) {
        if (v === undefined) return "{\"$undefined\":true}"
        if (v === null) return "null"
        var t = typeof v
        if (t === "number") {
            if (isNaN(v)) return "{\"$nan\":true}"
            if (!isFinite(v)) return "{\"$infinite\":true}"
            return String(v)
        }
        if (t === "string" || t === "boolean") return JSON.stringify(v)
        try { return JSON.stringify(String(v)) } catch (e) { return "\"<não serializável>\"" }
    }

    // Array-ness is decided by reading `.length`, not by trusting constructor
    // names: a QML-returned array is not always an Array to every build.
    function arrayLen(a) {
        if (a === undefined || a === null) return -1
        var n = -1
        try { n = a.length } catch (e) { return -1 }
        if (typeof n !== "number" || n < 0 || isNaN(n)) return -1
        return n
    }

    // countableQuotas -> array of { providerId, label, metric }
    function normalizeCountable(res) {
        if (res === undefined) return "{\"$undefined\":true}"
        if (res === null) return "{\"$null\":true}"
        var n = root.arrayLen(res)
        if (n < 0)
            return "{\"$notArray\":true,\"$type\":" + JSON.stringify(typeof res) +
                   ",\"$value\":" + root.jv(String(res)) + "}"
        var items = []
        for (var i = 0; i < n; i++) {
            var it = res[i]
            var o = "{\"i\":" + i
            if (it === undefined || it === null) {
                items.push("{\"i\":" + i + ",\"$null\":true}")
                continue
            }
            try { o += ",\"providerId\":" + root.jv(it.providerId) }
            catch (e) { o += ",\"providerId\":{\"$throws\":true}" }
            try { o += ",\"label\":" + root.jv(it.label) }
            catch (e) { o += ",\"label\":{\"$throws\":true}" }
            var m = undefined
            try { m = it.metric } catch (e) { m = undefined }
            if (m === undefined || m === null) {
                o += ",\"metric\":" + (m === null ? "null" : "{\"$undefined\":true}")
            } else {
                o += ",\"metric\":{"
                try { o += "\"label\":" + root.jv(m.label) } catch (e) { o += "\"label\":null" }
                try { o += ",\"percent\":" + root.jv(m.percent) } catch (e) { o += ",\"percent\":null" }
                try { o += ",\"window_secs\":" + root.jv(m.window_secs) } catch (e) { o += ",\"window_secs\":null" }
                o += "}"
            }
            o += "}"
            items.push(o)
        }
        return "{\"$len\":" + n + ",\"items\":[" + items.join(",") + "]}"
    }

    // operationalSummary -> { exhausted, high, nextResetRelative, nextResetSeconds, total }
    function normalizeSummary(res) {
        if (res === undefined) return "{\"$undefined\":true}"
        if (res === null) return "{\"$null\":true}"
        var fields = ["exhausted", "high", "total", "nextResetSeconds", "nextResetRelative"]
        var parts = []
        for (var i = 0; i < fields.length; i++) {
            var k = fields[i]
            var v = undefined
            try { v = res[k] } catch (e) { parts.push("\"" + k + "\":{\"$throws\":true}"); continue }
            parts.push("\"" + k + "\":" + root.jv(v))
        }
        var keys = "null"
        try {
            var ks = []
            for (var kk in res) ks.push(JSON.stringify(String(kk)))
            keys = "[" + ks.join(",") + "]"
        } catch (e) { keys = "null" }
        return "{" + parts.join(",") + ",\"$keys\":" + keys + "}"
    }

    // operationalSummarySegments -> array of translated strings
    function normalizeSegments(res) {
        if (res === undefined) return "{\"$undefined\":true}"
        if (res === null) return "{\"$null\":true}"
        var n = root.arrayLen(res)
        if (n < 0)
            return "{\"$notArray\":true,\"$type\":" + JSON.stringify(typeof res) +
                   ",\"$value\":" + root.jv(String(res)) + "}"
        var items = []
        for (var i = 0; i < n; i++) items.push(root.jv(res[i]))
        return "{\"$len\":" + n + ",\"items\":[" + items.join(",") + "]}"
    }

    function normalize(role, res) {
        if (role === "countable") return root.normalizeCountable(res)
        if (role === "segments") return root.normalizeSegments(res)
        return root.normalizeSummary(res)
    }

    function argsFor(cs) {
        if (cs.fn === "countable") return [cs.model]
        return [cs.model, cs.now]
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

    // Thresholds are declared properties of the contract. Reading them here is
    // what lets the Python side assert "the summary says 80% because the
    // property says 80", instead of hard-coding a number in two places.
    function prop(name) {
        var v = null
        try { v = viewL.item } catch (e) { v = null }
        if (v === null || v === undefined) return "{\"$undefined\":true}"
        var got = undefined
        try { got = v[name] } catch (e) { return "{\"$throws\":true}" }
        return root.jv(got)
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
        root.resetParts = root.search(v, "resetParts", 0)
        console.log("FN_ROLE|resetParts|" + (root.resetParts === null ? "<absent>" : root.resetParts.name)
                    + "|" + (root.resetParts === null ? "absent" : "present"))
        console.log("P_THRESHOLD|exhaustedThreshold|" + root.prop("exhaustedThreshold"))
        console.log("P_THRESHOLD|highWaterThreshold|" + root.prop("highWaterThreshold"))

        for (var i = 0; i < root.cases.length; i++) {
            var cs = root.cases[i]
            var role = cs.fn
            var hit = root.resolved[role]
            if (hit === null || hit === undefined) {
                console.log("FN_THROW|" + role + "|" + cs.name + "|função ausente")
                continue
            }
            var res
            try {
                res = hit.owner[hit.name].apply(hit.owner, root.argsFor(cs))
            } catch (e) {
                console.log("FN_THROW|" + role + "|" + cs.name + "|" + String(e))
                continue
            }
            var norm = ""
            try { norm = root.normalize(role, res) }
            catch (e) { norm = "{\"$normalize\":\"" + String(e) + "\"}" }
            console.log("FN|" + role + "|" + cs.name + "|" + typeof res + "|" + norm)

            // Item 5: the reset text is T23's. Composed through T23 itself so
            // this file never hard-codes a duration format.
            if (cs.resetIso !== undefined && cs.resetIso !== null && root.resetParts !== null) {
                try {
                    var rp = root.resetParts.owner[root.resetParts.name](cs.resetIso, cs.now)
                    var rel = undefined
                    try { rel = rp.relative } catch (e) { rel = undefined }
                    console.log("T23|" + role + "|" + cs.name + "|" + root.jv(rel))
                } catch (e) {
                    console.log("T23|" + role + "|" + cs.name + "|{\"$throw\":" + root.jv(String(e)) + "}")
                }
            }
        }
        root.emitRender()
        finish("casos")
    }

    function emitRender() {
        var v = root.viewItem()
        if (v === null) return
        var segHit = root.resolved["segments"]
        if (segHit !== null && segHit !== undefined) {
            try {
                var sg = segHit.owner[segHit.name].call(segHit.owner, root.renderModel, root.renderNow)
                console.log("RENDER_SEGMENTS|" + root.normalizeSegments(sg))
            } catch (e) {
                console.log("RENDER_SEGMENTS|{\"$throw\":" + root.jv(String(e)) + "}")
            }
        }
        root.collectTexts(v, 0)
    }

    function collectTexts(it, depth) {
        if (!it || depth > 18) return
        var shown = true
        try { shown = (it.visible !== false && it.opacity !== 0) } catch (e) { shown = true }
        if (shown) {
            try {
                if (typeof it.text === "string" && it.text.length > 0)
                    console.log("RENDER_TEXT|" + JSON.stringify(it.text))
            } catch (e) {}
        }
        var pool = root.poolOf(it)
        for (var i = 0; i < pool.length; i++) root.collectTexts(pool[i], depth + 1)
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
        // Synthetic main instance: a model from the first case so the view has
        // something to render, and no collector error.
        var rawRender = Quickshell.env("T27_RENDER_MODEL") || ""
        if (rawRender !== "") {
            try { root.renderModel = JSON.parse(rawRender) } catch (e) { root.renderModel = null }
        }
        if (root.renderModel === null && root.cases.length > 0) root.renderModel = root.cases[0].model
        apiObj.mainInstance = {
            model: root.renderModel,
            loading: false, lastError: "", errorKind: ""
        }
        viewL.setSource(root.plugDir + "/content/Widget.qml")
        viewL.active = true
    }
}
