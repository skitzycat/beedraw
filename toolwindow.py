import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore

from beeutil import *

import os

from abstractbeewindow import AbstractBeeDockWindow

from ToolOptionsDockUi import Ui_ToolOptionsWindow
from BeeToolSelectionDockUi import Ui_ToolSelection

class ToolOptionsWindow(AbstractBeeDockWindow):
	def __init__(self,master):
		AbstractBeeDockWindow.__init__(self,master)
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

class ToolSelectionWindow(AbstractBeeDockWindow):
	def __init__(self,master):
		AbstractBeeDockWindow.__init__(self,master)
		self.master=master

		self.ui=Ui_ToolSelection()
		self.ui.setupUi(self)
		self.show()

	# connect signals for tool buttons
	def on_pencil_button_clicked(self,accept=False):
		if accept:
			self.master.changeCurToolByName("pencil")

	def on_brush_button_clicked(self,accept=False):
		if accept:
			self.master.changeCurToolByName("brush")

	def on_eraser_button_clicked(self,accept=False):
		if accept:
			self.master.changeCurToolByName("eraser")

	def on_paint_bucket_button_clicked(self,accept=False):
		if accept:
			self.master.changeCurToolByName("bucket")

	def on_eye_dropper_button_clicked(self,accept=False):
		if accept:
			self.master.changeCurToolByName("eyedropper")

	def on_move_selection_button_clicked(self,accept=False):
		if accept:
			self.master.changeCurToolByName("move selection")

	def on_rectangle_select_button_clicked(self,accept=False):
		if accept:
			self.master.changeCurToolByName("rectselect")

	def on_feather_select_button_clicked(self,accept=False):
		if accept:
			self.master.changeCurToolByName("featherselect")

	def hideEvent(self,event):
		if not self.isMinimized():
			self.master.uncheckWindowToolSelectBox()
		return qtgui.QWidget.hideEvent(self,event)
