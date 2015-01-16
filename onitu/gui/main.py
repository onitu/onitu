import sys
import os

from PySide.QtGui import *
from PySide.QtCore import *

class OnituGui(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        self.closing = False
        self.onituProcess = None
        self.output = ""
        self.bottom = True
        self.textEdit = QTextEdit()
        self.textEdit.verticalScrollBar().valueChanged.connect(self.scrollBarMoved)
        self.startButton = QPushButton("Start Onitu")
        self.startButton.clicked.connect(self.startOnitu)
        self.stopButton = QPushButton("Stop Onitu")
        self.stopButton.clicked.connect(self.stopOnitu)
        self.exitButton = QPushButton("Exit Onitu GUI")
        self.exitButton.clicked.connect(self.exitOnitu)
        self.statusLabel = QLabel()
        self.statusLabel.setTextFormat(Qt.RichText)
        self.statusLabel.setText('<img src=":onitu.png"> Onitu status : Started')
        self.statusLabel.setAlignment(Qt.AlignCenter)

        menu = QMenu(self)
        configAction = menu.addAction(self.tr("Log and informations"))
        startAction = menu.addAction(self.tr("Start the server"))
        stopAction = menu.addAction(self.tr("Stop the server"))
        exitAction = menu.addAction(self.tr("Exit Onitu"))

        exitAction.triggered.connect(self.exitOnitu)
        startAction.triggered.connect(self.startOnitu)
        stopAction.triggered.connect(self.stopOnitu)
        configAction.triggered.connect(self.openConfig)

        self.onituIcon = QIcon("onitu.png")
        self.onituStoppedIcon = QIcon("onitu_stopped.png")

        self.setWindowIcon(self.onituIcon)

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.onituIcon)
        self.tray.setContextMenu(menu)
        self.tray.show()

        # Setup the process
        self.onituProcess = QProcess()
        self.onituProcess.setWorkingDirectory("../../")
        self.onituProcess.setProcessChannelMode(QProcess.MergedChannels)
        self.onituProcess.setReadChannel(QProcess.StandardOutput)

        self.onituProcess.readyReadStandardOutput.connect(self.processStandardOutput)
        self.onituProcess.readyReadStandardError.connect(self.processStandardError)
        self.onituProcess.finished.connect(self.onituTerminated)

        self.guiSetup()
        self.startOnitu()

    def guiSetup(self):
        vLayout = QVBoxLayout()
        hLayout = QHBoxLayout()
        vLayout.addWidget(self.statusLabel)
        hLayout.addWidget(self.startButton)
        hLayout.addWidget(self.stopButton)
        vLayout.addLayout(hLayout)
        vLayout.addWidget(self.textEdit)
        vLayout.addWidget(self.exitButton)
        self.setLayout(vLayout)
        self.resize(500, 600)

    def exitOnitu(self):
        self.closing = True
        self.stopOnitu()
        self.close()

    def startOnitu(self):
        if (self.onituProcess.state() == QProcess.NotRunning):
            self.statusLabel.setText('<img src=":onitu.png"> Onitu status : Started')

            self.output = ""
            self.onituProcess.start("onitu")
            self.tray.setIcon(self.onituIcon)

    def stopOnitu(self):
        if (self.onituProcess.state() != QProcess.NotRunning):
            self.statusLabel.setText('<img src=":onitu_stopped.png"> Onitu status : Stopped')

            self.onituProcess.terminate()
            self.onituProcess.waitForFinished()

    def onituTerminated(self, exitCode):
        self.tray.setIcon(self.onituStoppedIcon)
        self.updateTextEdit("Onitu was stopped ----------" + os.linesep)

    def openConfig(self):
        self.show()

    def scrollBarMoved(self, value):
        if (value == self.textEdit.verticalScrollBar().maximum()):
            self.bottom = True
        else:
            self.bottom = False

    def setScrollBarPosition(self):
        if self.bottom is True:
            self.textEdit.verticalScrollBar().setValue(self.textEdit.verticalScrollBar().maximum())

    def updateTextEdit(self, textToAdd):
        self.output += textToAdd
        self.textEdit.setText(unicode(self.output))
        self.setScrollBarPosition()

    def processStandardOutput(self):
        out = self.onituProcess.readAllStandardOutput()
        self.updateTextEdit(out)

    def processStandardError(self):
        out = self.onituProcess.readAllStandardError()
        self.updateTextEdit(out)

    def closeEvent(self, event):
        if self.closing is False:
            self.hide()
            event.ignore()


def main():
    app = QApplication(sys.argv)
    gui = OnituGui()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
