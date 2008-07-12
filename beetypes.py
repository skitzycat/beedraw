import PyQt4.QtCore as qtcore

# Global variables
fileformatversion=1

# custom event types
class BeeCustomEventTypes:
	refreshlayerslist = qtcore.QEvent.User

# custom enumerated types
class DrawingCommandTypes:
	quit, nonlayer, layer, alllayer = range(4)

# events that don't (inherantly) at least effect any layers
class NonLayerCommandTypes:
	undo, redo = range(2)

# events that effect only one layer
class LayerCommandTypes:
	alpha, mode, pendown, penmotion, penup, rawevent, tool = range(7)

# events that effect the list of layers or all layers
class AllLayerCommandTypes:
	scale, resize, layerup, layerdown, createlayer, deletelayer, insertlayer, resync = range(8)

class LayerTypes:
	user, animation, network = range(3)

class WindowTypes:
	singleuser, animation, networkclient, integratedserver, standaloneserver = range(5)

class ThreadTypes:
	user, animation, network, server = range(4)

# types of ways to modify the current selection
class SelectionModTypes:
	clear, new, intersect, add, subtract = range(5)
