import sys
sys.path.append("designer")

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui

import os
import cPickle as pickle

from beetypes import *
from beeview import BeeViewScrollArea
from beelayer import BeeLayer
from beeutil import *
from beeeventstack import *
from datetime import datetime
from sketchlog import SketchLogWriter
from beeglobals import *

from Queue import Queue
from drawingthread import DrawingThread

from DrawingWindowUI import Ui_DrawingWindowSpec
from ImageSizeAdjustDialogUi import Ui_CanvasSizeDialog
from ImageScaleDialog import Ui_CanvasScaleDialog

from animation import *

class BeeDrawingWindow(qtgui.QMainWindow):
	def __init__(self,master,width=600,height=400,startlayer=True,type=WindowTypes.singleuser,host="localhost",port=8333):
		qtgui.QMainWindow.__init__(self,master)
		# save passed values
		self.master=master
		self.docwidth=width
		self.docheight=height
		self.type=type

		# initialize values
		self.zoom=1.0
		self.log=None
		self.localcommandstack=CommandStack(self)
		self.remotecommandstacks={}
		self.ui=Ui_DrawingWindowSpec()
		self.ui.setupUi(self)
		self.curlayerkey=None
		self.activated=False
		self.backdrop=None

		self.nextlayerkey=0
		self.nextlayerkeymutex=qtcore.QMutex()

		self.cursoroverlay=None
		self.remoteid=None

		self.selection=[]
		self.selectionoutline=[]
		self.clippath=None

		self.localcommandqueue=Queue(0)
		self.remotecommandqueue=Queue(0)
		self.remoteoutputqueue=Queue(0)

		# initiate drawing thread
		if type==WindowTypes.standaloneserver:
			self.localdrawingthread=DrawingThread(self.remotecommandqueue,self,type=ThreadTypes.server)
		else:
			self.localdrawingthread=DrawingThread(self.localcommandqueue,self)

		self.localdrawingthread.start()

		self.remotedrawingthread=None
		self.remoteid=0

		# for sending events to server so they don't slow us down locally
		self.sendtoserverqueue=None
		self.sendtoserverthread=None

		self.serverreadingthread=None

		self.layers=[]
		self.layersmutex=qtcore.QMutex()

		self.image=qtgui.QImage(width,height,qtgui.QImage.Format_ARGB32_Premultiplied)
		self.imagelock=qtcore.QReadWriteLock()

		# replace widget with my custom class widget
		self.ui.PictureViewWidget=BeeViewScrollArea(self.ui.PictureViewWidget,self)
		self.view=self.ui.PictureViewWidget
		self.resizeViewToWindow()
		self.view.setCursor(master.getCurToolDesc().getCursor())

		if type!=WindowTypes.standaloneserver:
			self.show()

		# create a backdrop to be put at the bottom of all the layers
		self.recreateBackdrop()

		# put in starting blank layer if needed
		# don't go through the queue for this layer add because we need it to
		# be done before the next step
		if startlayer:
			self.insertLayer(self.nextLayerKey(),0,LayerTypes.user)

		# have window get destroyed when it gets a close event
		self.setAttribute(qtcore.Qt.WA_DeleteOnClose)

	# alternate constructor for serving a network session
	def startNetworkServer(parent,port="8333"):
		newwin=BeeDrawingWindow(parent)
		return newwin

	# make method static
	startNetworkServer=staticmethod(startNetworkServer)

	# alternate constructor for joining a network session
	def startNetworkWindow(parent,username,password,host="localhost",port="8333"):
		print "running startNetworkWindow"
		newwin=BeeDrawingWindow(parent,startlayer=False,type=WindowTypes.networkclient)

		newwin.username=username
		newwin.password=password
		newwin.host=host
		newwin.port=port

		return newwin

	# make method static
	startNetworkWindow=staticmethod(startNetworkWindow)

	# alternate constructor for starting an animation playback
	def newAnimationWindow(master,filename):
		newwin=BeeDrawingWindow(master,600,400,False,WindowTypes.animation)
		newwin.animationthread=PlayBackAnimation(newwin,filename)
		return newwin

	# make method static
	newAnimationWindow=staticmethod(newAnimationWindow)

	# return false if the layer id passed is owned another client in a network session and true otherwise, should always return true if there is no network session
	def ownedByMe(self,owner):
		if owner==0:
			return True
		if owner==self.remoteid:
			return True
		return False

	# add an event to the undo/redo history
	def addCommandToHistory(self,command,source=0):
		# if we don't get a source then assume that it's local
		if source==0:
			self.localcommandstack.add(command)
		# else add it to proper remote command stack, add stack if needed
		elif self.remotecommandstack.has_key(source):
			self.remotecommandstack[source].addCommand(command)
		else:
			self.remotecommandstack[source]=CommandStack(self)
			self.remotecommandstack[source].addCommand(command)

  # undo last event in stack for passed client id
	def undo(self,source=0):
		# if we don't get a source then assume that it's local, need to implement what it does if it's remote
		if source==0:
			self.localcommandstack.undo()

  # redo last event in stack for passed client id
	def redo(self,source=0):
		# if we don't get a source then assume that it's local
		if source==0:
			self.localcommandstack.redo()

  # update the clipping path to match the current selection
	def updateClipPath(self):
		if not self.selection:
			self.clippath=None
			return

		self.clippath=qtgui.QPainterPath()
		for select in self.selection:
			self.clippath.addPath(select)

	# change the current selection path
	def changeSelection(self,type,newarea=None):
		if not self.cursoroverlay and not newarea:
			return

		if not newarea:
			newarea=qtgui.QPainterPath(self.cursoroverlay.path)

		# if we get a clear operation clear the seleciton and outline then return
		if type==SelectionModTypes.clear:
			self.selection=[]
			self.selectionoutline=[]
			return

		elif type==SelectionModTypes.new or len(self.selection)==0:
			self.selection=[newarea]

		elif type==SelectionModTypes.add:
			newselect=[]
			for select in self.selection:
				# the new area completely contains this path so just ignore it
				if newarea.contains(select):
					pass
				elif select.contains(newarea):
					newarea=newarea.united(select)
				# if they intersect union the areas
				elif newarea.intersects(select):
					newarea=newarea.united(select)
				# otherwise they are completely disjoint so just add it separately
				else:
					newselect.append(select)

			# finally add in new select and update selection
			newselect.append(newarea)
			self.selection=newselect

		elif type==SelectionModTypes.subtract:
			newselect=[]
			for select in self.selection:
				# the new area completely contains this path so just ignore it
				if newarea.contains(select):
					pass
				# if they intersect subtract the areas and add to path
				elif newarea.intersects(select) or select.contains(newarea):
					select=select.subtracted(newarea)
					newselect.append(select)
				# otherwise they are completely disjoint so just add it separately
				else:
					newselect.append(select)

			self.selection=newselect

		elif type==SelectionModTypes.intersect:
			newselect=[]
			for select in self.selection:
				tmpselect=select.intersected(newarea)
				if not tmpselect.isEmpty():
					newselect.append(tmpselect)

			self.selection=newselect

		else:
			print "unrecognized selection modification type"

		self.updateClipPath()
		# make sure the selection is not the whole image

		# now change the selecition outline
		#self.selectionoutline=self.selection.toFillPolygons()

	# thread safe function to return a layer key number that hasn't been returned before
	def nextLayerKey(self):
		# get a lock so we don't get a collision ever
		lock=qtcore.QMutexLocker(self.nextlayerkeymutex)

		key=self.nextlayerkey
		self.nextlayerkey+=1
		return key

	def addRemoveLayerRequestToQueue(self,key,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.deletelayer,key),source)

	def queueCommand(self,command,source=ThreadTypes.user,owner=0):
		#print "queueing command:", command
		if source==ThreadTypes.user:
			#print "putting command in local queue"
			self.localcommandqueue.put(command)
		elif source==ThreadTypes.server:
			#print "putting command in routing queue"
			self.master.routinginput.put((command,owner))
		else:
			#print "putting command in remote queue"
			self.remotecommandqueue.put(command)

	# remove layer, but don't add it to history
	def removeLayerByKey(self,key,history=0):
		# get a lock so we don't get a collision ever
		lock=qtcore.QMutexLocker(self.layersmutex)
		
		layer=self.getLayerForKey(key)
		if(layer):
			index=self.layers.index(layer)
			if history!=-1:
				self.addCommandToHistory(DelLayerCommand(layer,index))
			self.layers.pop(index)

			# try to set current layer to a valid layer
			if index==0:
				if len(self.layers) == 0:
					self.curlayerkey=None
				else:
					self.curlayerkey=self.layers[index].key
			else:
				self.curlayerkey=self.layers[index-1].key

			self.requestLayerListRefresh()
			self.reCompositeImage()
			return (layer,index)

		return (None,None)

	def addLayerDownToQueue(self,key,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.layerdown,key),source)

	def layerDown(self,key):
		index=self.getLayerIndexForKey(key)
		if index>0:
			self.layers[index],self.layers[index-1]=self.layers[index-1],self.layers[index]
			self.reCompositeImage()
			self.requestLayerListRefresh()

			# if we are only running locally add command to local history
			# otherwise do nothing
			if self.type==WindowTypes.singleuser:
				self.addCommandToHistory(LayerDownCommand(key))

	def addLayerUpToQueue(self,key,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.layerup,key),source)

  # send event to GUI to update the list of current layers
	def requestLayerListRefresh(self):
		event=qtcore.QEvent(BeeCustomEventTypes.refreshlayerslist)
		self.master.app.postEvent(self.master,event)

	def layerUp(self,key):
		index=self.getLayerIndexForKey(key)
		if index<len(self.layers)-1:
			self.layers[index],self.layers[index+1]=self.layers[index+1],self.layers[index]
			self.reCompositeImage()
			self.requestLayerListRefresh()

			# if we are only running locally add command to local history
			# otherwise do nothing
			if self.type==WindowTypes.singleuser:
				self.addCommandToHistory(LayerUpCommand(key))

	# recomposite all layers together into the displayed image
	# when a thread calls this method it shouldn't have a lock on any layers
	def reCompositeImage(self,dirtyrect=None):
		# if we get a none for the dirty area do the whole thing
		if not dirtyrect:
			drawrect=self.image.rect()
		else:
			drawrect=dirtyrect

		# lock the image for writing
		imagelocker=ReadWriteLocker(self.imagelock,True)

		# first draw in the backdrop
		painter=qtgui.QPainter()
		painter.begin(self.image)

		if not self.backdrop:
			self.recreateBackdrop()

		painter.drawImage(drawrect,self.backdrop,drawrect)

		# then over it add all the layers
		for layer in self.layers:
			layer.compositeLayerOn(painter,drawrect)

		painter.end()

		# unlock the image
		imagelocker.unlock()

		if dirtyrect:
			self.view.updateView(dirtyrect)
		else:
			self.view.updateView()

	# handle a few events that don't have easy function over loading front ends
	def event(self,event):
		# when the window is resized change the view to match
		if event.type()==qtcore.QEvent.Resize:
			self.resizeViewToWindow()
		# do the last part of setup when the window is done being created
		elif event.type()==qtcore.QEvent.WindowActivate:
			if self.activated==False:
				self.activated=True
				self.reCompositeImage()
				if self.type==WindowTypes.singleuser:
					self.remotedrawingthread=None
				elif self.type==WindowTypes.animation:
					self.remotedrawingthread=DrawingThread(self.remotecommandqueue,self,ThreadTypes.animation)
					self.remotedrawingthread.start()
				elif self.type==WindowTypes.networkclient:
					self.startNetworkThreads(self.username,self.password,self.host,self.port)
					self.remotedrawingthread=DrawingThread(self.remotecommandqueue,self,ThreadTypes.network)
					self.remotedrawingthread.start()
				else:
					self.remotedrawingthread=DrawingThread(self.remotecommandqueue,self,ThreadTypes.network)
					self.remotedrawingthread.start()
			self.master.takeFocus(self)

		return False

