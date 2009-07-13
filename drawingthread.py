#!/usr/bin/env python

#import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore

import copy

from beetypes import *
from Queue import Queue

from beeutil import *

from beeapp import BeeApp

from hivecache import *

class DrawingThread(qtcore.QThread):
	def __init__(self,queue,windowid,type=ThreadTypes.user,master=None):
		qtcore.QThread.__init__(self)
		self.queue=queue
		self.windowid=windowid
		self.type=type

		if not master:
			self.master=BeeApp().master
		else:
			self.master=master

		# this will be keyed on a layer key, value will be the tool
		# object so it retains information throughout the stroke
		self.inprocesstools={}

		#print "starting thread with type:", type

	def addExitEventToQueue(self):
		self.queue.put((DrawingCommandTypes.quit,))

	def run(self):
		self.windowtype=self.master.getWindowById(self.windowid).type

		#print "starting drawing thread"
		while 1:
			command=self.queue.get()
			#print "got command from queue:", command

			type=command[0]

			if type==DrawingCommandTypes.quit:
				return

			elif type==DrawingCommandTypes.history:
				self.processHistoryCommand(command)

			elif type==DrawingCommandTypes.layer:
				self.processLayerCommand(command)

			elif type==DrawingCommandTypes.alllayer:
				if self.type==ThreadTypes.user and self.windowtype==WindowTypes.networkclient:
					self.requestAllLayerCommand(command)
				else:
					self.processAllLayerCommand(command)

			elif type==DrawingCommandTypes.networkcontrol:
				self.processNetworkCommand(command)

	def processHistoryCommand(self,command):
		window=self.master.getWindowById(self.windowid)
		subtype=command[1]
		if subtype==HistoryCommandTypes.undo:
			window.undo(command[2])
		elif subtype==HistoryCommandTypes.redo:
			window.redo(command[2])
		else:
			print "unknown processHistoryCommand subtype:", subtype

		window.logCommand(command,self.type)

	def processLayerCommand(self,command):
		window=self.master.getWindowById(self.windowid)
		subtype=command[1]
		if subtype==LayerCommandTypes.alpha:
			layer=window.getLayerForKey(command[2])
			if layer:
				layer.setOptions(opacity=command[3])
				window.logCommand(command,self.type)

		elif subtype==LayerCommandTypes.mode:
			layer=window.getLayerForKey(command[2])
			if layer:
				layer.setOptions(compmode=command[3])
				window.logCommand(command,self.type)

		elif subtype==LayerCommandTypes.pendown:
			layer=window.getLayerForKey(command[2])
			x=command[3]
			y=command[4]
			pressure=command[5]
			tool=command[6]
			# make sure we can find the layer and either it's a locally owned layer or a source that can draw on non-local layers
			if layer and (window.ownedByMe(layer.owner) or self.type!=ThreadTypes.user):
				self.inprocesstools[int(command[2])]=tool
				tool.penDown(x,y,pressure)
			else:
				print "WARNING: no valid layer selected, remote id:", window.remoteid

		elif subtype==LayerCommandTypes.penmotion:
			if command[2]==None:
				return
			#print "Pen motion event:", command
			x=command[3]
			y=command[4]
			pressure=command[5]
			if int(command[2]) in self.inprocesstools:
				tool=self.inprocesstools[int(command[2])]
				tool.penMotion(x,y,pressure)

		elif subtype==LayerCommandTypes.penup:
			if command[2]==None:
				return
			#print "Pen up event:", command
			x=command[3]
			y=command[4]
			if int(command[2]) in self.inprocesstools:
				tool=self.inprocesstools[int(command[2])]
				tool.penUp(x,y)

				# send to server and log file if needed
				window.logStroke(tool,int(command[2]),self.type)

				tool.cleanUp()
				del self.inprocesstools[int(command[2])]

		elif subtype==LayerCommandTypes.rawevent:
			layer=window.getLayerForKey(command[2])
			x=command[3]
			y=command[4]
			image=command[5]
			path=command[6]
			compmode=qtgui.QPainter.CompositionMode_Source
			layer.compositeFromCorner(image,x,y,compmode,path)
			window.logCommand(command,self.type)
		else:
			print "unknown processLayerCommand subtype:", subtype

	def processAllLayerCommand(self,command):
		window=self.master.getWindowById(self.windowid)
		subtype=command[1]
		if subtype==AllLayerCommandTypes.resize:
			window.adjustCanvasSize(command[2],command[3],command[4],command[5])

		elif subtype==AllLayerCommandTypes.scale:
			pass

		elif subtype==AllLayerCommandTypes.layerup:
			window.layerUp(command[2])

		elif subtype==AllLayerCommandTypes.layerdown:
			window.layerDown(command[2])

		elif subtype==AllLayerCommandTypes.deletelayer:
			window.removeLayerByKey(command[2])

		elif subtype==AllLayerCommandTypes.insertlayer:
			#print "processing insert layer command"
			# in this case we want to fill out the details ourselves
			key = command[2]
			index = command[3]
			owner = command[4]
			if self.type==ThreadTypes.server and owner != 0:
				pass
				window.insertLayer(key,index,owner=owner)

			else:
				if window.ownedByMe(owner):
					window.insertLayer(key,index,owner=owner)
				else:
					window.insertLayer(key,index,LayerTypes.network,owner=owner)

	def requestAllLayerCommand(self,command):
		self.sendToServer(command)

	def processNetworkCommand(self,command):
		window=self.master.getWindowById(self.windowid)
		subtype=command[1]
		if subtype==NetworkControlCommandTypes.resyncstart:
			width=command[2]
			height=command[3]
			remoteid=command[4]
			window.clearAllLayers()
			window.setCanvasSize(width,height)
			window.setRemoteId(remoteid)

		elif subtype==NetworkControlCommandTypes.giveuplayer:
			layer=window.getLayerForKey(command[2])
			layer.changeOwner(0)
			window.logCommand(command,self.type)

		elif subtype==NetworkControlCommandTypes.layerowner:
			layer=window.getLayerForKey(command[2])
			layer.changeOwner(command[3])
			window.logCommand(command,self.type)

		elif subtype==NetworkControlCommandTypes.requestlayer:
			layer=window.getLayerForKey(command[2])
			window.logCommand(command,self.type)

	def sendToServer(self,command):
		window=self.master.getWindowById(self.windowid)
		if command[0]==DrawingCommandTypes.alllayer and command[1]==AllLayerCommandTypes.insertlayer:
			command=(command[0],command[1],command[2],command[3],window.remoteid)
		window.remoteoutputqueue.put(command)

