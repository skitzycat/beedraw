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
 
from PencilOptionsDialogUi import *
from BrushOptionsDialogUi import *
from EraserOptionsDialogUi import *
from PaintBucketOptionsDialogUi import *

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
 
	def toolNameGenerator(self):
		for tool in self.toolslist:
			yield tool.name
 
	def getCurToolDesc(self):
		return self.toolslist[self.curtoolindex]
 
	def setCurToolIndex(self,index):
		self.curtoolindex=index
 
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
		self.setDefaultOptions()
 
	def getCursor(self):
		return qtcore.Qt.ArrowCursor
 
	def getDownCursor(self):
		return qtcore.Qt.ArrowCursor
 
	def setDefaultOptions(self):
		pass
 
	def getOptionsWidget(self,parent):
		return qtgui.QWidget(parent)
 
	def runOptionsDialog(self,parent):
		qtgui.QMessageBox(qtgui.QMessageBox.Information,"Sorry","No Options Avialable for this tool",qtgui.QMessageBox.Ok).exec_()
 
	# setup needed parts of tool using knowledge of current window
	# this should be implemented in subclass if needed
	def setupTool(self,window,layerkey=None):
		self.layerkey=layerkey
		return self.getTool(window)
 
	def getTool(self,window):
		return None
 
# base class for all drawing tools
class AbstractTool:
	# flag for if we need to log events of this type of tool
	logable=False
	def __init__(self,options,window):
		self.fgcolor=None
		self.bgcolor=None
		self.clippath=None
		self.options=options
		self.window=window
		self.layer=None
		self.valid=True

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
		self.window=None

	def validSetUp(self):
		return True
 
class EyeDropperToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"Eye Dropper")

	def setDefaultOptions(self):
		# option for if it should get color for a single layer or the whole visible image
		# curently this is set to just the whole visible image because otherwise for transparent colors it composes them onto black which doesn't look right at all
		self.options["singlelayer"]=0

	def getTool(self,window):
		tool=EyeDropperTool(self.options,window)
		tool.name=self.name
		return tool
 
	def setupTool(self,window,layerkey=None):
		self.layerkey=layerkey
		return self.getTool(window)

# eye dropper tool (select color from canvas)
class EyeDropperTool(AbstractTool):
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)
		self.name="Eye Dropper"

	def penDown(self,x,y,pressure=None):
		if self.options["singlelayer"]==0:
			color=self.window.getImagePixelColor(x,y)
		else:
			color=self.window.getCurLayerPixelColor(x,y)
		self.window.master.updateFGColor(qtgui.QColor(color))

