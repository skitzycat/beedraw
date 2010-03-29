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
import PyQt4.QtNetwork as qtnet

from Queue import Queue

from beeapp import BeeApp
from beetypes import *

from PIL import ImageQt
import Image

from beeglobals import *
import math

from datetime import datetime

try:
	import NumPy as numpy
except:
	try:
		import numpy
	except:
		import Numeric as numpy

# print contents of image as integers representing each pixel
def printImage(image):
	for i in range(image.height()):
		for j in range(image.width()):
			curpix=image.pixel(j,i)
			#print curpix,
			print "%08x" % (curpix),
		print

def printPixmap(pixmap):
	printImage(pixmap.toImage())

# print contents of image within rect as integers representing each pixel
def printImageRect(image,rect):
	for i in range(rect.x(),rect.x()+rect.width()):
		for j in range(rect.y(),rect.y()+rect.height()):
			curpix=image.pixel(i,j)
			print "%08x" % (curpix),
		print

def printPixmapRect(pixmap,rect):
	printImageRect(pixmap.toImage(),rect)

# returns a list of coordinates for where to put points between coord1 and coord2
# coord1 will not be included in the list becuase it should have already been
# drawn to as part of the last command, but coord2 will always be the last item
# in the list, points will be bounded to the area of height and width
def getPointsPath(x1,y1,x2,y2,linestep,width,height,p1=1,p2=1):
	# start with a blank list
	path=[]

	lastpoint=(x1,y1)

	# calculate straight line distance between coords
	delta_x=x2-x1
	delta_y=y2-y1
	delta_p=p2-p1

	h=math.hypot(abs(delta_x),abs(delta_y))

	# calculate intermediate coords
	intermediate_points=numpy.arange(linestep,h,linestep)
	if len(intermediate_points)==0:
		return path
	pstep=delta_p/len(intermediate_points)
	newp=p1

	for point in intermediate_points:
		newx=x1+(delta_x*point/h)
		newy=y1+(delta_y*point/h)
		newp=newp+pstep

		# make sure coords fall in widht and height restrictions
		if newx>=0 and newx<width and newy>=0 and newy<height:
			# make sure we don't skip a point
			#if step==0 int(newx)!=int(lastpoint[0]) and int(newy)!=int(lastpoint[1]):
			#	print "skipped from point:", lastpoint, "to:", newx,newy
			# only add point if it was different from previous one
			#if int(newx)!=int(lastpoint[0]) or int(newy)!=int(lastpoint[1]):
			lastpoint=(newx,newy,newp)
			path.append(lastpoint)

	return path

def getSupportedWriteFileFormats():
	l=[]
	for format in qtgui.QImageWriter.supportedImageFormats():
		l.append(qtcore.QString(format))
	return l

def getSupportedReadFileFormats():
	l=[]
	for format in qtgui.QImageReader.supportedImageFormats():
		l.append(qtcore.QString(format))
	return l

def rectToTuple(rect):
	return (rect.x(),rect.y(),rect.width(),rect.height())

# get the bounding rect of a region of the intersection of the 2 rects
def rectIntersectBoundingRect(rect1,rect2):
	region=qtgui.QRegion(rect1)
	region=region.intersect(qtgui.QRegion(rect2))
	return region.boundingRect()

# a class to do the same thing as the QMutexLocker only for read write locks
class ReadWriteLocker:
	def __init__(self,lock,write=False):
		self.lock=lock
		self.locked=False
		self.relock(write)
	def unlock(self):
		if self.locked:
			self.locked=False
			self.lock.unlock()
	def relock(self,write=False):
		if not self.locked:
			self.locked=True
			if write:
				self.lock.lockForWrite()
			else:
				self.lock.lockForRead()
	def __del__(self):
		if self.locked:
			self.lock.unlock()

