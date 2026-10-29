// -*- mode: qml -*-
// Behavior probe for T28 — compact vs expanded density, per-provider expansion.
//
// Gerado em contexto isolado (D5) — sem acesso à implementação.
// Base: SPEC rodada 3, tarefa T28.
//
// Why this exists: the T28 done-criterion is four claims that cannot be read off
// a screenshot of one state:
//   (a) compact draws FEWER elements than expanded;
//   (b) the chosen metric is the highest percent, not the first in the report;
//   (c) expanding one provider does not change the others;
//   (d) the top button works on a REAL click, not on a function call.
// Here the view is mounted, the setting is flipped mid-run, and everything is
// DUMPED: the pure functions are called with models chosen by the Python test,
// the rendered tree is CENSUSED twice (expanded / compact), and every clickable
// node is clicked one at a time to see which one flips the whole state — that
// last part identifies the button by BEHAVIOUR, so no `objectName`, no layout
// offset and no guess about where the button sits.
//
// NOTE on measurement: `implicitHeight` does not resolve offline (measured in
// this base), so "compact is shorter" is proven by COUNTING the rendered
// elements, which is the cause of the shorter height. Pixel height is NOT
// measured and the report must not claim it.
//
// NOTE on `objectName`: deliberately NOT set on anything. This base measured
// that naming a node makes a type dump carry a memory pointer
// (`QQuickColumn(0x7f67…)`), which breaks comparisons between runs.
//
// Inputs (env):
//   T28_PLUG_DIR   plugin folder under test
//   T28_MODEL      JSON model object (the view is fed this as mainInstance.model)
//   T28_CASES      JSON array of { "name": string, "fn": string, "args": array }
//                  fn: "leadingMetric" (args: [metrics])
//                      "visibleMetrics" (args: [provider])
//                      "hiddenMetricCount" (args: [provider])
//                      "isExpanded" (args: [providerId])
//   T28_STATE_DIR  synthetic stateDir
//   T28_SETTLE_MS  wait before the first phase (default 1400)
//   T28_WIDTH      host widthBudget (default 320)
//   T28_INITIAL_DENSITY  the `density` setting the view starts with:
//                  "expanded" (default) | "compact" | "absent" (the key is
//                  OMITTED, so the view has to fall back to its default)
//
// Output (stdout, one record per line; the consumer parses by prefix):
//   VIEW_PRESENT|<true|false>
//   FN_PROBE|<name>|<true|false>            DIAGNOSTIC ONLY
//   FN_ROLE|<role>|<name or <absent>>|<present|absent>
//   FN_HOST|<role>|<kind>|<name>
//   ===PHASE|<name>===
//   P_COMPACT_DEFAULT|<json>                compactByDefault (bool or marker)
//   P_ANY_EXPANDED|<json>                   anyProviderExpanded
//   EXPANDED_IDS|<json>                     keys of expandedIds
//   PROV|<json>                             {id, visible:[labels], hidden:n,
//                                            leading:label, expanded:bool}
//   CENSUS|texts|<n>|rects|<n>|mouse|<n>|metrics|<n>
//        rendered, visible-only census. `metrics` counts the drawn texts whose
//        content IS a metric label of the fixture (case-insensitive, trimmed),
//        i.e. how many metric rows are on screen — independent of chrome like
//        "+N more" or the button, which is what makes it comparable across
//        states. `texts`/`rects` are the raw totals, reported for diagnosis.
//   UC|<phase>|<case>|<typeof>|<json>       unit call (leadingMetric & co.)
//   UC_THROW|<phase>|<case>|<msg>
//   ===CLICKS===
//   CLICK_CAND|<i>|<kind>|<w>x<h>|<visible>|<true|false clicked signal>
//   CLICK|<i>|<kind>|<w>x<h>|<beforeCount>|<afterCount>|<allExpanded>|<changed>|<keys after>
//   TOGGLE_ALL|<step>|<beforeCount>|<afterCount>|<keys>
//   VIEW_ERR|<msg>
//   END|<reason>
//
// Everything is serialized BY HAND, field by field: this base has measured that
// objects and arrays returned from a QML function can arrive as `{}`/`[]` under
// JSON.stringify. An `undefined` field is reported as {"$undefined":true}; a
// NaN as {"$nan":true}.

