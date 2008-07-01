import sys
sys.path.append("designer")

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui
import PyQt4.QtNetwork as qtnet

from HiveMasterUi import Ui_HiveMasterSpec

from Queue import Queue
import time

class HiveMasterWindow(qtgui.QMainWindow):
	# this constructor should never be called directly, use an alternate
	def __init__(self,app):
		qtgui.QMainWindow.__init__(self)
		self.app=app

		# Initialize values
		self.connections=[]
		self.nextclientid=1
		self.nextclientidmutex=qtcore.QMutex()

		self.password=""

		# setup interface
		self.ui=Ui_HiveMasterSpec()
		self.ui.setupUi(self)
		self.show()

		# replace custom widget

		# setup queues used for all thread communication
		self.routinginput=Queue(100)

		# this will be keyed on the client ids and values will be queue objects
		self.clientwriterqueues={}

		# this dictionary will be keyed on id and map to the username
		self.clientnames={}

	# alternate constuctor to create a standalone server
	def standAloneServer(app):
		master=HiveMasterWindow(app)
		master.standalonemode=True
		# this serves as both the window and the master
		master.master=master
		master.layers=[]
		
		master.serverthread=None

		master.startServer()

	standAloneServer=staticmethod(standAloneServer)

	def registerClient(self):
		lock=qtcore.QMutexLocker(self.nextclientidmutex)
		newid=self.nextclientid
		self.nextclientid+=1
		lock.unlock()
		self.clientwriterqueues[newid]=Queue(100)
		return newid

	def closeEvent(self,event):
		qtgui.QMainWindow.closeEvent(self,event)
#		self.stopServer()

	def startServer(self):
		# make sure no other instance is running

		self.stopServer()
		self.serverthread=HiveServerThread(self)
		self.serverthread.start()

	def stopServer(self):
		if self.serverthread:
			self.serverthread.terminate()
			self.serverthread.wait()
			self.serverthread=None

# thread to setup connection, authenticate and then
# listen to a socket and add incomming client commands to queue
class HiveClientListener(qtcore.QThread):
	def __init__(self,parent,socket,master,id):
		#qtcore.QThread.__init__(self,parent)
		qtcore.QThread.__init__(self)
		self.socket=socket

		self.master=master
		self.id=id

		self.outputqueue=master.routinginput

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
		# register this new connection and get an id for it
		id=self.master.registerClient(self.username)
		# start writing thread
		newwriter=HiveClientWriter(self,newsock,self.master,id)
		newwriter.start()

	# pass initial setup data to new client
	def setupNewClient(self):
		self.socket.write(qtcore.QByteArray("Document Dimensions\n400\n600\n"))

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

		# pass initial data to client here
		self.setupNewClient()

		while 1:
			# wait for data ready to read or an erro
			if self.socket.waitForReadyRead(-1):
				curdata=self.socket.readAll()
				s=qtcore.QString(curdata).toAscii()
				print "recived data:", s

			# if error exit
			else:
				print "Recieved error:", self.socket.error(), "when reading from socket"
				return

# this thread will write to a specific client
class HiveClientWriter(qtcore.QThread):
	def __init__(self,parent,socket,master,id):
		qtcore.QThread.__init__(self,master)

		self.socket=socket
		self.master=master
		self.id=id

		self.queue=self.master.clientwriterqueues[id]

	def run(self):
		while 1:
			data=self.queue.get()
			self.socket.write(data)

# class to handle running the TCP server and handling new connections
class HiveServerThread(qtcore.QThread):
	def __init__(self,master,port=8333):
		qtcore.QThread.__init__(self,master)
		self.sockets=[]
		self.threads=[]
		self.port=port
		self.master=master

	#def on_finished(self):
	#	print "running server thread cleanup"
	#	self.server.close()
	#	qtcore.QThread.finished(self)

	def run(self):
		self.server=qtnet.QTcpServer()
		ret=self.server.listen(qtnet.QHostAddress("0.0.0.0"),self.port)

		while 1:
			available,timeout=self.server.waitForNewConnection(-1)

			if available:
				print "found new connection"
				newsock=self.server.nextPendingConnection()
				self.sockets.append(newsock)

				# start the listener, that will authenticate client and finish setup
				newlistener=HiveClientListener(self,newsock,self.master,id)

				# push responsibility to new thread
				newsock.setParent(None)
				newsock.moveToThread(newlistener)

				newlistener.start()

# this thread will route communication as needed between client listeners, the gui and client writers
class HiveRoutingThread(qtcore.QThread):
	def __init__(self,master):
		qtcore.QThread.__init__(self,master)
