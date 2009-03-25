# append designer dir to search path
import sys
sys.path.append("designer")

from beetypes import *

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui

from beeutil import *

from LayerWidgetUi import Ui_LayerConfigWidget
from LayersWindowUi import Ui_LayersWindow
import beemaster

class BeeLayer:
	def __init__(self,windowid,type,key,image=None,opacity=None,visible=None,compmode=None,owner=0):
		self.windowid=windowid
		self.key=key
		self.owner=owner

		win=beemaster.BeeMasterWindow().getWindowById(windowid)

		#print "creating layer with key:", key
		#print "creating layer with owner:", owner
		# this is a lock for locking access to the layer image when needed
		self.imagelock=qtcore.QReadWriteLock()

		self.type=type

		# for floting selections and temporary overlays for tools and such
		self.tooloverlay=None

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

	def getWindow(self):
		return beemaster.BeeMasterWindow().getWindowById(self.windowid)

	# this will set things up to be pickled
	def __getstate__(self):
		state=self.__dict__.copy()
		# mutex objects can't be pickled
		del state["mutex"]
		# don't pickle window with each layer
		del state["window"]
		return state

	# this will get things back from being pickled
	def __setstate__(self,state):
		self.__dict__.update(state)
		# make new mutex
		self.mutex=QMutex()

	def changeName(self,newname):
		#print "setting layer name to:", newname
		if self.type==LayerTypes.animation:
			newname+=" (Animation)"
		elif self.type==LayerTypes.network:
			newname+=" (Network)"
		self.name=newname

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
	def compositeFromCorner(self,image,x,y,compmode,clippath=None):
		x=int(x)
		y=int(y)
		#print "calling compositeFromCorner with args:",x,y
		lock=ReadWriteLocker(self.imagelock,True)
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
		win=beemaster.BeeMasterWindow().getWindowById(self.windowid)
		dirtyregion=dirtyregion.intersect(qtgui.QRegion(win.image.rect()))
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
		lock=ReadWriteLocker(self.imagelock,False)
		return self.image.pixel(x,y)

	# return copy of image
	def getImageCopy(self):
		retimage=self.image.copy()
		return retimage

	# composite section of layer onto paint object passed
	def compositeLayerOn(self,painter,dirtyrect):
		# if layer is not visible just return
		if not self.visible:
			return

		painter.setOpacity(self.opacity)
		painter.setCompositionMode(self.compmode)

		lock=ReadWriteLocker(self.imagelock,True)

		# if we have overlays, make a temporary image that with the overlays composited on it and composite that on the paint object
		if self.tooloverlay:
			tmpimage=self.image.copy(dirtyrect)
			tmprect=tmpimage.rect()
			tmppainter=qtgui.QPainter()
			tmppainter.begin(tmpimage)
			tmppainter.drawImage(tmprect,tooloverlay,dirtyrect)
			tmppainter.end()

			painter.drawImage(dirtyrect,tmpimage)

		# if there are no overlays we can do this far more optimized method way
		else:
			painter.drawImage(dirtyrect,self.image,dirtyrect)

	# set any passed layer options
	def setOptions(self,opacity=None,visibility=None,compmode=None):
		if opacity!=None:
			self.opacity=opacity

		if visibility!=None:
			self.visibility=visibility

		if compmode!=None:
			self.compmode=compmode

		if self.configwidget:
			self.configwidget.updateValuesFromLayer()

		beemaster.BeeMasterWindow().getWindowById(self.windowid).reCompositeImage()

	def adjustCanvasSize(self,leftadj,topadj,rightadj,bottomadj):
		lock=ReadWriteLocker(self.imagelock,True)

		win=beemaster.BeeMasterWindow().getWindowById(self.windowid)
		newimage=qtgui.QImage(win.docwidth,win.docheight,qtgui.QImage.Format_ARGB32_Premultiplied)
		newimage.fill(0)

		oldimagerect=self.image.rect()
		newimagerect=newimage.rect()
		srcRect=oldimagerect
		targetRect=qtcore.QRect(srcRect)
		targetRect.adjust(leftadj,topadj,leftadj,topadj)

		painter=qtgui.QPainter()
		painter.begin(newimage)
		painter.drawImage(targetRect,self.image,srcRect)
		painter.end()

		self.image=newimage

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
		layer=beemaster.BeeMasterWindow().getLayerById(self.windowid,self.layerkey)
		# update visibility box
		self.ui.visibility_box.setChecked(layer.visible)

		# update opacity value
		self.ui.opacity_box.setValue(layer.opacity)

		# update name
		self.ui.layer_name_label.setText(layer.name)

		# update blend mode box
		self.ui.blend_mode_box.setCurrentIndex(self.ui.blend_mode_box.findText(BlendTranslations.modeToName(layer.compmode)))

	def refreshThumb(self):
		self.ui.layerThumb.update()

	def highlight(self):
		self.ui.background_frame.setBackgroundRole(qtgui.QPalette.Dark)
		self.refreshThumb()

	def unhighlight(self):
		self.ui.background_frame.setBackgroundRole(qtgui.QPalette.Window)
		self.refreshThumb()

	def on_visibility_box_toggled(self,state):
		layer=beemaster.BeeMasterWindow().getLayerById(self.windowid,self.layerkey)
		# change visibility
		layer.visible=state
		# recomposite whole image
		layer.window.reCompositeImage()

	def on_opacity_box_valueChanged(self,value):
		# there are two events, one with a flota and one with a string, we only need one
		if type(value) is float:
			layer=beemaster.BeeMasterWindow().getLayerById(self.windowid,self.layerkey)
			layer.window.addOpacityChangeToQueue(layer.key,value)

	def on_blend_mode_box_activated(self,value):
		# we only want the event with the string
		if not type(value) is qtcore.QString:
			return

		newmode=BlendTranslations.nameToMode(value)
		if newmode!=None:
			layer=beemaster.BeeMasterWindow().getLayerById(self.windowid,self.layerkey)
			layer.window.addBlendModeChangeToQueue(layer.key,newmode)

	def mousePressEvent(self,event):
		layer=beemaster.BeeMasterWindow().getLayerById(self.windowid,self.layerkey)
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
	def refreshLayersList_backup(self,layers,curlayerkey):
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

		# ask each layer for it's widget and add it
		for layer in layers:
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

		# go through all items setting vertical offset higher each time
		item = 0
		for widget in frame.children():
			# skip items of wrong type
			if not type(widget) is LayerConfigWidget:
				continue
			widget.setGeometry(0,(vbox.count()-item-1)*widget.height,widget.width,widget.height)
			widget.show()
			item+=1

	# rebuild layers window by removing all the layers widgets and then adding them back in order
	def refreshLayersList(self,layers,curlayerkey):
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
		# go through all items setting vertical offset higher each time
		item = 0
		for widget in frame.children():
			# skip items of wrong type
			if not type(widget) is LayerConfigWidget:
				continue
			widget.setGeometry(0,(vbox.count()-item-1)*widget.height,widget.width,widget.height)
			widget.show()
			item+=1

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

	#def hideEvent(self,event):
	#	self.master.ui.actionLayers.setChecked(False)
	#	return False

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
		layer=beemaster.BeeMasterWindow().getLayerById(self.windowid,self.layerkey)
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
		lock=qtcore.QMutexLocker(self.mutex)
		# get how much we need to scale down both dimensions
		scalefactor=self.width()/float(max(layer.image.width(),layer.image.height()))

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
