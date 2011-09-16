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

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui
import math
import sys

from beeutil import *

from beeapp import BeeApp

class BeeCanvasView(qtgui.QGraphicsView):
	def __init__(self,window,oldwidget,scene):
		self.tabletdown=False

		qtgui.QGraphicsView.__init__(self,scene,window)
		replaceWidget(oldwidget,self)
		self.windowid=window.id

		self.curzoom=1

		# don't draw in the widget background
		self.setAttribute(qtcore.Qt.WA_NoSystemBackground)
		# don't double buffer
		self.setAttribute(qtcore.Qt.WA_PaintOnScreen)

		# set scene view optimizations
		self.setOptimizationFlag(qtgui.QGraphicsView.DontAdjustForAntialiasing)

		#self.setViewportUpdateMode(qtgui.QGraphicsView.FullViewportUpdate)
		#self.setViewportUpdateMode(qtgui.QGraphicsView.MinimalViewportUpdate)
		self.setViewportUpdateMode(qtgui.QGraphicsView.SmartViewportUpdate)

		self.show()

	# for debugging memory usage
	#def __del__(self):
	#	print "DESTRUCTOR: BeeCanvasView"

	def paintEvent(self,event):
		window=BeeApp().master.getWindowById(self.windowid)
		lock=qtcore.QReadLocker(window.layerslistlock)
		#print "starting to handle paint event"

		#attempt at resolving inconsistent subscaling
		# if this is zoomed in
		if self.curzoom>1:
			oldrect=event.rect()
			xadj=(oldrect.x()%self.curzoom)+(self.curzoom*2)
			yadj=(oldrect.y()%self.curzoom)+(self.curzoom*2)
			wadj=(oldrect.width()%self.curzoom)-(self.curzoom*4)
			hadj=(oldrect.height()%self.curzoom)-(self.curzoom*4)
			newrect=qtcore.QRect(oldrect.x()-xadj,oldrect.y()-yadj,oldrect.width()-wadj,oldrect.height()-hadj)
			#print "current zoom:", self.curzoom
			#print "old rect:", rectToTuple(oldrect)
			#print "new rect:", rectToTuple(newrect)
			event=qtgui.QPaintEvent(newrect)

		qtgui.QGraphicsView.paintEvent(self,event)
		#print "ending handle paint event"

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
		self.curzoom=newzoom
		print_debug("canvas zoom is now: %f" % newzoom)

	def getVisibleImageRect(self):
		return self.scene().getSceneRect()

	def updateView(self,dirtyrect=qtcore.QRectF()):
		#dirtyrect=qtcore.QRectF(dirtyrect)

		#dirtyrect=dirtyrect.toAlignedRect()
		#dirtyrect=dirtyrect.adjusted(-1,-1,2,2)

		#vpoint=self.mapFromScene(qtcore.QPointF(dirtyrect.x(),dirtyrect.y()))

		#dirtyrect=self.mapToScene(self.viewport().visibleRegion().boundingRect()).boundingRect()

		self.updateScene([qtcore.QRectF(dirtyrect)])
		# just update the whole thing, since it causes little graphics problems when I only update subregions
		#self.scene().update()

	def tabletEvent(self,event):
		#print "tablet event (x,y,pressure):", event.x(),event.y(), event.pressure()
		#print "other values", event.rotation(), event.tangentialPressure(), event.xTilt(), event.yTilt()
		if event.type()==qtcore.QEvent.TabletMove:
			if event.pressure()>0:
				self.cursorMoveEvent(event.x(),event.y(),event.modifiers(),event.pointerType(),event.pressure(),event.hiResGlobalX()%1,event.hiResGlobalY()%1)

		elif event.type()==qtcore.QEvent.TabletPress:
			self.tabletdown=True
			self.cursorPressEvent(event.x(),event.y(),event.modifiers(),event.pointerType(),event.pressure(),event.hiResGlobalX()%1,event.hiResGlobalY()%1)

		elif event.type()==qtcore.QEvent.TabletRelease:
			self.tabletdown=False
			self.cursorReleaseEvent(event.x(),event.y(),event.modifiers())

	def mousePressEvent(self,event):
		if not self.tabletdown:
			self.cursorPressEvent(event.x(),event.y(),event.modifiers())

	def mouseMoveEvent(self,event):
		if not self.tabletdown:
			self.cursorMoveEvent(event.x(),event.y(),event.modifiers())

	def mouseReleaseEvent(self,event):
		if not self.tabletdown:
			self.cursorReleaseEvent(event.x(),event.y(),event.modifiers())

	# these are called regardless of if a mouse or tablet event was used
	def cursorPressEvent(self,x,y,modkeys,pointertype=4,pressure=1,subx=0,suby=0):
		#print "cursorPressEvent:(x,y,pressure)",x,y,pressure

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
		#print "cursorMoveEvent (x,y,pressure):",x,y,pressure
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
		self.windowid=window.id
		qtgui.QGraphicsScene.__init__(self,window)
		self.setSceneRect(qtcore.QRectF(0,0,window.docwidth,window.docheight))
		self.backdropcolor=qtgui.QColor(255,255,255)
		self.framecolor=qtgui.QColor(200,200,200)
		self.scenerectlock=qtcore.QReadWriteLock()

		self.image=qtgui.QImage(window.docwidth,window.docheight,qtgui.QImage.Format_ARGB32_Premultiplied)
		self.imagelock=qtcore.QReadWriteLock()

		self.tmppainter=None

	def event(self,event):
		if event.type()==BeeCustomEventTypes.addlayertoscene:
			self.addItem(event.layer)
		elif event.type()==BeeCustomEventTypes.removelayerfromscene:
			self.removeItem(event.layer)
		elif event.type()==BeeCustomEventTypes.setscenerect:
			self.setSceneRect(event.rect)
		return qtgui.QGraphicsScene.event(self,event)

	def removeItem(self,item):
		if qtcore.QThread.currentThread()==self.thread():
			qtgui.QGraphicsScene.removeItem(self,item)
		else:
			event=RemoveLayerFromSceneEvent(item)
			BeeApp().app.postEvent(self,event)

	def addItem(self,item):
		if qtcore.QThread.currentThread()==self.thread():
			print "adding item to scene"
			qtgui.QGraphicsScene.addItem(self,item)
			BeeApp().master.requestLayerListRefresh()
		else:
			event=AddLayerToSceneEvent(item)
			BeeApp().app.postEvent(self,event)

	def getImageCopy(self):
		lock=qtcore.QReadLocker(self.imagelock)
		copy=self.image.copy()
		return copy

	def getPixelColor(self,x,y,size=1):
		lock=qtcore.QReadLocker(self.imagelock)
		return self.image.pixel(x,y)

	def getSceneRect(self,lock=None):
		if not lock:
			lock=qtcore.QReadLocker(self.scenerectlock)
		return qtcore.QRectF(self.sceneRect())

	def setSceneRect(self,rect):
		if qtcore.QThread.currentThread()==self.thread():
			qtgui.QGraphicsScene.setSceneRect(self,rect)
			window=BeeApp().master.getWindowById(self.windowid)
			window.layerfinisher.resize(rect)
		else:
			event=SetSceneRectEvent(rect)
			BeeApp().app.postEvent(self,event)

	def setCanvasSize(self,newwidth,newheight):
		scenelocker=qtcore.QWriteLocker(self.scenerectlock)
		imagelock=qtcore.QWriteLocker(self.imagelock)
		self.image=self.image.scaled(newwidth,newheight)
		self.setSceneRect(qtcore.QRectF(self.image.rect()))

	def adjustCanvasSize(self,leftadj,topadj,rightadj,bottomadj):
		scenelocker=qtcore.QWriteLocker(self.scenerectlock)
		imagelock=qtcore.QWriteLocker(self.imagelock)
		oldrect=self.image.rect()
		newrect=oldrect.adjusted(0,0,leftadj+rightadj,topadj+bottomadj)
		self.setSceneRect(qtcore.QRectF(newrect))
		newimage=qtgui.QImage(newrect.width(),newrect.height(),qtgui.QImage.Format_ARGB32_Premultiplied)
		painter=qtgui.QPainter()
		painter.begin(newimage)
		painter.drawImage(qtcore.QPoint(leftadj,topadj),self.image)
		painter.end()
		self.image=newimage
		self.update()

	def stopTmpPainter(self,painter,rect):
		if self.tmppainter:
			self.tmppainter.end()
			self.tmppainter=None

			rect=rect.toAlignedRect()
			painter.setCompositionMode(qtgui.QPainter.CompositionMode_Source)
			painter.drawImage(rect,self.image,rect)

			#print "finishing up all layers and pasting image to view"
			#printImage(self.image)

		self.locker=None

	def drawForeground(self,painter,rect):
		#print
		#print "finishing up by drawing foreground"
		rectpath=qtgui.QPainterPath()
		rectpath.addRect(rect)

		scenepath=qtgui.QPainterPath()
		scenepath.addRect(self.getSceneRect())

		clippath=rectpath.subtracted(scenepath)

		drawrect=rect
		painter.setClipPath(clippath)
		painter.fillRect(drawrect,self.framecolor)
		self.locker=None

	def drawBackground(self,painter,rect):
		# unfortunately we can't just draw onto the standard painter because it does not support all blending modes
		# instead we draw onto a temporary image which does support all blending modes and then paint that onto the final painter
		self.tmppainter=qtgui.QPainter()

		self.locker=qtcore.QWriteLocker(self.imagelock)
		self.tmppainter.begin(self.image)

		drawrect=rect.intersected(self.getSceneRect())
		self.tmppainter.fillRect(drawrect,self.backdropcolor)
		self.curlayerim=None
		self.curlayercompmode=None
		self.curlayeropacity=None
