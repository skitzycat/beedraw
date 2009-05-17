#!/usr/bin/env python

import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore

# this class is meant to replace a Qwidget that was put into the designer

class ColorSwatch(qtgui.QWidget):
	def __init__(self,replacingwidget,master):
		qtgui.QWidget.__init__(self,replacingwidget.parentWidget())
		self.master=master

		self.color=qtgui.QColor(0,0,0)

		self.setGeometry(replacingwidget.frameGeometry())
		self.setObjectName(replacingwidget.objectName())

		self.show()

	def updateColor(self,color):
		self.color=color
		self.update()

	def paintEvent(self, event):
		rect=self.contentsRect()

		painter=qtgui.QPainter()
		painter.begin(self)

		painter.fillRect(rect,self.color)
		painter.end()

	def mousePressEvent(self,event):
		if event.button()==qtcore.Qt.LeftButton:
			self.changeColorDialog()
		elif event.button()==qtcore.Qt.RightButton:
			self.setFGToCurrent()
		elif event.button()==qtcore.Qt.MidButton:
			self.setCurrentToFG()

	def changeColorDialog(self):
		color=qtgui.QColorDialog.getColor(self.color,self)
		if color.isValid():
			self.updateColor(color)

	def setFGToCurrent(self):
		pass

	def setCurrentToFG(self):
		pass

class FGSwatch(ColorSwatch):
	def mousePressEvent(self,event):
		if event.button()==qtcore.Qt.LeftButton:
			self.changeColorDialog()
		else:
			self.swapFGandBG()

	def updateColor(self,color):
		self.color=color
		self.master.fgcolor=color
		self.update()

class BGSwatch(ColorSwatch):
	def mousePressEvent(self,event):
		if event.button()==qtcore.Qt.LeftButton:
			self.changeColorDialog()
		elif event.button()==qtcore.Qt.RightButton:
			self.setFGToCurrent()
		elif event.button()==qtcore.Qt.MidButton:
			self.setCurrentToFG()

	def updateColor(self,color):
		self.color=color
		self.master.bgcolor=color
		self.update()

	def setFGToCurrent(self):
		pass

	def setCurrentToFG(self):
		pass
