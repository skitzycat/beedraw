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

# append designer dir to search path
import sys
sys.path.append("designer")

from beetypes import *

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui

from beeutil import *

from LayerWidgetUi import Ui_LayerConfigWidget
from LayersWindowUi import Ui_LayersWindow

from beeapp import BeeApp
from beeeventstack import *

class BeeLayerState:
	def __init__(self,windowid,type,key,image=None,opacity=None,visible=None,compmode=None,owner=0):
		self.windowid=windowid
		self.key=key
		self.owner=owner

		# way to flag that the layer should be deleted later, currently only used for anchoring floating selection layers
		self.shoulddelete=False
		self.deletelock=qtcore.QReadWriteLock()

		win=BeeApp().master.getWindowById(windowid)

		#print "creating layer with key:", key
		#print "creating layer with owner:", owner
		# this is a lock for locking access to the layer image when needed
		self.imagelock=qtcore.QReadWriteLock()
		self.propertieslock=qtcore.QReadWriteLock()

		self.configwidget=None

		self.type=type

		if image:
			self.image=image
		else:
			self.image=qtgui.QImage(win.docwidth,win.docheight,qtgui.QImage.Format_ARGB32_Premultiplied)
			self.image.fill(0)

		# set default values for anything we didn't get an explicit value for
		if opacity==None:
			opacity=1.0
		if visible==None:
			visible=True
		if compmode==None:
			compmode=qtgui.QPainter.CompositionMode_SourceOver

		self.changeOpacity(opacity)
		self.visible=visible
		self.compmode=compmode

		# set default name for layer
		self.changeName("Layer %d" % key)

	def changeOpacity(self,opacity):
		self.opacity_setting=opacity

	def getOpacity(self):
		return self.opacity_setting

	def getCompmode(self):
		return self.compmode

	def scale(self,newwidth,newheight):
		lock=qtcore.QWriteLocker(self.imagelock)
		self.image=self.image.scaled(newwidth,newheight,qtcore.Qt.IgnoreAspectRatio,qtcore.Qt.SmoothTransformation)

	def getImageRect(self):
		lock=qtcore.QReadLocker(self.imagelock)
		return self.image.rect()

	def getWindow(self):
		return BeeApp().master.getWindowById(self.windowid)

	def changeName(self,newname):
		proplock=qtcore.QWriteLocker(self.propertieslock)

		self.name=newname

		proplock.unlock()

		if self.configwidget:
			self.configwidget.updateValuesFromLayer()

	def getOwner(self,lock=None):
		if not lock:
			lock=qtcore.QReadLocker(self.propertieslock)

		return self.owner

	# change the ownership of a layer and remove all undo/redo history for that layer
	def changeOwner(self,owner):
		win=self.getWindow()

		win.deleteLayerHistory(self.key)

		proplock=qtcore.QWriteLocker(self.propertieslock)
		self.owner=owner

		if win.type==WindowTypes.networkclient or win.type==WindowTypes.standaloneserver or win.type==WindowTypes.integratedserver:
			if win.ownedByNobody(owner):
				self.type=LayerTypes.network
			elif win.ownedByMe(owner):
				self.type=LayerTypes.user
			else:
				self.type=LayerTypes.network
		else:
			self.type=LayerTypes.user

		proplock.unlock()

		if self.configwidget:
			self.configwidget.updateValuesFromLayer()

		win.setValidActiveLayer()

	# composite image onto layer from center coord
	def compositeFromCenter(self,image,x,y,compmode,clippath=None):
		x=int(x)
		y=int(y)
		#print "calling compositeFromCenter with args:",x,y
		width=image.size().width()
		height=image.size().height()
		#print "image dimensions:", width, height
		self.compositeFromCorner(image,x-int((width)/2),y-int((height)/2),compmode,clippath)

	# composite image onto layer from corner coord
	def compositeFromCorner(self,image,x,y,compmode,clippath=None,lock=None):
		x=int(x)
		y=int(y)
		#print "calling compositeFromCorner with args:",x,y

		if not lock:
			lock=qtcore.QWriteLocker(self.imagelock)

		width=image.size().width()
		height=image.size().height()
		rect=qtcore.QRect(x,y,width,height)
		painter=qtgui.QPainter()
		painter.begin(self.image)
		if clippath:
			painter.setClipPath(clippath)
		#print "inside compositeFromCorner"
		painter.setCompositionMode(compmode)
		#painter.setRenderHint(qtgui.QPainter.HighQualityAntialiasing)
		painter.drawImage(rect,image)
		painter.end()

		dirtyregion=qtgui.QRegion(rect)
		win=BeeApp().master.getWindowById(self.windowid)

		sizelock=qtcore.QReadLocker(win.docsizelock)
		# not every type of window actually has a full image representation so just calculate what the image rectangle would be
		imagerect=qtcore.QRect(0,0,win.docwidth,win.docheight)

		dirtyregion=dirtyregion.intersect(qtgui.QRegion(imagerect))
		lock.unlock()
		win.reCompositeImage(dirtyregion.boundingRect())

	# get color of pixel at specified point, or average color in range
	def getPixelColor(self,x,y,size):
		lock=qtcore.QReadLocker(self.imagelock)
		return self.image.pixel(x,y)

	# return copy of image
	def getImageCopy(self,lock=None,subregion=qtcore.QRect()):
		if not lock:
			lock=qtcore.QReadLocker(self.imagelock)
		retimage=self.image.copy(subregion)
		return retimage

	# composite section of layer onto paint object passed
	def compositeLayerOn(self,painter,dirtyrect):
		# if layer is not visible just return
		if not self.visible:
			return

		proplock=qtcore.QReadLocker(self.propertieslock)

		painter.setOpacity(self.opacity())
		painter.setCompositionMode(self.compmode)

		lock=qtcore.QWriteLocker(self.imagelock)

		painter.drawImage(dirtyrect,self.image,dirtyrect)

	# set any passed layer options
	def setOptions(self,opacity=None,compmode=None):
		proplock=qtcore.QWriteLocker(self.propertieslock)

		if opacity!=None:
			self.changeOpacity(opacity)

		if compmode!=None:
			self.compmode=compmode

		proplock.unlock()

		if self.configwidget:
			self.configwidget.updateValuesFromLayer()

		BeeApp().master.getWindowById(self.windowid).reCompositeImage()

	def adjustCanvasSize(self,leftadj,topadj,rightadj,bottomadj,lock=None):
		if not lock:
			lock=qtcore.QWriteLocker(self.imagelock)

		win=BeeApp().master.getWindowById(self.windowid)
		newimage=qtgui.QImage(win.docwidth,win.docheight,qtgui.QImage.Format_ARGB32_Premultiplied)
		newimage.fill(0)

		oldimagerect=self.image.rect()
		newimagerect=newimage.rect()
		srcRect=oldimagerect
		targetRect=qtcore.QRect(srcRect)
		targetRect.adjust(leftadj,topadj,leftadj,topadj)

		painter=qtgui.QPainter()
		painter.begin(newimage)
		#painter.drawImage(targetRect,self.image,srcRect)
		painter.drawImage(qtcore.QPoint(leftadj,topadj),self.image)
		painter.end()

		self.image=newimage
		self.prepareGeometryChange()

	def copy(self,path,imagelock=None):
		pass

	# cut is the only operation I see potential for being used in network communication
	def cut(self,path,imagelock=None):
		pathrectf=path.boundingRect()
		pathrect=pathrectf.toAlignedRect()

		if not imagelock:
			imagelock=qtcore.QWriteLocker(self.imagelock)

		oldareaimage=self.getImageCopy(imagelock,pathrect)

		win=BeeApp().master.getWindowById(self.windowid)
		if win.ownedByMe(self.owner):
			self.copy(path,imagelock)

		# erase from image
		painter=qtgui.QPainter()
		painter.begin(self.image)
		painter.setClipPath(path)
		painter.setCompositionMode(qtgui.QPainter.CompositionMode_Clear)
		painter.drawImage(self.image.rect(),self.image)
		painter.end()

		imagelock.unlock()

		self.update(pathrectf)
		BeeApp().master.refreshLayerThumb(self.windowid,self.key)

		command=DrawingCommand(self.key,oldareaimage,pathrect)
		win=BeeApp().master.getWindowById(self.windowid)
		win.addCommandToHistory(command,self.owner)