# basic tool for everything that draws points on the canvas
class DrawingTool(AbstractTool):
	# flag for if we need to log events of this type of tool
	logable=True
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)
		self.name="Pencil"
		self.lastpressure=-1
		self.compmode=qtgui.QPainter.CompositionMode_SourceOver
		self.pointshistory=None
		self.layer=None
 
	# for drawing tools make sure there is a valid layer before it will work
	def validSetUp(self):
		if layer==None:
			return False
		return True
 
	def getColorRGBA(self):
		return self.fgcolor.rgba()
 
	def makeFullSizedBrush(self):
		diameter=self.options["maxdiameter"]
		self.diameter=self.options["maxdiameter"]

		color=self.getColorRGBA()
 
		center=diameter/2.0
		self.fullsizedbrush=qtgui.QImage(diameter,diameter,qtgui.QImage.Format_ARGB32_Premultiplied)
		self.fullsizedbrush.fill(0)
		for i in range(diameter):
			for j in range(diameter):
				# add in .5 to each point so we measure from the center of the pixel
				distance=math.sqrt(((i+.5-center)**2)+((j+.5-center)**2))
				if distance <= center:
					self.fullsizedbrush.setPixel(i,j,color)

	def updateBrushForPressure(self,pressure,subpixelx=0,subpixely=0):
		# see if we need to update at all
		if self.lastpressure==pressure:
			return
 
		self.lastpressure=pressure
 
		# if we can use the full sized brush, then do it
		if self.options["pressuresize"]==0 or pressure==1:
			self.brushimage=self.fullsizedbrush
			self.lastpressure=1
			return
 
		# scaled size for brush
		bdiameter=self.options["maxdiameter"]*pressure
		self.diameter=int(math.ceil(bdiameter))

		# calculate offset into target
		targetoffset=(1-(bdiameter%1))/2.0
 
		# bounding radius for pixels to update
		side=self.diameter
 
		fullsizedrect=qtcore.QRectF(0,0,self.fullsizedbrush.width(),self.fullsizedbrush.height())
		cursizerect=qtcore.QRectF(targetoffset,targetoffset,bdiameter,bdiameter)
 
		self.brushimage=qtgui.QImage(side,side,qtgui.QImage.Format_ARGB32_Premultiplied)
		self.brushimage.fill(0)
		painter=qtgui.QPainter()
		painter.begin(self.brushimage)
 
		painter.drawImage(cursizerect,self.fullsizedbrush,fullsizedrect)

		painter.end()
 
	def penDown(self,x,y,pressure=1):
		#print "pen down point:", x, y
		#print "pen pressure:", pressure
		self.layer=self.window.getLayerForKey(self.layerkey)
		self.oldlayerimage=qtgui.QImage(self.layer.image)
		self.pointshistory=[(x,y,pressure)]
		self.lastpoint=(x,y)
		self.makeFullSizedBrush()
		self.updateBrushForPressure(pressure,x%1,y%1)

		targetx=int(x)-int(self.brushimage.width()/2)
		targety=int(y)-int(self.brushimage.height()/2)

		#print "button pressed on pixel:", x,y
		#print "pasting corner on pixel:", targetx,targety

		# if this is an even number then do adjustments for the center if needed
		if self.brushimage.width()%2==0:
			#print "this is an even sized brush:"
			if x%1>.5:
				targetx+=1
			if y%1>.5:
				targety+=1

		self.layer.compositeFromCorner(self.brushimage,targetx,targety,self.compmode,self.clippath)

	# determine if it's moved far enough that we care
	def movedFarEnough(self,x,y):
		if int(x)==int(self.lastpoint[0]) and int(y)==int(self.lastpoint[1]):
			return False
		return True

	def scaleForPressure(self,pressure):
		return pressure

	def getFullSizedBrushWidth(self):
		return self.fullsizedbrush.width()

	def penMotion(self,x,y,pressure):
		#print "pen motion point:", x, y
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
 
	def penUp(self,x=None,y=None):
		radius=int(math.ceil(self.options["maxdiameter"]))
 
		# get maximum bounds of whole brush stroke
		left=self.pointshistory[0][0]
		right=self.pointshistory[0][0]
		top=self.pointshistory[0][1]
		bottom=self.pointshistory[0][1]
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
 
		command=DrawingCommand(self.layer.key,oldimage,dirtyrect)

		self.window.addCommandToHistory(command,self.layer.owner)
 
		BeeApp().master.refreshLayerThumb(self.window.id,self.layer.key)
 
