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

import sys
sys.path.append("designer")

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui

import os

from beetypes import *
from beeview import BeeCanvasScene
from beeview import BeeCanvasView
from beeutil import *
from beeeventstack import *
from datetime import datetime
from beeglobals import *
from beelayer import BeeGuiLayer,SelectedAreaDisplay,LayerFinisher

from Queue import Queue
from drawingthread import DrawingThread

from DrawingWindowMdiUi import Ui_DrawingWindowMdi
from GrowSelectionDialogUi import Ui_Grow_Selection_Dialog
from ShrinkSelectionDialogUi import Ui_Shrink_Selection_Dialog
from beedialogs import BeeScaleImageDialog

from beesessionstate import BeeSessionState

from animation import *

from canvasadjustpreview import CanvasAdjustDialog

class BeeDrawingWindow(qtgui.QWidget,BeeSessionState):
	""" Represents a window that the user can draw in
	"""
	def __init__(self,master,width=600,height=400,startlayer=True,type=WindowTypes.singleuser,maxundo=40):
		self.logaction=None
		BeeSessionState.__init__(self,master,width,height,type)
		qtgui.QWidget.__init__(self)

		self.localcommandstack=CommandStack(self,CommandStackTypes.singleuser,maxundo=maxundo)

		self.layerfinisher=LayerFinisher(qtcore.QRectF(0,0,width,height))

		# initialize values
		self.zoom=1.0

		self.ui=Ui_DrawingWindowMdi()
		self.ui.setupUi(self)

		self.activated=False
		self.backdrop=None

		self.filename=""

		self.cursoroverlay=None
		self.remotedrawingthread=None

		self.tooloverlay=None

		self.selection=None
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

		self.selectiondisplay=SelectedAreaDisplay(None,self.scene,self.view)

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
			self.insertLayer(self.nextLayerKey(),0,history=False)

		# have window get destroyed when it gets a close event
		self.setAttribute(qtcore.Qt.WA_DeleteOnClose)

		self.changeWindowTitle("Bee Canvas %d" % self.id)

		self.setupMenu()

	# this is for debugging memory cleanup
	#def __del__(self):
	#	print "DESTRUCTOR: bee drawing window"

	def setupMenu(self):
		menubar=qtgui.QMenuBar(self)
		replaceWidget(self.ui.menu_widget,menubar)
		self.ui.menu_widget=menubar

		# File Menu
		filemenu=menubar.addMenu("File")
		curaction=filemenu.addAction("New",self.on_action_File_New_triggered)
		curaction=filemenu.addAction("Open",self.on_action_File_Open_triggered)
		curaction=filemenu.addAction("Play",self.on_action_File_Play_triggered)
		curaction=filemenu.addAction("Connect",self.on_action_File_Connect_triggered)

		filemenu.addSeparator()

		curaction=filemenu.addAction("Save (Ctrl+S)",self.on_action_File_Save_triggered)
		curaction=filemenu.addAction("Save As (Ctrl+A)",self.on_action_File_Save_As_triggered)

		curaction=filemenu.addAction("Log (Ctrl+L)")
		curaction.setCheckable(True)
		qtcore.QObject.connect(curaction,qtcore.SIGNAL("triggered(bool)"),self.on_action_File_Log_toggled)
		self.logaction=curaction
		if self.log:
			self.logaction.setChecked(True)

		curaction=filemenu.addAction("Close",self.on_action_File_Close_triggered)

		# Edit menu
		editmenu=menubar.addMenu("Edit")

		curaction=editmenu.addAction("Undo (Ctrl+Z)",self.on_action_Edit_Undo_triggered)
		curaction=editmenu.addAction("Redo (Ctrl+R)",self.on_action_Edit_Redo_triggered)

		editmenu.addSeparator()

		curaction=editmenu.addAction("Cut (Ctrl+X)",self.on_action_Edit_Cut_triggered)
		curaction=editmenu.addAction("Copy (Ctrl+C)",self.on_action_Edit_Copy_triggered)
		curaction=editmenu.addAction("Paste (Ctrl+V)",self.on_action_Edit_Paste_triggered)

		#View menu
		viewmenu=menubar.addMenu("View")
		curaction=viewmenu.addAction("Zoom In (+)",self.on_action_View_Zoom_In_triggered)
		curaction=viewmenu.addAction("Zoom Out (-)",self.on_action_View_Zoom_Out_triggered)
		curaction=viewmenu.addAction("Zoom 1:1 (1)",self.on_action_View_Zoom_1_1_triggered)

		#Image menu
		imagemenu=menubar.addMenu("Image")
		self.imagemenu=imagemenu

		curaction=imagemenu.addAction("Canvas Size",self.on_action_Image_Canvas_Size_triggered)
		curaction=imagemenu.addAction("Scale Image",self.on_action_Image_Scale_Image_triggered)
		curaction=imagemenu.addAction("Flatten Image",self.on_action_Image_Flatten_Image_triggered)

		#Select menu
		selectmenu=menubar.addMenu("Select")
		curaction=selectmenu.addAction("Select None",self.on_action_Select_None_triggered)
		curaction=selectmenu.addAction("Invert Selection",self.on_action_Select_Invert_Selection_triggered)
		curaction=selectmenu.addAction("Grow Selection",self.on_action_Select_Grow_Selection_triggered)
		curaction=selectmenu.addAction("Shrink Selection",self.on_action_Select_Shrink_Selection_triggered)

		#Network menu
		#networkmenu=menubar.addMenu("Network")

		self.menubar=menubar

	def keyPressEvent(self,event):
		if event.modifiers()==qtcore.Qt.ControlModifier:
			if event.key()==qtcore.Qt.Key_Z:
				self.on_action_Edit_Undo_triggered()
			elif event.key()==qtcore.Qt.Key_R:
				self.on_action_Edit_Redo_triggered()
			elif event.key()==qtcore.Qt.Key_X:
				self.on_action_Edit_Cut_triggered()
			elif event.key()==qtcore.Qt.Key_C:
				self.on_action_Edit_Copy_triggered()
			elif event.key()==qtcore.Qt.Key_P:
				self.on_action_Edit_Paste_triggered()
			elif event.key()==qtcore.Qt.Key_S:
				self.on_action_File_Save_triggered()
			elif event.key()==qtcore.Qt.Key_A:
				self.on_action_File_Save_As_triggered()
			elif event.key()==qtcore.Qt.Key_L:
				self.logaction.toggle()

		else:
			if event.key()==qtcore.Qt.Key_Plus:
				self.on_action_View_Zoom_In_triggered()
			elif event.key()==qtcore.Qt.Key_Minus:
				self.on_action_View_Zoom_Out_triggered()
			elif event.key()==qtcore.Qt.Key_1:
				self.on_action_View_Zoom_1_1_triggered()

	def changeWindowTitle(self,name):
		self.setWindowTitle(name)
		self.menufocusaction.setText(name)

	def setFileName(self,filename):
		self.filename=filename
		self.changeWindowTitle(os.path.basename(str(filename)))

	def resetLayerZValues(self,lock=None):
		i=0
		if not lock:
			lock=qtcore.QReadLocker(self.layerslistlock)
		for layer in self.layers:
			layer.setZValue(i)
			sublock=qtcore.QReadLocker(layer.sublayerslock)
			for sublayer in layer.sublayers:
				sublayer.setZValue(i+.5)
			i+=1

		sublock=None

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
		lock=qtcore.QWriteLocker(self.layerslistlock)
		if self.tooloverlay:
			self.scene.removeItem(self.tooloverlay)
			self.tooloverlay=None

		if overlay:
			self.scene.addItem(overlay)
			self.tooloverlay=overlay
			self.resetLayerZValues(lock)

	def startLog(self,filename=None,endlog=False):
		BeeSessionState.startLog(self,filename,endlog)
		if self.log:
			# make sure menu item is checked
			if self.logaction:
				self.logaction.setChecked(True)
		else:
			if self.logaction:
				self.logaction.setChecked(False)

	def saveFile(self,filename):
		""" save current state of session to file
		"""
		# if we are saving my custom format
		if filename.endsWith(".bee"):
			self.startLog(filename,True)
			# my custom format is a pickled list of tuples containing:
				# a compressed qbytearray with PNG data, opacity, visibility, blend mode
			#l=[]
			# first item in list is file format version and size of image
			#l.append((BEE_FILE_FORMAT_VERSION,self.docwidth,self.docheight))
			#for layer in self.layers:
			#	bytearray=qtcore.QByteArray()
			#	buf=qtcore.QBuffer(bytearray)
			#	buf.open(qtcore.QIODevice.WriteOnly)
			#	layer.image.save(buf,"PNG")
				# add gzip compression to byte array
			#	bytearray=qtcore.qCompress(bytearray)
			#	l.append((bytearray,layer.opacity,layer.visible,layer.compmode))

			#f=open(filename,"w")
			#pickle.dump(l,f)
		# for all other formats just use the standard qt image writer
		else:
			writer=qtgui.QImageWriter(filename)
			writer.write(self.scene.getImageCopy())

	def scaleCanvas(self,newwidth,newheight,history=True):
		sizelock=qtcore.QWriteLocker(self.docsizelock)
		BeeSessionState.scaleCanvas(self,newwidth,newheight,sizelock,history)
		self.scene.setCanvasSize(newwidth,newheight)

	def adjustCanvasSize(self,leftadj,topadj,rightadj,bottomadj,sizelock=None,history=True):
		# lock the image so no updates can happen in the middle of this
		if not sizelock:
			sizelock=qtcore.QWriteLocker(self.docsizelock)

		if history:
			historyevent=AdjustCanvasSizeCommand(self.docwidth,self.docheight,leftadj,topadj,rightadj,bottomadj,self.layers)
			self.addCommandToHistory(historyevent)

		self.docwidth=self.docwidth+leftadj+rightadj
		self.docheight=self.docheight+topadj+bottomadj

		# adjust size of all the layers
		for layer in self.layers:
			layer.adjustCanvasSize(leftadj,topadj,rightadj,bottomadj)

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

		self.clippath=qtgui.QPainterPath(self.selection)

	def penDown(self,x,y,pressure,modkeys,tool=None,source=ThreadTypes.user):
		if not tool:
			tool=self.master.getCurToolInst(self)

		self.curtool=tool

		self.curtool.guiLevelPenDown(x,y,pressure,modkeys)

		if not self.curtool.layerkey:
			return

		layer=self.getLayerForKey(self.curtool.layerkey)
		if not layer:
			return

		if layer.type==LayerTypes.user or ( layer.type==LayerTypes.floating and self.curtool.allowedonfloating):
			self.addPenDownToQueue(x,y,pressure,tool.layerkey,tool,source,modkeys=modkeys)

	def penMotion(self,x,y,pressure,modkeys,source=ThreadTypes.user):
		#print "window pen motion: (x,y,pressure):", x,y,pressure
		if self.curtool:
			self.curtool.guiLevelPenMotion(x,y,pressure,modkeys)

			layer=self.getLayerForKey(self.curtool.layerkey)
			if not layer:
				return

			if layer.type==LayerTypes.user or ( layer.type==LayerTypes.floating and self.curtool.allowedonfloating):
				self.addPenMotionToQueue(x,y,pressure,self.curtool.layerkey,source,modkeys=modkeys)

	def penUp(self,x,y,modkeys,source=ThreadTypes.user):
		if self.curtool:
			self.curtool.guiLevelPenUp(x,y,modkeys)

			layer=self.getLayerForKey(self.curtool.layerkey)
			if not layer:
				return

			if layer.type==LayerTypes.user or ( layer.type==LayerTypes.floating and self.curtool.allowedonfloating):
				self.addPenUpToQueue(x,y,self.curtool.layerkey,source,modkeys=modkeys)

			self.curtool=None

	def requestUpdateSelectionDisplayPath(self,path=None):
		event=SelectionDisplayUpdateEvent(path)
		BeeApp().app.postEvent(self,event)

	# change the current selection path, and update to screen to show it
	def changeSelection(self,type,newarea=None,slock=None,history=True):
		if not slock:
			slock=qtcore.QWriteLocker(self.selectionlock)

		if self.selection:
			oldpath=qtgui.QPainterPath(self.selection)
		else:
			oldpath=None

		defaultreturn=oldpath,oldpath

		dirtyregion=qtgui.QRegion()

		# if we get a clear operation clear the seleciton and outline then return
		if type==SelectionModTypes.clear:
			# in this case there already is no selection so just ignore it
			if not self.selection:
				return defaultreturn

			if self.selection:
				dirtyregion=dirtyregion.united(qtgui.QRegion(self.selection.boundingRect().toAlignedRect()))

			self.selection=None

			self.updateClipPath(slock=slock)
			self.requestUpdateSelectionDisplayPath()

		elif type==SelectionModTypes.setlist:
			if self.selection:
				dirtyregion=dirtyregion.united(qtgui.QRegion(self.selection.boundingRect().toAlignedRect()))

			self.selection=newarea

			if self.selection:
				dirtyregion=dirtyregion.united(qtgui.QRegion(self.selection.boundingRect().toAlignedRect()))

			self.updateClipPath(slock=slock)
			self.requestUpdateSelectionDisplayPath(self.clippath)


		elif type==SelectionModTypes.invert:
			sizelock=qtcore.QReadLocker(self.docsizelock)
			width,height=self.getDocSize(sizelock)

			rect=qtcore.QRectF(0,0,width,height)

			newpath=qtgui.QPainterPath()
			newpath.addRect(rect)

			if self.selection:
				newpath=newpath.subtracted(self.selection)

			self.selection=newpath

			self.updateClipPath(slock=slock)
			self.requestUpdateSelectionDisplayPath(self.clippath)

		elif type==SelectionModTypes.shrink or type==SelectionModTypes.grow:
			if self.selection:
				stroker=qtgui.QPainterPathStroker()
				stroker.setWidth(2*newarea)
				stroker.setJoinStyle(qtcore.Qt.MiterJoin)
				growpath=stroker.createStroke(self.selection)

				if type==SelectionModTypes.grow:
					self.selection=self.selection.united(growpath)

					# make sure the selection hasn't grown larger than the full image
					width,height=self.getDocSize()

					rect=qtcore.QRectF(0,0,width,height)

					fulldocpath=qtgui.QPainterPath()
					fulldocpath.addRect(rect)

					self.selection=self.selection.intersected(fulldocpath)

					dirtyregion=dirtyregion.united(qtgui.QRegion(self.selection.boundingRect().toAlignedRect()))

				elif type==SelectionModTypes.shrink:
					dirtyregion=dirtyregion.united(qtgui.QRegion(self.selection.boundingRect().toAlignedRect()))
					self.selection=self.selection.subtracted(growpath)
					if self.selection.isEmpty():
						self.selection=None

				self.updateClipPath(slock=slock)
				self.requestUpdateSelectionDisplayPath(self.clippath)

		else:
			# in all thses cases the new area argument can be implied to be the cursor overlay, but we need one or the other
			if not self.cursoroverlay and not newarea:
				return defaultreturn

			else:
				if not newarea:
					newarea=qtgui.QPainterPath(self.cursoroverlay.path)

			if type==SelectionModTypes.new or not self.selection:
				dirtyregion=dirtyregion.united(qtgui.QRegion(newarea.boundingRect().toAlignedRect()))

				if self.selection:
					dirtyregion=dirtyregion.united(qtgui.QRegion(self.selection.boundingRect().toAlignedRect()))

				self.selection=newarea

			elif type==SelectionModTypes.add:
				dirtyregion=dirtyregion.united(qtgui.QRegion(newarea.boundingRect().toAlignedRect()))

				# the new area completely contains this path so just go with the new one
				if newarea.contains(self.selection):
					self.selection=newarea

				# the new area is inside the old one so no change
				elif self.selection.contains(newarea):
					pass

				# if they intersect union the areas
				elif newarea.intersects(self.selection):
					self.selection=newarea.united(self.selection)

				# otherwise they are completely disjoint so just add it separately
				else:
					self.selection.addPath(newarea)

			elif type==SelectionModTypes.subtract:
				dirtyregion=dirtyregion.united(qtgui.QRegion(newarea.boundingRect().toAlignedRect()))

				# the new area completely contains the new path then deselect everything
				if newarea.contains(self.selection):
					self.selection=None

				# if they intersect subtract the areas
				elif newarea.intersects(self.selection) or self.selection.contains(newarea):
					self.selection=self.selection.subtracted(newarea)

			elif type==SelectionModTypes.intersect:
				dirtyregion=dirtyregion.united(qtgui.QRegion(newarea.boundingRect().toAlignedRect()))

				dirtyregion=dirtyregion.united(qtgui.QRegion(self.selection.boundingRect().toAlignedRect()))

				if newarea.contains(self.selection):
					pass

				elif newarea.intersects(self.selection) or self.selection.contains(newarea):
					self.selection=self.selection.intersected(newarea)

				else:
					self.selection=None

			else:
				print_debug("unrecognized selection modification type: %d" % type)

			self.updateClipPath(slock=slock)
			self.requestUpdateSelectionDisplayPath(self.clippath)

		# now update screen as needed
		if not dirtyregion.isEmpty():
			dirtyrect=dirtyregion.boundingRect()
			dirtyrect.adjust(-1,-1,2,2)
			self.view.updateView(dirtyrect)

		if history:
			command=ChangeSelectionCommand(oldpath,self.selection)
			self.addCommandToHistory(command)

		return oldpath,self.selection

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
	def requestLayerListRefresh(self,lock=None):
		self.resetLayerZValues(lock)
		event=qtcore.QEvent(BeeCustomEventTypes.refreshlayerslist)
		BeeApp().app.postEvent(self.master,event)

	def layerDownPushed(self):
		layer=self.getCurLayer()
		if layer:
			if layer.type==LayerTypes.floating:
				parent=layer.layerparent
				lock=qtcore.QReadLocker(self.layerslistlock)
				if parent in self.layers:
					index=self.layers.index(parent)
					while index>0:
						index-=1
						if self.ownedByMe(self.layers[index].owner):
							newparent=self.layers[index]
							layer.changeParent(newparent)

							self.scene.update()
							self.requestLayerListRefresh(lock=lock)
							self.addFloatingLayerMoveToQueue(layer.key,parent.key,newparent.key)
							break
			else:
				self.addLayerDownToQueue(layer.key)

	def addFloatingLayerMoveToQueue(self,layerkey,oldparentkey,newparentkey):
		self.queueCommand((DrawingCommandTypes.localonly,LocalOnlyCommandTypes.floatingmove,layerkey,oldparentkey,newparentkey),ThreadTypes.user)

	def layerUpPushed(self):
		layer=self.getCurLayer()
		if layer:
			if layer.type==LayerTypes.floating:
				parent=layer.layerparent
				lock=qtcore.QReadLocker(self.layerslistlock)
				if parent in self.layers:
					index=self.layers.index(parent)
					index+=1
					while index<len(self.layers):
						if self.ownedByMe(self.layers[index].owner):
							newparent=self.layers[index]
							layer.changeParent(newparent)

							self.scene.update()
							self.requestLayerListRefresh(lock=lock)
							self.addFloatingLayerMoveToQueue(layer.key,parent.key,newparent.key)
							break

						index+=1
			else:
				self.addLayerUpToQueue(layer.key)

	def removeLayer(self,layer,history=True,listlock=None):
		index=None
		if not listlock:
			listlock=qtcore.QWriteLocker(self.layerslistlock)

		if layer.type==LayerTypes.floating:
			parent=layer.getParent()
			if parent:
				layer.changeParent(None)
				self.setValidActiveLayer(True,listlock=listlock)
				self.requestLayerListRefresh(listlock)

				command=RemoveFloatingCommand(layer,parent.key)
				self.addCommandToHistory(command)

		else:
			(layer,index)=BeeSessionState.removeLayer(self,layer,history=history,listlock=listlock)
			if layer:
				self.scene.removeItem(layer)

				self.scene.update()
				self.setValidActiveLayer(True,listlock=listlock)

		return layer,index

	def insertRawLayer(self,layer,index,listlock=None):
		if not listlock:
			listlock=qtcore.QWriteLocker(self.layerslistlock)

		try:
			self.layers.insert(index,layer)
		except:
			self.layers.append(layer)

		self.scene.addItem(layer)

		listlock.unlock()

		self.setValidActiveLayer()
		self.requestLayerListRefresh()
		self.reCompositeImage()

	def insertLayer(self,key,index,type=LayerTypes.user,image=None,opacity=None,visible=None,compmode=None,owner=0,history=True,lock=None):
		if not lock:
			lock=qtcore.QWriteLocker(self.layerslistlock)

		# make sure layer doesn't exist already
		oldlayer=self.getLayerForKey(key,lock=lock)

		if oldlayer:
			print_debug("ERROR: tried to create layer with same key as existing layer")
			return

		layer=BeeGuiLayer(self.id,type,key,image,opacity=opacity,visible=visible,compmode=compmode,owner=owner,scene=self.scene)

		try:
			self.layers.insert(index,layer)
		except:
			self.layers.append(layer)

		self.resetLayerZValues(lock=lock)

		# only add command to history if we are in a local session
		if self.type==WindowTypes.singleuser and history:
			self.addCommandToHistory(AddLayerCommand(layer.key))

		#self.scene.addItem(layer)
		lock.unlock()

		self.setValidActiveLayer()
		self.requestLayerListRefresh()
		self.reCompositeImage()

	# recomposite all layers together into the displayed image
	# when a thread calls this method it shouldn't have a lock on any layers
	def reCompositeImage(self,dirtyrect=None):
		if dirtyrect:
			self.view.updateView(qtcore.QRectF(dirtyrect))
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

	def mdiWinStateChange(self,oldstate,newstate):
		if newstate & qtcore.Qt.WindowActive:
			self.master.takeFocus(self)

	# handle a few events that don't have easy function over loading front ends
	def event(self,event):
		# do the last part of setup when the window is done being created, this is so nothing starts drawing on the screen before it is ready
		if event.type()==qtcore.QEvent.WindowActivate:
			if self.activated==False:
				self.activated=True
				self.reCompositeImage()
				self.startRemoteDrawingThreads()

		elif event.type()==qtcore.QEvent.Show:
			if self.activated==False:
				self.activated=True
				self.reCompositeImage()
				self.startRemoteDrawingThreads()

		elif event.type()==BeeCustomEventTypes.displaymessage:
			self.displayMessage(event.boxtype,event.title,event.message)

		elif event.type()==BeeCustomEventTypes.updateselectiondisplay:
			self.selectiondisplay.updatePath(event.path)

		# once the window has received a deferred delete it needs to have all it's references removed so memory can be freed up
		elif event.type()==qtcore.QEvent.DeferredDelete:
			self.cleanUp()

		return qtgui.QWidget.event(self,event)

