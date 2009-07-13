#!/usr/bin/python

from beesessionstate import BeeSessionState
from drawingthread import ServerDrawingThread
from beetypes import *

class HiveSessionState(BeeSessionState):
	def __init__(self,master,width,height,type,maxundo):
		BeeSessionState.__init__(self,master,width,height,type)
		self.commandcaches={}
		self.commandindexes={}
		self.historysize=maxundo
		self.master=master

	def startRemoteDrawingThreads(self):
		# start remote command thread
		self.remotedrawingthread=ServerDrawingThread(self.remotecommandqueue,self.id,master=self.master)
		self.remotedrawingthread.start()

	# send full resync to client with given ID
	def sendLayersToClient(self,id):
		# get a read lock on all layers and the list of layers
		listlock=qtcore.QMutexLocker(self.layersmutex)
		locklist=[]
		for layer in self.layers:
			locklist.append(qtcore.QReadLocker(layer.imagelock))

		# send each layer to client
		index=0
		for layer in self.layers:
			index+=1
			self.sendLayerImageToClient(layer,index,id)

	def sendLayerImageToClient(self,layer,index,id):
		key=layer.key
		image=layer.getImageCopy()
		opacity=layer.opacity
		compmode=layer.compmode
		owner=layer.owner

		# send command to create layer
		insertcommand=(DrawingCommandTypes.alllayer,AllLayerCommandTypes.insertlayer,key,index,owner)
		self.master.routinginput.put((insertcommand,id*-1))

		# set alpha and composition mode for layer
		alphacommand=(DrawingCommandTypes.layer,LayerCommandTypes.alpha,key,opacity)
		self.master.routinginput.put((alphacommand,id*-1))
		modecommand=(DrawingCommandTypes.layer,LayerCommandTypes.mode,key,compmode)
		self.master.routinginput.put((modecommand,id*-1))

		# send raw image
		rawcommand=(DrawingCommandTypes.layer,LayerCommandTypes.rawevent,key,0,0,image,None)
		self.master.routinginput.put((rawcommand,id*-1))

	def addLayerRequestToQueue(self,layerkey,owner=0,source=ThreadTypes.network):
		self.queueCommand((DrawingCommandTypes.networkcontrol,NetworkControlCommandTypes.requestlayer,owner,layerkey),source)

	def addResyncRequestToQueue(self,owner=0,source=ThreadTypes.network):
		self.queueCommand((DrawingCommandTypes.networkcontrol,NetworkControlCommandTypes.resyncrequest,owner),source)

	def queueCommand(self,command,source=ThreadTypes.server,owner=0):
		self.remotecommandqueue.put(command)

	# the history is taken care of elsewhere
	def addCommandToHistory(self,command,source=0):
		pass
