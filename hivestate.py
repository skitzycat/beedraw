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

from beesessionstate import BeeSessionState
from hivedrawingthread import ServerDrawingThread
from beetypes import *

class HiveSessionState(BeeSessionState):
	def __init__(self,master,width,height,type,maxundo):
		BeeSessionState.__init__(self,master,width,height,type)
		self.commandcaches={}
		self.commandindexes={}
		self.historysize=maxundo
		self.master=master

	def localLayer(self,key):
		return False

	def startRemoteDrawingThreads(self):
		# start remote command thread
		self.remotedrawingthread=ServerDrawingThread(self.remotecommandqueue,self.id,master=self.master)
		self.remotedrawingthread.start()

	# send full resync to client with given ID
	def sendLayersToClient(self,id):
		# get a read lock on all layers and the list of layers
		lock=qtcore.QReadLocker(self.layerslistlock)
		locklist=[]
		for layer in self.layers:
			locklist.append(qtcore.QReadLocker(layer.imagelock))

		# send each layer to client
		index=0
		for layer in self.layers:
			index+=1
			self.sendLayerImageToClient(layer,index,id)

	def sendLayerImageToClient(self,layer,index,id):
		key=layer.key
		image=layer.getImageCopy()
		opacity=layer.opacity
		compmode=layer.compmode
		owner=layer.owner

		# send command to create layer
		insertcommand=(DrawingCommandTypes.alllayer,AllLayerCommandTypes.insertlayer,key,index,image,owner)
		self.master.routinginput.put((insertcommand,id*-1))

		# set alpha and composition mode for layer
		alphacommand=(DrawingCommandTypes.layer,LayerCommandTypes.alpha,key,opacity)
		self.master.routinginput.put((alphacommand,id*-1))
		modecommand=(DrawingCommandTypes.layer,LayerCommandTypes.mode,key,compmode)
		self.master.routinginput.put((modecommand,id*-1))

	def addFatalErrorNotificationToQueue(self,owner,errormessage,source=ThreadTypes.network):
		self.queueCommand((DrawingCommandTypes.networkcontrol,NetworkControlCommandTypes.fatalerror,owner,errormessage),source)

	def addLayerRequestToQueue(self,layerkey,owner=0,source=ThreadTypes.network):
		self.queueCommand((DrawingCommandTypes.networkcontrol,NetworkControlCommandTypes.requestlayer,owner,layerkey),source)

	def addResyncRequestToQueue(self,owner=0,source=ThreadTypes.network):
		self.queueCommand((DrawingCommandTypes.networkcontrol,NetworkControlCommandTypes.resyncrequest,owner),source)

	def queueCommand(self,command,source=ThreadTypes.server,owner=0):
		#print "putting command in remote queue:", command
		self.remotecommandqueue.put(command)

	# the history is taken care of elsewhere
	def addCommandToHistory(self,command,source=0):
		pass