class BeeGuiLayer(BeeLayerState,qtgui.QGraphicsItem):
	def __init__(self,windowid,type,key,image=None,opacity=None,visible=None,compmode=None,owner=0,parent=None):
		qtgui.QGraphicsItem.__init__(self,parent)
		BeeLayerState.__init__(self,windowid,type,key,image,opacity,visible,compmode,owner)
		self.setFlag(qtgui.QGraphicsItem.ItemUsesExtendedStyleOption)

	def paste(self,image,x=0,y=0):
		win=BeeApp().master.getWindowById(self.windowid)
		newkey=win.nextLayerKey()
		newlayer=FloatingSelection(image,newkey,self)
		BeeApp().master.requestLayerListRefresh()

	def copy(self,path,imagelock=None):
		pathrectf=path.boundingRect()
		pathrect=pathrectf.toAlignedRect()

		if not imagelock:
			imagelock=qtcore.QWriteLocker(self.imagelock)

		tmpimage=qtgui.QImage(self.image.width(),self.image.height(),qtgui.QImage.Format_ARGB32_Premultiplied)
		tmpimage.fill(0)

		# copy onto new image
		painter=qtgui.QPainter()
		painter.begin(tmpimage)
		painter.setClipPath(path)
		painter.drawImage(self.image.rect(),self.image)
		painter.end()

		# clip image down to minimum size
		tmpimage=tmpimage.copy(pathrect)

		BeeApp().master.setClipBoardImage(tmpimage)

	def deleteChildren(self):
		num_deleted=0
		win=BeeApp().master.getWindowById(self.windowid)
		for child in self.childItems():
			num_deleted+=1
			child.setParentItem(None)
			win.scene.removeItem(child)

		return num_deleted

	def anchor(self,child):
		win=BeeApp().master.getWindowById(self.windowid)
		win.addAnchorToQueue(self.key,child)
		win.scene.removeItem(child)
		newactive=win.setValidActiveLayer()
		if newactive:
			win.master.updateLayerHighlight(win,newactive)
		win.requestLayerListRefresh()

	def boundingRect(self):
		return qtcore.QRectF(self.getImageRect())

	def getOpacity(self):
		return self.opacity()

	def changeOpacity(self,opacity):
		BeeLayerState.changeOpacity(self,opacity)
		self.setOpacity(opacity)

	def scale(self,newwidth,newheight):
		BeeLayerState.scale(self,newwidth,newheight)
		self.prepareGeometryChange()

	def paint(self,painter,options,widget=None):
		drawrect=options.exposedRect
		self.scene().tmppainter.setCompositionMode(self.compmode)
		self.scene().tmppainter.setOpacity(painter.opacity())
		self.scene().tmppainter.drawImage(drawrect,self.image,drawrect)

	def getConfigWidget(self,winlock=None):
		# can't do this in the constructor because that may occur in a thread other than the GUI thread, this function however should only occur in the GUI thread
		if not self.configwidget:
			self.configwidget=LayerConfigWidget(self.windowid,self.key)
			self.configwidget.setSizePolicy(qtgui.QSizePolicy.MinimumExpanding,qtgui.QSizePolicy.Fixed)
			self.configwidget.ui.background_frame.setSizePolicy(qtgui.QSizePolicy.MinimumExpanding,qtgui.QSizePolicy.MinimumExpanding)
		else:
			self.configwidget.updateValuesFromLayer(winlock)
		return self.configwidget

