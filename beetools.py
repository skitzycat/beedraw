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
 
import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore
import math
from beeutil import *
from beetypes import *
from beeeventstack import *
from ImageQt import ImageQt
 
from PencilOptionsWidgetUi import *
from BrushOptionsWidgetUi import *
from EraserOptionsWidgetUi import *
from PaintBucketOptionsWidgetUi import *
from FeatherSelectOptionsWidgetUi import *

from beeapp import BeeApp
 
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
		print "Error, toolbox couldn't find tool with name:", name
		return None

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
 
	def getOptionsWidget(self,parent):
		return qtgui.QWidget(parent)

	def newModKeys(self,modkeys):
		pass
 
	# setup needed parts of tool using knowledge of current window
	# this should be implemented in subclass if needed
	def setupTool(self,window,layerkey):
		self.layerkey=layerkey
		return self.getTool(window)
 
	def getTool(self,window):
		return None

	# what to do when this tool is no longer active
	def deactivate(self):
		pass
 
# base class for all drawing tools
class AbstractTool:
	logtype=ToolLogTypes.unlogable
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
	def penDown(self,x,y,pressure=None):
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

	def getTool(self,window):
		tool=EyeDropperTool(self.options,window)
		tool.name=self.name
		return tool

	def pressToolButton(self):
		BeeApp().master.ui.eye_dropper_button.setChecked(True)
 
	def setupTool(self,window,layerkey):
		self.layerkey=layerkey
		return self.getTool(window)

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
		self.layer=None
		self.pendown=False

		self.inside=True
		self.returning=False

		self.returnpoint=None
		self.logtype=ToolLogTypes.regular

	def guiLevelPenDown(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		if modkeys==qtcore.Qt.ControlModifier:
			color=self.window.getImagePixelColor(x,y)
			self.window.master.setFGColor(qtgui.QColor(color))
			self.logtype=ToolLogTypes.unlogable

	def calculateCloseEdgePoint(self,p1,p2):
		""" Stub for now, eventually I'd like this algorithm to take over if the other one gets confused by drawing parrellel to the edge right before leaving. """
		return None

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

		exitpoint=None

		#print "last two points:", p1,p2

		dx=float(p2[0])-float(p1[0])
		dy=float(p2[1])-float(p1[1])

		# shouldn't ever get this as input, but just in case
		if dx==0 and dy==0:
			return None

		# special case for going parallel to an axis
		if dx==0:
			if dy<0:
				return(p1[0],topedge)
			else:
				return(p1[0],bottomedge)
		if dy==0:
			if dx<0:
				return(leftedge,p1[1])
			else:
				return(rightedge,p1[1])

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
		#print "distance between last two points:", pointdistance
		#print "distance between last point and edge:", edgedistance
		if edgedistance>2*pointdistance:
			#print "going to backup case"
			return self.calculateCloseEdgePoint(p1,p2)
		return exitpoint

	def calculateEdgePressure(self,p1,p2,pexit):
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
		if self.logtype==ToolLogTypes.unlogable:
			return
		#print "Got penEnter"
		if self.pendown:
			self.returning=True
			self.inside=True

	def getColorRGBA(self):
		return self.fgcolor.rgba()
 
	def makeFullSizedBrush(self):
		fgr=self.fgcolor.red()
		fgg=self.fgcolor.green()
		fgb=self.fgcolor.blue()

		opacity=int(self.options["opacity"]*255./100.)

		colortuple=(fgr,fgg,fgb,opacity)

		self.diameter=self.options["maxdiameter"]
		width=self.diameter
		height=self.diameter

		radius=width/2.
		imgwidth=int(math.ceil(width))
		imgheight=int(math.ceil(height))

		# use a greyscale image here to reduce number of calculations
		self.fullsizedbrush=Image.new("RGBA",(imgwidth,imgheight),(0,0,0,0))

		# create raw access object for faster pixel setting
		pix=self.fullsizedbrush.load()

		for i in range(width):
			for j in range(height):
				distance=math.sqrt(((i+.5-radius)**2)+((j+.5-radius)**2))
				if distance <= radius:
					pix[i,j]=colortuple

		self.fullsizedbrush=PILtoQImage(self.fullsizedbrush)

	def updateBrushForPressure(self,pressure,subpixelx=0,subpixely=0):
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
		bdiameter=self.options["maxdiameter"]*pressure
		self.diameter=int(math.ceil(bdiameter))+1

		# make target size an odd number
		if self.diameter%2==0:
			self.diameter+=1

		# calculate offset into target
		targetoffsetx=((self.diameter-bdiameter)/2.)-.5+subpixelx
		targetoffsety=((self.diameter-bdiameter)/2.)-.5+subpixely
 
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
		self.brushimage.setPixel(center,center,self.getColorRGBA())
 
	def penDown(self,x,y,pressure=1):
		if self.logtype==ToolLogTypes.unlogable:
			return

		#print "Got penDown",x,y
		self.returning=False
		self.inside=True
		self.pendown=True

		#print "pen down point:", x, y
		#print "pen pressure:", pressure
		self.layer=self.window.getLayerForKey(self.layerkey)
		self.oldlayerimage=self.layer.getImageCopy()

		self.startLine(x,y,pressure)

	# determine if it's moved far enough that we care
	def movedFarEnough(self,x,y):
		if int(x)==int(self.lastpoint[0]) and int(y)==int(self.lastpoint[1]):
			return False
		return True

	def scaleForPressure(self,pressure):
		return pressure

	def getFullSizedBrushWidth(self):
		return self.fullsizedbrush.width()

	# since windows apparently won't catch return and leave events when the button is pressed down I'm forced to do this
	def checkForPenBounds(self,x,y):
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
		#print "pen motion point,pressure:", x, y, pressure
		# if it hasn't moved just do nothing
		if not self.movedFarEnough(x,y):
			return

		#print "-------------------"
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

		# figure out the maximum pressure we will encounter for this motion
		maxpressure=max(self.lastpressure,pressure)

		# figure out the maximum radius the brush will have
		maxscale=self.scaleForPressure(maxpressure)
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
 
		# then make an image for that bounding rect
		lineimage=qtgui.QImage(width,height,qtgui.QImage.Format_ARGB32_Premultiplied)
		lineimage.fill(0)

		#print "line image size:", width, height

		# put points in that image
		painter=qtgui.QPainter()
		painter.begin(lineimage)
		#painter.setRenderHint(qtgui.QPainter.HighQualityAntialiasing)
 
		for point in path:
			self.updateBrushForPressure(point[2],point[0]%1,point[1]%1)

			xradius=self.brushimage.width()/2
			yradius=self.brushimage.height()/2

			pointx=point[0]
			pointy=point[1]

			#print "point:", pointx, pointy
			#print "brush width:", self.brushimage.width()
			#print "brush radius:", xradius
			#print "left:", left
			#print "top:", top

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

			painter.drawImage(stampx,stampy,self.brushimage)
 
		painter.end()

		#print "stamping line image:"
		#printImage(lineimage)
 
		self.layer.compositeFromCorner(lineimage,left,top,self.compmode,self.clippath)
 
		self.lastpoint=(path[-1][0],path[-1][1])
 
	def startLine(self,x,y,pressure):
		if self.pointshistory:
			self.prevpointshistory.append(self.pointshistory)

		self.pointshistory=[(x,y,pressure)]
		self.lastpoint=(x,y)
		self.makeFullSizedBrush()
		self.updateBrushForPressure(pressure,x%1,y%1)

		targetx=int(x)-int(self.brushimage.width()/2)
		targety=int(y)-int(self.brushimage.height()/2)

		# if this is an even number then do adjustments for the center if needed
		if self.brushimage.width()%2==0:
			#print "this is an even sized brush:"
			if x%1>.5:
				targetx+=1
			if y%1>.5:
				targety+=1

		self.layer.compositeFromCorner(self.brushimage,targetx,targety,self.compmode,self.clippath)

	def penUp(self,x=None,y=None):
		#print "Got penUp"
		self.pendown=False

		if not self.pointshistory:
			return

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
		dirtyrect=qtcore.QRect(left-radius,top-radius,right+(radius*2),bottom+(radius*2))
		
		# bound it by the area of the layer
		dirtyrect=rectIntersectBoundingRect(dirtyrect,self.layer.getImageRect())
 
		# get image of what area looked like before
		oldimage=self.oldlayerimage.copy(dirtyrect)
 
		command=DrawingCommand(self.layerkey,oldimage,dirtyrect)

		self.window.addCommandToHistory(command,self.layer.owner)
 
		BeeApp().master.refreshLayerThumb(self.window.id,self.layerkey)
 
# this is the most basic drawing tool
class PencilToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"pencil")
		self.displayname="Pencil"
 
	def getCursor(self):
		return qtcore.Qt.CrossCursor
 
	def getDownCursor(self):
		return getBlankCursor()
 
	def setDefaultOptions(self):
		self.options["mindiameter"]=0
		self.options["maxdiameter"]=21
		self.options["step"]=1
		self.options["pressuresize"]=1
		self.options["pressurebalance"]=100
		self.options["opacity"]=100
		self.options["stampmode"]=DrawingToolStampMode.darkest

	def pressToolButton(self):
		BeeApp().master.ui.pencil_button.setChecked(True)
 
	def getTool(self,window):
		tool=DrawingTool(self.options,window)
		tool.name=self.name
		return tool
 
	def setupTool(self,window,layerkey):
		tool=self.getTool(window)
		# copy the foreground color
		tool.fgcolor=qtgui.QColor(window.master.fgcolor)
		tool.layerkey=layerkey
 
		# if there is a selection get a copy of it
		tool.clippath=window.getClipPathCopy()
 
		return tool
 
	def getOptionsWidget(self,parent):
		if not self.optionswidget:
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

	def updateDisplayFromOptions(self):
		self.ui.brushdiameter.setValue(self.tooldesc.options["maxdiameter"])
		self.ui.stepsize.setValue(self.tooldesc.options["step"])

	def on_brushdiameter_sliderMoved(self,value):
		self.tooldesc.options["maxdiameter"]=value

	def on_stepsize_sliderMoved(self,value):
		self.tooldesc.options["step"]=value

	def on_opacity_sliderMoved(self,value):
		self.tooldesc.options["opacity"]=value
 
