import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui
import math

from beeutil import *

import beemaster

# widget that we actually draw the image on for the user to see
class BeeViewDisplayWidget(qtgui.QWidget):
	def __init__(self,window):
		qtgui.QWidget.__init__(self)
		self.transform=qtgui.QTransform()
		self.setGeometry(0,0,window.docwidth,window.docheight)
		self.windowid=window.id
		self.show()
		self.pendown=False
		# don't draw in the widget background
		self.setAttribute(qtcore.Qt.WA_NoSystemBackground)
		# don't double buffer
		self.setAttribute(qtcore.Qt.WA_PaintOnScreen)

	def newZoom(self):
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
		# set up a transformation to do all the zoomming
		self.transform=qtgui.QTransform()
		self.transform=self.transform.scale(window.zoom,window.zoom)

		oldcorner=qtcore.QPoint(window.docwidth,window.docheight)
		newcorner=oldcorner.__mul__(self.transform)

		# update size of widget to be size of zoommed image
		self.setGeometry(0,0,newcorner.x(),newcorner.y())
		self.setFixedSize(newcorner.x(),newcorner.y())
		self.updateGeometry()
		self.update()

	def paintEvent(self,event):
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
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
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
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
			else:
				self.cursorReleaseEvent(event.x(),event.y())
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
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
		# if the window has no layers in it's layers list then just return
		if not window.layers:
			return

		if self.pendown:
			window.addPenUpToQueue(x,y)
		
		self.setCursor(beemaster.BeeMasterWindow().getCurToolDesc().getDownCursor())

		self.pendown=True
		x=x+subx
		y=y+suby
		x,y=self.viewCoordsToImage(x,y)
		window.addPenDownToQueue(x,y,pressure)

	def cursorMoveEvent(self,x,y,pressure=1,subx=0,suby=0):
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
		if self.pendown:
			#print "cursorMoveEvent at:",x,y,subx,suby
			x=x+subx
			y=y+suby
			x,y=self.viewCoordsToImage(x,y)
			#print "translates to image coords:",x,y
			window.addPenMotionToQueue(x,y,pressure)

	def cursorReleaseEvent(self,x,y,pressure=1,subx=0,suby=0):
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
		if self.pendown:
			self.setCursor(window.master.getCurToolDesc().getCursor())
			x,y=self.viewCoordsToImage(x,y)
			window.addPenUpToQueue(x,y)
		self.pendown=False

	def leaveEvent(self,event):
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
		if self.pendown:
			window.penLeave()

	def enterEvent(self,event):
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
		if self.pendown:
			window.penEnter()

	def viewCoordsToImage(self,x,y):
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
		#print "translating coords:",x,y
		visible=self.visibleRegion().boundingRect()

		if x<visible.x():
			x=visible.x()
		elif x>visible.x()+visible.width():
			x=visible.x()+visible.width()

		if y<visible.y():
			y=visible.y()
		elif y>visible.y()+visible.height():
			y=visible.y()+visible.height()

		if window.zoom!=1:
			x=x/window.zoom
			y=y/window.zoom

		#print "to coords:",x,y

		return x,y

# this is meant to replace a QWidget in the designer
class BeeViewScrollArea(qtgui.QScrollArea):
	def __init__(self,oldwidget,window):
		qtgui.QScrollArea.__init__(self,oldwidget.parentWidget())
		self.pendown=False

		self.setHorizontalScrollBarPolicy(qtcore.Qt.ScrollBarAlwaysOn)
		self.setVerticalScrollBarPolicy(qtcore.Qt.ScrollBarAlwaysOn)
		self.setBackgroundRole(qtgui.QPalette.Dark)

		self.setWidget(BeeViewDisplayWidget(window))

		self.setGeometry(oldwidget.geometry())
		self.setSizePolicy(oldwidget.sizePolicy())
		self.setObjectName(oldwidget.objectName())

		# put widget in center of scrolled area if thre is extra space
		self.setAlignment(qtcore.Qt.AlignCenter)

		self.show()
		self.widget().show()

	def newZoom(self):
		self.widget().newZoom()

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
