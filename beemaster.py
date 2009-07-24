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

from beeglobals import *
from beetypes import *
from BeeMasterUI import Ui_BeeMasterSpec
from ConnectionDialogUi import Ui_ConnectionInfoDialog
from colorswatch import *
from beelayer import BeeLayersWindow
from beeutil import *
from beesave import PaletteXmlWriter
from beeload import PaletteParser

from beeapp import BeeApp

from abstractbeemaster import AbstractBeeMaster
from beedrawingwindow import BeeDrawingWindow, NetworkClientDrawingWindow, AnimationDrawingWindow

class BeeSwatchScrollArea(qtgui.QScrollArea):
	def __init__(self,master,oldwidget,rows=15,columns=12,boxsize=15):
		parent=oldwidget.parentWidget()
		qtgui.QScrollArea.__init__(self,parent)

		self.master=master

		self.boxsize=boxsize
		self.swatchrows=rows
		self.swatchcolumns=columns

		# steal attributes from old widget
		self.setSizePolicy(oldwidget.sizePolicy())
		self.setObjectName(oldwidget.objectName())

		# remove old widget and insert this one
		self.replaceWidget(oldwidget)

		self.setWidget(qtgui.QFrame(self))

		self.show()

	def replaceWidget(self,oldwidget):
		parent=oldwidget.parentWidget()
		index=parent.layout().indexOf(oldwidget)
		parent.layout().removeWidget(oldwidget)
		parent.layout().insertWidget(index,self)

	def setupSwatches(self,colors):
		self.widget().setLayout(qtgui.QGridLayout(self.widget()))
		self.widget().layout().setSpacing(0)
		if colors:
			self.rows=len(colors)
			self.columns=len(colors[0])
		# keep around pointer to all the swatches to read from them all later if needed

		curcolor=None
		self.swatches=[]
		widget=self.widget()
		layout=widget.layout()
		for i in range(self.swatchrows):
			curswatchrow=[]
			for j in range(self.swatchcolumns):
				if colors:
					rownum=len(curswatchrow)
					colnum=len(self.swatches)
					curcolor=colors[colnum][rownum]
				# just to make it look better, put each swatch in a frame with a border
				curframe=qtgui.QFrame(widget)
				curframe.setFrameShape(qtgui.QFrame.StyledPanel)
				curframe.setLayout(qtgui.QHBoxLayout(curframe))
				curswatch=ColorSwatch(self.master,parent=curframe,boxsize=self.boxsize,color=curcolor)
				curframe.layout().addWidget(curswatch)
				curswatchrow.append(curswatch)
				curframe.layout().setMargin(0)

				# readjust subframe size to swatch size
				curframe.adjustSize()
				curframe.show()

				# add the widget at the right place
				layout.addWidget(curframe,i,j)

			self.swatches.append(curswatchrow)

		# readjust the whole palette widget to the right size
		widget.adjustSize()

