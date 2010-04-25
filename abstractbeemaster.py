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
from beeload import BeeMasterConfigParser

class AbstractBeeMaster:
	""" This is a class that can be inherited from to provide a bee master object that controls tools, windows, layers, and options
	"""
	def __init__(self):
		# setup tool box
		self.toolbox=BeeToolBox()

		self.curwindow=None

		# set default config values
		self.configlock=qtcore.QReadWriteLock()
		self.config={}
		self.config['username']=""
		self.config['server']="localhost"
		self.config['port']=8333
		self.config['autolog']=False
		self.config['autosave']=False
		self.config['debug']=False

		# then load from config file if possible
		configfilename=os.path.join("config","beedrawoptions.xml")
		configfile=qtcore.QFile(configfilename)
		if configfile.exists():
			if configfile.open(qtcore.QIODevice.ReadOnly):
				parser=BeeMasterConfigParser(configfile)
				fileconfig=parser.loadOptions()

				self.config.update(fileconfig)

		BEE_DEBUG=self.config['debug']

	def getConfigOption(self,key,default=None):
		""" This function is used to fetch options, I'm well aware that dictionaries have a get function, but I want this function to output a debug message if the key isn't found """
		lock=qtcore.QReadLocker(self.configlock)
		if key in self.config:
			return self.config[key]
		print_debug("couldn't find config option: %s" % key)
		return default

	def refreshLayerThumb(self,window,layer=0):
		""" Indicates that layer thumbnails need to be updated, this may or may not need to be reimplemented in the subclass """
		return

	def getToolClassByName(self,name):
		return self.toolbox.getToolDescByName(name)

	def getCurToolInst(self,window):
		pass

	def getCurWindow(self,lock=None):
		return self.curwindow

	def getCurToolDesc(self):
		"""	return description object for current tool """
		return self.toolbox.getCurToolDesc()

	def registerWindow(self,window):
		pass

	def getLayerById(self,win_id,layer_id):
		""" return layer of current window that has specified ID, return None if no layer with that ID is found """
		return self.curwindow.getLayerByKey(layer_id)

	#def getLayerById(self,win_id):
	#	return self.curwindow

	def startRemoteDrawingThreads(self):
		pass