class EraserToolDesc(AbstractToolDesc):
	# describe actual tool
	class Tool(DrawingTool):
		def __init__(self,options,window):
			DrawingTool.__init__(self,options,window)
			self.compmode=qtgui.QPainter.CompositionMode_DestinationOut
 
		def getColorRGBA(self):
			return 0xFFFFFFFF
			#return self.fgcolor.rgba()
 
	# back to description stuff
	def __init__(self):
		AbstractToolDesc.__init__(self,"eraser")
		self.displayname="Eraser"
 
	def pressToolButton(self):
		BeeApp().master.ui.eraser_button.setChecked(True)
 
	def setDefaultOptions(self):
		self.options["maxdiameter"]=21
		self.options["step"]=1
		self.options["pressuresize"]=1
		self.options["pressurebalance"]=100
		self.options["blur"]=100
		self.options["opacity"]=100
 
	def getTool(self,window):
		tool=self.Tool(self.options,window)
		tool.name=self.name
		return tool
 
	def setupTool(self,window,layerkey):
		self.layerkey=layerkey
		tool=self.getTool(window)
		tool.clippath=window.getClipPathCopy()
		tool.layerkey=window.curlayerkey
		# foreground color doesn't matter, but it needs to be there
		tool.fgcolor=qtgui.QColor(0,0,0)
		return tool

	def getOptionsWidget(self,parent):
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

	def updateDisplayFromOptions(self):
		self.ui.eraserdiameter.setValue(self.tooldesc.options["maxdiameter"])
		self.ui.stepsize.setValue(self.tooldesc.options["step"])

	def on_eraserdiameter_sliderMoved(self,value):
		self.tooldesc.options["maxdiameter"]=value

	def on_stepsize_sliderMoved(self,value):
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
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)
 
	def updateOverlay(self,x,y):
		# calculate rectangle defined by the start and current
		left=min(x,self.startpoint[0])
		top=min(y,self.startpoint[1])
		width=max(x,self.startpoint[0])-left
		height=max(y,self.startpoint[1])-top
 
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
 
	def guiLevelPenUp(self,x,y,source=0):
		self.pendown=False
		#x,y=self.window.view.snapPointToView(x,y)
		#x=int(x)
		#y=int(y)
 
		# see how the user wants the selection altered
		modkeys=BeeApp().app.keyboardModifiers()
		selectionmod=getCurSelectionModType()

		if self.overlay:
			newpath=qtgui.QPainterPath()
			newpath.addRect(qtcore.QRectF(self.overlay.rect))
			self.window.changeToolOverlay()
			self.window.changeSelection(selectionmod,newpath)

		self.overlay=None
 
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
	def __init__(self):
		AbstractToolDesc.__init__(self,"rectselect")
		self.displayname="Rectangle Selection"

	def setupTool(self,window,layerkey):
		self.layerkey=layerkey
		tool=self.getTool(window)
		return tool

	def pressToolButton(self):
		BeeApp().master.ui.rectangle_select_button.setChecked(True)
 
	def getTool(self,window):
		tool=SelectionTool(self.options,window)
		tool.name=self.name
		return tool