# basic tool for drawing fuzzy edged stuff on the canvas
class PaintBrushTool(DrawingTool):
	def __init__(self,options,window):
		DrawingTool.__init__(self,options,window)
		self.name="brush"
		self.lastpressure=-1
		self.compmode=qtgui.QPainter.CompositionMode_SourceOver
 
	def updateBrushForPressure(self,pressure,subpixelx=0,subpixely=0):
		# see if we need to update at all
		if self.lastpressure==pressure:
			return
		self.lastpressure=pressure
 
		self.diameter=int(math.ceil(self.fullsizedbrush.width()*pressure))

		# the scaling algorithim fails here so we need our own method
		if self.diameter==1:
			# if the diameter is 1 set the opacity perportinal to the pressure and the blur options
			alpha=(pressure*self.fullsizedbrush.width())*(1-(self.options['blur']/100.0))
		
			self.brushimage=qtgui.QImage(1,1,qtgui.QImage.Format_ARGB32_Premultiplied)

			fgr=self.fgcolor.red()
			fgg=self.fgcolor.green()
			fgb=self.fgcolor.blue()

			# set only pixel
			color=qtgui.qRgba(fgr*alpha,fgg*alpha,fgb*alpha,alpha*255)
			self.brushimage.setPixel(0,0,color)

			return
		elif self.diameter==2:
			# set alpha for the pixels according to the blur option and pressure
			alpha=(pressure*self.fullsizedbrush.width())/2
			alpha*=.5
			alpha+=.5
			alpha*=1-(self.options["blur"]/100.0)
		
			self.brushimage=qtgui.QImage(2,2,qtgui.QImage.Format_ARGB32_Premultiplied)

			fgr=self.fgcolor.red()
			fgg=self.fgcolor.green()
			fgb=self.fgcolor.blue()

			# set upper right pixel
			#color=qtgui.qRgba(fgr,fgg,fgb,255)
			#self.brushimage.setPixel(0,0,color)

			# set all pixels
			color=qtgui.qRgba(fgr*alpha,fgg*alpha,fgb*alpha,alpha*255)
			self.brushimage.setPixel(0,0,color)
			self.brushimage.setPixel(1,0,color)
			self.brushimage.setPixel(0,1,color)
			self.brushimage.setPixel(1,1,color)

			return

		# if we can use the full sized brush, then do it
		if self.options["pressuresize"]==0 or pressure==1:
			self.brushimage=self.fullsizedbrush
			self.diameter=self.options["maxdiameter"]
			return

		# for a diameter of 3 or more the QT transforms seem to work alright
		scaletransform=qtgui.QTransform()
		finaltransform=qtgui.QTransform()

		scaledown=pressure
		#scaledown=float(self.diameter)/self.fullsizedbrush.width()

		scaletransform=scaletransform.scale(scaledown,scaledown)

		# scale the brush to proper size
		#self.brushimage=self.fullsizedbrush.transformed(scaletransform,qtcore.Qt.SmoothTransformation)
 
 		centeroffset=0
 		#centeroffset=(1-((self.options["maxdiameter"])%1))/2.0
		transbrushsize=scaletransform.map(qtcore.QPointF(self.fullsizedbrush.width(),self.fullsizedbrush.height()))

 		transformoffset=(1-(transbrushsize.x()%1))/2.0

		finaltransform=finaltransform.translate(transformoffset,transformoffset)
		finaltransform=finaltransform.scale(scaledown,scaledown)
 
 		newtransupperleft=finaltransform.map(qtcore.QPointF(0,0))
 		newtranslowerright=finaltransform.map(qtcore.QPointF(self.fullsizedbrush.width(),self.fullsizedbrush.height()))
		newtransright=1-(newtranslowerright.x()%1)
		newtransbottom=1-(newtranslowerright.y()%1)
		#print "new brush margins:", newtransupperleft.x(), newtransupperleft.y(), newtransright, newtransbottom

		# scale the brush to proper size (alternate method)
		self.brushimage=qtgui.QImage(self.diameter,self.diameter,qtgui.QImage.Format_ARGB32_Premultiplied)
		self.brushimage.fill(0)
		painter=qtgui.QPainter()
		painter.begin(self.brushimage)
		painter.setRenderHint(qtgui.QPainter.Antialiasing)
		painter.setRenderHint(qtgui.QPainter.SmoothPixmapTransform)
		painter.setRenderHint(qtgui.QPainter.HighQualityAntialiasing)
		painter.setTransform(finaltransform)
		painter.drawImage(qtcore.QPointF(centeroffset,centeroffset),self.fullsizedbrush)
 
 		# debugging, code, uncomment as needed
		#print "updated brush for pressure:", pressure
		#printImage(self.brushimage)
 
	def makeFullSizedBrush(self):
		diameter=self.options["maxdiameter"]
		radius=diameter/2.0
		blur=self.options["blur"]
 
		fgr=self.fgcolor.red()
		fgg=self.fgcolor.green()
		fgb=self.fgcolor.blue()
 
		center=diameter/2.0
		self.fullsizedbrush=qtgui.QImage(diameter,diameter,qtgui.QImage.Format_ARGB32_Premultiplied)
		self.fullsizedbrush.fill(0)
		for i in range(diameter):
			for j in range(diameter):
				# add in .5 to each point so we measure from the center of the pixel
				distance=math.sqrt(((i+.5-center)**2)+((j+.5-center)**2))
				if distance < radius:
					# fade the brush out a little if it is too close to the edge according to the blur percentage
					fade=(1-(distance/(radius)))/(blur/100.0)
					if fade > 1:
						fade=1
					# need to muliply the color by the alpha becasue it's going into
					# a premultiplied image
					curcolor=qtgui.qRgba(fgr*fade,fgg*fade,fgb*fade,fade*255)
					self.fullsizedbrush.setPixel(i,j,curcolor)
 
