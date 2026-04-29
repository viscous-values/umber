// SPDX-FileCopyrightText: 2014 Aleix Pol Gonzalez <aleixpol@blue-systems.com>
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Umber: verbatim copy of Plasma 6 stock LockScreen.qml. The Umber styling lives
// entirely in LockScreenUi.qml — keep this file in sync with upstream Plasma to
// avoid breaking kscreenlocker's "magical" property/signal contract.

import QtQuick

Item {
    id: root
    property bool debug: false
    property string notification
    signal clearPassword()
    signal notificationRepeated()

    property bool viewVisible: false
    property bool suspendToRamSupported: false
    property bool suspendToDiskSupported: false

    signal suspendToDisk()
    signal suspendToRam()

    LayoutMirroring.enabled: Application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

    implicitWidth: 800
    implicitHeight: 600

    LockScreenUi {
        anchors.fill: parent
    }
}
