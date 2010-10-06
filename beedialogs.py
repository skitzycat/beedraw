#    Beedraw/Hive network capable client and server allowing collaboration on a single image
#    Copyright (C) 2010 Thomas Becker
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

import sys
sys.path.append("designer")

import PyQt4.QtCore as qtcore
import PyQt4.QtGui as qtgui

from ImageScaleDialog import Ui_CanvasScaleDialog

class BeeScaleImageDialog(qtgui.QDialog):
	def __init__(self,parent,width,height):
		qtgui.QDialog.__init__(self,parent)
		self.ui=Ui_CanvasScaleDialog()
		self.ui.setupUi(self)

		self.ratiolock=False

		self.startwidth=width
		self.startheight=height

		self.curwidth=width
		self.curheight=width

		self.ui.width_spin_box.setValue(width)
		self.ui.height_spin_box.setValue(height)

	def on_width_spin_box_editingFinished(self):
		newval=self.ui.width_spin_box.value()
		if self.ratiolock and newval and newval != self.curwidth:
			self.curheight=(newval*self.startheight)/self.startwidth
			self.ui.height_spin_box.setValue(self.curheight)

		self.curwidth=newval

	def on_height_spin_box_editingFinished(self):
		newval=self.ui.height_spin_box.value()
		if self.ratiolock and newval and newval != self.curheight:
			self.curwidth=(newval*self.startwidth)/self.startheight
			self.ui.width_spin_box.setValue(self.curwidth)

		self.curheight=newval

	def on_lock_ratio_checkBox_toggled(self,val):
		self.ratiolock=val
		if self.ratiolock:
			self.curheight=(self.curwidth*self.startheight)/self.startwidth
			self.ui.height_spin_box.setValue(self.curheight)
