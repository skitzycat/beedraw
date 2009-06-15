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
from beeglobals import *

from Queue import Queue
from drawingthread import DrawingThread

from DrawingWindowUI import Ui_DrawingWindowSpec
from ImageSizeAdjustDialogUi import Ui_CanvasSizeDialog
from ImageScaleDialog import Ui_CanvasScaleDialog

from beesessionstate import BeeSessionState

from animation import *

from canvasadjustpreview import CanvasAdjustPreview

class BeeDrawingWindow(qtgui.QMainWindow,BeeSessionState):
	""" Represents a window that the user can draw in
	"""
	def __init__(self,master,width=600,height=400,startlayer=True,type=WindowTypes.singleuser,maxundo=20):
		BeeSessionState.__init__(self,master,width,height,type)
		qtgui.QMainWindow.__init__(self,master)

		self.localcommandstack=CommandStack(self.id,maxundo)

		# initialize values
		self.zoom=1.0
		self.ui=Ui_DrawingWindowSpec()
		self.ui.setupUi(self)
		self.activated=False
		self.backdrop=None

		self.cursoroverlay=None

		self.selectionoutline=[]
		self.clippath=None

		self.localcommandqueue=Queue(0)

		# initiate drawing thread
		if type==WindowTypes.standaloneserver:
			self.localdrawingthread=DrawingThread(self.remotecommandqueue,self.id,type=ThreadTypes.server,master=master)
		else:
			self.localdrawingthread=DrawingThread(self.localcommandqueue,self.id,master=self.master)

		self.localdrawingthread.start()

		# for sending events to server so they don't slow us down locally
		self.sendtoserverqueue=None
		self.sendtoserverthread=None

		self.serverreadingthread=None

		self.image=qtgui.QImage(width,height,qtgui.QImage.Format_ARGB32_Premultiplied)

		# replace widget with my custom class widget
		self.ui.PictureViewWidget=BeeViewScrollArea(self.ui.PictureViewWidget,self)
		self.view=self.ui.PictureViewWidget
		self.resizeViewToWindow()
		self.view.setCursor(master.getCurToolDesc().getCursor())

		self.show()

		# create a backdrop to be put at the bottom of all the layers
		self.recreateBackdrop()

		# put in starting blank layer if needed
		# don't go through the queue for this layer add because we need it to
		# be done before the next step
		if startlayer:
			#print "calling nextLayerKey from beedrawingwindow constructor"
			self.addInsertLayerEventToQueue(self.nextLayerKey(),0,source=ThreadTypes.user)

		# have window get destroyed when it gets a close event
		self.setAttribute(qtcore.Qt.WA_DeleteOnClose)

	# this is for debugging memory cleanup
	#def __del__(self):
	#	print "DESTRUCTOR: bee drawing window"

	# alternate constructor for starting an animation playback
	def newAnimationWindow(master,filename):
		newwin=BeeDrawingWindow(master,600,400,False,WindowTypes.animation)
		newwin.animationthread=PlayBackAnimation(newwin,filename)
		return newwin

	# make method static
	newAnimationWindow=staticmethod(newAnimationWindow)

	def saveFile(self,filename):
		""" save current state of session to file
		"""
		imagelock=ReadWriteLocker(self.imagelock)
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
		# for all other formats just use the standard qt image writer
		else:
			writer=qtgui.QImageWriter(filename)
			writer.write(self.image)

	def adjustCanvasSize(self,leftadj,topadj,rightadj,bottomadj):
		# lock the image so no updates can happen in the middle of this
		sizelock=ReadWriteLocker(self.docsizelock,True)
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

		# update all layer preview thumbnails
		self.master.refreshLayerThumb(self.id)

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
		# new area argument can be implied to be the cursor overlay, but we need one or the other
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
			print "unrecognized selection modification type:", type

		self.updateClipPath()
		# TODO: make sure the selection is not the whole image

		# now change the selecition outline
		#self.selectionoutline=self.selection.toFillPolygons()

	# thread safe function to return a layer key number that hasn't been returned before

	def queueCommand(self,command,source=ThreadTypes.user,owner=0):
		#print "queueing command:", command
		if source==ThreadTypes.user:
			#print "putting command in local queue"
			self.localcommandqueue.put(command)
		elif source==ThreadTypes.server:
			#print "putting command in routing queue"
			#self.master.routinginput.put((command,owner))
			self.remotecommandqueue.put(command)
		else:
			#print "putting command in remote queue"
			self.remotecommandqueue.put(command)

	# send event to GUI to update the list of current layers
	def requestLayerListRefresh(self):
		event=qtcore.QEvent(BeeCustomEventTypes.refreshlayerslist)
		BeeApp().app.postEvent(self.master,event)

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

	def getImagePixelColor(self,x,y,size=1):
		imagelocker=ReadWriteLocker(self.imagelock,False)
		return self.image.pixel(x,y)
		
	def getCurLayerPixelColor(self,x,y,size=1):
		key=self.getCurLayerKey()
		curlayer=self.getLayerForKey(key)
		if curlayer:
			return curlayer.getPixelColor(x,y,size)
		else:
			return qtgui.QColor()

	def startRemoteDrawingThreads(self):
		if self.type==WindowTypes.singleuser:
			self.remotedrawingthread=None
		elif self.type==WindowTypes.animation:
			self.remotedrawingthread=DrawingThread(self.remotecommandqueue,self.id,ThreadTypes.animation,master=self.master)
			self.remotedrawingthread.start()
		else:
			self.remotedrawingthread=DrawingThread(self.remotecommandqueue,self.id,ThreadTypes.network,master=self.master)
			self.remotedrawingthread.start()

	# handle a few events that don't have easy function over loading front ends
	def event(self,event):
		# do the last part of setup when the window is done being created, this is so nothing starts drawing on the screen before it is ready
		if event.type()==qtcore.QEvent.WindowActivate:
			if self.activated==False:
				self.activated=True
				self.reCompositeImage()
				self.startRemoteDrawingThreads()

			self.master.takeFocus(self)

		# once the window has received a deferred delete it needs to have all it's references removed so memory can be freed up
		elif event.type()==qtcore.QEvent.DeferredDelete:
			self.cleanUp()

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

	def penMotion(self,x,y,pressure):
		self.curtool.penMotion(x,y,pressure)

	def penUp(self,x,y):
		self.curtool.penUp(x,y)

	# not sure how useful these will be, but just in case a tool wants to do something special when it leaves the drawable area they are here
	def penEnter(self):
		self.curtool.penEnter()

	def penLeave(self):
		self.curtool.penLeave()

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
			self.addUndoToQueue()

	def on_action_Edit_Redo_triggered(self,accept=True):
		if accept:
			self.addRedoToQueue()

	def on_action_Zoom_In_triggered(self,accept=True):
		if accept:
			self.zoom*=1.25
			self.view.newZoom()

	def on_action_Zoom_Out_triggered(self,accept=True):
		if accept:
			self.zoom/=1.25
			self.view.newZoom()

	def on_action_File_Close_triggered(self,accept=True):
		if accept:
			self.close()

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
			dialog.ui.image_preview=CanvasAdjustPreview(dialog.ui.image_preview,self)

			# if the canvas is in any way shared don't allow changing the top or left
			# so no other lines in queue will be messed up
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

	# create backdrop for bottom of all layers, eventually I'd like this to be configurable, but for now it just fills in all white
	def recreateBackdrop(self):
		self.backdrop=qtgui.QImage(self.docwidth,self.docheight,qtgui.QImage.Format_ARGB32_Premultiplied)
		self.backdrop.fill(self.backdropcolor)

	def on_action_File_Log_toggled(self,state):
		"""If log box is now checked ask user to provide log file name and start a log file for the current session from this point
       If log box is now unchecked end the current log file
		"""
		if state:
			filename=qtgui.QFileDialog.getSaveFileName(self,"Choose File Name",".","Logfiles (*.slg)")
			if not filename:
				return
			self.startLog(filename)
		else:
			self.endLog()

	# start a log file
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

	# this is here because the window doesn't seem to get deleted when it's closed
	# the cleanUp function attempts to clean up as much memory as possible
	def cleanUp(self):
		# end the log if there is one
		self.endLog()

		# for some reason this seems to get rid of a reference
		self.setParent(None)

		self.localdrawingthread.addExitEventToQueue()
		if not self.localdrawingthread.wait(10000):
			print "WARNING: drawing thread did not terminate on time"

		# if we started a remote drawing thread kill it
		if self.remotedrawingthread:
			self.remotedrawingthread.addExitEventToQueue()
			if not self.remotedrawingthread.wait(20000):
				print "WARNING: remote drawing thread did not terminate on time"

		# this should be the last referece to the window
		self.master.unregisterWindow(self)

	# just in case someone lets up on the cursor when outside the drawing area this will make sure it's caught
	def tabletEvent(self,event):
		if event.type()==qtcore.QEvent.TabletRelease:
			self.view.cursorReleaseEvent(event.x(),event,y())

	def setActiveLayer(self,newkey):
		oldkey=self.curlayerkey
		self.curlayerkey=newkey
		self.master.updateLayerHighlight(newkey)
		self.master.updateLayerHighlight(oldkey)

	# do what's needed to start up any network threads
	def startNetworkThreads(self,username,password,host,port):
		print "running startNetworkThreads"
		self.listenerthread=NetworkListenerThread(self,username,password,host,port)
		print "about to start thread"
		self.listenerthread.start()

	def switchAllLayersToLocal(self):
		for layer in self.layers:
			layer.type=LayerTypes.user
			layer.changeName("Layer: %d" % layer.key)

	# delete all layers
	def clearAllLayers(self):
		# lock all layers and the layers list
		listlock=qtcore.QMutexLocker(self.layersmutex)
		locklist=[]
		for layer in self.layers:
			locklist.append(ReadWriteLocker(layer.imagelock,False))

		self.layers=[]
		self.requestLayerListRefresh()
		self.reCompositeImage()

class NetworkClientDrawingWindow(BeeDrawingWindow):
	""" Represents a window that the user can draw in
	"""
	def __init__(self,parent,username,password,host,port):
		print "initializign network window"
		BeeDrawingWindow.__init__(self,parent,startlayer=False,type=WindowTypes.networkclient)
		self.username=username
		self.password=password
		self.host=host
		self.port=port

	def startRemoteDrawingThreads(self):
		self.startNetworkThreads(self.username,self.password,self.host,self.port)
		self.remotedrawingthread=DrawingThread(self.remotecommandqueue,self.id,ThreadTypes.network,master=self.master)
		self.remotedrawingthread.start()

	def changeOwner(self,newowner,layerkey):
		for layer in self.layers:
			if layerkey==layer.key:
				imagelock=None
				if layerkey==layer.key:
					proplock=qtcore.QWriteLocker(layer.propertieslock)
					# don't think I really need this lock, but just in case
					imagelock=qtcore.QWriteLocker(layer.imagelock)
					self.localcommandstack.removeLayerRefs(layerkey)
					layer.owner=newowner
