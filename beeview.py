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

class BeeCanvasView(qtgui.QGraphicsView):
	def __init__(self,window,oldwidget,scene):
		qtgui.QGraphicsView.__init__(self,scene,window)
		replaceWidget(oldwidget,self)
		self.windowid=window.id

		# don't draw in the widget background
		self.setAttribute(qtcore.Qt.WA_NoSystemBackground)
		# don't double buffer
		self.setAttribute(qtcore.Qt.WA_PaintOnScreen)

		# set scene view optimizations
		#self.setOptimizationFlag(qtgui.QGraphicsView.DontAdjustForAntialiasing)

		self.show()

	def snapPointToView(self,x,y):
		visible=self.mapToScene(self.viewport().visibleRegion().boundingRect()).boundingRect()
		if x<visible.x():
			x=visible.x()
		elif x>visible.x()+visible.width():
			x=visible.x()+visible.width()

		if y<visible.y():
			y=visible.y()
		elif y>visible.y()+visible.height():
			y=visible.y()+visible.height()

		return x,y

	def snapPointToScene(self,x,y):
		rect=self.sceneRect().toAlignedRect()
		if x<rect.x():
			x=rect.x()
		elif x>rect.x()+rect.width():
			x=rect.x()+rect.width()

		if y<rect.y():
			y=rect.y()
		elif y>rect.y()+rect.height():
			y=rect.y()+rect.height()

		return x,y

	def newZoom(self,newzoom):
		self.setMatrix(qtgui.QMatrix())
		self.scale(newzoom,newzoom)

	def getVisibleImageRect(self):
		return self.scene().getSceneRect()

	def updateView(self,dirtyrect=qtcore.QRectF()):
		dirtyrect=qtcore.QRectF(dirtyrect)
		if not dirtyrect.isEmpty():
			dirtyrect=dirtyrect.toAlignedRect()
			dirtyrect=dirtyrect.adjusted(-1,-1,2,2)

		#print "updating view with rect:", rectToTuple(dirtyrect)
		self.updateScene([qtcore.QRectF(dirtyrect)])

	def tabletEvent(self,event):
		if event.type()==qtcore.QEvent.TabletMove:
			event.accept()
			if event.pressure()>0:
				self.cursorMoveEvent(event.x(),event.y(),event.modifiers(),event.pointerType(),event.pressure(),event.hiResGlobalX()%1,event.hiResGlobalY()%1)

		elif event.type()==qtcore.QEvent.TabletPress:
			event.accept()
			self.cursorPressEvent(event.x(),event.y(),event.modifiers(),event.pointerType(),event.pressure(),event.hiResGlobalX()%1,event.hiResGlobalY()%1)

		elif event.type()==qtcore.QEvent.TabletRelease:
			event.accept()
			self.cursorReleaseEvent(event.x(),event.y(),event.modifiers())

		return qtgui.QGraphicsView.tabletEvent(self,event)

	def mousePressEvent(self,event):
		self.cursorPressEvent(event.x(),event.y(),event.modifiers())

	def mouseMoveEvent(self,event):
		self.cursorMoveEvent(event.x(),event.y(),event.modifiers())

	def mouseReleaseEvent(self,event):
		self.cursorReleaseEvent(event.x(),event.y(),event.modifiers())

	# these are called regardless of if a mouse or tablet event was used
	def cursorPressEvent(self,x,y,modkeys,pointertype=4,pressure=1,subx=0,suby=0):
		#print "cursorPressEvent:",x,y,pressure
		
		window=BeeApp().master.getWindowById(self.windowid)
		# if the window has no layers in it's layers list then just return
		if not window.layers:
			return

		self.setCursor(BeeApp().master.getCurToolDesc().getDownCursor())

		x=x+subx
		y=y+suby
		x,y=self.viewCoordsToImage(x,y)
		window.penDown(x,y,pressure,modkeys)

	def cursorMoveEvent(self,x,y,modkeys,pointertype=4,pressure=1,subx=0,suby=0):
		window=BeeApp().master.getWindowById(self.windowid)
		#print "cursorMoveEvent:",x,y,pressure
		x=x+subx
		y=y+suby
		x,y=self.viewCoordsToImage(x,y)
		#print "translates to image coords:",x,y

		window.penMotion(x,y,pressure,modkeys)

	def cursorReleaseEvent(self,x,y,modkeys,pressure=1,subx=0,suby=0):
		#print "cursorReleaseEvent:",x,y
		window=BeeApp().master.getWindowById(self.windowid)
		self.setCursor(window.master.getCurToolDesc().getCursor())
		x,y=self.viewCoordsToImage(x,y)
		window.penUp(x,y,modkeys)

	def viewCoordsToImage(self,x,y):
		""" translates from a point for the input event to a point on the actual canvas.  Simply using mapToScene isn't sufficient because this needs to handle floats on both sides of the operation """
		x=float(x)
		y=float(y)
		#print "mapping coordinates:", x,y
		#point=self.mapToScene(x,y)
		#newx=point.x()
		#newy=point.y()
		#print "mapping to coordinates:", newx,newy
		#print "trying alternate method"
		trans=self.viewportTransform()
		revtrans,invertable=trans.inverted()
		altpoint=revtrans.map(qtcore.QPointF(x,y))
		#print altpoint.x(),altpoint.y()
		return altpoint.x(),altpoint.y()
		#return newx,newy

