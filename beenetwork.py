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
import PyQt4.QtNetwork as qtnet

import socket

try:
	from PyQt4.QtXml import QXmlStreamReader
except:
	from PyQt4.QtCore import QXmlStreamReader

import SocketServer

from animation import XmlToQueueEventsConverter
from sketchlog import SketchLogWriter

from beetypes import *
from beeutil import *
 
class PyServerEventHandler(SocketServer.BaseRequestHandler):
	def __init__(self,request,client_address,server,master,parentthread,id):
		self.master=master
		self.parentthread=parentthread
		self.clientid=id
		self.server=server
		SocketServer.BaseRequestHandler.__init__(self,request,client_address,server)

	def handle(self):
		newsock=BeeSocket(BeeSocketTypes.python,self.request,True)
		# start the listener, that will authenticate client and finish setup

		curthread=qtcore.QThread.currentThread()
		threadparent=curthread.parent()

		newlistener=HiveClientListener(self.server,newsock,self.master,self.clientid)
		newlistener.start()

class customPyServer(SocketServer.TCPServer,qtcore.QObject):
	def __init__(self,hostport,master,parentthread):
		qtcore.QObject.__init__(self)
		SocketServer.TCPServer.__init__(self,hostport,PyServerEventHandler)
		self.master=master
		self.parentthread=parentthread
		self.idlock=qtcore.QReadWriteLock()
		self.nextid=0

	def getNextId(self):
		lock=qtcore.QWriteLocker(self.idlock)
		self.nextid+=1
		return self.nextid

	def finish_request(self,request,client_address):
		PyServerEventHandler(request,client_address,self,self.master,self.parentthread,self.getNextId())

	# dont' close the request after we're done in here
	def close_request(self,request):
		pass

class BeeTCPServer(qtcore.QObject):
	""" Socket interface to allow changing between different tcp server implementations to see if Qt sockets or standard python sockets are better on each platform."""
	def __init__(self,type,port,parentthread,master):
		if type==BeeSocketTypes.qt:
			qtcore.QObject.__init__(self,parentthread)
		self.type=type
		self.parentthread=parentthread
		self.master=master
		self.port=port
		self.idlock=qtcore.QReadWriteLock()
		self.nextid=0

	def getNextId(self):
		lock=qtcore.QWriteLocker(self.idlock)
		self.nextid+=1
		return self.nextid

	def start(self):
		if self.type==BeeSocketTypes.qt:
			self.server=qtnet.QTcpServer(self.parentthread)
			qtcore.QObject.connect(self.server, qtcore.SIGNAL("newConnection()"), self.newConnectionQt)
			if self.server.listen(qtnet.QHostAddress("0.0.0.0"),self.port):
				event=HiveServerStatusEvent(HiveServerStatusTypes.running)
			else:
				event=HiveServerStatusEvent(HiveServerStatusTypes.starterror,"%s" % self.server.errorString())

			BeeApp().app.postEvent(self.master,event)

		elif self.type==BeeSocketTypes.python:
			try:
				self.server=customPyServer(("localhost",self.port),self.master,self.parentthread)
			except:
				self.server=None
				event=HiveServerStatusEvent(HiveServerStatusTypes.starterror)
				BeeApp().app.postEvent(self.master,event)
				print_debug("WARNING: failed to create server")

			if self.server:
				event=HiveServerStatusEvent(HiveServerStatusTypes.running)
				BeeApp().app.postEvent(self.master,event)
				self.server.serve_forever()

	def stop(self):
		if self.server:
			if self.type==BeeSocketTypes.qt:
				self.server.close()
			elif self.type==BeeSocketTypes.python:
				self.server.shutdown()
				self.server.socket.close()

	def newConnectionQt(self):
		print_debug("found new connection")
		while self.server.hasPendingConnections():
			newsock=BeeSocket(BeeSocketTypes.qt,self.server.nextPendingConnection())

			# start the listener, that will authenticate client and finish setup
			newlistener=HiveClientListener(self.parentthread,newsock,self.master,self.getNextId())

			# push responsibility to new thread
			newsock.socket.setParent(None)
			newsock.socket.moveToThread(newlistener)

			newlistener.start()

