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

class BeeLayerState:
	def __init__(self,windowid,type,key,image=None,opacity=None,visible=None,compmode=None,owner=0):
		self.windowid=windowid
		self.key=key
		self.owner=owner

		win=BeeApp().master.getWindowById(windowid)

		#print "creating layer with key:", key
		#print "creating layer with owner:", owner
		# this is a lock for locking access to the layer image when needed
		self.imagelock=qtcore.QReadWriteLock()
		self.propertieslock=qtcore.QReadWriteLock()

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

		self.opacity=opacity
		self.visible=visible
		self.compmode=compmode

		self.configwidget=None

		# set default name for layer
		self.changeName("Layer %d" % key)

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

	# composite image onto layer from center coord
	def compositeFromCenter(self,image,x,y,compmode,clippath=None):
		x=int(x)
		y=int(y)
		#print "calling compositeFromCenter with args:",x,y
		width=image.size().width()
		height=image.size().height()
		#print "image dimensions:", width, height
		self.compositeFromCorner(image,x-int((width)/2),y-int((height)/2),compmode,clippath)
		return

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

	def getConfigWidget(self):
		# can't do this in the constructor because that may occur in a thread other than the main thread, this function however should only occur in the main thread
		if not self.configwidget:
			self.configwidget=LayerConfigWidget(self.windowid,self.key)
			self.configwidget.setSizePolicy(qtgui.QSizePolicy.MinimumExpanding,qtgui.QSizePolicy.Fixed)
			self.configwidget.ui.background_frame.setSizePolicy(qtgui.QSizePolicy.MinimumExpanding,qtgui.QSizePolicy.MinimumExpanding)
		else:
			self.configwidget.updateValuesFromLayer()
		return self.configwidget

	# get color of pixel at specified point, or average color in range
	def getPixelColor(self,x,y,size):
		lock=qtcore.QReadLocker(self.imagelock)
		return self.image.pixel(x,y)

	# return copy of image
	def getImageCopy(self):
		lock=qtcore.QReadLocker(self.imagelock)
		retimage=self.image.copy()
		return retimage

	#def cutImage(self):
	#	selection=win.getClipPathCopy()

	# composite section of layer onto paint object passed
	def compositeLayerOn(self,painter,dirtyrect):
		# if layer is not visible just return
		if not self.visible:
			return

		proplock=qtcore.QReadLocker(self.propertieslock)

		painter.setOpacity(self.opacity)
		painter.setCompositionMode(self.compmode)

		lock=ReadWriteLocker(self.imagelock,True)

		painter.drawImage(dirtyrect,self.image,dirtyrect)

	# set any passed layer options
	def setOptions(self,opacity=None,visibility=None,compmode=None):
		proplock=qtcore.QWriteLocker(self.propertieslock)

		if opacity!=None:
			self.opacity=opacity

		if visibility!=None:
			self.visibility=visibility

		if compmode!=None:
			self.compmode=compmode

		proplock.unlock()

		if self.configwidget:
			self.configwidget.updateValuesFromLayer()

		BeeApp().master.getWindowById(self.windowid).reCompositeImage()

	def adjustCanvasSize(self,leftadj,topadj,rightadj,bottomadj):
		lock=ReadWriteLocker(self.imagelock,True)

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

	# shift image by specified x and y
	#def shiftImage(self,x,y):

class BeeGuiLayer(BeeLayerState,qtgui.QGraphicsItem):
	def __init__(self,windowid,type,key,image=None,opacity=None,visible=None,compmode=None,owner=0):
		BeeLayerState.__init__(self,windowid,type,key,image,opacity,visible,compmode,owner)
		qtgui.QGraphicsItem.__init__(self)
		self.setFlag(qtgui.QGraphicsItem.ItemUsesExtendedStyleOption)

	def boundingRect(self):
		return qtcore.QRectF(self.image.rect())

	def paint(self,painter,options,widget=None):
		drawrect=options.exposedRect
		self.scene().tmppainter.drawImage(drawrect,self.image,drawrect)

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

class SelectedAreaDisplay(qtgui.QGraphicsItem):
	def __init__(self,path,scene):
		qtgui.QGraphicsItem.__init__(self,None,scene)
		self.rect=scene.sceneRect()
		self.path=path
		self.dashoffset=0
		self.dashpatternlength=8

	def incrementDashOffset(self):
		self.dashoffset+=1
		self.dashoffset%=self.dashpatternlength

	def boundingRect(self):
		return self.rect

	def updatePath(self,path):
		self.path=path

	def paint(self,painter,options,widget=None):
		self.scene().stopTmpPainter(painter,options.exposedRect)

		painter.setPen(qtgui.QColor(255,255,255,255))
		painter.drawPath(self.path)

		pen=qtgui.QPen()
		pen.setDashPattern([4,4])
		pen.setDashOffset(self.dashoffset)
		painter.setPen(pen)
		painter.drawPath(self.path)

