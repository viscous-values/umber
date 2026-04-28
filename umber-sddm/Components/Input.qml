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
import QtQuick.Controls
import Qt5Compat.GraphicalEffects

Column {
    id: inputContainer
    Layout.fillWidth: true
    spacing: root.font.pointSize * 0.7

    property Item exposeLogin: loginButton
    property bool failed

    // Shared field height — both pills are exactly the same size and shape.
    property real fieldHeight: root.font.pointSize * 2.8

    // USERNAME INPUT
    Item {
        id: usernameField

        height: inputContainer.fieldHeight
        width: parent.width
        anchors.horizontalCenter: parent.horizontalCenter

        // Single pill border. Always 1px; focus changes color only, never thickness.
        Rectangle {
            id: usernamePill
            anchors.fill: parent
            color: "transparent"
            border.color: username.activeFocus ? root.palette.highlight : root.palette.text
            border.width: 1
            radius: config.RoundCorners || 0
        }

        // Source image — invisible. ColorOverlay below uses it to render a tinted icon.
        // ColorOverlay reliably tints any SVG regardless of fill attributes, unlike
        // Button.icon.color on an SVGZ that lacks fill="currentColor".
        Image {
            id: userIconImg
            source: Qt.resolvedUrl("../Assets/User.svgz")
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
            color: root.palette.text
            z: 2
        }

        // Invisible click target for the user picker, sized over the icon area.
        ComboBox {
            id: selectUser
            width: parent.height
            height: parent.height
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            z: 3

            model: userModel
            currentIndex: model.lastIndex
            textRole: "name"
            hoverEnabled: true
            onActivated: { username.text = currentText }

            background: Rectangle { color: "transparent"; border.color: "transparent" }
            contentItem: Item { }
            indicator: Item { }

            delegate: ItemDelegate {
                width: parent.width
                anchors.horizontalCenter: parent.horizontalCenter
                contentItem: Text {
                    text: model.realName != "" ? model.realName : model.name
                    font.pointSize: root.font.pointSize * 0.8
                    font.capitalization: Font.Capitalize
                    color: selectUser.highlightedIndex === index ? "#444" : root.palette.highlight
                    verticalAlignment: Text.AlignVCenter
                    horizontalAlignment: Text.AlignHCenter
                }
                highlighted: parent.highlightedIndex === index
                background: Rectangle {
                    color: selectUser.highlightedIndex === index ? root.palette.highlight : "transparent"
                }
            }

            popup: Popup {
                y: usernameField.height
                width: usernameField.width
                implicitHeight: contentItem.implicitHeight
                padding: 10

                contentItem: ListView {
                    clip: true
                    implicitHeight: contentHeight + 20
                    model: selectUser.popup.visible ? selectUser.delegateModel : null
                    currentIndex: selectUser.highlightedIndex
                    ScrollIndicator.vertical: ScrollIndicator { }
                }

                background: Rectangle {
                    radius: config.RoundCorners / 2
                    color: "#444"
                    layer.enabled: true
                    layer.effect: DropShadow {
                        transparentBorder: true
                        horizontalOffset: 0
                        verticalOffset: 0
                        radius: 100
                        samples: 201
                        cached: true
                        color: "#88000000"
                    }
                }

                enter: Transition {
                    NumberAnimation { property: "opacity"; from: 0; to: 1 }
                }
            }
        }

        // TextField fills the entire pill. Equal left/right padding makes HCenter
        // genuinely center the text in the pill — not in the right-of-icon strip.
        // leftPadding ≈ icon area width so text never collides with the icon.
        TextField {
            id: username
            text: config.ForceLastUser == "true" ? selectUser.currentText : ""
            anchors.fill: parent
            leftPadding: parent.height
            rightPadding: parent.height
            verticalAlignment: TextInput.AlignVCenter
            horizontalAlignment: TextInput.AlignHCenter
            placeholderText: config.TranslateUsernamePlaceholder || textConstants.userName
            selectByMouse: true
            renderType: Text.QtRendering
            color: activeFocus ? root.palette.highlight : root.palette.text
            background: null
            Keys.onReturnPressed: loginButton.clicked()
            KeyNavigation.down: password
            z: 1
        }
    }

    // PASSWORD INPUT
    Item {
        id: passwordField
        height: inputContainer.fieldHeight
        width: parent.width
        anchors.horizontalCenter: parent.horizontalCenter

        Rectangle {
            id: passwordPill
            anchors.fill: parent
            color: "transparent"
            border.color: password.activeFocus ? root.palette.highlight : root.palette.text
            border.width: 1
            radius: config.RoundCorners || 0
        }

        TextField {
            id: password
            anchors.fill: parent
            leftPadding: parent.height
            rightPadding: parent.height
            verticalAlignment: TextInput.AlignVCenter
            horizontalAlignment: TextInput.AlignHCenter
            focus: config.ForcePasswordFocus == "true" ? true : false
            selectByMouse: true
            echoMode: revealSecret.checked ? TextInput.Normal : TextInput.Password
            placeholderText: config.TranslatePasswordPlaceholder || textConstants.password
            passwordCharacter: "•"
            passwordMaskDelay: config.ForceHideCompletePassword == "true" ? undefined : 1000
            renderType: Text.QtRendering
            color: activeFocus ? root.palette.highlight : root.palette.text
            background: null
            Keys.onReturnPressed: loginButton.clicked()
            KeyNavigation.down: revealSecret
        }

    }

    // SHOW/HIDE PASS — hidden in Umber; modern login screens don't expose this.
    Item {
        id: secretCheckBox
        visible: false
        height: 0
        width: parent.width
        anchors.horizontalCenter: parent.horizontalCenter

        CheckBox {
            id: revealSecret
            width: parent.width
            hoverEnabled: true

            indicator: Rectangle {
                id: indicator
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.topMargin: 3
                anchors.leftMargin: 4
                implicitHeight: root.font.pointSize
                implicitWidth: root.font.pointSize
                color: "transparent"
                border.color: root.palette.text
                border.width: parent.visualFocus ? 2 : 1
                Rectangle {
                    id: dot
                    anchors.centerIn: parent
                    implicitHeight: parent.width - 6
                    implicitWidth: parent.width - 6
                    color: root.palette.text
                    opacity: revealSecret.checked ? 1 : 0
                }
            }

            contentItem: Text {
                id: indicatorLabel
                text: config.TranslateShowPassword || "Show Password"
                anchors.verticalCenter: indicator.verticalCenter
                anchors.verticalCenterOffset: 0
                horizontalAlignment: Text.AlignLeft
                anchors.left: indicator.right
                anchors.leftMargin: indicator.width / 2
                font.pointSize: root.font.pointSize * 0.8
                color: root.palette.text
            }

            Keys.onReturnPressed: toggle()
            KeyNavigation.down: loginButton

            background: Rectangle {
                color: "transparent"
                border.width: parent.visualFocus ? 1 : 0
                border.color: parent.visualFocus ? root.palette.text : "transparent"
                height: parent.visualFocus ? 2 : 0
                width: (indicator.width + indicatorLabel.contentWidth + indicatorLabel.anchors.leftMargin + 2)
                anchors.top: indicatorLabel.bottom
                anchors.left: parent.left
                anchors.leftMargin: 3
                anchors.topMargin: 8
            }
        }

        states: [
            State {
                name: "pressed"
                when: revealSecret.down
                PropertyChanges {
                    target: revealSecret.contentItem
                    color: Qt.darker(root.palette.highlight, 1.1)
                }
                PropertyChanges {
                    target: dot
                    color: Qt.darker(root.palette.highlight, 1.1)
                }
                PropertyChanges {
                    target: indicator
                    border.color: Qt.darker(root.palette.highlight, 1.1)
                }
                PropertyChanges {
                    target: revealSecret.background
                    border.color: Qt.darker(root.palette.highlight, 1.1)
                }
            },
            State {
                name: "hovered"
                when: revealSecret.hovered
                PropertyChanges {
                    target: indicatorLabel
                    color: Qt.lighter(root.palette.highlight, 1.1)
                }
                PropertyChanges {
                    target: indicator
                    border.color: Qt.lighter(root.palette.highlight, 1.1)
                }
                PropertyChanges {
                    target: dot
                    color: Qt.lighter(root.palette.highlight, 1.1)
                }
                PropertyChanges {
                    target: revealSecret.background
                    border.color: Qt.lighter(root.palette.highlight, 1.1)
                }
            },
            State {
                name: "focused"
                when: revealSecret.visualFocus
                PropertyChanges {
                    target: indicatorLabel
                    color: root.palette.highlight
                }
                PropertyChanges {
                    target: indicator
                    border.color: root.palette.highlight
                }
                PropertyChanges {
                    target: dot
                    color: root.palette.highlight
                }
                PropertyChanges {
                    target: revealSecret.background
                    border.color: root.palette.highlight
                }
            }
        ]

        transitions: [
            Transition {
                PropertyAnimation {
                    properties: "color, border.color, opacity"
                    duration: 150
                }
            }
        ]

    }

    // ERROR FIELD — collapses to zero height when no error is showing, so the
    // password→login spacing stays tight unless we actually have something to say.
    Item {
        height: errorMessage.opacity > 0 ? root.font.pointSize * 1.8 : 0
        width: parent.width
        anchors.horizontalCenter: parent.horizontalCenter
        Behavior on height { NumberAnimation { duration: 100 } }
        Label {
            id: errorMessage
            width: parent.width
            text: failed ? config.TranslateLoginFailed || textConstants.loginFailed + "!" : keyboard.capsLock ? textConstants.capslockWarning : null
            horizontalAlignment: Text.AlignHCenter
            font.pointSize: root.font.pointSize * 0.8
            font.italic: true
            color: root.palette.text
            opacity: 0
            states: [
                State {
                    name: "fail"
                    when: failed
                    PropertyChanges {
                        target: errorMessage
                        opacity: 1
                    }
                },
                State {
                    name: "capslock"
                    when: keyboard.capsLock
                    PropertyChanges {
                        target: errorMessage
                        opacity: 1
                    }
                }
            ]
            transitions: [
                Transition {
                    PropertyAnimation {
                        properties: "opacity"
                        duration: 100
                    }
                }
            ]
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
            text: config.TranslateLogin || textConstants.login
            height: inputContainer.fieldHeight
            implicitWidth: parent.width
            enabled: username.text != "" && password.text != "" ? true : false
            hoverEnabled: true

            contentItem: Text {
                text: parent.text
                color: root.palette.text
                font.pointSize: root.font.pointSize
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                opacity: 0.55
            }

            background: Rectangle {
                id: buttonBackground
                color: "transparent"
                border.color: root.palette.text
                border.width: 1
                opacity: 0.55
                radius: config.RoundCorners || 0
            }

            states: [
                State {
                    name: "pressed"
                    when: loginButton.down
                    PropertyChanges {
                        target: buttonBackground
                        color: Qt.darker(root.palette.highlight, 1.1)
                        opacity: 1
                    }
                    PropertyChanges {
                        target: loginButton.contentItem
                        color: "#444"
                    }
                },
                State {
                    name: "hovered"
                    when: loginButton.hovered
                    PropertyChanges {
                        target: buttonBackground
                        color: root.palette.highlight
                        opacity: 1
                    }
                    PropertyChanges {
                        target: loginButton.contentItem
                        opacity: 1
                        color: "#444"
                    }
                },
                State {
                    name: "focused"
                    when: loginButton.visualFocus
                    PropertyChanges {
                        target: buttonBackground
                        color: root.palette.highlight
                        opacity: 1
                    }
                    PropertyChanges {
                        target: loginButton.contentItem
                        opacity: 1
                        color: "#444"
                    }
                },
                State {
                    name: "enabled"
                    when: loginButton.enabled
                    PropertyChanges {
                        target: buttonBackground
                        color: root.palette.text
                        border.width: 0
                        opacity: 1
                    }
                    PropertyChanges {
                        target: loginButton.contentItem
                        color: config.BackgroundColor || "#2B2B2B"
                        opacity: 1
                    }
                }
            ]

            transitions: [
                Transition {
                    from: ""; to: "enabled"
                    PropertyAnimation {
                        properties: "opacity, color";
                        duration: 500
                    }
                },
                Transition {
                    from: "enabled"; to: ""
                    PropertyAnimation {
                        properties: "opacity, color";
                        duration: 300
                    }
                }
            ]

            Keys.onReturnPressed: clicked()
            onClicked: sddm.login(username.text, password.text, sessionSelect.selectedSession)
        }
    }

    // SESSION SELECT
    SessionButton {
        id: sessionSelect
        textConstantSession: textConstants.session
    }

    Connections {
        target: sddm
        function onLoginSucceeded() {}
        function onLoginFailed() {
            failed = true
            resetError.running ? resetError.stop() && resetError.start() : resetError.start()
        }
    }

    Timer {
        id: resetError
        interval: 2000
        onTriggered: failed = false
        running: false
    }
}
