//
// This file is part of Sugar Dark, a theme for the Simple Display Desktop Manager.
//
// Copyright 2018 Marian Arlt
//
// Sugar Dark is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// Sugar Dark is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with Sugar Dark. If not, see <https://www.gnu.org/licenses/>.
//

import QtQuick
import QtQuick.Layouts
import SddmComponents 2.0 as SDDM

ColumnLayout {
    id: formContainer
    SDDM.TextConstants { id: textConstants }
    spacing: root.font.pointSize * 1.6

    property bool virtualKeyboardActive
    property bool systemButtonVisibility: true
    property alias clockVisibility: clock.visible
    property alias exposeLogin: input.exposeLogin

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
