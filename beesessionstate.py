#!/usr/bin/env python

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui

from beeapp import BeeApp

from beetypes import *

from beeeventstack import CommandStack

from Queue import Queue

class BeeSessionState:
	""" Represents the state of a current drawing with all layers and the current composition of them to be displayed on the screen
	"""
	def __init__(self,width,height,type):
		# save passed values
		self.docwidth=width
		self.docheight=height
		self.type=type

		self.master=BeeApp().master

		self.remoteid=0

		# set unique ID
		self.id=self.master.getNextWindowId()

		# register state so the master can get back to here
		self.master.registerWindow(self)

		# initialize values
		self.backdropcolor=0xFFFFFFFF
		self.log=None
		self.localcommandstack=CommandStack(self.id)
		self.remotecommandstacks={}
		self.curlayerkey=None

		self.nextlayerkey=0
		self.nextlayerkeymutex=qtcore.QMutex()

		self.remotecommandqueue=Queue(0)
		self.remoteoutputqueue=Queue(0)
		self.remotedrawingthread=None

		self.layers=[]
		self.layersmutex=qtcore.QMutex()

	def ownedByMe(self,owner):
		""" return True if the layer is under the control of this state keeper or false if it's under the control of something else (ie an animation process or a network client
		"""
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

	def addPenDownToQueue(self,x,y,pressure,layerkey=None,tool=None,source=ThreadTypes.user):
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
		if not layerkey:
			layerkey=self.curlayerkey

		self.queueCommand((DrawingCommandTypes.layer,LayerCommandTypes.penup,self.curlayerkey,x,y),source)

