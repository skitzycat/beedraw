#!/usr/bin/env python

from hivemaster import HiveMasterWindow
import sys
import PyQt4.QtGui as qtgui

from beeapp import BeeApp

if __name__ == "__main__":
	beeapp = BeeApp()
	app = qtgui.QApplication(sys.argv)
	beeapp.app = app
	beeapp.master = HiveMasterWindow.standAloneServer(app)
	app.exec_()
