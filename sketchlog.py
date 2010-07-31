#    Beedraw/Hive network capable client and server allowing collaboration on a single image
#    Copyright (C) 2009 Thomas Becker
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

import PyQt4.QtCore as qtcore
import PyQt4.QtXml as qtxml
from beetypes import *
from beeutil import *

# changed locations between versions
try:
	from PyQt4.QtCore import QXmlStreamWriter
except:
	from PyQt4.QtXml import QXmlStreamWriter

class SketchLogWriter:
	def __init__(self, output):
		self.output=output

		self.log=QXmlStreamWriter(output)

		# mutex so we don't write to file from mulitple sources at once
		self.mutex=qtcore.QMutex()

		self.log.writeStartDocument()

		# add parent element
		self.log.writeStartElement('sketchlog')

	def logCommand(self,command,owner=0):
		lock=qtcore.QMutexLocker(self.mutex)
		self.startEvent(owner)
		type=command[0]

		if type==DrawingCommandTypes.history:
			self.logHistoryCommand(command)

		elif type==DrawingCommandTypes.layer:
			self.logLayerCommand(command)

		elif type==DrawingCommandTypes.alllayer:
			self.logAllLayerCommand(command)

		elif type==DrawingCommandTypes.networkcontrol:
			self.logNetworkControl(command)

		self.endEvent()

	def logHistoryCommand(self,command):
		subtype=command[1]
		if subtype==HistoryCommandTypes.undo:
			self.log.writeStartElement('undo')
			self.log.writeAttribute('owner',str(command[2]))

		elif subtype==HistoryCommandTypes.redo:
			self.log.writeStartElement('redo')
			self.log.writeAttribute('owner',str(command[2]))

	def logLayerCommand(self,command):
		subtype=command[1]
		layer=command[2]
		if subtype==LayerCommandTypes.alpha:
			self.logLayerAlphaChange(layer,command[3])

		elif subtype==LayerCommandTypes.mode:
			self.logLayerModeChange(layer,command[3])

		elif subtype==LayerCommandTypes.rawevent or subtype==LayerCommandTypes.anchor:
			self.logRawEvent(command[3],command[4],layer,command[5],command[6])

		elif subtype==LayerCommandTypes.tool:
			self.logToolEvent(layer,command[3])

		else:
			print_debug("WARNING: don't know how to log layer command type: %d" % subtype)

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
			self.logLayerAdd(command[3], command[2], command[4], command[5])

	def logNetworkControl(self,command):
		subtype=command[1]
		if subtype==NetworkControlCommandTypes.resyncrequest:
			self.logResyncRequest()

		elif subtype==NetworkControlCommandTypes.resyncstart:
			self.logResyncStart(command[2],command[3],command[4])

		elif subtype==NetworkControlCommandTypes.giveuplayer:
			self.logGiveUpLayer(command[3])

		elif subtype==NetworkControlCommandTypes.layerowner:
			self.logLayerOwnerChange(command[2],command[3])

		elif subtype==NetworkControlCommandTypes.requestlayer:
			self.logLayerRequest(command[3])

		elif subtype==NetworkControlCommandTypes.fatalerror:
			self.logFatalError(command[3])

		elif subtype==NetworkControlCommandTypes.networkhistorysize:
			self.logNetworkHistorySize(command[2])

	def startEvent(self,owner):
		self.log.writeStartElement('event')

	def endEvent(self):
		self.log.writeEndElement()

	def logNetworkHistorySize(self,newsize):
		self.log.writeStartElement('networkhistorysize')
		self.log.writeAttribute('newsize',str(newsize))
		self.log.writeEndElement()

	def logFatalError(self,errormessage):
		self.log.writeStartElement('fatalerror')
		self.log.writeAttribute('errormessage',str(errormessage))
		self.log.writeEndElement()
		
	def logLayerAdd(self, position, key, image=None, owner=0):
		# if there is an image then log it as
		if image:
			self.log.writeStartElement('image')

			bytearray=qtcore.QByteArray()
			buf=qtcore.QBuffer(bytearray)
			buf.open(qtcore.QIODevice.WriteOnly)
			image.save(buf,"PNG")

			# compress then convert to base 64 so it can be printed in ascii
			bytearray=qtcore.qCompress(bytearray)
			bytearray=bytearray.toBase64()

			rawstring='%s' % bytearray

			self.log.writeCharacters(rawstring)

			# end image
			self.log.writeEndElement()

		# start addlayer event
		self.log.writeStartElement('addlayer')
		self.log.writeAttribute('position',str(position))
		self.log.writeAttribute('key',str(key))
		self.log.writeAttribute('owner',str(owner))

		# end addlayer event
		self.log.writeEndElement()

	def logLayerSub(self, key):
		# start sublayer event
		self.log.writeStartElement('sublayer')
		self.log.writeAttribute('index',str(key))

		# end sublayer event
		self.log.writeEndElement()

	def logLayerModeChange(self, key, mode):
		modestr=str(BlendTranslations.modeToName(mode))
		if not modestr:
			print_debug("can't log mode change")
			return

		self.log.writeStartElement('layermode')
		self.log.writeAttribute('key',str(key))
		self.log.writeAttribute('mode',modestr)

		# end sublayer event
		self.log.writeEndElement()

	def logLayerAlphaChange(self, key, alpha):
		self.log.writeStartElement('layeralpha')
		self.log.writeAttribute('key',str(key))
		self.log.writeAttribute('alpha',str(alpha))

		# end sublayer event
		self.log.writeEndElement()

	# log a move with index and number indicating change (ie -1 for 1 down)
	def logLayerMove(self, index, change):
		# start sublayer event
		self.log.writeStartElement('movelayer')
		self.log.writeAttribute('index',str(index))
		self.log.writeAttribute('change',str(change))

		# end sublayer event
		self.log.writeEndElement()

	def logToolEvent(self,layerkey,tool):
		prevpoints=tool.prevpointshistory
		points=tool.pointshistory

		# write clip path if needed
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

		# start tool event
		self.log.writeStartElement('toolevent')
		self.log.writeAttribute('name',tool.name)
		self.log.writeAttribute('layerkey',str(layerkey))

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

		# add tool params to log
		for key in tool.options.keys():
			self.log.writeStartElement('toolparam')
			self.log.writeAttribute('name', key )
			self.log.writeAttribute('value',str(tool.options[key]))
			self.log.writeEndElement()

		for pointlist in prevpoints:
			self.log.writeStartElement('pointslist')
			for point in pointlist:
				self.log.writeStartElement('point')
				self.log.writeAttribute('x',str(point[0]))
				self.log.writeAttribute('y',str(point[1]))
				self.log.writeAttribute('pressure',str(point[2]))
				self.log.writeEndElement()
			self.log.writeEndElement()

		# add points to log
		self.log.writeStartElement('pointslist')
		for point in points:
			self.log.writeStartElement('point')
			self.log.writeAttribute('x',str(point[0]))
			self.log.writeAttribute('y',str(point[1]))
			self.log.writeAttribute('pressure',str(point[2]))
			self.log.writeEndElement()
		self.log.writeEndElement()

		# end tool event
		self.log.writeEndElement()

	def logCreateDocument(self,width,height):
		self.log.writeStartElement('createdoc')
		self.log.writeAttribute('width',str(width))
		self.log.writeAttribute('height',str(height))

		# end createdoc event
		self.log.writeEndElement()

	def logRawEvent(self,x,y,layerkey,image,path=None):
		# write out the image data
		self.log.writeStartElement('image')
		bytearray=qtcore.QByteArray()
		buf=qtcore.QBuffer(bytearray)
		buf.open(qtcore.QIODevice.WriteOnly)
		image.save(buf,"PNG")

		# compress then convert to base 64 so it can be printed in ascii
		bytearray=qtcore.qCompress(bytearray)
		bytearray=bytearray.toBase64()

		rawstring='%s' % bytearray

		self.log.writeCharacters(rawstring)

		# end writing the image data
		self.log.writeEndElement()

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

		x=str(x)
		y=str(y)
		layerkey=str(layerkey)

		self.log.writeStartElement('rawevent')
		self.log.writeAttribute('x',x)
		self.log.writeAttribute('y',y)
		self.log.writeAttribute('layerkey',layerkey)

		self.log.writeEndElement()

	def logResyncRequest(self):
		print_debug("DEBUG: logging resync")

		self.log.writeStartElement('resyncrequest')
		self.log.writeEndElement()

	def logResyncStart(self,width,height,remoteid):
		self.log.writeStartElement('resyncstart')
		self.log.writeAttribute('width',str(width))
		self.log.writeAttribute('height',str(height))
		self.log.writeAttribute('remoteid',str(remoteid))
		self.log.writeEndElement()

	def logGiveUpLayer(self,key):
		self.log.writeStartElement('giveuplayer')
		self.log.writeAttribute('key',str(key))
		self.log.writeEndElement()

	def logLayerOwnerChange(self,owner,key):
		self.log.writeStartElement('changelayerowner')
		self.log.writeAttribute('owner',str(owner))
		self.log.writeAttribute('key',str(key))
		self.log.writeEndElement()

	def logLayerRequest(self,key):
		self.log.writeStartElement('layerrequest')
		self.log.writeAttribute('key',str(key))
		self.log.writeEndElement()

	def endLog(self):
		self.log.writeEndElement()
		self.output.flush()
		self.output.close()