# get the current layer key and make sure it is valid, if it is not valid then set it to something valid if there are any layers
	def getCurLayerKey(self):
		if self.layers:
			if self.getLayerForKey(self.curlayerkey):
				return self.curlayerkey
			self.curlayerkey=self.layers[0].key
			return self.curlayerkey
		return None

	def penDown(self,x,y,pressure):
		self.curtool=self.master.getCurToolInst(self)
		self.curtool.penDown(x,y,pressure)

	def addPenDownToQueue(self,x,y,pressure,layerkey=None,tool=None,source=ThreadTypes.user):
		if not tool:
			tool=self.master.getCurToolInst(self)
			self.curtool=tool

		if layerkey==None:
			layerkey=self.getCurLayerKey()

		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.pendown,layerkey,x,y,pressure,tool),source)

	def penMotion(self,x,y,pressure):
		self.curtool.penMotion(x,y,pressure)

	def addPenMotionToQueue(self,x,y,pressure,layerkey=None,source=ThreadTypes.user):
		if layerkey==None:
			layerkey=self.curlayerkey

		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.penmotion,layerkey,x,y,pressure),source)

	def penUp(self,x,y,source=0):
		self.curtool.penUp(x,y,source)

	def addPenUpToQueue(self,x,y,layerkey=None,source=ThreadTypes.user):
		if not layerkey:
			layerkey=self.curlayerkey

		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.penup,self.curlayerkey,x,y),source)

	# not sure how useful these will be, but just in case a tool wants to do something special when it leaves the drawable area they are here
	def penEnter(self):
		self.curtool.penEnter()

	def penLeave(self):
		self.curtool.penLeave()

	def getLayerForKey(self,key):
		for layer in self.layers:
			if layer.key==key:
				return layer
		print "WARNING: could not find layer for key", key
		return None

	def getLayerIndexForKey(self,key):
		for index in range(len(self.layers)):
			if self.layers[index].key==key:
				return index
		print "WARNING: could not find layer for key", key
		return None

	def resizeViewToWindow(self):
		cw=self.ui.centralwidget
		geo=cw.geometry()
		mbgeo=self.ui.menubar.geometry()

		x=geo.x()
		y=geo.y()
		width=geo.width()
		height=geo.height()-mbgeo.height()

		self.view.setGeometry(x,y,width,height)

	# respond to menu item events in the drawing window
	def on_action_Edit_Undo_triggered(self,accept=True):
		if accept:
			self.undo()

	def on_action_Edit_Redo_triggered(self,accept=True):
		if accept:
			self.redo()

	def on_action_Zoom_In_triggered(self,accept=True):
		if accept:
			self.zoom*=1.25
			self.view.newZoom()

	def on_action_Zoom_Out_triggered(self,accept=True):
		if accept:
			self.zoom/=1.25
			self.view.newZoom()

	def on_action_Zoom_1_1_triggered(self,accept=True):
		if accept:
			self.zoom=1.0
			self.view.newZoom()

	def on_action_Image_Scale_Image_triggered(self,accept=True):
		if accept:
			dialog=qtgui.QDialog()
			dialog.ui=Ui_CanvasScaleDialog()
			dialog.ui.setupUi(dialog)

			dialog.ui.width_spin_box.setValue(self.docwidth)
			dialog.ui.height_spin_box.setValue(self.docheight)

			dialog.exec_()

			if dialog.result():
				newwidth=dialog.ui.width_spin_box.value()
				newheight=dialog.ui.height_spin_box.value()

	def on_action_Image_Canvas_Size_triggered(self,accept=True):
		if accept:
			dialog=qtgui.QDialog()
			dialog.ui=Ui_CanvasSizeDialog()
			dialog.ui.setupUi(dialog)
			if self.type!=WindowTypes.singleuser:
				dialog.ui.Left_Adjust_Box.setDisabled(True)
				dialog.ui.Top_Adjust_Box.setDisabled(True)

			dialog.exec_()

			if dialog.result():
				leftadj=dialog.ui.Left_Adjust_Box.value()
				topadj=dialog.ui.Top_Adjust_Box.value()
				rightadj=dialog.ui.Right_Adjust_Box.value()
				bottomadj=dialog.ui.Bottom_Adjust_Box.value()
				self.addAdjustCanvasSizeRequestToQueue(leftadj,topadj,rightadj,bottomadj)

	def addSetCanvasSizeRequestToQueue(self,width,height,source=ThreadTypes.user):
		if width!=self.docwidth or height!=self.docheight:
			print "changing size from:", self.docwidth, self.docheight, "to size:", width, height
			self.addAdjustCanvasSizeRequestToQueue(0,0,width-self.docwidth,height-self.docheight)

	def addAdjustCanvasSizeRequestToQueue(self,leftadj,topadj,rightadj,bottomadj,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.resize,leftadj,topadj,rightadj,bottomadj),source)

	# grow or crop canvas according to adjustments on each side
	def adjustCanvasSize(self,leftadj,topadj,rightadj,bottomadj):
		# lock the image so no updates can happen in the middle of this
		lock=ReadWriteLocker(self.imagelock,True)

		self.docwidth=self.docwidth+leftadj+rightadj
		self.docheight=self.docheight+topadj+bottomadj

		self.image=qtgui.QImage(self.docwidth,self.docheight,qtgui.QImage.Format_ARGB32_Premultiplied)

		# resize the backdrop
		self.recreateBackdrop()

		# adjust size of all the layers
		for layer in self.layers:
			layer.adjustCanvasSize(leftadj,topadj,rightadj,bottomadj)

		# finally resize the widget and update image
		self.ui.PictureViewWidget.newZoom()

		lock.unlock()
		self.reCompositeImage()

	# create backdrop for bottom of all layers, eventually I'd like this to be configurable, but for now it just fills in all white
	def recreateBackdrop(self):
		self.backdrop=qtgui.QImage(self.docwidth,self.docheight,qtgui.QImage.Format_ARGB32_Premultiplied)
		self.backdrop.fill(0xFFFFFFFF)

	def on_action_File_Log_toggled(self,state):
		if state:
			filename=qtgui.QFileDialog.getSaveFileName(self,"Choose File Name",".","Logfiles (*.slg)")
			self.startLog(filename)
		else:
			self.endLog()

	# start a log file
	def startLog(self,filename=None):
		if not filename:
			filename=os.path.join('logs',str(datetime.now()) + '.slg')

		locks=[]
		self.filename=filename

		self.logfile=qtcore.QFile(self.filename)
		self.logfile.open(qtcore.QIODevice.WriteOnly)
		log=SketchLogWriter(self.logfile)

		log.logCreateDocument(self.docwidth,self.docheight)
		# log everything to get upto this point
		pos=0
		for layer in self.layers:
			locks.append(ReadWriteLocker(layer.imagelock,True))
			log.logLayerAdd(pos,layer.key)
			log.logRawEvent(0,0,layer.key,layer.image)
			pos+=1

		self.log=log

	def endLog(self):
		if self.log:
			self.log.endLog()
			self.log=None

	def on_action_File_Save_triggered(self,accept=True):
		if not accept:
			return

		filterstring=qtcore.QString("Images (")
		formats=getSupportedWriteFileFormats()
		for f in formats:
			filterstring.append(" *.")
			filterstring.append(f)

		# add in extension for custom file format
		filterstring.append(" *.bee)")

		filename=qtgui.QFileDialog.getSaveFileName(self,"Choose File Name",".",filterstring)
		if filename:
			self.saveFile(filename)

	def saveFile(self,filename):
		# if we are saving my custom format
		if filename.endsWith(".bee"):
			# my custom format is a pickled list of tuples containing:
				# a compressed qbytearray with PNG data, opacity, visibility, blend mode
			l=[]
			# first item in list is file format version and size of image
			l.append((fileformatversion,self.docwidth,self.docheight))
			for layer in self.layers:
				bytearray=qtcore.QByteArray()
				buf=qtcore.QBuffer(bytearray)
				buf.open(qtcore.QIODevice.WriteOnly)
				layer.image.save(buf,"PNG")
				# add gzip compression to byte array
				bytearray=qtcore.qCompress(bytearray)
				l.append((bytearray,layer.opacity,layer.visible,layer.compmode))

			f=open(filename,"w")
			pickle.dump(l,f)
		else:
			writer=qtgui.QImageWriter(filename)
			imagelock=ReadWriteLocker(self.imagelock)
			writer.write(self.image)

	def cleanUp(self):
		# end the log if there is one
		self.endLog()

		self.localdrawingthread.addExitEventToQueue()
		self.localdrawingthread.wait(2000)

		# if we started a remote drawing thread kill it
		if self.remotedrawingthread:
			self.remotedrawingthread.addExitEventToQueue()
			self.remotedrawingthread.wait(2000)

		self.master.drawingwindows.remove(self)
		self.close()

	# this is for inserting a layer with a given image, for instance if loading from a log file with a partially started drawing
	def loadLayer(self,image,type=LayerTypes.user,key=None,index=None, opacity=None, visible=None, compmode=None):
		if not key:
			key=self.nextLayerKey()

		if not index:
			index=len(self.layers)

		self.insertLayer(key,index,type,image,opacity=opacity,visible=visible,compmode=compmode)
		self.reCompositeImage()

	def insertRawLayer(self,layer,index,history=0):
		self.layers.insert(index,layer)
		self.requestLayerListRefresh()
		self.reCompositeImage()
		# only select it immediately if we can draw on it
		if layer.type==LayerTypes.user:
			self.curlayerkey=layer.key

		# only add command to history if we should
		if self.type==WindowTypes.singleuser and history!=-1:
			self.addCommandToHistory(AddLayerCommand(layer.key))


	# insert a layer at a given point in the list of layers
	def insertLayer(self,key,index,type=LayerTypes.user,image=None,opacity=None,visible=None,compmode=None,owner=0,history=0):
		layer=BeeLayer(self,type,key,image,opacity=opacity,visible=visible,compmode=compmode,owner=0)

		self.layers.insert(index,layer)

		# only select it immediately if we can draw on it
		if type==LayerTypes.user:
			self.curlayerkey=key

		# only add command to history if we are in a local session
		if self.type==WindowTypes.singleuser and history!=-1:
			self.addCommandToHistory(AddLayerCommand(layer.key))

		self.requestLayerListRefresh()

	def addInsertLayerEventToQueue(self,index,key,name=None,source=ThreadTypes.user,owner=0):
		# when the source is local like this the owner will always be me (id 0)
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.insertlayer,key,index,owner),source,owner)
		return key

	def addLayer(self):
		key=self.nextLayerKey()
		index=len(self.layers)
		# when the source is local like this the owner will always be me (id 0)
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.insertlayer,key,index,0))

	# just in case someone lets up on the cursor when outside the drawing area this will make sure it's caught
	def tabletEvent(self,event):
		if event.type()==qtcore.QEvent.TabletRelease:
			self.view.cursorReleaseEvent(event.x(),event,y())

	def setActiveLayer(self,newkey):
		oldkey=self.curlayerkey
		self.curlayerkey=newkey
		self.master.updateLayerHighlight(newkey)
		self.master.updateLayerHighlight(oldkey)

	def addRawEventToQueue(self,key,image,x,y,path,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.rawevent,key,image,x,y,path),source)

	def addOpacityChangeToQueue(self,key,value,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.alpha,key,value),source)

	def addBlendModeChangeToQueue(self,key,value,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.mode,key,value),source)

	# do what's needed to start up any network threads
	def startNetworkThreads(self,username,password,host,port):
		print "running startNetworkThreads"
		self.listenerthread=NetworkListenerThread(self,username,password,host,port)
		print "about to start thread"
		self.listenerthread.start()

	def logCommand(self,command):
		if self.log:
			self.log.logCommand(command)
		if self.type==WindowTypes.standaloneserver:
			self.master.routinginput.put((command,self.remoteid))

	def logStroke(self,tool):
		if self.log:
			self.log.logToolEvent(tool)
		if self.type==WindowTypes.standaloneserver:
			self.master.routinginput.put(((DrawingCommandTypes.layer,LayerCommandTypes.tool,command),self.remoteid))
