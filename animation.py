from base64 import b64decode
import xml
from xml.sax import ContentHandler, make_parser
import time
from beeglobals import *
from beetypes import *
from beeutil import *
from sketchlog import SketchLogWriter

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui
import PyQt4.QtXml as qtxml

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
		print "attempting to get socket:"
		# setup initial connection
		self.socket,width,height=getServerConnection(self.username,self.password,self.host,self.port)

		#self.window.addToQueue()

		# if is was set up correctly tell window to start the thread that sends out data
		if self.socket:
			print "got socket connection"
			sendingthread=NetworkWriterThread(self.window,self.socket)
			self.window.sendingthread=sendingthread
			print "created thread, about to start thread"
			sendingthread.start()

		# if not tell window to exit and end thread
		else:
			print "failed to get socket connection"
			self.window.remotedrawinthread.quit()
			self.window.remotedrawinthread=None
			self.window.cleanUp()
			self.window.destroy()
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
