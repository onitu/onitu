import sys
from PySide.QtGui import *
from PySide.QtCore import *

class OnituGui(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        self.closing = False

        menu = QMenu(self)
        exitAction = menu.addAction(self.tr("Exit Onitu"))
        startAction = menu.addAction(self.tr("Start the server"))
        stopAction = menu.addAction(self.tr("Stop the server"))
        configAction = menu.addAction(self.tr("Configurations"))

        exitAction.triggered.connect(self.close_onitu)
        startAction.triggered.connect(self.start_onitu)
        stopAction.triggered.connect(self.stop_onitu)
        configAction.triggered.connect(self.open_config)

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon("onitu.png"))
        self.tray.setContextMenu(menu)
        self.tray.show()

    def close_onitu(self):
        self.closing = True
        self.close()

    def start_onitu(self):
        self.tray.setIcon(QIcon("onitu_started.png"))

    def stop_onitu(self):
        self.tray.setIcon(QIcon("onitu_stopped.png"))

    def open_config(self):
        self.show()

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
