import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore

from beeutil import *

import os

from ToolOptionsUi import Ui_ToolOptionsWindow

class ToolWindow(qtgui.QMainWindow):
	def __init__(self,master):
		qtgui.QMainWindow.__init__(self,master.topwinparent)
		self.master=master

		self.ui=Ui_ToolOptionsWindow()
		self.ui.setupUi(self)
		self.show()

		self.curwidget=self.ui.toolwidget
		self.toolwidgetparent=self.curwidget.parentWidget()

	def closeEvent(self,event):
		event.ignore()
		self.hide()

	def updateCurrentTool(self):
		curtool=self.master.getCurToolDesc()
		newwidget=curtool.getOptionsWidget(self.toolwidgetparent)

		replaceWidget(self.curwidget,newwidget)
		self.curwidget=newwidget

		self.ui.tool_name_label.setText(curtool.displayname)

	def hideEvent(self,event):
		if not self.isMinimized():
			self.master.uncheckWindowToolOptionsBox()
		return qtgui.QWidget.hideEvent(self,event)
