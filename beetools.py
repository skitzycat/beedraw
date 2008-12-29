#!/usr/bin/env python
 
import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore
import math
from beeutil import *
from beetypes import *
from beeeventstack import *
 
from PencilOptionsDialogUi import *
from BrushOptionsDialogUi import *
from EraserOptionsDialogUi import *
from PaintBucketOptionsDialogUi import *
 
# Class to manage tools and make instances as needed
class BeeToolBox:
	def __init__(self):
		self.toolslist=[]
		self.loadDefaultTools()
		self.curtoolindex=0
 
	def loadDefaultTools(self):
		self.toolslist.append(PencilToolDesc())
		self.toolslist.append(PaintBrushToolDesc())
		self.toolslist.append(EraserToolDesc())
		self.toolslist.append(RectSelectionToolDesc())
		self.toolslist.append(EyeDropperToolDesc())
		self.toolslist.append(FeatherSelectToolDesc())
		self.toolslist.append(PaintBucketToolDesc())
		self.toolslist.append(SketchToolDesc())
 
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
	def setupTool(self,window):
		return self.getTool(window)
 
	def getTool(self,window):
		return None
 
# base class for all drawing tools
class AbstractTool:
	def __init__(self,options,window):
		self.fgcolor=None
		self.bgcolor=None
		self.clippath=None
		self.options=options
		self.window=window
 
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
 
	def setupTool(self,window):
		return self.getTool(window)

# eye dropper tool (select color from canvas)
class EyeDropperTool(AbstractTool):
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)
		self.name="Eye Dropper"
		self.window=window

	def penDown(self,x,y,pressure=None):
		if self.options["singlelayer"]==0:
			color=self.window.getImagePixelColor(x,y)
		else:
			color=self.window.getCurLayerPixelColor(x,y)
		self.window.master.updateFGColor(qtgui.QColor(color))

# basic tool for everything that draws points on the canvas
class DrawingTool(AbstractTool):
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)
		self.name="Pencil"
		self.lastpressure=-1
		self.compmode=qtgui.QPainter.CompositionMode_SourceOver
		self.pointshistory=None
		self.layer=None
 
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

		x=math.floor(x)

		y=math.floor(y)

		self.layer.compositeFromCenter(self.brushimage,int(x),int(y),self.compmode,self.clippath)
 
	# determine if it's moved far enough that we care
	def movedFarEnough(self,x,y):
		if int(x)==int(self.lastpoint[0]) and int(y)==int(self.lastpoint[1]):
			return False
		return True

	def penMotion(self,x,y,pressure):
		#print "pen motion point:", x, y
		# if it hasn't moved just do nothing
		if not self.movedFarEnough(x,y):
			return

		#print "starting new line"
		self.pointshistory.append((x,y,pressure))
 
		# get size of layer
		layerwidth=self.layer.window.docwidth
		layerheight=self.layer.window.docheight
 
		# get points inbetween according to step option and layer size
		path=getPointsPath(self.lastpoint[0],self.lastpoint[1],x,y,self.options['step'],layerwidth,layerheight,self.lastpressure,pressure)

		# if no points are on the layer just return
		if len(path)==0:
			return

		self.updateBrushForPressure(pressure,x%1,y%1)
		#radius=int(math.ceil(self.diameter/2.0))
		radius=int(math.ceil(self.brushimage.width()/2.0))

		# calculate the bounding rect for this operation
		left=int(min(path[0][0],path[-1][0])-radius-.5)
		top=int(min(path[0][1],path[-1][1])-radius-.5)
		right=int(max(path[0][0],path[-1][0])+radius+.5)
		bottom=int(max(path[0][1],path[-1][1])+radius+.5)
 
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

		# put points in that image
		painter=qtgui.QPainter()
		painter.begin(lineimage)
		#painter.setRenderHint(qtgui.QPainter.HighQualityAntialiasing)
 
		for point in path:
			self.updateBrushForPressure(point[2],point[0]%1,point[1]%1)

			stampx=point[0]-left-radius
			stampy=point[1]-top-radius

			#print "stamping at point:", stampx, stampy

			#if self.brushimage.width()%2==0:
			#	stampx=round(stampx)
			#else:
			#	stampx=math.floor(stampx)

			#if self.brushimage.height()%2==0:
			#	stampy=round(stampy)
			#else:
			#	stampy=math.floor(stampy)

			stampx=math.floor(stampx)
			stampy=math.floor(stampy)

			painter.drawImage(stampx,stampy,self.brushimage)
 
		painter.end()
 
		self.layer.compositeFromCorner(lineimage,left,top,self.compmode,self.clippath)
 
		self.lastpoint=(path[-1][0],path[-1][1])
 
	# record this event in the history
	def penUp(self,x=None,y=None,source=0):
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
		dirtyrect=rectIntersectBoundingRect(dirtyrect,self.layer.image.rect())
 
		# get image of what area looked like before
		oldimage=self.oldlayerimage.copy(dirtyrect)
 
		command=DrawingCommand(self.layer.key,oldimage,dirtyrect)
		self.layer.window.addCommandToHistory(command,source)
 
		self.layer.window.master.refreshLayerThumb(self.layer.key)
 
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
		AbstractToolDesc.__init__(self,"Pencil")
 
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
 
	def getTool(self,window):
		tool=DrawingTool(self.options,window)
		tool.name=self.name
		return tool
 
	def setupTool(self,window):
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
		self.options["maxdiameter"]=7
		self.options["step"]=1
		self.options["pressuresize"]=1
		self.options["blur"]=30
		self.options["pressurebalance"]=100
 
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
 
	def setupTool(self,window):
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
		modkeys=self.window.master.app.keyboardModifiers()
 
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
	def setupTool(self,window):
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
 
	def setupTool(self,window):
		return self.getTool(window)