class BlendTranslations:
	map={
	qtcore.QString("Normal"):qtgui.QPainter.CompositionMode_SourceOver,
	qtcore.QString("Multiply"):qtgui.QPainter.CompositionMode_Multiply,
	qtcore.QString("Darken"):qtgui.QPainter.CompositionMode_Darken,
	qtcore.QString("Lighten"):qtgui.QPainter.CompositionMode_Lighten,
	qtcore.QString("Dodge"):qtgui.QPainter.CompositionMode_ColorDodge,
	qtcore.QString("Burn"):qtgui.QPainter.CompositionMode_ColorBurn,
	qtcore.QString("Difference"):qtgui.QPainter.CompositionMode_Difference
	}

	def nameToMode(name):
		if name in BlendTranslations.map:
			return BlendTranslations.map[name]
		print "warning, couldn't find mode for name:", name
		return None

	nameToMode=staticmethod(nameToMode)

	def modeToName(mode):
		for key in BlendTranslations.map.keys():
			if BlendTranslations.map[key]==mode:
				return key
		print "warning, couldn't find name for mode:", mode
		return None

	modeToName=staticmethod(modeToName)

	def intToMode(i):
		for key in BlendTranslations.map.keys():
			if BlendTranslations.map[key]==i:
				return BlendTranslations.map[key]

		print "warning, couldn't translate int to mode string:", i
		return None

	intToMode=staticmethod(intToMode)

	def getAllModeNames():
		l=[]
		for key in BlendTranslations.map.keys():
			l.append(key)
		return l

	getAllModeNames=staticmethod(getAllModeNames)

def getBlankCursor():
	image=qtgui.QPixmap(1,1)
	image.fill(qtgui.QColor(0,0,0,0))
	cursor=qtgui.QCursor(image)
	return cursor

# make sure point falls within bounds of QRect passed
def adjustPointToBounds(x,y,rect):
	if x<rect.x():
		x=rect.x()
	elif x>rect.x()+rect.width():
		x=rect.x()+rect.width()
	if y<rect.y():
		y=rect.y()
	elif y>rect.y()+rect.height():
		y=rect.y()+rect.height()

	return x,y

# return the closest rectangle to small rectangle that fits completely inside the big rectangle
def snapRectToRect(bigrect,smallrect):
	if bigrect.width()<smallrect.width() or bigrect.height()<smallrect.height():
		print "ERROR: first argument should be larger in both dimensions"
		return None

	print "snapRectToRect called with:"
	print "bigger rect:", rectToTuple(bigrect)
	print "small  rect:", rectToTuple(smallrect)

	newrect=qtcore.QRect(smallrect)
	if newrect.x() < bigrect.x():
		print "found that x value is too small"
		print "translating by:", bigrect.x()-newrect.x()
		newrect.translate(int(bigrect.x()-newrect.x()),0)
	elif newrect.x()+newrect.width() > bigrect.x()+bigrect.width():
		newrect.translate(bigrect.x()+bigrect.width()-newrect.width()-newrect.x(),0)

	#if newrect.y() < bigrect.y():
	#	newrect.setY(bigrect.y())
	#elif newrect.y()+newrect.height() > bigrect.y()+bigrect.height():
	#	newrect.setY(bigrect.y()+bigrect.height()-newrect.height())

	print "return value:", rectToTuple(newrect)

	return newrect

# gets passed 2 QColor objects and similarity if colors are close enough according to similarity return true, otherwise return false.
def compareColors(color1,color2,similarity):
	rdiff=abs(color1.red()-color2.red())
	gdiff=abs(color1.green()-color2.green())
	bdiff=abs(color1.blue()-color2.blue())
	adiff=abs(color1.alpha()-color2.alpha())

	if similarity >= max([rdiff,gdiff,bdiff,adiff]):
		return True
	return False