class BeeSocket:
	""" Socket interface to allow changing between different socket implementations to see if Qt socket or standard python sockets are better.  Also helps provide blocking interface to Qt sockets which are normally non-blocking. """
	def __init__(self,type,socket,connected=False):
		self.type=type
		self.socket=socket
		self.errorStr=""
		self.connected=connected

		# set blocking to never time out
		if self.type==BeeSocketTypes.python:
			self.socket.settimeout(None)

	def waitForConnected(self):
		if self.type==BeeSocketTypes.qt:
			connected=self.socket.waitForConnected()
			return connected
		elif self.type==BeeSocketTypes.python:
			return self.connected

	def errorString(self):
		if self.type==BeeSocketTypes.qt:
			return self.socket.errorString()
		elif self.type==BeeSocketTypes.python:
			return self.errorStr

	def disconnect(self):
		if self.type==BeeSocketTypes.qt:
			self.socket.disconnectFromHost()
			self.socket.waitForDisconnected(1000)
		elif self.type==BeeSocketTypes.python:
			self.socket.close()

	def abort(self):
		if self.type==BeeSocketTypes.qt:
			self.socket.abort()

	def connect(self,host,port):
		if self.type==BeeSocketTypes.qt:
			self.socket.connectToHost(host,port)
			return self.socket.waitForConnected()
		elif self.type==BeeSocketTypes.python:
			try:
				self.socket.connect((host,port))
				self.connected=True
			except socket.error, errmsg:
				print_debug("error while connecting: %s" % errmsg)
				self.connected=False
			except:
				self.errorStr="unknown connection error"
				self.connected=False

			return self.connected

	def read(self,size):
		retstring=""
		if self.type==BeeSocketTypes.qt:
			# only wait if there isn't data already available
			if not self.socket.bytesAvailable():
				status=self.socket.waitForReadyRead(-1)
			data=self.socket.read(size)
			if data:
				retstring="%s" % qtcore.QString(data)
		elif self.type==BeeSocketTypes.python:
			try:
				retstring=self.socket.recv(size)

			except socket.error, errmsg:
				print_debug("exception while trying to read data: %s" % errmsg)
				self.connected=False
				
			except:
				print_debug("unknown error while trying to read data")
				self.connected=False
				retstring=""

		return retstring

	def isConnected(self):
		if self.type==BeeSocketTypes.qt:
			if self.socket.state()==qtnet.QAbstractSocket.UnconnectedState:
				return False
			else:
				return True
		elif self.type==BeeSocketTypes.python:
			return self.connected

	def write(self,data):
		if not data:
			return
		if self.type==BeeSocketTypes.qt:
			self.socket.write(data)
			self.socket.flush()
			self.socket.waitForBytesWritten(-1)
		elif self.type==BeeSocketTypes.python:
			try:
				self.socket.sendall(data)

			except socket.error, errmsg:
				print_debug("exception while trying to send data: %s" % errmsg)
				self.connected=False
				
			except:
				print_debug("unknown exception while trying to send data")
				self.connected=False