class LayerFinisher(qtgui.QGraphicsItem):
	""" layers need to be drawn to a temporary image this takes that temporary image and draws it to the scene.  This item should be placed above all other layers, but below any overlays. """
	def __init__(self,rect):
		qtgui.QGraphicsItem.__init__(self)
		self.rect=rect

	def resize(self,newrect):
		self.rect=newrect
		self.prepareGeometryChange()

	def boundingRect(self):
		return self.rect

	def paint(self,painter,options,widget=None):
		self.scene().stopTmpPainter(painter,options.exposedRect)

class SelectedAreaAnimation(qtgui.QGraphicsItemAnimation):
	def __init__(self,item,parent=None):
		qtgui.QGraphicsItemAnimation.__init__(self,parent)
		self.timer=qtcore.QTimeLine(10,self)
		self.timer.setUpdateInterval(100)
		self.timer.setLoopCount(0)
		self.setTimeLine(self.timer)
		self.setItem(item)
		self.timer.start()

	def beforeAnimationStep(self,time):
		self.item().incrementDashOffset()

	def afterAnimationStep(self,time):
		self.item().update()

# This is an animated dashed line displayed to indicate where the current selection is.
class SelectedAreaDisplay(qtgui.QGraphicsItem):
	def __init__(self,path,scene):
		qtgui.QGraphicsItem.__init__(self,None,scene)
		self.rect=scene.sceneRect()
		self.path=path
		self.dashoffset=0
		self.dashpatternlength=8
		self.pathlock=qtcore.QReadWriteLock()

	def incrementDashOffset(self):
		self.dashoffset+=1
		self.dashoffset%=self.dashpatternlength

	def boundingRect(self):
		#lock=qtcore.QReadLocker(self.pathlock)
		return qtcore.QRectF(self.path.boundingRect())

	def updatePath(self,path):
		#lock=qtcore.QWriteLocker(self.pathlock)
		self.path=path
		self.prepareGeometryChange()

	def paint(self,painter,options,widget=None):
		painter.setPen(qtgui.QColor(255,255,255,255))
		painter.drawPath(self.path)

		pen=qtgui.QPen()
		pen.setDashPattern([4,4])
		pen.setDashOffset(self.dashoffset)
		painter.setPen(pen)
		painter.drawPath(self.path)

