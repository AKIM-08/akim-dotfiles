import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15
import Qt.labs.folderlistmodel 2.15
import QtGraphicalEffects 1.15

Window {
    id: root
    width: Screen.width
    height: Screen.height
    color: "transparent" // Required for Wayland transparency
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Popup
    visibility: Window.FullScreen

    Rectangle {
        anchors.fill: parent
        color: "#d9000000"
    }

    Shortcut {
        sequence: "Escape"
        onActivated: Qt.quit()
    }
    
    MouseArea {
        anchors.fill: parent
        onClicked: Qt.quit()
    }

    FolderListModel {
        id: folderModel
        folder: "file://WALLPAPER_DIR_PLACEHOLDER"
        nameFilters: ["*.jpg", "*.jpeg", "*.png", "*.webp"]
        showDirs: false
    }

    Text {
        anchors.centerIn: parent
        text: "Loading wallpapers..."
        color: "white"
        font.pixelSize: 24
        visible: folderModel.count === 0
    }

    property real hexWidth: 200
    property real hexHeight: 230.94 // 200 * 1.1547
    property real spacing: 8
    
    property int numCols: Math.max(1, Math.floor(width * 0.8 / hexWidth))

    Flickable {
        id: flickable
        anchors.centerIn: parent
        width: numCols * hexWidth + hexWidth/2
        height: Math.min(Screen.height * 0.8, Math.ceil(folderModel.count / numCols) * (hexHeight * 0.75) + hexHeight * 0.25)
        contentWidth: width
        contentHeight: Math.ceil(folderModel.count / numCols) * (hexHeight * 0.75) + hexHeight * 0.25
        clip: true

        Repeater {
            model: folderModel
            delegate: Item {
                property int col: index % numCols
                property int row: Math.floor(index / numCols)
                
                x: col * hexWidth + (row % 2 !== 0 ? hexWidth / 2 : 0)
                y: row * (hexHeight * 0.75)
                width: hexWidth - spacing
                height: hexHeight - spacing

                Image {
                    id: img
                    anchors.fill: parent
                    source: fileUrl
                    fillMode: Image.PreserveAspectCrop
                    visible: false
                    asynchronous: true
                }

                Image {
                    id: mask
                    anchors.fill: parent
                    source: Qt.resolvedUrl("hexagon.svg")
                    sourceSize: Qt.size(width, height)
                    visible: false
                }

                OpacityMask {
                    anchors.fill: parent
                    source: img
                    maskSource: mask
                    
                    Rectangle {
                        anchors.fill: parent
                        color: "white"
                        opacity: mouseArea.containsMouse ? 0.15 : 0
                    }
                }

                scale: mouseArea.containsMouse ? 1.05 : 1.0
                Behavior on scale { NumberAnimation { duration: 150 } }

                MouseArea {
                    id: mouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: {
                        console.log("SELECTED:" + filePath)
                        Qt.quit()
                    }
                    onWheel: (wheel) => {
                        flickable.contentY -= wheel.angleDelta.y
                        if(flickable.contentY < 0) flickable.contentY = 0
                        if(flickable.contentY > flickable.contentHeight - flickable.height) flickable.contentY = flickable.contentHeight - flickable.height
                    }
                }
            }
        }
    }
}
