from base64 import b64decode

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui
import PyQt4.QtXml as qtxml

try:
	from PyQt4.QtXml import QXmlStreamReader
except:
	from PyQt4.QtCore import QXmlStreamReader

class PaletteParser:
	def __init__(self,device):
		self.xml=QXmlStreamReader()

		self.xml.setNamespaceProcessing(False)

		self.xml.setDevice(device)
		self.colors=[[]]

	def getColors(self):
		while not self.xml.atEnd():
			tokentype=self.xml.readNext()
			if tokentype==QXmlStreamReader.StartElement:
				self.processStartElement()

		return self.colors

	def processStartElement(self):
		name=self.xml.name()
		attrs=self.xml.attributes()

		if name == "beepalette":
			(self.rows,ok)=attrs.value('rows').toString().toInt()
			(self.columns,ok)=attrs.value('columns').toString().toInt()

		elif name == "color":
			(r,ok)=attrs.value('r').toString().toInt()
			(g,ok)=attrs.value('g').toString().toInt()
			(b,ok)=attrs.value('b').toString().toInt()

			if len(self.colors[-1]) >= self.columns:
				self.colors.append([])

			self.colors[-1].append((r,g,b))
