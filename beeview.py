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

class BeeGraphicsScene(qtgui.QGraphicsScene):
	def __init__(self,window):
		qtgui.QGraphicsScene.__init__(self,0,0,window.docwidth,window.docheight)

		self.docwidth=window.docwidth
		self.docheight=window.docheight
		self.zoom=1
		self.windowid=window.id

		self.update()

	def drawBackground(self,painter,dirtyrect):
		print "drawing background"
		painter.fillRect(dirtyrect,qtgui.QColor(255,255,255))

	def drawItems(self,painter,items,options,widget=None):
		print "drawing Items"
		qtgui.QGraphicsScene.drawItems(self,painter,items,options,widget)

	def drawForeground(self,painter,dirtyrect):
		print "drawing foreground"
		scenepath=qtgui.QPainterPath()
		scenepath.addRect(self.sceneRect())
		scenepath.addRect(dirtyrect)
		painter.setClipPath(scenepath)
		painter.fillRect(dirtyrect,qtgui.QColor(200,200,200))

	def mousePressEvent(self,event):
		self.cursorPressEvent(event.scenePos().x(),event.scenePos().y(),event.modifiers())

	def mouseMoveEvent(self,event):
		self.cursorMoveEvent(event.scenePos().x(),event.scenePos().y(),event.modifiers())

	def mouseReleaseEvent(self,event):
		self.cursorReleaseEvent(event.scenePos().x(),event.scenePos().y(),event.modifiers())

	# these are called regardless of if a mouse or tablet event was used
	def cursorPressEvent(self,x,y,modkeys,pointertype=4,pressure=1):
		#print "cursorPressEvent:",x,y,pressure
		
		window=BeeApp().master.getWindowById(self.windowid)
		# if the window has no layers in it's layers list then just return
		if not window.layers:
			return

		self.views()[0].setCursor(BeeApp().master.getCurToolDesc().getDownCursor())

		window.penDown(x,y,pressure,modkeys,layerkey=window.getCurLayerKey())

	def cursorMoveEvent(self,x,y,modkeys,pointertype=4,pressure=1):
		window=BeeApp().master.getWindowById(self.windowid)
		#print "cursorMoveEvent:",x,y,pressure
		#print "translates to image coords:",x,y
		window.penMotion(x,y,pressure,modkeys,layerkey=window.getCurLayerKey())

	def cursorReleaseEvent(self,x,y,modkeys,pressure=1):
		#print "cursorReleaseEvent:",x,y
		window=BeeApp().master.getWindowById(self.windowid)
		self.views()[0].setCursor(window.master.getCurToolDesc().getCursor())
		window.penUp(x,y,modkeys,layerkey=window.getCurLayerKey())

	def leaveEvent(self,event):
		window=BeeApp().master.getWindowById(self.windowid)
		window.addPenLeaveToQueue(layerkey=window.getCurLayerKey())

	def enterEvent(self,event):
		window=BeeApp().master.getWindowById(self.windowid)
		window.addPenEnterToQueue(layerkey=window.getCurLayerKey())

class BeeGraphicsView(qtgui.QGraphicsView):
	def __init__(self,oldwidget,window):
		qtgui.QGraphicsView.__init__(self,window)
		parent=oldwidget.parentWidget()

		#self.setHorizontalScrollBarPolicy(qtcore.Qt.ScrollBarAlwaysOn)
		#self.setVerticalScrollBarPolicy(qtcore.Qt.ScrollBarAlwaysOn)

		#self.setViewportUpdateMode(qtgui.QGraphicsView.SmartViewportUpdate)

		#self.setCacheMode(qtgui.QGraphicsView.CacheNone)

		self.setScene(BeeGraphicsScene(window))

		replaceWidget(oldwidget,self)

		# put scene in center if there is extra space
		#self.setAlignment(qtcore.Qt.AlignCenter)

		#self.setAttribute(qtcore.Qt.WA_PaintOnScreen)
		#self.setAttribute(qtcore.Qt.WA_NoSystemBackground)

		self.zoom=1

	def paintEvent(self,event):
		print "got paint event in view"
		qtgui.QGraphicsView.paintEvent(self,event)

	def updateCanvasSize(self,width,height):
		self.scene().setSceneRect(0,0,width,height)
		self.update()

	def resizeEvent(self,event):
		qtgui.QWidget.resizeEvent(self,event)

	def event(self,event):
		if event.type()==qtcore.QEvent.TabletMove:
			x,y=self.viewCoordsToImage(event.x()+(event.hiResGlobalX()%1),event.y()+(event.hiResGlobalY()%1))
			# just a double check to make sure we don't pass on a value that doesn't make sense
			if event.pressure()>0:
				self.scene().cursorMoveEvent(x,y,event.modifiers(),event.pointerType(),event.pressure())

		elif event.type()==qtcore.QEvent.TabletPress:
			x,y=self.viewCoordsToImage(event.x()+(event.hiResGlobalX()%1),event.y()+(event.hiResGlobalY()%1))
			self.scene().cursorPressEvent(x,y,event.modifiers(),event.pointerType(),event.pressure())

		elif event.type()==qtcore.QEvent.TabletRelease:
			x,y=self.viewCoordsToImage(event.x()+(event.hiResGlobalX()%1),event.y()+(event.hiResGlobalY()%1))
			self.scene().cursorReleaseEvent(x,y,event.modifiers())

		return qtgui.QGraphicsView.event(self,event)

	def viewCoordsToImage(self,x,y):
		#print "translating coords:",x,y
		point=self.mapToScene(x,y)
		#print "to coords:",point.x(),point.y()

		return point.x(),point.y()

	def getVisibleImageRect(self):
		return qtcore.QRectF(self.viewport().visibleRegion().boundingRect())

	def keyPressEvent(self,event):
		BeeApp().master.newModKeys(event.modifiers())

	def newSize(self,width,height):
		self.scene().newSize(width,height)

	def newZoom(self,zoom):
		print_debug("zoom now: %f" % zoom)
		# reset translation matrix
		self.setMatrix(qtgui.QMatrix())
		self.zoom=zoom
		self.scale(zoom,zoom)
		self.update()

	def snapPointToView(self,x,y):
		return self.scene().snapPointToView(x,y)

	def updateView(self,dirtyrect=qtcore.QRect()):
		print "update view called"
		self.invalidateScene()
		self.updateScene([qtcore.QRectF(dirtyrect)])
		self.scene().invalidate()
		self.update(dirtyrect)
		self.scene().update(qtcore.QRectF(dirtyrect))
		self.scene().update()
		self.resetCachedContent()
		self.update()

	def drawItems(self,painter,items,options):
		print "view called drawing items"
		qtgui.QGraphicsView.drawItems(painter,items,options)
