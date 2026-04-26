import QtQuick 2.15

Rectangle {
    id: root
    color: "#2b2b2b"

    property int stage

    onStageChanged: {
        if (stage == 1) {
            introAnimation.running = true
        }
    }

    Item {
        id: content
        anchors.centerIn: parent
        width: 320
        height: 92
        opacity: 0

        Text {
            id: mark
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            text: "hush"
            font.family: "Noto Sans"
            font.pointSize: 36
            font.letterSpacing: 6
            font.weight: Font.Light
            color: "#D4BC91"
            renderType: Text.NativeRendering
        }

        Rectangle {
            id: track
            anchors.top: mark.bottom
            anchors.topMargin: 24
            anchors.horizontalCenter: parent.horizontalCenter
            width: 240
            height: 2
            radius: 1
            color: "#444444"

            Rectangle {
                id: bar
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: parent.width * Math.max(0, Math.min(1, (root.stage - 1) / 5))
                radius: 1
                color: "#D4BC91"
                Behavior on width {
                    NumberAnimation { duration: 250; easing.type: Easing.InOutQuad }
                }
            }
        }
    }

    OpacityAnimator {
        id: introAnimation
        running: false
        target: content
        from: 0
        to: 1
        duration: 600
        easing.type: Easing.InOutQuad
    }
}
