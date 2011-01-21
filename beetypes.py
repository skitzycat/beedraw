#    Beedraw/Hive network capable client and server allowing collaboration on a single image
#    Copyright (C) 2009 Thomas Becker
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

# custom event types
class BeeCustomEventTypes:
	refreshlayerslist = qtcore.QEvent.User
	displaymessage = qtcore.QEvent.User+1
	hiveserverstatus = qtcore.QEvent.User+2
	starthiveserver = qtcore.QEvent.User+3
	updateselectiondisplay = qtcore.QEvent.User+4
	addlayertoscene = qtcore.QEvent.User+5
	removelayerfromscene = qtcore.QEvent.User+6
	setscenerect = qtcore.QEvent.User+6

class SetSceneRectEvent(qtcore.QEvent):
	def __init__(self,rect):
		qtcore.QEvent.__init__(self,BeeCustomEventTypes.setscenerect)
		self.rect=rect

class AddLayerToSceneEvent(qtcore.QEvent):
	def __init__(self,layer):
		qtcore.QEvent.__init__(self,BeeCustomEventTypes.addlayertoscene)
		self.layer=layer

class RemoveLayerFromSceneEvent(qtcore.QEvent):
	def __init__(self,layer):
		qtcore.QEvent.__init__(self,BeeCustomEventTypes.removelayerfromscene)
		self.layer=layer

class SelectionDisplayUpdateEvent(qtcore.QEvent):
	def __init__(self,path=None):
		qtcore.QEvent.__init__(self,BeeCustomEventTypes.updateselectiondisplay)
		self.path=path

class HiveServerStatusEvent(qtcore.QEvent):
	def __init__(self,status,errorstring=None):
		qtcore.QEvent.__init__(self,BeeCustomEventTypes.hiveserverstatus)
		self.status=status
		self.errorstring=errorstring

class HiveServerStatusTypes:
	running,starterror,stopped = range(3)

class BeeDisplayMessageTypes:
	warning,error = range(2)

class DisplayMessageEvent(qtcore.QEvent):
	def __init__(self,boxtype,title,message):
		qtcore.QEvent.__init__(self,BeeCustomEventTypes.displaymessage)
		self.boxtype=boxtype
		self.title=title
		self.message=message

class BeeSocketTypes:
	qt, python = range(2)

# custom enumerated types
class DrawingCommandTypes:
	quit, history, layer, alllayer, networkcontrol, localonly = range(6)

# events that may effect one or more layers
class HistoryCommandTypes:
	undo, redo = range(2)

# localonly command types, commands that don't get seen by network clients
class LocalOnlyCommandTypes:
	selection, floatingmove = range(2)

# events that effect only one layer
class LayerCommandTypes:
	""" layer command type definitions
				alpha : the alpha of the layer has been changed
				alphadone : the alpha of the layer is finished being changed, this is for when the user lets the cursor up on the slider and the event can actually be logged and sent externally
	"""
	alpha, alphadone, mode, pendown, penmotion, penup, penleave, penenter, rawevent, tool, cut, copy, paste, anchor = range(14)

# events that effect the list of layers, all layers or layer ownership
class AllLayerCommandTypes:
	""" formats for command types:
				insertlayer : (layer key, index to insert at, image on layer, owner of layer)
	"""
	scale, resize, layerup, layerdown, deletelayer, insertlayer, deleteall, releaselayer, layerownership, flatten = range(10)

# commands that are only used to communicate when in a network session
class NetworkControlCommandTypes:
	""" resyncrequest: a client requesting to get all information on the current session
      resyncstart: sent from the server to client, tells client to delete all layers and undo history
      revokelayer: server telling a client to send a giveuplayer
      requestlayer: sent from client to server to request ownership of unowned layer
      giveuplayer: sent from client to server to change layer to unowned
      layerowner: sent from server to all clients to show change of a layer owner
      layerowner: sent from server to all clients to show change of a layer owner
      fatalerror: sent from server to client to indicate error occured and that session should end
			networkhistorysize: sent from server to client to indicate the size of the network history for the session
  """
	resyncrequest, resyncstart, requestlayer, giveuplayer, revokelayer, layerowner, fatalerror, networkhistorysize = range(8)

class LayerTypes:
	""" Represents types of layers:
				user: layer that can be drawn on by the user
        animation: layer that is being drawn on by a local process reading it out of a file
        network: layer in a network session that the user cannot draw on
        floating: layer that is a floating selection used to paste something, this not shared in a network session until anchored to another layer
	"""
	user, animation, network, floating, temporary = range(5)

class WindowTypes:
	""" Represents types of windows:
        singleuser: The window is not connected to any processes that are reading things out of a file or from the network
        animation: The window has at least some layers that are reading events out of a file
        networkclient: The window is connected to a server in a network session
        standaloneserver: The window being used to keep the master internal state for a network session
        integratedserver: A window running as both a client and keeping track of server state (Note that this is not supported yet and may never be)
	"""
	singleuser, animation, networkclient, integratedserver, standaloneserver = range(5)

class ThreadTypes:
	user, animation, network, server = range(4)

class ToolLogTypes:
	"""
	      unlogable
        regular: log a tool event by points
        raw: log an event that changes a layer by raw image change
        selection: log an event that changes the selection
        selectionraw: log an event that changes both a layer image and the selection
        move: log an event that moves a layer
	"""
	unlogable, regular, raw, selection, selectionraw, move = range(6)

# ways to modify the current selection
class SelectionModTypes:
	clear, new, intersect, invert, add, subtract, grow, shrink, setlist = range(9)

# ways to draw the current selection
class SelectionDrawTypes:
	fromcorner, fromcenter = range(2)

# ways to handle ratio of selection drawing
class SelectionRatioTypes:
	free, fixed = range(2)

# types of brush shapes
class BrushShapes:
	ellipse = range(1)

# types of stamp mode, currently only overlay is supported, eventually I'd like to support drawing with making each pixel the match that of the least opaque pixel, but there doesn't seem to be a blend mode for that
class DrawingToolStampMode:
	darkest, overlay = range(2)

# types of applications
class BeeAppType:
	server, daemon, client = range(3)

class ImageCombineTypes:
	composite, add, darkest, lightest = range(4)

class BrushImageFormats:
	qt, pil = range(2)

class DebugFlags:
  alloff, allon = range(2)

class UndoCommandTypes:
	none,localonly,remote,notinnetwork,nolog = range(5)

class BucketFillTypes:
	selection, layer, image = range(3)

class CommandStackTypes:
	singleuser, network, remoteonly = range(3)
