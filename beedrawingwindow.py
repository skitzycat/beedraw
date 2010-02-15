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

import sys
sys.path.append("designer")

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui

import os
import cPickle as pickle

from beetypes import *
from beeview import BeeCanvasScene
from beeview import BeeCanvasView
from beeutil import *
from beeeventstack import *
from datetime import datetime
from beeglobals import *
from beelayer import BeeGuiLayer,SelectedAreaDisplay,SelectedAreaAnimation,LayerFinisher

from Queue import Queue
from drawingthread import DrawingThread

from DrawingWindowUI import Ui_DrawingWindowSpec
from ImageScaleDialog import Ui_CanvasScaleDialog

from beesessionstate import BeeSessionState

from animation import *

from canvasadjustpreview import CanvasAdjustDialog

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
		self.remotedrawingthread=None

		self.selectiondisplay=None
		self.selectionanimation=None
		self.selectionanimationtimer=None

		self.tooloverlay=None

		self.selectionoutline=[]
		self.selection=[]
		self.selectionlock=qtcore.QReadWriteLock()
		self.clippath=None
		self.clippathlock=qtcore.QReadWriteLock()

		self.localcommandqueue=Queue(0)

		# replace widget with my custom class widget
		self.scene=BeeCanvasScene(self)
		self.ui.PictureViewWidget=BeeCanvasView(self,self.ui.PictureViewWidget,self.scene)
		self.view=self.ui.PictureViewWidget
		#self.resizeViewToWindow()
		self.view.setCursor(master.getCurToolDesc().getCursor())

		self.show()

		self.layerfinisher=LayerFinisher(qtcore.QRectF(0,0,width,height))

		self.scene.addItem(self.layerfinisher)

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

		# create a backdrop to be put at the bottom of all the layers
		self.recreateBackdrop()

		# put in starting blank layer if needed
		# don't go through the queue for this layer add because we need it to
		# be done before the next step
		if startlayer:
			self.addInsertLayerEventToQueue(0,self.nextLayerKey(),source=ThreadTypes.user)

		# have window get destroyed when it gets a close event
		self.setAttribute(qtcore.Qt.WA_DeleteOnClose)

	# this is for debugging memory cleanup
	#def __del__(self):
	#	print "DESTRUCTOR: bee drawing window"

	def resetLayerZValues(self):
		i=0
		locker=qtcore.QReadLocker(self.layerslistlock)
		for layer in self.layers:
			layer.setZValue(i)
			i+=1

		self.layerfinisher.setZValue(i)
		i+=1

		if self.selectiondisplay:
			self.selectiondisplay.setZValue(i)
			i+=1

		if self.tooloverlay:
			self.tooloverlay.setZValue(i)
			i+=1

		self.scene.update()

	def displayMessage(self,boxtype,title,message):
		if boxtype==BeeDisplayMessageTypes.warning:
			qtgui.QMessageBox.warning(self,title,message)
		elif boxtype==BeeDisplayMessageTypes.error:
			qtgui.QMessageBox.critical(self,title,message)

	def changeToolOverlay(self,overlay=None):
		if self.tooloverlay:
			self.scene.removeItem(self.tooloverlay)
			self.tooloverlay=None

		if overlay:
			self.scene.addItem(overlay)
			self.tooloverlay=overlay

	def saveFile(self,filename):
		""" save current state of session to file
		"""
		# if we are saving my custom format
		if filename.endsWith(".bee"):
			# my custom format is a pickled list of tuples containing:
				# a compressed qbytearray with PNG data, opacity, visibility, blend mode
			l=[]
			# first item in list is file format version and size of image
			l.append((BEE_FILE_FORMAT_VERSION,self.docwidth,self.docheight))
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
			writer.write(self.scene.getImageCopy())

	def adjustCanvasSize(self,leftadj,topadj,rightadj,bottomadj):
		# lock the image so no updates can happen in the middle of this
		sizelock=ReadWriteLocker(self.docsizelock,True)

		self.docwidth=self.docwidth+leftadj+rightadj
		self.docheight=self.docheight+topadj+bottomadj

		# adjust size of all the layers
		for layer in self.layers:
			layer.adjustCanvasSize(leftadj,topadj,rightadj,bottomadj)

		# adjust size of the layer finisher
		self.layerfinisher.resize()

		# finally resize the widget and update image
		self.scene.adjustCanvasSize(leftadj,topadj,rightadj,bottomadj)

		self.reCompositeImage()

		# update all layer preview thumbnails
		self.master.refreshLayerThumb(self.id)

	def getClipPathCopy(self):
		cliplock=qtcore.QReadLocker(self.clippathlock)
		if self.clippath:
			return qtgui.QPainterPath(self.clippath)
		return None

	# update the clipping path to match the current selection
	def updateClipPath(self,slock=None):
		""" updates the clip path to match current selections, should be called every time selections are updated """
		if not slock:
			slock=qtcore.QReadLocker(self.selectionlock)

		cliplock=qtcore.QWriteLocker(self.clippathlock)

		if not self.selection:
			self.clippath=None
			return

		self.clippath=qtgui.QPainterPath()
		for select in self.selection:
			self.clippath.addPath(select)

	def penDown(self,x,y,pressure,modkeys,layerkey=None,tool=None,source=ThreadTypes.user):
		if not tool:
			tool=self.master.getCurToolInst(self)
			self.curtool=tool

		self.curtool.guiLevelPenDown(x,y,pressure,modkeys)
		self.addPenDownToQueue(x,y,pressure,layerkey,tool,source,modkeys=modkeys)

	def penMotion(self,x,y,pressure,modkeys,layerkey=None,source=ThreadTypes.user):
		if self.curtool:
			self.curtool.guiLevelPenMotion(x,y,pressure,modkeys)
			self.addPenMotionToQueue(x,y,pressure,layerkey,source,modkeys=modkeys)

	def penUp(self,x,y,modkeys,layerkey=None,source=ThreadTypes.user):
		if self.curtool:
			self.curtool.guiLevelPenUp(x,y,modkeys)
			self.addPenUpToQueue(x,y,layerkey,source,modkeys=modkeys)
			self.curtool=None

	def growSelection(self,size):
		slock=qtcore.QWriteLocker(self.selectionlock)

	def updateSelectionDisplayPath(self,path=None):
		if path and not path.isEmpty():
			if self.selectiondisplay:
				self.selectiondisplay.updatePath(path)
			else:
				self.selectiondisplay=SelectedAreaDisplay(path,self.scene)
				self.selectionanimation=SelectedAreaAnimation(self.selectiondisplay)
				self.resetLayerZValues()

		else:
			self.scene.removeItem(self.selectiondisplay)
			self.selectiondisplay=None
			self.selectionanimation=None
			self.selectionanimationtimer=None

	# change the current selection path, and update to screen to show it
	def changeSelection(self,type,newarea=None,slock=None):
		if not slock:
			slock=qtcore.QWriteLocker(self.selectionlock)

		dirtyregion=qtgui.QRegion()

		# if we get a clear operation clear the seleciton and outline then return
		if type==SelectionModTypes.clear:
			for s in self.selection:
				dirtyregion=dirtyregion.united(qtgui.QRegion(s.boundingRect().toAlignedRect()))
			self.selection=[]
			self.selectionoutline=[]
			self.updateClipPath(slock=slock)
			self.updateSelectionDisplayPath()

		else:
			# new area argument can be implied to be the cursor overlay, but we need one or the other
			if not self.cursoroverlay and not newarea:
				return

			else:
				if not newarea:
					newarea=qtgui.QPainterPath(self.cursoroverlay.path)

			if type==SelectionModTypes.new or len(self.selection)==0:
				dirtyregion=dirtyregion.united(qtgui.QRegion(newarea.boundingRect().toAlignedRect()))
				for s in self.selection:
					dirtyregion=dirtyregion.united(qtgui.QRegion(s.boundingRect().toAlignedRect()))
				self.selection=[newarea]

			elif type==SelectionModTypes.add:
				newselect=[]
				dirtyregion=dirtyregion.united(qtgui.QRegion(newarea.boundingRect().toAlignedRect()))
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
				dirtyregion=dirtyregion.united(qtgui.QRegion(newarea.boundingRect().toAlignedRect()))
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
				dirtyregion=dirtyregion.united(qtgui.QRegion(newarea.boundingRect().toAlignedRect()))
				for select in self.selection:
					dirtyregion=dirtyregion.united(qtgui.QRegion(select.boundingRect().toAlignedRect()))
					tmpselect=select.intersected(newarea)
					if not tmpselect.isEmpty():
						newselect.append(tmpselect)

				self.selection=newselect

			else:
				print "unrecognized selection modification type:", type

			self.updateClipPath(slock=slock)
			self.updateSelectionDisplayPath(self.clippath)

		# now update screen as needed
		if not dirtyregion.isEmpty():
			dirtyrect=dirtyregion.boundingRect()
			dirtyrect.adjust(-1,-1,2,2)
			self.view.updateView(dirtyrect)

	def queueCommand(self,command,source=ThreadTypes.user,owner=0):
		if source==ThreadTypes.user:
			#print "putting command in local queue"
			self.localcommandqueue.put(command)
		elif source==ThreadTypes.server:
			#print "putting command in routing queue"
			#self.master.routinginput.put((command,owner))
			self.remotecommandqueue.put(command)
		else:
			#print "putting command in remote queue:", command, self.remotecommandqueue
			self.remotecommandqueue.put(command)

	# send event to GUI to update the list of current layers
	def requestLayerListRefresh(self):
		self.resetLayerZValues()
		event=qtcore.QEvent(BeeCustomEventTypes.refreshlayerslist)
		BeeApp().app.postEvent(self.master,event)

	def removeLayer(self,layer,history=0,lock=None):
		(layer,index)=BeeSessionState.removeLayer(self,layer,history,lock)
		if layer:
			self.scene.removeItem(layer)
			self.scene.update()
		return layer,index

	def insertLayer(self,key,index,type=LayerTypes.user,image=None,opacity=None,visible=None,compmode=None,owner=0,history=0):
		lock=qtcore.QWriteLocker(self.layerslistlock)
		# make sure layer doesn't exist already
		oldlayer=self.getLayerForKey(key,lock=lock)
		if oldlayer:
			print "ERROR: tried to create layer with same key as existing layer"
			return

		layer=BeeGuiLayer(self.id,type,key,image,opacity=opacity,visible=visible,compmode=compmode,owner=owner)

		self.layers.insert(index,layer)
		lock.unlock()

		# only add command to history if we are in a local session
		if self.type==WindowTypes.singleuser and history!=-1:
			self.addCommandToHistory(AddLayerCommand(layer.key))

		self.scene.addItem(layer)

		self.requestLayerListRefresh()
		self.reCompositeImage()

	# recomposite all layers together into the displayed image
	# when a thread calls this method it shouldn't have a lock on any layers
	def reCompositeImage(self,dirtyrect=None):
		if dirtyrect:
			self.view.updateView(dirtyrect)
		else:
			self.view.updateView()
		return

	def getImagePixelColor(self,x,y,size=1):
		return self.scene.getPixelColor(x,y,size)
		
	def getCurLayerPixelColor(self,x,y,size=1):
		key=self.getCurLayerKey()
		curlayer=self.getLayerForKey(key)
		if curlayer:
			return curlayer.getPixelColor(x,y,size)
		else:
			return qtgui.QColor()

	def startRemoteDrawingThreads(self):
		pass

	# handle a few events that don't have easy function over loading front ends
	def event(self,event):
		# do the last part of setup when the window is done being created, this is so nothing starts drawing on the screen before it is ready
		if event.type()==qtcore.QEvent.WindowActivate:
			if self.activated==False:
				self.activated=True
				self.reCompositeImage()
				self.startRemoteDrawingThreads()

			self.master.takeFocus(self)

		elif event.type()==BeeCustomEventTypes.displaymessage:
			print "got request to display message"
			self.displayMessage(event.boxtype,event.title,event.message)

		# once the window has received a deferred delete it needs to have all it's references removed so memory can be freed up
		elif event.type()==qtcore.QEvent.DeferredDelete:
			self.cleanUp()

		return qtgui.QMainWindow.event(self,event)

