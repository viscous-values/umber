// SPDX-License-Identifier: GPL-3.0-or-later
//
// Umber lockscreen Input — visual port of umber-sddm/Components/Input.qml.
// Differences from SDDM:
//   - No user picker: kscreenlocker has a single fixed user (kscreenlocker_userName),
//     so the username pill is read-only and shows that name.
//   - Login routes through kscreenlocker's authenticator.respond(password) rather
//     than sddm.login(user, password, session).
//   - Caps-lock warning reads from KeyboardIndicator.KeyState (Plasma's API)
//     instead of SDDM's `keyboard.capsLock`.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Qt5Compat.GraphicalEffects

import org.kde.plasma.private.keyboardindicator as KeyboardIndicator

Column {
    id: inputContainer
    Layout.fillWidth: true
    spacing: lockScreenUi.font.pointSize * 0.7

    property Item exposeLogin: loginButton
    property alias passwordField: password
    property bool failed
    property real fieldHeight: lockScreenUi.font.pointSize * 2.8

    // Hardcoded SDDM theme.conf values (no theme.conf on lockscreen side).
    readonly property int roundCorners: 20
    readonly property color cardColor: "#444"
    readonly property color bgColor: "#2D2823"

    KeyboardIndicator.KeyState {
        id: capsLockState
        key: Qt.Key_CapsLock
    }

    // USERNAME (read-only, mirrors SDDM pill but no picker).
    Item {
        id: usernameField
        height: inputContainer.fieldHeight
        width: parent.width
        anchors.horizontalCenter: parent.horizontalCenter

        Rectangle {
            id: usernamePill
            anchors.fill: parent
            color: "transparent"
            border.color: lockScreenUi.palette.text
            border.width: 1
            radius: inputContainer.roundCorners
            opacity: 0.55
        }

        Image {
            id: userIconImg
            source: Qt.resolvedUrl("Assets/User.svgz")
            width: parent.height * 0.42
            height: parent.height * 0.42
            sourceSize.width: width * 2
            sourceSize.height: height * 2
            fillMode: Image.PreserveAspectFit
            anchors.left: parent.left
            anchors.leftMargin: parent.height * 0.42
            anchors.verticalCenter: parent.verticalCenter
            visible: false
        }

        ColorOverlay {
            id: userIcon
            anchors.fill: userIconImg
            source: userIconImg
            color: lockScreenUi.palette.text
            opacity: 0.55
            z: 2
        }

        Text {
            anchors.fill: parent
            leftPadding: parent.height
            rightPadding: parent.height
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
            text: typeof kscreenlocker_userName !== "undefined" ? kscreenlocker_userName : ""
            font: password.font
            color: lockScreenUi.palette.text
            opacity: 0.85
            renderType: Text.QtRendering
        }
    }

    // PASSWORD
    Item {
        id: passwordField
        height: inputContainer.fieldHeight
        width: parent.width
        anchors.horizontalCenter: parent.horizontalCenter

        Rectangle {
            id: passwordPill
            anchors.fill: parent
            color: "transparent"
            border.color: password.activeFocus ? lockScreenUi.palette.highlight : lockScreenUi.palette.text
            border.width: 1
            radius: inputContainer.roundCorners
        }

        TextField {
            id: password
            anchors.fill: parent
            leftPadding: parent.height
            rightPadding: parent.height
            verticalAlignment: TextInput.AlignVCenter
            horizontalAlignment: TextInput.AlignHCenter
            focus: true
            selectByMouse: true
            echoMode: TextInput.Password
            placeholderText: "Password"
            passwordCharacter: "•"
            passwordMaskDelay: 1000
            renderType: Text.QtRendering
            color: activeFocus ? lockScreenUi.palette.highlight : lockScreenUi.palette.text
            background: null
            Keys.onReturnPressed: loginButton.clicked()
            KeyNavigation.down: loginButton
        }
    }

    // ERROR FIELD
    Item {
        height: errorMessage.opacity > 0 ? lockScreenUi.font.pointSize * 1.8 : 0
        width: parent.width
        anchors.horizontalCenter: parent.horizontalCenter
        Behavior on height { NumberAnimation { duration: 100 } }

        Label {
            id: errorMessage
            width: parent.width
            text: failed ? "Login failed!" : capsLockState.locked ? "Caps Lock is on" : ""
            horizontalAlignment: Text.AlignHCenter
            font.pointSize: lockScreenUi.font.pointSize * 0.8
            font.italic: true
            color: lockScreenUi.palette.text
            opacity: failed || capsLockState.locked ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 100 } }
        }
    }

    // LOGIN BUTTON
    Item {
        id: login
        height: inputContainer.fieldHeight
        width: parent.width
        anchors.horizontalCenter: parent.horizontalCenter

        Button {
            id: loginButton
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Unlock"
            height: inputContainer.fieldHeight
            implicitWidth: parent.width
            enabled: password.text != ""
            hoverEnabled: true

            contentItem: Text {
                text: parent.text
                color: lockScreenUi.palette.text
                font.pointSize: lockScreenUi.font.pointSize
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                opacity: 0.55
            }

            background: Rectangle {
                id: buttonBackground
                color: "transparent"
                border.color: lockScreenUi.palette.text
                border.width: 1
                opacity: 0.55
                radius: inputContainer.roundCorners
            }

            states: [
                State {
                    name: "pressed"
                    when: loginButton.down
                    PropertyChanges { target: buttonBackground; color: Qt.darker(lockScreenUi.palette.highlight, 1.1); opacity: 1 }
                    PropertyChanges { target: loginButton.contentItem; color: inputContainer.cardColor }
                },
                State {
                    name: "hovered"
                    when: loginButton.hovered
                    PropertyChanges { target: buttonBackground; color: lockScreenUi.palette.highlight; opacity: 1 }
                    PropertyChanges { target: loginButton.contentItem; opacity: 1; color: inputContainer.cardColor }
                },
                State {
                    name: "focused"
                    when: loginButton.visualFocus
                    PropertyChanges { target: buttonBackground; color: lockScreenUi.palette.highlight; opacity: 1 }
                    PropertyChanges { target: loginButton.contentItem; opacity: 1; color: inputContainer.cardColor }
                },
                State {
                    name: "enabled"
                    when: loginButton.enabled
                    PropertyChanges { target: buttonBackground; color: lockScreenUi.palette.text; border.width: 0; opacity: 1 }
                    PropertyChanges { target: loginButton.contentItem; color: inputContainer.bgColor; opacity: 1 }
                }
            ]

            transitions: [
                Transition { from: ""; to: "enabled"; PropertyAnimation { properties: "opacity, color"; duration: 500 } },
                Transition { from: "enabled"; to: ""; PropertyAnimation { properties: "opacity, color"; duration: 300 } }
            ]

            Keys.onReturnPressed: clicked()
            onClicked: {
                if (typeof authenticator !== "undefined") {
                    authenticator.respond(password.text)
                }
            }
        }
    }

    Connections {
        target: typeof authenticator !== "undefined" ? authenticator : null
        function onFailed(kind) {
            if (kind !== 0) return;
            failed = true
            password.clear()
            password.forceActiveFocus()
            resetError.restart()
        }
        function onSucceeded() {
            // Greeter quits; nothing to do here.
        }
    }

    Timer {
        id: resetError
        interval: 2000
        onTriggered: failed = false
        running: false
    }

    function clear() {
        password.clear()
        failed = false
    }
}