# fuzzy selection tool description
class FeatherSelectToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"featherselect")
		self.displayname="Feather Selection"

	def pressToolButton(self):
		BeeApp().master.ui.feather_select_button.setChecked(True)

	def setDefaultOptions(self):
		self.options["similarity"]=10
		self.options["currentlayeronly"]=0

	def getTool(self,window):
		tool=FeatherSelectTool(self.options,window)
		tool.name=self.name
		return tool
 
	def setupTool(self,window,layerkey):
		self.layerkey=layerkey
		if not layerkey:
			layerkey=window.getCurLayerKey()
		tool=self.getTool(window)
		tool.layerkey=layerkey
		return tool

	def getOptionsWidget(self,parent):
		if not self.optionswidget:
			self.optionswidget=FeatherSelectOptionsWidget(parent,self)
			self.optionswidget.updateDisplayFromOptions()
		return self.optionswidget

class FeatherSelectOptionsWidget(qtgui.QWidget):
	def __init__(self,parent,tooldesc):
		qtgui.QWidget.__init__(self,parent)
		self.tooldesc=tooldesc

		self.ui=Ui_FeatherSelectOptions()
		self.ui.setupUi(self)

	def updateDisplayFromOptions(self):
		if self.tooldesc.options["currentlayeronly"]==1:
			self.ui.current_layer_check.setCheckState(qtcore.Qt.Checked)
		else:
			self.ui.current_layer_check.setCheckState(qtcore.Qt.Unchecked)
		self.ui.color_threshold_box.setValue(self.tooldesc.options["similarity"])

	def on_color_threshold_box_valueChanged(self,value):
		if type(value)==int:
			self.tooldesc.options["similarity"]=value

	def on_current_layer_check_clicked(self,bool=None):
		if bool!=None:
			self.tooldesc.options["currentlayeronly"]=bool