# get the current layer key and make sure it is valid, if it is not valid then set it to something valid if there are any layers
	def getCurLayerKey(self):
		if self.layers:
			if self.getLayerForKey(self.curlayerkey):
				return self.curlayerkey
			self.curlayerkey=self.layers[0].key
			return self.curlayerkey
		return None

	# not sure how useful these will be, but just in case a tool wants to do something special when it leaves the drawable area they are here
	def penEnter(self):
		if self.curtool:
			self.curtool.penEnter()

	def penLeave(self):
		if self.curtool:
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

	def on_action_Select_None_triggered(self,accept=True):
		if accept:
			self.changeSelection(SelectionModTypes.clear)

	def on_action_Edit_Redo_triggered(self,accept=True):
		if accept:
			self.addRedoToQueue()

	def on_action_Zoom_In_triggered(self,accept=True):
		if accept:
			self.zoom*=1.25
			self.view.newZoom(self.zoom)

	def on_action_Zoom_Out_triggered(self,accept=True):
		if accept:
			self.zoom/=1.25
			self.view.newZoom(self.zoom)

	def on_action_Zoom_1_1_triggered(self,accept=True):
		if accept:
			self.zoom=1.0
			self.view.newZoom(self.zoom)

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
			dialog=CanvasAdjustDialog(self)

			# if the canvas is in any way shared don't allow changing the top or left
			# so no other lines in queue will be messed up
			if self.type!=WindowTypes.singleuser:
				dialog.ui.Left_Adjust_Box.setDisabled(True)
				dialog.ui.Top_Adjust_Box.setDisabled(True)

			dialog.exec_()

			if dialog.result():
				leftadj=dialog.leftadj
				topadj=dialog.topadj
				rightadj=dialog.rightadj
				bottomadj=dialog.bottomadj
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

		# for some reason this seems to get rid of a reference needed to allow garbage collection
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
			self.view.cursorReleaseEvent(event.x(),event.y(),event.modifiers())

	def setActiveLayer(self,newkey):
		oldkey=self.curlayerkey
		self.curlayerkey=newkey
		self.master.updateLayerHighlight(newkey)
		self.master.updateLayerHighlight(oldkey)

	# do what's needed to start up any network threads
	def startNetworkThreads(self,socket):
		print_debug("running startNetworkThreads")
		self.listenerthread=NetworkListenerThread(self,socket)
		print_debug("about to start thread")
		self.listenerthread.start()

	def switchAllLayersToLocal(self):
		lock=qtcore.QReadLocker(self.layerslistlock)
		for layer in self.layers:
			layer.type=LayerTypes.user
			layer.changeName("Layer: %d" % layer.key)

	# delete all layers
	def clearAllLayers(self):
		# lock all layers and the layers list
		lock=qtcore.QWriteLocker(self.layerslistlock)
		locklist=[]
		for layer in self.layers[:]:
			self.removeLayer(layer,history=0,lock=lock)

		self.layers=[]
		lock.unlock()

		self.requestLayerListRefresh()
		self.reCompositeImage()

