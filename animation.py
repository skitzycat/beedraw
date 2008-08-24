from base64 import b64decode
import time
from beeglobals import *
from beetypes import *
from beeutil import *
from sketchlog import SketchLogWriter

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui
import PyQt4.QtXml as qtxml

class XmlToQueueEventsConverter:
	def __init__(self,device,window,stepdelay,type=ThreadTypes.animation,id=0):
		if device:
			self.xml=qtxml.QXmlStreamReader(device)
		else:
			self.xml=qtxml.QXmlStreamReader()
		self.id=id
		self.window=window
		self.type=type
		self.inrawevent=False
		self.stepdelay=stepdelay
		self.keymap={}

		if type==ThreadTypes.animation:
			self.layertype=LayerTypes.animation
		else:
			self.layertype=LayerTypes.network

	def translateKey(self,key):
		if self.type!=ThreadTypes.animation:
			return key
		return self.keymap[key]

	def addKeyTranslation(self,key,dockey):
		if self.type!=ThreadTypes.animation:
			self.keymap[key]=key
		else:
			self.keymap[key]=dockey

	def read(self):
		while not self.xml.atEnd():
			tokentype=self.xml.readNext()
			if tokentype==qtxml.QXmlStreamReader.StartElement:
				self.processStartElement()
			elif tokentype==qtxml.QXmlStreamReader.EndElement:
				self.processEndElement()
			elif tokentype==qtxml.QXmlStreamReader.Characters:
				self.processCharacterData()

		# if it's an error that might actually be a problem then print it out
		if self.xml.hasError() and self.xml.error() != qtxml.QXmlStreamReader.PrematureEndOfDocumentError:
				print "error while parsing XML:", self.xml.errorString()

	def processStartElement(self):
		name=self.xml.name()
		attrs=self.xml.attributes()

		if name == 'createdoc':
			(width,ok)=attrs.value('width').toString().toInt()
			(height,ok)=attrs.value('height').toString().toInt()
			self.window.addSetCanvasSizeRequestToQueue(width,height,type)

		elif name == 'addlayer':
			if self.type==ThreadTypes.server:
				# create our own key data in this case
				key=self.window.nextLayerKey()
			else:
				(key,ok)=attrs.value("key").toString().toInt()

			(pos,ok)=attrs.value("position").toString().toInt()

			if self.type==ThreadTypes.server:
				owner=self.id
			else:
				(owner,ok)=attrs.value("owner").toString().toInt()

			if self.type!=ThreadTypes.animation:
				dockey=key
			# if it's an animation I need to map the key to a local one
			else:
				dockey=self.window.nextLayerKey()

			self.addKeyTranslation(key,dockey)

			self.window.addInsertLayerEventToQueue(pos,dockey,self.type,owner=owner)

		elif name == 'sublayer':
			(key,ok)=attrs.value("index").toString().toInt()
			self.window.addRemoveLayerRequestToQueue(key,type)

		elif name == 'movelayer':
			(change,ok)=attrs.value("change").toString().toInt()
			(index,ok)=attrs.value("index").toString().toInt()
			if change==1:
				self.window.addLayerUpToQueue(index,type)
			else:
				self.window.addLayerDownToQueue(index,type)

		elif name == 'layeralpha':
			(key,ok)=attrs.value("key").string.toInt()
			self.window.addOpacityChangeToQueue(key,attrs.value("alpha").toString().toFloat(),type)

		elif name == 'layermode':
			time.sleep(self.stepdelay)
			(index,ok)=attrs.value('index').toString().toInt()
			mode=BlendTranslations.intToMode(attrs.value('mode').toString().toInt())
			self.window.addBlendModeChangeToQueue(self.translateKey(index),mode,type)

		elif name == 'toolevent':
			self.strokestart=False
			toolname="%s" % attrs.value('name').toString()
			(layerkey,ok)=attrs.value('layerkey').toString().toInt()
			self.curlayer=self.translateKey(layerkey)

			tool=self.window.master.getToolClassByName(toolname.strip())

			# print error if we can't find the tool
			if tool == None:
				print "Error, couldn't find tool with name: ", toolname
				return

			self.curtool=tool.setupTool(self.window)
			self.curtool.layerkey=self.curlayer

		elif name == 'fgcolor':
			(r,ok)=attrs.value('r').toString().toInt()
			(g,ok)=attrs.value('g').toString().toInt()
			(b,ok)=attrs.value('b').toString().toInt()
			self.curtool.fgcolor=qtgui.QColor(r,g,b)
		elif name == 'bgcolor':
			(r,ok)=attrs.value('r').toString().toInt()
			(g,ok)=attrs.value('g').toString().toInt()
			(b,ok)=attrs.value('b').toString().toInt()
			self.curtool.bgcolor=qtgui.QColor(r,g,b)
		elif name == 'clippath':
			self.clippoints=[]
		elif name == 'polypoint':
			(x,ok)=attrs.value('x').toString().toInt()
			(y,ok)=attrs.value('y').toString().toInt()
			self.clippoints.append(qtcore.QPointF(x,y))
		elif name == 'toolparam':
			(value,ok)=attrs.value('value').toString().toInt()
			self.curtool.setOption("%s" % attrs.value('name').toString(),value)
		elif name == 'rawevent':
			self.inrawevent=True
			self.raweventargs=[]
			(self.x,ok)=attrs.value('x').toString().toInt()
			(self.y,ok)=attrs.value('y').toString().toInt()
			(layerkey,ok)=attrs.value('layerkey').toString().toInt()
			self.layerkey=self.translateKey(layerkey)
			self.rawstring=self.xml.readElementText()

			data=qtcore.QByteArray()
			data=data.append(self.rawstring)
			data=qtcore.QByteArray.fromBase64(data)
			data=qtcore.qUncompress(data)

			image=qtgui.QImage()
			image.loadFromData(data,"PNG")

			self.window.addRawEventToQueue(self.layerkey,image,self.x,self.y,None,type)

		elif name == 'point':
			time.sleep(self.stepdelay)
			(x,ok)=attrs.value('x').toString().toFloat()
			(y,ok)=attrs.value('y').toString().toFloat()
			#print "found point element for", x, y
			self.lastx=x
			self.lasty=y
			(pressure,ok)=attrs.value('pressure').toString().toFloat()
			if self.strokestart == False:
				#print "Adding start tool event to queue on layer", self.curlayer
				self.window.addPenDownToQueue(x,y,pressure,self.curlayer,self.curtool,type)
				self.strokestart=True
			else:
				#print "Adding tool motion event to queue on layer", self.curlayer
				self.window.addPenMotionToQueue(x,y,pressure,self.curlayer,type)

	def processEndElement(self):
		name=self.xml.name()
		if name == 'toolevent':
			#print "Adding end tool event to queue on layer", self.curlayer
			self.window.addPenUpToQueue(self.curlayer,self.lastx,self.lasty,type)
			self.curtool=None
		elif name == 'rawevent':
			return
			self.inrawevent=False

			# convert data out of base 64 then uncompress
			data=qtcore.QByteArray()
			print "%s" % self.rawstring
			data=data.append(self.rawstring)
			data=qtcore.QByteArray.fromBase64(data)
			data=qtcore.qUncompress(data)

			image=qtgui.QImage()
			image.loadFromData(data,"PNG")

			self.window.addRawEventToQueue(self.layerkey,image,self.x,self.y,None,type)
		elif name == 'clippath':
			poly=qtgui.QPolygonF(self.clippoints)
			self.curtool.clippath=qtgui.QPainterPath()
			self.curtool.clippath.addPolygon(poly)

	def processCharacterData(self):
		pass

