//
// Originally adapted from MarianArlt's Sugar Dark.
// Hush rewrites the icon-rendering path to use Image + ColorOverlay so the SVGs
// reliably tint to the palette color (Button.icon.color is unreliable on SVGZ
// without fill="currentColor").
//

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Qt5Compat.GraphicalEffects
import SddmComponents 2.0 as SDDM

Row {
    id: systemButtons

    SDDM.TextConstants { id: textConstants }

    spacing: root.font.pointSize * 1.4

    property Item exposedLogin

    // In real SDDM, sddm.canSuspend etc. are booleans the system fills in.
    // In --test-mode they're often false across the board, which would hide all
    // buttons. Force-show in test (when all four are false simultaneously, which
    // is the test-mode signature) so styling can be verified before reboot.
    property bool testMode: !sddm.canSuspend && !sddm.canHibernate && !sddm.canReboot && !sddm.canPowerOff

    property var actions: [
        { id: "Suspend",   label: config.TranslateSuspend   || textConstants.suspend,   available: testMode || sddm.canSuspend,  fn: function() { sddm.suspend() } },
        { id: "Hibernate", label: config.TranslateHibernate || textConstants.hibernate, available: testMode || sddm.canHibernate, fn: function() { sddm.hibernate() } },
        { id: "Reboot",    label: config.TranslateReboot    || textConstants.reboot,    available: testMode || sddm.canReboot,   fn: function() { sddm.reboot() } },
        { id: "Shutdown",  label: config.TranslateShutdown  || textConstants.shutdown,  available: testMode || sddm.canPowerOff, fn: function() { sddm.powerOff() } }
    ]

    Repeater {
        model: systemButtons.actions

        Item {
            id: btn
            width: root.font.pointSize * 4.6
            height: root.font.pointSize * 4.6
            visible: modelData.available

            // Icon + text stack inside the hit area
            Image {
                id: iconImg
                source: Qt.resolvedUrl("../Assets/" + modelData.id + ".svgz")
                width: root.font.pointSize * 2.2
                height: root.font.pointSize * 2.2
                sourceSize.width: width * 2
                sourceSize.height: height * 2
                fillMode: Image.PreserveAspectFit
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: root.font.pointSize * 0.2
                visible: false
            }

            ColorOverlay {
                anchors.fill: iconImg
                source: iconImg
                color: mouseArea.containsMouse ? root.palette.highlight : root.palette.text
                opacity: 0.85
                Behavior on color { ColorAnimation { duration: 120 } }
            }

            Text {
                anchors.top: iconImg.bottom
                anchors.topMargin: root.font.pointSize * 0.3
                anchors.horizontalCenter: parent.horizontalCenter
                text: modelData.label
                font.pointSize: root.font.pointSize * 0.7
                color: mouseArea.containsMouse ? root.palette.highlight : root.palette.text
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