class AnimationDrawingWindow(BeeDrawingWindow):
	""" Represents a window that plays a log file
	"""
	def __init__(self,master,filename):
		self.playfilename=filename
		BeeDrawingWindow.__init__(self,master,startlayer=False,type=WindowTypes.animation)

	def startRemoteDrawingThreads(self):
		self.remotedrawingthread=DrawingThread(self.remotecommandqueue,self.id,ThreadTypes.animation,master=self.master)
		self.remotedrawingthread.start()
		self.animationthread=PlayBackAnimation(self,self.playfilename)
		self.animationthread.start()

class NetworkClientDrawingWindow(BeeDrawingWindow):
	""" Represents a window that the user can draw in with others in a network session
	"""
	def __init__(self,parent,socket):
		print_debug("initializign network window")
		self.socket=socket
		BeeDrawingWindow.__init__(self,parent,startlayer=False,type=WindowTypes.networkclient)
		self.disconnectmessage=None

	def setDisconnectMessage(self,message):
		if not self.disconnectmessage:
			self.disconnectmessage=message

	def startRemoteDrawingThreads(self):
		self.startNetworkThreads(self.socket)
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

	def disconnected(self):
		if not self.disconnectmessage:
			self.disconnectmessage="For Unknown Reasons"

		print_debug("disconnected from server")
		self.switchAllLayersToLocal()
		requestDisplayMessage(BeeDisplayMessageTypes.warning,"Network Session has ended","Connection has been broken: " + self.disconnectmessage,self)
