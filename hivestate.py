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
		self.remotedrawingthread=ServerDrawingThread(self.remotecommandqueue,self.id,ThreadTypes.server,master=self.master)
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

	def addResyncRequestToQueue(self,owner=0,source=ThreadTypes.network):
		self.queueCommand((DrawingCommandTypes.networkcontrol,NetworkControlCommandTypes.resyncrequest,owner),source)

	def queueCommand(self,command,source=ThreadTypes.server,owner=0):
		self.remotecommandqueue.put(command)

	def verifyAllLayerCommand(self,command,owner):
		""" check to make sure that the all layer command a client sent is valid
		"""
		subtype=command[1]
		# verify if requester is actual owner
		if subtype==AllLayerCommandTypes.deletelayer or subtype==AllLayerCommandTypes.releaselayer:
			layerkey=command[2]
			curlayer=self.window.getLayerForKey(layerkey)
			if curlayer and curlayer.owner==owner:
				return True
			return False
		# never allow a client to request this
		elif subtype==AllLayerCommandTypes.deleteall:
			return False
		# there isn't a good way to do this in a network session
		elif subtype==AllLayerCommandTypes.scale:
			return False
		# for now disable this, there might be a workable way to do lower left growth only
		elif subtype==AllLayerCommandTypes.resize:
			#if command[2]==0 and command[3]==0:
			return False

		# allow by default
		return True
			

	def handleNetworkHistoryCommand(self,command,owner):
		""" Handles undo and redo commands sent from clients by updating local history counter and sending the commands out to all other clients, all of the print statements here should never trigger, but I'm putting them in for debugging purposes in case something goes wrong
		"""
		if not owner in commandindexes:
			self.commandcaches[owner]=[]
			self.commandindexes[owner]=0
		else:
			print "WARNING: got history control before initialization of history for client:", owner

		subtype=command[1]
		if subtype==HistoryCommandTypes.undo:
			# test to make sure there should be some history to undo
			if self.commandindexes[owner]>0:
				self.commandindexes[owner]-=1
				self.master.routinginput.put((command,owner))
			else:
				print "Error, got undo but no more past history for client", owner
		elif subtype==HistoryCommandTypes.redo:
			if self.commandindexes[owner]<len(self.commandcaches[owner]):
				self.commandindexes[owner]+=1
				self.master.routinginput.put((command,owner))
			else:
				print "Error, got redo but no more future history for client", owner

	def addToOwnerCache(self,command,owner):
		if not owner in commandcaches:
			self.commandcaches[owner]=[]
			self.commandindexes[owner]=0

		# if there are commands ahead of this one delete them
		if self.commandindexes[owner] >= len(self.commandcaches[owner]):
			self.commandcaches[owner]=self.commandcaches[owner][0:self.index]

		# if the command stack is full, execute and delete the oldest one
		if self.commandindexes[owner] > self.historysize:
			self.remotecommandqueue.put(self.commandcaches[owner][0])
			self.commandcaches[owner]=self.commandcaches[owner][1:]

		self.commandcaches[owner].append(command)
		self.commandindexes[owner]=len(self.commandcaches[owner])

	# the history is taken care of elsewhere
	def addCommandToHistory(self,command,source=0):
		pass
