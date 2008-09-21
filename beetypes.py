import PyQt4.QtCore as qtcore

# Global variables
fileformatversion=1

# custom event types
class BeeCustomEventTypes:
	refreshlayerslist = qtcore.QEvent.User

# custom enumerated types
class DrawingCommandTypes:
	quit, nonlayer, layer, alllayer, networkcontrol = range(5)

# events that may effect one or more layers
class NonLayerCommandTypes:
	undo, redo = range(2)

# events that effect only one layer
class LayerCommandTypes:
	alpha, mode, pendown, penmotion, penup, rawevent, tool = range(7)

# events that effect the list of layers, all layers or layer ownership
class AllLayerCommandTypes:
	scale, resize, layerup, layerdown, deletelayer, insertlayer, deleteall, releaselayer, layerownership = range(9)

# commands that are only used to communicate when in a network session
class NetworkControlCommandTypes:
	resyncrequest, resyncstart, resyncend = range(3)

class LayerTypes:
	user, animation, network = range(3)

class WindowTypes:
	singleuser, animation, networkclient, integratedserver, standaloneserver = range(5)

class ThreadTypes:
	user, animation, network, server = range(4)

# types of ways to modify the current selection
class SelectionModTypes:
	clear, new, intersect, add, subtract = range(5)
