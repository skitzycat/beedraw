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

# custom event types
class BeeCustomEventTypes:
	refreshlayerslist = qtcore.QEvent.User

# custom enumerated types
class DrawingCommandTypes:
	quit, history, layer, alllayer, networkcontrol = range(5)

# events that may effect one or more layers
class HistoryCommandTypes:
	undo, redo = range(2)

# events that effect only one layer
class LayerCommandTypes:
	alpha, mode, pendown, penmotion, penup, penleave, penenter, rawevent, tool = range(9)

# events that effect the list of layers, all layers or layer ownership
class AllLayerCommandTypes:
	""" formats for command types:
				insertlayer : (layer key, index to insert at, image on layer, owner of layer)
	"""
	scale, resize, layerup, layerdown, deletelayer, insertlayer, deleteall, releaselayer, layerownership = range(9)

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
  """
	resyncrequest, resyncstart, requestlayer, giveuplayer, revokelayer, layerowner, fatalerror= range(7)

class LayerTypes:
	""" Represents types of layers:
				user: layer that can be drawn on by the user
        animation: layer that is being drawn on by a local process reading it out of a file
        network: layer in a network session that the user cannot draw on
	"""
	user, animation, network = range(3)

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
	unlogable, regular, raw = range(3)

# types of ways to modify the current selection
class SelectionModTypes:
	clear, new, intersect, add, subtract = range(5)

# types of brush shapes
class BrushShapes:
	ellipse = range(1)

# types of stamp mode, currently only overlay is supported, eventually I'd like to support drawing with making each pixel the match that of the least opaque pixel, but there doesn't seem to be a blend mode for that
class DrawingToolStampMode:
	darkest, overlay = range(2)

# types of applications
class BeeAppType:
	server, daemon, client = range(3)
