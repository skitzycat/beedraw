#!/usr/bin/env python

#import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore

from beetypes import *
from Queue import Queue

from beeutil import *

import beemaster

class DrawingThread(qtcore.QThread):
	def __init__(self,queue,windowid,type=ThreadTypes.user):
		qtcore.QThread.__init__(self)
		self.queue=queue
		self.windowid=windowid
		self.type=type
		self.windowtype=beemaster.BeeMasterWindow().getWindowById(windowid).type

		# this will be keyed on a layer key, value will be the tool
		# object so it retains information throughout the stroke
		self.inprocesstools={}

		#print "starting thread with type:", type

	def addExitEventToQueue(self):
		self.queue.put((DrawingCommandTypes.quit,))

	def run(self):
		#print "starting drawing thread"
		while 1:
			command=self.queue.get()
			#print "got command from queue:", command

			type=command[0]

			if type==DrawingCommandTypes.quit:
				return

			elif type==DrawingCommandTypes.nonlayer:
				self.processNonLayerCommand(command)

			elif type==DrawingCommandTypes.layer:
				self.processLayerCommand(command)

			elif type==DrawingCommandTypes.alllayer:
				if self.type==ThreadTypes.user and self.windowtype==WindowTypes.networkclient:
					self.requestAllLayerCommand(command)
				else:
					self.processAllLayerCommand(command)

			elif type==DrawingCommandTypes.networkcontrol:
				if self.type==ThreadTypes.user and self.windowtype==WindowTypes.networkclient:
					self.processClientNetworkCommand(command)
				else:
					self.processServerNetworkCommand(command)

	def processNonLayerCommand(self,command):
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
		subtype=command[1]
		if subtype==NonLayerCommandTypes.startlog:
			pass
		elif subtype==NonLayerCommandTypes.endlog:
			pass
		elif subtype==NonLayerCommandTypes.undo:
			window.undo(command[2])
			if self.type==ThreadTypes.user and window.type==WindowTypes.networkclient:
				self.sendToServer(command)
		elif subtype==NonLayerCommandTypes.redo:
			window.redo(command[2])
			if self.type==ThreadTypes.user and window.type==WindowTypes.networkclient:
				self.sendToServer(command)
		else:
			print "unknown processNonLayerCommand subtype:", subtype

		window.logCommand(command)

	def processLayerCommand(self,command):
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
		subtype=command[1]
		if subtype==LayerCommandTypes.alpha:
			layer=window.getLayerForKey(command[2])
			if layer:
				layer.setOptions(opacity=command[3])
				window.logCommand(command)

		elif subtype==LayerCommandTypes.mode:
			layer=window.getLayerForKey(command[2])
			if layer:
				layer.setOptions(compmode=command[3])
				window.logCommand(command)

		elif subtype==LayerCommandTypes.pendown:
			#print "Pen down event:", command
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
				print "WARNING: no vaid layer selected"

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
				window.logStroke(tool,int(command[2]))

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
			window.logCommand(command)
		else:
			print "unknown processLayerCommand subtype:", subtype

	def processAllLayerCommand(self,command):
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
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
				print "calling nextLayerKey from drawingthread.py"
				window.insertLayer(key,index,owner=owner)

			else:
				if window.ownedByMe(owner):
					window.insertLayer(key,index,owner=owner)
				else:
					window.insertLayer(key,index,LayerTypes.network,owner=owner)

		window.logServerCommand(command)

	def requestAllLayerCommand(self,command):
		self.sendToServer(command)

	def processClientNetworkCommand(self,command):
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
		subtype=command[1]
		if subtype==NetworkControlCommandTypes.resyncstart:
			window.clearAllLayers()

	def processServerNetworkCommand(self,command):
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
		subtype=command[1]
		if subtype==NetworkControlCommandTypes.resyncrequest:
			window.sendResyncToClient(command[2]*-1)

	def sendToServer(self,command):
		window=beemaster.BeeMasterWindow().getWindowById(self.windowid)
		if command[0]==DrawingCommandTypes.alllayer and command[1]==AllLayerCommandTypes.insertlayer:
			command=(command[0],command[1],command[2],command[3],window.remoteid)
		window.remoteoutputqueue.put(command)
