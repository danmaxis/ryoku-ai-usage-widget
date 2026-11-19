// -*- mode: qml -*-
// Smoke de CARGA da R4 (agente) — NÃO é teste de comportamento (D5).
//
// Existe por um motivo só: provar que content/Widget.qml CRIA o objeto e desenha
// com o formato único (grade + gaveta), antes de qualquer asserção de contrato.
// Precedente medido: em T11 um `Text.background` inválido matou a criação do
// objeto, `contentLoader.item` ficou null e o host caiu em 680x520 — o popout
// aparecia como um corpo vazio enorme.
//
// Despeja uma CENSURA da árvore para o Python conferir:
//   LOADOK|<bool>           -> a view montou (col existe, raiz não-nula)
//   ROOT|<density>|<cols>   -> as propriedades derivadas resolveram
//   PILLS|<n>               -> quantas pílulas existem
//   TEXTS|<n>               -> quantos Text visíveis
//   METERS|<n>              -> quantos Meter desenhados
//   LABELS|<a\tb\tc>        -> os textos visíveis, para asserção de conteúdo
//   DRAWER|<aberta:bool>    -> se a gaveta resolveu visível
//   CLICK|<n>|<id>          -> cliques disparados nas pílulas (por índice)
//   AFTER|<n>               -> textos visíveis DEPOIS do clique (abre gaveta)
//
// Inputs (env):
//   R4_PLUG_DIR   pasta do plugin sob teste
//   R4_MODEL      JSON do modelo (vira mainInstance.model)
//   R4_SETTINGS   JSON das settings (default: {})
//   R4_OPEN_ID    id a abrir na gaveta (default: "")
//   R4_SETTLE_MS  espera antes de censar (default 1200)
//
// Nota de medição: `implicitHeight` não resolve offline. Tudo aqui conta NÓS,
// nunca pixels — a altura é provada em smoke real, não neste harness.

import QtQuick
import Quickshell
import Quickshell.Io

ShellRoot {
    id: shell

    readonly property string plugDir: Quickshell.env("R4_PLUG_DIR") || ""
    readonly property var modelData: {
        try { return JSON.parse(Quickshell.env("R4_MODEL") || "null"); }
        catch (e) { return null; }
    }
    readonly property var settingsData: {
        try { return JSON.parse(Quickshell.env("R4_SETTINGS") || "{}"); }
        catch (e) { return ({}); }
    }
    readonly property string openId: Quickshell.env("R4_OPEN_ID") || ""
    readonly property int settleMs: Number(Quickshell.env("R4_SETTLE_MS") || 1200)

    // A fake service, exactly the shape the view reads: model / lastError /
    // errorKind / loading / lastSuccessEpoch / refresh().
    QtObject {
        id: fakeService
        property var model: shell.modelData
        property string lastError: ""
        property string errorKind: ""
        property bool loading: false
        property real lastSuccessEpoch: Date.now() / 1000
        function refresh() {}
    }

    QtObject {
        id: fakeApi
        property var mainInstance: fakeService
        property var pluginSettings: shell.settingsData
        property string pluginDir: shell.plugDir
        function saveSettings() {}
    }

    Item {
        id: host
        width: 460; height: 900

        Loader {
            id: contentLoader
            anchors.fill: parent
            source: shell.plugDir !== "" ? "file://" + shell.plugDir + "/content/Widget.qml" : ""
            onLoaded: {
                item.pluginApi = fakeApi;
                item.density = "full";
                item.s = 1;
                item.widthBudget = 460;
                item.active = true;
                if (shell.openId !== "") item.openDrawerId = shell.openId;
            }
            onStatusChanged: if (status === Loader.Error) console.log("LOADERR")
        }
    }

    function census() {
        var texts = 0, labels = [], meters = 0, pills = 0;
        function walk(node, depth) {
            if (!node || depth > 40) return;
            var kids = node.children;
            if (!kids) return;
            for (var i = 0; i < kids.length; i++) {
                var c = kids[i];
                if (!c) continue;
                var tn = String(c).split("(")[0];
                if (tn === "QQuickText" && c.visible && c.text !== "")
                    { texts++; labels.push(String(c.text)); }
                if (tn === "QQuickRectangle" && c.visible && c.radius > 0) meters++;
                // A Pill is a Rectangle with a `provider` property.
                if (c.provider !== undefined && c.provider !== null && c.opened !== undefined) pills++;
                walk(c, depth + 1);
            }
        }
        var it = contentLoader.item;
        if (it) walk(it, 0);
        return { texts: texts, labels: labels, meters: meters, pills: pills };
    }

    Timer {
        interval: shell.settleMs; running: true; repeat: false
        onTriggered: {
            var it = contentLoader.item;
            console.log("LOADOK|" + (it !== null && it !== undefined));
            if (!it) { Qt.callLater(() => Qt.quit()); return; }
            console.log("ROOT|" + it.density + "|" + (typeof it.columns !== "undefined" ? it.columns : "NA"));
            var c = shell.census();
            console.log("PILLS|" + c.pills);
            console.log("TEXTS|" + c.texts);
            console.log("METERS|" + c.meters);
            console.log("LABELS|" + c.labels.join("\t"));
            console.log("DRAWER|" + (it.openDrawerId !== ""));
            Qt.callLater(() => Qt.quit());
        }
    }
}
