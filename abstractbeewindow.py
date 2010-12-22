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
import PyQt4.QtGui as qtgui

import os

class AbstractBeeDockWindow(qtgui.QDockWidget):
	""" Base class for every non-master displayed window in the bee application """
	def __init__(self,master):
		qtgui.QDockWidget.__init__(self,master)
		self.master=master
		self.setAttribute(qtcore.Qt.WA_QuitOnClose,False)

	def keyPressEvent(self,event):
		self.master.keyEvent(event)

	def keyReleaseEvent(self,event):
		self.master.keyEvent(event)
