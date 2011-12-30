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
 
import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore
import math
import sys
import ImageChops
import ImageFilter
import numpy
import qimage2ndarray
from beeutil import *
from beetypes import *
from beeeventstack import *
from ImageQt import ImageQt
 
from PencilOptionsWidgetUi import *
from BrushOptionsWidgetUi import *
from SmudgeOptionsWidgetUi import *
from BlurOptionsWidgetUi import *
from EraserOptionsWidgetUi import *
from PaintBucketOptionsWidgetUi import *
from FeatherSelectOptionsWidgetUi import *
from SelectionModificationWidgetUi import *

from beeapp import BeeApp

from beelayer import BeeTemporaryLayer, BeeTemporaryLayerPIL
from scipy.ndimage.filters import gaussian_filter1d, gaussian_filter
 
try:
	import NumPy as numpy
except:
	try:
		import numpy
	except:
		import Numeric as numpy

# Class to manage tools and make instances as needed
class BeeToolBox:
	def __init__(self):
		self.toolslist=[]
		self.loadDefaultTools()
		self.curtoolindex=0
 
	def loadDefaultTools(self):
		self.toolslist.append(PencilToolDesc())
		self.toolslist.append(SketchToolDesc())
		self.toolslist.append(EraserToolDesc())
		self.toolslist.append(RectSelectionToolDesc())
		self.toolslist.append(EyeDropperToolDesc())
		self.toolslist.append(FeatherSelectToolDesc())
		self.toolslist.append(PaintBucketToolDesc())
		self.toolslist.append(MoveSelectionToolDesc())
		self.toolslist.append(SmudgeToolDesc())
		self.toolslist.append(BlurToolDesc())
		#self.toolslist.append(SmearToolDesc())
 
	def getCurToolDesc(self):
		return self.toolslist[self.curtoolindex]
 
	def setCurToolIndex(self,index):
		self.curtoolindex=index

	def setCurToolByName(self,name):
		for i in range(len(self.toolslist)):
			if name==self.toolslist[i].name:
				self.curtoolindex=i
				return True
		return False
 
	def getToolDescByName(self,name):
		for tool in self.toolslist:
			if name==tool.name:
				return tool
		print_debug("Error, toolbox couldn't find tool with name: %s" % name)
		return None

# Widget class to display a monochrome preview of a brush
class BrushPreviewWidget(qtgui.QWidget):
	def __init__(self,replacingwidget,brushimage=None,opacity=0):
		qtgui.QWidget.__init__(self,replacingwidget.parentWidget())
		replaceWidget(replacingwidget,self)
		self.updateBrush(brushimage,opacity)

	def updateBrush(self,brushimage,opacity):
		self.brushimage=brushimage
		self.opacity=opacity
		self.setFixedSize(brushimage.size())
		self.update()

	def paintEvent(self,event):
		rect = self.contentsRect()

		painter = qtgui.QPainter()
		painter.begin(self)
		painter.fillRect(rect,qtgui.QColor(255,255,255))
		painter.setOpacity(self.opacity)
		painter.drawImage(qtcore.QPoint(rect.x(),rect.y()),self.brushimage)

# Base class for a class to describe all tools and spawn tool instances
class AbstractToolDesc:
	def __init__(self,name):
		self.clippath=None
		self.options={}
		self.name=name
		self.displayname=name
		self.setDefaultOptions()
		self.optionswidget=None
 
	def pressToolButton(self):
		pass

	def getCursor(self):
		return qtcore.Qt.ArrowCursor
 
	def getDownCursor(self):
		return qtcore.Qt.ArrowCursor
 
	def setDefaultOptions(self):
		pass
 
	def getOptionsWidget(self,parent=None):
		return qtgui.QWidget(parent)

	def newModKeys(self,modkeys):
		pass

	# called when a change in the options for the tool cause the look to be different in such a way it needs to update other internal variables
	def updateBrush(self):
		pass
 
	# setup needed parts of tool using knowledge of current window
	# this should be implemented in subclass if needed
	def setupTool(self,window,layerkey):
		return None
 
	# what to do when this tool is no longer active
	def deactivate(self):
		pass
 
