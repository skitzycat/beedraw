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

# append designer dir to search path
import sys
sys.path.append("designer")

import os
import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore

import os

from socket import socket as pysocket

from beenetwork import BeeSocket
from beeglobals import *
from beetypes import *
from BeeMasterMdi import Ui_BeeMasterMdiSpec
from AboutDisplayDialogUi import Ui_About_Dialog
from PickNewCanvasSizeDialogUi import Ui_canvas_size_dialog
from ConnectionDialogUi import Ui_ConnectionInfoDialog
from BeeDrawOptionsUi import Ui_BeeMasterOptions
from beelayer import BeeLayersWindow
from beeutil import *
from beesave import BeeToolConfigWriter
from beeload import PaletteParser,BeeToolConfigParser
from beepalette import PaletteWindow
from toolwindow import *

from beeapp import BeeApp

from abstractbeemaster import AbstractBeeMaster
from beedrawingwindow import BeeDrawingWindow, NetworkClientDrawingWindow, AnimationDrawingWindow

class BeeWindowParent(qtgui.QMainWindow):
	def __init__(self,master):
		qtgui.QWidget.__init__(self)
		self.master=master
		self.setAttribute(qtcore.Qt.WA_ForceUpdatesDisabled)

	def closeEvent(self,event):
		print_debug("Window Parent got close event")
		qtgui.QMainWindow.closeEvent(self,event)

