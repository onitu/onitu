import tempfile
import json
import sys
import os

from PySide.QtCore import Qt
from PySide.QtCore import QProcess
from PySide.QtCore import QFileSystemWatcher

from PySide.QtGui import QWidget
from PySide.QtGui import QApplication
from PySide.QtGui import QTextEdit
from PySide.QtGui import QPushButton
from PySide.QtGui import QLabel
from PySide.QtGui import QMenu
from PySide.QtGui import QIcon
from PySide.QtGui import QVBoxLayout
from PySide.QtGui import QHBoxLayout
from PySide.QtGui import QSystemTrayIcon


class OnituGui(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        self.closing = False
        self.onituProcess = None
        self.output = ""
        self.bottom = True
        self.textEdit = QTextEdit()
        self.textEdit.verticalScrollBar().valueChanged.connect(
            self.scrollBarMoved
            )
        self.startButton = QPushButton("Start Onitu")
        self.startButton.clicked.connect(self.startOnitu)
        self.stopButton = QPushButton("Stop Onitu")
        self.stopButton.clicked.connect(self.stopOnitu)
        self.exitButton = QPushButton("Exit Onitu GUI")
        self.exitButton.clicked.connect(self.exitOnitu)
        self.statusLabel = QLabel()
        self.statusLabel.setTextFormat(Qt.RichText)
        self.statusLabel.setText(
            '<img src=":onitu.png"> Onitu status: Started'
            )
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

        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        self.onituIcon = QIcon("onitu.png")
        self.onituStoppedIcon = QIcon("onitu_stopped.png")
        self.onituPendingIcon = QIcon("onitu_pending.png")

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

        self.onituProcess.readyReadStandardOutput.connect(
            self.processStandardOutput
            )
        self.onituProcess.readyReadStandardError.connect(
            self.processStandardError
            )
        self.onituProcess.finished.connect(self.onituTerminated)

        self.watcher = QFileSystemWatcher()

        tmp_dir = tempfile.gettempdir()
        tmp_filename = tmp_dir + os.sep + 'onitu_synced_files'

        try:
            open(tmp_filename, "a").close()
        except IOError as e:
            print "Failed to open/create '{}' file: {}".format(tmp_filename, e)

        self.watcher.addPath(tmp_filename)
        self.watcher.fileChanged.connect(self.tmpFileChanged)

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

    def tmpFileChanged(self, s):
        tmp_dir = tempfile.gettempdir()
        tmp_filename = tmp_dir + os.sep + 'onitu_synced_files'

        try:
            with open(tmp_filename, "r") as jsonFile:
                fileStr = jsonFile.read()
                data = json.loads(fileStr)
        except (IOError, ValueError):
            data = dict()

        nb_of_pending_files = 0
        if "onitu_nb_of_pending_files" in data:
            nb_of_pending_files = int(data["onitu_nb_of_pending_files"])

        if nb_of_pending_files > 0:
            self.tray.setIcon(self.onituPendingIcon)
        else:
            self.setSystrayIcon()

    def setSystrayIcon(self):
        if (self.onituProcess.state() == QProcess.NotRunning):
            self.tray.setIcon(self.onituStoppedIcon)
        else:
            self.tray.setIcon(self.onituIcon)

    def exitOnitu(self):
        self.closing = True
        self.stopOnitu()
        self.close()

    def startOnitu(self):
        if (self.onituProcess.state() == QProcess.NotRunning):
            self.statusLabel.setText(
                '<img src=":onitu.png"> Onitu status : Started'
                )

            self.output = ""
            self.onituProcess.start("onitu")
            self.setSystrayIcon()

    def stopOnitu(self):
        if (self.onituProcess.state() != QProcess.NotRunning):
            self.statusLabel.setText(
                '<img src=":onitu_stopped.png"> Onitu status : Stopped'
                )

            self.onituProcess.terminate()
            self.onituProcess.waitForFinished()

    def onituTerminated(self, exitCode):
        self.setSystrayIcon()
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
            self.textEdit.verticalScrollBar().setValue(
                self.textEdit.verticalScrollBar().maximum()
                )

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
    gui.hide()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
