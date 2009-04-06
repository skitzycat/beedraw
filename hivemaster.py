import sys
sys.path.append("designer")

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui
import PyQt4.QtNetwork as qtnet

from HiveMasterUi import Ui_HiveMasterSpec
from beedrawingwindow import BeeDrawingWindow
from beetypes import *
from beetools import BeeToolBox
from animation import XmlToQueueEventsConverter
from sketchlog import SketchLogWriter

from Queue import Queue
import time

class HiveMasterWindow(qtgui.QMainWindow):
	# this constructor should never be called directly, use an alternate
	def __init__(self,app):
		qtgui.QMainWindow.__init__(self)
		self.app=app

		# set defaults
		self.port=8333

		# Initialize values
		self.nextclientid=1
		self.nextclientidmutex=qtcore.QMutex()

		self.password=""

		# setup interface
		self.ui=Ui_HiveMasterSpec()
		self.ui.setupUi(self)
		self.show()

		# setup queues used for all thread communication
		self.routinginput=Queue(0)
		self.routingthread=HiveRoutingThread(self)
		self.routingthread.start()

		# this will be keyed on the client ids and values will be queue objects
		self.clientwriterqueues={}

		# this dictionary will be keyed on id and map to the username
		self.clientnames={}

		# default value stuff that needs to be here
		self.toolbox=BeeToolBox()
		self.fgcolor=qtgui.QColor(0,0,0)
		self.bgcolor=qtgui.QColor(255,255,255)

		# drawing window which holds the current state of the network session
		self.window=BeeDrawingWindow(self,600,400,False,WindowTypes.standaloneserver)

	# since there should only be one window just return 1
	def getNextWindowId(self):
		return 1

	def getWindowById(self,id):
		return self.window

	def getLayerById(self,win_id,layer_id):
		return self.window.getLayerByKey()

	def registerWindow(self,window):
		pass

	# needs to be implemented so this can be a window controller
	def refreshThumb(self):
		return
	# needs to be implemented so this can be a window controller
	def refreshLayerThumb(self,key):
		return

	def getToolClassByName(self,name):
		return self.toolbox.getToolDescByName(name)

	def getCurToolInst(self,window):
		curtool=self.getCurToolDesc()
		return curtool.setupTool(window)

	def getCurToolDesc(self):
		return self.toolbox.getCurToolDesc()

	# alternate constuctor to create a standalone server
	def standAloneServer(app):
		master=HiveMasterWindow(app)
		master.standalonemode=True
		# this serves as both the window and the master
		master.master=master
		master.layers=[]
		master.servergui=master
		master.serverthread=None

	standAloneServer=staticmethod(standAloneServer)

	def registerClient(self,username,id):
		self.clientwriterqueues[id]=Queue(100)
		self.clientnames[id]=username
		self.servergui.ui.clientsList.addItem(username)

	def unregisterClient(self,id):
		if not self.clientnames.has_key(id):
			return

		# remove from dictionary of clients
		username=self.clientnames[id]
		del self.clientnames[id]

		# remove from gui
		items=self.servergui.ui.clientsList.findItems(username,qtcore.Qt.MatchFixedString)
		for item in items:
			index=self.servergui.ui.clientsList.row(item)
			self.servergui.ui.clientsList.takeItem(index)

		# set layers owned by that client to unowned (do this eventually)

	def closeEvent(self,event):
		qtgui.QMainWindow.closeEvent(self,event)
#		self.stopServer()

	def startServer(self):
		# make sure no other instance is running
		self.stopServer()

		self.serverthread=HiveServerThread(self,self.port)
		self.serverthread.start()
		self.servergui.ui.statusLabel.setText("Serving on port %d" % self.port )

	def stopServer(self):
		if self.serverthread:
			#self.serverthread.terminate()
			#self.serverthread.quit()
			self.serverthread.exit()
			self.serverthread.wait()
			self.serverthread=None
			self.servergui.ui.statusLabel.setText("Serving not running")

	def on_kick_button_pressed(self):
		curselection=self.ui.clientsList.selectedIndexes()
		# if there are any items in the list that means that something was selected
		if curselection:
			target=curselection[0].data().toString()
			print "should kick off:", target
			self.kickClient(target)

	def kickClient(name):
		# first find the ID of the client
		id=None
		for i in self.clientnames.keys():
			if self.clientnames[i]==name:
				id=i
				break

		# if the client isn't in the list just do nothing
		if not id:
			return

	def on_actionStart_triggered(self,accept=True):
		if accept:
			self.startServer()

	def on_actionStop_triggered(self,accept=True):
		if accept:
			self.stopServer()