# this is the most basic drawing tool
class PencilToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"Hard Edge Brush")
 
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
 
	def getTool(self,window):
		tool=DrawingTool(self.options,window)
		tool.name=self.name
		return tool
 
	def setupTool(self,window,layerkey=None):
		if not layerkey:
			layerkey=window.curlayerkey

		tool=self.getTool(window)
		# copy the foreground color
		tool.fgcolor=qtgui.QColor(window.master.fgcolor)
		tool.layerkey=window.curlayerkey
 
		# if there is a selection get a copy of it
		if window.selection:
			tool.clippath=qtgui.QPainterPath(window.clippath)
 
		return tool
 
	def runOptionsDialog(self,parent):
		dialog=qtgui.QDialog()
		dialog.ui=Ui_PencilOptionsDialog()
		dialog.ui.setupUi(dialog)
 
		dialog.ui.brushdiameter.setValue(self.options["maxdiameter"])
		dialog.ui.pressurebalance.setValue(self.options["pressurebalance"])
		dialog.ui.stepsize.setValue(self.options["step"])
 
		dialog.exec_()
 
		if dialog.result():
			self.options["maxdiameter"]=dialog.ui.brushdiameter.value()
			self.options["pressurebalance"]=dialog.ui.pressurebalance.value()
			self.options["step"]=dialog.ui.stepsize.value()
 