# get path representing the outline of all pixels in a continuous region of color similar to that of the one at x,y
# note that this must be run only from the GUI thread since it relies on using bitmaps
def getSimilarColorPath(image,x,y,similarity):
	x=int(x)
	y=int(y)
	width=image.width()
	height=image.height()

	retmap=qtgui.QBitmap(width,height)
	retmap.clear()

	pen=qtgui.QPen()
	pen.setWidth(1)
	painter=qtgui.QPainter(retmap)
	painter.drawPoint(x,y)

	# dictionary to keep track of points already in path
	inpath={}

	# queue of points to check to see if they are part of the region
	pointsqueue=[]

	# get starting color to compare everything to
	basecolor=qtgui.QColor()
	basecolor.setRgba(image.pixel(x,y))
	#print "base color:", basecolor.alpha(), basecolor.red(), basecolor.green(), basecolor.blue()

	# set up starting conditions
	inpath[(x,y)]=1
	pointsqueue.append((x-1,y))
	pointsqueue.append((x,y-1))
	pointsqueue.append((x+1,y))
	pointsqueue.append((x,y+1))

	while len(pointsqueue):
		curpoint=pointsqueue.pop()
		# if point is out of bounds for the image or already in the path just ignore it
		if curpoint[0]<0 or curpoint[0]>=width or curpoint[1]<0 or curpoint[1]>=height or curpoint in inpath:
			continue

		# if point needs to be added to path add surrounding points to queue to check
		curcolor=qtgui.QColor()
		curcolor.setRgba(image.pixel(curpoint[0],curpoint[1]))

		if compareColors(basecolor,curcolor,similarity):
			inpath[curpoint]=1
			#print "adding point to path:", curpoint
			painter.drawPoint(curpoint[0],curpoint[1])
			pointsqueue.append((curpoint[0]-1,curpoint[1]))
			pointsqueue.append((curpoint[0],curpoint[1]-1))
			pointsqueue.append((curpoint[0]+1,curpoint[1]))
			pointsqueue.append((curpoint[0],curpoint[1]+1))

	painter.end()

	retpath=qtgui.QPainterPath()

	for rect in qtgui.QRegion(retmap).rects():
		tmprect=qtcore.QRectF(rect)
		# fudge so they overlap a bit and we can merge them properly
		tmprect.adjust(-.00001,-.00001,.00002,.00002)
		tmppath=qtgui.QPainterPath()
		tmppath.addRect(tmprect)
		retpath=retpath.united(tmppath)

	#attempt to smooth out the path
	#retpath=retpath.united(retpath)

	#print "done finding selection area"
	return retpath

# calculate distance between two points
def distance2d(x1,y1,x2,y2):
	return math.sqrt(((x1-x2)*(x1-x2))+(y1-y2)*(y1-y2))

def norme(a,b):
	return (a*a)+(b*b)

def print_debug(s):
	if BEE_DEBUG:
		print s

# convert from PIL to QImage
def PILtoQImage(im):
	return ImageQt.ImageQt(im)

def printPILImage(im):
	pix=im.load()
	for i in range(im.size[0]):
		for j in range(im.size[1]):
			print pix[i,j],
		print

# scale a PIL image, the dx and dy values should only be between 0 and 1
# xscale and yscale should be between 1 and .5, because that is the only range in which billenar interpolation looks good
def scaleShiftPIL(im,dx,dy,newsizex,newsizey,xscale,yscale,resample=Image.AFFINE):
	#print "calling scaleShiftPIL with args:", dx,dy,newsizex,newsizey,xscale,yscale
	#print "on image:"
	#printPILImage(im)

	imb_width=im.size[0]+2
	imb_height=im.size[1]+2

	# add in clear border around image so sampling for interpolation works right
	bordered_image=im.transform((imb_width,imb_height),Image.NEAREST,(1,0,-1,0,1,-1))
	#print "bordered image:"
	#printPILImage(bordered_image)

	# this will center the image even if it doesn't snap to exactly a pixel boundary
	pixcenteradjx=((im.size[0]*xscale)%1)/2
	pixcenteradjy=((im.size[1]*yscale)%1)/2

	stampsizex=math.floor(im.size[0]*xscale)
	stampsizey=math.floor(im.size[1]*yscale)

	# adjustment to go from even to odd size or vise versa
	eoadjx=int(stampsizex)%2
	eoadjy=int(stampsizey)%2

	#pixcenteradjx+=eoadjx
	#pixcenteradjy+=eoadjy

	# this will make the image centered even if it is more than a pixel smaller than the final area
	#print "newsizex, stampsizex:", newsizex, stampsizex
	stampcenteradjx=(newsizex-stampsizex)/2.
	stampcenteradjy=(newsizey-stampsizey)/2.

	pixcenteradjx-=stampcenteradjx
	pixcenteradjy-=stampcenteradjy

	#print "pix adjustments:", pixcenteradjx, pixcenteradjy

	trans=(1/xscale,0,1+((.5-dx+pixcenteradjx)*(1/xscale)),0,1/yscale,1+((.5-dy+pixcenteradjy)*(1/yscale)))

	#print "transform:", trans

	newim=bordered_image.transform((newsizex,newsizey),resample,trans,Image.BILINEAR)

	#print "producing image:"
	#printPILImage(newim)
	return newim