# base class for all drawing tools
class AbstractTool:
	logtype=ToolLogTypes.unlogable
	allowedonfloating=False
	def __init__(self,options,window):
		self.fgcolor=None
		self.bgcolor=None
		self.clippath=None
		self.options=options
		self.window=window
		self.layer=None
		self.layerkey=None

		self.prevpointshistory=[]
		self.pointshistory=[]

		# these are expected to get set if a tool is set to do raw logging
		self.oldstate=None
		self.changedarea=None

	# some things are better handled in the GUI thread (ability to use pixmaps) so if needed put it in this function
	# also anything that doesn't go out to remote sessions can be put here, such as selection controls.
	def guiLevelPenDown(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		pass

	def guiLevelPenMotion(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		pass

	def guiLevelPenUp(self,x,y,modkeys=qtcore.Qt.NoModifier):
		pass

	def newModKeys(self,modkeys):
		pass

	def setOption(self,key,value):
		self.options[key]=value
 
	# what to do when pen is down to be implemented in subclasses
	def penDown(self,x,y,pressure):
		pass
 
	def penMotion(self,x,y,pressure):
		pass
 
	def penUp(self,x=None,y=None,source=0):
		pass
 
	def penLeave(self):
		pass
 
	def penEnter(self):
		pass

	def cleanUp(self):
		pass

class EyeDropperToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"eyedropper")
		self.displayname="Eye Dropper"

	def setDefaultOptions(self):
		# option for if it should get color for a single layer or the whole visible image
		# curently this is set to just the whole visible image because otherwise for transparent colors it composes them onto black which doesn't look right at all
		self.options["singlelayer"]=0

	def pressToolButton(self):
		BeeApp().master.toolselectwindow.ui.eye_dropper_button.setChecked(True)
 
	def setupTool(self,window,layerkey):
		tool=EyeDropperTool(self.options,window)
		tool.name=self.name
		return tool

# eye dropper tool (select color from canvas)
class EyeDropperTool(AbstractTool):
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)
		self.name="Eye Dropper"

	def guiLevelPenDown(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		if self.options["singlelayer"]==0:
			color=self.window.getImagePixelColor(x,y)
		else:
			color=self.window.getCurLayerPixelColor(x,y)
		self.window.master.setFGColor(qtgui.QColor(color))

# basic tool for everything that draws points on the canvas
class DrawingTool(AbstractTool):
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)
		self.name="pencil"
		self.lastpressure=-1
		self.compmode=qtgui.QPainter.CompositionMode_SourceOver
		self.stampmode=qtgui.QPainter.CompositionMode_SourceOver
		self.layer=None
		self.pendown=False
		self.fullsizedbrush=None

		self.inside=True
		self.returning=False

		self.returnpoint=None
		self.logtype=ToolLogTypes.regular

		self.brushimageformat=BrushImageFormats.qt

	def guiLevelPenDown(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		""" guiLevelPenDown method of DrawingTool, if control key is pressed then do a color pick operation and flag the tool as not in drawing mode """
		if modkeys==qtcore.Qt.ControlModifier:
			color=self.window.getImagePixelColor(x,y)
			self.window.master.setFGColor(qtgui.QColor(color))
			self.logtype=ToolLogTypes.unlogable

		else:
			# this must be done here because adding items to the graphics scene must be performed in the GUI thread
			self.parentlayer=self.window.getLayerForKey(self.layerkey)

			if self.parentlayer:

				if self.brushimageformat==BrushImageFormats.qt:
					self.layer=self.parentlayer.getTmpLayer(self.options["opacity"]/100.,self.compmode)
				else:
					self.layer=self.parentlayer.getTmpLayerPIL(self.options["opacity"]/100.,self.compmode,self.clippath)

			else:
				self.logtype=ToolLogTypes.unlogable

	def calculateCloseEdgePoint(self,p1,p2):
		""" Stub for now, eventually I'd like this algorithm to take over if the other one encounters data that looks bad """
		return p2 

	def curBrushSize(self):
		if self.brushimageformat==BrushImageFormats.pil:
			return self.brushimage.size
		else:
			return self.brushimage.width(),self.brushimage.height()

	def calculateEdgePoint(self,p1,p2):
		""" Calculate where a continuation of two points would have left the canvas, does this by simply creating a line out of the points and looking for where the line crosses the visable area of the canvas"""
		# don't worry about this if it isn't a local layer
		if not self.window.localLayer(self.layerkey):
			return None

		rect=self.window.view.getVisibleImageRect()

		leftedge=rect.x()
		topedge=rect.y()

		rightedge=leftedge+rect.width()
		bottomedge=topedge+rect.height()

		# factor to go past the edge so the line seems to go all the way instead of stopping short
		brushsize=self.curBrushSize()
		edgefudge=brushsize[0]/2

		leftedge-=edgefudge
		topedge-=edgefudge

		rightedge+=edgefudge
		bottomedge+=edgefudge

		exitpoint=None

		dx=float(p2[0])-float(p1[0])
		dy=float(p2[1])-float(p1[1])

		# shouldn't ever get this as input, but just in case
		if dx==0 and dy==0:
			return None

		# special case for going parallel to a side
		if dx==0 or dy==0:
			m=None
			if dx==0:
				if dy<0:
					exitpoint=(p1[0],topedge)
				else:
					exitpoint=(p1[0],bottomedge)
			if dy==0:
				if dx<0:
					exitpoint=(leftedge,p1[1])
				else:
					exitpoint=(rightedge,p1[1])

		else:
			# calculate slope
			m=dy/dx

			# calculate line offset
			b=p1[1]-(m*p1[0])

			sides_to_check=[]

			if dy<0:
				sides_to_check.append("top")
			elif dy>0:
				sides_to_check.append("bottom")
	
			if dx<0:
				sides_to_check.append("left")
			elif dx>0:
				sides_to_check.append("right")
	
			for side in sides_to_check:
				if side=="top":
					x,y=findLineIntersection(-m,1,b,0,1,topedge)
					if x>leftedge and x<rightedge:
						exitpoint=(x,y)
				elif side=="bottom":
					x,y=findLineIntersection(-m,1,b,0,1,bottomedge)
					if x>leftedge and x<rightedge:
						exitpoint=(x,y)
				elif side=="right":
					x,y=findLineIntersection(-m,1,b,1,0,rightedge)
					if y>topedge and y<bottomedge:
						exitpoint=(x,y)
				elif side=="left":
					x,y=findLineIntersection(-m,1,b,1,0,leftedge)
					if y>topedge and y<bottomedge:
						exitpoint=(x,y)

		
		pointdistance=distance2d(p1[0],p1[1],p2[0],p2[1])
		edgedistance=distance2d(p2[0],p2[1],exitpoint[0],exitpoint[1])

		#print "last two points:", p1, p2
		#print "calculating edge point:", exitpoint
		#print "point distance, edge distance:", pointdistance, edgedistance

		# figure out if the calculated end point looks bad
		# right now the only easy to detect case is when the line is parallel to one edge
		if not m:
			exitpoint=self.calculateCloseEdgePoint(p1,p2)

		return exitpoint

	def calculateEdgePressure(self,p1,p2,pexit):
		""" method of DrawingTool """
		last_distance=distance2d(p1[0],p1[1],p2[0],p2[1])
		end_distance=distance2d(p2[0],p2[1],pexit[0],pexit[1])

		pressure_trend=p2[2]-p1[2]

		new_pressure=p2[2]+(pressure_trend*end_distance/last_distance)

		if new_pressure>1:
			new_pressure=1
		elif new_pressure<0:
			new_pressure=0

		return new_pressure
 
	def penLeave(self):
		""" method of DrawingTool """
		#print "Got penLeave"
		if self.pendown:
			# the leave point can only be calculated if there are multiple points in the current history
			if self.pointshistory and len(self.pointshistory) > 1:
				exitpoint=self.calculateEdgePoint(self.pointshistory[-2],self.pointshistory[-1])
				if exitpoint:
					exitpressure=self.calculateEdgePressure(self.pointshistory[-2],self.pointshistory[-1],exitpoint)
				#print "Exit point:",exitpoint,exitpressure

					self.continueLine(exitpoint[0],exitpoint[1],exitpressure)

			self.inside=False
			self.returning=False

	def penEnter(self):
		""" method of DrawingTool """
		if self.logtype==ToolLogTypes.unlogable:
			return
		#print "Got penEnter"
		if self.pendown:
			self.returning=True
			self.inside=True

	def updateBrushForPressure(self,pressure,pixelx=0,pixely=0):
		""" method of DrawingTool """
		# see if we need to update at all
		if self.lastpressure==pressure:
			return
 
		self.lastpressure=pressure
 
		# if we can use the full sized brush do it
		if self.options["pressuresize"]==0 or pressure==1:
			self.brushimage=self.fullsizedbrush
			self.lastpressure=1
			return
 
		# scaled size for brush
		bdiameter=self.scaleForPressure(pressure)*self.options["maxdiameter"]
		self.diameter=int(math.ceil(bdiameter))

		# make target size an odd number
		if self.diameter%2==0:
			self.diameter+=1

		# calculate offset into target
		targetoffsetx=((self.diameter-bdiameter)/2.)-.5+(pixelx%1)
		targetoffsety=((self.diameter-bdiameter)/2.)-.5+(pixely%1)
 
		# bounding radius for pixels to update
		side=self.diameter
 
		fullsizedrect=qtcore.QRectF(0,0,self.fullsizedbrush.width(),self.fullsizedbrush.height())
		cursizerect=qtcore.QRectF(targetoffsetx,targetoffsety,bdiameter,bdiameter)
 
		self.brushimage=qtgui.QImage(side,side,qtgui.QImage.Format_ARGB32_Premultiplied)
		self.brushimage.fill(0)
		painter=qtgui.QPainter()
		painter.begin(self.brushimage)
 
		painter.drawImage(cursizerect,self.fullsizedbrush,fullsizedrect)

		painter.end()

		# make sure brush isn't blank by pasting the brush color onto the center pixel
		center=int(self.diameter/2)
		self.brushimage.setPixel(center,center,self.fgcolor)
 
	def penDown(self,x,y,pressure):
		""" penDown method of DrawingTool """
		if self.logtype==ToolLogTypes.unlogable:
			return

		self.returning=False
		self.inside=True
		self.pendown=True

		self.startLine(x,y,pressure)

	# determine if it's moved far enough that we care
	def movedFarEnough(self,x,y):
		""" method of DrawingTool """
		if int(x)==int(self.lastpoint[0]) and int(y)==int(self.lastpoint[1]):
			return False
		return True

	# return how much to scale down the brush for the current pressure
	def scaleForPressure(self,pressure):
		""" method of DrawingTool """
		minsize=self.options["mindiameter"]
		maxsize=self.options["maxdiameter"]
		sizediff=maxsize-minsize

		scale=((sizediff*pressure) + minsize)/maxsize
		return scale

	def getFullSizedBrushWidth(self):
		""" method of DrawingTool """
		return self.fullsizedbrush.width()

	# since windows apparently won't catch return and leave events when the button is pressed down I'm forced to do this
	def checkForPenBounds(self,x,y):
		""" method of DrawingTool """
		if not self.pendown:
			return
		# only needed if this is a local layer
		if not self.window.localLayer(self.layerkey):
			return

		rect=self.window.view.getVisibleImageRect()
		inside=rect.contains(qtcore.QPointF(x,y))
		if inside and not self.inside:
			self.penEnter()

		if not inside and self.inside:
			self.penLeave()

	def penMotion(self,x,y,pressure):
		""" method of DrawingTool """
		#print "penMotion:",x,y,pressure
		self.checkForPenBounds(x,y)
		if not self.pendown or not self.inside:
			return

		if self.returning:
			#print "detected pen return"
			if not self.returnpoint:
				self.returnpoint=(x,y,pressure)
				return

			self.returning=False

			enterpoint=self.calculateEdgePoint((x,y,pressure),self.returnpoint)
			if enterpoint:
				enterpressure=self.calculateEdgePressure((x,y,pressure),self.returnpoint,enterpoint)

				self.startLine(enterpoint[0],enterpoint[1],enterpressure)
				self.penMotion(self.returnpoint[0],self.returnpoint[1],self.returnpoint[2])
			else:
				self.startLine(self.returnpoint[0],self.returnpoint[1],self.returnpoint[2])
			self.penMotion(x,y,pressure)

			self.returnpoint=None
			return

		self.continueLine(x,y,pressure)

	def continueLine(self,x,y,pressure):
		""" method of DrawingTool """
		# if it hasn't moved just do nothing
		if not self.movedFarEnough(x,y):
			return

		#print "starting new line"
		self.pointshistory.append((x,y,pressure))
 
		# get size of layer
		layerwidth=self.window.docwidth
		layerheight=self.window.docheight
 
		# get points inbetween according to step option and layer size
		path=getPointsPath(self.lastpoint[0],self.lastpoint[1],x,y,self.options['step'],layerwidth,layerheight,self.lastpressure,pressure)

		# if no points are on the layer just return
		if len(path)==0:
			return

		# figure out the maximum radius the brush will have
		maxradius=int(math.ceil(self.getFullSizedBrushWidth()/2.0))

		#print "maxradius:", maxradius
		#print "path:", path

		# calculate the bounding rect for this operation
		left=int(math.floor(min(path[0][0],path[-1][0])-maxradius)-1)
		top=int(math.floor(min(path[0][1],path[-1][1])-maxradius)-1)
		right=int(math.ceil(max(path[0][0],path[-1][0])+maxradius)+1)
		bottom=int(math.ceil(max(path[0][1],path[-1][1])+maxradius)+1)

		left=max(0,left)
		top=max(0,top)
		right=min(layerwidth,right)
		bottom=min(layerheight,bottom)

		# calulate area needed to hold everything
		width=right-left
		height=bottom-top
 
		if self.brushimageformat==BrushImageFormats.qt:

			# then make an image for that bounding rect
			#lineimage=qtgui.QImage(width,height,qtgui.QImage.Format_ARGB32_Premultiplied)
			#lineimage.fill(0)

			# put points in that image
			#painter=qtgui.QPainter()
			#painter.begin(lineimage)
			#painter.setRenderHint(qtgui.QPainter.HighQualityAntialiasing)
 
			for point in path:
				self.updateBrushForPressure(point[2],point[0],point[1])

				xradius=self.brushimage.width()/2
				yradius=self.brushimage.height()/2

				pointx=point[0]
				pointy=point[1]

				stampx=pointx-left-xradius
				stampy=pointy-top-yradius

				stampx=int(stampx)
				stampy=int(stampy)

				if self.brushimage.width()%2==0:
					if pointx%1<.5:
						stampx-=1
					if pointy%1<.5:
						stampy-=1

				#print "stamping at point:", stampx, stampy
				#printImage(self.brushimage)

				#painter.drawImage(stampx,stampy,self.brushimage)
				self.addImageToLayer(self.brushimage,pointx-xradius,pointy-yradius,refresh=False)
 
			#painter.end()

			#print "stamping line image:"
			#printImage(lineimage)

		else:

			for point in path:
				self.updateBrushForPressure(point[2],point[0],point[1])

				brushwidth=self.brushimage.size[0]
				brushheight=self.brushimage.size[1]

				xradius=brushwidth/2
				yradius=brushheight/2

				pointx=point[0]
				pointy=point[1]

				self.addImageToLayer(self.brushimage,pointx-xradius,pointy-yradius,refresh=False)

		#self.layer.update(refresharea)
		refresharea=qtcore.QRectF(left,top,width,height)
		self.layer.updateScene(refresharea)
		#self.layer.scene().update(refresharea)
 
		#self.layer.compositeFromCenter(lineimage,left,top,self.stampmode,self.clippath)
		#self.addImageToLayer(lineimage,left,top)
 
		self.lastpoint=(path[-1][0],path[-1][1])

	def addImageToLayer(self,image,left,top,refresh=True,stampmode=None):
		if not self.layer:

			# this should only happen if we are in a server drawing thread when using a tool that creates a temporary layer.  In that case the layer isn't already created, so create something to use as a temporary layer now.
			self.parentlayer=self.window.getLayerForKey(self.layerkey)

			if self.brushimageformat==BrushImageFormats.qt:
				self.layer=self.parentlayer.getTmpLayer(self.options["opacity"]/100.,self.compmode)
			else:
				self.layer=self.parentlayer.getTmpLayerPIL(self.options["opacity"]/100.,self.compmode,self.clippath)

		if not stampmode:
			stampmode=self.stampmode

		#print "compositing image into layer:"
		#printImage(image)
		self.layer.compositeFromCorner(image,left,top,stampmode,self.clippath, refreshimage=refresh)
 
	def startLine(self,x,y,pressure):
		""" method of DrawingTool """
		if self.pointshistory:
			self.prevpointshistory.append(self.pointshistory)

		self.pointshistory=[(x,y,pressure)]
		self.lastpoint=(x,y)
		self.updateBrushForPressure(pressure,x,y)

		if self.brushimageformat==BrushImageFormats.qt:
			brushwidth=self.brushimage.width()
			brushheight=self.brushimage.height()
		else:
			brushwidth=self.brushimage.size[0]
			brushheight=self.brushimage.size[1]

		targetx=int(x)-int(brushwidth/2)
		targety=int(y)-int(brushheight/2)

		# if this is an even number then do adjustments for the center if needed
		if brushwidth%2==0:
			#print "this is an even sized brush:"
			if x%1>.5:
				targetx+=1
			if y%1>.5:
				targety+=1

		#self.layer.compositeFromCorner(self.brushimage,targetx,targety,self.stampmode,self.clippath)
		self.addImageToLayer(self.brushimage,targetx,targety)

	def cleanupTmpLayer(self):
		self.oldlayerimage=self.parentlayer.getImageCopy()

		parentimagelock=qtcore.QWriteLocker(self.parentlayer.imagelock)

		if self.brushimageformat==BrushImageFormats.qt:
			tmplayerimage=self.layer.getImageCopy()
		else:
			tmplayerimage=PilToQImage(self.layer.pilimage)

		self.layer.removeFromScene()
		#self.layer.setParentItem(None)
		#self.window.scene.removeItem(self.layer)

		self.parentlayer.compositeFromCorner(tmplayerimage,0,0,self.layer.compmode,opacity=self.layer.getOpacity(),lock=parentimagelock,clippath=self.clippath)

		parentimagelock.unlock()

		#self.window.scene.update()
		self.layer.updateScene()

	def penUp(self,x=None,y=None):
		""" penUp method of DrawingTool class """
		#print "Got penUp"
		self.pendown=False

		if not self.pointshistory:
			return

		self.cleanupTmpLayer()

		radius=int(math.ceil(self.options["maxdiameter"]))
 
		# get maximum bounds of whole brush stroke
		left=self.pointshistory[0][0]
		right=self.pointshistory[0][0]
		top=self.pointshistory[0][1]
		bottom=self.pointshistory[0][1]
		for line in self.prevpointshistory:
			for point in line:
				if point[0]<left:
					left=point[0]
				elif point[0]>right:
					right=point[0]

				if point[1]<top:
					top=point[1]
				elif point[1]>bottom:
					bottom=point[1]

		for point in self.pointshistory:
			if point[0]<left:
				left=point[0]
			elif point[0]>right:
				right=point[0]
 
			if point[1]<top:
				top=point[1]
			elif point[1]>bottom:
				bottom=point[1]
 
		# calculate bounding area of whole event
		self.changedarea=qtcore.QRect(left-radius,top-radius,right+(radius*2),bottom+(radius*2))
		
		# bound it by the area of the layer
		self.changedarea=rectIntersectBoundingRect(self.changedarea,self.layer.getImageRect())
 
		# get image of what area looked like before
		oldimage=self.oldlayerimage.copy(self.changedarea)
 
		command=DrawingCommand(self.layerkey,oldimage,self.changedarea)

		self.window.addCommandToHistory(command,self.getOwner())
 
		BeeApp().master.refreshLayerThumb(self.window.id,self.layerkey)

	def getOwner(self):
		return self.parentlayer.owner

# this is the most basic drawing tool
class PencilToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"pencil")
		self.displayname="Pencil"
		self.updateBrush()

	def updateBrush(self):
		self.makeFullSizedBrush()
		widget = self.getOptionsWidget()
		if widget:
			widget.ui.brushpreviewwidget.updateBrush(self.fullsizedbrush,self.options["opacity"]/100.)
 
	def getCursor(self):
		return qtcore.Qt.CrossCursor
 
	def getDownCursor(self):
		return getBlankCursor()
 
	def setDefaultOptions(self):
		self.options["maxdiameter"]=21
		self.options["mindiameter"]=0
		self.options["step"]=1
		self.options["pressuresize"]=1
		self.options["pressurebalance"]=100
		self.options["opacity"]=100

	def pressToolButton(self):
		BeeApp().master.toolselectwindow.ui.pencil_button.setChecked(True)
 
	def setupTool(self,window,layerkey):
		tool=DrawingTool(self.options,window)
		tool.name=self.name

		# setup fullsized brush 
		width=self.diameter
		height=self.diameter
		coloredfullbrush=qtgui.QImage(width,height,qtgui.QImage.Format_ARGB32_Premultiplied)
		coloredfullbrush.fill(BeeApp().master.getFGColor().rgba())
		painter = qtgui.QPainter()
		painter.begin(coloredfullbrush)
		painter.setCompositionMode(qtgui.QPainter.CompositionMode_DestinationIn)
		painter.drawImage(qtcore.QPoint(0,0),self.fullsizedbrush)
		painter.end()
		tool.fullsizedbrush=coloredfullbrush

		tool.fgcolor=BeeApp().master.getFGColor().rgba()
		tool.layerkey=layerkey
 
		# if there is a selection get a copy of it
		tool.clippath=window.getClipPathCopy()
 
		return tool

	def makeFullSizedBrush(self):
		""" method of DrawingToolDesc """
		colortuple=(0,0,0,255)

		self.diameter=self.options["maxdiameter"]
		width=self.diameter
		height=self.diameter

		radius=width/2.
		imgwidth=int(math.ceil(width))
		imgheight=int(math.ceil(height))

		# use a greyscale image here to reduce number of calculations
		fullsizedbrush=Image.new("RGBA",(imgwidth,imgheight),(0,0,0,0))

		# create raw access object for faster pixel setting
		pix=fullsizedbrush.load()

		for i in range(width):
			for j in range(height):
				distance=math.sqrt(((i+.5-radius)**2)+((j+.5-radius)**2))
				if distance <= radius:
					pix[i,j]=colortuple

		self.fullsizedbrush=PilToQImage(fullsizedbrush)
 
	def getOptionsWidget(self,parent=None):
		if parent and not self.optionswidget:
			self.optionswidget=DrawingToolOptionsWidget(parent,self)
			self.optionswidget.updateDisplayFromOptions()
		return self.optionswidget
		

