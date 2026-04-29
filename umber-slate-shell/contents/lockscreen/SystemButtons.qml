// SPDX-License-Identifier: GPL-3.0-or-later
//
// Umber lockscreen SystemButtons — visual port of umber-sddm/Components/SystemButtons.qml.
// Lockscreen-appropriate action set: Suspend, Hibernate, Switch User. (Reboot/Shutdown
// can't be initiated from a locked session — those live on SDDM.)

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Qt5Compat.GraphicalEffects

import org.kde.plasma.private.sessions

Row {
    id: systemButtons
    spacing: lockScreenUi.font.pointSize * 1.4

    SessionManagement {
        id: sessionManagement
    }

    property var actions: [
        {
            id: "Suspend",
            label: "Suspend",
            available: root.suspendToRamSupported,
            fn: function() { root.suspendToRam() }
        },
        {
            id: "Hibernate",
            label: "Hibernate",
            available: root.suspendToDiskSupported,
            fn: function() { root.suspendToDisk() }
        },
        {
            id: "User",
            label: "Switch User",
            available: sessionManagement.canSwitchUser,
            fn: function() { sessionManagement.switchUser() }
        }
    ]

    Repeater {
        model: systemButtons.actions

        Item {
            id: btn
            width: lockScreenUi.font.pointSize * 4.6
            height: lockScreenUi.font.pointSize * 4.6
            visible: modelData.available

            Image {
                id: iconImg
                source: Qt.resolvedUrl("Assets/" + modelData.id + ".svgz")
                width: lockScreenUi.font.pointSize * 2.2
                height: lockScreenUi.font.pointSize * 2.2
                sourceSize.width: width * 2
                sourceSize.height: height * 2
                fillMode: Image.PreserveAspectFit
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: lockScreenUi.font.pointSize * 0.2
                visible: false
            }

            ColorOverlay {
                anchors.fill: iconImg
                source: iconImg
                color: mouseArea.containsMouse ? lockScreenUi.palette.highlight : lockScreenUi.palette.text
                opacity: 0.85
                Behavior on color { ColorAnimation { duration: 120 } }
            }

            Text {
                anchors.top: iconImg.bottom
                anchors.topMargin: lockScreenUi.font.pointSize * 0.3
                anchors.horizontalCenter: parent.horizontalCenter
                text: modelData.label
                font.pointSize: lockScreenUi.font.pointSize * 0.7
                color: mouseArea.containsMouse ? lockScreenUi.palette.highlight : lockScreenUi.palette.text
                opacity: 0.7
                Behavior on color { ColorAnimation { duration: 120 } }
            }

            MouseArea {
                id: mouseArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: modelData.fn()
            }
        }
    }
}