# thread to setup connection, authenticate and then
# listen to a socket and add incomming client commands to queue
class HiveClientListener(qtcore.QThread):
	def __init__(self,parent,socket,master,id):
		qtcore.QThread.__init__(self,parent)
		self.socket=socket

		self.master=master
		self.id=id

	def authenticate(self):
		# attempt to read stream of data, which should include version, username and password
		# make sure someone dosen't overload the buffer while wating for authentication info
		authstring=qtcore.QString()
		while authstring.count('\n')<3 and len(authstring)<100:
			if self.socket.waitForReadyRead(-1):
				data=self.socket.read(100)
				authstring.append(data)

			# if error exit
			else:
				print "Recieved error:", self.socket.error(), "when reading from socket"
				self.socket.write(qtcore.QByteArray("Authentication Failed"))
				return False

		authlist=authstring.split('\n')

		# if loop ended without getting enough separators just return false
		if len(authlist)<3:
			return False

		self.username=authlist[0]
		password=authlist[1]
		version=authlist[2]

		# if password is blank, let authentication pass
		if self.master.password=="":
			return True

		# otherwise trim off whitespace and compare to password string
		if password.trimmed().toAscii()==self.master.password:
			return True

		return False

	def register(self):
		# register this new connection
		self.master.registerClient(self.username,self.id)

	def disconnected(self):
		self.master.unregisterClient(self.id)

	def readyRead(self):
		while self.socket.bytesAvailable():
			data=self.socket.read(1024)
			print "recieved data from client: %s" % qtcore.QString(data)
			self.parser.xml.addData(data)
			self.parser.read()

	def run(self):
		# try to authticate user
		if not self.authenticate():
			# if authentication fails send close socket and exit
			print "authentication failed"
			self.socket.write(qtcore.QByteArray("Authtication failed\n"))
			self.socket.disconnectFromHost()
			self.socket.waitForDisconnected(1000)
			return

		print "authentication succeded"

		self.register()
		print "registered"
		self.parser=XmlToQueueEventsConverter(None,self.master.window,0,type=ThreadTypes.server,id=self.id)
		print "created parser"

		# pass initial data to client here
		self.socket.write(qtcore.QByteArray("%d\n%d\n%d\n" % (self.master.window.docwidth,self.master.window.docheight,self.id)))

		# wait for client to respond so it doesn't get confused and mangle the setup data with the start of the XML file
		self.socket.waitForReadyRead(-1)
		print "got client response"
		qtcore.QObject.connect(self.socket, qtcore.SIGNAL("readyRead()"), self.readyRead)
		qtcore.QObject.connect(self.socket, qtcore.SIGNAL("disconnected()"), self.disconnected)

		# start writing thread
		newwriter=HiveClientWriter(self,self.socket,self.master,self.id)
		newwriter.start()

		# start event loop
		print "starting event loop"
		self.exec_()

# this thread will write to a specific client
class HiveClientWriter(qtcore.QThread):
	def __init__(self,parent,socket,master,id):
		#qtcore.QThread.__init__(self,parent)
		qtcore.QThread.__init__(self)
		self.setParent(self)

		self.socket=socket
		self.master=master
		self.id=id

		self.queue=self.master.clientwriterqueues[id]
		self.xmlgenerator=SketchLogWriter(self.socket)

	def run(self):
		self.xmlgenerator.logCreateDocument(self.master.window.docwidth,self.master.window.docheight)
		while 1:
			data=self.queue.get()
			self.xmlgenerator.logCommand(data)

# class to handle running the TCP server and handling new connections
class HiveServerThread(qtcore.QThread):
	def __init__(self,master,port=8333):
		qtcore.QThread.__init__(self,master)
		self.sockets=[]
		self.threads=[]
		self.port=port
		self.master=master
		self.nextid=1

		# connect the signals we want
		qtcore.QObject.connect(self, qtcore.SIGNAL("finished()"), self.finished)
		qtcore.QObject.connect(self, qtcore.SIGNAL("started()"), self.started)

	def started(self):
		# needs to be done here because this is running in the proper thread
		self.server=qtnet.QTcpServer(self)

		# tell me when the server has gotten a new connection
		qtcore.QObject.connect(self.server, qtcore.SIGNAL("newConnection()"), self.newConnection)

		ret=self.server.listen(qtnet.QHostAddress("0.0.0.0"),self.port)

	def finished(self):
		print "in finished"

	def run(self):
		self.exec_()

	# signal for the server getting a new connection
	def newConnection(self):
		print "found new connection"
		while self.server.hasPendingConnections():
			newsock=self.server.nextPendingConnection()
			self.sockets.append(newsock)

			# start the listener, that will authenticate client and finish setup
			newlistener=HiveClientListener(self,newsock,self.master,self.nextid)
			self.nextid+=1

			# push responsibility to new thread
			newsock.setParent(None)
			newsock.moveToThread(newlistener)

			newlistener.start()

# this thread will route communication as needed between client listeners, the gui and client writers
class HiveRoutingThread(qtcore.QThread):
	def __init__(self,master):
		qtcore.QThread.__init__(self,master)
		self.master=master
		self.queue=master.routinginput

	def run(self):
		while 1:
			data=self.queue.get()
			print "routing info recieved:", data
			(command,owner)=data
			# a negative number is a flag that we only send it to one client
			if owner<0:
				self.sendToSingleClient(abs(owner),command)
			elif command[0]==DrawingCommandTypes.alllayer:
				self.sendToAllClients(command)
			else:
				self.sendToAllButOwner(owner,command)

	# I'd eventually put a check in here for if the queue is full and if so clear the queue and replace it with a raw event update to the current state
	def sendToAllClients(self,command):
		for id in self.master.clientwriterqueues.keys():
			print "sending to client:", id
			self.master.clientwriterqueues[id].put(command)

	def sendToAllButOwner(self,source,command):
		print "sending command to all, but the owner:", source, command
		for id in self.master.clientwriterqueues.keys():
			if source!=id:
				print "sending to client:", id
				self.master.clientwriterqueues[id].put(command)

	def sendToSingleClient(self,id,command):
		if self.master.clientwriterqueues.has_key(id):
			self.master.clientwriterqueues[id].put(command)
		else:
			print "WARNING: Can't find client", id, "for sending data to"
