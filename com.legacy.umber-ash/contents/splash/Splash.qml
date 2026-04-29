import QtQuick 2.15

// "Horizon" — a single peach hairline draws across the center as the boot
// stages advance, a small amber dot rides the leading edge. Wordmark sits
// beneath in muted glow. No spinner, no progress bar — just a slow draw.
Rectangle {
    id: root
    color: "#242424"

    property int stage

    // Stage range used for the line draw. KSplash typically emits 1..6;
    // we treat 1 as "fade in" and stretch the draw across 1..6.
    readonly property real progress: Math.max(0, Math.min(1, (stage - 1) / 5))

    onStageChanged: if (stage == 1) introAnimation.running = true

    // Subtle vertical gradient — charcoal at the top, marginally lifted at the
    // bottom. Implies a ground plane without ever drawing one.
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#242424" }
            GradientStop { position: 1.0; color: "#2B2B2B" }
        }
    }

    Item {
        id: content
        anchors.centerIn: parent
        width: 520
        height: 160
        opacity: 0

        // The "horizon" track — a thin charcoal-tinted rule that the peach
        // line draws over. Sits a touch above vertical center.
        Rectangle {
            id: track
            anchors.horizontalCenter: parent.horizontalCenter
            y: 70
            width: parent.width
            height: 1
            color: "#333333"
        }

        // The drawn portion — a horizontal gradient that fades in/out at the
        // ends so the line reads as a glimmer, not a progress bar. Width is
        // tied to stage progress with a smooth transition.
        Rectangle {
            id: glimmer
            anchors.left: track.left
            anchors.verticalCenter: track.verticalCenter
            height: 1
            width: track.width * root.progress
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0;  color: "#00D0BC95" }
                GradientStop { position: 0.15; color: "#FFD0BC95" }
                GradientStop { position: 0.85; color: "#FFD0BC95" }
                GradientStop { position: 1.0;  color: "#FFE5C07B" }
            }
            Behavior on width {
                NumberAnimation { duration: 600; easing.type: Easing.OutCubic }
            }
        }

        // Leading-edge dot — small amber pip with a soft halo. Travels with
        // the glimmer's right edge.
        Item {
            id: leadDot
            width: 24; height: 24
            x: glimmer.x + glimmer.width - width / 2
            y: track.y - height / 2
            Behavior on x {
                NumberAnimation { duration: 600; easing.type: Easing.OutCubic }
            }

            // Halo
            Rectangle {
                anchors.centerIn: parent
                width: 24; height: 24
                radius: 12
                color: "transparent"
                border.width: 0
                opacity: 0.35
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#80E5C07B" }
                    GradientStop { position: 1.0; color: "#00E5C07B" }
                }
            }
            // Pip
            Rectangle {
                anchors.centerIn: parent
                width: 5; height: 5
                radius: 2.5
                color: "#E5C07B"
            }
        }

        // Wordmark, two lines below the horizon. Lighter weight than before,
        // dimmer color — the line is the focal element, the word is grounding.
        Text {
            id: mark
            anchors.horizontalCenter: parent.horizontalCenter
            y: track.y + 38
            text: "umber-ash"
            font.family: "Noto Sans"
            font.pointSize: 24
            font.letterSpacing: 8
            font.weight: Font.Thin
            color: "#A6998A"
            renderType: Text.NativeRendering
        }

        // Tiny em-dash beneath the wordmark — barely visible, asymmetry cue.
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            y: mark.y + mark.height + 14
            width: 18
            height: 1
            color: "#444444"
        }
    }

    // Slow fade-in for the whole composition.
    OpacityAnimator {
        id: introAnimation
        running: false
        target: content
        from: 0
        to: 1
        duration: 900
        easing.type: Easing.OutCubic
    }
}