class DrawingToolOptionsWidget(qtgui.QWidget):
	def __init__(self,parent,tooldesc):
		qtgui.QWidget.__init__(self,parent)
		self.tooldesc=tooldesc

		# setup user interface
		self.ui=Ui_PencilOptionsWidget()
		self.ui.setupUi(self)

		self.ui.brushpreviewwidget = BrushPreviewWidget(self.ui.brushpreviewwidget,tooldesc.fullsizedbrush,1)

	def updateDisplayFromOptions(self):
		self.ui.brushdiameter.setValue(self.tooldesc.options["maxdiameter"])
		self.ui.brushmindiameter.setValue(self.tooldesc.options["mindiameter"])
		self.ui.stepsize.setValue(self.tooldesc.options["step"])
		self.ui.opacity.setValue(self.tooldesc.options["opacity"])

	def on_brushdiameter_valueChanged(self,value):
		self.tooldesc.options["maxdiameter"]=value
		self.tooldesc.updateBrush()

	def on_brushmindiameter_valueChanged(self,value):
		self.tooldesc.options["mindiameter"]=value

	def on_stepsize_valueChanged(self,value):
		self.tooldesc.options["step"]=value

	def on_opacity_valueChanged(self,value):
		self.tooldesc.options["opacity"]=value
		self.tooldesc.updateBrush()
 
class EraserToolDesc(PencilToolDesc):
	# describe actual tool
	class Tool(DrawingTool):
		def __init__(self,options,window):
			DrawingTool.__init__(self,options,window)
			self.compmode=qtgui.QPainter.CompositionMode_DestinationOut
			self.fgcolor=0
 
	# back to description stuff
	def __init__(self):
		AbstractToolDesc.__init__(self,"eraser")
		self.displayname="Eraser"
		self.updateBrush()
 
	def pressToolButton(self):
		BeeApp().master.toolselectwindow.ui.eraser_button.setChecked(True)
 
	def setDefaultOptions(self):
		self.options["maxdiameter"]=21
		self.options["mindiameter"]=0
		self.options["step"]=1
		self.options["pressuresize"]=1
		self.options["pressurebalance"]=100
		self.options["blur"]=100
		self.options["opacity"]=100
 
	def setupTool(self,window,layerkey):
		tool=self.Tool(self.options,window)
		tool.name=self.name
		tool.clippath=window.getClipPathCopy()
		tool.layerkey=window.curlayerkey

		# setup fullsized brush 
		width=self.diameter
		height=self.diameter
		coloredfullbrush=qtgui.QImage(width,height,qtgui.QImage.Format_ARGB32_Premultiplied)
		coloredfullbrush.fill(qtgui.QColor(0,0,0).rgba())
		painter = qtgui.QPainter()
		painter.begin(coloredfullbrush)
		painter.setCompositionMode(qtgui.QPainter.CompositionMode_DestinationIn)
		painter.drawImage(qtcore.QPoint(0,0),self.fullsizedbrush)
		painter.end()
		tool.fullsizedbrush=coloredfullbrush

		return tool

	def getOptionsWidget(self,parent=None):
		if not self.optionswidget:
			self.optionswidget=EraserOptionsWidget(parent,self)
			self.optionswidget.updateDisplayFromOptions()
		return self.optionswidget

class EraserOptionsWidget(qtgui.QWidget):
	def __init__(self,parent,tooldesc):
		qtgui.QWidget.__init__(self,parent)
		self.tooldesc=tooldesc

		# setup user interface
		self.ui=Ui_EraserOptionsWidget()
		self.ui.setupUi(self)

		self.ui.brushpreviewwidget = BrushPreviewWidget(self.ui.brushpreviewwidget,tooldesc.fullsizedbrush,1)

	def updateDisplayFromOptions(self):
		self.ui.eraserdiameter.setValue(self.tooldesc.options["maxdiameter"])
		self.ui.mindiameter.setValue(self.tooldesc.options["mindiameter"])
		self.ui.stepsize.setValue(self.tooldesc.options["step"])

	def on_eraserdiameter_valueChanged(self,value):
		self.tooldesc.options["maxdiameter"]=value
		self.tooldesc.updateBrush()

	def on_mindiameter_valueChanged(self,value):
		self.tooldesc.options["mindiameter"]=value

	def on_stepsize_valueChanged(self,value):
		self.tooldesc.options["step"]=value

class RectangleSelectionPickOverlay(qtgui.QGraphicsItem):
	def __init__(self,width,height):
		qtgui.QGraphicsItem.__init__(self)
		self.boundingrect=qtcore.QRect(0,0,width,height)
		self.rect=qtcore.QRect()

	def updateArea(self,newrect):
		self.rect=newrect

	def boundingRect(self):
		return qtcore.QRectF(self.boundingrect)

	def paint(self,painter,options,widget=None):
		if not self.rect.isNull():
			painter.setPen(qtgui.QColor(255,255,255))
			painter.drawRect(self.rect)

			pen=qtgui.QPen(qtgui.QColor(0,0,0))
			pen.setDashPattern([4,4])
			painter.setPen(pen)
			painter.drawRect(self.rect)
 
