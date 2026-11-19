// -*- mode: qml -*-
// Sonda de comportamento da EMENDA T38 — gaveta lateral com deslocamento (Joseki D5).
//
// Gerado em contexto isolado (D5) — sem acesso a content/Widget.qml nem a
// service/Main.qml. Base: SPEC rodada 4, emenda T38 assinada em 2026-10-30
// ("left: o detalhe entra pela esquerda e as pílulas deslizam para a direita;
// right, espelho; seta alta na ponta devolve à grade; pílulas visíveis, inteiras
// ou parciais, são clicáveis; pílulas cortadas recebem fade na borda; título
// fixo; altura lateral reservada desde a abertura; rodapé com divisória acima
// dos botões alinhados").
//
// O que esta sonda faz: monta APENAS content/Widget.qml num processo quickshell
// OFFLINE (QT_QPA_PLATFORM=offscreen) com pluginApi SINTÉTICO. Não roda o
// ai-usagebar, não usa rede, não lê credencial, não escreve em config.
//
// Cada caso é {name, settings, model, widthBudget, epoch, steps}.
//
// Steps:
//   {"op":"snap","name":"x"}                  censo da árvore
//   {"op":"wait","ms":N,"name":"x"}           espera N ms (deixa assentar) e censa
//   {"op":"clickText","value":"Pill Tau"}     clique no controle mais próximo do texto
//   {"op":"openDrawer","text":"TAU ALPHA",
//    "click":"Pill Tau","name":"x"}           abre se o marcador não está na árvore,
//                                             espera assentar e censa
//   {"op":"clickArrow","symbol":"→","name":"x"}  clique na faixa da seta, censa
//   {"op":"clickClipped","name":"x"}          acha a célula CORTADA pela borda (parte
//                                             dentro, parte fora) e clica o MEIO DA
//                                             FATIA VISÍVEL; emite
//                                             CLIPPED|<nome>|<visível>|<total>|col=..
//   {"op":"clickPillIx","ix":N,"name":"x"}    clique na N-ésima CÉLULA da grade, no
//                                             MEIO DA FATIA VISÍVEL dela; emite
//                                             PILLIX|ix|<nome>|<visível>|<total>|x=..
//   {"op":"clickDownCloser","name":"x"}       em `down`: clica o controle que vive
//                                             ABAIXO da grade e fora das pílulas
//   {"op":"copyKeybind","name":"x"}           clica o controle com rótulo /copy/i e
//                                             LÊ o clipboard → COPY|<texto>
//   {"op":"refresh","name":"x"}               clica o controle com rótulo ↻
//   {"op":"probeSave"}                        controle: dispara saveSetting 1×
//   {"op":"poll","name":"x","model":{...}}    simula poll: model NOVO, mesmos ids
//
// Saída (stdout; o consumidor parseia por prefixo):
//   VIEW_ERR|<msg> · CLICK|<alvo>|<controle>|<w>x<h>|<como> · CLICK_MISS|<alvo>
//   PILLIX|<ix>|<nome>|<visível>|<total>|x=<x>|caixa=<a>..<b>
//   COPY|<texto json> · SAVE_PROBE_OK|1 · REFRESH|<n> · MODEL|<nome>|<json>
//   ===CASE|<nome>=== / ===CASE_END|<nome>===
//   ===SNAP|<nome>===
//     PROP|<nome>|<tipo>|<valor>|<no último: SAVES|…|IW|iw|ih|w|h|RF|n>
//     NODE|<id>|<pai>|<tipo>|<texto json>|x|y|w|h|r|a|clicável|<stops do gradiente>|<clip>
//   ===SNAP_END|<nome>===
//
// LIMITAÇÕES DE MEDIÇÃO (medidas nesta base, declaradas de propósito)
// ----------------------------------------------------------------
// 1. Posição de PÍLULA só resolve quando a grade tem mais de uma coluna efetiva.
//    Com 2 pílulas em 2 colunas as duas saem em x = origem da grade. Por isso a
//    coluna de uma célula é inferida dos x OBSERVADOS (ver `cellX`), nunca de
//    fórmula com constante mágica.
// 2. A posição da GRADE e a do PAINEL resolvem e são determinísticas entre
//    execuções — é por elas que o DESLOCAMENTO é medido, e é exatamente a medida
//    que o teste anterior não fazia (ele aceitava sobreposição sem deslocamento).
// 3. `height` derivado de conteúdo não resolve offline; a reserva de altura é
//    medida no CONTÊINER da seção, que resolve.
// Nada aqui depende de objectName nem de nome de componente interno: os alvos
// são achados por estrutura (ancestral/irmandade), texto e comportamento
// (existência de sinal `clicked`).