class FloatingSelection(BeeGuiLayer):
	def __init__(self,image,key,parentlayer):
		BeeGuiLayer.__init__(self,parentlayer.windowid,LayerTypes.floating,key,image,parent=parentlayer)
		self.setFlag(qtgui.QGraphicsItem.ItemIsMovable)
		self.name="Floating selection (%d x %d)" % ( self.image.rect().width(), self.image.rect().height() )

	def paint(self,painter,options,widget=None):
		drawrect=options.exposedRect
		self.scene().tmppainter.save()
		self.scene().tmppainter.translate(self.pos())
		self.scene().tmppainter.setCompositionMode(self.compmode)
		self.scene().tmppainter.setOpacity(painter.opacity())
		self.scene().tmppainter.drawImage(drawrect,self.image,drawrect)
		self.scene().tmppainter.restore()

	# don't allow pasting on other floating selections, go to parent layer instead
	def paste(self,image,x=0,y=0):
		self.parentItem().paste(image,x,y)

	def anchor(self,layer):
		print "WARNING: anchor called from child layer"

	def mousePressEvent(self,event):
		pass
	def mouseMoveEvent(self,event):
		pass
	def mouseReleaseEvent(self,event):
		pass

# widget that we can use to set the options of each layer
class LayerConfigWidget(qtgui.QWidget):
	def __init__(self,windowid,layerkey):
		qtgui.QWidget.__init__(self)

		# save the layer this is suppose to configure
		self.layerkey=layerkey
		self.windowid=windowid

		#setup ui
		self.ui=Ui_LayerConfigWidget()
		self.ui.setupUi(self)

		self.width=self.geometry().width()
		self.height=self.geometry().height()

		# put options in combobox
		for mode in BlendTranslations.getAllModeNames():
			self.ui.blend_mode_box.addItem(mode)

		# without this the frame background is transparent
		self.ui.background_frame.setAutoFillBackground(True)

		# replace layer preview widget with custom widget
		self.ui.layerThumb=LayerPreviewWidget(self.ui.layerThumb,windowid,layerkey)

		self.ui.layerThumb.setAutoFillBackground(True)

		# set initial values according to what the layer has set
		self.updateValuesFromLayer()

	# create a quick instance just to figure out the standard geometry
	def getStandardGeometry():
		testwidget=qtgui.QWidget()
		#setup ui
		testwidget.ui=Ui_LayerConfigWidget()
		testwidget.ui.setupUi(testwidget)

		return testwidget.geometry()

	getStandardGeometry=staticmethod(getStandardGeometry)

	# update the gui to reflect the values of the layer
	def updateValuesFromLayer(self,winlock=None):
		win=BeeApp().master.getWindowById(self.windowid,winlock)
		layer=win.getLayerForKey(self.layerkey)

		if not layer:
			print_debug("WARNING: updateValueFromLayer could not find layer with key %s" % self.layerkey)
			return

		proplock=qtcore.QReadLocker(layer.propertieslock)

		# update visibility box
		self.ui.visibility_box.setChecked(layer.isVisible())

		# update opacity slider
		#self.ui.opacity_box.setValue(layer.opacity())
		self.ui.opacity_slider.setValue(int(layer.opacity()*100))

		# update name
		displayname=layer.name

		if layer.type==LayerTypes.animation:
			displayname+=" (Animation)"
		elif layer.type==LayerTypes.network:
			displayname+=" (Network)"

		self.ui.layer_name_label.setText(displayname)

		# update blend mode box
		self.ui.blend_mode_box.setCurrentIndex(self.ui.blend_mode_box.findText(BlendTranslations.modeToName(layer.compmode)))

		netbuttonstate=False
		netbuttontext=""

		# only need text on the button if it's a network or floating layer
		if win.type==WindowTypes.networkclient:
			if win.ownedByNobody(layer.owner):
				netbuttontext="Claim ownership"
				netbuttonstate=True
			elif win.ownedByMe(layer.owner):
				netbuttontext="Give Up Ownership"
				netbuttonstate=True

		if layer.type==LayerTypes.floating:
			netbuttontext="Anchor On Layer"
			netbuttonstate=True

		# disable controls if client shouldn't be able to control them
		if win.type==WindowTypes.networkclient:
			if win.ownedByMe(layer.owner):
				self.ui.opacity_slider.setEnabled(True)
				self.ui.blend_mode_box.setEnabled(True)
			else:
				self.ui.opacity_slider.setDisabled(True)
				self.ui.blend_mode_box.setDisabled(True)

		self.ui.network_control_button.setText(netbuttontext)
		self.ui.network_control_button.setEnabled(netbuttonstate)

	def refreshThumb(self):
		self.ui.layerThumb.update()

	def highlight(self):
		self.ui.background_frame.setBackgroundRole(qtgui.QPalette.Dark)
		self.refreshThumb()

	def unhighlight(self):
		self.ui.background_frame.setBackgroundRole(qtgui.QPalette.Window)
		self.refreshThumb()

	def on_visibility_box_toggled(self,state):
		layer=BeeApp().master.getLayerById(self.windowid,self.layerkey)
		window=layer.getWindow()
		# change visibility
		layer.setVisible(state)
		# recomposite whole image
		window.reCompositeImage()

	def on_opacity_slider_sliderMoved(self,value):
		# there are two events, one with a float and one with a string, we only need one
		win=BeeApp().master.getWindowById(self.windowid)
		win.addOpacityChangeToQueue(self.layerkey,value/100.)

	def on_opacity_slider_sliderReleased(self):
		win=BeeApp().master.getWindowById(self.windowid)
		win.addOpacityDoneToQueue(self.layerkey)

	def on_blend_mode_box_activated(self,value):
		# we only want the event with the string
		if not type(value) is qtcore.QString:
			return

		newmode=BlendTranslations.nameToMode(value)
		if newmode!=None:
			layer=BeeApp().master.getLayerById(self.windowid,self.layerkey)
			if layer:
				win=layer.getWindow()
				win.addBlendModeChangeToQueue(layer.key,newmode)

	def on_network_control_button_pressed(self):
		layer=BeeApp().master.getLayerById(self.windowid,self.layerkey)
		win=layer.getWindow()

		proplock=qtcore.QReadLocker(layer.propertieslock)

		if layer.type==LayerTypes.floating:
			parent=layer.parentItem()
			parent.anchor(layer)

		# the layer is owned locally so change it to be owned by no one
		elif win.ownedByMe(layer.owner):
			#print_debug("adding give up layer to queue for layer key: %d" % layer.key)
			if len(layer.childItems()):
				result=qtgui.QMessageBox.warning(None,"Floating layers can not be given up","You are attempting to give up ownership of layer that has floting layers, if you continue the floating layers will be destroyed.  To avoid having them destroyed please anchor them or move them to other layers.","Continue","Cancel")
				if result:
					return

			win.addGiveUpLayerToQueue(layer.key)

		# if the layer is owned by nobody then request it
		elif win.ownedByNobody(layer.owner):
			win.addRequestLayerToQueue(layer.key)

	def mousePressEvent(self,event):
		layer=BeeApp().master.getLayerById(self.windowid,self.layerkey)
		win=BeeApp().master.getWindowById(self.windowid)
		if layer:
			if win.type==WindowTypes.networkclient:
				if win.ownedByMe(layer.owner) or layer.type==LayerTypes.floating:
					win.setActiveLayer(layer.key)
			else:
				win.setActiveLayer(layer.key)

