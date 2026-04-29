// SPDX-License-Identifier: GPL-3.0-or-later
//
// Umber lockscreen LoginForm — visual port of umber-sddm/Components/LoginForm.qml.
// Container for clock + input. The lockscreen orchestrator (LockScreenUi.qml)
// places this column-centered, mirroring SDDM's Main.qml layout.

import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: formContainer
    spacing: lockScreenUi.font.pointSize * 1.6

    property bool virtualKeyboardActive
    property alias clockVisibility: clock.visible
    property alias exposeLogin: input.exposeLogin
    property alias inputItem: input

    Clock {
        id: clock
        Layout.alignment: Qt.AlignHCenter
    }

    Input {
        id: input
        Layout.alignment: Qt.AlignHCenter
        Layout.fillWidth: true
        Layout.topMargin: virtualKeyboardActive ? -height * 1.5 : 0
    }
}
