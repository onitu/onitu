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

        menu = QMenu(self)
        exitAction = menu.addAction(self.tr("Exit Onitu"))
        startAction = menu.addAction(self.tr("Start the server"))
        stopAction = menu.addAction(self.tr("Stop the server"))
        configAction = menu.addAction(self.tr("Log and Configurations"))

        exitAction.triggered.connect(self.closeOnitu)
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

        self.guiSetup()
        self.startOnitu()

    def guiSetup(self):
        vLayout = QVBoxLayout()
        vLayout.addWidget(self.textEdit)
        self.setLayout(vLayout)
        self.resize(500, 600)

    def closeOnitu(self):
        self.closing = True
        self.stopOnitu()
        self.close()

    def startOnitu(self):
        if (self.onituProcess.state() == QProcess.NotRunning):
            self.onituProcess.start("onitu")
            self.tray.setIcon(self.onituIcon)

    def stopOnitu(self):
        if (self.onituProcess.state() != QProcess.NotRunning):
            self.onituProcess.kill()
            self.onituProcess.waitForFinished()
            self.tray.setIcon(self.onituStoppedIcon)
            self.output += "Onitu was stopped ----------" + os.linesep
            self.textEdit.setText(unicode(self.output))
            self.setScrollBarPosition()

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
#        print textToAdd,
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