class BeeLayersWindow(qtgui.QMainWindow):
	def __init__(self,master):
		qtgui.QMainWindow.__init__(self)

		self.master=master
		#self.mutex=qtcore.QMutex()

		#setup ui
		self.ui=Ui_LayersWindow()
		self.ui.setupUi(self)
		self.show()

		layersListArea=qtgui.QScrollArea(self.ui.layersListArea.parentWidget())
		layout=self.ui.layersListArea.parentWidget().layout()

		# setup new scroll area options
		layersListArea.setGeometry(self.ui.layersListArea.geometry())
		layersListArea.setSizePolicy(self.ui.layersListArea.sizePolicy())
		layersListArea.setObjectName(self.ui.layersListArea.objectName())
		layersListArea.setVerticalScrollBarPolicy(qtcore.Qt.ScrollBarAlwaysOn)
		layersListArea.setHorizontalScrollBarPolicy(qtcore.Qt.ScrollBarAlwaysOff)

		scrollareawidth=LayerConfigWidget.getStandardGeometry().width()
		#layersListArea.setFixedWidth(scrollareawidth)
		layersListArea.setMinimumWidth(scrollareawidth+15)
		layersListArea.setSizePolicy(qtgui.QSizePolicy.MinimumExpanding,qtgui.QSizePolicy.MinimumExpanding)

		# remove widget that I'm replacing in the layout
		index=layout.indexOf(self.ui.layersListArea)
		layout.removeWidget(self.ui.layersListArea)

		# replace widget with custom scroll area widget
		self.ui.layersListArea=layersListArea
		layout.insertWidget(index,layersListArea)

		# add frame to scrolled area
		frame=qtgui.QFrame(layersListArea)
		layersListArea.setWidget(frame)
		#frame.setSizePolicy(qtgui.QSizePolicy.MinimumExpanding,qtgui.QSizePolicy.MinimumExpanding)

		# add layout to frame inside the scroll area
		vbox=qtgui.QVBoxLayout()
		frame.setLayout(vbox)

		self.layersListArea=layersListArea

	# rebuild layers window by removing all the layers widgets and then adding them back in order
	def refreshLayersList(self,win,curlayerkey,winlock=None):
		""" Update the list of layers displayed in the layers display window, if passed none for the layers arguement, the list of layers is cleared
		"""
		if not winlock:
			winlock=qtcore.QReadLocker(self.master.drawingwindowslock)

		frame=self.layersListArea.widget()

		vbox=frame.layout()

		# remove widgets from layout
		for widget in frame.children():
			# skip items of wrong type
			if not type(widget) is LayerConfigWidget:
				continue
			widget.setParent(None)
			vbox.removeWidget(widget)

		# make sure the window has not be unregistered already
		if not self.master.isWindowRegistered(win,winlock):
			return

		newwidget=None

		# ask each layer for it's widget and add it
		for layer in reversed(win.layers):
			for floating in layer.childItems():
				newwidget=floating.getConfigWidget(winlock)
				vbox.addWidget(newwidget)
				newwidget.show()

			newwidget=layer.getConfigWidget(winlock)
			if layer.key==curlayerkey:
				newwidget.highlight()
			else:
				newwidget.unhighlight()
			vbox.addWidget(newwidget)
			newwidget.show()

		if newwidget:
			frame.setGeometry(qtcore.QRect(0,0,newwidget.width,newwidget.height*vbox.count()))
		else:
			frame.setGeometry(qtcore.QRect(0,0,0,0))

	# set proper highlight for layer with passed key
	def refreshLayerHighlight(self,win,key,lock=None):
		frame=self.layersListArea.widget()

		if not lock:
			lock=qtcore.QMutexLocker(win.curlayerkeymutex)

		winkey=win.getCurLayerKey(lock)

		# go through all the children of the frame
		# this seems like a hackish way to do things, but I've yet to find better and speed is not all that vital here
		for widget in frame.children():
			# skip items of wrong type
			if not type(widget) is LayerConfigWidget:
				continue

			if key==widget.layerkey:
				if key==winkey:
					widget.highlight()
					return
				else:
					widget.unhighlight()
					return

	def refreshLayerThumb(self,key=None):
		#lock=qtcore.QMutexLocker(self.mutex)
		vbox=self.layersListArea.widget().layout()
		for item in range(vbox.count()):
			widget=vbox.itemAt(item).widget()
			k=widget.layerkey
			if key==k or key==None:
				widget.refreshThumb()

	def on_new_layer_button_clicked(self,accept=True):
		if accept:
			if self.master.curwindow:
				self.master.curwindow.addLayer()

	def on_delete_layer_button_clicked(self,accept=True):
		if accept:
			if self.master.curwindow:
				self.master.curwindow.addRemoveLayerRequestToQueue(self.master.curwindow.getCurLayerKey())

	def on_layer_up_button_clicked(self,accept=True):
		if accept:
			if self.master.curwindow:
				self.master.curwindow.layerUpPushed()
				#self.master.curwindow.addLayerUpToQueue(self.master.curwindow.getCurLayerKey())

	def on_layer_down_button_clicked(self,accept=True):
		if accept:
			if self.master.curwindow:
				self.master.curwindow.layerDownPushed()
				#self.master.curwindow.addLayerDownToQueue(self.master.curwindow.getCurLayerKey())

	def hideEvent(self,event):
		if not self.isMinimized():
			self.master.uncheckWindowLayerBox()
		return qtgui.QWidget.hideEvent(self,event)

