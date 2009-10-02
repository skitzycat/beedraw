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

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui
import math

from beeutil import *

from beeapp import BeeApp

# widget that we actually draw the image on for the user to see
class BeeViewDisplayWidget(qtgui.QWidget):
	def __init__(self,window):
		qtgui.QWidget.__init__(self)
		self.transform=qtgui.QTransform()
		self.docwidth=window.docwidth
		self.docheight=window.docheight
		self.setGeometry(0,0,window.docwidth,window.docheight)
		self.windowid=window.id
		self.show()
		# don't draw in the widget background
		self.setAttribute(qtcore.Qt.WA_NoSystemBackground)
		# don't double buffer
		self.setAttribute(qtcore.Qt.WA_PaintOnScreen)
		self.zoom=1

	def newSize(self,width,height):
		self.docwidth=width
		self.docheight=height
		self.refreshView()

	def getZoom(self):
		return self.zoom

	def newZoom(self,zoom):
		self.zoom=zoom
		self.refreshView()

	def refreshView(self):
		self.transform=qtgui.QTransform()
		self.transform=self.transform.scale(self.zoom,self.zoom)

		oldcorner=qtcore.QPoint(self.docwidth,self.docheight)
		newcorner=oldcorner.__mul__(self.transform)

		# update size of widget to be size of zoommed image
		self.setGeometry(0,0,newcorner.x(),newcorner.y())
		self.setFixedSize(newcorner.x(),newcorner.y())
		self.updateGeometry()
		self.update()

	def paintEvent(self,event):
		window=BeeApp().master.getWindowById(self.windowid)
		dirtyregion=event.region()

		if dirtyregion.isEmpty():
			return

		zoom=window.zoom

		# this rectangle region needs to be updated on the display widget
		widgetrect=dirtyregion.boundingRect()

		# get reverse matrix transform
		revtransform,isinvertable=self.transform.inverted()
		if not isinvertable:
			print "ERROR: can't invert zoom matrix"

		topleft=qtcore.QPointF(widgetrect.x(),widgetrect.y())
		bottomright=qtcore.QPointF(widgetrect.width(),widgetrect.height())

		# translate rectangle to what part of the image needs to be updated
		topleft=topleft.__mul__(revtransform)
		bottomright=bottomright.__mul__(revtransform)
		imagerect=qtcore.QRectF(topleft.x(),topleft.y(),bottomright.x(),bottomright.y())
		#imagerect.adjust(-1,-1,2,2)

		#print "got repaint for rect:", rectToTuple(widgetrect);
		#print "need to update view (", window.zoom, ") section:", rectToTuple(widgetrect)

		painter=qtgui.QPainter()
		painter.begin(self)

		painter.setTransform(self.transform)

		# get read lock on the image
		imagelock=ReadWriteLocker(window.imagelock)

		# draw just what is needed into viewable area
		painter.drawImage(imagerect,window.image,imagerect)

		# relase the lock
		imagelock.unlock()

		self.drawViewOverlay(painter)

		painter.end()

		#self.dirtyimage=None

	# draw overlay things on the image, like selections
	def drawViewOverlay(self,painter):
		window=BeeApp().master.getWindowById(self.windowid)
		# this section will highlight selections if there is one
		selection=window.selection

		# if there is a selection then draw it
		for select in selection:
		#if selection:
			painter.setPen(qtgui.QPen(qtgui.QColor(255,255,255,255)))
			painter.drawPath(select)
			painter.setPen(qtgui.QPen(qtcore.Qt.DashDotLine))
			painter.setBrush(qtgui.QBrush())
			painter.drawPath(select)

		# draw overlay related to what the cursor is currently doing
		# for instance if a user has the pen down with a selection tool
		cursoroverlay=window.cursoroverlay

		if cursoroverlay:
			painter.setBrush(cursoroverlay.brush)
			painter.setPen(cursoroverlay.pen)
			painter.drawPath(cursoroverlay.path)
			
	def tabletEvent(self,event):
		if event.type()==qtcore.QEvent.TabletMove:
			# for some reason we don't get a release event when the pen is released
			# after going off the canvas, this is a quick hack to deal with it
			if event.pressure()>0:
				self.cursorMoveEvent(event.x(),event.y(),event.pressure(),event.hiResGlobalX()%1,event.hiResGlobalY()%1)
			#else:
			#	self.cursorReleaseEvent(event.x(),event.y())
		elif event.type()==qtcore.QEvent.TabletPress:
			self.cursorPressEvent(event.x(),event.y(),event.pressure(),event.hiResGlobalX()%1,event.hiResGlobalY()%1)
		elif event.type()==qtcore.QEvent.TabletRelease:
			self.cursorReleaseEvent(event.x(),event.y())

	def mousePressEvent(self,event):
		self.cursorPressEvent(event.x(),event.y())

	def mouseMoveEvent(self,event):
		self.cursorMoveEvent(event.x(),event.y())

	def mouseReleaseEvent(self,event):
		self.cursorReleaseEvent(event.x(),event.y())

	# these are called regardless of if a mouse or tablet event was used
	def cursorPressEvent(self,x,y,pressure=1,subx=0,suby=0):
		#print "cursorPressEvent:",x,y,pressure
		
		window=BeeApp().master.getWindowById(self.windowid)
		# if the window has no layers in it's layers list then just return
		if not window.layers:
			return

		self.setCursor(BeeApp().master.getCurToolDesc().getDownCursor())

		x=x+subx
		y=y+suby
		x,y=self.viewCoordsToImage(x,y)
		window.addPenDownToQueue(x,y,pressure,layerkey=window.getCurLayerKey())

	def cursorMoveEvent(self,x,y,pressure=1,subx=0,suby=0):
		window=BeeApp().master.getWindowById(self.windowid)
		#print "cursorMoveEvent:",x,y,pressure
		x=x+subx
		y=y+suby
		x,y=self.viewCoordsToImage(x,y)
		#print "translates to image coords:",x,y
		window.addPenMotionToQueue(x,y,pressure,layerkey=window.getCurLayerKey())

	def cursorReleaseEvent(self,x,y,pressure=1,subx=0,suby=0):
		#print "cursorReleaseEvent:",x,y
		window=BeeApp().master.getWindowById(self.windowid)
		self.setCursor(window.master.getCurToolDesc().getCursor())
		x,y=self.viewCoordsToImage(x,y)
		window.addPenUpToQueue(x,y,layerkey=window.getCurLayerKey())

	def leaveEvent(self,event):
		window=BeeApp().master.getWindowById(self.windowid)
		window.penLeave()

	def enterEvent(self,event):
		window=BeeApp().master.getWindowById(self.windowid)
		window.penEnter()

	def snapPointToView(self,x,y):
		visible=self.visibleRegion().boundingRect()

		if x<visible.x():
			x=visible.x()
		elif x>visible.x()+visible.width():
			x=visible.x()+visible.width()

		if y<visible.y():
			y=visible.y()
		elif y>visible.y()+visible.height():
			y=visible.y()+visible.height()

		return x,y

	def viewCoordsToImage(self,x,y):
		window=BeeApp().master.getWindowById(self.windowid)
		#print "translating coords:",x,y

		if window.zoom!=1:
			x=x/window.zoom
			y=y/window.zoom

		#print "to coords:",x,y

		return x,y

