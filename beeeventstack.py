#    Beedraw/Hive network capable client and server allowing collaboration on a single image
#    Copyright (C) 2009 B. Becker
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

	def deleteLayerHistory(self,layerkey):
		""" remove all references to given layer in history """
		# make copy of stack so I can iterate through it correctly while deleting
		newstack=self.commandstack[:]

		for c in self.commandstack:
			if c.layerkey==layerkey:
				if newstack.index(c)<self.index:
					self.index-=1
				newstack.remove(c)

		self.commandstack=newstack

	def add(self,command):
		# if there are commands ahead of this one delete them
		if self.index<len(self.commandstack):
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
	def __init__(self):
		self.layerkey=0
	def undo(self):
		pass

	def redo(self):
		pass

# this class is for any command that changes the image on a layer
class DrawingCommand(AbstractCommand):
	def __init__(self,layerkey,oldimage,location):
		AbstractCommand.__init__(self)
		self.layerkey=layerkey
		self.oldimage=oldimage
		self.location=location

	def undo(self,windowid):
		print_debug("running undo in drawing command")
		layer=BeeApp().master.getLayerById(windowid,self.layerkey)
		if layer:
			self.redoimage=layer.image.copy(self.location)
			layer.compositeFromCorner(self.oldimage,self.location.x(),self.location.y(),qtgui.QPainter.CompositionMode_Source)

	def redo(self,windowid):
		layer=BeeApp().master.getLayerById(windowid,self.layerkey)
		if layer:
			layer.compositeFromCorner(self.redoimage,self.location.x(),self.location.y(),qtgui.QPainter.CompositionMode_Source)

class AddLayerCommand(AbstractCommand):
	def __init__(self,layerkey):
		AbstractCommand.__init__(self)
		self.layerkey=layerkey

	def undo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		(self.oldlayer,self.index)=window.removeLayerByKey(self.layerkey,history=-1)

	def redo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		window.insertRawLayer(self.oldlayer,self.index,history=-1)

class DelLayerCommand(AbstractCommand):
	def __init__(self,layer,index):
		AbstractCommand.__init__(self)
		self.layerkey=layer.key
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
		AbstractCommand.__init__(self)
		self.layerkey=layerkey

	def undo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		window.layerDown(self.layerkey)

	def redo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		window.layerUp(self.layerkey)

class LayerDownCommand(AbstractCommand):
	def __init__(self,layerkey):
		AbstractCommand.__init__(self)
		self.layerkey=layerkey

	def undo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		window.layerUp(self.layerkey)

	def redo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		window.layerDown(self.layerkey)

class ResizeCanvasCommand(AbstractCommand):
	def __init__(self,layers,windowid,adjustments):
		AbstractCommand.__init__(self)
		self.windowid=windowid

		self.adjustments=adjustments
		self.reverseadjustments=(0-adjustments[0],0-adjustments[1],0-adjustments[2],0-adjustments[3])

		self.oldlayerimages={}
		for layer in layers:
			self.oldlayerimages[layer.key]=layer.getImageCopy()
	def undo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		self.newwidth=window.docwidth
		self.newheight=window.docheight
		window.adjustCanvasSize(self.reverseadjustments,history=False)
		for key in self.oldlayerimages:
			layer=window.getLayerForKey(key)
			layer.setImage(self.oldlayerimages[key])
	def redo(self,windowid):
		window=BeeApp().master.getWindowById(windowid)
		window.adjustCanvasSize(self.adjustments,history=False)
