#    Beedraw/Hive network capable client and server allowing collaboration on a single image
#    Copyright (C) 2009 B. Becker
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

# append designer dir to search path
import sys
sys.path.append("designer")

import os
import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore

import cPickle as pickle

from socket import socket as pysocket

from beenetwork import BeeSocket
from beeglobals import *
from beetypes import *
from BeeMasterUI import Ui_BeeMasterSpec
from AboutDisplayDialogUi import Ui_About_Dialog
from PickNewCanvasSizeDialogUi import Ui_canvas_size_dialog
from ConnectionDialogUi import Ui_ConnectionInfoDialog
from BeeDrawOptionsUi import Ui_BeeMasterOptions
from beelayer import BeeLayersWindow
from beeutil import *
from beesave import PaletteXmlWriter,BeeToolConfigWriter,BeeMasterConfigWriter
from beeload import PaletteParser,BeeToolConfigParser
from beepalette import PaletteWindow
from toolwindow import ToolWindow

from beeapp import BeeApp

from abstractbeemaster import AbstractBeeMaster
from beedrawingwindow import BeeDrawingWindow, NetworkClientDrawingWindow, AnimationDrawingWindow


class BeeMasterWindow(qtgui.QMainWindow,object,AbstractBeeMaster):
	def __init__(self):
		qtgui.QMainWindow.__init__(self)
		AbstractBeeMaster.__init__(self)

		# read tool options from file if needed
		toolconfigfilename=os.path.join("config","tooloptions.xml")
		toolconfigfile=qtcore.QFile(toolconfigfilename)
		if toolconfigfile.exists():
			if toolconfigfile.open(qtcore.QIODevice.ReadOnly):
				parser=BeeToolConfigParser(toolconfigfile)
				parser.loadToToolBox(self.toolbox)

		# setup interface according to designer code
		self.ui=Ui_BeeMasterSpec()
		self.ui.setupUi(self)
		self.show()

		# list to hold drawing windows created
		self.drawingwindows=[]
		self.drawingwindowslock=qtcore.QReadWriteLock()

		self.curwindow=None

		self.curpointertype=-1
		self.curtoolname=self.toolbox.getCurToolDesc().name

		self.clipboardimage=None
		self.clipboardlock=qtcore.QReadWriteLock()

		self.pointertoolmap={}
		# set some initial default values for tool pointers
		self.pointertoolmap[1]="brush"
		self.pointertoolmap[3]="eraser"

		# setup foreground and background swatches
		# default foreground to black and background to white
		#self.ui.FGSwatch=FGSwatch(self,replacingwidget=self.ui.FGSwatch)
		#self.setFGColor(qtgui.QColor(0,0,0))

		#self.ui.BGSwatch=BGSwatch(self,replacingwidget=self.ui.BGSwatch)
		#self.setBGColor(qtgui.QColor(255,255,255))

		# vars for dialog windows that there should only be one of each
		self.layerswindow=BeeLayersWindow(self)

		# keep track of current ID so each window gets a unique ID
		self.nextwindowid=0

		# setup window with tool options
		self.tooloptionswindow=ToolWindow(self)
		self.tooloptionswindow.updateCurrentTool()

		# setup window with colors
		self.palettewindow=PaletteWindow(self)

		self.fgcolor=qtgui.QColor(0,0,0)
		self.bgcolor=qtgui.QColor(255,255,255)

		palfilename=os.path.join(BEE_CONFIG_DIR,"config/default.pal")
		palfile=qtcore.QFile(palfilename)
		if palfile.exists():
			palfile.open(qtcore.QIODevice.ReadOnly)
			reader=PaletteParser(palfile)
			colors=reader.getColors()
		else:
			colors=[]

	def setClipBoardImage(self,image):
		lock=qtcore.QWriteLocker(self.clipboardlock)
		self.clipboardimage=image.copy()

	def getClipBoardImage(self,image):
		lock=qtcore.QReadLocker(self.clipboardlock)
		return self.clipboardimage.copy()

	# I don't think these currently need to have mutexes, but if they ever do it can be done here
	def setFGColor(self,color):
		self.fgcolor=color
		self.palettewindow.ui.FGSwatch.updateColor(color)

	def setBGColor(self,color):
		self.bgcolor=color
		self.palettewindow.ui.BGSwatch.updateColor(color)

	def getFGColor(self):
		return self.fgcolor

	def getBGColor(self):
		return self.bgcolor

	def registerWindow(self,window):
		lock=qtcore.QWriteLocker(self.drawingwindowslock)
		self.drawingwindows.append(window)

	def unregisterWindow(self,window):
		lock=qtcore.QWriteLocker(self.drawingwindowslock)
		self.drawingwindows.remove(window)
		# if the window we're deleting was the active window
		if self.curwindow==window:
			# if there is at least one other window make that the current window
			if self.drawingwindows:
				self.curwindow=self.drawingwindows[0]
			else:
				self.curwindow=None

			self.refreshLayersList()

	def getNextWindowId(self):
		self.nextwindowid+=1
		return self.nextwindowid

	def getWindowById(self,id):
		lock=qtcore.QReadLocker(self.drawingwindowslock)
		for win in self.drawingwindows:
			if win.id==id:
				return win
		print "WARNING: Couldn't find window with ID:", id
		return None

	def getLayerById(self,win_id,layer_id):
		win=self.getWindowById(win_id)
		if win:
			return win.getLayerForKey(layer_id)
		else:
			print "WARNING: can't find layer with id:", layer_id, "in window:", win_id
		return None

	def removeWindow(self,window):
		"""remove a drawing window from the list of current windows"""
		lock=qtcore.QWriteLocker(self.drawingwindowslock)
		try:
			self.drawingwindows.remove(window)
		except:
			pass
		if self.curwindow==window:
			self.curwindow=None

	def getCurToolInst(self,window):
		"""return new instance of current tool type, with layer set to current layer"""
		curtool=self.getCurToolDesc()
		return curtool.setupTool(window,window.getCurLayerKey())

	def getCurToolDesc(self):
		"""return pointer to the currently selected tool description object"""
		return self.toolbox.getCurToolDesc()

	def changeCurToolByName(self,name):
		if self.toolbox.setCurToolByName(name):
			self.curtoolname=name
			self.tooloptionswindow.updateCurrentTool()
			self.toolbox.getCurToolDesc().pressToolButton()

	def newModKeys(self,modkeys):
		#print "master got new mod keys"
		pass

	def pointerTypeCheck(self,pointertype):
		if pointertype!=self.curpointertype:
			#print "changing pointer type to:", pointertype
			self.pointertoolmap[self.curpointertype]=self.curtoolname

			if pointertype in self.pointertoolmap:
				self.changeCurToolByName(self.pointertoolmap[pointertype])

			self.curpointertype=pointertype

	# connect signals for tool buttons
	def on_pencil_button_clicked(self,accept=False):
		if accept:
			self.changeCurToolByName("pencil")

	def on_brush_button_clicked(self,accept=False):
		if accept:
			self.changeCurToolByName("brush")

	def on_eraser_button_clicked(self,accept=False):
		if accept:
			self.changeCurToolByName("eraser")

	def on_paint_bucket_button_clicked(self,accept=False):
		if accept:
			self.changeCurToolByName("bucket")

	def on_eye_dropper_button_clicked(self,accept=False):
		if accept:
			self.changeCurToolByName("eyedropper")

	def on_rectangle_select_button_clicked(self,accept=False):
		if accept:
			self.changeCurToolByName("rectselect")

	def on_feather_select_button_clicked(self,accept=False):
		if accept:
			self.changeCurToolByName("featherselect")

	def on_tool_changed(self,index):
		self.toolbox.setCurToolIndex(index)
		lock=qtcore.QReadLocker(self.drawingwindowslock)
		for win in self.drawingwindows:
			win.view.setCursor(self.toolbox.getCurToolDesc().getCursor())

	def on_tooloptionsbutton_pressed(self):
		self.getCurToolDesc().runOptionsDialog(self)

	def on_Tool_save_default_triggered(self,accept=True):
		if not accept:
			return

		filename=os.path.join("config","tooloptions.xml")
		outfile=qtcore.QFile(filename,self)
		outfile.open(qtcore.QIODevice.Truncate|qtcore.QIODevice.WriteOnly)
		writer=BeeToolConfigWriter(outfile)
		writer.startLog()
		for tool in self.toolbox.toolslist:
			writer.logToolConfig(tool.name,tool.options)
		writer.endLog()
		outfile.close()

	def on_backgroundbutton_pressed(self):
		self.ui.BGSwatch.changeColorDialog()

	def on_foregroundbutton_pressed(self):
		self.ui.FGSwatch.changeColorDialog()

	def on_action_File_Play_triggered(self,accept=True):
		if not accept:
			return

		filename=str(qtgui.QFileDialog.getOpenFileName(self,"Select log file to play","","Sketch logfiles (*.slg)"))

		if filename:
			self.playFile(filename)

	def playFile(self,filename):
		self.curwin=AnimationDrawingWindow(self,filename)

	def on_action_File_Open_triggered(self,accept=True):
		if not accept:
			return

		formats=getSupportedReadFileFormats()
		filterstring=qtcore.QString("Images (")

		for f in formats:
			filterstring.append(" *.")
			filterstring.append(f)

		filterstring.append(" *.bee)")

		filename=qtgui.QFileDialog.getOpenFileName(self,"Choose File To Open","",filterstring)

		if filename:
			self.openFile(filename)

	def openFile(self,filename):
		# create a drawing window to start with
		# if we are saving my custom format
		if filename.endsWith(".bee"):
			self.playFile(filename)

		else:
			reader=qtgui.QImageReader(filename)
			image=reader.read()

			self.curwindow=BeeDrawingWindow(self,image.width(),image.height(),False)
			self.curwindow.loadLayer(image)

			self.refreshLayersList()

	def on_actionFileMenuNew_triggered(self,accept=True):
		if not accept:
			return
		dialog=qtgui.QDialog(self)
		dialogui=Ui_canvas_size_dialog()
		dialogui.setupUi(dialog)
		dialog.exec_()

		if dialog.result():
			width=dialogui.width_box.value()
			height=dialogui.height_box.value()
			self.curwindow=BeeDrawingWindow(self,width=width,height=height)
			self.refreshLayersList()

	def on_action_Edit_Configure_triggered(self,accept=True):
		if not accept:
			return

		dialog=qtgui.QDialog(self)
		dialogui=Ui_BeeMasterOptions()
		dialogui.setupUi(dialog)

		# put current values into GUI
		lock=qtcore.QWriteLocker(self.configlock)

		if self.config['debug']:
			dialogui.debug_checkBox.setCheckState(qtcore.Qt.Checked)
		if self.config['autolog']:
			dialogui.autolog_checkBox.setCheckState(qtcore.Qt.Checked)
		if self.config['autosave']:
			dialogui.autosave_checkBox.setCheckState(qtcore.Qt.Checked)
		dialogui.username_entry.setText(self.config['username'])
		
		ok=dialog.exec_()

		if not ok:
			return

		# get values out of GUI
		self.config['username']=dialogui.username_entry.text()

		if dialogui.debug_checkBox.isChecked():
			self.config['debug']=True
		else:
			self.config['debug']=False

		BEE_DEBUG=self.config['debug']

		if dialogui.autolog_checkBox.isChecked():
			self.config['autolog']=True
		else:
			self.config['autolog']=False

		if dialogui.autosave_checkBox.isChecked():
			self.config['autosave']=True
		else:
			self.config['autosave']=False

		# write out everything to file
		filename=os.path.join("config","beedrawoptions.xml")
		outfile=qtcore.QFile(filename,self)
		outfile.open(qtcore.QIODevice.Truncate|qtcore.QIODevice.WriteOnly)
		writer=BeeMasterConfigWriter(outfile)
		writer.writeConfig(self.config)
		outfile.close()

	def on_action_Help_About_triggered(self,accept=True):
		if not accept:
			return

		dialog=qtgui.QDialog(self)
		dialogui=Ui_About_Dialog()
		dialogui.setupUi(dialog)
		dialog.exec_()

	def on_action_File_Connect_triggered(self,accept=True):
		if not accept:
			return

		# launch dialog
		dialog=qtgui.QDialog(self)
		dialogui=Ui_ConnectionInfoDialog()
		dialogui.setupUi(dialog)

		# set default options
		dialogui.usernamefield.setText(self.getConfigOption('username',""))

		ok=dialog.exec_()

		if not ok:
			return

		hostname=dialogui.hostnamefield.text()
		port=dialogui.portbox.value()
		username=dialogui.usernamefield.text()
		password=dialogui.passwordfield.text()

		# error if username is blank
		if username=="":
			qtgui.QMessageBox.warning(None,"No username","You must enter a username")
			return

		socket=self.getServerConnection(username,password,hostname,port)

		if socket:
			self.curwindow=NetworkClientDrawingWindow(self,socket)
			self.refreshLayersList()

	# connect to host and authticate
	def getServerConnection(self,username,password,host,port):
		if os.name=="posix":
			# qt sockets are giving me trouble under linux, but work fine under windows
			socket=BeeSocket(BeeSocketTypes.python,pysocket())
		else:
			socket=BeeSocket(BeeSocketTypes.qt,qtnet.QTcpSocket())

		print_debug("waiting for socket connection:")
		connected=socket.connect(host,port)
		print_debug("finished waiting for socket connection")

		# return error if we couldn't get a connection after 30 seconds
		if not connected:
			#qtgui.QMessageBox.warning(None,"Failed to connect to server",socket.errorString())
			qtgui.QMessageBox.warning(None,"Failed to connect to server",socket.errorString())
			return None

		#authrequest=qtcore.QByteArray()
		authrequest="%s\n%s\n%d\n" % (username,password,PROTOCOL_VERSION)
		
		# send authtication info
		socket.write(authrequest)

		responsestring=qtcore.QString()

		# wait for response
		while responsestring.count('\n')<2 and len(responsestring)<500:
			data=socket.read(512)
			if data:
				print_debug("got authentication answer: %s" % qtcore.QString(data))
				responsestring.append(data)

			# if error exit
			else:
				qtgui.QMessageBox.warning(None,"Connection Error","server dropped connection")
				return None

		# if we get here we have a response that probably wasn't a disconnect
		responselist=responsestring.split('\n')
		if len(responselist)>1:
			answer="%s" % responselist[0]
			message="%s" % responselist[1]
		else:
			answer="Failure"
			message="Unknown Status"

		if answer=="Success":
			return socket

		socket.close()
		qtgui.QMessageBox.warning(None,"Server Refused Connection",message)
		return None

	def on_action_File_Start_Server_triggered(self,accept=True):
		if not accept:
			return
		self.serverwin=HiveMasterWindow(BeeApp().app)
		self.curwindow=BeeDrawingWindow.startNetworkServer(self)
		self.refreshLayersList()

	def uncheckWindowLayerBox(self):
		self.ui.Window_Layers.setChecked(False)

	def on_Window_Layers_triggered(self,state=None):
		if state==None:
			return
		if state:
			self.layerswindow.show()
			self.refreshLayersList()
		else:
			self.layerswindow.hide()

	def uncheckWindowPaletteBox(self):
		self.ui.Window_Palette.setChecked(False)

	def on_Window_Palette_triggered(self,state=None):
		if state==None:
			return
		if state:
			self.palettewindow.show()
		else:
			self.palettewindow.hide()

	def uncheckWindowToolOptionsBox(self):
		self.ui.Window_Tool_Options.setChecked(False)

	def on_Window_Tool_Options_triggered(self,state=None):
		if state==None:
			return
		if state:
			self.tooloptionswindow.show()
		else:
			self.tooloptionswindow.hide()

	# destroy all subwindows
	def cleanUp(self):
		# copy list of windows otherwise destroying the windows as we iterate through will skip some
		lock=qtcore.QWriteLocker(self.drawingwindowslock)
		tmplist=self.drawingwindows[:]

		# sending close will cause the windows to remove themselves from the window list
		for window in tmplist:
			window.close()

		self.layerswindow.close()
		self.layerswindow=None

		self.palettewindow.close()
		self.palettewindow=None

		self.tooloptionswindow.close()
		self.tooloptionswindow=None

	def closeEvent(self,event):
		# destroy subwindows
		self.cleanUp()
		# then do the standard main window close event
		qtgui.QMainWindow.closeEvent(self,event)

	def refreshLayersList(self):
		if self.layerswindow:
			if self.curwindow:
				self.layerswindow.refreshLayersList(self.curwindow.layers,self.curwindow.curlayerkey)
			else:
				self.layerswindow.refreshLayersList(None,None)

	# function for a window to take the focus from other windows
	def takeFocus(self,window):
		if window != self.curwindow:
			self.curwindow=window
			self.refreshLayersList()

	def updateLayerHighlight(self,key):
		if self.layerswindow:
			self.layerswindow.refreshLayerHighlight(key)

	# refresh thumbnail of layer with inidcated key
	def refreshLayerThumb(self,windowid,key=None):
		if self.curwindow and self.curwindow.id==windowid:
			self.layerswindow.refreshLayerThumb(key)

	# handle the custom event I created to trigger refreshing the list of layers
	def customEvent(self,event):
		if event.type()==BeeCustomEventTypes.refreshlayerslist:
			self.refreshLayersList()
		elif event.type()==BeeCustomEventTypes.displaymessage:
			print "attempting to display message"
			self.displayMessage(event.boxtype,event.title,event.message)

	def displayMessage(self,boxtype,title,message):
		print "displaying message with box type:", boxtype
		if boxtype==BeeDisplayMessageTypes.warning:
			qtgui.QMessageBox.warning(self,title,message)
		elif boxtype==BeeDisplayMessageTypes.error:
			qtgui.QMessageBox.error(self,title,message)
		else:
			print "unknown box type"