class PaintBrushToolDesc(PencilToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"paintbrush")
 
	def setDefaultOptions(self):
		PencilToolDesc.setDefaultOptions(self)
		self.options["maxdiameter"]=7
		self.options["step"]=1
		self.options["pressuresize"]=1
		self.options["blur"]=30
		self.options["pressurebalance"]=100
		self.options["opacity"]=100
 
	def getTool(self,window):
		tool=PaintBrushTool(self.options,window)
		tool.name=self.name
		return tool
 
	def runOptionsDialog(self,parent):
		dialog=qtgui.QDialog()
		dialog.ui=Ui_BrushOptionsDialog()
		dialog.ui.setupUi(dialog)
 
		dialog.ui.brushdiameter.setValue(self.options["maxdiameter"])
		dialog.ui.pressurebalance.setValue(self.options["pressurebalance"])
		dialog.ui.stepsize.setValue(self.options["step"])
		dialog.ui.blurslider.setValue(self.options["blur"])
 
		dialog.exec_()
 
		if dialog.result():
			self.options["maxdiameter"]=dialog.ui.brushdiameter.value()
			self.options["pressurebalance"]=dialog.ui.pressurebalance.value()
			self.options["step"]=dialog.ui.stepsize.value()
			self.options["blur"]=dialog.ui.blurslider.value()
 
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
 
	def setDefaultOptions(self):
		self.options["maxdiameter"]=21
		self.options["step"]=1
		self.options["pressuresize"]=1
		self.options["pressurebalance"]=100
		self.options["blur"]=100
 
	def runOptionsDialog(self,parent):
		dialog=qtgui.QDialog()
		dialog.ui=Ui_EraserOptionsDialog()
		dialog.ui.setupUi(dialog)
 
		dialog.ui.eraserdiameter.setValue(self.options["maxdiameter"])
		dialog.ui.stepsize.setValue(self.options["step"])
		dialog.ui.blurpercent.setValue(self.options["blur"])
 
		dialog.exec_()
 
		if dialog.result():
			self.options["maxdiameter"]=dialog.ui.eraserdiameter.value()
			self.options["step"]=dialog.ui.stepsize.value()
			self.options["blur"]=dialog.ui.blurpercent.value()
 
	def getTool(self,window):
		tool=self.Tool(self.options,window)
		tool.name=self.name
		return tool
 
	def setupTool(self,window,layerkey=None):
		self.layerkey=layerkey
		tool=self.getTool(window)
		if window.selection:
			tool.clippath=qtgui.QPainterPath(window.clippath)
		tool.layerkey=window.curlayerkey
		return tool
 
# selection overlay information
class SelectionOverlay:
	def __init__(self,path,pen=None,brush=None):
		if not pen:
			pen=qtgui.QPen()
		self.pen=pen
 
		if not brush:
			brush=qtgui.QBrush()
		self.brush=brush
 
		self.path=path
 
# basic rectangle selection tool
class SelectionTool(AbstractTool):
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)
 
	def updateOverlay(self,x,y):
		oldrect=None
		# calculate rectangle defined by the start and current
		left=min(x,self.startpoint[0])
		top=min(y,self.startpoint[1])
		width=max(x,self.startpoint[0])-left
		height=max(y,self.startpoint[1])-top
 
		if self.window.cursoroverlay:
			oldrect=self.window.cursoroverlay.path.boundingRect().toAlignedRect()
 
		overlay=qtgui.QPainterPath()
		overlay.addRect(left,top,width,height)
 
		# calculate area we need to refresh, it should be the union of rect to draw
		# next and the last one that was drawn
		self.window.cursoroverlay=SelectionOverlay(overlay)
		newrect=self.window.cursoroverlay.path.boundingRect().toAlignedRect()
		newrect.adjust(-1,-1,2,2)
		refreshregion=qtgui.QRegion(newrect)
 
		if oldrect:
			oldrect.adjust(-1,-1,2,2)
			refreshregion=refreshregion.unite(qtgui.QRegion(oldrect))
 
		self.window.view.updateView(refreshregion.boundingRect())
 
	def penDown(self,x,y,pressure=None):
		x=int(x)
		y=int(y)
		self.startpoint=(x,y)
		self.lastpoint=(x,y)
 
	def penUp(self,x,y,source=0):
		x=int(x)
		y=int(y)
		# just for simplicty the dirty region will be the old selection unioned
		# with the current overlay
		if len(self.window.selection)>0:
			srect=qtcore.QRect()
			for select in self.window.selection:
				srect=srect.united(select.boundingRect().toAlignedRect())
 
			srect.adjust(-1,-1,2,2)
			dirtyregion=qtgui.QRegion(srect)
		else:
			dirtyregion=qtgui.QRegion()
 
		# get modifier keys currently being held down
		modkeys=BeeApp().app.keyboardModifiers()
 
		# change selection according to current modifier keys
		if modkeys==qtcore.Qt.ShiftModifier:
			self.window.changeSelection(SelectionModTypes.add)
		elif modkeys==qtcore.Qt.ControlModifier:
			self.window.changeSelection(SelectionModTypes.subtract)
		elif modkeys==qtcore.Qt.ControlModifier|qtcore.Qt.ShiftModifier:
			self.window.changeSelection(SelectionModTypes.intersect)
		# if we don't recognize the modifier types just replace the selection
		else:
			self.window.changeSelection(SelectionModTypes.new)
 
		if self.window.cursoroverlay:
			srect=self.window.cursoroverlay.path.boundingRect().toAlignedRect()
			srect.adjust(-1,-1,2,2)
			dirtyregion=dirtyregion.unite(qtgui.QRegion(srect))
			self.window.cursoroverlay=None
 
		self.window.view.updateView(dirtyregion.boundingRect())
 
	# set overlay to display area that would be selected if user lifted up button
	def penMotion(self,x,y,pressure):
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
		AbstractToolDesc.__init__(self,"rectangle select")
	def setupTool(self,window,layerkey=None):
		self.layerkey=layerkey
		tool=self.getTool(window)
		return tool
 
	def getTool(self,window):
		tool=SelectionTool(self.options,window)
		tool.name=self.name
		return tool

