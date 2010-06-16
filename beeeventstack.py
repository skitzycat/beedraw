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
	def __init__(self,window,maxundo=20):
		self.commandstack=[]
		self.index=0
		self.changessincesave=0
		self.maxundo=maxundo
		self.win=window

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
		self.commandstack[self.index].undo(self.window)
		BeeApp().master.refreshLayerThumb(self.window)

	def redo(self):
		if self.index>=len(self.commandstack):
			return

		self.commandstack[self.index].redo(self.win)
		self.index+=1
		BeeApp().master.refreshLayerThumb(self.win)

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
	undotype=UndoCommandTypes.remote
	def __init__(self,layerkey,oldimage,location):
		AbstractCommand.__init__(self)
		self.layerkey=layerkey
		self.oldimage=oldimage
		self.location=location

	def undo(self,win):
		print_debug("running undo in drawing command")
		layer=win.getLayerForKey(self.layerkey)
		if layer:
			self.redoimage=layer.image.copy(self.location)
			layer.compositeFromCorner(self.oldimage,self.location.x(),self.location.y(),qtgui.QPainter.CompositionMode_Source)

	def redo(self,win):
		print_debug("running redo in drawing command")
		layer=win.getLayerForKey(self.layerkey)
		if layer:
			layer.compositeFromCorner(self.redoimage,self.location.x(),self.location.y(),qtgui.QPainter.CompositionMode_Source)

class AnchorCommand(DrawingCommand):
	undotype=UndoCommandTypes.remote
	def __init__(self,layerkey,oldimage,location,floating):
		DrawingCommand.__init__(self,layerkey,oldimage,location)
		self.floating=floating

	def undo(self,win):
		DrawingCommand.undo(self,windowid)
		layer=win.getLayerForKey(self.layerkey)
		if layer:
			layer.scene().addItem(self.floating)
			self.floating.setParentItem(layer)
			win.requestLayerListRefresh()
			BeeApp().master.updateLayerHighlight(win,self.floating.key)

	def redo(self,win):
		DrawingCommand.redo(self,windowid)
		layer=win.getLayerForKey(self.layerkey)
		if layer:
			layer.scene().removeItem(self.floating)
			win.setValidActiveLayer()
			win.requestLayerListRefresh()

class AddLayerCommand(AbstractCommand):
	undotype=UndoCommandTypes.notinnetwork
	def __init__(self,layerkey):
		AbstractCommand.__init__(self)
		self.layerkey=layerkey

	def undo(self,win):
		(self.oldlayer,self.index)=win.removeLayerByKey(self.layerkey,history=-1)

	def redo(self,win):
		win.insertRawLayer(self.oldlayer,self.index,history=-1)

class DelLayerCommand(AbstractCommand):
	undotype=UndoCommandTypes.notinnetwork
	def __init__(self,layer,index):
		AbstractCommand.__init__(self)
		self.layerkey=layer.key
		self.layer=layer
		self.index=index

	def undo(self,win):
		win.insertRawLayer(self.layer,self.index,history=-1)

	def redo(self,win):
		win.removeLayerByKey(self.layer.key,history=-1)

class LayerUpCommand(AbstractCommand):
	undotype=UndoCommandTypes.notinnetwork
	def __init__(self,layerkey):
		AbstractCommand.__init__(self)
		self.layerkey=layerkey

	def undo(self,win):
		win.layerDown(self.layerkey,history=False)

	def redo(self,win):
		win.layerUp(self.layerkey,history=False)

class LayerDownCommand(AbstractCommand):
	undotype=UndoCommandTypes.notinnetwork
	def __init__(self,layerkey):
		AbstractCommand.__init__(self)
		self.layerkey=layerkey

	def undo(self,win):
		win.layerUp(self.layerkey,history=False)

	def redo(self,win):
		win.layerDown(self.layerkey,history=False)

class CutCommand(DrawingCommand):
	undotype=UndoCommandTypes.remote
	def __init__(self,layerkey,oldimage,location,path):
		DrawingCommand.__init__(self)
		self.path=path

	def undo(self,win):
		DrawingCommand.undo(self,win)
		win.changeSelection(SelectionModTypes.new,path)

	def redo(self,win):
		DrawingCommand.redo(self,win)
		win.changeSelection(SelectionModTypes.clear)

class PasteCommand(AddLayerCommand):
	undotype=UndoCommandTypes.localonly
	def __init__(self,layerkey,path):
		AbstractCommand.__init__(self)
		self.path=path

	def undo(self,win):
		AddLayerCommand.undo(self,win)
		layer=getLayerForKey(self.layerkey)
		self.layerparent=layer.parentItem()
		win.changeSelection(SelectionModTypes.new,path)

	def redo(self,win):
		AddLayerCommand.redo(self,win)
		win.changeSelection(SelectionModTypes.clear)

class ChangeSelectionCommand(AbstractCommand):
	def __init__(self,oldpath,newpath):
		AbstractCommand.__init__(self)
		self.oldpath=oldpath
		self.newpath=newpath

	def undo(self,win):
		win.changeSelection(SelectionModTypes.new,oldpath)

	def redo(self,win):
		win.changeSelection(SelectionModTypes.new,newpath)

class MoveSelectionCommand(AbstractCommand):
	def __init__(self,layerkey,oldpos,newpos):
		AbstractCommand.__init__(self)
		self.oldpos=oldpos
		self.newpos=newpos

	def undo(self,win):
		layer=win.getLayerForKey(self.layerkey)
		layer.setPos(oldpos)

	def redo(self,win):
		layer=win.getLayerForKey(self.layerkey)
		layer.setPos(newpos)