# basic rectangle selection tool
class SelectionTool(AbstractTool):
	logtype=ToolLogTypes.selection
	def __init__(self,desc,options,window):
		AbstractTool.__init__(self,options,window)
		self.desc=desc
 
	def updateOverlay(self,x=None,y=None):
		if x==None:
			x=self.lastpoint[0]
			y=self.lastpoint[1]

		# calculate rectangle defined by the start and current
		if self.options["drawcenter"]==SelectionDrawTypes.fromcorner:
			left=min(x,self.startpoint[0])
			width=max(x,self.startpoint[0])-left
			top=min(y,self.startpoint[1])
			height=max(y,self.startpoint[1])-top

			if self.options["fixedaspect"]==SelectionRatioTypes.fixed:
				if y>self.startpoint[1]:
					height=width
				else:
					height=width
					top=self.startpoint[1]-width

		elif self.options["drawcenter"]==SelectionDrawTypes.fromcenter:
			left=self.startpoint[0]-abs(x-self.startpoint[0])
			width=abs(x-self.startpoint[0])*2
			top=self.startpoint[1]-abs(y-self.startpoint[1])
			height=abs(y-self.startpoint[1])*2

			if self.options["fixedaspect"]==SelectionRatioTypes.fixed:
				top=self.startpoint[1]-(width/2)
				height=width

		else:
			print_debug("Unknown draw center type in SelectionTool.updateOverlay")
			return
 
		oldrect=self.window.tooloverlay.rect
		newrect=qtcore.QRect(left,top,width,height)
		self.window.tooloverlay.updateArea(newrect)

		# calculate area we need to refresh, it should be the union of rect to draw
		# next and the last one that was drawn
		dirtyrect=newrect.united(oldrect)
		# increase the size just in case
		dirtyrect.adjust(-1,-1,2,2)
 
		self.window.view.updateView(dirtyrect)

 
	def guiLevelPenDown(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		self.overlay=RectangleSelectionPickOverlay(self.window.docwidth,self.window.docheight)
		self.window.changeToolOverlay(self.overlay)
		self.pendown=True
		x=int(x)
		y=int(y)
		self.startpoint=(x,y)
		self.lastpoint=(x,y)
 
	def guiLevelPenUp(self,x,y,modkeys=qtcore.Qt.NoModifier):
		self.pendown=False
		selectionop=self.options["modtype"]

		if self.overlay:
			path=qtgui.QPainterPath()
			path.addRect(qtcore.QRectF(self.overlay.rect))

			self.window.addSelectionChangeToQueue(selectionop,path)

		self.window.changeToolOverlay()
		self.overlay=None

		self.desc.resetOptions()

		# not sure why I need this, but without it there ends up being an extra reference to the window after it is closed which prevents memory cleanup
		self.window=None

	# set overlay to display area that would be selected if user lifted up button
	def guiLevelPenMotion(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		if not self.pendown:
			return

		#x,y=self.window.view.snapPointToView(x,y)
		x,y=self.window.view.snapPointToScene(x,y)

		x=int(x)
		y=int(y)
		if self.startpoint[0]==x or self.startpoint[1]==y:
			self.window.cursoroverlay=None
			return
 
		self.updateOverlay(x,y)
		self.lastpoint=(x,y)

# this is the most basic selection tool (rectangular)
class RectSelectionToolDesc(AbstractToolDesc):
	logtype=ToolLogTypes.selection
	def __init__(self):
		AbstractToolDesc.__init__(self,"rectselect")
		self.displayname="Rectangle Selection"
		self.curtool=None

	def setDefaultOptions(self):
		self.options["modtype"]=SelectionModTypes.new
		self.options["drawcenter"]=SelectionDrawTypes.fromcorner
		self.options["fixedaspect"]=SelectionRatioTypes.free

	def setupTool(self,window,layerkey):
		self.curtool=SelectionTool(self,self.options,window)
		self.curtool.name=self.name
		return self.curtool

	def pressToolButton(self):
		BeeApp().master.toolselectwindow.ui.rectangle_select_button.setChecked(True)
		self.oldmodkeys=BeeApp().app.keyboardModifiers()
 
	def getOptionsWidget(self,parent=None):
		if not self.optionswidget:
			self.optionswidget=ShapeSelectionOptionsWidget(parent,self)
			self.optionswidget.updateDisplayFromOptions()

		return self.optionswidget

	def newModKeys(self,modkeys):
		if not self.optionswidget:
			return

		# check for what is currently held down
		# under linux pressing the alt and shift key in the wrong order will cause it to look like the meta key is being used, but it seems to work fine under windows
		if modkeys & qtcore.Qt.ShiftModifier and modkeys & qtcore.Qt.AltModifier:
			self.optionswidget.ui.intersect_selection_button.setChecked(True)
		elif modkeys & qtcore.Qt.ShiftModifier:
			self.optionswidget.ui.add_selection_button.setChecked(True)
		elif modkeys & qtcore.Qt.AltModifier:
			self.optionswidget.ui.subtract_selection_button.setChecked(True)
		else:
			self.optionswidget.ui.new_selection_button.setChecked(True)

		if self.curtool and self.curtool.pendown:
			# see what has toggled if we are currently drawing something
			if self.oldmodkeys & qtcore.Qt.ShiftModifier and not modkeys & qtcore.Qt.ShiftModifier:
				self.optionswidget.ui.checkBox_fixed_aspect.toggle()
				self.curtool.updateOverlay()

			if self.oldmodkeys & qtcore.Qt.AltModifier and not modkeys & qtcore.Qt.AltModifier:
				self.optionswidget.ui.checkBox_draw_center.toggle()
				self.curtool.updateOverlay()

		self.oldmodkeys=modkeys

	def resetOptions(self):
		self.optionswidget.ui.checkBox_fixed_aspect.setChecked(False)
		self.optionswidget.ui.checkBox_draw_center.setChecked(False)

class ShapeSelectionOptionsWidget(qtgui.QWidget):
	def __init__(self,parent,tooldesc):
		qtgui.QWidget.__init__(self,parent)
		self.tooldesc=tooldesc

		self.ui=Ui_SelectionModificationWidget()
		self.ui.setupUi(self)

	def updateDisplayFromOptions(self):
		if self.tooldesc.options["modtype"]==SelectionModTypes.new:
			self.ui.new_selection_button.setChecked(True)
		elif self.tooldesc.options["modtype"]==SelectionModTypes.add:
			self.ui.add_selection_button.setChecked(True)
		elif self.tooldesc.options["modtype"]==SelectionModTypes.subtract:
			self.ui.subtract_selection_button.setChecked(True)
		elif self.tooldesc.options["modtype"]==SelectionModTypes.intersect:
			self.ui.intersect_selection_button.setChecked(True)

		if self.tooldesc.options["drawcenter"]==SelectionDrawTypes.fromcorner:
			self.ui.checkBox_draw_center.setChecked(False)
		elif self.tooldesc.options["drawcenter"]==SelectionDrawTypes.fromcenter:
			self.ui.checkBox_draw_center.setChecked(True)

		if self.tooldesc.options["fixedaspect"]==SelectionRatioTypes.fixed:
			self.ui.checkBox_fixed_aspect.setChecked(True)
		elif self.tooldesc.options["fixedaspect"]==SelectionRatioTypes.free:
			self.ui.checkBox_fixed_aspect.setChecked(False)

	def on_new_selection_button_toggled(self,bool=None):
		if bool:
			self.tooldesc.options["modtype"]=SelectionModTypes.new

	def on_add_selection_button_toggled(self,bool=None):
		if bool:
			self.tooldesc.options["modtype"]=SelectionModTypes.add

	def on_subtract_selection_button_toggled(self,bool=None):
		if bool:
			self.tooldesc.options["modtype"]=SelectionModTypes.subtract

	def on_intersect_selection_button_toggled(self,bool=None):
		if bool:
			self.tooldesc.options["modtype"]=SelectionModTypes.intersect

	def on_checkBox_draw_center_toggled(self,bool=None):
		if bool:
			self.tooldesc.options["drawcenter"]=SelectionDrawTypes.fromcenter
		else:
			self.tooldesc.options["drawcenter"]=SelectionDrawTypes.fromcorner

	def on_checkBox_fixed_aspect_toggled(self,bool=None):
		if bool:
			self.tooldesc.options["fixedaspect"]=SelectionRatioTypes.fixed
		else:
			self.tooldesc.options["fixedaspect"]=SelectionRatioTypes.free

# fuzzy selection tool description
class FeatherSelectToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"featherselect")
		self.displayname="Feather Selection"

	def pressToolButton(self):
		BeeApp().master.toolselectwindow.ui.feather_select_button.setChecked(True)
		self.oldmodkeys=BeeApp().app.keyboardModifiers()

	def setDefaultOptions(self):
		self.options["modtype"]=SelectionModTypes.new
		self.options["similarity"]=10
		self.options["selectiontype"]=BucketFillTypes.layer

	def setupTool(self,window,layerkey):
		if not layerkey:
			layerkey=window.getCurLayerKey()
		tool=FeatherSelectTool(self.options,window)
		tool.name=self.name
		tool.layerkey=layerkey
		return tool

	def getOptionsWidget(self,parent=None):
		if not self.optionswidget:
			self.optionswidget=FeatherSelectOptionsWidget(parent,self)
			self.optionswidget.updateDisplayFromOptions()
		return self.optionswidget

	def newModKeys(self,modkeys):
		if not self.optionswidget:
			return

		# check for what is currently held down
		# under linux pressing the alt and shift key in the wrong order will cause it to look like the meta key is being used, but it seems to work fine under windows
		if modkeys & qtcore.Qt.ShiftModifier and modkeys & qtcore.Qt.AltModifier:
			self.optionswidget.ui.intersect_selection_button.setChecked(True)
		elif modkeys & qtcore.Qt.ShiftModifier:
			self.optionswidget.ui.add_selection_button.setChecked(True)
		elif modkeys & qtcore.Qt.AltModifier:
			self.optionswidget.ui.subtract_selection_button.setChecked(True)
		else:
			self.optionswidget.ui.new_selection_button.setChecked(True)

class FeatherSelectOptionsWidget(qtgui.QWidget):
	def __init__(self,parent,tooldesc):
		qtgui.QWidget.__init__(self,parent)
		self.tooldesc=tooldesc

		self.ui=Ui_FeatherSelectOptions()
		self.ui.setupUi(self)

	def updateDisplayFromOptions(self):
		if self.tooldesc.options["modtype"]==SelectionModTypes.new:
			self.ui.new_selection_button.setChecked(True)
		elif self.tooldesc.options["modtype"]==SelectionModTypes.add:
			self.ui.add_selection_button.setChecked(True)
		elif self.tooldesc.options["modtype"]==SelectionModTypes.subtract:
			self.ui.subtract_selection_button.setChecked(True)
		elif self.tooldesc.options["modtype"]==SelectionModTypes.intersect:
			self.ui.intersect_selection_button.setChecked(True)

		if self.tooldesc.options["selectiontype"]==BucketFillTypes.layer:
			self.ui.radio_cur_layer.setChecked(True)
		elif self.tooldesc.options["selectiontype"]==BucketFillTypes.image:
			self.ui.radio_whole_image.setChecked(True)

		self.ui.color_threshold_box.setValue(self.tooldesc.options["similarity"])

	def on_color_threshold_box_valueChanged(self,value):
		if type(value)==int:
			self.tooldesc.options["similarity"]=value

	def on_radio_whole_image_clicked(self,bool=None):
		self.tooldesc.options["selectiontype"]=BucketFillTypes.selection

	def on_radio_cur_layer_clicked(self,bool=None):
		self.tooldesc.options["selectiontype"]=BucketFillTypes.layer

	def on_new_selection_button_toggled(self,bool=None):
		if bool:
			self.tooldesc.options["modtype"]=SelectionModTypes.new

	def on_add_selection_button_toggled(self,bool=None):
		if bool:
			self.tooldesc.options["modtype"]=SelectionModTypes.add

	def on_subtract_selection_button_toggled(self,bool=None):
		if bool:
			self.tooldesc.options["modtype"]=SelectionModTypes.subtract

	def on_intersect_selection_button_toggled(self,bool=None):
		if bool:
			self.tooldesc.options["modtype"]=SelectionModTypes.intersect

# fuzzy selection tool
class FeatherSelectTool(AbstractTool):
	logtype=ToolLogTypes.selection
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)

	def guiLevelPenDown(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		selectionop=self.options["modtype"]

		if self.options["selectiontype"]==BucketFillTypes.layer:
			layer=self.window.getLayerForKey(self.layerkey)
			if layer:
				image=layer.getImageCopy()
			else:
				image=self.window.scene.getImageCopy()
		else:
			image=self.window.scene.getImageCopy()

		self.newpath=getSimilarColorPath(image,x,y,self.options['similarity'])
		if not self.newpath.isEmpty():
			self.window.changeToolOverlay()
			self.window.changeSelection(selectionop,self.newpath)

# paint bucket tool description
class PaintBucketToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"bucket")
		self.displayname="Paint Bucket"

	def pressToolButton(self):
		BeeApp().master.toolselectwindow.ui.paint_bucket_button.setChecked(True)

	def setDefaultOptions(self):
		self.options["similarity"]=10
		self.options["bucketfilltype"]=BucketFillTypes.layer

	def setupTool(self,window,layerkey):
		if not layerkey:
			layerkey=window.curlayerkey

		tool=PaintBucketTool(self.options,window)
		tool.name=self.name

		tool.fgcolor=qtgui.QColor(window.master.fgcolor)
		tool.layerkey=layerkey

		# if there is a selection get a copy of it
		tool.clippath=window.getClipPathCopy()

		return tool

	def getOptionsWidget(self,parent=None):
		if not self.optionswidget:
			self.optionswidget=PaintBucketOptionsWidget(parent,self)
			self.optionswidget.updateDisplayFromOptions()
		return self.optionswidget

