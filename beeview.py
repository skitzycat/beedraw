import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui
import math

from beeutil import *

# widget that we actually draw the image on for the user to see
class BeeViewDisplayWidget(qtgui.QWidget):
	def __init__(self,window):
		qtgui.QWidget.__init__(self)
		self.setGeometry(0,0,window.docwidth,window.docheight)
		self.window=window
		self.show()
		self.pendown=False

	def newZoom(self):
		self.setGeometry(0,0,math.ceil(self.window.docwidth*self.window.zoom),math.ceil(self.window.docheight*self.window.zoom))

		self.setFixedSize(math.ceil(self.window.docwidth*self.window.zoom),math.ceil(self.window.docheight*self.window.zoom))

		self.updateGeometry()
		self.update()

	def paintEvent(self,event):
		dirtyregion=event.region()

		#visible=self.visibleRegion()
		#dirtyregion.intersect(visible)

		if dirtyregion.isEmpty():
			return

		zoom=self.window.zoom

		# this rectangle region needs to be updated on the display widget
		widgetrect=dirtyregion.boundingRect()
		#print "got repaint for rect:", rectToTuple(widgetrect);
		#print "need to update view (", self.window.zoom, ") section:", rectToTuple(widgetrect)

		# align rect to even boundry with image
		#xadjust=widgetrect.x()%zoom
		#wadjust=widgetrect.width()%zoom

		#yadjust=widgetrect.y()%zoom
		#hadjust=widgetrect.height()%zoom
		#widgetrect=qtcore.QRectF(widgetrect.x()-xadjust,widgetrect.y()-yadjust,widgetrect.width()-wadjust+zoom,widgetrect.height()-hadjust+zoom)

		# calculate actual area of image we see due to current zoom factor
		# extra math is needed here so rows aren't missed due to rounding
		imagerect=qtcore.QRectF((widgetrect.x()/zoom)
													,(widgetrect.y()/zoom)
													,(widgetrect.width()/zoom)
													,(widgetrect.height()/zoom))


		#print "going from image rect:", rectToTuple(imagerect), "to widget rect:", rectToTuple(widgetrect), "zoom factor is:", zoom

		painter=qtgui.QPainter()
		painter.begin(self)

		painter.scale(zoom,zoom)

		# get read lock on the image
		imagelock=ReadWriteLocker(self.window.imagelock)

		# draw just what is needed into viewable area
		painter.drawImage(imagerect,self.window.image,imagerect)

		# relase the lock
		imagelock.unlock()

		self.drawViewOverlay(painter)

		painter.end()

		#self.dirtyimage=None

	# draw overlay things on the image, like selections
	def drawViewOverlay(self,painter):
		# this section will highlight selections if there is one
		selection=self.window.selection

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
		cursoroverlay=self.window.cursoroverlay

		if cursoroverlay:
			painter.setBrush(cursoroverlay.brush)
			painter.setPen(cursoroverlay.pen)
			painter.drawPath(cursoroverlay.path)
			
	def tabletEvent(self,event):
		if event.type()==qtcore.QEvent.TabletMove:
			# for some reason we don't get a release event when the pen is released
			# after going off the canvas, this is a quick hack to deal with it
			if event.pressure()>0:
				self.cursorMoveEvent(event.x(),event.y(),event.pressure())
			else:
				self.cursorReleaseEvent(event.x(),event.y())
		elif event.type()==qtcore.QEvent.TabletPress:
			self.cursorPressEvent(event.x(),event.y(),event.pressure())
		elif event.type()==qtcore.QEvent.TabletRelease:
			self.cursorReleaseEvent(event.x(),event.y())

	def mousePressEvent(self,event):
		self.cursorPressEvent(event.x(),event.y())

	def mouseMoveEvent(self,event):
		self.cursorMoveEvent(event.x(),event.y())

	def mouseReleaseEvent(self,event):
		self.cursorReleaseEvent(event.x(),event.y())

	# these are called regardless of if a mouse or tablet event was used
	def cursorPressEvent(self,x,y,pressure=1):
		# if the window has no layers in it's layers list then just return
		if not self.window.layers:
			return

		if self.pendown:
			self.window.penUp(x,y)
		
		self.setCursor(self.window.master.getCurToolDesc().getDownCursor())

		self.pendown=True
		x,y=self.viewCoordsToImage(x,y)
		self.window.addPenDownToQueue(x,y,pressure)

	def cursorMoveEvent(self,x,y,pressure=1):
		if self.pendown:
			x,y=self.viewCoordsToImage(x,y)
			self.window.addPenMotionToQueue(x,y,pressure)

	def cursorReleaseEvent(self,x,y,pressure=1):
		if self.pendown:
			self.setCursor(self.window.master.getCurToolDesc().getCursor())
			x,y=self.viewCoordsToImage(x,y)
			self.window.addPenUpToQueue(x,y)
		self.pendown=False

	def leaveEvent(self,event):
		if self.pendown:
			self.window.penLeave()

	def enterEvent(self,event):
		if self.pendown:
			self.window.penEnter()

	def viewCoordsToImage(self,x,y):
		visible=self.visibleRegion().boundingRect()

		if x<visible.x():
			x=visible.x()
		elif x>visible.x()+visible.width():
			x=visible.x()+visible.width()

		if y<visible.y():
			y=visible.y()
		elif y>visible.y()+visible.height():
			y=visible.y()+visible.height()

		x=int(x/self.window.zoom)
		y=int(y/self.window.zoom)

		return x,y

# this is meant to replace a QWidget in the designer
class BeeViewScrollArea(qtgui.QScrollArea):
	def __init__(self,oldwidget,window):
		qtgui.QScrollArea.__init__(self,oldwidget.parentWidget())
		self.pendown=False
		self.window=window

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
		#self.ensureWidgetVisible(self.widget())
		#self.setWidget(BeeViewDisplayWidget(self.window))

	def updateView(self,dirtyrect=None):
		if not dirtyrect:
			self.widget().update()
			return

		zoom=self.window.zoom

		# the rectangle needs to be according to the view instead of the image
		dirtyview=qtcore.QRect(math.floor(dirtyrect.x()*zoom),math.floor(dirtyrect.y()*zoom),math.ceil(dirtyrect.width()*zoom),math.ceil(dirtyrect.height()*zoom))

		# expand the area a little in case of rounding area during zoom change
		dirtyrect.adjust(-2,-2,4,4)

		self.widget().update(dirtyview)
