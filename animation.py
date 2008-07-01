from base64 import b64decode
import xml
from xml.sax import ContentHandler, make_parser
import time
from beeglobals import *
from beetypes import *
from beeutil import *

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui

class LogContentHandler(xml.sax.ContentHandler):
	def __init__(self,window,stepdelay=0,type=LayerTypes.animation):
		self.inrawevent=False
		self.run=True
		self.stepdelay=stepdelay
		self.window=window
		self.type=type
		# keyed on what the layer in in the log is, value is what the key in the document is
		self.keymap={}

	def translateKey(self,key):
		if self.type!=LayerTypes.animation:
			return key
		return self.keymap[key]

	def addKeyTranslation(self,key,dockey):
		if self.type!=LayerTypes.animation:
			self.keymap[key]=key
			return
		self.keymap[key]=dockey

	def startElement(self, name, attrs):
		if name == 'createdoc':
			width=int(attrs.get('width'))
			height=int(attrs.get('height'))
			self.window.addSetCanvasSizeRequestToQueue(width,height,ThreadTypes.remote)

		elif name == 'addlayer':
			pos=int(attrs.get("position"))
			key=int(attrs.get("key"))

			dockey=self.window.addInsertLayerEventToQueue(pos,LayerTypes.animation,"animation",ThreadTypes.remote)
			self.addKeyTranslation(key,dockey)

		elif name == 'sublayer':
			self.window.addRemoveLayerRequestToQueue(int(attrs.get("key")),ThreadTypes.remote)

		elif name == 'movelayer':
			change=int(attrs.get("change"))
			if change==1:
				self.window.addLayerUpToQueue(int(attrs.get("index")),ThreadTypes.remote)
			else:
				self.window.addLayerDownToQueue(int(attrs.get("index")),ThreadTypes.remote)

		elif name == 'layeralpha':
			self.window.addOpacityChangeToQueue(int(attrs.get("key")),float(attrs.get("alpha")))

		elif name == 'layermode':
			time.sleep(self.stepdelay)
			index=int(attrs.get('index'))
			mode=BlendTranslations.intToMode(int(attrs.get('mode')))
			self.window.addBlendModeChangeToQueue(self.translateKey(index),mode,ThreadTypes.remote)

		elif name == 'toolevent':
			self.strokestart=False
			toolname=attrs.get('name')
			#self.curlayer=self.keymap[int(attrs.get('layerkey'))]
			self.curlayer=self.translateKey(int(attrs.get('layerkey')))

			tool=self.window.master.getToolClassByName(toolname.strip())

			# print error if we can't find the tool
			if tool == None:
				print "Error, couldn't find tool with name: ", toolname
				return

			self.curtool=tool.setupTool(self.window)
			self.curtool.layerkey=self.curlayer

		elif name == 'fgcolor':
			self.curtool.fgcolor=qtgui.QColor(int(attrs.get('r')),int(attrs.get('g')),int(attrs.get('b')))
		elif name == 'bgcolor':
			self.curtool.bgcolor=qtgui.QColor(int(attrs.get('r')),int(attrs.get('g')),int(attrs.get('b')))
		elif name == 'clippath':
			self.clippoints=[]
		elif name == 'polypoint':
			self.clippoints.append(qtcore.QPointF(int(attrs.get('x')),int(attrs.get('y'))))
		elif name == 'toolparam':
			self.curtool.setOption(attrs.get('name'),float(attrs.get('value')))
		elif name == 'rawevent':
			self.inrawevent=True
			self.rawstring=''
			self.raweventargs=[]
			self.x=int(attrs.get('x'))
			self.y=int(attrs.get('y'))
			#self.layerkey=self.keymap[int(attrs.get('layerkey'))]
			self.layerkey=self.translateKey(int(attrs.get('layerkey')))

		elif name == 'point':
			time.sleep(self.stepdelay)
			x=float(attrs.get('x'))
			y=float(attrs.get('y'))
			#print "found point element for", x, y
			self.lastx=x
			self.lasty=y
			pressure=float(attrs.get('pressure'))
			if self.strokestart == False:
				#print "Adding start tool event to queue on layer", self.curlayer
				self.window.addPenDownToQueue(x,y,pressure,self.curlayer,self.curtool,ThreadTypes.remote)
				self.strokestart=True
			else:
				#print "Adding tool motion event to queue on layer", self.curlayer
				self.window.addPenMotionToQueue(x,y,pressure,self.curlayer,ThreadTypes.remote)
	
	def endElement(self, name):
		if name == 'toolevent':
			#print "Adding end tool event to queue on layer", self.curlayer
			self.window.addPenUpToQueue(self.curlayer,self.lastx,self.lasty,ThreadTypes.remote)
			self.curtool=None
		elif name == 'rawevent':
			self.inrawevent=False

			# convert data out of base 64 then uncompress
			data=qtcore.QByteArray()
			data=data.append(qtcore.QString(self.rawstring))
			data=qtcore.QByteArray.fromBase64(data)
			data=qtcore.qUncompress(data)

			image=qtgui.QImage()
			image.loadFromData(data,"PNG")

			self.window.addRawEventToQueue(self.layerkey,image,self.x,self.y,None,ThreadTypes.remote)
		elif name == 'clippath':
			poly=qtgui.QPolygonF(self.clippoints)
			self.curtool.clippath=qtgui.QPainterPath()
			self.curtool.clippath.addPolygon(poly)

	def characters(self,content):
		if self.inrawevent:
			self.rawstring+=content

	def endDocument(self):
		# set all layers we created to be user layers now that animation is over
		for key in self.keymap.keys():
			layer=self.window.getLayerForKey(self.keymap[key])
			if layer:
				layer.type=LayerTypes.user
				layer.changeName("")

# thread for playing local animations out of a file
class PlayBackAnimation (qtcore.QThread):
	def __init__(self,window,filename,stepdelay=.05):
		qtcore.QThread.__init__(self)
		self.window=window
		self.filename=filename
		self.stepdelay=stepdelay

	def run(self):
		f=file(self.filename)
		handler=LogContentHandler(self.window,self.stepdelay)
		parser=xml.sax.make_parser()
		parser.setFeature(xml.sax.handler.feature_namespaces, 0)
		parser.setContentHandler(handler)
		parser.parse(f)
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
		# setup initial connection
		self.socket,width,height=getServerConnection(self.username,self.password,self.host,self.port)

		self.window.addToQueue

		# if is was set up correctly tell window to start the thread that sends out data
		if self.socket:
			self.window.sendingthread=NetworkWriterThread(self.window,socket)
			self.window.sendingthread.exec_()

		# if not tell window to exit and end thread
		else:
			self.window.remotedrawinthread=None
			self.window.cleanUp()
			return

		handler=LogContentHandler(self.window)
		parser=xml.sax.make_parser()
		parser.setFeature(xml.sax.handler.feature_namespaces, 0)
		parser.setContentHandler(handler)

		# listen for events and draw them as they come in
		while 1:
			if self.socket.waitForReadyRead(-1):
				curdata=self.socket.readAll()
				# convert to python string
				s='%s' % qtcore.QString(curdata).toAscii()

				parser.feed(s)

			else:
				print "Recieved socket error:", self.socket.error(), "when reading"
				parser.close()
				return

class NetworkWriterThread (qtcore.QThread):
	def __init__(self,socket,window):
		self.socket=socket
		self.gen=qtxml.QXmlStreamWriter(socket)

		self.gen.writeStartDocument()
		self.window=window
		self.queue=window.remoteoutputqueue

	def run(self):
		while 1:
			command=self.queue.get()
