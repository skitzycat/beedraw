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

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui

from sketchlog import SketchLogWriter
from beeapp import BeeApp
from beetypes import *
from beeeventstack import *
from beelayer import BeeLayerState
from beeutil import getTimeString

from Queue import Queue
import os
from datetime import datetime

class BeeSessionState:
	""" Represents the state of a current drawing with all layers and the current composition of them to be displayed on the screen
	"""
	def __init__(self,master,width,height,type):
		# save passed values
		self.docwidth=width
		self.docheight=height
		self.type=type
		self.master=master

		self.remoteidlock=qtcore.QReadWriteLock()
		self.remoteid=0

		self.historysize=20

		self.layers=[]
		# mutex for messing with the list of layer: adding, removing or rearranging
		self.layerslistlock=qtcore.QReadWriteLock()

		# never have a local clip path
		self.clippath=None

		# set unique ID
		self.id=master.getNextWindowId()

		# initialize values
		self.backdropcolor=0xFFFFFFFF
		self.remotecommandstacks={}
		self.curlayerkey=None
		self.curlayerkeymutex=qtcore.QMutex()

		self.docsizelock=qtcore.QReadWriteLock()

		self.nextlayerkey=1
		self.nextlayerkeymutex=qtcore.QMutex()

		self.remotecommandqueue=Queue(0)
		self.remoteoutputqueue=Queue(0)
		self.remotedrawingthread=None

		# register state so the master can get back to here
		master.registerWindow(self)

		# start log if autolog is enabled
		self.log=None
		if self.master.getConfigOption("autolog"):
			# don't do this for animations, there's already a log of it if there's an animation
			if type!=WindowTypes.animation:
				self.startLog()

		self.curtool=None

	def setRemoteId(self,id):
		lock=qtcore.QWriteLocker(self.remoteidlock)
		self.remoteid=id

	def ownedByNobody(self,owner):
		if self.type==WindowTypes.networkclient or self.type==WindowTypes.standaloneserver or self.type==WindowTypes.integratedserver:
			if owner==0:
				return True
		return False

	def localLayer(self,layerkey):
		""" return True if the key passed is for a layer that is local, False otherwise """
		layer=self.getLayerForKey(layerkey)
		proplock=qtcore.QReadLocker(layer.propertieslock)
		return self.ownedByMe(layer.owner)

	def ownedByMe(self,owner):
		""" return True if the layer is under the control of this state keeper or False if it's under the control of something else (ie an animation process or another network client or unowned by anyone in a network session)
		"""
		lock=qtcore.QReadLocker(self.remoteidlock)
		if self.type==WindowTypes.networkclient or self.type==WindowTypes.standaloneserver or self.type==WindowTypes.integratedserver:
			if owner==self.remoteid:
				return True
		elif owner==0 or owner==self.remoteid:
			return True
		return False

	def deleteLayerHistory(self,oldowner,layerkey):
		if self.ownedByMe(oldowner):
			self.localcommandstack.cleanLocalLayerHistory()
		elif oldowner in self.remotecommandstacks:
			self.remotecommandstacks[oldowner].cleanRemoteLayerHistory(layerkey)

	def addGiveUpLayerToQueue(self,key,id=0,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.networkcontrol,NetworkControlCommandTypes.giveuplayer,id,key),source)

	def addChangeLayerOwnerToQueue(self,key,owner,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.networkcontrol,NetworkControlCommandTypes.layerowner,owner,key),source)

	def addRequestLayerToQueue(self,key,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.networkcontrol,NetworkControlCommandTypes.requestlayer,0,key),source)

	def addRemoveLayerRequestToQueue(self,key,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.deletelayer,key),source)

	def addExitEventToQueue(self,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.quit,),source)

	def removeLayer(self,layer,history=True,listlock=None):
		if layer:
			if not listlock:
				listlock=qtcore.QWriteLocker(self.layerslistlock)
			if layer in self.layers:
				index=self.layers.index(layer)
				if history:
					self.addCommandToHistory(DelLayerCommand(layer,index))
				self.layers.pop(index)

				self.requestLayerListRefresh(listlock)
				self.reCompositeImage()
				return (layer,index)

		return (None,None)

	def removeLayerByKey(self,key,history=False,lock=None):
		""" remove layer with key equal to passed value, each layer should have a unique key so there is no need to check for multiples
      The history argument is 0 if the event should be added to the undo/redo history and -1 if it shouldn't.  This is needed so when running an undo/redo command it doesn't get added again.
		"""
		print_debug("calling removeLayerByKey for %d" % key)
		# get a lock so we don't get a collision ever
		if not lock:
			lock=qtcore.QWriteLocker(self.layerslistlock)

		curlaylock=qtcore.QMutexLocker(self.curlayerkeymutex)
		
		layer=self.getLayerForKey(key,lock)
		return self.removeLayer(layer,history,lock)

	def addLayerDownToQueue(self,key,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.layerdown,key),source)

	def layerDown(self,key,history=True):
		index=self.getLayerIndexForKey(key)
		lock=qtcore.QWriteLocker(self.layerslistlock)
		if index>0:
			self.layers[index],self.layers[index-1]=self.layers[index-1],self.layers[index]
			lock.unlock()
			self.reCompositeImage()
			self.requestLayerListRefresh()

			# if we are only running locally add command to local history
			# otherwise do nothing
			# layer movment operations can't be undone with an undo command when in a network session
			if self.type==WindowTypes.singleuser and history:
				self.addCommandToHistory(LayerDownCommand(key))

	def addLayerUpToQueue(self,key,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.layerup,key),source)

	def layerUp(self,key,history=True):
		lock=qtcore.QWriteLocker(self.layerslistlock)
		index=self.getLayerIndexForKey(key)
		if index==None:
			return
		if index<len(self.layers)-1:
			self.layers[index],self.layers[index+1]=self.layers[index+1],self.layers[index]
			lock.unlock()
			self.requestLayerListRefresh()
			self.reCompositeImage()

			# if we are only running locally add command to local history
			# otherwise do nothing
			if self.type==WindowTypes.singleuser and history:
				self.addCommandToHistory(LayerUpCommand(key))

	def reCompositeImage(self,dirtyrect=None):
		""" This is not needed to actually do anything in all state keepers, but it needs to be here so it can be called
		"""
		pass

	def getClipPathCopy(self):
		return None

	def addPenEnterToQueue(self,layerkey=None,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.penenter,layerkey),source)

	def addPenLeaveToQueue(self,layerkey=None,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.penleave,layerkey),source)

	def addPenDownToQueue(self,x,y,pressure,layerkey,tool,source=ThreadTypes.user,modkeys=qtcore.Qt.NoModifier):
		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.pendown,layerkey,x,y,pressure,tool),source)

	def addPenMotionToQueue(self,x,y,pressure,layerkey,source=ThreadTypes.user,modkeys=qtcore.Qt.NoModifier):
		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.penmotion,layerkey,x,y,pressure),source)

	def addPenUpToQueue(self,x,y,layerkey,source=ThreadTypes.user,modkeys=qtcore.Qt.NoModifier):
		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.penup,layerkey,x,y),source)

	def recreateBackdrop(self):
		"""only needs to be imlemented in subclasses that need to display the session"""
		pass

	def startLog(self,filename=None,endlog=False):
		""" start logging the session, starting with a base image of it in it's current state, if no file name is provided use make a name up based on current time
		"""
		if not filename:
			filename=os.path.join('logs',getTimeString() + '.slg')

		locks=[]
		self.filename=filename

		logfile=qtcore.QFile(self.filename)
		logfile.open(qtcore.QIODevice.WriteOnly)
		log=SketchLogWriter(logfile)

		# lock for reading the size of the document
		sizelocker=qtcore.QReadLocker(self.docsizelock)
		log.logResyncStart(self.docwidth,self.docheight,0)
		# log everything to get upto this point
		pos=0
		for layer in self.layers:
			locks.append(qtcore.QWriteLocker(layer.imagelock))
			log.logLayerAdd(pos,layer.key, layer.image)
			#log.logRawEvent(0,0,layer.key,layer.image)
			pos+=1

		if endlog:
			self.endLog(log)
		else:
			self.log=log

	def endLog(self,log=None):
		""" if there is a log started end it """
		if log:
			log.endLog()
		elif self.log:
			self.log.endLog()
			self.log=None

	def loadLayer(self,image,type=LayerTypes.user,key=None,index=None, opacity=None, visible=None, compmode=None):
		""" this is for inserting a layer with a given image, for instance if loading from a log file with a partially started drawing """
		if not key:
			key=self.nextLayerKey()

		if not index:
			index=0

		self.insertLayer(key,index,type,image,opacity=opacity,visible=visible,compmode=compmode)

	def insertRawLayer(self,layer,index,history=0):
		self.layers.insert(index,layer)
		self.requestLayerListRefresh()
		self.reCompositeImage()
		curlaylock=qtcore.QMutexLocker(self.curlayerkeymutex)
		# only select it immediately if we can draw on it
		#if layer.type==LayerTypes.user:
		#	self.curlayerkey=layer.key

		# only add command to history if we should
		if self.type==WindowTypes.singleuser and history!=-1:
			self.addCommandToHistory(AddLayerCommand(layer.key))

	# insert a layer at a given point in the list of layers
	def insertLayer(self,key,index,type=LayerTypes.user,image=None,opacity=None,visible=None,compmode=None,owner=0,history=0):
		lock=qtcore.QWriteLocker(self.layerslistlock)

		# make sure layer doesn't exist already
		oldlayer=self.getLayerForKey(key,lock=lock)
		if oldlayer:
			print_debug("ERROR: tried to create layer with same key as existing layer")
			return
			
		layer=BeeLayerState(self.id,type,key,image,opacity=opacity,visible=visible,compmode=compmode,owner=owner)

		self.layers.insert(index,layer)

		# only add command to history if we are in a local session
		#if self.type==WindowTypes.singleuser and history!=-1:
		#	self.addCommandToHistory(AddLayerCommand(layer.key))

		#self.requestLayerListRefresh()
		#self.reCompositeImage()

	def requestLayerListRefresh(self,lock=None):
		""" Only needed in subclasses that display a list of layers
		"""
		pass

	def nextLayerKey(self):
		""" returns the next layer key available, thread safe """
		# get a lock so we don't get a collision ever
		lock=qtcore.QMutexLocker(self.nextlayerkeymutex)

		key=self.nextlayerkey
		self.nextlayerkey+=1
		return key

	def queueCommand(self,command,source=ThreadTypes.user,owner=0):
		""" This needs to be reimplemented in subclass """
		print_debug("ERROR: abstract call to queueCommand")

	# central function for finding a layer with a given key, right now layers are stored in a list to preserve order, eventually there may need to be an addintional dictionary to index them and make this faster when lots of layers are in the list
	def getLayerForKey(self,key,lock=None):
		""" Retruns a the BeeLayer object with the matching layer key """
		if not lock:
			lock=qtcore.QReadLocker(self.layerslistlock)
		for layer in self.layers:
			if layer.key==key:
				return layer
		if key==None:
			print_debug("WARNING: current layer key is None" )
		else:
			print_debug("WARNING: could not find layer for key %d" % int(key) )
		return None

	def getLayerIndexForKey(self,key):
		for index in range(len(self.layers)):
			if self.layers[index].key==key:
				return index
		if key==None:
			print_debug("WARNING: current layer key is None" )
		else:
			print_debug("WARNING: could not find layer for key %d" % int(key) )
		return None

	def addScaleCanvasToQueue(self,newwidth,newheight,source=ThreadTypes.user,owner=0):
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.scale,newwidth,newheight),source,owner)

	def getDocSize(self,sizelock=None):
		if not sizelock:
			sizelock=qtcore.QReadLocker(self.docsizelock)

		return (self.docwidth,self.docheight)

	def scaleCanvas(self,newwidth,newheight,sizelock=None,history=True):
		if not sizelock:
			sizelock=qtcore.QWriteLocker(self.docsizelock)

		layerlistlock=qtcore.QReadLocker(self.layerslistlock)

		layersimagelocks=[]

		for layer in self.layers:
			layersimagelocks.append(qtcore.QWriteLocker(layer.imagelock))

		if history:
			historycommand=ScaleImageCommand(self.docwidth,self.docheight,newwidth,newheight,self.layers)
			self.addCommandToHistory(historycommand)

		for layer in self.layers:
			layer.scale(newwidth,newheight,True)

		self.docwidth=newwidth
		self.docheight=newheight

		self.scene.update()
		self.master.refreshLayerThumb(self.id)

	def addSetCanvasSizeRequestToQueue(self,width,height,source=ThreadTypes.user,owner=0):
		# lock for reading the size of the document
		lock=qtcore.QReadLocker(self.docsizelock)
		if width!=self.docwidth or height!=self.docheight:
			self.addAdjustCanvasSizeRequestToQueue(0,0,width-self.docwidth,height-self.docheight,source,owner)

	def addAdjustCanvasSizeRequestToQueue(self,leftadj,topadj,rightadj,bottomadj,source=ThreadTypes.user,owner=0):
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.resize,leftadj,topadj,rightadj,bottomadj),source,owner)

	def setCanvasSize(self,width,height):
		sizelock=qtcore.QWriteLocker(self.docsizelock)
		rightadj=width-self.docwidth
		bottomadj=height-self.docheight
		self.adjustCanvasSize(0,0,rightadj,bottomadj,sizelock)

	# grow or crop canvas according to adjustments on each side
	def adjustCanvasSize(self,leftadj,topadj,rightadj,bottomadj,sizelock=None):
		# get lock on adjusting the document size
		if not sizelock:
			sizelock=qtcore.QWriteLocker(self.docsizelock)

		self.docwidth=self.docwidth+leftadj+rightadj
		self.docheight=self.docheight+topadj+bottomadj

		# update all layer preview thumbnails
		self.master.refreshLayerThumb(self.id)

	def addInsertLayerEventToQueue(self,index,key,image=None,source=ThreadTypes.user,owner=0):
		# when the source is local like this the owner will always be me (id 0)
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.insertlayer,key,index,image,owner),source,owner)
		return key

	def addLayer(self):
		key=self.nextLayerKey()
		index=len(self.layers)
		# when the source is local like this the owner will always be me (id 0)
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.insertlayer,key,index,None,0))

	def addRawEventToQueue(self,key,image,x,y,path,compmode=qtgui.QPainter.CompositionMode_SourceOver,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.rawevent,key,x,y,image,path,compmode),source)

	def addResyncStartToQueue(self,remoteid,width,height,source=ThreadTypes.network):
		self.queueCommand((DrawingCommandTypes.networkcontrol,NetworkControlCommandTypes.resyncstart,remoteid,width,height),source)

	def addFatalErrorNotificationToQueue(self,remoteid,errormessage,source=ThreadTypes.network):
		self.queueCommand((DrawingCommandTypes.quit,),source)
		requestDisplayMessage(BeeDisplayMessageTypes.warning,"Network Session Ended","Server has severed connection due to: %s" % errormessage,self)

	def addOpacityChangeToQueue(self,key,value,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.alpha,key,value),source)

	def addOpacityDoneToQueue(self,key,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.alphadone,key),source)

	def addBlendModeChangeToQueue(self,key,value,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.mode,key,value),source)

	def logServerCommand(self,command,id=0):
		if self.log:
			self.log.logCommand(command)
		if self.type==WindowTypes.standaloneserver:
			self.master.routinginput.put((command,id))

	def logCommand(self,command,source=ThreadTypes.network):
		if self.log:
			self.log.logCommand(command)
		if self.type==WindowTypes.networkclient and source==ThreadTypes.user:
			self.remoteoutputqueue.put(command)

	def logStroke(self,tool,layerkey,source=ThreadTypes.network):
		# if the tool isn't suppose to be logged then don't do anything
		if tool.logtype==ToolLogTypes.unlogable:
			return

		layer=self.getLayerForKey(tool.layerkey)

		if tool.logtype==ToolLogTypes.regular:
			command=(DrawingCommandTypes.layer,LayerCommandTypes.tool,tool.layerkey,tool)
		elif tool.logtype==ToolLogTypes.raw:
			if tool.changedarea:
				imlock=qtcore.QReadLocker(layer.imagelock)
				stamp=layer.image.copy(tool.changedarea)
				command=(DrawingCommandTypes.layer,LayerCommandTypes.rawevent,tool.layerkey,tool.changedarea.x(),tool.changedarea.y(),stamp,None,qtgui.QPainter.CompositionMode_Source)
			else:
				print_debug("Warning: could not log tool as raw event, proper tool variables not set")
				return

		# if there is a local text log, then log it there
		if self.log:
			self.log.logCommand(command)

		# if this is part of a network session then send it out
		if self.type==WindowTypes.networkclient and source==ThreadTypes.user:
			self.remoteoutputqueue.put(command)

		elif self.type==WindowTypes.standaloneserver:
			layer=self.getLayerForKey(tool.layerkey)
			if not layer:
				print_debug("couldn't find layer when logging stroke")
				return
			self.master.routinginput.put((command,layer.owner))

	def setNetworkHistorySize(self,newsize):
		self.localcommandstack.setNetworkHistorySize(newsize)
		for key in self.remotecommandstacks.keys():
			self.remotecommandstacks[key].setHistorySize()

	def setHistorySize(self,newsize):
		self.localcommandstack.setHistorySize(newsize)

	# subclasses will redefine this if there's more than just the local history
	def addCommandToHistory(self,command,source=0):
		self.localcommandstack.add(command)

	def addUndoToQueue(self,owner=0,source=ThreadTypes.user):
		if not owner:
			owner=self.remoteid
		command=(DrawingCommandTypes.history,HistoryCommandTypes.undo,owner)
		self.queueCommand(command,source)

	def addRedoToQueue(self,owner=0,source=ThreadTypes.user):
		if not owner:
			owner=self.remoteid
		command=(DrawingCommandTypes.history,HistoryCommandTypes.redo,owner)
		self.queueCommand(command,source)

	# undo last event in stack for passed client id
	def undo(self,source=0):
		if self.ownedByMe(source):
			return self.localcommandstack.undo()
		else:
			if source in self.remotecommandstacks:
				return self.remotecommandstacks[source].undo()
			else:
				print_debug("ERROR: recieved undo for blank remote command stack: %d" % source)
		return UndoCommandTypes.none

	# redo last event in stack for passed client id
	def redo(self,source=0):
		# if we don't get a source then assume that it's local
		if self.ownedByMe(source):
			return self.localcommandstack.redo()
		else:
			return self.remotecommandstacks[source].redo()

		return UndoCommandTypes.none

	def refreshLayerThumb(self,window,id):
		pass

	def displayMessage(self,type,title,message):
		if type==BeeDisplayMessageTypes.warning:
			print "WARNING:", title, message
		elif type==BeeDisplayMessageTypes.error:
			print "ERROR:", title, message

	def removeOwner(self,id):
		""" find all layers with indicated owner and set them to be unowned, also remove all history for those layers, needs to be reimplemented in the subclass """
		pass

	