import QtQuick
import Quickshell

ShellRoot {
    id: root

    property string plugDir: Quickshell.env("T28_PLUG_DIR") || ""
    property var model: JSON.parse(Quickshell.env("T28_MODEL") || "null")
    property var cases: JSON.parse(Quickshell.env("T28_CASES") || "[]")
    property int settleMs: parseInt(Quickshell.env("T28_SETTLE_MS") || "1400")
    property int widthBudget: parseInt(Quickshell.env("T28_WIDTH") || "320")
    property bool done: false

    property var roleCandidates: ({
        "leadingMetric": ["leadingMetric", "metricaLider", "leadingMetricOf", "headlineMetric", "mostCriticalMetric"],
        "visibleMetrics": ["visibleMetrics", "metricasVisiveis", "shownMetrics", "visibleMetricsOf"],
        "hiddenMetricCount": ["hiddenMetricCount", "contagemOcultas", "hiddenCount", "ocultasCount"],
        "isExpanded": ["isExpanded", "estaExpandido", "providerExpanded"],
        "toggleExpanded": ["toggleExpanded", "alternarExpandido", "expandProvider"],
        "toggleAll": ["toggleAll", "alternarTudo", "expandAll", "toggleExpandAll"]
    })
    property var roles: ["leadingMetric", "visibleMetrics", "hiddenMetricCount",
                         "isExpanded", "toggleExpanded", "toggleAll"]
    property var resolved: ({})
    property var phase: "init"
    property var saveKeys: []
    property var labelSetCache: ({})
    property bool dumpNodes: (Quickshell.env("T28_DUMP_NODES") || "0") === "1"
    property var providerIds: []

    QtObject {
        id: apiObj
        property var mainInstance: null
        property var pluginSettings: ({
            "accent": "wallpaper",
            "language": "en",
            "showMetricDetail": true,
            "showSecondaries": true,
            "density": "expanded"
        })
        //: The starting setting, before the mid-run flip to compact.
        function initSettings() {
            var d = Quickshell.env("T28_INITIAL_DENSITY") || "expanded"
            var st = {
                "accent": "wallpaper",
                "language": "en",
                "showMetricDetail": true,
                "showSecondaries": true
            }
            if (d !== "absent") st["density"] = d
            return st
        }
        property string pluginDir: root.plugDir
        property string stateDir: Quickshell.env("T28_STATE_DIR") || "/tmp/t28-state"
        property bool panelOpen: false
        function saveSetting(k, v) {
            console.log("SAVE_SETTING|" + k + "|" + JSON.stringify(String(v)))
            root.saveKeys.push(String(k))
        }
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
                item.density = "full"          // HOST density, not the setting
                item.widthBudget = root.widthBudget
            } catch (e) { console.log("VIEW_ERR|view: " + e) }
            settle.restart()
        }
        onStatusChanged: {
            if (status === Loader.Error)
                console.log("VIEW_ERR|o Loader não conseguiu carregar a view")
        }
    }

    // ------------------------------------------------------------------ utils
    function kindOf(it) {
        try {
            return String(it).replace(/\(0x[0-9a-f]+\)/, "").split("_QML")[0]
        } catch (e) { return "<?" + e + ">" }
    }

    function poolOf(it) {
        try { return it.data || [] } catch (e) { return it.children || [] }
    }

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

    function arrayLen(a) {
        if (a === undefined || a === null) return -1
        var n = -1
        try { n = a.length } catch (e) { return -1 }
        if (typeof n !== "number" || n < 0 || isNaN(n)) return -1
        return n
    }

    // A metric OBJECT, serialized by the fields the contract names. Reading
    // `.label` and `.percent` one at a time is what makes the answer legible:
    // String(metric) would print "[object Object]" and say nothing.
    function jmetric(mv) {
        if (mv === undefined) return "{\"$undefined\":true}"
        if (mv === null) return "null"
        if (typeof mv !== "object") return "{\"$notObject\":true,\"$value\":" + root.jv(mv) + "}"
        var o = "{"
        try { o += "\"label\":" + root.jv(mv.label) } catch (e) { o += "\"label\":{\"$throws\":true}" }
        try { o += ",\"percent\":" + root.jv(mv.percent) } catch (e) { o += ",\"percent\":null" }
        o += "}"
        return o
    }

    function stringsOf(a) {
        if (a === undefined) return "{\"$undefined\":true}"
        if (a === null) return "{\"$null\":true}"
        var n = root.arrayLen(a)
        if (n < 0) return "{\"$notArray\":true,\"$value\":" + root.jv(String(a)) + "}"
        var out = []
        for (var i = 0; i < n; i++) out.push(root.jmetric(a[i]))
        return "{\"$len\":" + n + ",\"items\":[" + out.join(",") + "]}"
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

    function viewItem() {
        var v = null
        try { v = viewL.item } catch (e) { v = null }
        return (v === undefined ? null : v)
    }

    function propIsTrue(name) {
        var v = root.viewItem()
        if (v === null) return "{\"$undefined\":true}"
        var got = undefined
        try { got = v[name] } catch (e) { return "{\"$throws\":true}" }
        return root.jv(got)
    }

    function expandedCount() {
        var v = root.viewItem()
        if (v === null) return -1
        var ids = undefined
        try { ids = v.expandedIds } catch (e) { return -1 }
        if (ids === undefined || ids === null) return -1
        var n = 0
        try {
            for (var k in ids) {
                var val = ids[k]
                // A set may be stored as {"id": true} or as {"id": something};
                // the key is what matters — the contract calls it a SET of ids.
                if (val !== false) n++
            }
        } catch (e) { return -1 }
        return n
    }

    function expandedKeys() {
        var v = root.viewItem()
        if (v === null) return "{\"$undefined\":true}"
        var ids = undefined
        try { ids = v.expandedIds } catch (e) { return "{\"$throws\":true}" }
        if (ids === undefined) return "{\"$undefined\":true}"
        if (ids === null) return "null"
        var ks = []
        try {
            for (var k in ids) {
                if (ids[k] !== false) ks.push(JSON.stringify(String(k)))
            }
        } catch (e) { return "{\"$throws\":true}" }
        return "[" + ks.join(",") + "]"
    }

    // ------------------------------------------------------------- census
    function census(it, depth, acc) {
        if (!it || depth > 18) return
        var shown = true
        try { shown = (it.visible !== false && it.opacity !== 0) } catch (e) { shown = true }
        if (shown) {
            try {
                if (typeof it.text === "string" && it.text.length > 0) {
                    acc.texts++
                    if (root.labelSetCache[it.text.toUpperCase().trim()] === true)
                        acc.metrics++
                }
                if (root.kindOf(it).indexOf("Rectangle") >= 0) acc.rects++
                if (typeof it.clicked === "function") acc.mouse++
            } catch (e) {}
        }
        var pool = root.poolOf(it)
        for (var i = 0; i < pool.length; i++) root.census(pool[i], depth + 1, acc)
    }

    // Metric labels of the fixture, upper-cased: the view upper-cases its
    // headings (measured), so the comparison is case-insensitive by construction.
    function labelSet() {
        var set = {}
        var ps = root.providers()
        for (var i = 0; i < ps.length; i++) {
            var ms = ps[i].metrics || []
            for (var j = 0; j < ms.length; j++) {
                var l = ms[j].label
                if (typeof l === "string" && l.length > 0) set[l.toUpperCase().trim()] = true
            }
        }
        return set
    }

    // Counts the rendered tree. `implicitHeight` does not resolve offline, so
    // the number of drawn elements is the measurable proxy for "shorter".
    function emitCensus() {
        var acc = { texts: 0, rects: 0, mouse: 0, metrics: 0 }
        var v = root.viewItem()
        if (v !== null) root.census(v, 0, acc)
        console.log("CENSUS|texts|" + acc.texts + "|rects|" + acc.rects +
                    "|mouse|" + acc.mouse + "|metrics|" + acc.metrics)
        if (root.dumpNodes) {
            var seen = { texts: [], rects: [] }
            if (v !== null) root.collectNodes(v, 0, seen)
            for (var t = 0; t < seen.texts.length; t++)
                console.log("NODE_TEXT|" + JSON.stringify(seen.texts[t]))
            for (var r = 0; r < seen.rects.length; r++)
                console.log("NODE_RECT|" + seen.rects[r])
        }
    }

    function collectNodes(it, depth, acc) {
        if (!it || depth > 18) return
        var shown = true
        try { shown = (it.visible !== false && it.opacity !== 0) } catch (e) { shown = true }
        if (shown) {
            try {
                if (typeof it.text === "string" && it.text.length > 0) acc.texts.push(it.text)
                if (root.kindOf(it).indexOf("Rectangle") >= 0)
                    acc.rects.push(Math.round(it.width) + "x" + Math.round(it.height) +
                                   "|a=" + ((it.color && it.color.a !== undefined) ? it.color.a : 1))
            } catch (e) {}
        }
        var pool = root.poolOf(it)
        for (var i = 0; i < pool.length; i++) root.collectNodes(pool[i], depth + 1, acc)
    }

    // ----------------------------------------------------------- providers
    function providers() {
        var v = root.viewItem()
        var m = root.model
        if (m === null || m === undefined) {
            if (v !== null) {
                try { m = apiObj.mainInstance.model } catch (e) { m = null }
            }
        }
        var out = []
        if (m === null || m === undefined) return out
        if (m.all !== undefined && m.all !== null) out = m.all
        else if (m.primary !== undefined) out = [m.primary]
        return out
    }

    function callRole(role, args) {
        var hit = root.resolved[role]
        if (hit === null || hit === undefined) return { ok: false, why: "função ausente" }
        try {
            return { ok: true, value: hit.owner[hit.name].apply(hit.owner, args) }
        } catch (e) {
            return { ok: false, why: String(e) }
        }
    }

    function emitProviders(phaseName) {
        var list = root.providers()
        for (var i = 0; i < list.length; i++) {
            var p = list[i]
            var id = undefined, lead = undefined
            try { id = p.id } catch (e) {}
            var vis = root.callRole("visibleMetrics", [p])
            var hid = root.callRole("hiddenMetricCount", [p])
            var exp = root.callRole("isExpanded", [id])
            var lm = root.callRole("leadingMetric", [p.metrics])
            var o = "{\"i\":" + i + ",\"id\":" + root.jv(id)
            if (vis.ok) o += ",\"visible\":" + root.stringsOf(vis.value)
            else o += ",\"visible\":{\"$throw\":" + root.jv(vis.why) + "}"
            if (hid.ok) o += ",\"hidden\":" + root.jv(hid.value)
            else o += ",\"hidden\":{\"$throw\":" + root.jv(hid.why) + "}"
            if (exp.ok) o += ",\"expanded\":" + root.jv(exp.value)
            else o += ",\"expanded\":{\"$throw\":" + root.jv(exp.why) + "}"
            if (lm.ok) {
                try { lead = lm.value.label } catch (e) { lead = undefined }
                o += ",\"leading\":" + root.jv(lead)
            } else o += ",\"leading\":{\"$throw\":" + root.jv(lm.why) + "}"
            // Metric labels as declared in the fixture, so the Python side can
            // compare "what should be visible" without re-reading the harness.
            var labels = []
            try {
                for (var k = 0; k < p.metrics.length; k++)
                    labels.push(root.jv(p.metrics[k].label))
            } catch (e) {}
            o += ",\"allLabels\":[" + labels.join(",") + "]}"
            console.log("PROV|" + o)
        }
    }

    function emitUnitCases(phaseName) {
        for (var i = 0; i < root.cases.length; i++) {
            var cs = root.cases[i]
            var hit = root.resolved[cs.fn]
            if (hit === null || hit === undefined) {
                console.log("UC_THROW|" + phaseName + "|" + cs.name + "|função ausente")
                continue
            }
            var res
            try {
                res = hit.owner[hit.name].apply(hit.owner, cs.args || [])
            } catch (e) {
                console.log("UC_THROW|" + phaseName + "|" + cs.name + "|" + String(e))
                continue
            }
            var norm
            var t = typeof res
            if (cs.fn === "visibleMetrics") norm = root.stringsOf(res)
            else if (t === "object" && res !== null && res.label !== undefined) {
                norm = "{\"label\":" + root.jv(res.label) +
                       ",\"percent\":" + root.jv(res.percent) + "}"
            } else norm = root.jv(res)
            console.log("UC|" + phaseName + "|" + cs.name + "|" + t + "|" + norm)
        }
    }

    function phaseExpandedName() {
        return "inicial(" + (Quickshell.env("T28_INITIAL_DENSITY") || "expanded") + ")"
    }

    function emitState(phaseName) {
        console.log("===PHASE|" + phaseName + "===")
        console.log("P_COMPACT_DEFAULT|" + root.propIsTrue("compactByDefault"))
        console.log("P_ANY_EXPANDED|" + root.propIsTrue("anyProviderExpanded"))
        console.log("EXPANDED_IDS|" + root.expandedKeys())
        root.emitProviders(phaseName)
        root.emitCensus()
        root.emitUnitCases(phaseName)
    }

    // ------------------------------------------------------------------ run
    function run() {
        var v = root.viewItem()
        console.log("VIEW_PRESENT|" + (v !== null))
        if (v === null) {
            console.log("VIEW_ERR|a view não montou")
            finish("sem view")
            return
        }
        for (var r = 0; r < root.roles.length; r++) {
            var role = root.roles[r]
            var cands = root.roleCandidates[role] || []
            var found = null
            for (var c = 0; c < cands.length; c++) {
                var hit = root.search(v, cands[c], 0)
                if (role === "leadingMetric" || role === "visibleMetrics" ||
                    role === "hiddenMetricCount" || role === "isExpanded" ||
                    role === "toggleExpanded" || role === "toggleAll")
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
        root.labelSetCache = root.labelSet()
        // Provider ids, captured once while the model is the fixture.
        var list = root.providers()
        root.providerIds = []
        for (var p = 0; p < list.length; p++) root.providerIds.push(list[p].id)

        root.phase = root.phaseExpandedName()
        root.emitState(root.phaseExpandedName())
        toCompact.restart()
    }

    // Flip the SETTING (not a call) and let the binding re-evaluate on a later
    // cycle — measuring inside the same handler reads the old binding.
    Timer {
        id: toCompact
        interval: 400
        repeat: false
        onTriggered: {
            apiObj.pluginSettings = {
                "accent": "wallpaper",
                "language": "en",
                "showMetricDetail": true,
                "showSecondaries": true,
                "density": "compact"
            }
            afterCompact.restart()
        }
    }

    Timer {
        id: afterCompact
        interval: 700
        repeat: false
        onTriggered: {
            root.emitState("compact")
            // Isolate the SECOND provider (the contract says "a provider", not
            // "the first": expanding the first could hide an off-by-one).
            if (root.providerIds.length < 2) {
                console.log("VIEW_ERR|modelo com menos de 2 providers: isolação não exercitável")
                root.clicksAndToggleAll()
                return
            }
            var target = root.providerIds[1]
            var t = root.resolved["toggleExpanded"]
            if (t === null) {
                console.log("VIEW_ERR|toggleExpanded ausente")
                root.clicksAndToggleAll()
                return
            }
            try { t.owner[t.name].call(t.owner, target) }
            catch (e) { console.log("VIEW_ERR|toggleExpanded lançou: " + e) }
            afterExpand.restart()
        }
    }

    Timer {
        id: afterExpand
        interval: 600
        repeat: false
        onTriggered: {
            root.emitState("compact+1expandido")
            // Collapse again, then exercise toggleAll twice: {} -> all -> {}.
            var t = root.resolved["toggleExpanded"]
            try { t.owner[t.name].call(t.owner, root.providerIds[1]) } catch (e) {}
            toggleAllProbe.restart()
        }
    }

    Timer {
        id: toggleAllProbe
        interval: 400
        repeat: false
        onTriggered: { root.toggleAllStep(1) }
    }

    function toggleAllStep(step) {
        var t = root.resolved["toggleAll"]
        if (t === null) {
            console.log("TOGGLE_ALL|" + step + "|função ausente||")
            root.clicksAndToggleAll()
            return
        }
        console.log("TOGGLE_ALL|" + step + "|before|" + root.expandedCount() + "|" + root.expandedKeys())
        try { t.owner[t.name].call(t.owner) }
        catch (e) { console.log("VIEW_ERR|toggleAll lançou: " + e) }
        console.log("TOGGLE_ALL|" + step + "|after|" + root.expandedCount() + "|" + root.expandedKeys())
        root.toggleAllStepNext = step + 1
        nextProbe.restart()
    }
    property int toggleAllStepNext: 1

    Timer {
        id: nextProbe
        interval: 300
        repeat: false
        onTriggered: {
            if (root.toggleAllStepNext === 2) root.toggleAllStep(2)
            else if (root.toggleAllStepNext === 3) {
                root.emitCensus()
                root.clicksAndToggleAll()
            }
        }
    }

    // --------------------------------------------------------- click phase
    property var clickables: []
    property int clickIdx: 0

    function collectClickable(it, depth) {
        if (!it || depth > 18) return
        var hasClick = false
        try { hasClick = (typeof it.clicked === "function") } catch (e) { hasClick = false }
        if (hasClick) root.clickables.push(it)
        var pool = root.poolOf(it)
        for (var i = 0; i < pool.length; i++) root.collectClickable(pool[i], depth + 1)
    }

    function clicksAndToggleAll() {
        console.log("===CLICKS===")
        root.clickables = []
        var v = root.viewItem()
        if (v !== null) root.collectClickable(v, 0)
        for (var i = 0; i < root.clickables.length; i++) {
            var c = root.clickables[i]
            var w = -1, h = -1, vis = null
            try { w = Math.round(c.width) ; h = Math.round(c.height) } catch (e) {}
            try { vis = (c.visible !== false) } catch (e) {}
            console.log("CLICK_CAND|" + i + "|" + root.kindOf(c) + "|" + w + "x" + h +
                        "|" + vis + "|true")
        }
        root.clickIdx = 0
        nextClick.restart()
    }

    // Put the view back into compact mode without touching the setting: the
    // override is what the view itself uses, and `null` means "follow the setting".
    function restoreCompactMode() {
        var v = root.viewItem()
        if (v === null) return
        try {
            if (v.compactMode !== true && v.densityOverride !== undefined)
                v.densityOverride = true
        } catch (e) {}
    }

    function resetExpansion() {
        // Collapse everything: the contract says toggleAll from a non-empty set
        // collapses all, so one call is enough; the loop is only a guard.
        var t = root.resolved["toggleAll"]
        if (t === null) return
        for (var g = 0; g < 4 && root.expandedCount() > 0; g++) {
            try { t.owner[t.name].call(t.owner) } catch (e) { break }
        }
    }

    function clickOne() {
        if (root.clickIdx >= root.clickables.length) { root.toggleAllByClick(); return }
        var i = root.clickIdx
        var c = root.clickables[i]
        // Restore the MODE before every click, not only the expansion.
        //
        // The view has TWO controls now (density in the popout was split into a
        // mode button and an expand/collapse button — Att1, decided 2026-10-29).
        // One of the clickable nodes IS the mode button: clicking it leaves compact
        // mode, which removes the expand button from the tree, and every later click
        // in this loop then switches modes instead of expanding. Restoring the mode
        // is what makes each click measure what it claims to.
        root.restoreCompactMode()
        root.resetExpansion()
        var before = root.expandedCount()
        var w = 8, h = 8
        try { w = Math.max(1, c.width); h = Math.max(1, c.height) } catch (e) {}
        var changed = false
        try {
            c.clicked(Qt.point(w / 2, h / 2))
            changed = true
        } catch (e) {
            console.log("VIEW_ERR|click " + i + ": " + e)
        }
        var after = root.expandedCount()
        var allExpanded = (after === root.providerIds.length && root.providerIds.length > 0)
        // The KEYS after the click, so the Python side can assert that a
        // per-provider control expanded exactly THAT provider (isolation by a
        // real click, not only by calling toggleExpanded).
        console.log("CLICK|" + i + "|" + root.kindOf(c) + "|" + Math.round(w) + "x" +
                    Math.round(h) + "|" + before + "|" + after + "|" + allExpanded +
                    "|" + (changed && before !== after) + "|" + root.expandedKeys())
        root.clickIdx++
        nextClick.restart()
    }

    Timer { id: nextClick; interval: 260; repeat: false; onTriggered: root.clickOne() }

    // ------------------------------------------------- the top button, twice
    // The button is identified by BEHAVIOUR (the clickable that expands every
    // provider from an empty set), never by name or position. Then it is clicked
    // again from the expanded state: the contract says one button toggles all.
    property int topButtonIdx: -1

    function findTopButton() {
        root.resetExpansion()
        var list = root.clickables
        for (var i = 0; i < list.length; i++) {
            var c = list[i]
            var vis = true
            try { vis = (c.visible !== false) } catch (e) { vis = true }
            if (!vis) continue
            var w = 8, h = 8
            try { w = Math.max(1, c.width); h = Math.max(1, c.height) } catch (e) {}
            root.restoreCompactMode()
            root.resetExpansion()
            try { c.clicked(Qt.point(w / 2, h / 2)) } catch (e) { continue }
            if (root.expandedCount() === root.providerIds.length && root.providerIds.length > 0)
                return i
        }
        return -1
    }

    function toggleAllByClick() {
        root.topButtonIdx = root.findTopButton()
        console.log("TOP_BUTTON|" + root.topButtonIdx)
        if (root.topButtonIdx < 0) { root.remountCheck(); return }
        var c = root.clickables[root.topButtonIdx]
        var w = 8, h = 8
        try { w = Math.max(1, c.width); h = Math.max(1, c.height) } catch (e) {}
        // State is "all expanded" right now (findTopButton stopped there).
        var before = root.expandedCount()
        var beforeKeys = root.expandedKeys()
        try { c.clicked(Qt.point(w / 2, h / 2)) } catch (e) {}
        var after = root.expandedCount()
        console.log("CLICK_TOGGLE|" + before + "|" + beforeKeys + "|" + after + "|" + root.expandedKeys())
        // And once more, from empty back to all.
        try { c.clicked(Qt.point(w / 2, h / 2)) } catch (e) {}
        console.log("CLICK_TOGGLE|" + after + "|" + root.expandedKeys() + "|" +
                    root.expandedCount() + "|" + root.expandedKeys())
        root.restoreCompactMode()
        remount.restart()
    }

    // ------------------------------------------------------- volatility (item 5)
    // "The expansion state is VOLATILE (it does not persist)." Remounting the
    // view is the closest observable to "reopening the surface": a state that
    // survives it was persisted somewhere. The saveSetting log is dumped too, so
    // a view that persists by writing a setting is named explicitly.
    Timer {
        id: remount
        interval: 400
        repeat: false
        onTriggered: {
            root.remountPhase = true
            console.log("SAVE_KEYS_BEFORE_REMOUNT|" + JSON.stringify(root.saveKeys))
            viewL.active = false
            viewL.setSource("")
            viewL.setSource(root.plugDir + "/content/Widget.qml")
            viewL.active = true
            afterRemount.restart()
        }
    }

    property bool remountPhase: false

    Timer {
        id: afterRemount
        interval: 1000
        repeat: false
        onTriggered: {
            console.log("REMOUNT_EXPANDED_IDS|" + root.expandedKeys())
            console.log("REMOUNT_COUNT|" + root.expandedCount())
            console.log("SAVE_KEYS|" + JSON.stringify(root.saveKeys))
            root.remountCheck()
        }
    }

    function remountCheck() {
        if (!root.remountPhase) {
            // Save keys are still worth reporting even when the remount was skipped.
            console.log("SAVE_KEYS|" + JSON.stringify(root.saveKeys))
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
        interval: root.settleMs + 45000
        repeat: false
        running: true
        onTriggered: {
            console.log("VIEW_ERR|watchdog: fases não terminaram")
            root.done = true
            Qt.quit()
        }
    }

    Component.onCompleted: {
        apiObj.pluginSettings = apiObj.initSettings()
        apiObj.mainInstance = {
            model: root.model,
            loading: false, lastError: "", errorKind: ""
        }
        viewL.setSource(root.plugDir + "/content/Widget.qml")
        viewL.active = true
    }
}
