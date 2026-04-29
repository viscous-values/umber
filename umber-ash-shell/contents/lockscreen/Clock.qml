// SPDX-License-Identifier: GPL-3.0-or-later
//
// Umber lockscreen Clock — visual port of umber-sddm/Components/Clock.qml.
// Hardcodes the SDDM theme.conf values (HourFormat, DateFormat) since the
// lockscreen has no theme.conf — config.* on this side is for Plasma's own
// alwaysShowClock/showMediaControls knobs.

import QtQuick
import QtQuick.Controls

Column {
    id: clock
    spacing: 0
    width: parent.width / 2

    Label {
        id: timeLabel
        anchors.horizontalCenter: parent.horizontalCenter
        font.pointSize: lockScreenUi.font.pointSize * 3
        color: lockScreenUi.palette.text
        renderType: Text.QtRendering
        function updateTime() {
            text = new Date().toLocaleTimeString(Qt.locale(), "HH:mm")
        }
    }

    Label {
        id: dateLabel
        anchors.horizontalCenter: parent.horizontalCenter
        color: lockScreenUi.palette.text
        renderType: Text.QtRendering
        function updateTime() {
            text = new Date().toLocaleDateString(Qt.locale(), "dddd, d of MMMM")
        }
    }

    Timer {
        interval: 1000
        repeat: true
        running: true
        onTriggered: {
            dateLabel.updateTime()
            timeLabel.updateTime()
        }
    }

    Component.onCompleted: {
        dateLabel.updateTime()
        timeLabel.updateTime()
    }
}
