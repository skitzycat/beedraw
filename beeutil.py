#!/usr/bin/env python

import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore
import PyQt4.QtNetwork as qtnet

from beeglobals import *
import math

try:
	import NumPy as numpy
except:
	try:
		import numpy
	except:
		import Numeric as numpy

# print contents of image as integers representing each pixel
def printImage(image):
	for i in range(image.width()):
		for j in range(image.height()):
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
def getPointsPath(x1,y1,x2,y2,step,width,height,p1=1,p2=1):
	# start with empty path
	path=[]

	lastpoint=(-1,-1)

	# calculate straight line distance between coords
	delta_x=x2-x1
	delta_y=y2-y1
	delta_p=p2-p1
	h=math.hypot(abs(delta_x),abs(delta_y))

	# if distance between is too small, just return coord 2
	if h < step*2:
		path.append((x2,y2,p2))
		return path

	# calculate intermediate coords
	intermediate_points=numpy.arange(step,h,step)
	for point in intermediate_points:
		newx=int(x1+(delta_x*point/h))
		newy=int(y1+(delta_y*point/h))
		newp=p1+(delta_p*point/h)
		# make sure coords fall in widht and height restrictions
		if newx>=0 and newx<width and newy>=0 and newy<height:
			# only add point if it was different from previous one
			if newx!=lastpoint[0] or newy!=lastpoint[1]:
				lastpoint=(newx,newy,newp)
				path.append(lastpoint)

	if x2>=0 and x2<width and y2>=0 and y2<height:
		path.append((x2,y2,p2))

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
		if BlendTranslations.map.has_key(name):
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

# connect to host, authticate and get inital size of canvas
def getServerConnection(username,password,host,port):
	socket=qtnet.QTcpSocket()

	socket.connectToHost(host,port)
	print "waiting for socket connection:"
	connected=socket.waitForConnected()
	print "finished waiting for socket connection"

	# return error if we couldn't get a connection after 30 seconds
	if not connected:
		print "Error: could not connect to server"
		#qtgui.QMessageBox(qtgui.QMessageBox.Information,"Connection Error","Failed to connect to server",qtgui.QMessageBox.Ok).exec_()
		return None, None, None, None

	authrequest=qtcore.QByteArray()
	authrequest=authrequest.append("%s\n%s\n%s\n" % (username,password,PROTOCOL_VERSION))
	# send authtication info
	socket.write(authrequest)

	sizestring=qtcore.QString()

	# wait for response
	while sizestring.count('\n')<2 and len(sizestring)<100:
		if socket.waitForReadyRead(-1):
			data=socket.read(100)
			print "got authentication answer: %s" % qtcore.QString(data)
			sizestring.append(data)

		# if error exit
		else:
			qtgui.QMessageBox(qtgui.QMessageBox.Information,"Authentication Error","Wrong password",qtgui.QMessageBox.Ok).exec_()
			return None, None, None, None

	# if we get here we have a response that probably wasn't a disconnect
	sizelist=sizestring.split('\n')
	width,ok=sizelist[0].toInt()
	height,ok=sizelist[1].toInt()
	id,ok=sizelist[2].toInt()

	return socket,width,height,id
