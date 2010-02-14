#    Beedraw/Hive network capable client and server allowing collaboration on a single image
#    Copyright (C) 2009 B. Becker
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

import sys
sys.path.append("designer")

import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore

from beeutil import *

from ImageSizeAdjustDialogUi import Ui_CanvasSizeDialog

class CanvasAdjustDialog(qtgui.QDialog):
	def __init__(self,window):
		qtgui.QDialog.__init__(self)

		self.scene=qtgui.QGraphicsScene()
		self.view=qtgui.QGraphicsView(self.scene,self)

		self.ui=Ui_CanvasSizeDialog()
		self.ui.setupUi(self)

		replaceWidget(self.ui.image_preview,self.view)

		image=window.scene.getImageCopy()
		self.startwidth=image.width()
		self.startheight=image.height()

		self.item=CanvasAdjustPreview(image)

		self.scene.addItem(self.item)
		self.view.fitInView(self.item,qtcore.Qt.KeepAspectRatio)
		self.view.setHorizontalScrollBarPolicy(qtcore.Qt.ScrollBarAlwaysOff)
		self.view.setVerticalScrollBarPolicy(qtcore.Qt.ScrollBarAlwaysOff)
		self.view.setBackgroundBrush(qtgui.QColor(200,200,200))
		self.view.setAlignment(qtcore.Qt.AlignCenter)
		self.ui.image_preview=self.scene

		self.topadj=0
		self.leftadj=0
		self.rightadj=0
		self.bottomadj=0

	def showEvent(self,event):
		self.refreshPreview()
		return qtgui.QDialog.showEvent(self,event)

	def on_Top_Adjust_Box_valueChanged(self,value):
		if type(value)==type(int()):
			self.topadj=value
			if self.startheight+self.topadj+self.bottomadj<1:
				self.topadj=1-self.bottomadj-self.startheight
				self.ui.Top_Adjust_Box.setValue(self.topadj)
			self.refreshPreview()
	def on_Bottom_Adjust_Box_valueChanged(self,value):
		if type(value)==type(int()):
			self.bottomadj=value
			if self.startheight+self.topadj+self.bottomadj<1:
				self.bottomadj=1-self.topadj-self.startheight
				self.ui.Bottom_Adjust_Box.setValue(self.bottomadj)
			self.refreshPreview()
	def on_Left_Adjust_Box_valueChanged(self,value):
		if type(value)==type(int()):
			self.leftadj=value
			if self.startwidth+self.leftadj+self.rightadj<1:
				self.leftadj=1-self.rightadj-self.startwidth
				self.ui.Left_Adjust_Box.setValue(self.leftadj)
			self.refreshPreview()
	def on_Right_Adjust_Box_valueChanged(self,value):
		if type(value)==type(int()):
			self.rightadj=value
			if self.startwidth+self.leftadj+self.rightadj<1:
				self.rightadj=1-self.leftadj-self.startwidth
				self.ui.Left_Adjust_Box.setValue(self.rightadj)
			self.refreshPreview()

	def refreshPreview(self):
		self.item.newAdjustments(self.leftadj,self.topadj,self.rightadj,self.bottomadj)
		self.view.fitInView(self.item,qtcore.Qt.KeepAspectRatio)

class CanvasAdjustPreview(qtgui.QGraphicsItem):
	def __init__(self,image):
		qtgui.QGraphicsItem.__init__(self)

		self.oldimagecopy=image
		self.previewimage=self.oldimagecopy.copy()

	def boundingRect(self):
		return qtcore.QRectF(self.previewimage.rect())

	def paint(self,painter,options,widget=None):
		painter.drawImage(0,0,self.previewimage)

	def newAdjustments(self,left,top,right,bottom):
		newwidth=self.oldimagecopy.width()+left+right
		newheight=self.oldimagecopy.height()+top+bottom

		self.previewimage=qtgui.QImage(newwidth,newheight,qtgui.QImage.Format_ARGB32_Premultiplied)

		# fill area with white
		self.previewimage.fill(0xFFFFFFFF)

		# draw image onto preview area
		painter=qtgui.QPainter()
		painter.begin(self.previewimage)
		painter.drawImage(qtcore.QPoint(left,top),self.oldimagecopy)
		#self.drawrect=qtcore.QRectF(leftbound,topbound,width,height)

		self.prepareGeometryChange()
		self.update()
