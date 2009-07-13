from beetypes import *

class CachedLayerEvent:
	def __init__(self,layer):
		self.layer=layer

	def process(self):
		""" Must be implemented in subclass """
		pass

	def send(self,id,queue):
		""" Must be implemented in subclass """
		pass


class CachedAlphaEvent(CachedLayerEvent):
	def __init__(self,layer,newalpha):
		CachedLayerEvent.__init__(self,layer)
		self.newalpha=newalpha

	def process(self):
		layer.setOptions(opacity=self.newalpha)

	def send(self,id,queue):
		queue.put((DrawingCommandTypes.layer,LayerCommandTypes.alpha,layer.key,self.newalpha),id)

class CachedModeEvent(CachedLayerEvent):
	def __init__(self,layer,newmode):
		CachedLayerEvent.__init__(self,layer)
		self.newmode=newmode

	def process(self):
		layer.setOptions(compmode=self.newmode)

	def send(self,id,queue):
		queue.put((DrawingCommandTypes.layer,LayerCommandTypes.mode,layer.key,self.newmode),id)

class CachedToolEvent(CachedLayerEvent):
	def __init__(self,layer,tool):
		CachedLayerEvent.__init__(self,layer)
		self.tool=tool
		self.points=[]

	def process(self):
		print "processing cached tool event"
		self.tool.penDown(self.points[0][0],self.points[0][1],self.points[0][2])
		for point in self.points[1:]:
			self.tool.penMotion(point[0],point[1],point[2])

		self.tool.penUp(self.points[-1][0],self.points[-1][1])

	def send(self,id,queue):
		print "Sending cached tool event to client:", id
		self.tool.pointshistory=self.points
		queue.put(((DrawingCommandTypes.layer,LayerCommandTypes.tool,self.layer.key,self.tool),id*-1))
