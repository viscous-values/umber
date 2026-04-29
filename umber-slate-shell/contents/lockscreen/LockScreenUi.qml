// SPDX-License-Identifier: GPL-3.0-or-later
//
// Umber lockscreen UI — visual port of umber-sddm/Main.qml.
// Honors kscreenlocker's contract (LockScreen.qml's root signals/properties,
// the magical `wallpaper`/`authenticator`/`kscreenlocker_userName` globals)
// while laying out the same way SDDM does:
//   - charcoal floor under the wallpaper (matches theme.conf BackgroundColor)
//   - 0.55 black scrim over the wallpaper for legibility (BackgroundDimOpacity)
//   - centered LoginForm column (clock + username + password + unlock)
//   - SystemButtons row anchored bottom-right
//   - footer (virtual keyboard / layout switcher / battery) bottom-left

import QtQml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects

import org.kde.plasma.components as PlasmaComponents3
import org.kde.plasma.workspace.components as PW
import org.kde.kirigami as Kirigami

import org.kde.plasma.private.sessions
import org.kde.breeze.components

Pane {
    id: lockScreenUi

    // Always size to the screen — match SDDM's Main.qml.
    height: Screen.height
    width: Screen.width

    // Umber palette, hardcoded to match umber-sddm/theme.conf.
    palette.text: "#CFBC98"        // MainColor
    palette.highlight: "#ECE5D7"   // AccentColor
    palette.window: "#2A2C2F"      // BackgroundColor
    palette.button: "transparent"
    palette.buttonText: "#CFBC98"

    font.family: "Noto Sans"
    font.pointSize: Math.max(11, Math.min(15, Math.round(height / 80)))
    padding: 0

    LayoutMirroring.enabled: Application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

    readonly property color umberFloor: "#2A2C2F"
    readonly property real umberScrimOpacity: 0.55

    function handleMessage(msg) {
        if (!root.notification) {
            root.notification += msg;
        } else if (root.notification.includes(msg)) {
            root.notificationRepeated();
        } else {
            root.notification += "\n" + msg
        }
    }

    Connections {
        target: authenticator
        function onFailed(kind) {
            if (kind != 0) {
                return;
            }
            const msg = i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:status", "Unlocking failed");
            lockScreenUi.handleMessage(msg);
            graceLockTimer.restart();
            notificationRemoveTimer.restart();
            rejectPasswordAnimation.start();
        }

        function onSucceeded() {
            if (authenticator.hadPrompt) {
                Qt.quit();
            }
        }

        function onInfoMessageChanged() {
            lockScreenUi.handleMessage(authenticator.infoMessage);
        }

        function onErrorMessageChanged() {
            lockScreenUi.handleMessage(authenticator.errorMessage);
        }

        function onPromptChanged(msg) {
            lockScreenUi.handleMessage(authenticator.prompt);
        }

        function onPromptForSecretChanged(msg) {
            loginForm.inputItem.clear();
        }
    }

    SessionManagement {
        id: sessionManagement
    }

    Connections {
        target: sessionManagement
        function onAboutToSuspend() {
            root.clearPassword();
        }
    }

    RejectPasswordAnimation {
        id: rejectPasswordAnimation
        target: loginForm
    }

    // Charcoal floor — visible under any wallpaper transparency, sole color
    // when no wallpaper is set. Matches SDDM theme.conf BackgroundColor.
    Rectangle {
        id: floor
        anchors.fill: parent
        color: lockScreenUi.umberFloor
        z: -3
    }

    // Reparent kscreenlocker's `wallpaper` Item into our scene. KDE wallpaper
    // plugin items handle their own anchoring once parented.
    Item {
        id: wallpaperLayer
        anchors.fill: parent
        z: -2

        Component.onCompleted: {
            if (typeof wallpaper !== "undefined" && wallpaper) {
                wallpaper.parent = wallpaperLayer;
            }
        }
    }

    // 0.55 black scrim — mirrors theme.conf BackgroundDimOpacity.
    Rectangle {
        id: scrim
        anchors.fill: parent
        color: "#000000"
        opacity: lockScreenUi.umberScrimOpacity
        z: -1
    }

    MouseArea {
        id: lockScreenRoot
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.ArrowCursor
        drag.filterChildren: true

        onPressed: authenticator.startAuthenticating()

        Keys.onEscapePressed: {
            root.clearPassword();
            loginForm.inputItem.clear();
        }
        Keys.onPressed: event => {
            event.accepted = false;
        }

        Timer {
            id: notificationRemoveTimer
            interval: 3000
            onTriggered: root.notification = ""
        }

        Timer {
            id: graceLockTimer
            interval: 3000
            onTriggered: {
                root.clearPassword();
                authenticator.startAuthenticating();
            }
        }

        PropertyAnimation {
            id: launchAnimation
            target: lockScreenRoot
            property: "opacity"
            from: 0
            to: 1
            duration: Kirigami.Units.veryLongDuration * 2
        }

        Component.onCompleted: {
            launchAnimation.start();
            authenticator.startAuthenticating();
        }

        // Centered SDDM-style form.
        LoginForm {
            id: loginForm
            width: Math.min(parent.width * 0.32, 360)
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: 0
            virtualKeyboardActive: false
            z: 1
        }

        // Power buttons bottom-right — mirrors SDDM Main.qml.
        SystemButtons {
            id: globalSystemButtons
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.rightMargin: lockScreenUi.font.pointSize * 2.5
            anchors.bottomMargin: lockScreenUi.font.pointSize * 2
            z: 1
        }

        // Footer bottom-left — virtual keyboard / layout switcher / battery.
        // Lockscreen-only niceties; SDDM has its own boot-time pieces for these.
        RowLayout {
            id: footer
            anchors {
                bottom: parent.bottom
                left: parent.left
                margins: Kirigami.Units.smallSpacing
            }
            spacing: Kirigami.Units.smallSpacing

            PlasmaComponents3.ToolButton {
                id: keyboardButton
                focusPolicy: Qt.TabFocus
                Accessible.description: i18ndc("plasma_shell_org.kde.plasma.desktop", "Button to change keyboard layout", "Switch layout")
                icon.name: "input-keyboard"

                PW.KeyboardLayoutSwitcher {
                    id: keyboardLayoutSwitcher
                    anchors.fill: parent
                    acceptedButtons: Qt.NoButton
                }

                text: keyboardLayoutSwitcher.layoutNames.longName
                onClicked: keyboardLayoutSwitcher.keyboardLayout.switchToNextLayout()
                visible: keyboardLayoutSwitcher.hasMultipleKeyboardLayouts
            }

            Battery {}
        }

        Loader {
            z: 2
            active: root.viewVisible
            source: "LockOsd.qml"
            anchors {
                horizontalCenter: parent.horizontalCenter
                bottom: parent.bottom
                bottomMargin: Kirigami.Units.gridUnit
            }
        }
    }
}