import QtQuick
import Quickshell

ShellRoot {
    id: root

    readonly property string plugDir: Quickshell.env("T45_PLUG_DIR") || ""
    function casePayload() {
        try {
            var n = parseInt(Quickshell.env("T45_CASES_PARTS") || "0")
            if (n <= 0) return Quickshell.env("T45_CASES") || "[]"
            var acc = ""
            for (var i = 0; i < n; i++) acc += (Quickshell.env("T45_CASES_" + i) || "")
            return acc
        } catch (e) { return "[]" }
    }
    property var cases: { try { return JSON.parse(root.casePayload()) } catch (e) { return [] } }
    property int idx: 0
    property bool done: false
    property var saves: []
    property var settings: ({})
    property var steps: []
    property int si: 0
    property string caseName: ""
    property int nodeId: 0
    property string pendingSnap: ""
    property var activeCase: null
    property bool wantClip: false

    // Serviço falso: a forma que a view lê de pluginApi.mainInstance. O contador
    // `refreshes` existe para provar que o botão de atualizar CHAMA refresh()
    // (sem ele, "o botão existe" não distinguiria um botão morto).
    QtObject {
        id: service
        property var model: null
        property bool loading: false
        property string lastError: ""
        property string errorKind: ""
        property real lastSuccessEpoch: 0
        property int refreshes: 0
        function refresh() { service.refreshes++; console.log("REFRESH|" + service.refreshes) }
    }

    QtObject {
        id: apiObj
        property var mainInstance: service
        property var pluginSettings: root.settings
        property string pluginDir: root.plugDir
        property string stateDir: Quickshell.env("T45_STATE_DIR") || "/tmp/t45-state"
        property bool panelOpen: false
        property bool panelAvailable: false
        function saveSetting(k, v) { root.saves.push(String(k)) }
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
                item.widthBudget = (root.activeCase && root.activeCase.widthBudget)
                    ? root.activeCase.widthBudget
                    : parseInt(Quickshell.env("T45_WIDTH") || "460")
                item.density = "full"
            } catch (e) { console.log("VIEW_ERR|props: " + e) }
            mount.restart()
        }
        onStatusChanged: {
            if (status === Loader.Error || status === 3)
                console.log("VIEW_ERR|o Loader não carregou a view (status " + status + ")")
        }
    }

    // ---------------------------------------------------------------- utils
    function kindOf(it) {
        try { return String(it).replace(/\(0x[0-9a-f]+\)/, "").split("_QML")[0] }
        catch (e) { return "<?" + e + ">" }
    }
    function poolOf(it) { try { return it.data || [] } catch (e) { return [] } }
    function visibleOf(it) {
        try { return (it.visible !== false && it.opacity !== 0) } catch (e) { return true }
    }
    function nodeW(n) { try { return Math.max(n.width || 0, n.implicitWidth || 0) } catch (e) { return 0 } }
    function nodeH(n) { try { return Math.max(n.height || 0, n.implicitHeight || 0) } catch (e) { return 0 } }
    function absPos(it) {
        try {
            var v = viewL.item
            if (v && it.mapToItem) { var p = it.mapToItem(v, 0, 0); return { x: p.x, y: p.y } }
        } catch (e) {}
        return { x: 0, y: 0 }
    }
    function alphaOf(it) {
        try { return (it.color && it.color.a !== undefined) ? it.color.a : 1 } catch (e) { return 1 }
    }
    function hasClicked(it) { try { return (typeof it.clicked === "function") } catch (e) { return false } }
    function isInteractive(it) {
        var k = root.kindOf(it)
        if (/MouseArea|TapHandler|HoverHandler|DragHandler|WheelHandler|AbstractButton|QQuickButton|QQuickControl|QQuickSwitch|QQuickCheckBox/.test(k))
            return true
        return root.hasClicked(it)
    }
    function collectAll(it, depth, out) {
        if (!it || depth > 30) return out
        if (root.visibleOf(it)) out.push(it)
        var pool = root.poolOf(it)
        for (var i = 0; i < pool.length; i++) root.collectAll(pool[i], depth + 1, out)
        return out
    }
    function subtreeTexts(it, depth, acc) {
        if (!it || depth > 22) return acc
        try { if (typeof it.text === "string" && it.text.length > 0) acc.push(String(it.text)) } catch (e) {}
        var pool = root.poolOf(it)
        for (var i = 0; i < pool.length; i++) root.subtreeTexts(pool[i], depth + 1, acc)
        return acc
    }
    function deepestClicked(it, depth) {
        if (!it || depth > 30) return null
        if (root.hasClicked(it)) return it
        var pool = root.poolOf(it)
        for (var i = 0; i < pool.length; i++) {
            var r = root.deepestClicked(pool[i], depth + 1)
            if (r) return r
        }
        return null
    }
    function enclosingControl(it) {
        var up = it
        for (var d = 0; d < 10 && up; d++) {
            if (root.hasClicked(up)) return up
            var all = root.collectAll(up, 0, [])
            var n = 0
            for (var i = 0; i < all.length; i++) if (root.hasClicked(all[i])) n++
            if (n > 0) return up
            try { up = up.parent } catch (e) { return null }
        }
        return null
    }
    function clickTarget(c) {
        var target = root.hasClicked(c) ? c : root.deepestClicked(c, 0)
        if (target === null) { console.log("CLICK_MISS|nenhum nó com sinal clicked"); return false }
        var tw = Math.max(1, root.nodeW(target)), th = Math.max(1, root.nodeH(target))
        try {
            target.clicked(Qt.point(tw / 2, th / 2))
            console.log("CLICK|" + root.kindOf(c) + "|" + root.kindOf(target) + "|"
                + Math.round(tw) + "x" + Math.round(th) + "|clicked")
            return true
        } catch (e) {
            console.log("CLICK|" + root.kindOf(c) + "|" + root.kindOf(target) + "|"
                + Math.round(tw) + "x" + Math.round(th) + "|throw:" + e)
            return false
        }
    }
    // Clica o controle MAIS PRÓXIMO do texto, preferindo o MENOR (a pílula, não o
    // contêiner que a envolve). Recusa alvo cuja subárvore tenha mais de um nome
    // de pílula: foi assim que uma sonda anterior clicava o provider errado.
    function clickByText(value) {
        var needle = String(value).toUpperCase()
        var v = viewL.item
        if (!v) { console.log("CLICK_MISS|sem view"); return false }
        var all = root.collectAll(v, 0, [])
        var best = null, bestArea = -1
        for (var i = 0; i < all.length; i++) {
            var own = ""
            try { if (typeof all[i].text === "string") own = all[i].text.toUpperCase() } catch (e) {}
            if (own.indexOf(needle) < 0) continue
            var c = root.enclosingControl(all[i])
            if (c === null) continue
            var area = root.nodeW(c) * root.nodeH(c)
            if (best === null || (area > 0 && (bestArea <= 0 || area < bestArea))) { best = c; bestArea = area }
        }
        if (best === null) { console.log("CLICK_MISS|" + value); return false }
        var ts = root.subtreeTexts(best, 0, [])
        var nomes = {}
        for (var j = 0; j < ts.length; j++) {
            var tt = ts[j].trim()
            if (/^Pill /.test(tt)) nomes[tt] = true
        }
        var distintos = 0
        for (var k in nomes) distintos++
        if (distintos > 1) {
            console.log("CLICK_MISS|ambíguo: " + value + " (nomes=" + distintos + ")")
            return false
        }
        return root.clickTarget(best)
    }
    function hasTextNow(needle) {
        var v = viewL.item
        if (!v) return false
        var n = String(needle).toUpperCase()
        var all = root.collectAll(v, 0, [])
        for (var i = 0; i < all.length; i++) {
            try {
                if (typeof all[i].text === "string" && all[i].text.toUpperCase().indexOf(n) >= 0) return true
            } catch (e) {}
        }
        return false
    }
    function exactNodeText(value) {
        var v = viewL.item
        if (!v) return null
        var all = root.collectAll(v, 0, [])
        for (var i = 0; i < all.length; i++) {
            try { if (typeof all[i].text === "string" && all[i].text === value) return all[i] } catch (e) {}
        }
        return null
    }
    function findGrid() {
        var v = viewL.item
        if (!v) return null
        var all = root.collectAll(v, 0, [])
        for (var i = 0; i < all.length; i++) if (root.kindOf(all[i]) === "QQuickGrid") return all[i]
        return null
    }
    // Células VISUAIS da grade, na ordem de inserção (= ordem de leitura). Recursos
    // não visuais não são células.
    function gridCells() {
        var g = root.findGrid()
        if (g === null) return []
        var out = [], kids = root.poolOf(g)
        for (var i = 0; i < kids.length; i++) {
            var k = root.kindOf(kids[i])
            if (/Repeater|Timer|Handler|Behavior|Animation|Transition|Instantiator|Delegate/.test(k)) continue
            out.push(kids[i])
        }
        return out
    }
    function pillNameOf(c) {
        var ts = root.subtreeTexts(c, 0, [])
        for (var i = 0; i < ts.length; i++) if (/^Pill /.test(ts[i].trim())) return ts[i].trim()
        return ""
    }
    // Caixa de conteúdo VISÍVEL (o que o popout deixa ver), em coordenadas da view.
    function contentBox() {
        var v = viewL.item
        if (!v) return null
        var pad = 12
        try { if (typeof v.pad === "number") pad = v.pad } catch (e) {}
        var cw = 0
        try { cw = (typeof v.contentWidth === "number") ? v.contentWidth : v.implicitWidth } catch (e) {}
        return { x: pad, w: cw }
    }
    // Posição x da célula `ix`. Ver limitação 1 no cabeçalho: com uma coluna
    // efetiva todas as células reportam x = origem da grade, então a coluna vem
    // dos x OBSERVADOS (ordenados) e de `ix % columns`.
    function cellX(ix) {
        var v = viewL.item
        var cells = root.gridCells()
        if (!v || ix < 0 || ix >= cells.length) return null
        var cols = 1
        try { cols = (typeof v.columns === "number") ? v.columns : 1 } catch (e) {}
        if (cols < 1) cols = 1
        var xs = []
        for (var i = 0; i < cells.length; i++) {
            var x = root.absPos(cells[i]).x
            var visto = false
            for (var j = 0; j < xs.length; j++) if (Math.abs(xs[j] - x) < 0.5) { visto = true; break }
            if (!visto) xs.push(x)
        }
        xs.sort(function (a, b) { return a - b })
        var pos = root.absPos(cells[ix])
        if (xs.length >= cols) pos = { x: xs[ix % cols], y: pos.y }
        return { x: pos.x, w: root.nodeW(cells[ix]) }
    }
    // Clica a célula `ix` no MEIO DA FATIA VISÍVEL dela. É a asserção do contrato
    // ("pílulas visíveis, inteiras ou parciais, são clicáveis"): o centro de uma
    // pílula cortada está fora do popout e o clique não chegaria nela.
    function clickPillIx(ix) {
        var box = root.contentBox()
        var cells = root.gridCells()
        if (!box) { console.log("CLICK_MISS|sem view"); return false }
        if (ix < 0 || ix >= cells.length) {
            console.log("CLICK_MISS|célula " + ix + " de " + cells.length)
            return false
        }
        var pos = root.cellX(ix)
        var cell = cells[ix]
        var ctl = root.deepestClicked(cell, 0)
        if (pos === null || ctl === null) { console.log("CLICK_MISS|célula sem geometria"); return false }
        var x0 = Math.max(pos.x, box.x), x1 = Math.min(pos.x + pos.w, box.x + box.w)
        if (x1 - x0 <= 0.5) {
            console.log("CLICK_MISS|célula " + ix + " inteiramente fora da área visível (x=" + pos.x + ")")
            return false
        }
        var ccp = root.absPos(ctl), cp = root.absPos(cell)
        var dx = ccp.x - cp.x
        console.log("PILLIX|" + ix + "|" + root.pillNameOf(cell) + "|" + (x1 - x0) + "|" + pos.w
            + "|x=" + pos.x + "|caixa=" + box.x + ".." + (box.x + box.w))
        try {
            ctl.clicked(Qt.point((x0 + x1) / 2 - pos.x - dx, root.nodeH(ctl) / 2))
            console.log("CLICK|" + root.kindOf(ctl) + "|" + root.kindOf(ctl) + "|"
                + Math.round(pos.w) + "x" + Math.round(root.nodeH(ctl)) + "|clicked-na-celula-" + ix)
            return true
        } catch (e) {
            console.log("CLICK|" + ix + "|throw:" + e)
            return false
        }
    }
    // A célula da coluna `col`: a k-ésima célula cuja coluna (k % columns) é `col`.
    function cellAt(col) {
        var cells = root.gridCells()
        var cols = 1
        try { cols = (typeof viewL.item.columns === "number") ? viewL.item.columns : 1 } catch (e) {}
        if (cols < 1) cols = 1
        for (var k = 0; k < cells.length; k++) if (k % cols === col) return cells[k]
        return null
    }

    // O id do provider que a célula representa, lido do TEXTO do nome: o
    // `openDrawerId` da view e o nome da pílula são as duas pontas do mesmo dado.
    // Comparar por nome normalizado evita depender de qualquer campo interno.
    function pillIdOf(cell) {
        var nome = root.pillNameOf(cell)
        if (nome === "") return ""
        var id = nome.replace(/^Pill\s+/i, "").trim().toLowerCase()
        return id
    }

    // Célula CORTADA: parte dentro da área visível, parte fora. A largura da célula
    // vem do nó; a coluna, dos x observados (ver limitação 1 no cabeçalho).
    function clippedCell() {
        var box = root.contentBox()
        var cells = root.gridCells()
        var g = root.findGrid()
        if (!box || !g || cells.length === 0) return null
        var cols = 1
        try { cols = (typeof viewL.item.columns === "number") ? viewL.item.columns : 1 } catch (e) {}
        if (cols < 1) cols = 1
        var xs = []
        for (var i = 0; i < cells.length; i++) {
            var x = root.absPos(cells[i]).x
            var seen = false
            for (var j = 0; j < xs.length; j++) if (Math.abs(xs[j] - x) < 0.5) { seen = true; break }
            if (!seen) xs.push(x)
        }
        xs.sort(function (a, b) { return a - b })
        var w0 = root.nodeW(cells[0])
        var gapx = 0
        try { gapx = (typeof viewL.item.gap === "number") ? viewL.item.gap : 0 } catch (e2) {}
        var gp = root.absPos(g)
        // Nunca mira a pílula do provider JÁ ABERTO: clicar nela é toggle (fecha a
        // gaveta), e o teste perderia o que quer medir — que a pílula cortada
        // TROCA o provider. A exclusão é por nome, não por posição.
        var abertoId = ""
        try { abertoId = String(viewL.item.openDrawerId || "") } catch (e3) {}
        var melhor = null, melhorVis = 0
        for (var c = 0; c < cols; c++) {
            var cx = (xs.length >= cols) ? xs[c] : gp.x + c * (w0 + gapx)
            var vis = Math.min(cx + w0, box.x + box.w) - Math.max(cx, box.x)
            if (!(vis > 0.5 && vis < w0 - 0.5)) continue
            var cand = root.cellAt(c)
            if (cand && abertoId !== "" && root.pillIdOf(cand) === abertoId) continue
            if (vis > melhorVis) { melhor = { col: c, x: cx, vis: vis, w: w0, cell: cand }; melhorVis = vis }
        }
        if (melhor === null) return null
        melhor.ix = melhor.col
        if (!melhor.cell) melhor.cell = cells[melhor.col % cells.length]
        melhor.ctl = root.deepestClicked(melhor.cell, 0)
        return melhor
    }

    function clickClipped() {
        var box = root.contentBox()
        var alvo = root.clippedCell()
        if (alvo === null || alvo.ctl === null) {
            console.log("CLICK_MISS|nenhuma pílula CORTADA na área visível")
            return false
        }
        var x0 = Math.max(alvo.x, box.x), x1 = Math.min(alvo.x + alvo.w, box.x + box.w)
        console.log("CLIPPED|" + root.pillNameOf(alvo.cell) + "|" + (x1 - x0) + "|" + alvo.w
            + "|col=" + alvo.col + "|x=" + alvo.x + "|caixa=" + box.x + ".." + (box.x + box.w))
        var cp = root.absPos(alvo.cell), ccp = root.absPos(alvo.ctl)
        try {
            alvo.ctl.clicked(Qt.point((x0 + x1) / 2 - alvo.x - (ccp.x - cp.x), root.nodeH(alvo.ctl) / 2))
            console.log("CLICK|" + root.kindOf(alvo.ctl) + "|" + root.kindOf(alvo.ctl) + "|"
                + Math.round(alvo.w) + "x" + Math.round(root.nodeH(alvo.ctl)) + "|clicked-na-fatia-cortada")
            return true
        } catch (e) {
            console.log("CLICK|fatia cortada|throw:" + e)
            return false
        }
    }

    function clickLabelled(re, label) {
        var v = viewL.item
        if (!v) { console.log("CLICK_MISS|sem view"); return false }
        var all = root.collectAll(v, 0, [])
        for (var i = 0; i < all.length; i++) {
            var tx = ""
            try { if (typeof all[i].text === "string") tx = all[i].text } catch (e) {}
            if (!re.test(tx)) continue
            var c = root.enclosingControl(all[i])
            if (c !== null) return root.clickTarget(c)
        }
        console.log("CLICK_MISS|" + label)
        return false
    }

    // -------------------------------------------------------------- census
    function emitModel(name) {
        var fp = "<throw>"
        try { fp = JSON.stringify(service.model) } catch (e) { fp = "<throw:" + e + ">" }
        console.log("MODEL|" + name + "|" + fp)
    }
    function emitTree(it, depth, parentId) {
        if (!it || depth > 30) return
        root.nodeId++
        var myId = root.nodeId
        if (root.visibleOf(it)) {
            var p = root.absPos(it)
            var txt = ""
            try { if (typeof it.text === "string" && it.text.length > 0) txt = it.text } catch (e) {}
            var r = 0
            try { r = (it.radius === undefined ? 0 : it.radius) } catch (e) {}
            // `fade`: o nó carrega gradiente — as duas formas possíveis (a
            // propriedade `gradient` do retângulo e um item LinearGradient com
            // `stops`). A sonda não diz COMO o fade foi feito, só se existe.
            var fade = 0
            try {
                if (it.gradient !== undefined && it.gradient !== null) {
                    try { fade = (it.gradient.stops || []).length } catch (e2) { fade = 1 }
                }
            } catch (e3) {}
            try {
                if (fade === 0 && it.stops !== undefined && it.stops !== null)
                    fade = (it.stops.length === undefined) ? 1 : it.stops.length
            } catch (e4) {}
            var clip = 0
            try { clip = (it.clip === true) ? 1 : 0 } catch (e5) {}
            console.log("NODE|" + myId + "|" + parentId + "|" + root.kindOf(it) + "|"
                + JSON.stringify(String(txt)) + "|" + p.x + "|" + p.y + "|"
                + root.nodeW(it) + "|" + root.nodeH(it) + "|" + r + "|"
                + root.alphaOf(it) + "|" + root.isInteractive(it) + "|" + fade + "|" + clip)
        }
        var pool = root.poolOf(it)
        for (var m = 0; m < pool.length; m++) root.emitTree(pool[m], depth + 1, myId)
    }
    function propValue(v) {
        if (v === undefined) return "{\"$undefined\":true}"
        if (v === null) return "null"
        var t = typeof v
        if (t === "number") { if (isNaN(v)) return "{\"$nan\":true}"; return String(v) }
        if (t === "string" || t === "boolean") return JSON.stringify(v)
        return "{\"$type\":\"" + t + "\"}"
    }
    function emitSnap(name) {
        console.log("===SNAP|" + name + "===")
        var v = viewL.item
        if (v === null || v === undefined) {
            console.log("PROP|<noview>|object|null|SAVES|[]|IW|0|0|0|0|RF|0")
            console.log("===SNAP_END|" + name + "===")
            return
        }
        var props = ["columns", "drawerDirection", "openDrawerId", "pad", "gap",
                     "available", "contentWidth", "baseWidth", "widthBudget",
                     "drawerPanelWidth", "drawerMaxHeight", "drawerHeaderHeight",
                     "drawerMetricBudget", "density"]
        var tail = "SAVES|" + JSON.stringify(root.saves) + "|IW|" + v.implicitWidth
            + "|" + v.implicitHeight + "|" + v.width + "|" + v.height
            + "|RF|" + service.refreshes
        for (var i = 0; i < props.length; i++) {
            var tv = "undefined", vv = "{\"$undefined\":true}"
            try { var got = v[props[i]]; tv = typeof got; vv = root.propValue(got) } catch (e) { tv = "<throw>" }
            var extra = (i === props.length - 1) ? "|" + tail : ""
            console.log("PROP|" + props[i] + "|" + tv + "|" + vv + extra)
        }
        root.nodeId = 0
        try { root.emitTree(v, 0, 0) } catch (e2) { console.log("VIEW_ERR|censo: " + e2) }
        console.log("===SNAP_END|" + name + "===")
    }

    // ------------------------------------------------------- step engine
    function later(ms, snapName, clip) {
        root.pendingSnap = snapName || ""
        root.wantClip = (clip === true)
        waitT.interval = ms || 700
        waitT.restart()
    }
    function tick() {
        if (root.si >= root.steps.length) { root.endCase(); return }
        var st = root.steps[root.si]
        root.si++
        try {
            if (st.op === "snap") {
                root.emitSnap(st.name)
            } else if (st.op === "wait") {
                later(st.ms || 600, st.name)
                return
            } else if (st.op === "clickText") {
                root.clickByText(st.value)
            } else if (st.op === "openDrawer") {
                if (!root.hasTextNow(st.text)) root.clickByText(st.click)
                later(st.ms || 900, st.name || "open")
                return
            } else if (st.op === "clickArrow") {
                var alvo = root.exactNodeText(st.symbol)
                if (alvo === null) console.log("CLICK_MISS|seta " + st.symbol)
                else {
                    var c = root.enclosingControl(alvo)
                    if (c === null) console.log("CLICK_MISS|seta sem controle")
                    else root.clickTarget(c)
                }
                later(st.ms || 900, st.name || "arrow")
                return
            } else if (st.op === "clickClipped") {
                root.clickClipped()
                later(st.ms || 900, st.name || "clipped")
                return
            } else if (st.op === "clickPillIx") {
                root.clickPillIx(st.ix)
                later(st.ms || 900, st.name || "pill")
                return
            } else if (st.op === "clickDownCloser") {
                // O recolher de `down` vive ABAIXO da grade e fora das pílulas.
                // Achar por posição + estrutura evita depender do rótulo traduzido.
                var g = root.findGrid()
                var vv = viewL.item
                var alvo2 = null
                if (vv && g) {
                    var gy = root.absPos(g).y
                    var all2 = root.collectAll(vv, 0, [])
                    for (var ai = 0; ai < all2.length; ai++) {
                        var cand = all2[ai]
                        if (!root.isInteractive(cand)) continue
                        if (root.absPos(cand).y <= gy + 2) continue
                        if (root.pillNameOf(cand) !== "") continue
                        alvo2 = cand
                        break
                    }
                }
                if (alvo2 === null) console.log("CLICK_MISS|nenhum controle abaixo da grade")
                else root.clickTarget(alvo2)
                later(st.ms || 900, st.name || "closer")
                return
            } else if (st.op === "copyKeybind") {
                root.clickLabelled(/copy/i, "botão de copiar")
                later(st.ms || 600, st.name || "copy", true)
                return
            } else if (st.op === "refresh") {
                root.clickLabelled(/\u21bb/, "botão de atualizar")
                later(st.ms || 600, st.name || "refresh")
                return
            } else if (st.op === "probeSave") {
                // Controle de vacuidade: prova que o gancho saveSetting FUNCIONA.
                // Sem isto, "a view nunca grava" passaria com o gancho quebrado.
                apiObj.saveSetting("T45_PROBE_CONTROL", true)
                console.log("SAVE_PROBE_OK|1")
            } else if (st.op === "poll") {
                service.model = st.model
                later(st.ms || 900, st.name || "poll")
                return
            } else if (st.op === "model") {
                root.emitModel(st.name)
            } else {
                console.log("VIEW_ERR|step desconhecido: " + st.op)
            }
        } catch (e2) {
            console.log("VIEW_ERR|step " + st.op + ": " + e2)
        }
        next.restart()
    }

    function startCase() {
        if (root.idx >= root.cases.length) { root.finish(); return }
        var c = root.cases[root.idx]
        root.activeCase = c
        root.caseName = String(c.name)
        root.saves = []
        root.settings = c.settings || {}
        root.steps = c.steps || []
        root.si = 0
        service.model = c.model
        // `epoch` existe por caso: sem instante de sucesso o rodapé de frescor não
        // tem o que datar e some da árvore — a asserção de rodapé passaria por
        // ausência em vez de por alinhamento.
        service.lastSuccessEpoch = (c.epoch === undefined) ? 0 : c.epoch
        console.log("===CASE|" + root.caseName + "===")
        root.emitModel("mount")
        viewL.active = false
        viewL.setSource("")
        viewL.setSource(root.plugDir + "/content/Widget.qml")
        viewL.active = true
        watchdog.restart()
    }

    function endCase() {
        watchdog.stop()
        console.log("===CASE_END|" + root.caseName + "===")
        viewL.active = false
        viewL.setSource("")
        root.idx++
        nextCase.restart()
    }

    function finish() {
        if (root.done) return
        root.done = true
        console.log("END")
        Qt.quit()
    }

    Timer { id: mount; interval: 700; repeat: false; onTriggered: root.tick() }
    Timer { id: next; interval: 240; repeat: false; onTriggered: root.tick() }
    Timer {
        id: waitT; repeat: false
        onTriggered: {
            if (root.pendingSnap !== "") root.emitSnap(root.pendingSnap)
            root.pendingSnap = ""
            if (root.wantClip) {
                // Lido DEPOIS do clique: o clipboard do processo é global e a
                // leitura tem de vir depois do efeito.
                try { console.log("COPY|" + JSON.stringify(Quickshell.clipboardText)) }
                catch (e) { console.log("COPY|<throw>") }
                root.wantClip = false
            }
            next.restart()
        }
    }
    Timer { id: nextCase; interval: 200; repeat: false; onTriggered: root.startCase() }
    Timer { id: boot; interval: 300; running: true; repeat: false; onTriggered: root.startCase() }
    Timer {
        id: watchdog; interval: 25000; repeat: false
        onTriggered: {
            console.log("VIEW_ERR|watchdog no caso " + root.caseName)
            root.endCase()
        }
    }
}