class PaintBucketOptionsWidget(qtgui.QWidget):
	def __init__(self,parent,tooldesc):
		qtgui.QWidget.__init__(self,parent)
		self.tooldesc=tooldesc

		# setup user interface
		self.ui=Ui_PaintBucketOptions()
		self.ui.setupUi(self)

	def updateDisplayFromOptions(self):
		if self.tooldesc.options["bucketfilltype"]==BucketFillTypes.selection:
			self.ui.radio_whole_selection.setChecked(True)
		elif self.tooldesc.options["bucketfilltype"]==BucketFillTypes.layer:
			self.ui.radio_cur_layer.setChecked(True)
		elif self.tooldesc.options["bucketfilltype"]==BucketFillTypes.image:
			self.ui.radio_whole_image.setChecked(True)

		self.ui.color_threshold_box.setValue(self.tooldesc.options["similarity"])

	def on_color_threshold_box_valueChanged(self,value):
		if type(value)==int:
			self.tooldesc.options["similarity"]=value

	def on_radio_whole_selection_clicked(self,bool=None):
		self.tooldesc.options["bucketfilltype"]=BucketFillTypes.selection

	def on_radio_cur_layer_clicked(self,bool=None):
		self.tooldesc.options["bucketfilltype"]=BucketFillTypes.layer

	def on_radio_whole_image_clicked(self,bool=None):
		self.tooldesc.options["bucketfilltype"]=BucketFillTypes.image

# paint bucket tool
class PaintBucketTool(AbstractTool):
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)
		self.newpath=None
		self.logtype=ToolLogTypes.raw

	def guiLevelPenDown(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		layer=self.window.getLayerForKey(self.layerkey)
		if not layer:
			self.logtype=ToolLogTypes.unlogable
			return

		if self.options['bucketfilltype']==BucketFillTypes.image:
			image=self.window.scene.getImageCopy()
			self.newpath=getSimilarColorPath(image,x,y,self.options['similarity'])

		elif self.options['bucketfilltype']==BucketFillTypes.layer:
			image=layer.getImageCopy()
			self.newpath=getSimilarColorPath(image,x,y,self.options['similarity'])

	def penDown(self,x,y,pressure):
		if self.logtype==ToolLogTypes.unlogable:
			return

		layer=self.window.getLayerForKey(self.layerkey)
		if not layer:
			return

		# save image for history
		self.oldimage=layer.getImageCopy()

		proplock=qtcore.QReadLocker(layer.propertieslock)

		image=qtgui.QImage(layer.image.size(),layer.image.format())
		proplock.unlock()

		image.fill(self.fgcolor.rgb())
		if self.newpath:
			fillpath=self.newpath
			if self.clippath:
				fillpath=fillpath.intersected(self.clippath)
			self.changedarea=fillpath
		else:
			fillpath=self.clippath

		self.changedarea=fillpath.boundingRect().toAlignedRect()
		layer.compositeFromCorner(image,0,0,qtgui.QPainter.CompositionMode_SourceOver,fillpath)

		oldstamp=qtgui.QImage.copy(self.oldimage,self.changedarea)
		# add to history
		command=DrawingCommand(self.layerkey,oldstamp,self.changedarea)
		self.window.addCommandToHistory(command,layer.owner)

		# refresh layer preview
		BeeApp().master.refreshLayerThumb(self.window.id,self.layerkey)

# elipse selection tool
class EllipseSelectionToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"ellipse select")
		self.displayname="Ellipse Selection"

	def setupTool(self,window,layerkey):
		tool=SelectionTool(self,self.options,window)
		return tool
 
class SketchToolDesc(PencilToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"brush")
		self.brushshape=BrushShapes.ellipse
		self.displayname="Brush"
		self.updateBrush()

	# make full sized brush (and list of pre-scaled brushes)
	def makeFullSizedBrush(self):
		# only support one brush shape right now
		if self.brushshape==BrushShapes.ellipse:
			self.fullsizedbrush=self.makeEllipseBrush(self.options["maxdiameter"],self.options["maxdiameter"])

		self.makeScaledBrushes()

		#printMonochromePIL(self.fullsizedbrush)

		self.singlepixelbrush=self.scaledbrushes[-1][0]

	def makeEllipseBrush(self,width,height):
		""" Make an ellipse brush to use, in order to save processing time the image is in gray scale here """

		radius=width/2.
		imgwidth=int(math.ceil(width))
		imgheight=int(math.ceil(height))

		fadepercent=self.options["fade start"]/100.
		#fadepercent=.4

		# use a greyscale image here to reduce number of calculations
		brushimage=Image.new("L",(imgwidth,imgheight),0)

		# create raw access object for faster pixel setting
		pix=brushimage.load()

		for i in range(width):
			for j in range(height):
				v=self.ellipseBrushFadeAt(i,j,radius,width,height,fadepercent)
				if v>0:
					pix[i,j]=(int(round(255*v)))

		return brushimage

	def ellipseBrushFadeAt(self,x,y,radius,imgwidth,imgheight,fadepercent):
		radius += .5

		centerx=math.ceil(imgwidth)/2.
		centery=math.ceil(imgheight)/2.

		distance=math.sqrt(((x+.5-centerx)**2)+((y+.5-centery)**2))

		# if the distance is over .5 past the radius then it's past the bounds of the brush
		if distance>=radius:
			return 0

		# special case for the center pixel
		elif distance==0:
			return 1

		#elif distance <= radius*fadepercent:
		#	return 1

		fade = ((radius-distance)/radius)/fadepercent
		if fade>1:
			fade = 1

		return fade

	# make list of pre-scaled brushes
	def makeScaledBrushes(self):
		self.scaledbrushes=[]

		width,height=self.fullsizedbrush.size
		fullwidth,fullheight=self.fullsizedbrush.size

		while True:
			if width >= fullwidth and height >= fullheight:
				scaledImage=scaleImage(self.fullsizedbrush,width,height)
			# scale down using previous one once below 1:1
			else:
				scaledImage=scaleImage(scaledImage,width,height)

			xscale = float(width) / fullwidth
			yscale = float(height) / fullheight
			scale=xscale

			self.scaledbrushes.append((scaledImage,xscale,yscale))

			# break after we get to a single pixel brush, single pixel brushes don't scale up right so don't bother making one
			if width<=3 and height<=3:
				break

			# never scale by less than 1/2
			width = int ((width + 1) / 2)
			height = int((height + 1) / 2)

			# don't scale to even numbered sizes, scale to next highest odd number
			if width%2==0:
				width+=1
			if height%2==0:
				height+=1

	def pressToolButton(self):
		BeeApp().master.toolselectwindow.ui.brush_button.setChecked(True)
 
	def setDefaultOptions(self):
		PencilToolDesc.setDefaultOptions(self)
		self.options["maxdiameter"]=7
		self.options["mindiameter"]=0
		self.options["step"]=1
		self.options["blur"]=50
		self.options["pressurebalance"]=100
		self.options["fade start"]=50
		self.options["opacity"]=100
		self.options["pressuresize"]=1
		self.options["pressureopacity"]=0

	def updateBrush(self):
		self.makeFullSizedBrush()

		brushpreview=Image.new("RGBA",self.fullsizedbrush.size,(0,0,0,0))
		brushpreview.paste((0,0,0),box=(0,0),mask=self.fullsizedbrush)
		self.brushpreview = PilToQImage(brushpreview)

		widget = self.getOptionsWidget()
		if widget:
			widget.ui.brushpreviewwidget.updateBrush(self.brushpreview,self.options.get("opacity",100)/100.)

	def setupTool(self,window,layerkey):
		tool=SketchTool(self.options,window)
		tool.fullsizedbrush = self.fullsizedbrush
		tool.scaledbrushes = self.scaledbrushes
		tool.singlepixelbrush = self.singlepixelbrush
		tool.name=self.name

		# copy the foreground color
		tool.fgcolor=qtgui.QColor(window.master.fgcolor)
		tool.layerkey=layerkey
 
		# if there is a selection get a copy of it
		tool.clippath=window.getClipPathCopy()
 
		return tool
 
	def getOptionsWidget(self,parent=None):
		if not self.optionswidget:
			self.optionswidget=BrushOptionsWidget(parent,self)
			self.optionswidget.updateDisplayFromOptions()
		return self.optionswidget

