#!/usr/bin/env python

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui

from beeapp import BeeApp

from beetypes import *

from beeeventstack import CommandStack

from beelayer import BeeLayer
from beeeventstack import *

from Queue import Queue

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

		# set unique ID
		self.id=master.getNextWindowId()

		# register state so the master can get back to here
		master.registerWindow(self)

		self.selection=[]

		# initialize values
		self.backdropcolor=0xFFFFFFFF
		self.log=None
		self.remotecommandstacks={}
		self.curlayerkey=None

		self.imagelock=qtcore.QReadWriteLock()
		self.docsizelock=qtcore.QReadWriteLock()

		self.nextlayerkey=0
		self.nextlayerkeymutex=qtcore.QMutex()

		self.remotecommandqueue=Queue(0)
		self.remoteoutputqueue=Queue(0)
		self.remotedrawingthread=None

		self.layers=[]
		self.layersmutex=qtcore.QMutex()

	def setRemoteId(self,id):
		lock=qtcore.QWriteLocker(self.remoteidlock)
		self.remoteid=id

	def ownedByMe(self,owner):
		""" return True if the layer is under the control of this state keeper or false if it's under the control of something else (ie an animation process or a network client
		"""
		lock=qtcore.QReadLocker(self.remoteidlock)
		if owner==0 or owner==self.remoteid:
			return True
		return False

	def addRemoveLayerRequestToQueue(self,key,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.deletelayer,key),source)

	def removeLayerByKey(self,key,history=0):
		""" remove layer with key equal to passed value, each layer should have a unique key so there is no need to check for multiples
      The history argument is 0 if the event should be added to the undo/redo history and -1 if it shouldn't.  This is needed so when running an undo/redo command it doesn't get added again.
		"""
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
			# layer movment operations can't be undone with an undo command when in a network session
			if self.type==WindowTypes.singleuser:
				self.addCommandToHistory(LayerDownCommand(key))

	def addLayerUpToQueue(self,key,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.layerup,key),source)

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

	def reCompositeImage(self,dirtyrect=None):
		""" This is not needed to actually do anything in all state keepers, but it needs to be here so it can be called
		"""
		pass

	def addPenDownToQueue(self,x,y,pressure,layerkey=None,tool=None,source=ThreadTypes.user,owner=0):
		if not tool:
			tool=self.master.getCurToolInst(self)
			self.curtool=tool

		if layerkey==None:
			layerkey=self.getCurLayerKey()

		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.pendown,layerkey,x,y,pressure,tool),source)

	def addPenMotionToQueue(self,x,y,pressure,layerkey=None,source=ThreadTypes.user):
		if layerkey==None:
			layerkey=self.curlayerkey

		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.penmotion,layerkey,x,y,pressure),source)

	def addPenUpToQueue(self,x,y,layerkey=None,source=ThreadTypes.user):
		if layerkey==None:
			layerkey=self.curlayerkey

		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.penup,layerkey,x,y),source)

	def recreateBackdrop(self):
		"""only needs to be imlemented in subclasses that need to display the session"""
		pass

	def startLog(self,filename=None):
		""" start logging the session, starting with a base image of it in it's current state, if no file name is provided use make a name up based on current time
		"""
		if not filename:
			filename=os.path.join('logs',str(datetime.now()) + '.slg')

		locks=[]
		self.filename=filename

		self.logfile=qtcore.QFile(self.filename)
		self.logfile.open(qtcore.QIODevice.WriteOnly)
		log=SketchLogWriter(self.logfile)

		# lock for reading the size of the document
		sizelocker=ReadWriteLocker(self.docsizelock)
		log.logResyncStart(self.docwidth,self.docheight,0)
		# log everything to get upto this point
		pos=0
		for layer in self.layers:
			locks.append(ReadWriteLocker(layer.imagelock,True))
			log.logLayerAdd(pos,layer.key)
			log.logRawEvent(0,0,layer.key,layer.image)
			pos+=1

		self.log=log

	def endLog(self):
		""" if there is a log started end it """
		if self.log:
			self.log.endLog()
			self.log=None

	def loadLayer(self,image,type=LayerTypes.user,key=None,index=None, opacity=None, visible=None, compmode=None):
		""" this is for inserting a layer with a given image, for instance if loading from a log file with a partially started drawing """
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
		#print "calling insertLayer"
		layer=BeeLayer(self.id,type,key,image,opacity=opacity,visible=visible,compmode=compmode,owner=owner)

		self.layers.insert(index,layer)

		# only select it immediately if we can draw on it
		if type==LayerTypes.user:
			self.curlayerkey=key

		# only add command to history if we are in a local session
		if self.type==WindowTypes.singleuser and history!=-1:
			self.addCommandToHistory(AddLayerCommand(layer.key))

		self.requestLayerListRefresh()

	def requestLayerListRefresh(self):
		""" Only needed in subclasses that display a list of layers
		"""
		pass

	def nextLayerKey(self):
		# get a lock so we don't get a collision ever
		lock=qtcore.QMutexLocker(self.nextlayerkeymutex)

		key=self.nextlayerkey
		self.nextlayerkey+=1
		return key

	def queueCommand(self,command,source=ThreadTypes.user,owner=0):
		""" This needs to be reimplemented in subclass """
		pass

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

	def addSetCanvasSizeRequestToQueue(self,width,height,source=ThreadTypes.user,owner=0):
		# lock for reading the size of the document
		lock=ReadWriteLocker(self.docsizelock)
		if width!=self.docwidth or height!=self.docheight:
			#print "changing size from:", self.docwidth, self.docheight, "to size:", width, height
			self.addAdjustCanvasSizeRequestToQueue(0,0,width-self.docwidth,height-self.docheight,source,owner)

	def addAdjustCanvasSizeRequestToQueue(self,leftadj,topadj,rightadj,bottomadj,source=ThreadTypes.user,owner=0):
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.resize,leftadj,topadj,rightadj,bottomadj),source,owner)

	def setCanvasSize(self,width,height):
		lock=ReadWriteLocker(self.docsizelock,False)
		rightadj=width-self.docwidth
		bottomadj=height-self.docheight
		lock.unlock()
		self.adjustCanvasSize(0,0,rightadj,bottomadj)

	# grow or crop canvas according to adjustments on each side
	def adjustCanvasSize(self,leftadj,topadj,rightadj,bottomadj):
		# get lock on adjusting the document size
		sizelock=ReadWriteLocker(self.docsizelock,True)

		self.docwidth=self.docwidth+leftadj+rightadj
		self.docheight=self.docheight+topadj+bottomadj

		# update all layer preview thumbnails
		self.master.refreshLayerThumb(self.id)

	def addInsertLayerEventToQueue(self,index,key,source=ThreadTypes.user,owner=0):
		# when the source is local like this the owner will always be me (id 0)
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.insertlayer,key,index,owner),source,owner)
		return key

	def addLayer(self):
		#print "calling nextLayerKey from beedrawingwindow addLayer"
		key=self.nextLayerKey()
		index=len(self.layers)
		# when the source is local like this the owner will always be me (id 0)
		self.queueCommand((DrawingCommandTypes.alllayer,AllLayerCommandTypes.insertlayer,key,index,0))

	def addRawEventToQueue(self,key,image,x,y,path,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.rawevent,key,x,y,image,path),source)

	def addResyncStartToQueue(self,width,height,remoteid,source=ThreadTypes.network):
		self.queueCommand((DrawingCommandTypes.networkcontrol,NetworkControlCommandTypes.resyncstart,width,height,remoteid),source)

	def addOpacityChangeToQueue(self,key,value,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.alpha,key,value),source)

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

	def logStroke(self,tool,layer,source=ThreadTypes.network):
		if self.log:
			self.log.logToolEvent(tool)

		if self.type==WindowTypes.networkclient and source==ThreadTypes.user:
			self.remoteoutputqueue.put((DrawingCommandTypes.layer,LayerCommandTypes.tool,tool.layerkey,tool))

		elif self.type==WindowTypes.standaloneserver:
			layer=self.getLayerForKey(tool.layerkey)
			if not layer:
				print "couldn't find layer when logging stroke"
				return
			print "logging stroke from owner:", layer.owner
			self.master.routinginput.put(((DrawingCommandTypes.layer,LayerCommandTypes.tool,tool.layerkey,tool),layer.owner))

	# add an event to the undo/redo history
	def addCommandToHistory(self,command,source=0):
		print "adding command to history from source:", source
		# if we don't get a source then assume that it's local
		if self.ownedByMe(source):
			self.localcommandstack.add(command)
		# else add it to proper remote command stack, add stack if needed
		elif source in self.remotecommandstacks:
			self.remotecommandstacks[source].add(command)
		else:
			self.remotecommandstacks[source]=CommandStack(self.id)
			self.remotecommandstacks[source].add(command)

	def addUndoToQueue(self,owner=0,source=ThreadTypes.user):
		if not owner:
			owner=self.remoteid
		command=(DrawingCommandTypes.history,HistoryCommandTypes.undo,owner)
		self.queueCommand(command,source)

	def addRedoToQueue(self,owner=0,source=ThreadTypes.user):
		self.queueCommand((DrawingCommandTypes.history,HistoryCommandTypes.redo,owner),source)

	# undo last event in stack for passed client id
	def undo(self,source=0):
		print "Undo called on source:", source
		if self.ownedByMe(source):
			self.localcommandstack.undo()
		else:
			if source in self.remotecommandstacks:
				self.remotecommandstacks[source].undo()
			else:
				print "ERROR: recieved undo for blank remote command stack:", source

	# redo last event in stack for passed client id
	def redo(self,source=0):
		# if we don't get a source then assume that it's local
		if source==0:
			self.localcommandstack.redo()
		else:
			self.remotecommandstacks[source].redo()

	def refreshLayerThumb(self,window,id):
		pass