# fuzzy selection tool description
class FeatherSelectToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"Feather Select")

	def setDefaultOptions(self):
		self.options["similarity"]=10

	def getTool(self,window):
		tool=FeatherSelectTool(self.options,window)
		tool.name=self.name
		return tool
 
	def setupTool(self,window,layerkey=None):
		self.layerkey=layerkey
		return self.getTool(window)

# fuzzy selection tool
class FeatherSelectTool(SelectionTool):
	def __init__(self,options,window):
		SelectionTool.__init__(self,options,window)

	def penDown(self,x,y,pressure=None):
		newpath=getSimilarColorRegion(self.window.image,x,y,self.options['similarity'])
		self.window.changeSelection(SelectionModTypes.new,newpath)

# paint bucket tool description
class PaintBucketToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"Paint Bucket Fill")

	def setDefaultOptions(self):
		self.options["similarity"]=10
		self.options["wholeselection"]=1

	def getTool(self,window):
		tool=PaintBucketTool(self.options,window)
		tool.name=self.name
		return tool
 
	def setupTool(self,window,layerkey=None):
		if not layerkey:
			layerkey=window.curlayerkey

		tool=self.getTool(window)

		tool.fgcolor=qtgui.QColor(window.master.fgcolor)
		tool.layerkey=layerkey

		# if there is a selection get a copy of it
		if window.selection:
			tool.clippath=qtgui.QPainterPath(window.clippath)

		return tool

	def runOptionsDialog(self,parent):
		dialog=qtgui.QDialog()
		dialog.ui=Ui_PaintBucketOptionsDialog()
		dialog.ui.setupUi(dialog)

		if self.options["wholeselection"]==1:
			dialog.ui.whole_selection_check.setCheckState(qtcore.Qt.Checked)
		else:
			dialog.ui.whole_selection_check.setCheckState(qtcore.Qt.Unchecked)
		dialog.ui.color_threshold_box.setValue(self.options["similarity"])
 
		dialog.exec_()

		if dialog.result():
			self.options["similarity"]=dialog.ui.color_threshold_box.value()
			if dialog.ui.whole_selection_check.checkState()==qtcore.Qt.Unchecked:
				self.options["wholeselection"]=0
			else:
				self.options["wholeselection"]=1

# paint bucket tool
class PaintBucketTool(AbstractTool):
	logable=True
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)
		self.pointshistory=[]

	def penDown(self,x,y,pressure=None):
		self.pointshistory=[(x,y,pressure)]
		layer=self.window.getLayerForKey(self.layerkey)
		if not layer:
			return

		image=qtgui.QImage(layer.image.size(),layer.image.format())
		image.fill(self.window.master.fgcolor.rgb())
		if self.options['wholeselection']==0:
			fillpath=getSimilarColorRegion(self.window.image,x,y,self.options['similarity'])
			if self.window.clippath:
				fillpath=fillpath.intersected(self.window.clippath)
			self.window.addRawEventToQueue(self.layerkey,image,0,0,fillpath)
		else:
			self.window.addRawEventToQueue(self.layerkey,image,0,0,self.window.clippath)

