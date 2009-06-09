#!/usr/bin/env Python

# changed locations between versions
try:
	from PyQt4.QtCore import QXmlStreamWriter
except:
	from PyQt4.QtXml import QXmlStreamWriter

class PaletteXmlWriter:
	def __init__(self, output):
		self.out=QXmlStreamWriter(output)

	def logPalette(self,palettelist):
		if not palettelist:
			print "Error, can't find list of colors to write out"
			return

		rows=len(palettelist)
		columns=len(palettelist[0])

		self.out.writeStartElement('beepalette')
		self.out.writeAttribute('rows',str(rows))
		self.out.writeAttribute('columns',str(columns))

		for row in palettelist:
			for swatch in row:
				self.out.writeStartElement('color')
				self.out.writeAttribute('r',str(swatch.color.red()))
				self.out.writeAttribute('g',str(swatch.color.green()))
				self.out.writeAttribute('b',str(swatch.color.blue()))

				self.out.writeEndElement()

		self.out.writeEndElement()
