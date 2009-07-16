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
		owner=command[2]
		if subtype==NetworkControlCommandTypes.resyncstart:
			width=command[3]
			height=command[4]
			window.clearAllLayers()
			window.setCanvasSize(width,height)
			window.setRemoteId(owner)

		elif subtype==NetworkControlCommandTypes.giveuplayer:
			layer=window.getLayerForKey(command[3])
			layer.changeOwner(0)
			window.logCommand(command,self.type)

		elif subtype==NetworkControlCommandTypes.layerowner:
			layer=window.getLayerForKey(command[3])
			layer.changeOwner(command[2])
			window.logCommand(command,self.type)

		elif subtype==NetworkControlCommandTypes.requestlayer:
			layer=window.getLayerForKey(command[3])
			window.logCommand(command,self.type)

	def sendToServer(self,command):
		window=self.master.getWindowById(self.windowid)
		if command[0]==DrawingCommandTypes.alllayer and command[1]==AllLayerCommandTypes.insertlayer:
			command=(command[0],command[1],command[2],command[3],window.remoteid)
		window.remoteoutputqueue.put(command)

class RemoteDrawingThread(DrawingThread):
	def __init__(self,queue,windowid,type=ThreadTypes.network,master=None,historysize=20):
		DrawingThread.__init__(self,queue,windowid,type=ThreadTypes.network,master=master)