class BrushOptionsWidget(qtgui.QWidget):
	def __init__(self,parent,tooldesc):
		qtgui.QWidget.__init__(self,parent)
		self.tooldesc=tooldesc

		# setup user interface
		self.ui=Ui_BrushOptionsWidget()
		self.ui.setupUi(self)

		self.ui.brushpreviewwidget = BrushPreviewWidget(self.ui.brushpreviewwidget,brushimage=tooldesc.brushpreview,opacity=1)

	def updateDisplayFromOptions(self):
		self.ui.brushdiameter.setValue(self.tooldesc.options["maxdiameter"])
		self.ui.brushmindiameter.setValue(self.tooldesc.options["mindiameter"])
		self.ui.stepsize.setValue(self.tooldesc.options["step"])
		self.ui.opacity_slider.setValue(self.tooldesc.options["opacity"])
		self.ui.fadestartslider.setValue(self.tooldesc.options["fade start"])

		if self.tooldesc.options["pressuresize"]:
			self.ui.pressure_size_box.setChecked(True)
		else:
			self.ui.pressure_size_box.setChecked(False)

		if self.tooldesc.options["pressureopacity"]:
			self.ui.pressure_opacity_box.setChecked(True)
		else:
			self.ui.pressure_opacity_box.setChecked(False)

	def on_brushdiameter_valueChanged(self,value):
		self.tooldesc.options["maxdiameter"]=value
		self.tooldesc.updateBrush()

	def on_brushmindiameter_valueChanged(self,value):
		self.tooldesc.options["mindiameter"]=value

	def on_stepsize_valueChanged(self,value):
		self.tooldesc.options["step"]=value

	def on_fadestartslider_valueChanged(self,value):
		self.tooldesc.options["fade start"]=value
		self.tooldesc.updateBrush()

	def on_opacity_slider_valueChanged(self,value):
		self.tooldesc.options["opacity"]=value
		self.tooldesc.updateBrush()

	def on_pressure_size_box_stateChanged(self,value):
		if value:
			self.tooldesc.options["pressuresize"]=1
		else:
			self.tooldesc.options["pressuresize"]=0

	def on_pressure_opacity_box_stateChanged(self,value):
		if value:
			self.tooldesc.options["pressureopacity"]=1
		else:
			self.tooldesc.options["pressureopacity"]=0

class SketchTool(DrawingTool):
	def __init__(self,options,window):
		DrawingTool.__init__(self,options,window)
		self.lastpressure=-1
		self.compmode=qtgui.QPainter.CompositionMode_SourceOver
		self.scaledbrushes=[]
		self.brushshape=BrushShapes.ellipse
		self.brushimageformat=BrushImageFormats.pil
		self.fgcolor=qtgui.QColor(window.master.fgcolor)
		self.colortuple=(self.fgcolor.red(),self.fgcolor.green(),self.fgcolor.blue())

	def movedFarEnough(self,x,y):
		if distance2d(self.lastpoint[0],self.lastpoint[1],x,y) < self.options["step"]:
			return False
		return True

	def updateBrushForPressure(self,pressure,pixelx=0,pixely=0):
		self.updateBrushSizeAndShiftForPressure(pressure,pixelx%1,pixely%1)

		if self.options["pressureopacity"]:
			self.updateBrushOpacityForPressure(pressure)

	def updateBrushOpacityForPressure(self,pressure):
		fade=int(math.ceil(pressure * 255.))
		fadeimage=Image.new("RGBA",self.brushimage.size,(255,255,255,fade))

		self.brushimage=ImageChops.multiply(self.brushimage,fadeimage)

	def updateBrushSizeAndShiftForPressure(self,pressure,subpixelx=0,subpixely=0):
		self.lastpressure=pressure
		#print "updating brush for pressure/subpixels:", pressure, subpixelx, subpixely
		scale=self.scaleForPressure(pressure)
		#print "brush scale:", scale

		# adjust size for pressure
		if self.options["pressuresize"] and scale<1:
			fullwidth,fullheight=self.fullsizedbrush.size
			targetwidth=int(math.ceil(fullwidth*scale))+1
			targetheight=int(math.ceil(fullheight*scale))+1

			# if the target size is an even number then make it odd
			if targetwidth%2==0:
				targetwidth+=1
			if targetheight%2==0:
				targetheight+=1

			# try to find exact or closest brushes to scale
			scaledbrush = self.findScaledBrush(scale)

			# we're either exact on for scale or less than double what we need
			if scaledbrush:
				# scale down the image above
				scaledaboveimage=self.scaleShiftImage(scaledbrush,scale,subpixelx-.5,subpixely-.5,targetwidth,targetheight)

				outputimage=scaledaboveimage

			# if the scale is so small it should be at one pixel
			else:
				#s = scale * self.fullsizedbrush.size[0]
				outputimage = self.scaleSmallBrush(scale, subpixelx-.5, subpixely-.5)

		# else just shift the image
		else:
			fullwidth,fullheight=self.fullsizedbrush.size
			targetwidth=fullwidth+1
			targetheight=fullheight+1

			# if ithe target size is an even number then make it odd
			if targetwidth%2==0:
				targetwidth+=1
			if targetheight%2==0:
				targetheight+=1

			brush=(self.fullsizedbrush,1)
			outputimage=self.scaleShiftImage(brush,1,subpixelx-.5,subpixely-.5,targetwidth,targetheight)

		self.brushimage=Image.new("RGBA",outputimage.size,(self.colortuple[0],self.colortuple[1],self.colortuple[2],0))

		self.brushimage.paste(self.colortuple,box=(0,0),mask=outputimage)

	# do special case calculations for brush of size smaller than full 3x3
	def scaleSmallBrush(self,scale,subpixelx,subpixely):
		fullwidth,fullheight=self.fullsizedbrush.size
		radius=fullwidth*scale/2.

		if radius>1.5:
			print "WARNING: small brush called on brush with radius:", radius
			radius=1.5

		#print "radius:", radius

		brushwidth=3
		brushheight=3

		brushimage=Image.new("L",(brushwidth,brushheight),0)
		pix=brushimage.load()

		for i in range(brushwidth):
			for j in range(brushheight):
				curfade=radius*2
				if curfade>1:
					curfade=0
				pix[i,j]=(int(round(curfade*255)))

		return scaleShiftPIL(brushimage,subpixelx,subpixely,5,5,1,1)

	# do special case calculations for brush of single pixel size
	def scaleSinglePixelImage(self,scale,pixel,subpixelx,subpixely):
		outputimage=scaleShiftPIL(pixel,subpixelx,subpixely,2,2,scale,scale)

		#print "Scaled single pixel brush:"
		#printPILImage(outputimage)

		return outputimage

	# return single brush that matches scale passed or two brushes that are nearest to that scale
	def findScaledBrush(self,scale):
		current=None
		for i in range(len(self.scaledbrushes)):
			current=self.scaledbrushes[i]
			# if we get an exact match or the next step above return it
			if current[1] <= scale:
				return self.scaledbrushes[i-1]
		# if we get to the end return none, meaning that 
		return None

	# use subpixel adjustments to shift image and scale it too if needed
	def scaleShiftImage(self,srcbrush,targetscale,subpixelx,subpixely,targetwidth,targetheight):
		scale=targetscale/srcbrush[1]
		#print "going from scale:", srcbrush[1], "to scale", targetscale
		#print "calculated conversion:", scale
		return scaleShiftPIL(srcbrush[0],subpixelx,subpixely,targetwidth,targetheight,scale,scale)

	def getFullSizedBrushWidth(self):
		return self.fullsizedbrush.size[0]

class MoveSelectionToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"move selection")
		self.displayname="Move Selection"

	def pressToolButton(self):
		BeeApp().master.toolselectwindow.ui.move_selection_button.setChecked(True)

	def setupTool(self,window,layerkey):
		if not layerkey:
			layerkey=window.getCurLayerKey()
		tool=MoveSelectionTool(self.options,window)
		tool.name=self.name
		tool.layerkey=layerkey
		return tool