# fuzzy selection tool
class FeatherSelectTool(AbstractTool):
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)

	def guiLevelPenDown(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		self.selectionmod=getCurSelectionModType()
		if self.options["currentlayeronly"]:
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
			self.window.changeSelection(self.selectionmod,self.newpath)

# paint bucket tool description
class PaintBucketToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"bucket")
		self.displayname="Paint Bucket"

	def pressToolButton(self):
		BeeApp().master.ui.paint_bucket_button.setChecked(True)

	def setDefaultOptions(self):
		self.options["similarity"]=10
		self.options["wholeselection"]=0

	def getTool(self,window):
		tool=PaintBucketTool(self.options,window)
		tool.name=self.name
		return tool
 
	def setupTool(self,window,layerkey):
		if not layerkey:
			layerkey=window.curlayerkey

		tool=self.getTool(window)

		tool.fgcolor=qtgui.QColor(window.master.fgcolor)
		tool.layerkey=layerkey

		# if there is a selection get a copy of it
		tool.clippath=window.getClipPathCopy()

		return tool

	def getOptionsWidget(self,parent):
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
		if self.tooldesc.options["wholeselection"]==1:
			self.ui.whole_selection_check.setCheckState(qtcore.Qt.Checked)
		else:
			self.ui.whole_selection_check.setCheckState(qtcore.Qt.Unchecked)
		self.ui.color_threshold_box.setValue(self.tooldesc.options["similarity"])

	def on_color_threshold_box_valueChanged(self,value):
		if type(value)==int:
			self.tooldesc.options["similarity"]=value

	def on_whole_selection_check_clicked(self,bool=None):
		if bool!=None:
			self.tooldesc.options["wholeselection"]=bool

