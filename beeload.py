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

class BeeToolConfigParser:
	def __init__(self,device):
		self.xml=QXmlStreamReader()
		self.xml.setNamespaceProcessing(False)
		self.xml.setDevice(device)
		self.curtool=None

	def loadToToolBox(self,toolbox):
		self.toolbox=toolbox
		while not self.xml.atEnd():
			tokentype=self.xml.readNext()
			if tokentype==QXmlStreamReader.StartElement:
				self.processStartElement()

	def processStartElement(self):
		name=self.xml.name()
		attrs=self.xml.attributes()

		if name=="toolconfig":
			toolname="%s" % attrs.value('name').toString()
			self.curtool=self.toolbox.getToolDescByName(toolname)
		elif name=="option":
			if self.curtool:
				valname="%s" % attrs.value('name').toString()
				(value,ok)=attrs.value('value').toString().toInt()
				self.curtool.options[valname]=value

class BeeMasterConfigParser:
	def __init__(self,device):
		self.xml=QXmlStreamReader()
		self.xml.setNamespaceProcessing(False)
		self.xml.setDevice(device)
		self.options={}

	def loadOptions(self):
		while not self.xml.atEnd():
			tokentype=self.xml.readNext()
			if tokentype==QXmlStreamReader.StartElement:
				self.processStartElement()

		return self.options

	def processStartElement(self):
		name=self.xml.name()
		attrs=self.xml.attributes()

		if name in ["username","server"]:
			key="%s" % name.toString()
			val="%s" % attrs.value("value").toString()
			self.options[key]=val
		elif name in ["port","maxundo"]:
			key="%s" % name.toString()
			(val,ok)=attrs.value("value").toString().toInt()
			self.options[key]=val
		elif name in ["autolog","autosave","debug"]:
			key="%s" % name.toString()
			val="%s" % attrs.value("value").toString()
			if val=="True":
				self.options[key]=True
			else:
				self.options[key]=False

class HiveMasterConfigParser(BeeMasterConfigParser):
	def processStartElement(self):
		name=self.xml.name()
		attrs=self.xml.attributes()

		if name in ["password"]:
			key="%s" % name.toString()
			val="%s" % attrs.value("value").toString()
			self.options[key]=val
		elif name in ["port","height","width","networkhistorysize"]:
			key="%s" % name.toString()
			(val,ok)=attrs.value("value").toString().toInt()
			self.options[key]=val
		elif name in ["debug"]:
			key="%s" % name.toString()
			val="%s" % attrs.value("value").toString()
			if val=="True":
				self.options[key]=True
			else:
				self.options[key]=False

class BeeWindowPositionConfigParser(BeeMasterConfigParser):
	def processStartElement(self):
		name=self.xml.name()
		attrs=self.xml.attributes()

		if name in ["toolx","tooly","toolw","toolh","palettex","palettey","palettew","paletteh","layerx","layery","layerw","layerh"]:
			key="%s" % name.toString()
			(val,ok)=attrs.value("value").toString().toInt()
			self.options[key]=val
		elif name in ["toolshow","paletteshow","layershow"]:
			key="%s" % name.toString()
			val="%s" % attrs.value("value").toString()
			if val=="True":
				self.options[key]=True
			else:
				self.options[key]=False
