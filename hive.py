#!/usr/bin/env python

from hivemaster import HiveMasterWindow
import sys
import PyQt4.QtGui as qtgui

if __name__ == "__main__":
	app = qtgui.QApplication(sys.argv)
	hiveMasterWindow = HiveMasterWindow.standAloneServer(app)
	app.exec_()
