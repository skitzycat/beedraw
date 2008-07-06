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
	def __init__(self,device,window,stepdelay,type=ThreadTypes.animation):
		if device:
			self.xml=qtxml.QXmlStreamReader(device)
		else:
			self.xml=qtxml.QXmlStreamReader()
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
		if self.type!=ThreadTypes.user:
			return key
		return self.keymap[key]

	def addKeyTranslation(self,key,dockey):
		if self.type!=ThreadTypes.user:
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

		if self.xml.hasError():
			print "error while parsing XML:", self.xml.errorString()

		# set all layers we created to be user layers now that animation is over
		for key in self.keymap.keys():
			layer=self.window.getLayerForKey(self.keymap[key])
			if layer:
				layer.type=LayerTypes.user
				layer.changeName("")

	def processStartElement(self):
		name=self.xml.name()
		attrs=self.xml.attributes()

		if name == 'createdoc':
			(width,ok)=attrs.value('width').toString().toInt()
			(height,ok)=attrs.value('height').toString().toInt()
			self.window.addSetCanvasSizeRequestToQueue(width,height,type)

		elif name == 'addlayer':
			(pos,ok)=attrs.value("position").toString().toInt()
			(key,ok)=attrs.value("key").toString().toInt()

			dockey=self.window.addInsertLayerEventToQueue(pos,self.layertype,"animation",self.type)
			self.addKeyTranslation(key,dockey)

		elif name == 'sublayer':
			(key,ok)=attrs.value("key").string.toInt()
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
			self.curtool.setOption(attrs.value('name'),value)
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
		#if self.inrawevent:
		#	self.rawstring=self.xml.text()

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
		self.socket,width,height=getServerConnection(self.username,self.password,self.host,self.port)

		# if is was set up correctly tell window to start the thread that sends out data
		if self.socket:
			print "got socket connection"
			sendingthread=NetworkWriterThread(self.window,self.socket)
			self.window.sendingthread=sendingthread
			print "created thread, about to start sending thread"
			sendingthread.start()

		# if not tell window to exit and end thread
		else:
			print "failed to get socket connection"
			self.window.remotedrawinthread.quit()
			self.window.remotedrawinthread=None
			self.window.cleanUp()
			self.window.destroy()
			return

		parser=XmlToQueueEventsConverter(None,self.window,0,type=ThreadTypes.network)

		# listen for events and draw them as they come in
		while 1:
			if self.socket.waitForReadyRead(-1):
				data=self.socket.read(1024)
				parser.xml.feed(data)
				parser.read()

			# if error exit
			else:
				print "Recieved error:", self.socket.error(), "when reading from socket"
				#self.socket.write(qtcore.QByteArray("Authentication Failed"))
				return

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
			type=command[0]

			if type==DrawingCommandTypes.quit:
				return
			elif type==DrawingCommandTypes.nonlayer:
				self.sendNonLayerCommand(command)
			elif type==DrawingCommandTypes.layer:
				self.sendLayerCommand(command)
			elif type==DrawingCommandTypes.alllayer:
				self.sendAllLayerCommand(command)

	def sendNonLayerCommand(self,command):
		pass

	def sendLayerCommand(self,command):
		subtype=command[1]
		if subtype==LayerCommandTypes.alpha:
			pass

		elif subtype==LayerCommandTypes.mode:
			pass

		elif subtype==LayerCommandTypes.tool:
			self.gen.logToolEvent(tool)

		elif subtype==LayerCommandTypes.rawevent:
			pass

		else:
			print "unknown processLayerCommand subtype:", subtype

	def sendAllLayerCommand(self,command):
		subtype=command[1]
		if subtype==AllLayerCommandTypes.resize:
			pass

		elif subtype==AllLayerCommandTypes.scale:
			pass

		elif subtype==AllLayerCommandTypes.layerup:
			self.gen.logLayerMove(command[2],1)

		elif subtype==AllLayerCommandTypes.layerdown:
			self.gen.logLayerMove(command[2],-1)

		elif subtype==AllLayerCommandTypes.deletelayer:
			self.gen.logLayerSub(command[2])

		elif subtype==AllLayerCommandTypes.insertlayer:
			self.gen.logLayerAdd(0,0)
