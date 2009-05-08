import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui

from beetools import BeeToolBox

class AbstractBeeMaster:
	def __init__(self):
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
		return self.curwindow.getLayerByKey()

	def startRemoteDrawingThreads(self):
		pass
