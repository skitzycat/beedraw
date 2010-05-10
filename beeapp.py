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

from beetypes import BeeAppType

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui

class BeeApp(object):
	""" Represents a beedraw application.
				This class is a singleton so that from anywhere in the program the master window can be accessed without leaving around extra references
	"""
	instances = {}
	def __new__(cls, *args, **kwargs):
		""" this redefinition of new is here to make the object a singleton
		"""
		# if there is no instance of this class just make a new one and save what the init function was
		if BeeApp.instances.get(cls) is None:
			cls.__original_init__ = cls.__init__
			BeeApp.instances[cls] = object.__new__(cls)
		# if there already was an instance and the init function is the same then make init do nothing so it's not run again and return the already created instance
		elif cls.__init__ == cls.__original_init__:
			def nothing(*args, **kwargs):
				pass
			cls.__init__ = nothing
		return BeeApp.instances[cls]

	def __init__(self,argv,type=1):
		self.debug_flags={}
		self.master=None
		self.type=type
		self.app=BeeGuiApp(argv)

class BeeGuiApp(qtgui.QApplication):
	def event(self,event):
		if event.type()==qtcore.QEvent.TabletEnterProximity:
			BeeApp().master.pointerTypeCheck(event.pointerType())
			event.accept()
			return True
		return qtgui.QApplication.event(self,event)