# custom widget for the thumbnail view of a layer
class LayerPreviewWidget(qtgui.QWidget):
	def __init__(self,replacingwidget,windowid,layerkey):
		qtgui.QWidget.__init__(self,replacingwidget.parentWidget())

		self.setGeometry(replacingwidget.frameGeometry())
		self.setObjectName(replacingwidget.objectName())

		self.windowid=windowid
		self.layerkey=layerkey
		self.show()

	# repaint preview for layer, I want to keep this in the same aspect ratio as the layer
	def paintEvent(self,event):
		layer=BeeApp().master.getLayerById(self.windowid,self.layerkey)
		# just to make sure nothing goes wrong
		if not layer:
			return

		window=BeeApp().master.getWindowById(self.windowid)
		# get how much we need to scale down both dimensions
		maximagedimension=max(layer.image.width(),layer.image.height())
		if maximagedimension==0:
			return
		scalefactor=self.width()/float(maximagedimension)

		# get dimensions of the image if we keep the aspect ratio and put it in the preview widget
		scalewidth=layer.image.width()*scalefactor
		scaleheight=layer.image.height()*scalefactor
		xoffset=(self.width()-scalewidth)/2
		yoffset=(self.height()-scaleheight)/2

		scaledimage=qtcore.QRectF(xoffset,yoffset,scalewidth,scaleheight)

		backdrop=qtgui.QImage(scalewidth,scaleheight,qtgui.QImage.Format_ARGB32_Premultiplied)
		backdrop.fill(window.backdropcolor)
		painter=qtgui.QPainter()
		painter.begin(self)
		painter.drawImage(scaledimage,backdrop)
		# have preview reflect the opacity of the layer
		painter.setOpacity(layer.getOpacity())
		painter.drawImage(scaledimage,layer.image,qtcore.QRectF(layer.image.rect()))
		painter.end()
