#!/usr/bin/env python

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui

from beeutil import *

# object to handle the undo/redo history
class CommandStack:
	def __init__(self,window):
		self.commandstack=[]
		self.index=0
		self.window=window
		self.changessincesave=0
		self.maxundo=20

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
		self.commandstack[self.index].undo(self.window)

	def redo(self):
		if self.index>=len(self.commandstack):
			return

		self.commandstack[self.index].redo(self.window)
		self.index+=1

# parent class for all commands that get put in undo/redo stack
class AbstractCommand:
	def undo(self,window):
		pass

	def redo(self,window):
		pass

# this class is for any command that changes the image on a layer
class DrawingCommand(AbstractCommand):
	def __init__(self,layerkey,oldimage,location):
		self.layerkey=layerkey
		self.oldimage=oldimage
		self.location=location

	def undo(self,window):
		layer=window.getLayerForKey(self.layerkey)
		if layer:
			self.newimage=layer.image.copy(self.location)
			layer.compositeFromCorner(self.oldimage,self.location.x(),self.location.y(),qtgui.QPainter.CompositionMode_Source)

	def redo(self,window):
		layer=window.getLayerForKey(self.layerkey)
		if layer:
			layer.compositeFromCorner(self.newimage,self.location.x(),self.location.y(),qtgui.QPainter.CompositionMode_Source)

class AddLayerCommand(AbstractCommand):
	def __init__(self,layerkey):
		self.layerkey=layerkey

	def undo(self,window):
		(self.oldlayer,self.index)=window.removeLayerByKey(self.layerkey,history=-1)

	def redo(self,window):
		window.insertRawLayer(self.oldlayer,self.index,history=-1)

class DelLayerCommand(AbstractCommand):
	def __init__(self,layer,index):
		self.layer=layer
		self.index=index

	def undo(self,window):
		window.insertRawLayer(self.layer,self.index,history=-1)

	def redo(self,window):
		window.removeLayerByKey(self.layer.key,history=-1)

class LayerUpCommand(AbstractCommand):
	def __init__(self,layerkey):
		self.layerkey=layerkey

	def undo(self,window):
		self.window.layerDown(self.layerkey)

	def redo(self,window):
		self.window.layerUp(self.layerkey)

class LayerDownCommand(AbstractCommand):
	def __init__(self,layerkey):
		self.layerkey=layerkey

	def undo(self,window):
		self.window.layerUp(self.layerkey)

	def redo(self,window):
		self.window.layerDown(self.layerkey)