# get the current layer key
	def getCurLayerKey(self,curlayerlock=None):
		if not curlayerlock:
			curlayerlock=qtcore.QMutexLocker(self.curlayerkeymutex)
		return self.curlayerkey

	def findValidLayer(self,layerslock=None):
		if not layerslock:
			layerslock=qtcore.QReadLocker(self.layerslistlock)

		for layer in self.layers:
			if self.ownedByMe(self.layer.owner):
				return layer

		return None

	def getCurLayer(self):
		if self.layers:
			if self.getLayerForKey(self.curlayerkey):
				return self.getLayerForKey(self.curlayerkey)
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
	def on_action_Edit_Cut_triggered(self,accept=True):
		if accept:
			self.addCutToQueue()

	def on_action_Edit_Copy_triggered(self,accept=True):
		if accept:
			self.addCopyToQueue()

	def on_action_Edit_Paste_triggered(self,accept=True):
		if accept:
			x,y=self.view.snapPointToView(0,0)
			self.addPasteToQueue(x,y)

	def on_action_Edit_Undo_triggered(self,accept=True):
		if accept:
			self.addUndoToQueue()

	def on_action_Edit_Redo_triggered(self,accept=True):
		if accept:
			self.addRedoToQueue()

	def on_action_Select_None_triggered(self,accept=True):
		if accept:
			self.addSelectionChangeToQueue(SelectionModTypes.clear,None)

	def on_action_Select_Invert_Selection_triggered(self,accept=True):
		if accept:
			self.addSelectionChangeToQueue(SelectionModTypes.invert,None)

	def on_action_Select_Grow_Selection_triggered(self,accept=True):
		if accept:
			dialog=qtgui.QDialog(self)
			dialog.ui=Ui_Grow_Selection_Dialog()
			dialog.ui.setupUi(dialog)

			dialog.exec_()

			if dialog.result():
				pixels=dialog.ui.SpinBox_grow.value()

				self.addSelectionChangeToQueue(SelectionModTypes.grow,pixels)

	def on_action_Select_Shrink_Selection_triggered(self,accept=True):
		if accept:
			dialog=qtgui.QDialog(self)
			dialog.ui=Ui_Shrink_Selection_Dialog()
			dialog.ui.setupUi(dialog)

			dialog.exec_()

			if dialog.result():
				pixels=dialog.ui.SpinBox_shrink.value()

				self.addSelectionChangeToQueue(SelectionModTypes.shrink,pixels)

	def on_action_View_Zoom_In_triggered(self,accept=True):
		if accept:
			#self.zoom*=1.25
			self.zoom*=2
			self.view.newZoom(self.zoom)

	def on_action_View_Zoom_Out_triggered(self,accept=True):
		if accept:
			#self.zoom/=1.25
			self.zoom/=2
			self.view.newZoom(self.zoom)

	def on_action_View_Zoom_1_1_triggered(self,accept=True):
		if accept:
			self.zoom=1.0
			self.view.newZoom(self.zoom)

	def on_action_Image_Scale_Image_triggered(self,accept=True):
		if accept:
			width,height=self.getDocSize()

			dialog=BeeScaleImageDialog(self,width,height)

			dialog.exec_()

			if dialog.result():
				newwidth=dialog.ui.width_spin_box.value()
				newheight=dialog.ui.height_spin_box.value()

				self.addScaleCanvasToQueue(newwidth,newheight)

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

	def on_action_Image_Flatten_Image_triggered(self,accept=True):
		if accept:
			self.addFlattenImageToQueue()

	def flattenImage(self,listlock=None,history=True):
		# lock the list of layers and all the layer images
		if not listlock:
			listlock=qtcore.QWriteLocker(self.layerslistlock)

		# we need at least two layers and the layer finisher layer to have this operation actually do something
		if len(self.scene.items())<3:
			return

		layerlocks=[]
		for l in self.layers:
			layerlocks.append(qtcore.QReadLocker(l.imagelock))

		sceneimage=self.scene.getImageCopy()

		newkey=self.nextLayerKey()
		newlayer=BeeGuiLayer(self.id,LayerTypes.user,newkey,sceneimage)

		oldlayers=[]
		layers=self.layers[:]
		for l in layers:
			layer,index=self.removeLayer(l,history=False,listlock=listlock)
			oldlayers.append(layer)

		newlayer.image=sceneimage

		self.scene.update()

		self.insertLayer(self.nextLayerKey(),0,history=False,image=sceneimage,lock=listlock)

		if history:
			historyevent=FlattenImageCommand(oldlayers)
			self.addCommandToHistory(historyevent)

	def addSelectionChangeToQueue(self,selectionop,path):
		self.queueCommand((DrawingCommandTypes.localonly,LocalOnlyCommandTypes.selection,selectionop,path),ThreadTypes.user)

	def addPasteToQueue(self,x=0,y=0):
		# It is only possible for this to happen from a local source so it's defined here instead of in the base state class.
		layerkey=self.getCurLayerKey()
		# don't do anything if there is no current layer
		if layerkey:
			# make sure layer is owned locally so it can be altered
			if self.localLayer(layerkey):
				self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.paste,layerkey,x,y),ThreadTypes.user)

	def addCopyToQueue(self):
		# It is only possible for this to happen from a local source so it's defined here instead of in the base state class.
		layerkey=self.getCurLayerKey()
		# don't do anything if there is no current layer
		if layerkey:
			path=self.getClipPathCopy()
			if path and not path.isEmpty():
				self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.copy,layerkey,path),ThreadTypes.user)

	def addCutToQueue(self):
		# It is only possible for this to happen from a local source so it's defined here instead of in the base state class.
		layerkey=self.getCurLayerKey()

		# make sure current layer is valid
		if layerkey:
			# make sure layer is owned locally so it can be altered
			if self.localLayer(layerkey):
				clippath=self.getClipPathCopy()
				if clippath and not clippath.isEmpty():
					self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.cut,layerkey,clippath),ThreadTypes.user)

					# deselect everything when we do this
					self.changeSelection(SelectionModTypes.clear,history=False)

	def addAnchorToQueue(self,parentkey,floating):
		pos=floating.pos()
		x=pos.x()
		y=pos.y()
		image=floating.getImageCopy()
		clippath=None
		compmode=floating.getCompmode()
		alphachannel=qtgui.QImage(image.size(),qtgui.QImage.Format_ARGB32_Premultiplied)

		# fade image if the opacity is less than full
		alphaammount=int(255*floating.getOpacity())
		if alphaammount < 255:
			alphachannel.fill(qtgui.QColor(0,0,0,alphaammount).rgba())
			#image.setAlphaChannel(alphachannel)
			painter=qtgui.QPainter()
			painter.begin(image)
			painter.setCompositionMode(qtgui.QPainter.CompositionMode_DestinationIn)
			painter.drawImage(0,0,alphachannel)
			painter.end()
		
		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.anchor,parentkey,x,y,image,clippath,compmode,floating),ThreadTypes.user)

	# create backdrop for bottom of all layers, eventually I'd like this to be configurable, but for now it just fills in all white
	def recreateBackdrop(self):
		self.backdrop=qtgui.QImage(self.docwidth,self.docheight,qtgui.QImage.Format_ARGB32_Premultiplied)
		self.backdrop.fill(self.backdropcolor)

	def on_action_File_Log_toggled(self,state):
		"""If log box is now checked ask user to provide log file name and start a log file for the current session from this point
		If log box is now unchecked end the current log file
		"""
		if state:
			filename=qtgui.QFileDialog.getSaveFileName(self.master,"Choose File Name",".","Logfiles (*.slg)")
			if not filename:
				return
			self.startLog(filename)
		else:
			self.endLog()

	def on_action_File_New_triggered(self,accept=True):
		if not accept:
			return

		self.master.on_action_File_New_triggered()

	def on_action_File_Open_triggered(self,accept=True):
		if not accept:
			return

		self.master.on_action_File_Open_triggered()

	def on_action_File_Play_triggered(self,accept=True):
		if not accept:
			return

		self.master.on_action_File_Play_triggered()

	def on_action_File_Connect_triggered(self,accept=True):
		if not accept:
			return

		self.master.on_action_File_Connect_triggered()

	def on_action_File_Save_triggered(self,accept=True):
		if not self.filename:
			self.on_action_File_Save_As_triggered()
			return

		self.saveFile(self.filename)

	def on_action_File_Save_As_triggered(self,accept=True):
		if not accept:
			return

		filterstring=qtcore.QString("Images (")
		formats=getSupportedWriteFileFormats()
		for f in formats:
			filterstring.append(" *.")
			filterstring.append(f)

		# add in extension for custom file format
		filterstring.append(" *.bee)")

		filename=qtgui.QFileDialog.getSaveFileName(self.master,"Choose File Name",".",filterstring)
		if filename:
			self.saveFile(filename)

		self.setFileName(filename)

	def on_action_File_Close_triggered(self,accept=True):
		if accept:
			self.closeDrawingWindow()

	def closeDrawingWindow(self):
		parent=self.parentWidget()
		if parent:
			parent.close()

	# this is here because the window doesn't seem to get deleted when it's closed
	# the cleanUp function attempts to clean up as much memory as possible
	def cleanUp(self):
		#print "ref counts at beginning of cleanup:", sys.getrefcount(self)
		# end the log if there is one
		self.endLog()

		self.selectiondisplay.cleanUp()

		self.localdrawingthread.addExitEventToQueue()
		if not self.localdrawingthread.wait(10000):
			print_debug("WARNING: drawing thread did not terminate on time")

		# if we started a remote drawing thread kill it
		if self.remotedrawingthread:
			self.remotedrawingthread.addExitEventToQueue()
			if not self.remotedrawingthread.wait(20000):
				print_debug("WARNING: remote drawing thread did not terminate on time")

		self.scene.removeItem(self.selectiondisplay)
		self.selectiondisplay=None

		self.scene.removeItem(self.layerfinisher)

		if self.tooloverlay:
			self.scene.removeItem(self.tooloverlay)

		# this should be the last referece to the window
		self.master.unregisterWindow(self)

		self.localcommandstack=None

		#print "ref counts after cleanup:", sys.getrefcount(self)

	# just in case someone lets up on the cursor when outside the drawing area this will make sure it's caught
	def tabletEvent(self,event):
		if event.type()==qtcore.QEvent.TabletRelease:
			self.view.cursorReleaseEvent(event.x(),event.y(),event.modifiers())
		return qtgui.QWidget.tabletEvent(self,event)

	def getLayerForKey(self,key,lock=None):
		if key==None:
			return None

		if not lock:
			lock=qtcore.QReadLocker(self.layerslistlock)

		for layer in self.layers:
			if layer.key==key:
				return layer

			for child in layer.sublayers:
				if child.key==key:
					return child

		return None

	def findValidLayer(self,listlock=None):
		if not listlock:
			listlock=qtcore.QReadLocker(self.layerslistlock)

		for curlayer in self.layers:
			if self.ownedByMe(curlayer.getOwner()):
				return curlayer

		return None

	def setValidActiveLayer(self,curlayerkeylock=None,listlock=None):
		needchange=False
		if not curlayerkeylock:
			curlayerkeylock=qtcore.QMutexLocker(self.curlayerkeymutex)
		curlayer=self.getLayerForKey(self.curlayerkey,listlock)
		if not curlayer:
			needchange=True
		elif self.type==WindowTypes.networkclient:
			if not self.ownedByMe(curlayer.getOwner()):
				needchange=True

		if needchange:
			if not listlock:
				listlock=qtcore.QReadLocker(self.layerslistlock)
			for layer in self.layers:
				if self.ownedByMe(layer.getOwner()):
					self.setActiveLayer(layer.key,curlayerkeylock)
					return layer.key

			self.setActiveLayer(None,curlayerkeylock)
			return None

		return self.curlayerkey

	def setActiveLayer(self,newkey,lock=None):
		if not lock:
			lock=qtcore.QMutexLocker(self.curlayerkeymutex)

		oldkey=self.curlayerkey
		oldkey=self.getCurLayerKey(lock)
		self.curlayerkey=newkey
		self.master.updateLayerHighlight(self,newkey,lock)
		self.master.updateLayerHighlight(self,oldkey,lock)

	def switchAllLayersToLocal(self):
		lock=qtcore.QReadLocker(self.layerslistlock)
		for layer in self.layers:
			layer.type=LayerTypes.user
			layer.changeName("Layer: %d" % layer.key)

	# delete all layers
	def clearAllLayers(self):
		# lock all layers and the layers list
		lock=qtcore.QWriteLocker(self.layerslistlock)
		for layer in self.layers[:]:
			self.removeLayer(layer,history=False,lock=lock)

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
	def __init__(self,parent,socket,maxundo=20):
		self.socket=socket
		BeeDrawingWindow.__init__(self,parent,startlayer=False,type=WindowTypes.networkclient,maxundo=maxundo)

		self.disconnectmessage="No Response From Server"
		# disable options that can't be used in network sessions
		#self.ui.action_Image_Scale_Image.setDisabled(True)

		# enable/disable menu options for network window
		self.imagemenu.setDisabled(True)
		#self.networkmenu.setEnabled(True)

		# setup command stack with 0 size network history, this should get reset during intialization
		self.localcommandstack.changeToNetwork()

	def setDisconnectMessage(self,message):
		self.disconnectmessage=message

	# do what's needed to start up any network threads
	def startRemoteDrawingThreads(self):
		self.listenerthread=NetworkListenerThread(self.id,self.socket)
		self.listenerthread.start()

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
		self.switchToSingleUser()
		requestDisplayMessage(BeeDisplayMessageTypes.warning,"Network Session has ended","Connection has been broken: " + self.disconnectmessage,self)

	def switchToSingleUser(self):
		# change command stack to single user
		localcommand=self.localcommandstack
		if localcommand:
			localcommand.changeToLocal()
		# get rid of all remote command stacks
		self.remotecommandstacks={}

		# switch around which menus are active
		#self.networkmenu.setDisabled(True)
		self.imagemenu.setEnabled(True)

	# add an event to the undo/redo history
	def addCommandToHistory(self,command,source=0):
		# if we don't get a source then assume that it's local
		if self.ownedByMe(source) or source<=0:
			self.localcommandstack.add(command)
		# else add it to proper remote command stack, add stack if needed
		elif source in self.remotecommandstacks:
			self.remotecommandstacks[source].add(command)
		else:
			self.remotecommandstacks[source]=CommandStack(self,CommandStackTypes.remoteonly,maxundo=self.getNetworkHistorySize())
			self.remotecommandstacks[source].add(command)

	def cleanUp(self):
		BeeDrawingWindow.cleanUp(self)
		self.remotecommandstacks=None
		self.socket.disconnect()
		self.socket=None
		self.listenerthread.terminate()
		#self.listenerthread.wait(10000)
		#self.listenerthread=None
