// SPDX-FileCopyrightText: 2014 Aleix Pol Gonzalez <aleixpol@blue-systems.com>
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Hush: verbatim copy of Plasma 6 stock LockOsd.qml.

import QtQuick
import org.kde.ksvg as KSvg
import org.kde.kirigami as Kirigami
import org.kde.plasma.workspace.osd

KSvg.FrameSvgItem {
    id: osd

    property alias timeout: osdItem.timeout
    property alias osdValue: osdItem.osdValue
    property alias osdMaxValue: osdItem.osdMaxValue
    property alias icon: osdItem.icon
    property alias showingProgress: osdItem.showingProgress

    objectName: "onScreenDisplay"
    visible: false
    width: osdItem.width + margins.left + margins.right
    height: osdItem.height + margins.top + margins.bottom
    imagePath: "dialogs/background"

    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.Window

    function show() {
        osd.visible = true;
        hideAnimation.restart();
    }

    Item {
        width: osdItem.width
        height: osdItem.height
        anchors.centerIn: parent

        OsdItem {
            id: osdItem
        }
    }

    SequentialAnimation {
        id: hideAnimation
        ScriptAction {
            script: osd.layer.enabled = true
        }
        PauseAnimation { duration: osd.timeout }
        NumberAnimation {
            target: osd
            property: "opacity"
            from: 1
            to: 0
            duration: Kirigami.Units.shortDuration
            easing.type: Easing.InQuad
        }
        ScriptAction {
            script: {
                osd.visible = false;
                osd.opacity = 1;
                osd.icon = "";
                osd.osdValue = 0;
                osd.layer.enabled = false;
            }
        }
    }
}