# elipse selection tool
class ElipseSelectionToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"elipse select")
	def setupTool(self,window,layerkey=None):
		self.layerkey=layerkey
		tool=self.getTool(window)
		return tool
 
	def getTool(self,window):
		return SelectionTool(self.options,window)

class SketchToolDesc(PencilToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"Soft Edge Brush")
 
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
 
	def runOptionsDialog(self,parent):
		dialog=qtgui.QDialog()
		dialog.ui=Ui_BrushOptionsDialog()
		dialog.ui.setupUi(dialog)
 
		dialog.ui.brushdiameter.setValue(self.options["maxdiameter"])
		dialog.ui.pressurebalance.setValue(self.options["pressurebalance"])
		dialog.ui.stepsize.setValue(self.options["step"])
		dialog.ui.blurslider.setValue(self.options["blur"])
 
		dialog.exec_()
 
		if dialog.result():
			self.options["maxdiameter"]=dialog.ui.brushdiameter.value()
			self.options["pressurebalance"]=dialog.ui.pressurebalance.value()
			self.options["step"]=dialog.ui.stepsize.value()
			self.options["blur"]=dialog.ui.blurslider.value()

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
			scaledbelowimage=self.scaleShiftImage(belowbrush,scale,subpixelx-.5,subpixely-.5,targetwidth,targetheight)

			t = (scale-belowbrush[1])/(abovebrush[1]-belowbrush[1])

			# interpolate between the results, but trust the one that was closer more
			outputimage = self.interpolate(scaledbelowimage,scaledaboveimage, t)

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

		return scaleShiftPIL(brushimage,subpixelx,subpixely,5,5,1,1)

	# do special case calculations for brush of single pixel size
	def scaleSinglePixelImage(self,scale,pixel,subpixelx,subpixely):
		#print "calling scaleSinglePixelImage with subpixels:",subpixelx,subpixely
		#print "calling scaleSinglePixelImage with scale",scale
		#print "single pixel image:"
		#printPILImage(pixel)

		outputimage=scaleShiftPIL(pixel,subpixelx,subpixely,2,2,scale,scale)

		#print "Scaled single pixel brush:"
		#printPILImage(outputimage)

		return outputimage

	# optimizied algorithm to interpoloate two images, this pushes the work into Qt functions and saves memory by altering the original images
	def interpolate(self,image1,image2,t):
		if not ( image1.size[0] == image2.size[0] and image1.size[1] == image2.size[1] ):
			print "Error: interploate function passed non compatable images"
			return image1

		if t < 0:
			print  "Error: interploate function passed bad t value:", t
			return image2
		elif t > 1:
			print  "Error: interploate function passed bad t value:", t
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

		brushimage=Image.new("L",(imgwidth,imgheight),0)

		# create raw access object for faster pixel setting
		pix=brushimage.load()

		for i in range(width):
			for j in range(height):
				v=self.ellipseBrushFadeAt(i,j,radius,width,height,fadepercent)
				if v>0:
					pix[i,j]=(int(round(255*v)))

		return brushimage

	# 
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
		return scaleShiftPIL(srcbrush[0],subpixelx,subpixely,targetwidth,targetheight,scale,scale)

	def scaleImage(self,srcimage,width,height):

		srcwidth,srcheight=srcimage.size

		if srcwidth==width and srcheight==height:
			return srcimage

		xscale=width/float(srcwidth)
		yscale=height/float(srcheight)

		return scaleShiftPIL(srcimage,0,0,width,height,xscale,yscale)

	def getFullSizedBrushWidth(self):
		return self.fullsizedbrush.size[0]