# thread for playing local animations out of a file
class PlayBackAnimation (qtcore.QThread):
	def __init__(self,window,filename,stepdelay=.05):
		qtcore.QThread.__init__(self)
		self.window=window
		self.filename=filename
		self.stepdelay=stepdelay

	def run(self):
		f=qtcore.QFile(self.filename)
		f.open(qtcore.QIODevice.ReadOnly)
		parser=XmlToQueueEventsConverter(f,self.window,self.stepdelay)
		parser.read()
		f.close()

class NetworkListenerThread (qtcore.QThread):
	def __init__(self,window,username,password,host,port):
		qtcore.QThread.__init__(self)
		self.window=window
		self.username=username
		self.password=password
		self.host=host
		self.port=port

	def run(self):
		print "attempting to get socket:"
		# setup initial connection
		self.socket,width,height,id=getServerConnection(self.username,self.password,self.host,self.port)

		# if we failed to get a socket then destroy the window and exit
		if not self.socket:
			print "failed to get socket connection"
			self.window.cleanUp()
			self.window.destroy()
			return

		# get ready for next contact from server
		self.parser=XmlToQueueEventsConverter(None,self.window,0,type=ThreadTypes.network)
		qtcore.QObject.connect(self.socket, qtcore.SIGNAL("readyRead()"), self.readyRead)
		qtcore.QObject.connect(self.socket, qtcore.SIGNAL("disconnected()"), self.disconnected)

		print "got socket connection"
		self.window.remoteid=id
		sendingthread=NetworkWriterThread(self.window,self.socket)
		self.window.sendingthread=sendingthread
		print "created thread, about to start sending thread"
		sendingthread.start()

		# enter control loop
		self.exec_()

	# what to do when a disconnected signal is recieved
	def disconnected(self):
		print "disconnected from server"
		self.window.switchAllLayersToLocal()
		self.exit()
		return

	def readyRead(self):
		while self.socket.bytesAvailable():
			data=self.socket.read(1024)
			print "got animation data from socket: %s" % qtcore.QString(data)
			self.parser.xml.addData(data)
			self.parser.read()

class NetworkWriterThread (qtcore.QThread):
	def __init__(self,window,socket):
		qtcore.QThread.__init__(self)
		self.socket=socket
		self.gen=SketchLogWriter(self.socket)

		self.window=window
		self.queue=window.remoteoutputqueue

	def run(self):
		while 1:
			print "attempting to get item from queue"
			command=self.queue.get()
			if command[0]==DrawingCommandTypes.quit:
				return
			self.gen.logCommand(command)