# fuzzy selection tool
class FeatherSelectTool(SelectionTool):
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)

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
 
	def setupTool(self,window):
		return self.getTool(window)

	def runOptionsDialog(self,parent):
		dialog=qtgui.QDialog()
		dialog.ui=Ui_PaintBucketOptionsDialog()
		dialog.ui.setupUi(dialog)
 
		self.options["similarity"]=10
		if self.options["wholeselection"]==1:
			dialog.ui.whole_selection_check.setCheckState(qtcore.CheckState.Checked)
		else:
			dialog.ui.whole_selection_check.setCheckState(qtcore.CheckState.Unchecked)
		dialog.ui.color_threshold_box.setValue(self.options["similarity"])
 
		dialog.exec_()

		if dialog.result():
			self.options["similarity"]=dialog.ui.color_threshold_box.value()
			if dialog.ui.whole_selection_check.checkState()==qtcore.CheckState.Unchecked:
				self.options["wholeselection"]==0
			else:
				self.options["wholeselection"]==1

# paint bucket tool
class PaintBucketTool(AbstractTool):
	def __init__(self,options,window):
		AbstractTool.__init__(self,options,window)

	def penDown(self,x,y,pressure=None):
		image=qtgui.QImage(self.window.image.size(),self.window.image.format())
		image.fill(self.window.master.fgcolor.rgb())
		if self.options['wholeselection']==0:
			fillpath=getSimilarColorRegion(self.window.image,x,y,self.options['similarity'])
			if self.window.clippath:
				fillpath=fillpath.intersected(self.window.clippath)
			self.window.addRawEventToQueue(self.window.curlayerkey,image,0,0,fillpath)
		else:
			self.window.addRawEventToQueue(self.window.curlayerkey,image,0,0,self.window.clippath)

# elipse selection tool
class ElipseSelectionToolDesc(AbstractToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"elipse select")
	def setupTool(self,window):
		tool=self.getTool(window)
		return tool
 
	def getTool(self,window):
		return SelectionTool(self.options,window)

