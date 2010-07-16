#!/usr/bin/env python
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

from hivemaster import HiveMasterWindow
import sys
import PyQt4.QtGui as qtgui

from beeapp import BeeApp

import pdb

if __name__ == "__main__":
	beeapp = BeeApp(sys.argv)
	#app = qtgui.QApplication(sys.argv)
	#beeapp.app = app
	beeapp.master = HiveMasterWindow()
	beeapp.app.exec_()
