#!/usr/bin/env python

from beemaster import BeeMasterWindow
from beeapp import BeeApp
import sys
import PyQt4.QtGui as qtgui

if __name__ == "__main__":
	beeapp = BeeApp()
	app = qtgui.QApplication(sys.argv)
	beeapp.app=app
	beeapp.master = BeeMasterWindow(app)
	#app.setMainWidget(beeMasterWindow.window)
	app.exec_()
