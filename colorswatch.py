#!/usr/bin/env python

import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore

# this class is meant to replace a Qwidget that was put into the designer

class ColorSwatch(qtgui.QWidget):
	def __init__(self,replacingwidget):
		qtgui.QWidget.__init__(self,replacingwidget.parentWidget())

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