# this is meant to replace a QWidget in the designer
class BeeViewScrollArea(qtgui.QScrollArea):
	def __init__(self,oldwidget,window):
		parent=oldwidget.parentWidget()
		qtgui.QScrollArea.__init__(self,parent)

		self.setHorizontalScrollBarPolicy(qtcore.Qt.ScrollBarAlwaysOn)
		self.setVerticalScrollBarPolicy(qtcore.Qt.ScrollBarAlwaysOn)
		self.setBackgroundRole(qtgui.QPalette.Dark)

		self.setWidget(BeeViewDisplayWidget(window))

		index=parent.layout().indexOf(oldwidget)
		parent.layout().removeWidget(oldwidget)
		parent.layout().insertWidget(index,self)

		self.setSizePolicy(oldwidget.sizePolicy())
		self.setObjectName(oldwidget.objectName())

		# put widget in center of scrolled area if thre is extra space
		self.setAlignment(qtcore.Qt.AlignCenter)

		self.show()
		self.widget().show()

	def getVisibleRect(self):
		return self.widget().visibleRegion().boundingRect()

	def getVisibleImageRect(self):
		widgetrect=self.getVisibleRect()
		zoom=self.widget().getZoom()
		x=widgetrect.x()/zoom
		y=widgetrect.y()/zoom
		width=widgetrect.width()/zoom
		height=widgetrect.height()/zoom
		return qtcore.QRectF(x,y,width,height)

	def newSize(self,width,height):
		self.widget().newSize(width,height)

	def newZoom(self,zoom):
		self.widget().newZoom(zoom)

	def snapPointToView(self,x,y):
		return self.widget().snapPointToView(x,y)

	def updateView(self,dirtyrect=None):
		if not dirtyrect:
			self.widget().update()
			return

		transform=self.widget().transform
		
		topleft=qtcore.QPointF(dirtyrect.x(),dirtyrect.y())
		bottomright=qtcore.QPointF(dirtyrect.width(),dirtyrect.height())

		# the rectangle needs to be according to the view instead of the image
		topleft=topleft.__mul__(transform)
		bottomright=bottomright.__mul__(transform)

		dirtyview=qtcore.QRectF(topleft.x(),topleft.y(),bottomright.x(),bottomright.y())

		#self.widget().update(dirtyview.toAlignedRect())
		self.widget().update(qtgui.QRegion(dirtyview.toAlignedRect()))
