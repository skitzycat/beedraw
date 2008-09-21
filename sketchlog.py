import PyQt4.QtCore as qtcore
import PyQt4.QtXml as qtxml
from beetypes import *

class SketchLogWriter:
	def __init__(self, output):
		self.output=output

		self.log=qtxml.QXmlStreamWriter(output)

		# mutex so we don't write to file from mulitple sources at once
		self.mutex=qtcore.QMutex()

		self.log.writeStartDocument()

		# add parent element
		self.log.writeStartElement('sketchlog')

	def logCommand(self,command):
		type=command[0]

		if type==DrawingCommandTypes.nonlayer:
			self.logNonLayerCommand(command)

		elif type==DrawingCommandTypes.layer:
			self.logLayerCommand(command)

		elif type==DrawingCommandTypes.alllayer:
			self.logAllLayerCommand(command)

		elif type==DrawingCommandTypes.networkcontrol:
			self.logNetworkControl(command)

		bytestowrite=self.output.bytesToWrite()
		while self.output.bytesToWrite()>0:
			self.output.flush()
			bytestowrite=self.output.bytesToWrite()
		self.output.flush()

	def logNonLayerCommand(self,command):
		subtype=command[1]
		if subtype==NonLayerCommandTypes.startlog:
			pass

		elif subtype==NonLayerCommandTypes.endlog:
			pass

		elif subtype==NonLayerCommandTypes.undo:
			pass

		elif subtype==NonLayerCommandTypes.redo:
			pass

	def logLayerCommand(self,command):
		subtype=command[1]
		layer=command[2]
		if subtype==LayerCommandTypes.alpha:
			self.logLayerAlphaChange(layer,command[3])

		elif subtype==LayerCommandTypes.mode:
			self.logLayerModeChange(layer,command[3])

		elif subtype==LayerCommandTypes.rawevent:
			self.logRawEvent(command[3],command[4],layer,command[5],command[6])

		elif subtype==LayerCommandTypes.tool:
			self.logToolEvent(command[3])

		else:
			print "WARNING: don't know how to log layer command type:", subtype

	def logAllLayerCommand(self,command):
		subtype=command[1]
		if subtype==AllLayerCommandTypes.resize:
			pass

		elif subtype==AllLayerCommandTypes.scale:
			pass

		elif subtype==AllLayerCommandTypes.layerup:
			self.logLayerMove(command[2],1)

		elif subtype==AllLayerCommandTypes.layerdown:
			self.logLayerMove(command[2],-1)

		elif subtype==AllLayerCommandTypes.deletelayer:
			self.logLayerSub(command[2])

		elif subtype==AllLayerCommandTypes.insertlayer:
			self.logLayerAdd(command[3], command[2], command[4])

	def logNetworkControl(self,command):
		subtype=command[1]
		if subtype==NetworkControlCommandTypes.resyncrequest:
			self.logResyncRequest()

		elif subtype==NetworkControlCommandTypes.resyncstart:
			self.logResyncStart()

	def startEvent(self):
		self.log.writeStartElement('event')

	def endEvent(self):
		self.log.writeEndElement()
		#self.output.flush()

	def logLayerAdd(self, position, key, owner=0):
		lock=qtcore.QMutexLocker(self.mutex)
		self.startEvent()

		# start layer event
		self.log.writeStartElement('layerevent')

		# start addlayer event
		self.log.writeStartElement('addlayer')
		self.log.writeAttribute('position',str(position))
		self.log.writeAttribute('key',str(key))
		self.log.writeAttribute('owner',str(owner))

		# end addlayer event
		self.log.writeEndElement()

		# end layer event
		self.log.writeEndElement()

		self.endEvent()

	def logLayerSub(self, index):
		lock=qtcore.QMutexLocker(self.mutex)
		self.startEvent()

		# start layer event
		self.log.writeStartElement('layerevent')

		# start sublayer event
		self.log.writeStartElement('sublayer')
		self.log.writeAttribute('index',str(index))

		# end sublayer event
		self.log.writeEndElement()

		# end layer event
		self.log.writeEndElement()

		self.endEvent()

	def logLayerModeChange(self, index, mode):
		lock=qtcore.QMutexLocker(self.mutex)
		self.startEvent()

		# start layer event
		self.log.writeStartElement('layerevent')

		self.log.writeStartElement('layermode')
		self.log.writeAttribute('index',str(index))
		self.log.writeAttribute('mode',str(mode))

		# end sublayer event
		self.log.writeEndElement()

		# end layer event
		self.log.writeEndElement()

		self.endEvent()

	def logLayerAlphaChange(self, key, alpha):
		lock=qtcore.QMutexLocker(self.mutex)
		self.startEvent()

		# start layer event
		self.log.writeStartElement('layerevent')

		self.log.writeStartElement('layeralpha')
		self.log.writeAttribute('key',str(key))
		self.log.writeAttribute('alpha',str(alpha))

		# end sublayer event
		self.log.writeEndElement()

		# end layer event
		self.log.writeEndElement()

		self.endEvent()

	# log a move with index and number indicating change (ie -1 for 1 down)
	def logLayerMove(self, index, change):
		lock=qtcore.QMutexLocker(self.mutex)
		self.startEvent()

		# start layer event
		self.log.writeStartElement('layerevent')

		# start sublayer event
		self.log.writeStartElement('movelayer')
		self.log.writeAttribute('index',str(index))
		self.log.writeAttribute('change',str(change))

		# end sublayer event
		self.log.writeEndElement()

		# end layer event
		self.log.writeEndElement()

		self.endEvent()
		
	def logToolEvent(self,tool):
		lock=qtcore.QMutexLocker(self.mutex)
		self.startEvent()

		points=tool.pointshistory

		# start tool event
		self.log.writeStartElement('toolevent')
		self.log.writeAttribute('name',tool.name)
		self.log.writeAttribute('layerkey',str(tool.layer.key))

		if tool.fgcolor:
			self.log.writeStartElement('fgcolor')
			self.log.writeAttribute('r',str(tool.fgcolor.red()))
			self.log.writeAttribute('g',str(tool.fgcolor.green()))
			self.log.writeAttribute('b',str(tool.fgcolor.blue()))
			self.log.writeEndElement()

		if tool.bgcolor:
			self.log.writeStartElement('bgcolor')
			self.log.writeAttribute('r',str(tool.bgcolor.red()))
			self.log.writeAttribute('g',str(tool.bgcolor.green()))
			self.log.writeAttribute('b',str(tool.bgcolor.blue()))
			self.log.writeEndElement()

		if tool.clippath:
			poly=tool.clippath.toFillPolygon().toPolygon()
			self.log.writeStartElement('clippath')

			for p in range(poly.size()):
				self.log.writeStartElement('polypoint')
				self.log.writeAttribute('x',str(poly.at(p).x()))
				self.log.writeAttribute('y',str(poly.at(p).y()))
				self.log.writeEndElement()

			# end clip path
			self.log.writeEndElement()

		# add tool params to log
		for key in tool.options.keys():
			self.log.writeStartElement('toolparam')
			self.log.writeAttribute('name', key )
			self.log.writeAttribute('value',str(tool.options[key]))
			self.log.writeEndElement()

		# add points to log
		for point in points:
			self.log.writeStartElement('point')
			self.log.writeAttribute('x',str(point[0]))
			self.log.writeAttribute('y',str(point[1]))
			self.log.writeAttribute('pressure',str(point[2]))
			self.log.writeEndElement()
			
		# end tool event
		self.log.writeEndElement()

		self.endEvent()

	def logCreateDocument(self,width,height):
		lock=qtcore.QMutexLocker(self.mutex)

		#attrs=AttributesNSImpl(attr_vals, attr_qnames)
		self.log.writeStartElement('createdoc')
		self.log.writeAttribute('width',str(width))
		self.log.writeAttribute('height',str(height))

		# end createdoc event
		self.log.writeEndElement()

	def logRawEvent(self,x,y,layerkey,image,path=None):
		lock=qtcore.QMutexLocker(self.mutex)
		self.startEvent()

		x=str(x)
		y=str(y)
		layerkey=str(layerkey)

		self.log.writeStartElement('rawevent')
		self.log.writeAttribute('x',x)
		self.log.writeAttribute('y',y)
		self.log.writeAttribute('layerkey',layerkey)

		# if there is a clip path for this raw event
		if path:
			poly=path.toFillPolygon().toPolygon()
			self.log.writeStartElement('clippath')

			for p in range(poly.size()):
				self.log.writeStartElement('polypoint')
				self.log.writeAttribute('x',str(poly.at(p).x()))
				self.log.writeAttribute('y',str(poly.at(p).y()))
				self.log.writeEndElement()

			# end clip path
			self.log.writeEndElement()

		bytearray=qtcore.QByteArray()
		buf=qtcore.QBuffer(bytearray)
		buf.open(qtcore.QIODevice.WriteOnly)
		image.save(buf,"PNG")

		# compress then convert to base 64 so it can be printed in ascii
		bytearray=qtcore.qCompress(bytearray)
		bytearray=bytearray.toBase64()

		rawstring='%s' % bytearray

		self.log.writeCharacters(rawstring)
		self.log.writeEndElement()

		self.endEvent()

	def logResyncRequest(self):
		print "DEBUG: logging resync"
		lock=qtcore.QMutexLocker(self.mutex)
		self.startEvent()

		self.log.writeStartElement('resyncrequest')
		self.log.writeEndElement()

		self.endEvent()

	def logResyncStart(self):
		lock=qtcore.QMutexLocker(self.mutex)
		self.startEvent()

		self.log.writeStartElement('resyncstart')
		self.log.writeEndElement()

		self.endEvent()

	def endLog(self):
		lock=qtcore.QMutexLocker(self.mutex)
		self.log.writeEndElement()
		self.output.close()
