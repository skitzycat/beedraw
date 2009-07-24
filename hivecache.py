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
		self.tool.penDown(self.points[0][0],self.points[0][1],self.points[0][2])
		for point in self.points[1:]:
			self.tool.penMotion(point[0],point[1],point[2])

		self.tool.penUp(self.points[-1][0],self.points[-1][1])

	def send(self,id,queue):
		self.tool.pointshistory=self.points
		queue.put(((DrawingCommandTypes.layer,LayerCommandTypes.tool,self.layer.key,self.tool),id*-1))
