#!/usr/bin/env python

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui

from beeutil import *
from beeapp import BeeApp

# object to handle the undo/redo history
class CommandStack:
	def __init__(self,windowid,maxundo=20):
		self.commandstack=[]
		self.index=0
		self.changessincesave=0
		self.maxundo=maxundo
		self.windowid=windowid

	def add(self,command):
		# if there are commands ahead of this one delete them
		if self.index>=len(self.commandstack):
			self.commandstack=self.commandstack[0:self.index]

		# if the command stack is full, delete the oldest one
		if self.index>self.maxundo:
			self.commandstack=self.commandstack[1:]

		self.commandstack.append(command)
		self.index=len(self.commandstack)
		self.changessincesave+=1

	def undo(self):
		if self.index<=0:
			return

		self.index-=1
		self.commandstack[self.index].undo(self.windowid)
		BeeApp().master.refreshLayerThumb(self.windowid)

	def redo(self):
		if self.index>=len(self.commandstack):
			return

		self.commandstack[self.index].redo(self.windowid)
		self.index+=1
		BeeApp().master.refreshLayerThumb(self.windowid)

# parent class for all commands that get put in undo/redo stack
class AbstractCommand:
	def undo(self):
		pass

	def redo(self):
		pass

# this class is for any command that changes the image on a layer
class DrawingCommand(AbstractCommand):
	def __init__(self,layerkey,oldimage,location):
		self.layerkey=layerkey
		self.oldimage=oldimage
		self.location=location

	def undo(self,windowid):
		print "running undo in drawing command"
		layer=BeeApp().master.getLayerById(windowid,self.layerkey)
		if layer:
			self.newimage=layer.image.copy(self.location)
			layer.compositeFromCorner(self.oldimage,self.location.x(),self.location.y(),qtgui.QPainter.CompositionMode_Source)

	def redo(self,windowid):
		layer=BeeApp().master.getLayerById(windowid,self.layerkey)
		if layer:
			layer.compositeFromCorner(self.newimage,self.location.x(),self.location.y(),qtgui.QPainter.CompositionMode_Source)

class AddLayerCommand(AbstractCommand):
	def __init__(self,layerkey):
		self.layerkey=layerkey

	def undo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		(self.oldlayer,self.index)=window.removeLayerByKey(self.layerkey,history=-1)

	def redo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		window.insertRawLayer(self.oldlayer,self.index,history=-1)

class DelLayerCommand(AbstractCommand):
	def __init__(self,layer,index):
		self.layer=layer
		self.index=index

	def undo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		window.insertRawLayer(self.layer,self.index,history=-1)

	def redo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		window.removeLayerByKey(self.layer.key,history=-1)

class LayerUpCommand(AbstractCommand):
	def __init__(self,layerkey):
		self.layerkey=layerkey

	def undo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		window.layerDown(self.layerkey)

	def redo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		window.layerUp(self.layerkey)

class LayerDownCommand(AbstractCommand):
	def __init__(self,layerkey):
		self.layerkey=layerkey

	def undo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		window.layerUp(self.layerkey)

	def redo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		window.layerDown(self.layerkey)