class BeeMasterWindow(qtgui.QMainWindow,object,AbstractBeeMaster):
	def __init__(self):
		qtgui.QMainWindow.__init__(self)
		AbstractBeeMaster.__init__(self)

		# setup interface according to designer code
		self.ui=Ui_BeeMasterSpec()
		self.ui.setupUi(self)
		self.show()

		# list to hold drawing windows created
		self.drawingwindows=[]

		# add list of tools to tool choice drop down
		for tool in self.toolbox.toolNameGenerator():
			self.ui.toolChoiceBox.addItem(tool)

		# set signal so we know when the tool changes
		self.connect(self.ui.toolChoiceBox,qtcore.SIGNAL("activated(int)"),self.on_tool_changed)

		self.curwindow=None

		# set initial tool
		self.curtoolindex=0

		# setup foreground and background swatches
		# default foreground to black and background to white
		self.ui.FGSwatch=FGSwatch(self,replacingwidget=self.ui.FGSwatch)
		self.setFGColor(qtgui.QColor(0,0,0))

		self.ui.BGSwatch=BGSwatch(self,replacingwidget=self.ui.BGSwatch)
		self.setBGColor(qtgui.QColor(255,255,255))

		# vars for dialog windows that there should only be one of each
		self.layerswindow=BeeLayersWindow(self)

		# keep track of current ID so each window gets a unique ID
		self.nextwindowid=0

		# replace widget with scroll area to hold them
		self.ui.swatch_frame=BeeSwatchScrollArea(self,self.ui.swatch_frame)

		palfilename=os.path.join(BEE_CONFIG_DIR,"config/default.pal")
		palfile=qtcore.QFile(palfilename)
		if palfile.exists():
			palfile.open(qtcore.QIODevice.ReadOnly)
			reader=PaletteParser(palfile)
			colors=reader.getColors()
		else:
			colors=[]

		self.ui.swatch_frame.setupSwatches(colors)

	def registerWindow(self,window):
		self.drawingwindows.append(window)

	def unregisterWindow(self,window):
		#print "unregistering window with references:", sys.getrefcount(window)
		self.drawingwindows.remove(window)

	def getNextWindowId(self):
		self.nextwindowid+=1
		return self.nextwindowid

	def getWindowById(self,id):
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
		try:
			self.drawingwindows.remove(window)
		except:
			pass
		if self.curwindow==window:
			self.curwindow=None

	def getCurToolInst(self,window):
		curtool=self.getCurToolDesc()
		return curtool.setupTool(window,window.getCurLayerKey())

	def getCurToolDesc(self):
		return self.toolbox.getCurToolDesc()

	def on_tool_changed(self,index):
		self.toolbox.setCurToolIndex(index)
		for win in self.drawingwindows:
			win.view.setCursor(self.toolbox.getCurToolDesc().getCursor())

	def on_tooloptionsbutton_pressed(self):
		self.getCurToolDesc().runOptionsDialog(self)

	def on_save_palette_button_pressed(self):
		filename=qtgui.QFileDialog.getSaveFileName(self,"Choose File Name",".","Palette save (*.pal)")
		if not filename:
			return
		if filename[-4:] != ".pal":
			filename+=".pal"
		outfile=qtcore.QFile(filename)
		outfile.open(qtcore.QIODevice.WriteOnly)
		writer=PaletteXmlWriter(outfile)
		writer.logPalette(self.ui.swatch_frame.swatches)

	def on_load_palette_button_pressed(self):
		filename=qtgui.QFileDialog.getOpenFileName(self,"Choose Palette File To Load",".","Palette save (*.pal)")
		if not filename:
			return

		infile=qtcore.QFile(filename)
		infile.open(qtcore.QIODevice.ReadOnly)
		reader=PaletteParser(infile)
		colors=reader.getColors()
		self.ui.swatch_frame.setupSwatches(colors)

	def on_backgroundbutton_pressed(self):
		self.ui.BGSwatch.changeColorDialog()

	def on_foregroundbutton_pressed(self):
		self.ui.FGSwatch.changeColorDialog()

	def setFGColor(self,color):
		self.ui.FGSwatch.updateColor(color)

	def setBGColor(self,color):
		self.ui.BGSwatch.updateColor(color)

	def on_action_File_Exit_triggered(self,accept=True):
		if not accept:
			return

		self.close();

	def on_action_File_Play_triggered(self,accept=True):
		if not accept:
			return

		filename=str(qtgui.QFileDialog.getOpenFileName(self,"Select log file to play","","Sketch logfiles (*.slg)"))

		if filename:
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
			f=open(filename,"r")
			try:
				l=pickle.load(f)
			except:
				qtgui.QMessageBox.warning(self,"ERROR when reading file","File does not seem to be in valid bee format")
				print_debug("Error, file dosen't seem to be in bee image format")
				return

			self.curwindow=None
			# first take version number and document size out of front of list
			version=l[0][0]
			width=l[0][1]
			height=l[0][2]

			if version > fileformatversion:
				print_debug("Error unsuppored file format version, please upgrade bee draw version")

			self.curwindow=BeeDrawingWindow(self,width,height,False)

			layers=l[1:]

			# for each layer in the file uncompress the image data and set options
			for layer in layers:
				bytearray=qtcore.qUncompress(layer[0])
				image=qtgui.QImage()
				image.loadFromData(bytearray,"PNG")
				self.curwindow.loadLayer(image,opacity=layer[1],visible=layer[2],compmode=layer[3])

		else:
			reader=qtgui.QImageReader(filename)
			image=reader.read()

			self.curwindow=BeeDrawingWindow(self,image.width(),image.height(),False)
			self.curwindow.loadLayer(image)

			self.refreshLayersList()

	def on_actionFileMenuNew_triggered(self,accept=True):
		if not accept:
			return
		self.curwindow=BeeDrawingWindow(self)

		self.refreshLayersList()

	def on_action_File_Connect_triggered(self,accept=True):
		if not accept:
			return

		# launch dialog
		dialog=qtgui.QDialog(self)
		dialogui=Ui_ConnectionInfoDialog()
		dialogui.setupUi(dialog)
		ok=dialog.exec_()

		if not ok:
			return

		hostname=dialogui.hostnamefield.text()
		port=dialogui.portbox.value()
		username=dialogui.usernamefield.text()
		password=dialogui.passwordfield.text()

		socket=self.getServerConnection(username,password,hostname,port)

		if socket:
			self.curwindow=NetworkClientDrawingWindow(self,socket)
			self.refreshLayersList()

	# connect to host and authticate
	def getServerConnection(self,username,password,host,port):
		socket=qtnet.QTcpSocket()

		socket.connectToHost(host,port)
		print_debug("waiting for socket connection:")
		connected=socket.waitForConnected()
		print_debug("finished waiting for socket connection")

		# return error if we couldn't get a connection after 30 seconds
		if not connected:
			qtgui.QMessageBox.warning(None,"Failed to connect to server",socket.errorString())
			#qtgui.QMessageBox(qtgui.QMessageBox.Information,"Connection Error","Failed to connect to server",qtgui.QMessageBox.Ok).exec_()
			return None

		authrequest=qtcore.QByteArray()
		authrequest=authrequest.append("%s\n%s\n%d\n" % (username,password,PROTOCOL_VERSION))
		# send authtication info
		socket.write(authrequest)

		responsestring=qtcore.QString()

		# wait for response
		while responsestring.count('\n')<2 and len(responsestring)<500:
			if socket.waitForReadyRead(-1):
				data=socket.read(500)
				print("got authentication answer: %s" % qtcore.QString(data))
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

	def on_actionLayers_toggled(self,state):
		if state:
			self.layerswindow.show()
			self.refreshLayersList()
		else:
			self.layerswindow.hide()

	# destroy all subwindows
	def cleanUp(self):
		# copy list of windows otherwise destroying the windows as we iterate through will skip some
		tmplist=self.drawingwindows[:]

		# sending close will cause the windows to remove themselves from the window list
		for window in tmplist:
			window.close()

		self.layerswindow.close()
		self.layerswindow=None

	def closeEvent(self,event):
		# destroy subwindows
		self.cleanUp()
		# then do the standard main window close event
		qtgui.QMainWindow.closeEvent(self,event)

	def refreshLayersList(self):
		if self.curwindow and self.layerswindow:
			self.layerswindow.refreshLayersList(self.curwindow.layers,self.curwindow.curlayerkey)

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