# paint bucket tool
class PaintBucketTool(AbstractTool):
	logtype=ToolLogTypes.raw
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)
		self.pointshistory=[]
		self.newpath=None

	def guiLevelPenDown(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		if self.options['wholeselection']==0:
			image=self.window.scene.getImageCopy()
			self.newpath=getSimilarColorPath(image,x,y,self.options['similarity'])

	def penDown(self,x,y,pressure=None):
		self.pointshistory=[(x,y,pressure)]
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
		self.layerkey=layerkey
		tool=self.getTool(window)
		return tool
 
	def getTool(self,window):
		return SelectionTool(self.options,window)

class SketchToolDesc(PencilToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"brush")
		self.displayname="Brush"

	def pressToolButton(self):
		BeeApp().master.ui.brush_button.setChecked(True)
 
	def setDefaultOptions(self):
		PencilToolDesc.setDefaultOptions(self)
		self.options["mindiameter"]=0
		self.options["maxdiameter"]=7
		self.options["step"]=1
		self.options["blur"]=30
		self.options["pressurebalance"]=100
		self.options["fade percent"]=0
		self.options["opacity"]=100
 
	def getTool(self,window):
		tool=SketchTool(self.options,window)
		tool.name=self.name
		return tool

	def getOptionsWidget(self,parent):
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

	def updateDisplayFromOptions(self):
		self.ui.brushdiameter.setValue(self.tooldesc.options["maxdiameter"])
		self.ui.stepsize.setValue(self.tooldesc.options["step"])

	def on_brushdiameter_sliderMoved(self,value):
		self.tooldesc.options["maxdiameter"]=value

	def on_stepsize_sliderMoved(self,value):
		self.tooldesc.options["step"]=value

class SketchTool(DrawingTool):
	def __init__(self,options,window):
		DrawingTool.__init__(self,options,window)
		self.lastpressure=-1
		self.compmode=qtgui.QPainter.CompositionMode_SourceOver
		self.scaledbrushes=[]
		self.brushshape=BrushShapes.ellipse

	def movedFarEnough(self,x,y):
		if distance2d(self.lastpoint[0],self.lastpoint[1],x,y) < self.options["step"]:
			return False
		return True

	# return how much to scale down the brush for the current pressure
	def scaleForPressure(self,pressure):
		minsize=self.options["mindiameter"]
		maxsize=self.options["maxdiameter"]

		#unroundedscale=(((maxsize-minsize)/maxsize)*pressure) + ((minsize/maxsize) * pressure)
		#print "unrounded scale:", unroundedscale
		unroundedscale=pressure
		#iscale=int(unroundedscale*BRUSH_SIZE_GRANULARITY)
		#scale=float(iscale)/BRUSH_SIZE_GRANULARITY
		scale=unroundedscale

		#print "calculated that scale should be:", scale

		return scale

	def updateBrushForPressure(self,pressure,subpixelx=0,subpixely=0):
		self.lastpressure=pressure
		#print "updating brush for pressure/subpixels:", pressure, subpixelx, subpixely
		scale=self.scaleForPressure(pressure)

		fullwidth,fullheight=self.fullsizedbrush.size
		targetwidth=int(math.ceil(fullwidth*scale))+1
		targetheight=int(math.ceil(fullheight*scale))+1

		# if the target size is an even number then make it odd
		if targetwidth%2==0:
			targetwidth+=1
		if targetheight%2==0:
			targetheight+=1

		# try to find exact or closest brushes to scale
		abovebrush, belowbrush = self.findScaledBrushes(scale)

		# didn't get an exact match so interpolate between two others
		if belowbrush:
			# shift both of the nearby brushes
			scaledaboveimage=self.scaleShiftImage(abovebrush,scale,subpixelx-.5,subpixely-.5,targetwidth,targetheight)

			# BEGIN: temporary change for testing speed and quality when taking out the dual scaling and interpolation
			outputimage=scaledaboveimage
			#scaledbelowimage=self.scaleShiftImage(belowbrush,scale,subpixelx-.5,subpixely-.5,targetwidth,targetheight)

			#t = (scale-belowbrush[1])/(abovebrush[1]-belowbrush[1])

			# interpolate between the results, but trust the one that was closer more
			#outputimage = self.interpolate(scaledbelowimage,scaledaboveimage, t)
			# END: temporary change for testing

		# if the scale is so small it should be at one
		elif abovebrush[1]!=scale or (abovebrush[0].size[0]==1 and abovebrush[0].size[1]==1):
			s = scale/abovebrush[1]
			outputimage = self.scaleSmallBrush(s, subpixelx-.5, subpixely-.5)
			#outputimage = self.scaleSinglePixelImage(s, self.singlepixelbrush, subpixelx-.5, subpixely-.5)

		# got an exact match, so just shift it according to sub-pixels
		else:
			outputimage=self.scaleShiftImage(abovebrush, scale, subpixelx-.5, subpixely-.5,targetwidth,targetheight)

		outputimage=outputimage.convert("RGBA")
		qalpha=ImageQt(outputimage)

		qimage=qtgui.QImage(qalpha.width(),qalpha.height(),qtgui.QImage.Format_RGB32)
		qimage.fill(self.getColorRGBA())
		qimage.setAlphaChannel(qalpha)

		self.brushimage=qimage

	# do special case calculations for brush of size smaller than full 3x3
	def scaleSmallBrush(self,scale,subpixelx,subpixely):
		fullwidth,fullheight=self.fullsizedbrush.size
		radius=fullwidth*scale/2.

		if radius>1.5:
			"WARNING: small brush called on brush with radius:", radius
			radius=1.5

		#print "radius:", radius

		brushwidth=3
		brushheight=3

		brushimage=Image.new("L",(brushwidth,brushheight),0)
		pix=brushimage.load()

		for i in range(brushwidth):
			for j in range(brushheight):
				curfade=self.ellipseBrushFadeAt(i,j,radius,brushwidth,brushheight,0)
				pix[i,j]=(int(round(curfade*255)))

		return scaleShiftPIL(brushimage,subpixelx,subpixely,5,5,1,1,Image.AFFINE)

	# do special case calculations for brush of single pixel size
	def scaleSinglePixelImage(self,scale,pixel,subpixelx,subpixely):
		#print "calling scaleSinglePixelImage with subpixels:",subpixelx,subpixely
		#print "calling scaleSinglePixelImage with scale",scale
		#print "single pixel image:"
		#printPILImage(pixel)

		outputimage=scaleShiftPIL(pixel,subpixelx,subpixely,2,2,scale,scale,Image.AFFINE)

		#print "Scaled single pixel brush:"
		#printPILImage(outputimage)

		return outputimage

	# optimizied algorithm to interpoloate two images, this pushes the work into Qt functions and saves memory by altering the original images
	def interpolate(self,image1,image2,t):
		if not ( image1.size[0] == image2.size[0] and image1.size[1] == image2.size[1] ):
			print "Error: interploate function passed non compatable images"
			return image1

		if t < 0:
			print "Error: interploate function passed bad t value:", t
			return image2
		elif t > 1:
			print "Error: interploate function passed bad t value:", t
			return image1

		#print "t value:", t
		#if t>.5:
		#	print "result should look more like image 1"
		#else:
		#	print "result should look more like image 2"

		#print "blending image:"
		#printPILImage(image1)
		#print "and image:"
		#printPILImage(image2)
		im=Image.blend(image1,image2,t)
		#print "to produce"
		#printPILImage(im)
		#print
		return im

	# return single brush that matches scale passed or two brushes that are nearest to that scale
	def findScaledBrushes(self,scale):
		current=None
		for i in range(len(self.scaledbrushes)):
			current=self.scaledbrushes[i]
			# if we get an exact match return just it
			if current[1] == scale:
				return (current,None)
			# if we fall between two return both
			elif current[1] < scale:
				return (current,self.scaledbrushes[i-1])
		# if we get to the end just return the last one
		return (current,None)

	# make full sized brush and list of pre-scaled brushes
	def makeFullSizedBrush(self):
		# only support one brush shape right now
		if self.brushshape==BrushShapes.ellipse:
			self.fullsizedbrush=self.makeEllipseBrush(self.options["maxdiameter"],self.options["maxdiameter"])

		self.makeScaledBrushes()

		self.singlepixelbrush=self.scaledbrushes[-1][0]

		self.colortuple=(self.fgcolor.red(),self.fgcolor.green(),self.fgcolor.blue())

	# make list of pre-scaled brushes
	def makeScaledBrushes(self):
		self.scaledbrushes=[]

		width,height=self.fullsizedbrush.size
		fullwidth,fullheight=self.fullsizedbrush.size

		while True:
			if width >= fullwidth and height >= fullheight:
				scaledImage=self.scaleImage(self.fullsizedbrush,width,height)
			# scale down using previous one once below 1:1
			else:
				scaledImage=self.scaleImage(scaledImage,width,height)

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

		#print "List of scaled brushes"
		#for brush in self.scaledbrushes:
			#print "brush scale: ", brush[1]
			#printPILImage(brush[0])
			
	def makeEllipseBrush(self,width,height):
		fgr=self.fgcolor.red()
		fgg=self.fgcolor.green()
		fgb=self.fgcolor.blue()

		radius=width/2.
		imgwidth=int(math.ceil(width))
		imgheight=int(math.ceil(height))

		fadepercent=self.options["fade percent"]

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
		centerx=math.ceil(imgwidth)/2.
		centery=math.ceil(imgheight)/2.

		distance=math.sqrt(((x+.5-centerx)**2)+((y+.5-centery)**2))

		# if the distance is over .5 past the radius then it's past the bounds of the brush
		if distance>radius+.5:
			return 0

		# special case for the center pixel
		elif distance==0:
			if radius<.5:
				return radius*2
			return 1

		elif distance<radius-.5:
			return 1

		return radius+.5-distance

	# use subpixel adjustments to shift image and scale it too if needed
	def scaleShiftImage(self,srcbrush,targetscale,subpixelx,subpixely,targetwidth,targetheight):
		scale=targetscale/srcbrush[1]
		#print "going from scale:", srcbrush[1], "to scale", targetscale
		#print "calculated conversion:", scale
		return scaleShiftPIL(srcbrush[0],subpixelx,subpixely,targetwidth,targetheight,scale,scale,Image.AFFINE)

	def scaleImage(self,srcimage,width,height):
		srcwidth,srcheight=srcimage.size

		if srcwidth==width and srcheight==height:
			return srcimage

		xscale=width/float(srcwidth)
		yscale=height/float(srcheight)

		return scaleShiftPIL(srcimage,0,0,width,height,xscale,yscale,Image.AFFINE)

	def getFullSizedBrushWidth(self):
		return self.fullsizedbrush.size[0]

class MoveSelectionToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"move selection")
		self.displayname="Move Selection"

	def pressToolButton(self):
		BeeApp().master.ui.move_selection_button.setChecked(True)

	def getTool(self,window):
		tool=MoveSelectionTool(self.options,window)
		tool.name=self.name
		return tool

	def setupTool(self,window,layerkey):
		if not layerkey:
			layerkey=window.getCurLayerKey()
		tool=self.getTool(window)
		tool.layerkey=layerkey
		return tool

# selection move tool
class MoveSelectionTool(AbstractTool):
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)
		self.pendown=False

	# figure out if pen is over selection or not, if it is over selection then do a move, if not do an anchor if current layer is a floating selection
	# command does not change any layers or even go through the drawing thread until the cursor is let up, at that point it puts an event through the drawing thread that moves it all at once
	def guiLevelPenDown(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		self.layer=self.window.getLayerForKey(self.layerkey)
		if self.layer:
			if self.layer.type==LayerTypes.floating:
				self.pendown=True
				self.lastx=int(x)
				self.lasty=int(y)
				self.startx=self.layer.pos().x()
				self.starty=self.layer.pos().y()

			else:
				for item in self.window.scene.items(qtcore.QPointF(x,y)):
					if item.type==LayerTypes.floating:
						self.layer=item
						guiLevelPenDown(x,y,pressure,modkeys)
						break

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

	def guiLevelPenMotion(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		if self.pendown:
			self.moveLayer(x,y,modkeys)

	def guiLevelPenUp(self,x,y,pressure,modkeys=qtcore.Qt.NoModifier):
		self.layer=None
		self.pendown=False
