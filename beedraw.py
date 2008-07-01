#!/usr/bin/env python

from beemaster import BeeMasterWindow
import sys
import PyQt4.QtGui as qtgui

if __name__ == "__main__":
	app = qtgui.QApplication(sys.argv)
	beeMasterWindow = BeeMasterWindow(app)
	#app.setMainWidget(beeMasterWindow.window)
	app.exec_()
