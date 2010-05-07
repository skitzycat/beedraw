import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore

import os

from beeglobals import BEE_CONFIG_DIR
from colorswatch import *

from beesave import PaletteXmlWriter,BeeToolConfigWriter,BeeMasterConfigWriter
from beeload import PaletteParser,BeeToolConfigParser

from BeePaletteUi import Ui_PaletteWindow

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

class PaletteWindow(qtgui.QMainWindow):
	def __init__(self,master):
		qtgui.QMainWindow.__init__(self,master.topwinparent)
		self.setAttribute(qtcore.Qt.WA_DeleteOnClose,False)
		self.master=master

		self.ui=Ui_PaletteWindow()
		self.ui.setupUi(self)
		self.show()

		self.ui.swatch_frame=BeeSwatchScrollArea(self.master,self.ui.swatch_frame)

		self.ui.FGSwatch=FGSwatch(master,replacingwidget=self.ui.FGSwatch)
		self.setFGColor(qtgui.QColor(0,0,0))

		self.ui.BGSwatch=BGSwatch(master,replacingwidget=self.ui.BGSwatch)
		self.setBGColor(qtgui.QColor(255,255,255))

		# read in pallette file
		palfilename=os.path.join(BEE_CONFIG_DIR,"config/default.pal")
		palfile=qtcore.QFile(palfilename)
		if palfile.exists():
			palfile.open(qtcore.QIODevice.ReadOnly)
			reader=PaletteParser(palfile)
			colors=reader.getColors()
		else:
			colors=[]

		self.ui.swatch_frame.setupSwatches(colors)

	def closeEvent(self,event):
		event.ignore()
		self.hide()

	def setFGColor(self,color):
		self.ui.FGSwatch.updateColor(color)

	def setBGColor(self,color):
		self.ui.BGSwatch.updateColor(color)

	def hideEvent(self,event):
		if not self.isMinimized():
			self.master.uncheckWindowPaletteBox()
		return qtgui.QWidget.hideEvent(self,event)

	def on_Palette_save_triggered(self,accept=True):
		if not accept:
			return

		filename=qtgui.QFileDialog.getSaveFileName(self,"Choose File Name",".","Palette save (*.pal)")
		if not filename:
			return
		if filename[-4:] != ".pal":
			filename+=".pal"
		outfile=qtcore.QFile(filename)
		outfile.open(qtcore.QIODevice.WriteOnly)
		writer=PaletteXmlWriter(outfile)
		writer.logPalette(self.ui.swatch_frame.swatches)

	def on_Palette_load_triggered(self,accept=True):
		if not accept:
			return

		filename=qtgui.QFileDialog.getOpenFileName(self,"Choose Palette File To Load",".","Palette save (*.pal)")
		if not filename:
			return

		infile=qtcore.QFile(filename)
		infile.open(qtcore.QIODevice.ReadOnly)
		reader=PaletteParser(infile)
		colors=reader.getColors()
		self.ui.swatch_frame.setupSwatches(colors)
