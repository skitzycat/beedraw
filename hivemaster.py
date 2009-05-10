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
from abstractbeemaster import AbstractBeeMaster
from hivestate import HiveSessionState

from Queue import Queue
import time

class HiveMasterWindow(qtgui.QMainWindow, AbstractBeeMaster):
	# this constructor should never be called directly, use an alternate
	def __init__(self):
		qtgui.QMainWindow.__init__(self)
		AbstractBeeMaster.__init__(self)

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

		# set up client list mutex for messing with either of the above 2 dictinoaries
		self.clientslistmutex=qtcore.QReadWriteLock()

		# default value stuff that needs to be here
		self.fgcolor=qtgui.QColor(0,0,0)
		self.bgcolor=qtgui.QColor(255,255,255)

		# drawing window which holds the current state of the network session
		self.curwindow=HiveSessionState(self,600,400,WindowTypes.standaloneserver,20)

		self.curwindow.startRemoteDrawingThreads()

		self.layers=[]
		self.serverthread=None

	# since there should only be one window just return 1
	def getNextWindowId(self):
		return 1

	def getWindowById(self,id):
		return self.curwindow

	def getToolClassByName(self,name):
		return self.toolbox.getToolDescByName(name)

	def registerClient(self,username,id):
		lock=qtcore.QWriteLocker(self.clientslistmutex)
		self.clientwriterqueues[id]=Queue(100)
		self.clientnames[id]=username
		self.ui.clientsList.addItem(username)

		command=(DrawingCommandTypes.networkcontrol,NetworkControlCommandTypes.resyncrequest)
		self.curwindow.addResyncRequestToQueue(id)

	def unregisterClient(self,id):
		lock=qtcore.QReadLocker(self.clientslistmutex)
		if not id in self.clientnames:
			return

		# remove from dictionary of clients
		username=self.clientnames[id]
		del self.clientnames[id]

		# remove from gui
		items=self.ui.clientsList.findItems(username,qtcore.Qt.MatchFixedString)
		for item in items:
			index=self.ui.clientsList.row(item)
			self.ui.clientsList.takeItem(index)

		# set layers owned by that client to unowned (do this eventually)

	def closeEvent(self,event):
		qtgui.QMainWindow.closeEvent(self,event)
#		self.stopServer()

	def startServer(self):
		# make sure no other instance is running
		self.stopServer()

		self.serverthread=HiveServerThread(self,self.port)
		self.serverthread.start()
		self.ui.statusLabel.setText("Serving on port %d" % self.port )

	def stopServer(self):
		if self.serverthread:
			#self.serverthread.terminate()
			#self.serverthread.quit()
			self.serverthread.exit()
			self.serverthread.wait()
			self.serverthread=None
			self.ui.statusLabel.setText("Serving not running")

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
		print "disconnecting client with ID:", self.id
		self.master.unregisterClient(self.id)

	def readyRead(self):
		readybytes=self.socket.bytesAvailable()

		if readybytes>0:
			data=self.socket.read(readybytes)
			print "got animation data from socket: %s" % qtcore.QString(data)
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
		self.parser=XmlToQueueEventsConverter(None,self.master.curwindow,0,type=ThreadTypes.server,id=self.id)
		print "created parser"

		# pass initial data to client here
		self.socket.write(qtcore.QByteArray("Success\nConnected To Server\n"))

		# wait for client to respond so it doesn't get confused and mangle the setup data with the start of the XML file
		self.socket.waitForReadyRead(-1)
		print "got client response"

		#qtcore.QObject.connect(self.socket, qtcore.SIGNAL("readyRead()"), self.readyRead)
		#qtcore.QObject.connect(self.socket, qtcore.SIGNAL("disconnected()"), self.disconnected)

		# start writing thread
		newwriter=HiveClientWriter(self,self.socket,self.master,self.id)
		newwriter.start()

		# while the "correct" way to do this might be to start an event loop, but for some reason that causes the socket to not read correctly.   It was reading the same data multiple times like it was reading before it had a chance to reset.
		while 1:
			# make sure we've waited long enough
			self.socket.waitForReadyRead(-1)
			self.readyRead()
			if self.socket.state() != qtnet.QAbstractSocket.ConnectedState:
				break

		# after the socket has closed make sure there isn't more to read
		self.readyRead()

		# this should be run when the socket is disconnected
		self.disconnected()


# this thread will write to a specific client
class HiveClientWriter(qtcore.QThread):
	def __init__(self,parent,socket,master,id):
		#qtcore.QThread.__init__(self,parent)
		qtcore.QThread.__init__(self)
		self.setParent(self)

		self.socket=socket
		self.master=master
		self.id=id

		lock=qtcore.QReadLocker(self.master.clientslistmutex)
		self.queue=self.master.clientwriterqueues[id]
		self.xmlgenerator=SketchLogWriter(self.socket)

	def run(self):
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
			elif command[0]==DrawingCommandTypes.alllayer or command[0]==DrawingCommandTypes.networkcontrol:
				self.sendToAllClients(command)
			else:
				self.sendToAllButOwner(owner,command)

	# I'd eventually put a check in here for if the queue is full and if so clear the queue and replace it with a raw event update to the current state
	def sendToAllClients(self,command):
		lock=qtcore.QReadLocker(self.master.clientslistmutex)
		for id in self.master.clientwriterqueues.keys():
			print "sending to client:", id
			self.master.clientwriterqueues[id].put(command)

	def sendToAllButOwner(self,source,command):
		lock=qtcore.QReadLocker(self.master.clientslistmutex)
		print "sending command to all, but the owner:", source, command
		for id in self.master.clientwriterqueues.keys():
			if source!=id:
				print "sending to client:", id
				self.master.clientwriterqueues[id].put(command)

	def sendToSingleClient(self,id,command):
		lock=qtcore.QReadLocker(self.master.clientslistmutex)
		if id in self.master.clientwriterqueues:
			self.master.clientwriterqueues[id].put(command)
		else:
			print "WARNING: Can't find client", id, "for sending data to"
