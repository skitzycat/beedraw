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

import os

from beetools import BeeToolBox

class AbstractBeeMaster:
	def __init__(self):
		# setup tool box
		self.toolbox=BeeToolBox()

		self.curwindow=None

	def refreshLayerThumb(self,window,layer=0):
		""" May need to be implemented in a subclass """
		return

	def getToolClassByName(self,name):
		return self.toolbox.getToolDescByName(name)

	def getCurToolInst(self,window):
		pass

	def getCurToolDesc(self):
		return self.toolbox.getCurToolDesc()

	def registerWindow(self,window):
		pass

	def getLayerById(self,win_id,layer_id):
		return self.curwindow.getLayerByKey(layer_id)

	def getLayerById(self,win_id):
		return self.curwindow

	def startRemoteDrawingThreads(self):
		pass
