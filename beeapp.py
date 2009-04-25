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
			BeeApp.instances[cls] = object.__new__(cls, *args, **kwargs)
		# if there already was an instance and the init function is the same then make init do nothing so it's not run again and return the already created instance
		elif cls.__init__ == cls.__original_init__:
			def nothing(*args, **kwargs):
				pass
			cls.__init__ = nothing
		return BeeApp.instances[cls]

	def __init__(self):
		self.master=None
		self.app=None