class FloatingSelection(BeeGuiLayer):
	def __init__(self,image,parentlayer):
		self.key=BeeApp().master.getNextLayerKey()
		self.image=image

	# paste the selection on it's layer
	#def anchor(self,layer):

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
	def updateValuesFromLayer(self):
		layer=BeeApp().master.getLayerById(self.windowid,self.layerkey)
		win=BeeApp().master.getWindowById(self.windowid)

		if not layer:
			print_debug("WARNING: updateValueFromLayer could not find layer with key %s" % self.layerkey)
			return

		proplock=qtcore.QReadLocker(layer.propertieslock)

		# update visibility box
		self.ui.visibility_box.setChecked(layer.visible)

		# update opacity value
		self.ui.opacity_box.setValue(layer.opacity)

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

		# only need text on the button if it's a network layer
		if win.type==WindowTypes.networkclient:
			if win.ownedByNobody(layer.owner):
				netbuttontext="Claim ownership"
				netbuttonstate=True
			elif win.ownedByMe(layer.owner):
				netbuttontext="Give Up Ownership"
				netbuttonstate=True

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
		layer.visible=state
		# recomposite whole image
		window.reCompositeImage()

	def on_opacity_box_valueChanged(self,value):
		# there are two events, one with a flota and one with a string, we only need one
		if type(value) is float:
			layer=BeeApp().master.getLayerById(self.windowid,self.layerkey)
			layer.window.addOpacityChangeToQueue(layer.key,value)

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

		# the layer is owned locally so change it to be owned by no one
		if win.ownedByMe(layer.owner):
			#print_debug("adding give up layer to queue for layer key: %d" % layer.key)
			win.addGiveUpLayerToQueue(layer.key)

		# if the layer is owned by nobody then request it
		if win.ownedByNobody(layer.owner):
			win.addRequestLayerToQueue(layer.key)

	def mousePressEvent(self,event):
		layer=BeeApp().master.getLayerById(self.windowid,self.layerkey)
		if layer:
			window=layer.getWindow()
			window.setActiveLayer(layer.key)

class BeeLayersWindow(qtgui.QMainWindow):
	def __init__(self,master):
		qtgui.QMainWindow.__init__(self)

		self.master=master
		self.mutex=qtcore.QMutex()

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
	def refreshLayersList(self,layers,curlayerkey):
		""" Update the list of layers displayed in the layers display window, if passed none for the layers arguement, the list of layers is cleared
		"""
		lock=qtcore.QMutexLocker(self.mutex)

		frame=self.layersListArea.widget()

		vbox=frame.layout()

		# remove widgets from layout
		for widget in frame.children():
			# skip items of wrong type
			if not type(widget) is LayerConfigWidget:
				continue
			widget.setParent(None)
			vbox.removeWidget(widget)

		newwidget=None

		if not layers:
			return

		# ask each layer for it's widget and add it
		for layer in reversed(layers):
			newwidget=layer.getConfigWidget()
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

		return

	# set proper highlight for layer with passed key
	def refreshLayerHighlight(self,key):
		lock=qtcore.QMutexLocker(self.mutex)
		frame=self.layersListArea.widget()
		# go through all the children of the frame
		# this seems like a hackish way to do things, but I've yet to find better and speed is not all that vital here
		for widget in frame.children():
			# skip items of wrong type
			if not type(widget) is LayerConfigWidget:
				continue

			if key==widget.layerkey:
				if key==self.master.curwindow.curlayerkey:
					widget.highlight()
					return
				else:
					widget.unhighlight()
					return

	def refreshLayerThumb(self,key=None):
		lock=qtcore.QMutexLocker(self.mutex)
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
				self.master.curwindow.addRemoveLayerRequestToQueue(self.master.curwindow.curlayerkey)

	def on_layer_up_button_clicked(self,accept=True):
		if accept:
			if self.master.curwindow:
				self.master.curwindow.addLayerUpToQueue(self.master.curwindow.curlayerkey)

	def on_layer_down_button_clicked(self,accept=True):
		if accept:
			if self.master.curwindow:
				self.master.curwindow.addLayerDownToQueue(self.master.curwindow.curlayerkey)

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

		self.mutex=qtcore.QMutex()

	# repaint preview for layer, I want to keep this in the same aspect ratio as the layer
	def paintEvent(self,event):
		layer=BeeApp().master.getLayerById(self.windowid,self.layerkey)
		# just to make sure nothing goes wrong
		if not layer:
			return

		window=BeeApp().master.getWindowById(self.windowid)
		lock=qtcore.QMutexLocker(self.mutex)
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
		painter.drawImage(scaledimage,layer.image,qtcore.QRectF(layer.image.rect()))
		painter.end()
