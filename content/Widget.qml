import QtQuick
import Quickshell.Io
import Ryoku.PluginKit
import Ryoku.PluginKit.Singletons

// content/Widget.qml — the DETAIL surface of ai-usage.
//
// Host: framePopout (density "full"). The shell DRAWS the popout body
// (Popout.qml -> bodyBlob: BlobRect with Theme.radiusWindow and the theme's
// border), so THIS FILE DRAWS NO FRAME AND NO BACKGROUND. Drawing our own on top
// stacked TWO frames: since our radius (20) was smaller than the host's, the
// opaque corner invaded the area the shell had rounded — the "square corner /
// opaque background" the real smoke test called out.
//
// Rules this file obeys:
//   R4    — only QtQuick + Ryoku.PluginKit{,.Singletons}; nothing outside the folder.
//   R5    — settings read through pluginApi.pluginSettings BEHIND a default.
//   R8    — nothing is written here: the collector is pure stdout.
//   Tactical — JetBrains Mono tracked caps ONLY in short telemetry (cooldown,
//           percentage, metric label); one live accent per screen; no bounce
//           (only short OutExpo); no emoji.
//   stale/error NEVER by colour alone — always with a word (contrast is legibility).
Item {
    id: root

    property var pluginApi
    property var screen
    property bool active: false
    property string density: "full"
    property real s: 1
    property real widthBudget: 0


    readonly property var service: pluginApi ? pluginApi.mainInstance : null
    readonly property var model: service ? service.model : null
    readonly property var primaryProvider: model ? model.primary : null
    readonly property var secondaryProviders: model && model.secondary ? model.secondary : []
    readonly property int totalSecondary: {
        var n = model ? Number(model.total_providers) : NaN;
        return isFinite(n) ? Math.max(0, n - (primaryProvider ? 1 : 0)) : secondaryProviders.length;
    }
    readonly property string lastError: service ? service.lastError : ""
    readonly property string errorKind: service ? (service.errorKind || "") : ""

    // The numbers on screen come from an earlier read, and the LATEST read failed.
    // Keeping the last good model is deliberate (a transient failure must not blank
    // the panel), but showing it silently would be the lie the previous version was
    // trying to avoid. This property is what makes keeping it honest: it drives a
    // visible warning and a warning-coloured footer.
    readonly property bool staleData: root.errorKind !== "" && root.primaryProvider !== null

    // R5: always behind a default.
    readonly property var cfg: pluginApi ? pluginApi.pluginSettings : null
    readonly property int pad: {
        var v = cfg ? Number(cfg.padding) : NaN;
        return isFinite(v) ? Math.max(0, Math.min(32, Math.round(v))) : 12;
    }
    readonly property int gap: {
        var v = cfg ? Number(cfg.gap) : NaN;
        return isFinite(v) ? Math.max(2, Math.min(24, Math.round(v))) : 6;
    }
    readonly property bool showSecondary: cfg ? cfg.showSecondaries !== false : true

    // ---- type scale -----------------------------------------------------------
    // SEVEN steps lived between 7.5 and 10, most of them 0.5px apart. At a glance
    // 7.5 / 8 / 8.5 / 9 / 9.5 / 10 are the same weight, so the panel had no
    // hierarchy at all: the provider name, the quota label, the value and the
    // helper prose all read as one block. That is what "esperava um layout um
    // pouco mais distribuído" describes (Att2, 2026-10-29).
    //
    // Five ROLES, each a visible step apart (ratio ~1.15 minimum, which is what
    // survives a 1x display):
    //   display  the provider name — the one thing the eye should find first
    //   title    a section marker (OUTROS PROVEDORES)
    //   value    the reading that carries a number (the % outside a bar)
    //   body     quota labels and the three readings — the working text
    //   meta     timestamps, counts, footer prose — the smallest, still legible
    //
    // Every step multiplies `s`, so the ratios survive the user's scaling.
    readonly property real fsDisplay: 15 * s
    readonly property real fsTitle: 10 * s
    readonly property real fsValue: 11 * s
    readonly property real fsBody: 9 * s
    readonly property real fsMeta: 8 * s
    // There is deliberately NO half-step between `meta` and `body`. An earlier
    // revision had `fsReading: 8.5` for the three readings, which reproduced the
    // exact defect this scale exists to remove: 0.5px is not a step, it is noise
    // (measured: meta 8 / reading 8.5, ratio 1.06 — indistinguishable).
    // The three readings ARE body text; they share `fsBody`.
    readonly property bool showDetail: cfg ? cfg.showMetricDetail !== false : true
    readonly property string secondaryLabelMode: {
        var mode = cfg && cfg.secondaryLabel ? String(cfg.secondaryLabel) : "name";
        return ["name", "short", "plan"].indexOf(mode) >= 0 ? mode : "name";
    }
    // Slight indent of each secondary's block: the separator line sits flush left
    // and the content steps in, so the eye does not read every provider as one
    // line. Small on purpose — it is breathing room, not a new hierarchy.
    readonly property real secondaryIndent: 8 * s

    readonly property color accentColor: {
        var mode = cfg && cfg.accent ? String(cfg.accent) : "wallpaper";
        if (mode === "brand") return Theme.sun;
        if (mode === "mono") return Theme.cream;
        return Theme.accent;
    }

    // ---- i18n ---------------------------------------------------------------
    // The plugin CANNOT use Ryoku's I18n: R4 rejects `import Ryoku.Ui`
    // (plugin_audit.go:228, "internal-import") and I18n lives under
    // Ryoku.Ui.Singletons; PluginKit does not re-export it. Reading shell.json to
    // learn the shell's language is ALSO blocked (R5, plugin_audit.go:428, even
    // for a read). So the plugin carries its own catalogue, read from
    // `pluginApi.pluginDir` — a field the host exposes (docs/plugins.md:285).
    //
    // Source-string-as-key, the same contract as Ryoku's own I18n: a missing key
    // returns the ENGLISH key itself, never "" and never "TODO". The UI can never
    // break because a translation is incomplete.
    // English is the DEFAULT and the source of truth (decision R3-v1). "auto" is
    // available for whoever wants the UI to follow the session locale, but it is
    // not the default: a plugin's language should not silently depend on the
    // machine it happens to run on.
    readonly property string languageSetting: {
        var v = cfg && cfg.language ? String(cfg.language) : "en";
        return ["auto", "en", "es", "fr", "pt", "pt_BR"].indexOf(v) >= 0 ? v : "en";
    }

    // "auto" derives from Qt.locale(), which DOES work inside a plugin (measured:
    // returned "pt_BR" in an offline harness). `pt_BR` keeps its region; any
    // other locale falls back to the part before the underscore; an unknown
    // language resolves to English.
    readonly property string language: {
        if (root.languageSetting !== "auto") return root.languageSetting;
        var name = String(Qt.locale().name || "");
        if (name === "") return "en";
        var full = name.replace("-", "_");
        if (full.toLowerCase() === "pt_br") return "pt_BR";
        var base = full.split("_")[0].toLowerCase();
        return ["en", "es", "fr", "pt"].indexOf(base) >= 0 ? base : "en";
    }

    // The catalogue for the active language. Kept in a property so the whole view
    // re-evaluates when the language changes — no restart, no manual reload.
    property var catalogue: ({})

    FileView {
        id: catalogueFile
        path: root.pluginApi && root.pluginApi.pluginDir
              ? root.pluginApi.pluginDir + "/content/i18n/" + root.language + ".json"
              : ""
        watchChanges: false
        onLoaded: {
            try {
                root.catalogue = JSON.parse(catalogueFile.text());
            } catch (e) {
                // A malformed catalogue degrades to English rather than blanking
                // the UI: the keys ARE the English strings.
                console.log("ai-usage: could not parse " + path + ": " + e);
                root.catalogue = ({});
            }
        }
        onLoadFailed: (e) => { root.catalogue = ({}); }
    }

    // Translate a source string. `%1` is the only substitution used (counts and
    // times), kept because translators often need to reorder it.
    // Translate a source string. `%1`, `%2`… are positional substitutions, kept
    // because translators often need to reorder them. Extra arguments are ignored
    // when the string has no placeholder, so a partial translation never leaves a
    // literal `%2` on screen.
    function tr(key, arg1, arg2, arg3) {
        var s = root.catalogue ? root.catalogue[key] : null;
        if (s === null || s === undefined || s === "") s = key;
        s = String(s);
        var args = [arg1, arg2, arg3];
        for (var i = 0; i < args.length; i++) {
            if (args[i] === undefined || args[i] === null) continue;
            var token = "%" + (i + 1);
            if (s.indexOf(token) >= 0) s = s.split(token).join(String(args[i]));
        }
        return s;
    }

    // The countdown has to tick: Timer in the VIEW, not in the service — it only
    // exists when the host mounts the surface.
    //
    // CRITICAL: `now` is a REPAINT TRIGGER, not a time source. The timer bumps it
    // so that bindings depending on `epoch` re-evaluate once a second; `epoch`
    // itself reads the real clock. Adding the two — `Date.now()/1000 + now`, which
    // is what this was until 2026-10-28 — makes time advance TWICE as fast:
    // measured 3.2 real seconds produced 6.0 seconds of `epoch`. That poisoned
    // every countdown, elapsed percentage, pace, next-reset and data-age reading.
    property int now: 0
    Timer { interval: 1000; running: root.active; repeat: true; onTriggered: root.now++ }
    readonly property real epoch: {
        var tick = root.now;          // dependency: forces re-evaluation each second
        return Date.now() / 1000;     // the actual clock, read fresh
    }

    // ---- reset time formatting (T23) ---------------------------------------
    // ONE convention for every reset in the UI, so the same datum never appears
    // in four shapes (`3h 22m`, `3H18`, `4D56`, `5D` all did):
    //   3h 22min · 4d 56min · 5d        plus the exact clock when it helps:
    //   · Hoje, 18:33 / Amanhã, 09:10 / 12/nov, 14:00
    //
    // `resetParts` is PURE — no locale, no translation, no `root` state except
    // nothing at all. That is what makes it testable in isolation; the localised
    // composition happens in `resetLabel` below.
    function resetParts(resetAt, nowEpoch) {
        if (resetAt === null || resetAt === undefined || resetAt === "") return { valid: false };
        var target = Date.parse(resetAt) / 1000;
        if (!isFinite(target)) return { valid: false };
        var nowS = Number(nowEpoch);
        if (!isFinite(nowS)) return { valid: false };
        var s = Math.max(0, Math.round(target - nowS));
        var days = Math.floor(s / 86400);
        var hours = Math.floor((s % 86400) / 3600);
        var minutes = Math.floor((s % 3600) / 60);
        var relative;
        if (s < 60) {
            relative = "now";
        } else if (s < 3600) {
            relative = minutes + "min";
        } else if (s < 86400) {
            // Always BOTH parts inside a day: "3h 22min", never a bare "3h".
            relative = hours + "h " + minutes + "min";
        } else {
            // Past a day: days + the LARGEST non-zero remainder unit. This is
            // what the owner's own example demands — `4d 56min` (days + minutes)
            // is two units, which rule 2 allows; `4d 0h` would lose the 56
            // minutes and `4d 0h 56min` would be three units, which rule 2
            // forbids. So: hours when there are any, otherwise minutes, otherwise
            // nothing.
            if (hours === 0 && minutes === 0) relative = days + "d";
            else if (hours === 0) relative = days + "d " + minutes + "min";
            else relative = days + "d " + hours + "h";
        }
        return { valid: true, seconds: s, days: days, hours: hours,
                 minutes: minutes, relative: relative };
    }

    // Calendar position of the reset, for the exact-clock suffix. Pure as well.
    // `daysAhead` is a CALENDAR distance (today = 0, tomorrow = 1), not an
    // elapsed-time distance: a reset in 3h may still be "tomorrow" at 23:00.
    function resetClockParts(resetAt, nowEpoch) {
        if (resetAt === null || resetAt === undefined || resetAt === "") return { valid: false };
        var t = new Date(resetAt);
        if (isNaN(t.getTime())) return { valid: false };
        var nowS = Number(nowEpoch);
        if (!isFinite(nowS)) return { valid: false };
        var n = new Date(nowS * 1000);
        var dayA = new Date(n.getFullYear(), n.getMonth(), n.getDate());
        var dayB = new Date(t.getFullYear(), t.getMonth(), t.getDate());
        return {
            valid: true,
            daysAhead: Math.round((dayB - dayA) / 86400000),
            hours: t.getHours(),
            minutes: t.getMinutes(),
            day: t.getDate(),
            month: t.getMonth()
        };
    }

    // ---- footer: freshness, manual refresh, missing data (T30) -------------
    // "Updated 2 min ago" answers a question the bars cannot: is what I am looking
    // at current? It ages while the popout is open because `root.now` ticks (the
    // same Timer that drives the reset countdowns).
    //
    // It reports OUR reading (`lastSuccessEpoch` from the service), not the
    // upstream's `fetched_at`: a report collected hours ago but read a minute ago
    // is a FRESH reading of old data, and saying otherwise would misplace the
    // blame. Provider-level staleness is already shown per provider.
    readonly property real dataAgeSeconds: {
        var t = service ? Number(service.lastSuccessEpoch) : 0;
        if (!isFinite(t) || t <= 0) return -1;
        return Math.max(0, root.epoch - t);
    }

    // Age in the T23 vocabulary: "now", "22min", "3h 22min", "4d 56min". Written
    // here rather than reusing `resetParts` because that function saturates a PAST
    // target at zero — feeding it a past instant returns "now" for any age, which
    // is exactly the bug this comment prevents from coming back.
    function ageText(seconds) {
        var s = Number(seconds);
        if (!isFinite(s) || s < 0) return "";
        s = Math.round(s);
        if (s < 60) return "now";
        var days = Math.floor(s / 86400);
        var hours = Math.floor((s % 86400) / 3600);
        var minutes = Math.floor((s % 3600) / 60);
        if (s < 3600) return minutes + "min";
        if (s < 86400) return hours + "h " + minutes + "min";
        if (hours === 0 && minutes === 0) return days + "d";
        if (hours === 0) return days + "d " + minutes + "min";
        return days + "d " + hours + "h";
    }

    readonly property int troubledProviders: model ? Number(model.with_issues || 0) : 0
    readonly property bool loading: service ? service.loading === true : false

    // The service mounts ONCE and persists; only the view is remounted when the
    // popout opens. So `refresh()` in the service's Component.onCompleted fires
    // on shell start, not on open — reopening showed the model from up to a whole
    // poll interval ago (external review, 2026-10-28). Asking here, on mount,
    // makes "reopening re-reads" true.
    //
    // Guarded: only when the surface is actually ACTIVE and the data is older than
    // a short grace, so a host that remounts the view repeatedly cannot start a
    // collection storm.
    readonly property int reopenRefreshAfter: 30

    Component.onCompleted: {
        if (!root.active) return;
        if (root.service && (root.dataAgeSeconds < 0 || root.dataAgeSeconds > root.reopenRefreshAfter))
            root.requestRefresh();
    }

    onActiveChanged: {
        if (!root.active) return;
        if (root.service && (root.dataAgeSeconds < 0 || root.dataAgeSeconds > root.reopenRefreshAfter))
            root.requestRefresh();
    }

    function requestRefresh() {
        if (!service) return;
        if (typeof service.refresh === "function") service.refresh();
    }

    // In compact mode each provider shows ONE metric — the most critical, measured
    // by percentage, the same rule as `headline_metric` (F020). The others stay
    // behind a per-provider expander. The point is height: seven providers used to
    // fill the whole popout, and most of that was detail nobody reads every time.
    //
    // Expansion state is VOLATILE (decided by the owner on 2026-10-28): it lives in
    // this Item and dies with the surface. Persisting it would require writing to
    // `stateDir`, and this plugin is documented as read-only — R8 allows the write,
    // but the README promises no writing, and a stale expansion set outliving the
    // providers it names is worse than starting fresh.
    readonly property bool compactByDefault: {
        var v = cfg && cfg.density ? String(cfg.density) : "expanded";
        return v === "compact";
    }
    // The mode actually rendered. `null` follows the setting; `true`/`false` is a
    // VIEW-LOCAL override set by the toggle button.
    //
    // Why the override has to exist: the framePopout host hands the content an
    // `api` with `mainInstance`, `pluginSettings`, `pluginDir` and a NO-OP
    // `saveSettings()` — there is no `saveSetting(key, value)`
    // (PluginPopouts.qml:190-195, measured 2026-10-28). A button drawn by the view
    // therefore CANNOT persist the density setting; it can only change what is
    // rendered now. Volatile, which is consistent with the owner's decision that
    // expansion state does not persist.
    property var densityOverride: null
    readonly property bool compactMode: root.densityOverride === null
                                        ? root.compactByDefault
                                        : root.densityOverride === true
    // Ids the user expanded by hand, in compact mode. A plain object as a set;
    // reassigned (never mutated in place) so QML sees the change.
    property var expandedIds: ({})

    function isExpanded(providerId) {
        return root.expandedIds[String(providerId)] === true;
    }

    function toggleExpanded(providerId) {
        var id = String(providerId);
        var proximo = {};
        for (var k in root.expandedIds) proximo[k] = root.expandedIds[k];
        if (proximo[id] === true) delete proximo[id];
        else proximo[id] = true;
        root.expandedIds = proximo;
    }

    // Which metric a provider leads with in compact mode: the highest percentage,
    // tie-broken by report order (first wins), exactly like the collector's
    // `headline_metric`. A metric without a percentage cannot win — it has no
    // magnitude to compare, and picking it would be a guess.
    function leadingMetric(metrics) {
        if (!metrics || metrics.length === 0) return null;
        var best = null, bestPct = -1;
        for (var i = 0; i < metrics.length; i++) {
            var m = metrics[i];
            if (!m) continue;
            var p = m.percent;
            if (p === null || p === undefined || !isFinite(Number(p))) continue;
            if (Number(p) > bestPct) { bestPct = Number(p); best = m; }
        }
        // No metric has a percentage: fall back to the first, so the provider is
        // never blank. The caller draws it without a bar.
        return best !== null ? best : metrics[0];
    }

    // The metrics a provider actually shows, in the current mode.
    function visibleMetrics(provider) {
        if (!provider || !provider.metrics) return [];
        if (!root.compactMode || root.isExpanded(provider.id)) return provider.metrics;
        var lead = root.leadingMetric(provider.metrics);
        return lead === null ? [] : [lead];
    }

    // How many metrics remain hidden behind the expander. TWO different questions
    // live here and conflating them created a real bug (found by external review,
    // 2026-10-28): "how many are hidden right now" is 0 when expanded, but the
    // EXPANDER MUST STAY VISIBLE while expanded — otherwise the only way back is
    // `Collapse all`, which also throws away every other provider's choice.
    function hiddenMetricCount(provider) {
        if (!provider || !provider.metrics) return 0;
        if (!root.compactMode || root.isExpanded(provider.id)) return 0;
        return Math.max(0, provider.metrics.length - root.visibleMetrics(provider).length);
    }

    // Is there anything to toggle for this provider? True whenever compact mode is
    // on and the provider has more than one metric — regardless of the current
    // expansion state. This is what the control's visibility uses.
    function canToggleProvider(provider) {
        if (!provider || !provider.metrics) return false;
        return root.compactMode && provider.metrics.length > 1;
    }

    // How many the control should ANNOUNCE when collapsed. Separate from
    // `hiddenMetricCount` so the label stays correct while expanded.
    function hiddenMetricCountForLabel(provider) {
        if (!provider || !provider.metrics) return 0;
        return Math.max(0, provider.metrics.length - 1);
    }

    // The top button flips the WHOLE surface, which in compact mode means clearing
    // the per-provider exceptions (collapse all) or marking every provider expanded
    // (expand all). In expanded mode the button is absent: there is nothing to
    // compact that the setting has not already decided.
    readonly property bool anyProviderExpanded: {
        for (var k in root.expandedIds) if (root.expandedIds[k] === true) return true;
        return false;
    }

    // TWO controls, one job each.
    //
    // They used to be ONE button with two stacked meanings — the third click in a
    // cycle switched nothing and the only way back to the default view was a
    // separate `Reset view` chip. The owner read that as redundancy and asked for a
    // split (Att1, decided 2026-10-29). Each control now names its own action and
    // never does the other's work:
    //   mode button  — names the mode you are going TO
    //   expand button— names what happens to the LIST, and only exists in compact

    // Destination, not current state: "Compact" means "go compact".
    function modeButtonLabel() {
        return root.compactMode ? root.tr("Expanded") : root.tr("Compact");
    }

    function modeButtonAction() {
        // Either direction starts COLLAPSED: carrying expansions across a mode
        // change would hide the change the user just asked for.
        root.expandedIds = ({});
        root.densityOverride = !root.compactMode;
    }

    // Is there anything list-shaped to toggle at all? A provider with a single
    // quota has nothing to expand, so the control would be inert.
    readonly property bool canToggleAny: {
        var provs = root.model && root.model.all ? root.model.all : [];
        for (var i = 0; i < provs.length; i++) {
            var pr = provs[i];
            if (pr && pr.metrics && pr.metrics.length > 1) return true;
        }
        return false;
    }

    function toggleAll() {
        if (root.anyProviderExpanded) {
            root.expandedIds = ({});
            return;
        }
        var todos = {};
        var provs = root.model && root.model.all ? root.model.all : [];
        for (var i = 0; i < provs.length; i++) {
            if (provs[i] && provs[i].id !== undefined) todos[String(provs[i].id)] = true;
        }
        root.expandedIds = todos;
    }

    // One line at the top says the situation without walking every bar. It counts
    // QUOTAS, not providers, and it never compares percentages across windows:
    // "exhausted" is `percent >= 100` on that quota's own scale.
    //
    // Three different thresholds live in this round on purpose, and they are not
    // interchangeable:
    //   >= 100  exhausted          (this summary)
    //   >  80   "above 80%"        (this summary — the contract's wording)
    //   >= 85   critical colour    (T26, the bar's colour)
    // Raising the summary's 80 to 85 would hide quotas between 80 and 85; lowering
    // the colour's 85 to 80 would repaint bars the contract fixed. Each stays.
    readonly property int exhaustedThreshold: 100
    readonly property int highWaterThreshold: 80

    // Every quota the summary may count: one entry per (provider, metric label).
    // A provider in `error` contributes NOTHING — its quotas are unknown, and
    // counting them as zero or as exhausted would both be inventions.
    //
    // Deduplication is by `(provider id, metric label)`, never by percentage:
    // three metrics above 80% on one provider are three quotas, but the same two
    // windows listed twice are one each. A provider whose two metrics share a
    // label would collapse to one — that is the only case where the rule bites,
    // and it is the honest reading of "the same window".
    function countableQuotas(model) {
        var out = [];
        if (!model) return out;
        var providers = model.all ? model.all : [];
        var seen = ({});
        for (var i = 0; i < providers.length; i++) {
            var p = providers[i];
            if (!p || p.status === "error") continue;
            var metrics = p.metrics ? p.metrics : [];
            for (var j = 0; j < metrics.length; j++) {
                var m = metrics[j];
                if (!m) continue;
                var label = m.label === null || m.label === undefined ? "" : String(m.label);
                var chave = String(p.id) + "\u0000" + label;
                if (seen[chave]) continue;
                seen[chave] = true;
                out.push({ providerId: p.id, label: label, metric: m });
            }
        }
        return out;
    }

    // The summary as data, so the view only renders and the logic is testable.
    // Segments are omitted when they would say zero — "0 exhausted" is noise, and
    // the contract forbids it.
    function operationalSummary(model, nowEpoch) {
        var quotas = root.countableQuotas(model);
        var exhausted = 0, high = 0;
        var nextReset = null, nextSecs = Number.POSITIVE_INFINITY;
        for (var i = 0; i < quotas.length; i++) {
            var m = quotas[i].metric;
            var pct = m.percent;
            if (pct !== null && pct !== undefined && isFinite(Number(pct))) {
                if (Number(pct) >= root.exhaustedThreshold) exhausted++;
                else if (Number(pct) > root.highWaterThreshold) high++;
            }
            // Only FUTURE resets compete for "next"; a past one is not upcoming.
            var r = root.resetParts(m.reset_at, nowEpoch);
            if (r.valid && r.seconds > 0 && r.seconds < nextSecs) {
                nextSecs = r.seconds;
                nextReset = r;
            }
        }
        return {
            exhausted: exhausted,
            high: high,
            nextResetRelative: nextReset ? nextReset.relative : "",
            nextResetSeconds: nextReset ? nextReset.seconds : null,
            total: quotas.length
        };
    }

    // The rendered segments, already translated. Empty array = nothing to say,
    // and then the header hides itself entirely.
    function operationalSummarySegments(model, nowEpoch) {
        var s = root.operationalSummary(model, nowEpoch);
        var out = [];
        // Singular and plural are separate keys: "1 quotas exhausted" is wrong in
        // every language here, and a translator cannot fix a count that arrives as
        // a number inside a fixed string.
        if (s.exhausted === 1) out.push(root.tr("1 quota exhausted"));
        else if (s.exhausted > 1) out.push(root.tr("%1 quotas exhausted", s.exhausted));
        if (s.high === 1) out.push(root.tr("1 quota above %1%", root.highWaterThreshold));
        else if (s.high > 1) out.push(root.tr("%1 quotas above %2%", s.high, root.highWaterThreshold));
        if (s.nextResetRelative !== "")
            out.push(root.tr("next reset in %1", s.nextResetRelative));
        return out;
    }

    // The bar colour must mean the same thing in every theme. It used to come
    // straight from the host accent, which is the USER'S choice and therefore
    // cannot be trusted to signal danger: with a red accent, low consumption
    // looked alarming and critical looked calm.
    //
    // Thresholds are the ones the round signed off: <60 neutral, 60–84 attention,
    // >=85 critical, >=100 exhausted. Documented contrast (WCAG 2.1) against the
    // popout surface `#1e100d` (F014) and against the track, which is the accent
    // at alpha 0.13 over that surface and is therefore always dark:
    //
    //   colour            vs surface   vs track (worst accent tested)
    //   critical #e2342a      4.19        3.72      (amber accent)
    //   attention #d9a441     8.00        7.22
    //   neutral (accent)      >=4.0       >=3.4   (accent-dependent, see below)
    //
    // All pass SC 1.4.11's 3:1 for non-text contrast. Colour never carries the
    // state alone: the percentage and the metric label already say it (SC 1.4.1).
    //
    // THE SCALE WINS OVER TheACCENT for attention and critical. If the user's
    // accent is itself red, "low consumption" must not read as danger — the
    // semantic reading is not negotiable, so only the NEUTRAL band follows the
    // accent. That is the one place the plugin overrides the host's styling, and
    // it is deliberate.
    readonly property color semanticAttention: Theme.gold      // #d9a441
    readonly property color semanticCritical: Theme.sun        // #e2342a

    // Pure: percent (and the accent for the neutral band) in, colour out. Always
    // returns a VALID colour — a missing or absurd percent falls back to the
    // accent, and an invalid accent falls back to the theme's own accent. The
    // guard matters: returning an invalid colour paints nothing and would leave a
    // metric silently blank.
    function validColour(c) {
        return c !== null && c !== undefined
            && isFinite(c.r) && isFinite(c.g) && isFinite(c.b)
            && (c.a === undefined || (isFinite(c.a) && c.a > 0.05));
    }

    // Does this colour already read as "danger"? A red/orange accent cannot serve
    // as the NEUTRAL band: 30% consumption would look like an alarm, which is
    // precisely the defect this task exists to remove.
    //
    // Detected by HUE plus LIGHTNESS, and the lightness test is essential: this
    // theme's default accent is `#ffb4a8`, a soft peach whose hue is 8° and whose
    // saturation is 1.0 — a saturation-only test called it danger and would have
    // desaturated the plugin's normal look for every user. A pastel red is not an
    // alarm; a saturated dark red is. Measured: `#ffb4a8` L=0.83 (safe, stays),
    // `#e2342a` L=0.53 (danger, neutral band desaturated).
    function isDangerHue(c) {
        if (!root.validColour(c)) return false;
        var deg = c.hslHue * 360;
        var sat = c.hslSaturation;
        var lig = c.hslLightness;
        if (!isFinite(deg) || !isFinite(sat) || !isFinite(lig)) return false;
        var inBand = (deg >= 335 || deg <= 25);
        return inBand && sat >= 0.35 && lig <= 0.65;
    }

    // The neutral band: the accent when it is safe to use, otherwise the SAME
    // hue with the saturation pulled down. Desaturated, not replaced — the plugin
    // stays in the user's colour family while stopping the false alarm.
    function neutralColour(accent) {
        var base = root.validColour(accent) ? accent
                 : (root.validColour(root.accentColor) ? root.accentColor : Theme.bright);
        if (!root.isDangerHue(base)) return base;
        return Qt.hsla(base.hslHue, base.hslSaturation * 0.22,
                       Math.min(0.86, base.hslLightness + 0.18), base.a);
    }

    // Pure: percent (and the accent for the neutral band) in, colour out. Always
    // returns a VALID colour — a missing or absurd percent falls back to the
    // neutral band, and an invalid accent falls back to the theme's own accent.
    // The guard matters: an invalid colour paints nothing and would leave a
    // metric silently blank.
    function usageColour(percent, accent) {
        var neutral = root.neutralColour(accent);
        var p = Number(percent);
        if (percent === null || percent === undefined || !isFinite(p)) return neutral;
        if (p >= 85) return root.semanticCritical;
        if (p >= 60) return root.semanticAttention;
        return neutral;
    }

    // Absolute consumption and pace are DIFFERENT things and used to share one
    // line: "32% elapsed · 68pts ahead" read as a single, ambiguous statement.
    // They are now three labelled readings, and each one is derived in ONE place.
    //
    // Pace exists only when the window length is known. Without `window_secs`
    // there is no elapsed time, so there is NO pace — showing 0 would invent a
    // datum. That is why every function here returns `valid: false` and the view
    // renders an em dash instead of a number.
    //
    // `reset_at` gives the remaining time and `window_secs` the total, so:
    //   elapsed_secs = window_secs - (reset_at - now)
    // which is the same protocol the upstream's own `detail` describes, but
    // DERIVED here instead of parsed from prose.
    function elapsedRatio(metric, nowEpoch) {
        if (!metric) return { valid: false };
        var win = metric.window_secs;
        if (win === null || win === undefined) return { valid: false };
        win = Number(win);
        if (!isFinite(win) || win <= 0) return { valid: false };
        var resetAt = metric.reset_at;
        if (resetAt === null || resetAt === undefined || resetAt === "") return { valid: false };
        var target = Date.parse(resetAt) / 1000;
        var nowS = Number(nowEpoch);
        if (!isFinite(target) || !isFinite(nowS)) return { valid: false };
        var remaining = Math.max(0, target - nowS);
        var elapsed = Math.min(win, Math.max(0, win - remaining));
        return { valid: true, elapsedSecs: elapsed, windowSecs: win,
                 percent: Math.round(elapsed / win * 100) };
    }

    // Pace = usage − elapsed, in percentage points. Positive means burning faster
    // than the window; negative means headroom. `|pace| < 1pp` is "on pace": it
    // absorbs the rounding noise of two independently rounded percentages and
    // avoids claiming a direction that is not really there.
    function pacePoints(usagePercent, elapsedPercent) {
        if (usagePercent === null || usagePercent === undefined) return { valid: false };
        if (elapsedPercent === null || elapsedPercent === undefined) return { valid: false };
        var u = Number(usagePercent), e = Number(elapsedPercent);
        if (!isFinite(u) || !isFinite(e)) return { valid: false };
        var diff = u - e;
        return { valid: true, points: diff, onPace: Math.abs(diff) < 1 };
    }

    // The three labelled lines, ready to draw. `usage` is ALWAYS present when the
    // metric has a percentage (that is the absolute datum); `elapsed` and `pace`
    // appear only when derivable. An em dash is the honest answer for "not
    // derivable", never a zero.
    function usageReadings(metric, nowEpoch) {
        if (!metric) return [];
        var out = [];
        var pct = metric.percent;
        var hasPct = pct !== null && pct !== undefined && isFinite(Number(pct));
        if (hasPct)
            out.push({ kind: "usage", label: root.tr("Usage"),
                       value: root.tr("%1% of the quota", Math.round(Number(pct))) });
        var el = root.elapsedRatio(metric, nowEpoch);
        if (el.valid)
            out.push({ kind: "elapsed", label: root.tr("Elapsed"),
                       value: root.tr("%1% of the window", el.percent) });
        if (hasPct && el.valid) {
            var pc = root.pacePoints(Number(pct), el.percent);
            if (pc.valid) {
                var pts = Math.round(Math.abs(pc.points));
                var value;
                if (pc.onPace) value = root.tr("on pace with the window");
                else if (pc.points > 0) value = root.tr("%1 percentage points above the fair share", pts);
                else value = root.tr("%1 percentage points below the fair share", pts);
                out.push({ kind: "pace", label: root.tr("Pace"), value: value,
                           ahead: pc.points > 0 && !pc.onPace });
            }
        }
        // The upstream `detail` survives ONLY where it is absolute data, not pace
        // prose. The fixture shows both kinds: "0 of 200 used" (absolute, keep)
        // and "61% elapsed · 30pts ahead" (pace prose, replaced above).
        if (!el.valid && metric.detail)
            out.push({ kind: "detail", label: "", value: String(metric.detail) });
        return out;
    }

    // The time pattern follows the ACTIVE LANGUAGE's locale, not the machine's:
    // a user reading the UI in English should not get Portuguese clock rules.
    function clockText(c) {
        if (!c || !c.valid) return "";
        var locName = root.language === "auto" ? "" : root.language;
        var loc = locName === "" ? Qt.locale() : Qt.locale(locName);
        var date = new Date(2000, c.month, c.day, c.hours, c.minutes, 0);
        var time;
        try {
            time = date.toLocaleTimeString(loc, Locale.ShortFormat);
        } catch (e) {
            var hh = String(c.hours).padStart(2, "0");
            var mm = String(c.minutes).padStart(2, "0");
            time = hh + ":" + mm;
        }
        var dayLabel;
        if (c.daysAhead === 0) dayLabel = root.tr("Today");
        else if (c.daysAhead === 1) dayLabel = root.tr("Tomorrow");
        else {
            var monthShort = "?";
            try { monthShort = loc.monthName(c.month, Locale.ShortFormat); } catch (e) {}
            dayLabel = c.day + "/" + monthShort;
        }
        return dayLabel + ", " + time;
    }

    // The one entry point the UI uses. Nothing draws a reset time any other way.
    function resetLabel(resetAt) {
        var p = root.resetParts(resetAt, root.epoch);
        if (!p.valid) return "";
        var label = p.relative === "now"
                  ? root.tr("RESET NOW")
                  : root.tr("RESET IN %1", p.relative);
        // The exact clock is a help, not a substitute. Past a week it stops
        // helping — the relative number is enough and the line stays short.
        var c = root.resetClockParts(resetAt, root.epoch);
        if (c.valid && c.daysAhead >= 0 && c.daysAhead <= 7)
            label += " · " + root.clockText(c);
        return label;
    }

    // Does another provider in `model.all` produce the same base label under the
    // current mode? Only then does the account need to be shown.
    function labelIsAmbiguous(provider, base) {
        var provs = root.model && root.model.all ? root.model.all : [];
        var alvo = String(base).toLowerCase();
        for (var i = 0; i < provs.length; i++) {
            var outro = provs[i];
            if (!outro || outro.id === provider.id) continue;
            var outroBase = outro.display_name || outro.id;
            if (root.secondaryLabelMode === "short" && outro.short_name) outroBase = outro.short_name;
            else if (root.secondaryLabelMode === "plan" && outro.plan)
                outroBase = root.redactText(outro.plan) || outro.display_name || outro.id;
            if (String(outroBase).toLowerCase() === alvo) return true;
        }
        return false;
    }

    function secondaryName(provider) {
        var base;
        if (root.secondaryLabelMode === "short" && provider.short_name) base = provider.short_name;
        else if (root.secondaryLabelMode === "plan" && provider.plan) {
            base = root.redactText(provider.plan) || provider.display_name || provider.id;
        } else base = provider.display_name || provider.id;
        // Two accounts of the same vendor can share `display_name` (both "Beta"),
        // so the name alone cannot tell them apart — the report carries them apart
        // in `account`, and the README promises the panel distinguishes them.
        //
        // Appended ONLY when the label is genuinely ambiguous, i.e. when another
        // provider in the same list produced the SAME base label. Appending always
        // would break the `short` mode, whose whole point is a short code
        // ("ghc" becoming "ghc@work" defeats it). Never appended twice either: a
        // base that already contains the account is left alone.
        var acc = provider.account ? String(provider.account) : "";
        if (acc === "") return base;
        if (String(base).toLowerCase().indexOf(acc.toLowerCase()) >= 0) return base;
        if (!root.labelIsAmbiguous(provider, base)) return base;
        return base + " @" + acc;
    }

    function redactText(value) {
        return String(value || "")
            .replace(/sk-[^\s]+/ig, "[REDACTED]")
            .replace(/(api[_-]?key\s*[:=]\s*)[^\s,;]+/ig, "$1[REDACTED]");
    }

    // Cut at a WORD boundary, for when the text has to be shortened before it
    // reaches the `Text`.
    //
    // Why it exists: truncating with `slice(0, N)` splits words in half.
    // Measured on kiro's real error (102 chars), with N=56:
    //   "credentials error: no Kiro CLI `kirocli:odic:token` entr"
    // — "entry" cut in half. Worse: that `Text` ALREADY has `elide:
    // Text.ElideRight`, so the blind cut PREVENTED the correct elision (the text
    // arrived too short for elide to act, and short in the wrong way).
    //
    // Semantics (T19 contract):
    //   - empty/null -> ""
    //   - fits within the limit -> unchanged, WITHOUT an ellipsis
    //   - does not fit -> longest prefix ending at a word boundary + "…"
    //   - a single word longer than the limit -> cut at the limit (there is no
    //     word boundary to respect); never returns "" and never loops
    //   - limit <= 0 -> ""
    function truncateAtWord(text, limit) {
        var s = String(text === null || text === undefined ? "" : text);
        var n = Math.floor(Number(limit));
        if (!isFinite(n) || n <= 0) return "";
        if (s.length <= n) return s;
        var cut = s.slice(0, n);
        // If the FOLLOWING character ends a word (it is a space, or the text has
        // ended), then the whole prefix ends on a complete word: use all of it.
        // Without this, "alpha beta gamma" with limit 10 — where the prefix
        // "alpha beta" is already whole words — would return only "alpha…",
        // wasting half the width (the same sin as slice, to a lesser degree).
        // Found by joseki-tester as an ambiguity in the contract.
        if (cut.length === n && /^\s/.test(s.slice(n, n + 1))) {
            return cut.replace(/\s+$/, "") + "…";
        }
        var lastSpace = cut.lastIndexOf(" ");
        if (lastSpace > 0) {
            // There is a word boundary within the limit: cut there.
            return cut.slice(0, lastSpace).replace(/\s+$/, "") + "…";
        }
        // No space in the prefix: one giant word. Cutting at the limit is the
        // only way out; returning "" would hide the text entirely.
        return cut + "…";
    }

    // The framePopout sizes the body by doing `implicitWidth/Height * root.s`, so
    // the intrinsic dimensions go in HERE without multiplying by `s`.
    // `widthBudget` arrives from the host already multiplied.
    readonly property real baseWidth: 430
    readonly property real available: widthBudget > 0 ? widthBudget : baseWidth * root.s
    readonly property real padX: pad * root.s
    readonly property real padY: Math.round(pad * 0.8) * root.s
    readonly property real contentWidth: Math.max(160 * root.s, available - 2 * padX)

    implicitWidth: baseWidth
    implicitHeight: Math.max(1, (col.implicitHeight + 2 * padY) / Math.max(0.001, root.s))

    // Usage meter: track + severity fill, with the value OUTSIDE the track (on the
    // right) and the track reserving that width. With a full bar the text never
    // lands on top of the fill — white on red is not legibility, and that is the
    // defect the real smoke test called out.
    //
    // T25: a 1–2px vertical tick marks where the ELAPSED TIME sits in the window.
    // The deviation between usage and time becomes visible without reading a
    // number — the fill to the right of the tick means "ahead of schedule". The
    // tick NEVER recolours the bar: bar and tick are separate channels, which is
    // the `meter-quota-rule` pattern (a fixed rule marks a threshold; it does not
    // repaint the value) and what WCAG 1.4.1 asks for (state must not rest on
    // colour alone — and here it does not rest on colour at all).
    component Meter: Item {
        id: med
        property var metric
        property real thickness: 5
        property real valueFontSize: 10
        // Elapsed percentage of the window, or -1 when not derivable. -1 draws
        // no tick at all (a tick at 0% would claim "just started").
        property real elapsedPercent: -1
        // T30: does this metric carry a percentage at all? `0` is a real reading
        // (empty bar); `null`/absent is a different state (no bar, em dash).
        readonly property bool hasPercent: med.metric !== null && med.metric !== undefined
            && med.metric.percent !== null && med.metric.percent !== undefined
            && isFinite(Number(med.metric.percent))
        height: Math.max(thickness, label.implicitHeight)

        Text {
            id: label
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.bright
            font.family: Theme.mono
            font.pixelSize: med.valueFontSize
            text: med.metric ? (med.metric.value || "") : ""
        }
        Rectangle {
            id: track
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(0, parent.width - label.implicitWidth - 6 * root.s)
            height: med.thickness
            radius: height / 2
            color: Theme.threadBg
            // T30: `0%` and "no datum" must not look alike. A metric with a
            // percentage draws a track (an empty one at 0%, which reads as "nothing
            // used"). A metric WITHOUT a percentage draws NO track at all — the
            // absence of the bar is the signal, and the view shows an em dash
            // instead. Drawing an empty track for both was the conflation this task
            // removes.
            visible: med.hasPercent
            Rectangle {
                width: {
                    var h = med.metric;
                    return h && h.percent !== null ? parent.width * h.percent / 100 : 0;
                }
                height: parent.height; radius: height / 2
                color: {
                    var h = med.metric;
                    if (!h) return Theme.faint;
                    // T26: the colour comes from the PERCENT through the semantic
                    // scale, not from the upstream's `severity` field. The two
                    // disagree on a real case (89% is `high` upstream, `critical`
                    // by these thresholds) and the signed contract fixes the
                    // thresholds — see the note on `usageColour`.
                    return root.usageColour(h.percent, root.accentColor);
                }
                Behavior on width { NumberAnimation { duration: 220; easing.type: Easing.OutExpo } }
            }
            // The elapsed tick. Drawn last so it sits above the fill; 2px wide,
            // and its colour is the bright ink of the theme so it contrasts with
            // both the track and every severity colour the fill can take.
            //
            // The alpha lives in the COLOUR, not in `opacity`: the design
            // invariant is "one live opaque accent per screen", and an item
            // opacity would still hand an opaque colour to anything inspecting
            // `color.a`. The tick is not a fill, so it must not read as one.
            // `radius: height / 2` is the honest shape — a vertical capsule,
            // 2px across with fully rounded ends.
            Rectangle {
                id: elapsedTick
                visible: med.elapsedPercent >= 0
                width: Math.max(2, Math.round(1.5 * root.s))
                height: parent.height + Math.round(2 * root.s)
                y: -Math.round(1 * root.s)
                x: Math.max(0, Math.min(parent.width - width,
                       parent.width * med.elapsedPercent / 100 - width / 2))
                color: Qt.rgba(Theme.bright.r, Theme.bright.g, Theme.bright.b, 0.85)
                radius: height / 2
            }
        }
    }


    // The per-provider expander (T28, contract item 3). It is NOT global: expanding
    // one provider must leave the others exactly as they were. It only exists when
    // there IS something hidden — a control that does nothing is noise.
    component Expander: Item {
        id: exp
        property var provider
        // The chip is a control, not prose: it sits at the `meta` step, which is
        // the same weight as the count it announces. Passed as a role (never a raw
        // number) so it cannot drift away from the scale (Att2).
        // Already scaled: `fsMeta` carries `s`, so the Text must NOT multiply
        // again. (Doing `fsMeta / s` here and `* s` there was a needless round trip
        // that also risked dividing by zero when the host reports s = 0.)
        property real fontSize: root.fsMeta
        // Visibility uses `canToggleProvider`, NOT "hidden > 0": the control has to
        // stay on screen while expanded, otherwise it could never collapse back.
        readonly property int hidden: root.hiddenMetricCountForLabel(exp.provider)
        // NOT `readonly property bool expanded: root.isExpanded(...)`: that is a
        // FUNCTION call, so QML cannot see the dependency on `expandedIds` and the
        // chip never repainted on toggle — it said "+2 more" while expanded
        // (measured 2026-10-29). Reading the property IN the expression is what
        // makes the dependency visible to the engine.
        readonly property bool expanded: {
            var ids = root.expandedIds;   // the dependency, read here on purpose
            var id = exp.provider ? exp.provider.id : "";
            return ids !== null && ids !== undefined && ids[id] === true;
        }
        visible: root.canToggleProvider(exp.provider)
        width: visible ? expLabel.implicitWidth + 14 * root.s : 0
        height: visible ? expLabel.implicitHeight + 5 * root.s : 0

        // Drawn as a CHIP, not as loose text.
        //
        // It used to be bare "+2 more" in `faint` (the timestamp's weight) with no
        // border, sitting right after the provider name. The owner could not tell it
        // was a control at all: "o botão que aciona isso não está intuitivo"
        // (Att1, 2026-10-29). A border and a caret say "this is pressable and it
        // does something to the list"; the `+N`/`−` glyph says WHICH way.
        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: expMouse.containsMouse ? Theme.threadBg : "transparent"
            border.width: 1
            border.color: expMouse.containsMouse ? Theme.lineStrong : Theme.lineStrong
            opacity: expMouse.containsMouse ? 1.0 : 0.75
        }

        Text {
            id: expLabel
            anchors.centerIn: parent
            // Not `faint` unless idle: the chevron carries the state, the text the
            // count. Both are legible on hover.
            color: expMouse.containsMouse || exp.expanded ? Theme.bright : Theme.faint
            font.family: Theme.mono
            font.pixelSize: exp.fontSize
            font.letterSpacing: 0.3 * root.s
            text: {
                // A caret in front, so the direction of the click is visible before
                // reading the words: down = "there is more below", up = "close it".
                var caret = exp.expanded ? "\u25B4" : "\u25BE";
                return caret + " " + (exp.expanded
                    ? root.tr("less")
                    : root.tr("+%1 more", exp.hidden));
            }
        }
        MouseArea {
            id: expMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: if (exp.provider) root.toggleExpanded(exp.provider.id)
        }
    }

    Column {
        id: col
        // NO objectName here on purpose: the harness dumps `KIND|<type>(<ptr>)`,
        // and a named widget makes QML's type string carry a memory address, so
        // two runs never compare equal. The measurement that needed a handle was
        // done by counting filled bars instead — see the T28 evidence.
        x: root.padX
        y: root.padY
        width: root.contentWidth
        spacing: root.gap * root.s

        // ---- header: operational summary + density toggle (T27 + T28) --------
        // One row, not two: the whole point of T28 is HEIGHT. The summary takes the
        // width it needs and the button sits at the far right.
        //
        // The button only exists in compact mode — in expanded mode there is
        // nothing to collapse that the setting has not already decided, and an
        // inert button is worse than no button.
        // Header: the summary on its OWN full-width line, the controls on the line
        // below, right-aligned.
        //
        // Why not side by side: with both controls visible in Portuguese the summary
        // had 231px of the 350 it needs, so it was always chopped short right where
        // the button started — which reads as the button covering the text ("no
        // monitor com escala maior, o texto começa a ser tampado pelos botões", P6,
        // measured 2026-10-29). Squeezing them into one line cannot work: the labels
        // grow with the scale and with the translation, and there is no threshold to
        // elide at that is both readable and honest.
        //
        // A `Row` of controls was tried and DISCARDED: Qt does not re-run its layout
        // when a child's `visible` flips, so the two buttons landed on the same x
        // (measured: both at x=372, `width: childrenRect.width` made it worse by
        // creating a binding cycle). Anchored buttons in a plain Item do not have
        // that problem, so they are anchored to each other here.
        Column {
            id: headerRow
            width: parent.width
            // Gap only when both lines exist: a lone summary keeps its tight rhythm.
            spacing: controlsRow.visible ? 5 * root.s : 0
            visible: root.primaryProvider !== null

            // The summary WRAPS instead of being cut, and it spans the full width —
            // it is the only sentence on the surface and it carries the most urgent
            // news, so it gets the whole line (P6: "com pouco ênfase").
            Text {
                id: summaryLine
                width: parent.width
                visible: text !== ""
                wrapMode: Text.WordWrap
                // `cream`, not `faint`: `faint` is the timestamp's weight, and using
                // it here made the most important line the quietest thing on screen.
                color: Theme.cream
                font.family: Theme.mono
                font.pixelSize: root.fsBody
                text: root.operationalSummarySegments(root.model, root.epoch).join("  ·  ")
            }

            Item {
                id: controlsRow
                width: parent.width
                height: modeButton.height
                visible: root.primaryProvider !== null

                // LEFT: the list. It exists only in compact mode, because that is
                // the only mode with a list to expand — in expanded mode every quota
                // is already shown, so an "Expand absolutely everything" button
                // would be inert. It is NOT a mode switch.
                Rectangle {
                    id: expandButton
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.compactMode && root.canToggleAny
                    width: visible ? expandLabel.implicitWidth + 12 * root.s : 0
                    height: 16 * root.s
                    radius: height / 2
                    color: expandMouse.containsMouse ? Theme.threadBg : "transparent"
                    border.width: 1
                    border.color: Theme.lineStrong

                    Text {
                        id: expandLabel
                        anchors.centerIn: parent
                        color: expandMouse.containsMouse ? Theme.bright : Theme.faint
                        font.family: Theme.mono
                        font.pixelSize: root.fsMeta
                        text: root.anyProviderExpanded ? root.tr("Collapse all")
                                                      : root.tr("Expand all")
                    }
                    MouseArea {
                        id: expandMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.toggleAll()
                    }
                }

                // RIGHT: the mode. Always visible, and it names the mode you are
                // going TO — never the state you are in. It used to require compact
                // mode already being on, so it was exactly the control you could not
                // use to GET there (owner report, 2026-10-28).
                //
                // `Reset view` was here and is GONE: it existed only because this
                // button carried two meanings, so nothing could return to the
                // default view. With the mode switch isolated, the way back is the
                // button itself (Att1, decided 2026-10-29).
                Rectangle {
                    id: modeButton
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    width: modeLabel.implicitWidth + 12 * root.s
                    height: 16 * root.s
                    radius: height / 2
                    color: modeMouse.containsMouse ? Theme.threadBg : "transparent"
                    border.width: 1
                    border.color: Theme.lineStrong

                    Text {
                        id: modeLabel
                        anchors.centerIn: parent
                        color: modeMouse.containsMouse ? Theme.bright : Theme.faint
                        font.family: Theme.mono
                        font.pixelSize: root.fsMeta
                        text: root.modeButtonLabel()
                    }
                    MouseArea {
                        id: modeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.modeButtonAction()
                    }
                }
            }
        }

        // ---- no data, with an error, or loading ---------------------------
        // Three distinct states, discriminated by `errorKind` (not by text): the
        // missing-dependency warning exists because the way out of it belongs to
        // the user — install the binary. An upstream failure has no local way out,
        // so it shows the diagnostic. Neither of them is `LOADING`.
        Column {
            visible: root.primaryProvider === null
            width: parent.width
            spacing: 4 * root.s

            Text {
                width: parent.width
                elide: Text.ElideRight
                color: Theme.faint
                font.family: Theme.mono
                font.pixelSize: root.fsTitle
                font.letterSpacing: 1.2 * root.s
                text: {
                    if (root.errorKind === "dep-missing") return root.tr("MISSING DEPENDENCY");
                    // The upstream diagnostic is redacted here too. The per-provider
                    // path already did this; leaving the global path raw meant the
                    // SAME kind of text was scrubbed in one place and printed in the
                    // other (found by external review, 2026-10-28).
                    if (root.errorKind === "upstream") return root.tr("NO DATA") + " · " + root.redactText(root.lastError);
                    // LOADING only while a collection is actually in flight. With no
                    // primary and no error and nothing loading, the report simply
                    // has no usable provider — saying "LOADING" then promises an
                    // operation that already finished (same review).
                    if (root.loading) return root.tr("LOADING");
                    return root.tr("NO PROVIDERS");
                }
            }
            // Install command: only in the case it resolves. In mono, so the eye
            // recognises what to copy. `wrapMode` instead of `elide` so the command
            // never appears cut in half.
            Text {
                visible: root.errorKind === "dep-missing"
                width: parent.width
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                color: Theme.bright
                font.family: Theme.mono
                font.pixelSize: root.fsTitle
                text: "ai-usagebar " + root.tr("not found. Install it with:") + "\nparu -S ai-usagebar-bin"
            }
        }

        Column {
            visible: root.primaryProvider !== null
            width: parent.width
            spacing: 4 * root.s

            Row {
                width: parent.width
                spacing: 6 * root.s
                Text {
                    width: Math.max(0, parent.width - primNameGap.width)
                    elide: Text.ElideRight
                    color: Theme.bright
                    font.family: Theme.font
                    font.pixelSize: root.fsDisplay
                    text: root.primaryProvider ? root.primaryProvider.display_name : ""
                }
                Expander {
                    id: primNameGap
                    provider: root.primaryProvider
                }
            }
            Text {
                width: parent.width
                elide: Text.ElideRight
                // status + plan in tracked mono: short telemetry (Tactical)
                color: root.primaryProvider && root.primaryProvider.status === "error" ? Theme.sun : Theme.faint
                font.family: Theme.mono
                font.pixelSize: root.fsMeta
                font.letterSpacing: 1 * root.s
                text: {
                    if (!root.primaryProvider) return "";
                    var p = root.primaryProvider;
                    // No blind cut: this Text's `elide` cuts at a word boundary
                    // according to the REAL width, not at 56 characters.
                    if (p.status === "error") return root.tr("ERROR") + " · " + root.redactText(p.error || "no detail");
                    var plan = root.redactText(p.plan);
                    var out = plan ? plan.toUpperCase() : p.id.toUpperCase();
                    if (p.stale) out += " · " + root.tr("STALE");
                    if (p.account) out += " · " + p.account.toUpperCase();
                    return out;
                }
            }
            Repeater {
                // T28: in compact mode only the leading metric shows, unless the
                // user expanded this provider.
                model: root.visibleMetrics(root.primaryProvider)
                delegate: Column {
                    required property var modelData
                    width: parent.width
                    spacing: 3 * root.s
                    Text {
                        width: parent.width
                        elide: Text.ElideRight
                        color: Theme.faint
                        font.family: Theme.mono
                        font.pixelSize: root.fsBody
                        font.letterSpacing: 0.8 * root.s
                        text: modelData.label ? modelData.label.toUpperCase() : root.tr("USAGE")
                    }
                    Meter {
                        width: parent.width
                        thickness: 6 * root.s
                        valueFontSize: root.fsValue
                        metric: modelData
                        elapsedPercent: {
                            var el = root.elapsedRatio(modelData, root.epoch)
                            return el.valid ? el.percent : -1
                        }
                    }
                    // The three readings, one per line, each with its own label.
                    // Never concatenated: that was the ambiguity being removed.
                    //
                    // `showMetricDetail` is labelled "Show primary pace detail",
                    // so it governs the DERIVED lines (elapsed, pace) and the
                    // upstream detail — never `Usage`, which is the absolute datum
                    // the widget exists to show. Hiding it when someone turns off
                    // "pace detail" would empty the metric.
                    // The model is ALWAYS the full list; the setting gates each row's
                    // visibility. Passing `showDetail ? list : []` here deleted
                    // `Usage` along with the rest — the absolute datum vanished with
                    // the pace detail (caught by T9, 2026-10-28).
                    Repeater {
                        model: root.usageReadings(modelData, root.epoch)
                        delegate: Row {
                            required property var modelData
                            width: parent.width
                            spacing: 5 * root.s
                            // `usage` is never gated; elapsed/pace/detail are.
                            visible: modelData.kind === "usage" || root.showDetail
                            height: visible ? implicitHeight : 0
                            Text {
                                visible: modelData.label !== ""
                                color: Theme.faint
                                font.family: Theme.mono
                                font.pixelSize: root.fsBody
                                // NO tracking: these labels introduce full
                                // sentences ("61% of the window"), not short
                                // telemetry. Tracked caps is the Tactical rule for
                                // cooldowns, percentages and metric labels only.
                                text: modelData.label ? (modelData.label + ":") : ""
                            }
                            Text {
                                color: modelData.kind === "pace" && modelData.ahead ? Theme.sun : Theme.faint
                                font.family: Theme.mono
                                font.pixelSize: root.fsBody
                                elide: Text.ElideRight
                                text: modelData.value
                            }
                        }
                    }
                    // A metric with no percentage at all says so, with an em dash.
                    // `0%` is a real reading and draws an empty bar; ABSENCE is a
                    // different state and must never look like zero (T30).
                    Text {
                        visible: (modelData.percent === null || modelData.percent === undefined)
                                 && root.showDetail
                        color: Theme.faint
                        font.family: Theme.mono
                        font.pixelSize: root.fsBody
                        text: "—"
                    }
                    Text {
                        visible: text !== ""
                        color: Theme.faint
                        font.family: Theme.mono
                        font.pixelSize: root.fsMeta
                        font.letterSpacing: 0.8 * root.s
                        text: root.resetLabel(modelData.reset_at)
                    }
                }
            }
        }

        // ---- separator + list header --------------------------------------
        // The line takes only the space AFTER the label — no mask: `Text` has no
        // `background` (that belongs to `Control`), and using that property killed
        // object creation, so `col` never came to life, contentLoader.item stayed
        // null and the host fell back to 680x520. The result on screen was a huge,
        // empty body.
        Item {
            visible: root.showSecondary && root.secondaryProviders.length > 0
            width: parent.width
            height: 18 * root.s
            Row {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8 * root.s
                Text {
                    id: sepLabel
                    color: Theme.faint
                    font.family: Theme.mono
                    font.pixelSize: root.fsTitle
                    font.letterSpacing: 1.4 * root.s
                    text: root.tr("OTHER PROVIDERS") + " " + root.secondaryProviders.length + "/" + root.totalSecondary
                }
                Item {
                    width: Math.max(0, parent.width - sepLabel.implicitWidth - parent.spacing)
                    height: 1
                    Rectangle {
                        anchors.fill: parent
                        color: Theme.lineStrong
                    }
                }
            }
        }

        // ---- secondaries: one per row, with a cooldown where one exists -----
        Repeater {
            model: root.showSecondary ? root.secondaryProviders : []
            delegate: Column {
                required property var modelData
                width: col.width
                spacing: 4 * root.s

                Rectangle {
                    width: parent.width
                    height: 1 * root.s
                    color: Theme.lineStrong
                    opacity: 0.65
                }

                // Provider content, indented from the line: the line marks the
                // group boundary, the indent separates the block from the provider
                // above it.
                Item {
                    id: block
                    x: root.secondaryIndent
                    width: parent.width - root.secondaryIndent
                    height: inner.implicitHeight

                    Column {
                        id: inner
                        width: parent.width
                        spacing: 3 * root.s

                        Row {
                            width: parent.width
                            spacing: 5 * root.s
                            Text {
                                width: Math.max(0, parent.width - secExpander.width)
                                elide: Text.ElideRight
                                // an error comes out in colour AND in a word (never colour alone)
                                color: modelData.status === "error" ? Theme.sun : Theme.bright
                                font.family: Theme.font
                                font.pixelSize: root.fsTitle
                                text: (modelData.status === "error" ? "! " : "")
                                      + root.secondaryName(modelData)
                            }
                            Expander {
                                id: secExpander
                                provider: modelData
                            }
                        }
                Repeater {
                            model: root.visibleMetrics(modelData)
                            delegate: Column {
                                required property var modelData
                                width: parent.width
                                spacing: 1 * root.s
                                Row {
                                    width: parent.width
                                    spacing: 5 * root.s
                                    Text {
                                        width: Math.max(0, parent.width - reset.implicitWidth - parent.spacing)
                                        elide: Text.ElideRight
                                        color: Theme.faint
                                        font.family: Theme.mono
                                        font.pixelSize: root.fsMeta
                                        font.letterSpacing: 0.5 * root.s
                                        text: modelData.label ? modelData.label.toUpperCase() : "USAGE"
                                    }
                                    Text {
                                        id: reset
                                        color: Theme.faint
                                        font.family: Theme.mono
                                        font.pixelSize: root.fsMeta
                                        font.letterSpacing: 0.4 * root.s
                                        text: root.resetLabel(modelData.reset_at)
                                    }
                                }
                                Meter {
                                    width: parent.width
                                    thickness: 3 * root.s
                                    // `fsBody`, NOT `fsValue * 0.78`: the scaled variant
                                    // landed 1px under `body` at s>=1.5 — a sixth step
                                    // created by arithmetic, invisible at s=1 and a
                                    // half-step at every larger scale. A secondary's
                                    // number is body text; it does not get its own step.
                                    valueFontSize: root.fsBody
                                    metric: modelData
                                    // T24/T25 apply to EVERY quota, not only the
                                    // highlighted one. Leaving this out made the
                                    // marker and the readings privilege whichever
                                    // provider happened to be expanded — found by
                                    // external review, 2026-10-28.
                                    elapsedPercent: {
                                        var el = root.elapsedRatio(modelData, root.epoch)
                                        return el.valid ? el.percent : -1
                                    }
                                }
                                // The same three labelled readings as the primary,
                                // one size down. Compact mode already limits them.
                                Repeater {
                                    model: root.usageReadings(modelData, root.epoch)
                                    delegate: Row {
                                        required property var modelData
                                        width: parent.width
                                        spacing: 4 * root.s
                                        visible: modelData.kind === "usage" || root.showDetail
                                        height: visible ? implicitHeight : 0
                                        Text {
                                            visible: modelData.label !== ""
                                            color: Theme.faint
                                            font.family: Theme.mono
                                            font.pixelSize: root.fsMeta
                                            text: modelData.label ? (modelData.label + ":") : ""
                                        }
                                        Text {
                                            color: modelData.kind === "pace" && modelData.ahead ? Theme.sun : Theme.faint
                                            font.family: Theme.mono
                                            font.pixelSize: root.fsMeta
                                            elide: Text.ElideRight
                                            text: modelData.value
                                        }
                                    }
                                }
                                // Absence of a percentage is stated here too, so a
                                // secondary never silently shows nothing.
                                Text {
                                    visible: (modelData.percent === null || modelData.percent === undefined)
                                    color: Theme.faint
                                    font.family: Theme.mono
                                    font.pixelSize: root.fsMeta
                                    text: "—"
                                }
                            }
                        }
                        Text {
                            visible: text !== ""
                            width: parent.width
                            elide: Text.ElideRight
                            color: Theme.faint
                            font.family: Theme.mono
                            font.pixelSize: root.fsMeta
                            font.letterSpacing: 0.6 * root.s
                            // stale and error come out in TEXT: colour alone is not information
                            text: {
                                // No blind cut — this Text's `elide` decides.
                                if (modelData.status === "error")
                                    return root.redactText(modelData.error || root.tr("ERROR")).toUpperCase();
                                if (modelData.stale) return root.tr("STALE");
                                return "";
                            }
                        }
                    }
                }
            }
        }
        // ---- footer (T30) --------------------------------------------------
        // Only when there is something to say: an age, a problem count, or a
        // refresh in flight. Otherwise it hides rather than drawing a bare rule.
        Item {
            id: footer
            width: parent.width
            height: visible
                    ? (root.staleData
                        ? footerText.implicitHeight + staleReason.implicitHeight + 3 * root.s
                        : Math.max(footerText.implicitHeight, refreshButton.height))
                    : 0
            // NOT gated on `primaryProvider`: the footer is exactly what a user
            // needs when there is NO primary — the age of the attempt and the
            // refresh button. Gating it there hid the retry control precisely in
            // the error state (found by external review, 2026-10-28).
            visible: root.errorKind === "" || root.loading
                     ? (root.dataAgeSeconds >= 0 || root.troubledProviders > 0 || root.loading)
                     : true

            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1 * root.s
                color: Theme.lineStrong
                opacity: 0.5
            }

            Text {
                id: footerText
                anchors.left: parent.left
                anchors.right: refreshButton.left
                anchors.rightMargin: 8 * root.s
                anchors.bottom: parent.bottom
                elide: Text.ElideRight
                font.family: Theme.mono
                font.pixelSize: root.fsMeta
                // Prose, not short telemetry: no tracking here.
                // A FAILED refresh over kept data is the one case the footer must
                // say out loud: the numbers are real, but they are old.
                color: root.staleData ? Theme.gold : Theme.faint
                text: {
                    var partes = [];
                    if (root.staleData)
                        partes.push(root.tr("refresh failed, showing earlier reading"));
                    if (root.loading) partes.push(root.tr("updating..."));
                    else if (root.dataAgeSeconds >= 0) {
                        var idade = root.ageText(root.dataAgeSeconds);
                        partes.push(idade === "now" ? root.tr("updated just now")
                                                    : root.tr("updated %1 ago", idade));
                    }
                    if (root.troubledProviders === 1)
                        partes.push(root.tr("1 provider with a problem"));
                    else if (root.troubledProviders > 1)
                        partes.push(root.tr("%1 providers with a problem", root.troubledProviders));
                    return partes.join(" · ");
                }
            }

            // WHY it failed, next to the age. Elided, because an upstream message
            // ("network transport error: error sending request for url (https://...")
            // is long and the beginning is the useful part. Hidden entirely when
            // there is no stale data, so a healthy panel gains no line.
            Text {
                id: staleReason
                visible: root.staleData
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: footerText.top
                elide: Text.ElideRight
                color: Theme.gold
                font.family: Theme.mono
                font.pixelSize: root.fsMeta
                text: root.redactText(root.lastError)
            }

            // The manual refresh. Same MouseArea pattern the density button uses —
            // verified to receive real clicks inside a popout body.
            Rectangle {
                id: refreshButton
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                width: 18 * root.s
                height: 18 * root.s
                radius: height / 2
                color: refreshMouse.containsMouse ? Theme.threadBg : "transparent"
                border.width: 1
                border.color: Theme.lineStrong

                Text {
                    anchors.centerIn: parent
                    color: root.loading ? Theme.faint : Theme.bright
                    font.family: Theme.mono
                    font.pixelSize: root.fsBody
                    // A plain arrow glyph: the kit forbids emoji, and a text glyph
                    // needs no asset and scales with `s`.
                    text: root.loading ? "\u22EF" : "\u21BB"
                }
                MouseArea {
                    id: refreshMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    enabled: !root.loading
                    onClicked: root.requestRefresh()
                }
            }
        }

    }
}