class RemoteDrawingThread(DrawingThread):
	def __init__(self,queue,windowid,type=ThreadTypes.network,master=None,historysize=20):
		DrawingThread.__init__(self,queue,windowid,type=ThreadTypes.network,master=master)

class ServerDrawingThread(DrawingThread):
	def __init__(self,queue,windowid,master=None,historysize=20):
		DrawingThread.__init__(self,queue,windowid,type=ThreadTypes.server,master=master)
		self.commandcaches={}
		self.commandindexes={}
		self.historysize=historysize

	def processNetworkCommand(self,command):
		window=self.master.getWindowById(self.windowid)
		subtype=command[1]
		requester=command[2]
		if subtype==NetworkControlCommandTypes.resyncrequest:
			self.sendResyncToClient(requester,window)
		elif subtype==NetworkControlCommandTypes.giveuplayer:
			layerkey=command[3]
			layer=window.getLayerForKey(layerkey)
			proplock=qtcore.QWriteLocker(layer.propertieslock)
			self.layerOwnerChangeCommand(layer,0)
		elif subtype==NetworkControlCommandTypes.requestlayer:
			layerkey=command[3]
			layer=window.getLayerForKey(layerkey)
			proplock=qtcore.QWriteLocker(layer.propertieslock)
			if layer.owner==0:
				self.layerOwnerChangeCommand(layer,requester)
			

	def sendResyncToClient(self,requester,window):
		print "sending resync with requester:", requester
		# first tell client to get rid of list of layers
		resynccommand=(DrawingCommandTypes.networkcontrol,NetworkControlCommandTypes.resyncstart,window.docwidth,window.docheight,requester)
		dest=-1*requester
		self.master.routinginput.put((resynccommand,dest))

		window.sendLayersToClient(requester)

		#send event cache to client
		for c in self.commandcaches.keys():
			for command in self.commandcaches[c]:
				command.send(requester,self.master.routinginput)

	# Change layer owner, must lock down properties layer before calling this
	def layerOwnerChangeCommand(self,layer,newowner):
		oldowner=layer.owner
		if oldowner and oldowner in self.commandcaches:
			# make copy of list so removing while iterating works
			newcache=self.commandcaches[oldowner][:]
			# go through the command stack for the owner to remove commands that relate to that layer
			for command in self.commandcaches[oldowner]:
				if command.layer.key==layer.key:
					# if the command is before the current index then decrement the index
					if newcache.index(command)<self.commandindexes[oldowner]:
						self.commandindexes[oldowner]-=1
					command.process()
					newcache.remove(command)

			# update cache of old owner to not include references to that layer
			self.commandcaches[oldowner]=newcache

		layer.owner=newowner
		command=(DrawingCommandTypes.networkcontrol,NetworkControlCommandTypes.layerowner,layer.key,newowner)
		# if the old owner was 0, meaning it was unowned, then send it to everyone, otherwise the old owner has already changed it locally to 0 and doesn't need it again
		self.master.routinginput.put((command,oldowner))

	def processLayerCommand(self,command):
		cachedcommand=None
		window=self.master.getWindowById(self.windowid)
		subtype=command[1]
		layer=window.getLayerForKey(command[2])
		if not layer:
			return
		owner=layer.owner
		# if the layer is owned locally then no one should be able to change it since this is a server session
		if owner==0:
			print "ERROR: recieved layer command for unowned layer in server session:", command
			return

		if subtype==LayerCommandTypes.alpha:
			cachedcommand=CachedAlphaEvent(layer,command[3])
			self.master.routinginput.put((command,layer.owner))

		elif subtype==LayerCommandTypes.mode:
			cachedcommand=CachedModeEvent(layer,command[3])
			self.master.routinginput.put((command,layer.owner))

		elif subtype==LayerCommandTypes.pendown:
			x=command[3]
			y=command[4]
			pressure=command[5]
			tool=command[6]

			self.inprocesstools[command[2]]=CachedToolEvent(layer,tool)
			self.inprocesstools[command[2]].points=[(x,y,pressure)]

		elif subtype==LayerCommandTypes.penmotion:
			#print "Pen motion event:", command
			x=command[3]
			y=command[4]
			pressure=command[5]

			self.inprocesstools[command[2]].points.append((x,y,pressure))

		elif subtype==LayerCommandTypes.penup:
			x=command[3]
			y=command[4]

			cachedcommand=self.inprocesstools[command[2]]

			# make a shallow copy so that the points history won't get changed in the middle of any operations
			tool=copy.copy(cachedcommand.tool)
			tool.pointshistory=cachedcommand.points

			toolcommand=(DrawingCommandTypes.layer,LayerCommandTypes.tool,cachedcommand.layer.key,tool)

			self.master.routinginput.put((toolcommand,cachedcommand.layer.owner))

			del self.inprocesstools[command[2]]

		elif subtype==LayerCommandTypes.rawevent:
			layer=window.getLayerForKey(command[2])
			x=command[3]
			y=command[4]
			image=command[5]
			path=command[6]
			compmode=qtgui.QPainter.CompositionMode_Source
			layer.compositeFromCorner(image,x,y,compmode,path)
			window.logCommand(command,self.type)
		else:
			sendcommand=False
			print "unknown processLayerCommand subtype:", subtype

		if cachedcommand:
			self.addToCache(cachedcommand)

	def addToCache(self,command):
		owner=command.layer.owner
		if not owner in self.commandcaches:
			self.commandcaches[owner]=[]
			self.commandindexes[owner]=0

		# if there are commands ahead of this one delete them
		if self.commandindexes[owner] > len(self.commandcaches[owner]):
			self.commandcaches[owner]=self.commandcaches[owner][0:self.commandindexes[owner]]

		# if the command stack is full, execute and delete the oldest one
		if self.commandindexes[owner] > self.historysize:
			self.commandcaches[owner][0].process()
			self.commandcaches[owner]=self.commandcaches[owner][1:]

		self.commandcaches[owner].append(command)
		self.commandindexes[owner]=len(self.commandcaches[owner])

	def processHistoryCommand(self,command):
		""" Handles undo and redo commands sent from clients by updating local history counter and sending the commands out to all other clients, all of the print statements here should never trigger, but I'm putting them in for debugging purposes in case something goes wrong
		"""
		subtype=command[1]
		owner=command[2]

		if not owner in self.commandindexes:
			self.commandcaches[owner]=[]
			self.commandindexes[owner]=0

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

	def processAllLayerCommand(self,command):
		DrawingThread.processAllLayerCommand(self,command)
		self.master.routinginput.put((command,0))