# selection move tool
class MoveSelectionTool(AbstractTool):
	logtype=ToolLogTypes.unlogable
	allowedonfloating=True
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)
		self.pendown=False

	# figure out if pen is over selection or not, if it is over selection then do a move, if not do an anchor if current layer is a floating selection
	# command does not change any layers or even go through the drawing thread until the cursor is let up, at that point it puts an event through the drawing thread that moves it all at once
	def guiLevelPenDown(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		self.layer=self.window.getLayerForKey(self.layerkey)
		if self.layer:
			if self.layer.type==LayerTypes.floating:
				self.initializeLayerMove(x,y)
			else:
				for item in self.window.scene.items(qtcore.QPointF(x,y)):
					if item.type==LayerTypes.floating:
						self.layer=item
						self.initializeLayerMove(x,y)
						break

	def initializeLayerMove(self,x,y):
		self.pendown=True
		self.lastx=int(x)
		self.lasty=int(y)

		self.startpos=self.layer.pos()
		self.endpos=self.layer.pos()

	def moveLayer(self,x,y,modkeys):
		x=int(x)
		y=int(y)
		if x==self.lastx and y==self.lasty:
			return

		oldrect=qtcore.QRectF(self.layer.boundingRect())
		oldrect.moveTo(self.layer.pos())
		newrect=oldrect.translated(x-self.lastx,y-self.lasty)


		# determine if move would move selection completely off the layer
		overlap=newrect.intersected(self.layer.scene().sceneRect())
		if overlap.isNull():
			boundingrect=self.layer.scene().sceneRect().adjusted(1-self.layer.boundingRect().width(),1-self.layer.boundingRect().height(),self.layer.boundingRect().width()-1,self.layer.boundingRect().height()-1)
			newloc=snapRectToRect(boundingrect,newrect.toAlignedRect())
			newx=newloc.x()
			newy=newloc.y()
			self.layer.setPos(float(newx),float(newy))

		else:
			self.layer.moveBy(x-self.lastx,y-self.lasty)

		# update whole scene because for some reason I can't figure out how to just update the needed areas
		self.layer.scene().update()

		self.lastx=x
		self.lasty=y

		self.endpos=self.layer.pos()

	def guiLevelPenMotion(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		if self.pendown:
			self.moveLayer(x,y,modkeys)

	def penUp(self,x=None,y=None):
		if self.pendown:
			# make sure there was an actual net change
			if self.startpos.x()!=self.endpos.x() or self.startpos.y()!=self.endpos.y():
				command=MoveFloatingCommand(self.startpos.x(),self.startpos.y(),self.endpos.x(),self.endpos.y(),self.layer.key)
				self.window.addCommandToHistory(command,-1)

		self.pendown=False
		self.layer=None

class SmudgeToolDesc(SketchToolDesc):
	def __init__(self):
		SketchToolDesc.__init__(self)
		self.displayname="Smudge"
		self.name="smudge"
 
	def getCursor(self):
		return qtcore.Qt.CrossCursor
 
	def getDownCursor(self):
		return getBlankCursor()
 
	def setDefaultOptions(self):
		self.options["step"]=1
		self.options["pressure pickup"]=1
		self.options["maxdiameter"]=8
		self.options["mindiameter"]=0
		self.options["cleanstart"]=1
		self.options["fade start"]=50
		self.options["pickup rate"]=25
		self.options["dirty start"]=0

	def pressToolButton(self):
		BeeApp().master.toolselectwindow.ui.smudge_button.setChecked(True)
 
	def setupTool(self,window,layerkey):
		tool=SmudgeTool(self.options,window,self.fullcolorbrush)
		tool.name=self.name
		tool.smudgerate = self.options["pickup rate"]/100.
		tool.layerkey=layerkey
		tool.fgcolor=qtgui.QColor(window.master.fgcolor)
 
		# if there is a selection get a copy of it
		tool.clippath=window.getClipPathCopy()
 
		return tool
 
	def getOptionsWidget(self,parent=None):
		if not self.optionswidget:
			self.optionswidget=SmudgeToolOptionsWidget(parent,self)
			self.optionswidget.updateDisplayFromOptions()
		return self.optionswidget

	# make full sized brush shape
	def makeFullSizedBrush(self):
		self.fullsizedbrush=self.makeEllipseBrush(self.options["maxdiameter"],self.options["maxdiameter"])
		fullsizedbrush = self.fullsizedbrush.convert("RGBA")
		fullsizedbrush.putalpha(self.fullsizedbrush)
		self.fullcolorbrush = PilToQImage(fullsizedbrush)

	def updateBrush(self):
		SketchToolDesc.updateBrush(self)

class SmudgeToolOptionsWidget(qtgui.QWidget):
	def __init__(self,parent,tooldesc):
		qtgui.QWidget.__init__(self,parent)
		self.tooldesc=tooldesc

		# setup user interface
		self.ui=Ui_SmudgeOptionsWidget()
		self.ui.setupUi(self)

		self.ui.brushpreviewwidget = BrushPreviewWidget(self.ui.brushpreviewwidget,brushimage=tooldesc.brushpreview,opacity=1)

	def updateDisplayFromOptions(self):
		self.ui.pickupslider.setValue(self.tooldesc.options["pickup rate"])
		self.ui.stepsize.setValue(self.tooldesc.options["step"])
		self.ui.brushsizeslider.setValue(self.tooldesc.options["maxdiameter"])

		if self.tooldesc.options["pressure pickup"]:
			self.ui.pressure_pickup_box.setChecked(True)
		else:
			self.ui.pressure_pickup_box.setChecked(False)

		if self.tooldesc.options["dirty start"]:
			self.ui.dirty_start_box.setChecked(True)
		else:
			self.ui.dirty_start_box.setChecked(False)

	def on_pickupslider_valueChanged(self,value):
		self.tooldesc.options["pickup rate"]=value

	def on_brushsizeslider_valueChanged(self,value):
		self.tooldesc.options["maxdiameter"]=value
		self.tooldesc.updateBrush()

	def on_stepsize_valueChanged(self,value):
		self.tooldesc.options["step"]=value

	def on_pressure_pickup_box_toggled(self,bool=None):
		if bool:
			self.tooldesc.options["pressure pickup"]=1
		else:
			self.tooldesc.options["pressure pickup"]=0

	def on_dirty_start_box_toggled(self,bool=None):
		if bool:
			self.tooldesc.options["dirty start"]=1
		else:
			self.tooldesc.options["dirty start"]=0

class SmudgeTool(SketchTool):
	def __init__(self,options,window,fullsizedbrush):
		SketchTool.__init__(self,options,window)
		self.name="smudge"
		self.brushimageformat=BrushImageFormats.qt
		self.brushwidth = fullsizedbrush.width()
		self.brushheight = fullsizedbrush.height()
		self.fullsizedbrush = fullsizedbrush
		self.xradius=self.brushwidth/2
		self.yradius=self.brushheight/2

		self.brushimage = qtgui.QImage(self.brushwidth,self.brushheight,qtgui.QImage.Format_ARGB32_Premultiplied)
		self.brusharr = qimage2ndarray.byte_view(self.brushimage)

		self.logtype=ToolLogTypes.regular
		self.dirtarr=None

	def startLine(self,x,y,pressure):
		if self.options["dirty start"] and not self.dirtarr:
			# start with brush looking like the foreground color
			# when going off and back on the canvas the brush will retain previous color
			dirt = qtgui.QImage(self.brushwidth,self.brushheight,qtgui.QImage.Format_ARGB32_Premultiplied)
			dirt.fill(self.fgcolor.rgb())
		else:
			# start with the brush looking like what is immediately under it
			brushrect = qtcore.QRect(x-self.xradius,y-self.yradius,self.brushwidth,self.brushheight)
			dirt = self.layer.getImageCopy(subregion=brushrect)

		self.dirtarr = numpy.array(qimage2ndarray.byte_view(dirt),dtype=numpy.float32)

		if self.pointshistory:
			self.prevpointshistory.append(self.pointshistory)

		self.pointshistory=[(x,y,pressure)]
		self.lastpoint=(x,y)

	def penDown(self,x,y,pressure):
		self.layer=self.window.getLayerForKey(self.layerkey)
		self.oldlayerimage = self.layer.getImageCopy()
		SketchTool.penDown(self,x,y,pressure)

	def guiLevelPenDown(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		pass

	def updateBrushWithDirt(self,pressure,dirtypickup):
		if self.options["pressure pickup"]:
			currentpickup = self.smudgerate * pressure
		else:
			currentpickup = self.smudgerate

		pickuparr = qimage2ndarray.byte_view(dirtypickup)

		self.brusharr[:]=(((self.dirtarr*currentpickup) + (pickuparr * (1-currentpickup))).round())[:]

		self.dirtarr = (self.dirtarr * (1-currentpickup)) + (pickuparr * currentpickup)

		# make brush a circular shape with a blurred edge
		painter = qtgui.QPainter()
		painter.begin(self.brushimage)
		painter.setCompositionMode(qtgui.QPainter.CompositionMode_DestinationIn)
		painter.drawImage(qtcore.QPoint(0,0),self.fullsizedbrush)
		painter.end()

		#print "fullsized brush:"
		#printImage(self.fullsizedbrush)

		#print "brush now looks like:"
		#printImage(self.brushimage)

	def cleanupTmpLayer(self):
		pass

	def getOwner(self):
		return self.layer.owner

	def continueLine(self,x,y,pressure):
		# if it hasn't moved just do nothing
		if not self.movedFarEnough(x,y):
			return

		x=int(x)
		y=int(y)

		#print "starting new line"
		self.pointshistory.append((x,y,pressure))
 
		# get size of layer
		layerwidth=self.window.docwidth
		layerheight=self.window.docheight
 
		# get points inbetween according to step option and layer size
		path=getPointsPath(self.lastpoint[0],self.lastpoint[1],x,y,self.options['step'],layerwidth,layerheight,self.lastpressure,pressure)

		# if no points are on the layer just return
		if len(path)==0:
			return

		# figure out the maximum radius the brush will have
		maxradius=int(math.ceil(self.getFullSizedBrushWidth()/2.0))

		#print "maxradius:", maxradius
		#print "path:", path

		# calculate the bounding rect for this operation
		left=int(math.floor(min(path[0][0],path[-1][0])-maxradius)-1)
		top=int(math.floor(min(path[0][1],path[-1][1])-maxradius)-1)
		right=int(math.ceil(max(path[0][0],path[-1][0])+maxradius)+1)
		bottom=int(math.ceil(max(path[0][1],path[-1][1])+maxradius)+1)

		left=max(0,left)
		top=max(0,top)
		right=min(layerwidth,right)
		bottom=min(layerheight,bottom)

		# calulate area needed to hold everything
		width=right-left
		height=bottom-top

		for point in path:

			stampx = point[0]-self.xradius
			stampy = point[1]-self.yradius

			brushrect = qtcore.QRect(stampx,stampy,self.brushwidth,self.brushheight)
			dirtypickup = self.layer.getImageCopy(subregion=brushrect)

			self.updateBrushWithDirt(pressure,dirtypickup)

			#print "final brush image"
			#printImage(self.brushimage)

			self.addImageToLayer(self.fullsizedbrush,stampx,stampy,refresh=False,stampmode=qtgui.QPainter.CompositionMode_DestinationOut)
			self.addImageToLayer(self.brushimage,stampx,stampy,refresh=False,stampmode=qtgui.QPainter.CompositionMode_Plus)

		refresharea=qtcore.QRectF(left,top,width,height)
		self.layer.updateScene(refresharea)

		self.lastpoint=(path[-1][0],path[-1][1])

	def movedFarEnough(self,x,y):
		return DrawingTool.movedFarEnough(self,x,y)

	def getFullSizedBrushWidth(self):
		return self.brushwidth

class BlurToolDesc(SketchToolDesc):
	def __init__(self):
		SketchToolDesc.__init__(self)
		self.displayname="Blur"
		self.name="blur"
 
	def getCursor(self):
		return qtcore.Qt.CrossCursor
 
	def getDownCursor(self):
		return getBlankCursor()
 
	def setDefaultOptions(self):
		self.options["step"]=1
		self.options["pressuresize"]=1
		self.options["pressureblur"]=1
		self.options["pressureopacity"]=0
		self.options["maxdiameter"]=9
		self.options["mindiameter"]=0
		self.options["fade start"]=50
		self.options["opacity"]=100
		self.options["maxblur"]=10

	def pressToolButton(self):
		BeeApp().master.toolselectwindow.ui.blur_button.setChecked(True)
 
	def setupTool(self,window,layerkey):
		tool=BlurTool(self.options,window,PilToQImage(self.fullsizedbrush))
		tool.name=self.name

		brushimage=Image.new("RGBA",self.fullsizedbrush.size,(0,0,0,0))
		brushimage.paste((0,0,0),box=(0,0),mask=self.fullsizedbrush)

		tool.fullsizedbrush = brushimage
		tool.scaledbrushes = self.scaledbrushes

		tool.layerkey=layerkey
 
		# if there is a selection get a copy of it
		tool.clippath=window.getClipPathCopy()
 
		return tool

	def getOptionsWidget(self,parent=None):
		if not self.optionswidget:
			self.optionswidget=BlurToolOptionsWidget(parent,self)
			self.optionswidget.updateDisplayFromOptions()
		return self.optionswidget

class BlurToolOptionsWidget(qtgui.QWidget):
	def __init__(self,parent,tooldesc):
		qtgui.QWidget.__init__(self,parent)
		self.tooldesc=tooldesc

		# setup user interface
		self.ui=Ui_BlurOptionsWidget()
		self.ui.setupUi(self)

		self.ui.brushpreviewwidget = BrushPreviewWidget(self.ui.brushpreviewwidget,brushimage=tooldesc.brushpreview,opacity=1)

	def updateDisplayFromOptions(self):
		self.ui.brushdiameter.setValue(self.tooldesc.options["maxdiameter"])
		self.ui.stepsize.setValue(self.tooldesc.options["step"])
		self.ui.blurslider.setValue(self.tooldesc.options["maxblur"])

		if self.tooldesc.options["pressuresize"]==1:
			self.ui.pressure_size_box.setChecked(True)
		else:
			self.ui.pressure_size_box.setChecked(False)

		if self.tooldesc.options["pressureblur"]==1:
			self.ui.pressure_blur_box.setChecked(True)
		else:
			self.ui.pressure_blur_box.setChecked(False)
			

	def on_brushdiameter_valueChanged(self,value):
		self.tooldesc.options["maxdiameter"]=value
		self.tooldesc.updateBrush()

	def on_stepsize_valueChanged(self,value):
		self.tooldesc.options["step"]=value

	def on_blurslider_valueChanged(self,value):
		self.tooldesc.options["maxblur"]=value

	def on_pressure_size_box_stateChanged(self,value):
		if value:
			self.tooldesc.options["pressuresize"]=1
		else:
			self.tooldesc.options["pressuresize"]=0

	def on_pressure_blur_box_stateChanged(self,value):
		if value:
			self.tooldesc.options["pressureblur"]=1
		else:
			self.tooldesc.options["pressureblur"]=0
 
class BlurTool(SketchTool):
	def __init__(self,options,window,fullsizedbrush):
		SketchTool.__init__(self,options,window)
		self.brushshape=BrushShapes.ellipse
		self.brushwidth = fullsizedbrush.width()
		self.brushheight = fullsizedbrush.height()
		self.fullsizedbrush = fullsizedbrush
		self.brushimage = fullsizedbrush
		self.xradius=self.brushwidth/2
		self.yradius=self.brushheight/2
		self.brushimageformat=BrushImageFormats.qt
		self.logtype=ToolLogTypes.regular

	def movedFarEnough(self,x,y):
		return DrawingTool.movedFarEnough(self,x,y)

	def startLine(self,x,y,pressure):
		x=int(x)
		y=int(y)

		self.layer=self.window.getLayerForKey(self.layerkey)

		self.oldlayerimage = self.layer.getImageCopy()

		self.updateBrushForPressure(pressure)

		self.filterAtPoint(x,y,pressure)

		if self.pointshistory:
			self.prevpointshistory.append(self.pointshistory)

		self.pointshistory=[(x,y,pressure)]
		self.lastpoint=(x,y)

		refresharea=qtcore.QRectF(x-self.xradius,y-self.yradius,self.brushwidth,self.brushheight)
		self.layer.updateScene(refresharea)

		self.lastpressure=pressure

	def updateBrushForPressure(self,pressure):
		SketchTool.updateBrushForPressure(self,pressure)
		self.brushimage=PilToQImage(self.brushimage)

	def continueLine(self,x,y,pressure):
		x=int(x)
		y=int(y)
		# if it hasn't moved just do nothing
		if not self.movedFarEnough(x,y):
			return

		self.pointshistory.append((x,y,pressure))
 
		# get size of layer
		layerwidth=self.window.docwidth
		layerheight=self.window.docheight
 
		# get points inbetween according to step option and layer size
		path=getPointsPath(self.lastpoint[0],self.lastpoint[1],x,y,self.options['step'],layerwidth,layerheight,self.lastpressure,pressure)

		self.lastpressure=pressure

		# if no points are on the layer just return
		if len(path)==0:
			return

		maxradius=int(math.ceil(self.getFullSizedBrushWidth()/2.0))

		#print "maxradius:", maxradius
		#print "path:", path

		# calculate the bounding rect for this operation
		left=int(math.floor(min(path[0][0],path[-1][0])-maxradius)-1)
		top=int(math.floor(min(path[0][1],path[-1][1])-maxradius)-1)
		right=int(math.ceil(max(path[0][0],path[-1][0])+maxradius)+1)
		bottom=int(math.ceil(max(path[0][1],path[-1][1])+maxradius)+1)

		left=max(0,left)
		top=max(0,top)
		right=min(layerwidth,right)
		bottom=min(layerheight,bottom)

		# calulate area needed to hold everything
		width=right-left
		height=bottom-top
 
		for point in path:
			self.updateBrushForPressure(point[2])
			self.filterAtPoint(point[0],point[1],point[2])

		refresharea=qtcore.QRectF(left,top,width,height)
		self.layer.updateScene(refresharea)
 
		self.lastpoint=(path[-1][0],path[-1][1])

	def cleanupTmpLayer(self):
		pass

	def filterAtPoint(self,x,y,pressure):
		x=int(x)
		y=int(y)

		if pressure <= 0:
			return

		stddev = (self.options["maxblur"]+9)/50.
		if self.options["pressureblur"]:
			stddev = pressure * stddev

		curbrushwidth = self.brushimage.width()
		curbrushheight = self.brushimage.height()

		stampx = x-(curbrushwidth/2)
		stampy = y-(curbrushheight/2)

		im = self.layer.getImageCopy(subregion=qtcore.QRect(stampx,stampy,curbrushwidth,curbrushheight))

		imarr = qimage2ndarray.byte_view(im)

		brushimage = qtgui.QImage(curbrushwidth,curbrushheight,qtgui.QImage.Format_ARGB32_Premultiplied)

		brusharr = qimage2ndarray.byte_view(brushimage)

		gaussian_filter(imarr,(stddev,stddev,0),output=brusharr,mode='nearest')

		# make brush a circular shape with a faded edge
		painter = qtgui.QPainter()
		painter.begin(brushimage)
		painter.setCompositionMode(qtgui.QPainter.CompositionMode_DestinationIn)
		painter.drawImage(qtcore.QPoint(0,0),self.brushimage)
		painter.end()

		self.addImageToLayer(self.brushimage,stampx,stampy,refresh=False,stampmode=qtgui.QPainter.CompositionMode_DestinationOut)
		self.addImageToLayer(brushimage,stampx,stampy,refresh=False,stampmode=qtgui.QPainter.CompositionMode_Plus)

	def getFullSizedBrushWidth(self):
		return self.brushwidth

	def getOwner(self):
		return self.layer.owner

class SmearToolDesc(SketchToolDesc):
	def __init__(self):
		SketchToolDesc.__init__(self)
		self.displayname="Smear"
		self.name="smear"
		self.brushshape=BrushShapes.ellipse
 
	def getCursor(self):
		return qtcore.Qt.CrossCursor
 
	def getDownCursor(self):
		return getBlankCursor()
 
	def setDefaultOptions(self):
		self.options["step"]=1
		self.options["maxdiameter"]=12
		self.options["mindiameter"]=12
		self.options["fade start"]=50

	def pressToolButton(self):
		BeeApp().master.toolselectwindow.ui.smear_button.setChecked(True)
 
	def setupTool(self,window,layerkey):
		tool=SmearTool(self.options,window,self.fullsizedbrush)
		tool.name=self.name
		tool.layerkey = layerkey
		tool.layer=window.getLayerForKey(layerkey)

		# if there is a selection get a copy of it
		tool.clippath=window.getClipPathCopy()
 
		return tool

	def makeFullSizedBrush(self):
		# only support one brush shape right now
		if self.brushshape==BrushShapes.ellipse:
			self.fullsizedbrush=self.makeEllipseBrush(self.options["maxdiameter"],self.options["maxdiameter"])
 
	def getOptionsWidget(self,parent=None):
		if not self.optionswidget:
			self.optionswidget=DrawingToolOptionsWidget(parent,self)
			self.optionswidget.updateDisplayFromOptions()
		return self.optionswidget

class SmearTool(SketchTool):
	def __init__(self,options,window,fullsizedbrush):
		SketchTool.__init__(self,options,window)
		self.brushimageformat=BrushImageFormats.qt
		self.fullsizedbrush = PilToQImage(fullsizedbrush)
		self.brushwidth = self.fullsizedbrush.width()
		self.brushheight = self.fullsizedbrush.height()

	def guiLevelPenDown(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		pass

	def penDown(self,x,y,pressure):
		SketchTool.penDown(self,x,y,pressure)

	def startLine(self,x,y,pressure):
		if self.pointshistory:
			self.prevpointshistory.append(self.pointshistory)

		self.oldlayerimage=self.layer.getImageCopy()

		self.pointshistory=[(x,y,pressure)]
		self.lastpoint=(x,y)
		self.captureBrushImage(int(x),int(y),pressure)

	def captureBrushImage(self,x,y,pressure):
		rect = qtcore.QRect(x-(self.brushwidth/2),y-(self.brushheight/2),self.brushwidth,self.brushheight)
		brushimage = self.layer.getImageCopy(subregion=rect)

		painter = qtgui.QPainter()
		painter.begin(brushimage)
		painter.setCompositionMode(qtgui.QPainter.CompositionMode_DestinationIn)
		painter.drawImage(qtcore.QPoint(0,0),self.fullsizedbrush)
		painter.end()

		#print "brush image before scale:"
		#printImage(brushimage)
		self.brushimage = PilToQImage(ScaleClosestPil(QImageToPil(brushimage),.8,.8))
		#print "brush image after scale:"
		#printImage(self.brushimage)

	def updateBrushForPressure(self,pressure,x,y):
		self.captureBrushImage(int(x),int(y),pressure)

	def getFullSizedBrushWidth(self):
		return self.brushwidth

	def movedFarEnough(self,x,y):
		return DrawingTool.movedFarEnough(self,x,y)

	def cleanupTmpLayer(self):
		pass

	def getOwner(self):
		return self.layer.owner
