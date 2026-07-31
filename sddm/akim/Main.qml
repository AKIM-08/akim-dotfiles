import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtGraphicalEffects 1.15

Rectangle {
    id: root
    width: Screen.width
    height: Screen.height
    color: "#0f0f17"

    readonly property string wallpaperSource: config.background || "background.jpg"
    readonly property color panelColor: "#cc0f0f17"
    readonly property color fieldColor: "#33ffffff"
    readonly property color accentColor: "#89b4fa"
    readonly property color textColor: "#cdd6f4"

    Image {
        id: bgImage
        anchors.fill: parent
        source: wallpaperSource
        fillMode: Image.PreserveAspectCrop
        cache: false
        asynchronous: true
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Item {
            Layout.preferredWidth: 350
            Layout.fillHeight: true

            ShaderEffectSource {
                id: blurSource
                sourceItem: bgImage
                sourceRect: Qt.rect(0, 0, parent.width, parent.height)
            }

            FastBlur {
                anchors.fill: parent
                source: blurSource
                radius: 64
            }

            Rectangle {
                anchors.fill: parent
                color: panelColor

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: 56
                anchors.rightMargin: 56
                anchors.topMargin: 64
                anchors.bottomMargin: 48
                spacing: 14

                Item { Layout.fillHeight: true }

                Text {
                    text: "Welcome!"
                    color: textColor
                    font.pixelSize: 34
                    font.weight: Font.Light
                    Layout.alignment: Qt.AlignHCenter
                }

                Text {
                    id: clockText
                    color: textColor
                    font.pixelSize: 56
                    font.weight: Font.Light
                    Layout.alignment: Qt.AlignHCenter

                    Timer {
                        interval: 1000
                        running: true
                        repeat: true
                        triggeredOnStart: true
                        onTriggered: clockText.text = Qt.formatTime(new Date(), "hh:mm")
                    }
                }

                Text {
                    id: dateText
                    color: Qt.rgba(1, 1, 1, 0.75)
                    font.pixelSize: 14
                    Layout.alignment: Qt.AlignHCenter

                    Timer {
                        interval: 60000
                        running: true
                        repeat: true
                        triggeredOnStart: true
                        onTriggered: dateText.text = Qt.formatDate(new Date(), "dddd, d MMMM")
                    }
                }

                Item { Layout.preferredHeight: 24 }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 48
                    radius: 12
                    color: fieldColor

                    TextInput {
                        id: usernameField
                        anchors.fill: parent
                        anchors.margins: 14
                        color: textColor
                        font.pixelSize: 14
                        selectByMouse: true
                        readOnly: true
                        text: sddm.autologinUser || "marci"
                        verticalAlignment: Text.AlignVCenter
                        Keys.onReturnPressed: passwordField.forceActiveFocus()
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 48
                    radius: 12
                    color: fieldColor

                    TextInput {
                        id: passwordField
                        anchors.fill: parent
                        anchors.margins: 14
                        color: textColor
                        font.pixelSize: 14
                        echoMode: showPassword.checked ? TextInput.Normal : TextInput.Password
                        passwordCharacter: "•"
                        selectByMouse: true
                        focus: true
                        verticalAlignment: Text.AlignVCenter
                        Keys.onReturnPressed: loginButton.clicked()
                    }
                }

                CheckBox {
                    id: showPassword
                    text: "Show Password"
                    checked: false

                    contentItem: Text {
                        text: showPassword.text
                        color: textColor
                        font.pixelSize: 12
                        leftPadding: showPassword.indicator.width + showPassword.spacing
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Button {
                    id: loginButton
                    Layout.fillWidth: true
                    Layout.preferredHeight: 48
                    text: "Login"
                    background: Rectangle {
                        radius: 12
                        color: accentColor
                    }
                    contentItem: Text {
                        text: loginButton.text
                        color: "#11111b"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 14
                        font.weight: Font.Medium
                    }
                    onClicked: {
                        sddm.login(usernameField.text, passwordField.text, sessionSelect.currentIndex)
                    }
                }

                Connections {
                    target: sddm
                    function onLoginFailed() {
                        errorText.visible = true
                        passwordField.text = ""
                        passwordField.forceActiveFocus()
                    }
                }

                ComboBox {
                    id: sessionSelect
                    visible: false
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    model: sessionModel
                    textRole: "name"
                    background: Rectangle {
                        radius: 10
                        color: fieldColor
                    }
                    contentItem: Text {
                        leftPadding: 12
                        text: sessionSelect.displayText
                        color: textColor
                        font.pixelSize: 12
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Text {
                    id: errorText
                    visible: false
                    text: "Invalid username or password"
                    color: "#f38ba8"
                    font.pixelSize: 12
                    Layout.alignment: Qt.AlignHCenter
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 36

                    ColumnLayout {
                        spacing: 6
                        Layout.alignment: Qt.AlignHCenter

                        Rectangle {
                            width: 52
                            height: 52
                            radius: 26
                            color: fieldColor
                            border.color: Qt.rgba(1, 1, 1, 0.15)
                            border.width: 1

                            Text {
                                anchors.centerIn: parent
                                text: "⏸"
                                color: textColor
                                font.pixelSize: 18
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: sddm.suspend()
                            }
                        }

                        Text {
                            text: "Suspend"
                            color: Qt.rgba(1, 1, 1, 0.8)
                            font.pixelSize: 11
                            Layout.alignment: Qt.AlignHCenter
                        }
                    }

                    ColumnLayout {
                        spacing: 6
                        Layout.alignment: Qt.AlignHCenter

                        Rectangle {
                            width: 52
                            height: 52
                            radius: 26
                            color: fieldColor
                            border.color: Qt.rgba(1, 1, 1, 0.15)
                            border.width: 1

                            Text {
                                anchors.centerIn: parent
                                text: "↻"
                                color: textColor
                                font.pixelSize: 18
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: sddm.reboot()
                            }
                        }

                        Text {
                            text: "Reboot"
                            color: Qt.rgba(1, 1, 1, 0.8)
                            font.pixelSize: 11
                            Layout.alignment: Qt.AlignHCenter
                        }
                    }

                    ColumnLayout {
                        spacing: 6
                        Layout.alignment: Qt.AlignHCenter

                        Rectangle {
                            width: 52
                            height: 52
                            radius: 26
                            color: fieldColor
                            border.color: Qt.rgba(1, 1, 1, 0.15)
                            border.width: 1

                            Text {
                                anchors.centerIn: parent
                                text: "⏻"
                                color: textColor
                                font.pixelSize: 18
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: sddm.powerOff()
                            }
                        }

                        Text {
                            text: "Shutdown"
                            color: Qt.rgba(1, 1, 1, 0.8)
                            font.pixelSize: 11
                            Layout.alignment: Qt.AlignHCenter
                        }
                    }
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