class SketchToolDesc(PencilToolDesc):
	def __init__(self):
		AbstractToolDesc.__init__(self,"sketch brush")
 
	def setDefaultOptions(self):
		self.options["maxdiameter"]=7
		self.options["step"]=1
		self.options["pressuresize"]=1
		self.options["blur"]=30
		self.options["pressurebalance"]=100
		self.options["fade vertical"]=2
		self.options["fade horizontal"]=2
 
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


	def movedFarEnough(self,x,y):
		if distance2d(self.lastpoint[0],self.lastpoint[1],x,y) < self.options["step"]:
			return False
		return True

	# return how much to scale down the brush for the current pressure
	def scaleForPressure(self,pressure):
		minsize=0
		maxsize=self.options["maxdiameter"]

		#unroundedscale=(((maxsize-minsize)/maxsize)*pressure) + ((minsize/maxsize) * pressure)
		#print "unrounded scale:", unroundedscale
		unroundedscale=pressure
		#iscale=int(unroundedscale*BRUSH_SIZE_GRANULARITY)
		#scale=float(iscale)/BRUSH_SIZE_GRANULARITY
		scale=unroundedscale

		return scale

	def updateBrushForPressure(self,pressure,subpixelx=0,subpixely=0):
		self.lastpressure=pressure
		#print "updating brush for pressure/subpixels:", pressure, subpixelx, subpixely
		scale=self.scaleForPressure(pressure)

		# try to find exact or closes brushes to scale
		abovebrush, belowbrush = self.findScaledBrushes(scale)

		# didn't get an exact match so interpolate between two others
		if belowbrush:
			# shift both of the nearby brushes
			scaledaboveimage=self.scaleShiftImage(abovebrush,scale,subpixelx,subpixely)
			scaledbelowimage=self.scaleShiftImage(belowbrush,scale,subpixelx,subpixely)

			t = (scale-belowbrush[1])/(abovebrush[1]-belowbrush[1])

			# interpolate between the results, but trust the one that was closer more
			outputimage = self.interpolate(scaledbelowimage,scaledaboveimage, t)

		# we were below the lowest sized brush or exactly at 1
		elif abovebrush[1]!=scale or (abovebrush[0].width()==1 and abovebrush[0].height()==1):
			s = scale/abovebrush[1]
			outputimage = self.scaleSinglePixelImage(s, self.singlepixelbrush.pixel(0,0), subpixelx, subpixely)

		# got an exact match, so just shift it according to sub-pixels
		else:
			outputimage=self.scaleShiftImage(abovebrush, scale, subpixelx, subpixely)

		self.brushimage=outputimage

	# do special case calculations for brush of single pixel size
	def scaleSinglePixelImage(self,scale,pixel,subpixelx,subpixely):
		#print "calling scaleSinglePixelImage with subpixels:",subpixelx,subpixely
		#print "calling scaleSinglePixelImage with scale",scale
		srcwidth=1
		srcheight=1
		dstwidth=2
		dstheight=2

		outputimage=qtgui.QImage(dstwidth,dstheight,qtgui.QImage.Format_ARGB32_Premultiplied)

		a = subpixelx
		b = subpixely

		#a = subpixelx-.5
		#b = subpixely-.5

		#if a<0:
		#	a=1.+a

		#if b<0:
		#	b=1.+b
 
 		for y in range(dstheight):
			for x in range(dstwidth):
				if x > 0 and y > 0:
					topleft=pixel
				else:
					topleft=qtgui.qRgba(0,0,0,0)
				if x > 0 and y < srcheight:
					bottomleft=pixel
				else:
					bottomleft=qtgui.qRgba(0,0,0,0)
				if x < srcwidth and y > 0:
					topright=pixel
				else:
					topright=qtgui.qRgba(0,0,0,0)
				if x < srcwidth and y < srcheight:
					bottomright=pixel
				else:
					bottomright=qtgui.qRgba(0,0,0,0)

				red=(a*b*qtgui.qRed(topleft)
						+ a * (1-b) * qtgui.qRed(bottomleft)
						+ (1-a) * b * qtgui.qRed(topright)
						+ (1-a) * (1-b) * qtgui.qRed(bottomright) + .5 )
				green=(a*b*qtgui.qGreen(topleft)
						+ a * (1-b) * qtgui.qGreen(bottomleft)
						+ (1-a) * b * qtgui.qGreen(topright)
						+ (1-a) * (1-b) * qtgui.qGreen(bottomright) + .5 )
				blue=(a*b*qtgui.qBlue(topleft)
						+ a * (1-b) * qtgui.qBlue(bottomleft)
						+ (1-a) * b * qtgui.qBlue(topright)
						+ (1-a) * (1-b) * qtgui.qBlue(bottomright) + .5 )
				alpha=(a*b*qtgui.qAlpha(topleft)
						+ a * (1-b) * qtgui.qAlpha(bottomleft)
						+ (1-a) * b * qtgui.qAlpha(topright)
						+ (1-a) * (1-b) * qtgui.qAlpha(bottomright) + .5 )

				alpha=int(alpha * scale * scale + .5)
				red=int(red * scale * scale + .5)
				green=int(green * scale * scale + .5)
				blue=int(blue * scale * scale + .5)

				if red > 255:
					red=255
				if green > 255:
					green=255
				if blue > 255:
					blue=255
				if alpha > 255:
					alpha=255

				outputimage.setPixel(x,y,qtgui.qRgba(red,green,blue,alpha))

		return outputimage

	# interpolate between two images that are the exact same size
	def interpolate(self,image1,image2,t):
		if not ( image1.width() == image2.width() and image1.width() == image2.width() ):
			print "Error: interploate function passed non compatable images"
			return image1

		if t < 0 or t > 1:
			print "Error: interploate function passed bad t value:", t
			raise Exception, "interploate passed bad t value"
			return image1

		width=image1.width()
		height=image1.height()

		outputimage=qtgui.QImage(width,height,qtgui.QImage.Format_ARGB32_Premultiplied)

		for x in range(width):
			for y in range(height):
				image1pixel = image1.pixel(x,y)
				image2pixel = image2.pixel(x,y)

				red = int((1-t) * qtgui.qRed(image1pixel) + t * qtgui.qRed(image1pixel) + .5 )
				green = int((1-t) * qtgui.qGreen(image1pixel) + t * qtgui.qGreen(image1pixel) + .5 )
				blue = int((1-t) * qtgui.qBlue(image1pixel) + t * qtgui.qBlue(image1pixel) + .5 )
				alpha = int((1-t) * qtgui.qAlpha(image1pixel) + t * qtgui.qAlpha(image1pixel) + .5 )

				if red > 255:
					red=255
				if green > 255:
					green=255
				if blue > 255:
					blue=255
				if alpha > 255:
					alpha=255

				outputimage.setPixel(x,y,qtgui.qRgba(red,green,blue,alpha))

		return outputimage

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
		shape=BrushShapes.ellipse

		# only support one brush shape right now
		if shape==BrushShapes.ellipse:
			self.makeEllipseBrush()

		self.makeScaledBrushes()

		self.singlepixelbrush=qtgui.QImage(1,1,qtgui.QImage.Format_ARGB32_Premultiplied)
		self.singlepixelbrush.setPixel(0,0,self.fgcolor.rgba())

	# make list of pre-scaled brushes
	def makeScaledBrushes(self):
		self.scaledbrushes=[]

		width=self.fullsizedbrush.width() * MAXIMUM_SCALE
		height=self.fullsizedbrush.height() * MAXIMUM_SCALE

		while True:
			if width >= self.fullsizedbrush.width() and height >= self.fullsizedbrush.height():
				scaledImage=self.scaleImage(self.fullsizedbrush,width,height)
			# scale down using previous one once below 1:1
			else:
				scaledImage=self.scaleImage(scaledImage,width,height)

			xscale = float(width) / self.fullsizedbrush.width()
			yscale = float(height) / self.fullsizedbrush.height()
			scale=xscale

			self.scaledbrushes.append((scaledImage,xscale,yscale))

			# never scale by less than 1/2
			width = int ((width + 1) / 2)
			height = int((height + 1) / 2)

			# break before we get to a single pixel brush
			if width==1 and height==1:
				break

	def makeEllipseBrush(self):
		self.width=self.options["maxdiameter"]
		self.height=self.options["maxdiameter"]
		fgr=self.fgcolor.red()
		fgg=self.fgcolor.green()
		fgb=self.fgcolor.blue()

		self.fullsizedbrush=qtgui.QImage(self.width,self.height,qtgui.QImage.Format_ARGB32_Premultiplied)

		for i in range(self.width):
			for j in range(self.height):
				v=self.ellipseBrushFadeAt(i,j)
				self.fullsizedbrush.setPixel(i,j,qtgui.qRgba(int(fgr*v),int(fgg*v),int(fgb*v),int(v*255)))

	def ellipseBrushFadeAt(self,x,y):
		m_xcentre = self.width/2.0
		m_ycentre = self.height/2.0
		m_xcoef = 2.0/self.width
		m_ycoef = 2.0/self.height

		if self.options["fade horizontal"] == 0:
			m_xfadecoef = 1.0
		else:
			m_xfadecoef = 1.0 / self.options["fade horizontal"] 

		if self.options["fade vertical"] == 0:
			m_yfadecoef = 1.0
		else:
			m_yfadecoef = 1.0 / self.options["fade vertical"] 

		xr = (x - m_xcentre) + .5
		yr = (y - m_ycentre) + .5

		n = norme(xr*m_xcoef,yr*m_ycoef)

		# case 1:
		if n > 1:
			return 0

		# case 2:
		normefade = norme(xr * m_xfadecoef, yr * m_yfadecoef)
		if normefade > 1:
			if xr == 0:
				xle = 0
				if yr > 0:
					yle=1.0/m_ycoef
				else:
					yle=-1.0/m_ycoef

			else:
				c = yr / float(xr)
				xle = math.sqrt(1. / norme(m_xcoef, c * m_ycoef ))
				if xr <= 0:
					xle = -xle
				yle = xle*c

				normefadelimite = norme(xle * m_xfadecoef, yle * m_yfadecoef)
				return 1.-(normefade - 1) / (normefadelimite - 1 )

		# case 3
		return 1

	# use subpixel adjustments to shift image and scale it too if needed
	def scaleShiftImage(self,srcbrush,scale,subpixelx,subpixely):
		#print "scaleShiftImage called with subpixels:", subpixelx, subpixely
		#print "scaleShiftImage called with scale:", scale
		# add one pixel for subpixel adjustments
		dstwidth=math.ceil(scale*self.fullsizedbrush.width())+1
		dstheight=math.ceil(scale*self.fullsizedbrush.height())+1

		dstimage=qtgui.QImage(dstwidth,dstheight,qtgui.QImage.Format_ARGB32_Premultiplied)

		srcimage=srcbrush[0]
		#print "performing scale and shift on image:"
		#printImage(srcimage)

		xscale=srcbrush[1]/scale
		yscale=srcbrush[2]/scale

		#print "xscale, yscale:",xscale,yscale

		srcwidth=srcimage.width()
		srcheight=srcimage.height()

		srccenterx=srcwidth/2.
		srccentery=srcheight/2.

		dstcenterx=dstwidth/2.
		dstcentery=dstheight/2.

		for dsty in range(int(dstheight)):
			for dstx in range(int(dstwidth)):
				# distance from x to center of dst image x
				#distx = dstx - dstcenterx + .5
				#srcx = (distx * scale) + srccenterx - subpixelx

				#disty = dsty - dstcentery + .5
				#srcy = (disty * scale) + srccentery - subpixely
				srcx = (dstx - subpixelx + .5) * xscale
				srcy = (dsty - subpixely + .5) * yscale

				srcx -= .5
				srcy -= .5

				# simple integer truncation will not be suitable here because it does the wrong thing for negative numbers
				leftx = int(math.floor(srcx))
				xinterp = srcx - leftx

				topy = int(math.floor(srcy))
				yinterp = srcy - topy

				if leftx >= 0 and leftx < srcwidth and topy >= 0 and topy < srcheight:
					topleft = srcimage.pixel(leftx,topy)
				else:
					topleft = qtgui.qRgba(0,0,0,0)

				if leftx >= 0 and leftx < srcwidth and topy + 1 >= 0 and topy + 1 < srcheight:
					bottomleft = srcimage.pixel(leftx,topy+1)
				else:
					bottomleft = qtgui.qRgba(0,0,0,0)

				if leftx + 1 >= 0 and leftx + 1 < srcwidth and topy >= 0 and topy < srcheight:
					topright = srcimage.pixel(leftx+1,topy)
				else:
					topright = qtgui.qRgba(0,0,0,0)

				if leftx + 1 >= 0 and leftx + 1 < srcwidth and topy + 1 >= 0 and topy + 1 < srcheight:
					bottomright = srcimage.pixel(leftx+1,topy+1)
				else:
					bottomright = qtgui.qRgba(0,0,0,0)

				a = 1.-xinterp
				b = 1.-yinterp

				red=(a*b*qtgui.qRed(topleft)
						+ a * (1-b) * qtgui.qRed(bottomleft)
						+ (1-a) * b * qtgui.qRed(topright)
						+ (1-a) * (1-b) * qtgui.qRed(bottomright) + .5 )
				green=(a*b*qtgui.qGreen(topleft)
						+ a * (1-b) * qtgui.qGreen(bottomleft)
						+ (1-a) * b * qtgui.qGreen(topright)
						+ (1-a) * (1-b) *qtgui.qGreen(bottomright) + .5 )
				blue=(a*b*qtgui.qBlue(topleft)
						+ a * (1-b) * qtgui.qBlue(bottomleft)
						+ (1-a) * b * qtgui.qBlue(topright)
						+ (1-a) * (1-b) * qtgui.qBlue(bottomright) + .5 )
				alpha=(a*b*qtgui.qAlpha(topleft)
						+ a * (1-b) * qtgui.qAlpha(bottomleft)
						+ (1-a) * b * qtgui.qAlpha(topright)
						+ (1-a) * (1-b) * qtgui.qAlpha(bottomright) + .5 )

				if red > 255:
					red=255
				if green > 255:
					green=255
				if blue > 255:
					blue=255
				if alpha > 255:
					alpha=255

				dstimage.setPixel(dstx,dsty,qtgui.qRgba(red,green,blue,alpha))

		#print "Shifted into:"
		#printImage(dstimage)
		return dstimage

	def scaleImage(self,brushimage,width,height):
		srcwidth=brushimage.width()
		srcheight=brushimage.height()

		if srcwidth==width and srcheight==height:
			return brushimage

		xscale=float(srcwidth)/width
		yscale=float(srcheight)/height

		#if(xScale > 2 or yScale > 2 or xScale < 1 or yScale < 1)
		# do this every time for now, I'll make special cases later if needed
		scaledimage=brushimage.scaled(width,height,qtcore.Qt.IgnoreAspectRatio,qtcore.Qt.SmoothTransformation)

		return scaledimage
