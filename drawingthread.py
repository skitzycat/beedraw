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

import copy

from beetypes import *
from Queue import Queue

from beeutil import *

from beeeventstack import DrawingCommand, AnchorCommand

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

		while 1:
			#print "Drawing thread ready to get commands from queue:", self.queue
			command=self.queue.get()
			#print "got command from queue:", command, self.type

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

			elif type==DrawingCommandTypes.selection:
				self.processSelectionCommand(command)

	def processSelectionCommand(self,command):
		selectionop=command[1]
		newpath=command[2]
		window=self.master.getWindowById(self.windowid)
		window.changeSelection(selectionop,newpath)

	def processHistoryCommand(self,command):
		window=self.master.getWindowById(self.windowid)
		subtype=command[1]
		undotype=UndoCommandTypes.none
		if subtype==HistoryCommandTypes.undo:
			undotype=window.undo(command[2])
		elif subtype==HistoryCommandTypes.redo:
			undotype=window.redo(command[2])
		else:
			print_debug("unknown processHistoryCommand subtype: %d" % subtype)

		if undotype==UndoCommandTypes.remote or undotype==UndoCommandTypes.notinnetwork:
			window.logCommand(command,self.type)

	def processLayerCommand(self,command):
		window=self.master.getWindowById(self.windowid)
		subtype=command[1]
		layerkey=command[2]
		layer=window.getLayerForKey(layerkey)
		if not layer:	
			print_debug("ERROR: Can't process Layer command: %s Layer not found" % str(command))
			return

		if subtype==LayerCommandTypes.alpha:
			layer.changeOpacity(command[3])
			window.scene.update()

		elif subtype==LayerCommandTypes.alphadone:
			self.master.refreshLayerThumb(self.windowid,layerkey)
			opacity=layer.getOpacity()
			loggingcommand=(DrawingCommandTypes.layer,LayerCommandTypes.alpha,layerkey,opacity)
			window.logCommand(loggingcommand,self.type)

		elif subtype==LayerCommandTypes.mode:
			layer.setOptions(compmode=command[3])
			window.logCommand(command,self.type)

		elif subtype==LayerCommandTypes.cut:
			selection=command[3]

			rect=selection.boundingRect().toAlignedRect()

			imagelock=qtcore.QWriteLocker(layer.imagelock)
			layer.cut(selection,imagelock=imagelock)
			newimage=layer.getImageCopy(lock=imagelock,subregion=rect)

			rawcommand=(DrawingCommandTypes.layer,LayerCommandTypes.rawevent,layerkey,rect.x(),rect.y(),newimage,None,qtgui.QPainter.CompositionMode_Source)
			window.logCommand(rawcommand,self.type)

		elif subtype==LayerCommandTypes.copy:
			selection=command[3]
			layer.copy(selection)

		elif subtype==LayerCommandTypes.paste:
			image=self.master.getClipBoardImage()
			if image:
				x=command[3]
				y=command[4]
				layer.paste(image,x,y)

		elif subtype==LayerCommandTypes.pendown:
			x=command[3]
			y=command[4]
			pressure=command[5]
			tool=command[6]
			# make sure we can find the layer and either it's a locally owned layer or a source that can draw on non-local layers
			if window.ownedByMe(layer.owner) or self.type!=ThreadTypes.user:
				self.inprocesstools[int(layerkey)]=tool
				tool.penDown(x,y,pressure)
			else:
				print_debug("WARNING: no valid layer selected, remote id: %d" % window.remoteid)

		elif subtype==LayerCommandTypes.penmotion:
			#print "Pen motion event:", command
			x=command[3]
			y=command[4]
			pressure=command[5]
			#print "drawing thread pen motion (x,y,pressure)", x,y,pressure
			if int(layerkey) in self.inprocesstools:
				tool=self.inprocesstools[int(layerkey)]
				tool.penMotion(x,y,pressure)

		elif subtype==LayerCommandTypes.penup:
			#print "Pen up event:", command
			x=command[3]
			y=command[4]
			if int(layerkey) in self.inprocesstools:
				tool=self.inprocesstools[int(layerkey)]
				tool.penUp(x,y)

				# send to server and log file if needed
				window.logStroke(tool,int(layerkey),self.type)

				tool.cleanUp()
				del self.inprocesstools[int(layerkey)]

		elif subtype==LayerCommandTypes.penenter:
			if int(layerkey) in self.inprocesstools:
				self.inprocesstools[int(layerkey)].penEnter()

		elif subtype==LayerCommandTypes.penleave:
			if int(layerkey) in self.inprocesstools:
				self.inprocesstools[int(layerkey)].penLeave()

		elif subtype==LayerCommandTypes.rawevent or subtype==LayerCommandTypes.anchor:
			x=command[3]
			y=command[4]
			image=command[5]
			clippath=command[6]
			compmode=command[7]

			layerimagelock=qtcore.QWriteLocker(layer.imagelock)

			# determine bounding area for event
			dirtyrect=qtcore.QRect(x,y,image.width(),image.height())
			dirtyrect=rectIntersectBoundingRect(dirtyrect,layer.image.rect())
			if clippath:
				dirtyrect=rectIntersectBoundingRect(dirtyrect,clippath.boundingRect().toAlignedRect())

			# set up history event
			oldimage=layer.image.copy(dirtyrect)
			layer.compositeFromCorner(image,x,y,compmode,clippath,lock=layerimagelock)

			if subtype==LayerCommandTypes.rawevent:
				historycommand=DrawingCommand(layerkey,oldimage,dirtyrect)
			else:
				floating=command[8]
				historycommand=AnchorCommand(layerkey,oldimage,dirtyrect,floating)

			window.logCommand(command,self.type)

			# add to undo/redo history
			window.addCommandToHistory(historycommand,layer.owner)

		else:
			print_debug("unknown processLayerCommand subtype: %d" % subtype)

	def processAllLayerCommand(self,command):
		window=self.master.getWindowById(self.windowid)
		subtype=command[1]
		if subtype==AllLayerCommandTypes.resize:
			window.adjustCanvasSize(command[2],command[3],command[4],command[5])

		elif subtype==AllLayerCommandTypes.scale:
			window.scaleCanvas(command[2],command[3])

		elif subtype==AllLayerCommandTypes.layerup:
			window.layerUp(command[2])

		elif subtype==AllLayerCommandTypes.layerdown:
			window.layerDown(command[2])

		elif subtype==AllLayerCommandTypes.deletelayer:
			window.removeLayerByKey(command[2])

		elif subtype==AllLayerCommandTypes.insertlayer:
			# in this case we want to fill out the details ourselves
			key = command[2]
			index = command[3]
			image = command[4]
			owner = command[5]
			if self.type==ThreadTypes.server and owner != 0:
				window.insertLayer(key,index,image=image,owner=owner)

			else:
				if window.ownedByMe(owner):
					window.insertLayer(key,index,image=image,owner=owner)
				else:
					window.insertLayer(key,index,type=LayerTypes.network,image=image,owner=owner)

		window.logCommand(command,self.type)

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
			if not layer:
				return
			if layer.deleteChildren():
				window.master.refreshLayersList()
			layer.changeOwner(0)
			window.logCommand(command,self.type)

		elif subtype==NetworkControlCommandTypes.layerowner:
			layer=window.getLayerForKey(command[3])
			if not layer:
				return
			layer.changeOwner(command[2])
			window.logCommand(command,self.type)

		elif subtype==NetworkControlCommandTypes.requestlayer:
			layer=window.getLayerForKey(command[3])
			if not layer:
				return
			window.logCommand(command,self.type)

	def sendToServer(self,command):
		window=self.master.getWindowById(self.windowid)
		if command[0]==DrawingCommandTypes.alllayer and command[1]==AllLayerCommandTypes.insertlayer:
			command=(command[0],command[1],command[2],command[3],command[4],window.remoteid)
		window.remoteoutputqueue.put(command)

class RemoteDrawingThread(DrawingThread):
	def __init__(self,queue,windowid,type=ThreadTypes.network,master=None,historysize=20):
		DrawingThread.__init__(self,queue,windowid,type=ThreadTypes.network,master=master)
