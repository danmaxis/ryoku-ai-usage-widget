// -*- mode: qml -*-
// Sonda de comportamento de T19 — a função PURA de corte por limite de palavra.
// (Joseki D5, contexto isolado: monta a view e CHAMA a função pública; não lê
// content/Widget.qml e não depende de detalhe interno.)
//
// Por que existe: o critério de done de T19 pede a função pura exercitada
// diretamente, e não apenas o texto que aparece na tela. Aqui a função é
// chamada com entradas escolhidas pelo teste e o RESULTADO BRUTO é despejado,
// de modo que "não parte palavra", "não devolve vazio" e "não entra em laço"
// sejam observáveis sem olhar o corpo da função.
//
// O service/Main.qml NÃO é montado de propósito: o coletor não tem nada a ver
// com uma função de string, e montá-lo faria a sonda depender de PATH, rede e
// estado do usuário para responder uma pergunta puramente textual.
//
// Entradas (env):
//   T19_PLUG_DIR    pasta do plugin sob teste
//   T19_FN_CASES    JSON array de { "name": string, "args": array }
//                   marcador {"$null": true} vira `null`
//                   marcador {"$undef": true} vira `undefined`
//                   marcador {"$num": n} vira o número n (float sem notação)
//   T19_STATE_DIR   stateDir sintético
//   T19_SETTLE_MS   espera antes de chamar (default 900)
//   T19_WIDTH       widthBudget do host (default 240)
//
// Saída (stdout, um registro por linha; o consumidor parseia por prefixo):
//   VIEW_PRESENT|<true|false>
//   FN_HOST|<tipo do objeto que hospeda a função>|<nome observado>
//   FN_NAME|<nome real>|<present|absent>
//   FN_CAND|<nome candidato>|<true|false>     (sondagem de nomes alternativos)
//   FN|<caso>|<typeof do resultado>|<JSON.stringify do resultado>
//   FN_THROW|<caso>|<mensagem>
//   VIEW_ERR|<mensagem>
//   END|<motivo>

import QtQuick
import Quickshell

ShellRoot {
    id: root

    property string plugDir: Quickshell.env("T19_PLUG_DIR") || ""
    property var cases: JSON.parse(Quickshell.env("T19_FN_CASES") || "[]")
    property int settleMs: parseInt(Quickshell.env("T19_SETTLE_MS") || "900")
    property int widthBudget: parseInt(Quickshell.env("T19_WIDTH") || "240")
    property bool done: false

    // Nomes que a implementação pode ter escolhido. O contrato assume
    // `truncarNaPalavra`; a sondagem serve para RELATAR o nome real, não para
    // aceitar qualquer coisa em silêncio: o teste exige um deles e diz qual veio.
    property var candidates: [
        "truncarNaPalavra", "truncarPalavra", "cortarNaPalavra",
        "cortarTextoNaPalavra", "encurtarNaPalavra", "elidirNaPalavra",
        "truncarPorPalavra", "truncateAtWord", "truncateWords"
    ]

    // pluginApi sintético: a view precisa instanciar sem o host real.
    QtObject {
        id: apiObj
        property var mainInstance: null
        property var pluginSettings: ({
            "accent": "wallpaper", "showMetricDetail": true, "showSecondaries": true
        })
        property string pluginDir: root.plugDir
        property string stateDir: Quickshell.env("T19_STATE_DIR") || "/tmp/t19-state"
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
    }

    function kindOf(it) {
        return String(it).replace(/\(0x[0-9a-f]+\)/, "").split("_QML")[0]
    }

    function poolOf(it) {
        try { return it.data || [] } catch (e) { return it.children || [] }
    }

    // Procura a função no nó raiz da view e, se não estiver lá, em qualquer
    // objeto da árvore (o contrato admite a função "num Item raiz", mas um
    // helper interno num QtObject também é acessível e merece ser relatado).
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

    function resolve() {
        var v = viewL.item
        if (v === null || v === undefined) return null
        for (var i = 0; i < root.candidates.length; i++) {
            var r = root.search(v, root.candidates[i], 0)
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

    function run() {
        var v = null
        try { v = viewL.item } catch (e) { v = null }
        console.log("VIEW_PRESENT|" + (v !== null && v !== undefined))
        if (v === null || v === undefined) {
            console.log("FN_NAME|<semview>|absent")
            console.log("VIEW_ERR|a view não montou")
            finish("sem view")
            return
        }
        for (var c = 0; c < root.candidates.length; c++) {
            var found = root.search(v, root.candidates[c], 0)
            console.log("FN_CAND|" + root.candidates[c] + "|" + (found !== null))
        }
        var hit = root.resolve()
        if (hit === null) {
            console.log("FN_NAME|<absent>|absent")
            finish("função ausente")
            return
        }
        console.log("FN_HOST|" + root.kindOf(hit.owner) + "|" + hit.name)
        console.log("FN_NAME|" + hit.name + "|present")

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
            var json = ""
            try { json = JSON.stringify(res) } catch (e) { json = "<stringify falhou>" }
            console.log("FN|" + cs.name + "|" + typeof res + "|" + json)
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
            console.log("FN_NAME|<timeout>|absent")
            root.finish("watchdog")
        }
    }

    Component.onCompleted: {
        // Instância principal sintética: sem modelo, sem erro, sem coletor.
        apiObj.mainInstance = {
            model: null, loading: false, lastError: "", errorKind: ""
        }
        viewL.setSource(root.plugDir + "/content/Widget.qml")
        viewL.active = true
    }
}
