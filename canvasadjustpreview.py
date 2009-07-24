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

import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore

class CanvasAdjustPreview(qtgui.QWidget):
	def __init__(self,replacingwidget,window):
		qtgui.QWidget.__init__(self,replacingwidget.parentWidget())

		self.setGeometry(replacingwidget.frameGeometry())
		self.setObjectName(replacingwidget.objectName())

		self.window=window

		self.previewimage=window.image.scaled(200,200,qtcore.Qt.KeepAspectRatio)

		self.basewidth=window.image.width()
		self.baseheight=window.image.height()

		self.xoffset=(200-self.previewimage.width())/2
		self.yoffset=(200-self.previewimage.height())/2

		self.sizeratio=self.previewimage.width()/window.image.width()

		self.drawrect=qtcore.QRectF(self.xoffset,self.yoffset,self.previewimage.width(),self.previewimage.height())

		self.show()

	def paintEvent(self,event):
		painter=qtgui.QPainter()
		painter.begin(self)

		painter.drawImage(self.xoffset,self.yoffset,self.previewimage)

		painter.end()

	def newAdjustments(self,left,top,right,bottom):
		newwidth=self.basewidth-left+right
		newheight=self.baseheight-top+bottom

		newscalefactor=200/max(newwidth,newheight)

		newscaledwidth=newwidth*newscalefactor
		newscaledheight=newheight*newscalefactor

		newpreview=qtgui.QImage(newwidth,newheight,qtgui.QImage.Format_ARGB32_Premultiplied)

		oldimagepos_x=left*newscalefactor
		oldimagepos_y=top*newscalefactor

		# fill area with white
		newpreview.fill(0xFFFFFFFF)

		# draw image onto preview area
		painter=qtgui.QPainter()

		self.drawrect=qtcore.QRectF(leftbound,topbound,width,height)

		self.update()