# debugging function to see how the affine translation is working
def translatePoint(x,y,trans):
	a,b,c,d,e,f=trans
	return ( (a*x) + (b*y) + c, (d*x) + (e*y) + f )

def getCurSelectionModType():
	modkeys=BeeApp().app.keyboardModifiers()

	if modkeys==qtcore.Qt.ShiftModifier:
		return SelectionModTypes.add
	elif modkeys==qtcore.Qt.ControlModifier:
		return SelectionModTypes.subtract
	elif modkeys==qtcore.Qt.ControlModifier|qtcore.Qt.ShiftModifier:
		return SelectionModTypes.intersect

	return SelectionModTypes.new

def getTimeString():
	now=datetime.now()
	returnstring="%d-%002d-%002d %002d-%002d-%002d-%d" % ( now.year, now.month, now.day, now.hour, now.minute, now.second, now.microsecond )
	return returnstring

# takes constants from 2 line formulas, of the form a1x + b1y = d1 and a2x + b2y = d2
def findLineIntersection(a1,b1,d1,a2,b2,d2):
	if a1*b2 - a2*b1 == 0 or a1*b2 - a2*b1 == 0:
		print "ERROR parrallel lines:"
		print "x *", a1, "+ y *", b1, "=", d1
		print "x *", a2, "+ y *", b2, "=", d2
		return None, None
	x=(b2*d1 - b1*d2)/(a1*b2 - a2*b1)
	y=(a1*d2 - a2*d1)/(a1*b2 - a2*b1)
	return x,y

# return true if passed value are of the same sign (both positive, both negative or both 0)
def sameSign(a,b):
	if a*b > 0:
		return True
	elif a == 0 and b == 0:
		return True
	return False

def replaceWidget(oldwidget,newwidget):
	""" replace one widget with another """
	parent=oldwidget.parentWidget()

	index=parent.layout().indexOf(oldwidget)
	parent.layout().removeWidget(oldwidget)
	oldwidget.hide()
	parent.layout().insertWidget(index,newwidget)
	newwidget.show()

def PILcomposite(baseim,newim,pos,comptype,mask=None):
	if newim.size==baseim.size and pos==(0,0):
		return compfunc(basim,newim)

	topim=newim.copy()

	if pos[0]<0 or pos[1]<0:
		topim=topim.crop((abs(min(pos[0],0)),abs(min(pos[1],0)),topim.size[0],topim.size[1]))
		pos=((max(pos[0],0)),max(pos[1],0))

	if topim.size[0]>baseim.size[0] or topim.size[1]>baseim.size[1]:
		topim=topim.crop((0,0,min(topim.size[0],baseim.size[0]),min(topim.size[1],baseim.size[1])))

	baseswatch=baseim.crop((pos[0],pos[1],newim.size[0]+pos[0],newim.size[1]+pos[1]))

	if comptype==ImageCombineTypes.composite:
		newswatch=ImageChops.composite(baseswatch,topim,None)
	elif newswatch==ImageCombineTypes.darkest:
		newswatch=ImageChops.darker(baseswatch,topim)

	baseim.paste(newswatch,box=pos,mask=mask)

def requestDisplayMessage(type,title,message,destination=None):
	if not destination:
		destination=BeeApp().master

	event=DisplayMessageEvent(type,title,message)
	BeeApp().app.postEvent(destination,event)
	print "requesting to display message"

class ThreadNotifierQueue(Queue,qtcore.QObject):
	__pyqtSignals__ = ("datainqueue()")
	def __init__(self,parent=None,maxsize=0):
		qtcore.QObject.__init__(self,parent)
		Queue.__init__(self,parent)
	def _put(self,item):
		Queue._put(self,item)
		print "emmiting signal"
		self.emit(qtcore.SIGNAL("datainqueue()"))
	def _get(self):
		Queue._get(self)
		if self._qsize():
			self.emit(qtcore.SIGNAL("datainqueue()"))

	def connectNotify(self,signal):
		print "signal connected to Queue:", signal
