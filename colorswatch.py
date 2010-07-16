#    Beedraw/Hive network capable client and server allowing collaboration on a single image
#    Copyright (C) 2009 Thomas Becker
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore

# this class is meant to replace a Qwidget that was put into the designer

class ColorSwatch(qtgui.QWidget):
	def __init__(self,master,replacingwidget=None,parent=None,boxsize=20,color=None):
		self.master=master
		if color:
			self.color=qtgui.QColor(color[0],color[1],color[2])
		else:
			self.color=qtgui.QColor(255,255,255)

		if replacingwidget:
			qtgui.QWidget.__init__(self,replacingwidget.parentWidget())
			self.setGeometry(replacingwidget.frameGeometry())
			self.setObjectName(replacingwidget.objectName())

		else:
			qtgui.QWidget.__init__(self,parent)
			self.setFixedWidth(boxsize)
			self.setFixedHeight(boxsize)

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
			self.setFGToCurrent()
		elif event.button()==qtcore.Qt.RightButton:
			self.changeColorDialog()
		elif event.button()==qtcore.Qt.MidButton:
			self.setCurrentToFG()

	def changeColorDialog(self):
		color=qtgui.QColorDialog.getColor(self.color,self)
		if color.isValid():
			self.updateColor(color)

	def setFGToCurrent(self):
		self.master.setFGColor(self.color)

	def setCurrentToFG(self):
		self.updateColor(self.master.getFGColor())

	def swapFGandBG(self):
		tmp=self.master.getFGColor()
		self.master.setFGColor(self.master.getBGColor())
		self.master.setBGColor(tmp)

class FGSwatch(ColorSwatch):
	def mousePressEvent(self,event):
		if event.button()==qtcore.Qt.LeftButton:
			self.changeColorDialog()
		else:
			self.swapFGandBG()

	def changeColorDialog(self):
		color=qtgui.QColorDialog.getColor(self.master.getFGColor(),self)
		if color.isValid():
			self.updateColor(color)
			self.master.setFGColor(color)

	def updateColor(self,color):
		ColorSwatch.updateColor(self,color)

class BGSwatch(ColorSwatch):
	def mousePressEvent(self,event):
		if event.button()==qtcore.Qt.LeftButton:
			self.changeColorDialog()
		else:
			self.swapFGandBG()

	def changeColorDialog(self):
		color=qtgui.QColorDialog.getColor(self.master.getBGColor(),self)
		if color.isValid():
			self.updateColor(color)
			self.master.setBGColor(color)

	def updateColor(self,color):
		ColorSwatch.updateColor(self,color)