# thread to setup connection, authenticate and then
# listen to a socket and add incomming client commands to queue
class HiveClientListener(qtcore.QThread):
	def __init__(self,parent,socket,master,id):
		qtcore.QThread.__init__(self,parent)
		self.socket=socket

		self.master=master
		self.id=id

		self.authenticationerror="Unknown Error"

	def authenticate(self):
		# attempt to read stream of data, which should include version, username and password
		# make sure someone dosen't overload the buffer while wating for authentication info
		authstring=qtcore.QString()
		while authstring.count('\n')<3 and len(authstring)<512:
			data=self.socket.read(512)
			if data:
				authstring.append(data)

			# if error exit
			else:
				self.authenticationerror="Error: Lost connection during authentication request"
				return False

		authlist=authstring.split('\n')

		# if loop ended without getting enough separators just return false
		if len(authlist)<3:
			self.authenticationerror="Error parsing authentication information"
			return False

		self.username=authlist[0]
		password=authlist[1]
		try:
			version=int(authlist[2])
		except ValueError:
			self.authenticationerror="Error parsing authentication information"
			return False

		if version != PROTOCOL_VERSION:
			self.authenticationerror="Protocol version mismatch, please change to server version: %d" % PROTOCOL_VERSION
			return False

		masterpass=self.master.getPassword()

		# if password is blank, let authentication pass
		if masterpass=="":
			return True

		# otherwise trim off whitespace and compare to password string
		if password.trimmed().toAscii()==masterpass:
			return True

		self.authenticationerror="Incorrect Password"
		return False

	def register(self):
		# register this new connection
		self.master.registerReaderThread(self.id,self)
		return self.master.registerClient(self.username,self.id,self.socket)

	def disconnected(self):
		print_debug("disconnecting client with ID: %d" % self.id)
		self.master.unregisterClient(self.id)

	def readyRead(self):
		data=self.socket.read(readybytes)
		#print_debug("got animation data from socket: %s" % qtcore.QString(data))
		self.parser.xml.addData(data)
		error=self.parser.read()

		self.socket.waitForBytesWritten()

		if error!=QXmlStreamReader.PrematureEndOfDocumentError and error!=QXmlStreamReader.NoError:
			return error

		return None

	def run(self):
		# try to authticate user
		if not self.authenticate():
			# if authentication fails send close socket and exit
			print_debug("authentication failed")
			self.socket.write(qtcore.QByteArray("Authtication failed\n%s\n" % self.authenticationerror))
			self.socket.disconnect()
			return

		print_debug("authentication succeded")

		if not self.register():
			print_debug("Registration with server failed, probably due to duplicate username")
			self.socket.write(qtcore.QByteArray("Registration Failed\nRegistration with server failed, the username you chose is already in use already, try a different one\n"))
			self.socket.disconnect()
			return

		self.parser=XmlToQueueEventsConverter(None,self.master.curwindow,0,type=ThreadTypes.server,id=self.id)

		# pass initial data to client here
		self.socket.write(qtcore.QByteArray("Success\nConnected To Server\n"))

		# wait for client to respond so it doesn't get confused and mangle the setup data with the start of the XML file
		data=self.socket.read(1024)

		#qtcore.QObject.connect(self.socket, qtcore.SIGNAL("readyRead()"), self.readyRead)
		#qtcore.QObject.connect(self.socket, qtcore.SIGNAL("disconnected()"), self.disconnected)

		# start writing thread
		newwriter=HiveClientWriter(self,self.socket,self.master,self.id)
		newwriter.start()

		while 1:
			if not data:
				print_debug("remote socket closed")
				break

			#print_debug("got animation data from socket: %s" % qtcore.QString(data))
			self.parser.xml.addData(data)
			error=self.parser.read()

			if error!=QXmlStreamReader.PrematureEndOfDocumentError and error!=QXmlStreamReader.NoError:
				# queue up command for client to be disconnected
				break

			if not self.socket.isConnected():
				print_debug("found that socket isn't connected")
				break

			data=self.socket.read(1024)
		# this should be run when the socket is disconnected
		self.disconnected()

# this thread will write to a specific client
class HiveClientWriter(qtcore.QThread):
	def __init__(self,parent,socket,master,id):
		qtcore.QThread.__init__(self)
		self.setParent(self)

		self.socket=socket
		self.master=master
		self.id=id

		self.master.registerWriterThread(id,self)

		self.buffer=qtcore.QBuffer()
		self.buffer.open(qtcore.QIODevice.ReadWrite)

		# add to list of writing threads
		lock=qtcore.QReadLocker(self.master.clientslistmutex)
		self.queue=self.master.clientwriterqueues[id]

		# create custom QXmlStreamWriter
		#self.xmlgenerator=SketchLogWriter(self.socket)

		self.xmlgenerator=SketchLogWriter(self.buffer)

		#print "attempting to connect signal"
		#self.connect(self.queue,qtcore.SIGNAL("datainqueue()"),self,qtcore.SIGNAL("datainqueue()"))
		#print "attempted to connect signal"

	def run(self):
		while 1:
			if not self.socket.isConnected():
				self.master.unregisterClient(self.id)
				return

			#print "Hive Client Writer is ready to read from queue:", self.queue
			# block until item is available from thread safe queue
			data=self.queue.get()
			if data[0]==DrawingCommandTypes.quit:
				self.master.unregisterClient(self.id)
				return
			#print "Hive Client Writer got command from Queue:", data
			# write xml data to socket
			self.xmlgenerator.logCommand(data)

			datastr="%s" % qtcore.QString(self.buffer.data())
			#print_debug("client writer wrote to sending buffer: %s" % datastr)
			self.socket.write(datastr)
			self.buffer.buffer().resize(0)
			self.buffer.seek(0)