class BeeCanvasScene(qtgui.QGraphicsScene):
	def __init__(self,window):
		qtgui.QGraphicsScene.__init__(self,window)
		self.setSceneRect(0,0,window.docwidth,window.docheight)
		self.windowid=window.id
		self.backdropcolor=qtgui.QColor(255,255,255)
		self.framecolor=qtgui.QColor(200,200,200)
		self.scenerectlock=qtcore.QReadWriteLock()

		self.image=qtgui.QImage(window.docwidth,window.docheight,qtgui.QImage.Format_ARGB32_Premultiplied)
		self.imagelock=qtcore.QReadWriteLock()

		self.tmppainter=None

	def getImageCopy(self):
		lock=qtcore.QReadLocker(self.imagelock)
		return self.image.copy()

	def getPixelColor(self,x,y,size=1):
		lock=qtcore.QReadLocker(self.imagelock)
		return self.image.pixel(x,y)

	def getSceneRect(self,lock=None):
		if not lock:
			lock=qtcore.QReadLocker(self.scenerectlock)
		return qtcore.QRectF(self.sceneRect())

	def updateView(self,dirtyrect=qtcore.QRectF()):
		pass

	def setCanvasSize(self,newwidth,newheight):
		scenelocker=qtcore.QWriteLocker(self.scenerectlock)
		imagelock=qtcore.QWriteLocker(self.imagelock)
		self.image=self.image.scaled(newwidth,newheight)
		self.setSceneRect(qtcore.QRectF(self.image.rect()))

	def adjustCanvasSize(self,leftadj,topadj,rightadj,bottomadj):
		scenelocker=qtcore.QWriteLocker(self.scenerectlock)
		imagelock=qtcore.QWriteLocker(self.imagelock)
		oldrect=self.getSceneRect(scenelocker)
		newrect=oldrect.adjusted(0,0,leftadj+rightadj,topadj+bottomadj)
		self.setSceneRect(newrect)
		newimage=qtgui.QImage(newrect.width(),newrect.height(),qtgui.QImage.Format_ARGB32_Premultiplied)
		painter=qtgui.QPainter()
		painter.begin(newimage)
		painter.drawImage(qtcore.QPoint(leftadj,topadj),self.image)
		self.image=newimage
		self.update()

	def stopTmpPainter(self,painter,rect):
		if self.tmppainter:
			self.tmppainter.end()
			self.tmppainter=None

			#print "stopping tmp painter with float rectangle:", rectToTuple(rect)
			rect=rect.toAlignedRect()
			#print "stopping tmp painter with rectangle:", rectToTuple(rect)
			painter.setCompositionMode(qtgui.QPainter.CompositionMode_Source)
			painter.drawImage(rect,self.image,rect)
			self.locker=None

	def drawForeground(self,painter,rect):
		rectpath=qtgui.QPainterPath()
		rectpath.addRect(rect)

		scenepath=qtgui.QPainterPath()
		scenepath.addRect(self.getSceneRect())

		clippath=rectpath.subtracted(scenepath)

		drawrect=rect
		painter.setClipPath(clippath)
		painter.fillRect(drawrect,self.framecolor)

	def drawBackground(self,painter,rect):
		# unfortunately we can't just draw onto the standard painter because it does not support all blending modes
		# instead we draw onto a temporary image which does support all blending modes and then paint that onto the final painter
		self.tmppainter=qtgui.QPainter()
		self.locker=qtcore.QWriteLocker(self.imagelock)
		self.tmppainter.begin(self.image)

		drawrect=rect.intersected(self.getSceneRect())
		self.tmppainter.fillRect(drawrect,self.backdropcolor)