class BeeMasterWindow(qtgui.QMainWindow,object,AbstractBeeMaster):
	def __init__(self):
		# set the parent for all windows here, currently none
		self.topwinparent=None

		qtgui.QMainWindow.__init__(self)
		AbstractBeeMaster.__init__(self)

		settings=qtcore.QSettings("BeeDraw","BeeDraw")

		# set default config values
		self.config['username']=settings.value("username").toString()
		self.config['server']=settings.value("server","localhost").toString()
		self.config['port'],ok=settings.value("port",8333).toInt()
		self.config['autolog']=settings.value("autolog",False).toBool()
		self.config['autosave']=settings.value("autosave",False).toBool()
		self.config['debug']=settings.value("debug",False).toBool()
		self.config['maxundo'],ok=settings.value("maxundo",30).toInt()

		# read tool options from file if needed
		toolconfigfilename=os.path.join("config","tooloptions.xml")
		toolconfigfile=qtcore.QFile(toolconfigfilename)
		if toolconfigfile.exists():
			if toolconfigfile.open(qtcore.QIODevice.ReadOnly):
				parser=BeeToolConfigParser(toolconfigfile)
				parser.loadToToolBox(self.toolbox)

		# setup interface according to designer code
		self.ui=Ui_BeeMasterMdiSpec()
		self.ui.setupUi(self)
		self.show()

		# list to hold drawing windows and lock for it
		self.curwindow=None
		self.drawingwindows=[]
		self.drawingwindowslock=qtcore.QReadWriteLock()

		self.curpointertype=-1
		self.curtoolname=self.toolbox.getCurToolDesc().name

		self.clipboardimage=None
		self.clipboardlock=qtcore.QReadWriteLock()

		self.pointertoolmap={}
		# set some initial default values for tool pointers
		self.pointertoolmap[1]="brush"
		self.pointertoolmap[3]="eraser"

		# setup foreground and background swatches
		#self.ui.FGSwatch=FGSwatch(self,replacingwidget=self.ui.FGSwatch)
		#self.setFGColor(qtgui.QColor(0,0,0))

		#self.ui.BGSwatch=BGSwatch(self,replacingwidget=self.ui.BGSwatch)
		#self.setBGColor(qtgui.QColor(255,255,255))

		# vars for dialog windows that there should only be one of each
		self.layerswindow=BeeLayersWindow(self)

		# keep track of current ID so each window gets a unique ID
		self.nextwindowid=0

		# setup window with tool options
		self.tooloptionswindow=ToolOptionsWindow(self)
		self.tooloptionswindow.updateCurrentTool()

		self.initializedwindows=True

		# default foreground color to black and background color to white
		self.fgcolor=qtgui.QColor(0,0,0)
		self.bgcolor=qtgui.QColor(255,255,255)

		# setup window with colors
		self.palettewindow=PaletteWindow(self)

		self.toolselectwindow=ToolSelectionWindow(self)

		self.setCorner(qtcore.Qt.TopLeftCorner,qtcore.Qt.LeftDockWidgetArea)
		self.setCorner(qtcore.Qt.TopRightCorner,qtcore.Qt.RightDockWidgetArea)
		self.setCorner(qtcore.Qt.BottomLeftCorner,qtcore.Qt.LeftDockWidgetArea)
		self.setCorner(qtcore.Qt.BottomRightCorner,qtcore.Qt.RightDockWidgetArea)

		# by default have the windows docked in the main window
		self.addDockWidget(qtcore.Qt.LeftDockWidgetArea,self.toolselectwindow)
		self.addDockWidget(qtcore.Qt.LeftDockWidgetArea,self.palettewindow)
		self.addDockWidget(qtcore.Qt.RightDockWidgetArea,self.tooloptionswindow)
		self.addDockWidget(qtcore.Qt.RightDockWidgetArea,self.layerswindow)

		# restore settings
		self.restoreGeometry(settings.value("geometry").toByteArray())
		self.restoreState(settings.value("windowState").toByteArray())

		# set menu settings according to the new restored settings
		if not self.layerswindow.isVisible():
			self.uncheckWindowLayerBox()
		else:
			self.checkWindowLayerBox()

		if not self.palettewindow.isVisible():
			self.uncheckWindowPaletteBox()
		else:
			self.checkWindowPaletteBox()

		if not self.toolselectwindow.isVisible():
			self.uncheckWindowToolSelectBox()
		else:
			self.checkWindowToolSelectBox()

		if not self.tooloptionswindow.isVisible():
			self.uncheckWindowToolOptionsBox()
		else:
			self.checkWindowToolOptionsBox()

	# Palette Menu Actions:
	def on_Palette_Configure_triggered(self,accept=True):
		if not accept:
			return

		self.palettewindow.on_Palette_Configure_triggered()

	def on_Palette_save_triggered(self,accept=True):
		if not accept:
			return

		self.palettewindow.on_Palette_save_triggered()

	def on_Palette_save_default_triggered(self,accept=True):
		if not accept:
			return

		self.palettewindow.on_Palette_save_default_triggered()

	def on_Palette_load_default_triggered(self,accept=True):
		if not accept:
			return

		self.palettewindow.on_Palette_load_default_triggered()

	def on_Palette_load_triggered(self,accept=True):
		if not accept:
			return

		self.palettewindow.on_Palette_load_triggered

	def keyEvent(self,event):
		if event.key() in (qtcore.Qt.Key_Shift,qtcore.Qt.Key_Control,qtcore.Qt.Key_Alt,qtcore.Qt.Key_Meta):
			self.newModKeys(event.modifiers())

		curwin=self.getCurWindow()
		if curwin:
			curwin.keyPressEvent(event)

	def keyReleaseEvent(self,event):
		self.keyEvent(event)

	def keyPressEvent(self,event):
		self.keyEvent(event)

	def getCurWindow(self,lock=None):
		if not lock:
			lock=qtcore.QReadLocker(self.drawingwindowslock)
		return self.curwindow

	def setCurWindow(self,window,lock=None):
		if not lock:
			lock=qtcore.QWriteLocker(self.drawingwindowslock)
		if self.curwindow!=window:
			self.curwindow=window
			self.refreshLayersList(winlock=lock)

	def setClipBoardImage(self,image):
		lock=qtcore.QWriteLocker(self.clipboardlock)
		self.clipboardimage=image

	def getClipBoardImage(self):
		lock=qtcore.QReadLocker(self.clipboardlock)
		if self.clipboardimage:
			return self.clipboardimage.copy()
		return None

	# I don't think these currently need to have mutexes since they are only manipulated in the gui thread, but if they ever do it can be done here
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

	def isWindowRegistered(self,window,winlock):
		if not winlock:
			winlock=qtcore.QReadLocker(self.drawingwindowslock)

		if window in self.drawingwindows:
			return True

		return False

	def registerWindow(self,window):
		lock=qtcore.QWriteLocker(self.drawingwindowslock)
		self.drawingwindows.append(window)
		self.setCurWindow(window,lock)

		action=WindowSelectionAction(self,self.ui.menu_Window_Drawing_Windows,window.id)
		self.ui.menu_Window_Drawing_Windows.addAction(action)
		window.menufocusaction=action

	def unregisterWindow(self,window):
		lock=qtcore.QWriteLocker(self.drawingwindowslock)

		self.drawingwindows.remove(window)
		self.ui.menu_Window_Drawing_Windows.removeAction(window.menufocusaction)
		# if the window we're deleting was the active window
		if self.curwindow==window:
			# if there is at least one other window make that the current window
			if self.drawingwindows:
				self.curwindow=self.drawingwindows[0]
			else:
				self.curwindow=None

			self.requestLayerListRefresh()

		#self.ui.mdiArea.removeSubWindow(window)

	def requestLayerListRefresh(self):
		event=qtcore.QEvent(BeeCustomEventTypes.refreshlayerslist)
		BeeApp().app.postEvent(self,event)

	def getNextWindowId(self):
		self.nextwindowid+=1
		return self.nextwindowid

	def getWindowById(self,id,lock=None):
		if not lock:
			lock=qtcore.QReadLocker(self.drawingwindowslock)
		for win in self.drawingwindows:
			if win.id==id:
				return win
		print_debug("WARNING: Couldn't find window with ID: %d" % id)
		return None

	def getLayerById(self,win_id,layer_id,winlock=None):
		win=self.getWindowById(win_id)
		if win:
			return win.getLayerForKey(layer_id,winlock)
		else:
			print_debug("WARNING: can't find layer with id: %d in window: %d" % (layer_id,win_id))
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
		tooldesc=self.toolbox.getCurToolDesc()
		if tooldesc:
			tooldesc.newModKeys(modkeys)

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

	def on_move_selection_button_clicked(self,accept=False):
		if accept:
			self.changeCurToolByName("move selection")

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
		if outfile.open(qtcore.QIODevice.Truncate|qtcore.QIODevice.WriteOnly):
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
		window=self.ui.mdiArea.addSubWindow(AnimationDrawingWindow(self,filename))
		result=qtcore.QObject.connect(window,qtcore.SIGNAL("windowStateChanged(Qt::WindowStates,Qt::WindowStates)"),window.widget().mdiWinStateChange)
		window.widget().setFileName(filename)
		window.show()

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

			window=self.ui.mdiArea.addSubWindow(BeeDrawingWindow(self,image.width(),image.height(),False,maxundo=self.config["maxundo"]))
			result=qtcore.QObject.connect(window,qtcore.SIGNAL("windowStateChanged(Qt::WindowStates,Qt::WindowStates)"),window.widget().mdiWinStateChange)
			window.widget().loadLayer(image)
			window.widget().setFileName(filename)
			window.show()

	def on_action_File_New_triggered(self,accept=True):
		if not accept:
			return
		dialog=qtgui.QDialog(self)
		dialogui=Ui_canvas_size_dialog()
		dialogui.setupUi(dialog)
		dialog.exec_()

		if dialog.result():
			width=dialogui.width_box.value()
			height=dialogui.height_box.value()

			window=self.ui.mdiArea.addSubWindow(BeeDrawingWindow(self,width=width,height=height,maxundo=self.config["maxundo"]))
			result=qtcore.QObject.connect(window,qtcore.SIGNAL("windowStateChanged(Qt::WindowStates,Qt::WindowStates)"),window.widget().mdiWinStateChange)
			window.show()

	def on_action_Edit_Configure_triggered(self,accept=True):
		if not accept:
			return

		dialog=qtgui.QDialog(self)
		dialogui=Ui_BeeMasterOptions()
		dialogui.setupUi(dialog)

		# put current values into GUI
		lock=qtcore.QWriteLocker(self.configlock)

		dialogui.history_size_box.setValue(self.config['maxundo'])

		if self.config['debug']:
			dialogui.debug_checkBox.setCheckState(qtcore.Qt.Checked)
		if self.config['autolog']:
			dialogui.autolog_checkBox.setCheckState(qtcore.Qt.Checked)
		if self.config['autosave']:
			dialogui.autosave_checkBox.setCheckState(qtcore.Qt.Checked)
		dialogui.username_entry.setText(self.config['username'])
		dialogui.server_entry.setText(self.config['server'])
		dialogui.port_spinBox.setValue(self.config['port'])
		
		ok=dialog.exec_()

		if not ok:
			return

		# get values out of GUI
		self.config['username']=dialogui.username_entry.text()
		self.config['server']=dialogui.server_entry.text()

		self.config['maxundo']=dialogui.history_size_box.value()
		self.config['port']=dialogui.port_spinBox.value()

		if dialogui.debug_checkBox.isChecked():
			self.config['debug']=True
		else:
			self.config['debug']=False

		BeeApp().debug_flags[DebugFlags.allon]=self.config['debug']

		if dialogui.autolog_checkBox.isChecked():
			self.config['autolog']=True
		else:
			self.config['autolog']=False

		if dialogui.autosave_checkBox.isChecked():
			self.config['autosave']=True
		else:
			self.config['autosave']=False

		settings=qtcore.QSettings("BeeDraw","BeeDraw")
		settings.setValue("username",self.config['username'])
		settings.setValue("maxundo",self.config['maxundo'])
		settings.setValue("debug",self.config['debug'])
		settings.setValue("autolog",self.config['autolog'])
		settings.setValue("autosave",self.config['autosave'])
		settings.setValue("server",self.config['server'])
		settings.setValue("port",self.config['port'])

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
			qtgui.QMessageBox.warning(self,"No username","You must enter a username")
			return

		socket=self.getServerConnection(username,password,hostname,port)

		if socket:
			window=self.ui.mdiArea.addSubWindow(NetworkClientDrawingWindow(self,socket,maxundo=self.config["maxundo"]))
			result=qtcore.QObject.connect(window,qtcore.SIGNAL("windowStateChanged(Qt::WindowStates,Qt::WindowStates)"),window.widget().mdiWinStateChange)
			window.show()

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
			qtgui.QMessageBox.warning(self,"Failed to connect to server",socket.errorString())
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
				qtgui.QMessageBox.warning(self,"Connection Error","server dropped connection")
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

		socket.disconnect()
		qtgui.QMessageBox.warning(self,"Server Refused Connection",message)
		return None

	def uncheckWindowLayerBox(self):
		self.ui.Window_Layers.setChecked(False)

	def checkWindowLayerBox(self):
		self.ui.Window_Layers.setChecked(True)

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

	def checkWindowPaletteBox(self):
		self.ui.Window_Palette.setChecked(True)

	def on_Window_Palette_triggered(self,state=None):
		if state==None:
			return
		if state:
			self.palettewindow.show()
		else:
			self.palettewindow.hide()

	def uncheckWindowToolOptionsBox(self):
		self.ui.Window_Tool_Options.setChecked(False)

	def checkWindowToolOptionsBox(self):
		self.ui.Window_Tool_Options.setChecked(True)

	def on_Window_Tool_Options_triggered(self,state=None):
		if state==None:
			return
		if state:
			self.tooloptionswindow.show()
		else:
			self.tooloptionswindow.hide()

	def uncheckWindowToolSelectBox(self):
		self.ui.Window_Tool_Selection.setChecked(False)

	def checkWindowToolSelectBox(self):
		self.ui.Window_Tool_Selection.setChecked(True)

	def on_Window_Tool_Selection_triggered(self,state=None):
		if state==None:
			return
		if state:
			self.toolselectwindow.show()
		else:
			self.toolselectwindow.hide()

	# destroy all subwindows
	def cleanUp(self):
		BeeApp().app.closingState()

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
		result=qtgui.QMessageBox.question(self,"Ready to Quit?","Are you sure you'd like to exit the whole application?\nAll unsaved changes will be lost.",qtgui.QMessageBox.Ok,qtgui.QMessageBox.Cancel)
		if result==qtgui.QMessageBox.Ok:
			settings=qtcore.QSettings("BeeDraw","BeeDraw")
			settings.setValue("geometry",self.saveGeometry())
			settings.setValue("windowState",self.saveState())
			self.cleanUp()
			qtgui.QMainWindow.closeEvent(self,event)
		else:
			event.ignore()

	def refreshLayersList(self,winlock=None,layerslock=None):
		if not winlock:
			winlock=qtcore.QReadLocker(self.drawingwindowslock)
		if self.layerswindow:
			if self.curwindow:
				if not layerslock:
					layerslock=qtcore.QReadLocker(self.curwindow.layerslistlock)
				self.layerswindow.refreshLayersList(self.curwindow,self.curwindow.curlayerkey,winlock)
			else:
				self.layerswindow.refreshLayersList(None,None)

	# function for a window to take the focus from other windows
	def takeFocus(self,window):
		self.setCurWindow(window)

	def updateLayerHighlight(self,win,key,lock=None):
		if self.layerswindow and key:
			self.layerswindow.refreshLayerHighlight(win,key,lock)

	# refresh thumbnail of layer with inidcated key
	def refreshLayerThumb(self,windowid,key=None):
		if self.curwindow and self.curwindow.id==windowid:
			self.layerswindow.refreshLayerThumb(key)

	# handle the custom event I created to trigger refreshing the list of layers
	def customEvent(self,event):
		if event.type()==BeeCustomEventTypes.refreshlayerslist:
			self.refreshLayersList()
		elif event.type()==BeeCustomEventTypes.displaymessage:
			self.displayMessage(event.boxtype,event.title,event.message)

	def displayMessage(self,boxtype,title,message):
		if boxtype==BeeDisplayMessageTypes.warning:
			qtgui.QMessageBox.warning(self,title,message)
		elif boxtype==BeeDisplayMessageTypes.error:
			qtgui.QMessageBox.error(self,title,message)
		else:
			print_debug("ERROR unknown box type in displayMessage")

class WindowSelectionAction(qtgui.QAction):
	def __init__(self,master,parent,windowid):
		qtgui.QAction.__init__(self,"Bee Canvas %d" % windowid,parent)
		self.windowid=windowid
		self.master=master
		qtcore.QObject.connect(self, qtcore.SIGNAL("triggered()"), self.trigger)

	def trigger(self):
		win=self.master.getWindowById(self.windowid)
		if win:
			#attempt to unhide the window if it is hidden and raise it to the top of other application windows
			win.setWindowState(win.windowState() & ~qtcore.Qt.WindowMinimized | qtcore.Qt.WindowActive)
			win.show()
			win.activateWindow()
