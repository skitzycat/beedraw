import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore

import os

from beeglobals import BEE_CONFIG_DIR
from colorswatch import *

from abstractbeewindow import AbstractBeeDockWindow
from beeutil import *

from beesave import PaletteXmlWriter,BeeToolConfigWriter,BeeMasterConfigWriter
from beeload import PaletteParser,BeeToolConfigParser

from PaletteOptionsDialogUi import Ui_Pallete_Config_Dialog

from BeePaletteUi import Ui_PaletteWindow
from BeePaletteDockUi import Ui_BeePaletteDock

class BeeSwatchScrollArea(qtgui.QScrollArea):
	def __init__(self,master,colors,swatchsize=15):
		#parent=oldwidget.parentWidget()
		qtgui.QScrollArea.__init__(self)

		self.master=master

		self.swatchsize=swatchsize
		self.rows=len(colors)
		self.cols=len(colors[0])

		# remove old widget and insert this one
		#replaceWidget(oldwidget)

		self.setWidget(qtgui.QFrame(self))

		self.setupSwatches(colors)
		self.show()

	def getSettings(self):
		return (self.rows,self.cols,self.swatchsize)

	def swatchesToColors(self):
		colors=[]
		for row in self.swatches:
			currow=[]
			for swatch in row:
				currow.append((swatch.color.red(),swatch.color.green(),swatch.color.blue()))
			colors.append(currow)

		return colors

	def setupSwatches(self,colors):
		layout=self.widget().layout()
		if not layout:
			self.widget().setLayout(qtgui.QGridLayout(self.widget()))
			self.widget().layout().setSpacing(0)

		if colors:
			self.swatchrows=len(colors)
			self.swatchcolumns=len(colors[0])

		curcolor=None
		# keep around pointer to all the swatches to read from them all later if needed
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
				curswatch=ColorSwatch(self.master,parent=curframe,swatchsize=self.swatchsize,color=curcolor)
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

class PaletteWindow(AbstractBeeDockWindow):
	def __init__(self,master):
		AbstractBeeDockWindow.__init__(self,master)
		self.setAttribute(qtcore.Qt.WA_DeleteOnClose,False)

		self.ui=Ui_BeePaletteDock()
		self.ui.setupUi(self)
		self.show()

		self.ui.FGSwatch=FGSwatch(master,replacingwidget=self.ui.FGSwatch)
		self.setFGColor(qtgui.QColor(0,0,0))

		self.ui.BGSwatch=BGSwatch(master,replacingwidget=self.ui.BGSwatch)
		self.setBGColor(qtgui.QColor(255,255,255))

		# read in pallette file
		palfilename=os.path.join("config","default.pal")
		palfile=qtcore.QFile(palfilename)
		if palfile.exists():
			palfile.open(qtcore.QIODevice.ReadOnly)
			reader=PaletteParser(palfile)
			colors=reader.getColors()
			swatchsize=reader.swatchsize
		else:
			colors=[]

		self.setColors(colors,swatchsize)

	def setColors(self,colors,swatchsize=15):
		oldwidget=self.ui.swatch_frame
		newwidget=BeeSwatchScrollArea(self.master,colors,swatchsize)
		replaceWidget(oldwidget,newwidget)
		self.ui.swatch_frame=newwidget

	def resetSwatches(self,newrows,newcols,newsize):
		oldcolors=self.ui.swatch_frame.swatchesToColors()
		if newrows<1 or newcols<1:
			return

		oldrows=len(oldcolors)
		oldcols=len(oldcolors[0])

		newcolors=[]

		for row in range(newrows):
			currow=[]
			for col in range(newcols):
				if col<oldcols and row<oldrows:
					currow.append(oldcolors[row][col])
				else:
					currow.append((255,255,255))
			newcolors.append(currow)

		self.setColors(newcolors,newsize)

	def setFGColor(self,color):
		self.ui.FGSwatch.updateColor(color)

	def setBGColor(self,color):
		self.ui.BGSwatch.updateColor(color)

	def hideEvent(self,event):
		if not self.isMinimized():
			self.master.uncheckWindowPaletteBox()
		return qtgui.QWidget.hideEvent(self,event)

	def on_Palette_Configure_triggered(self,accept=True):
		if not accept:
			return

		dialog=qtgui.QDialog()
		dialogui=Ui_Pallete_Config_Dialog()
		dialogui.setupUi(dialog)

		rows,cols,pixels=self.ui.swatch_frame.getSettings()

		dialogui.row_box.setValue(rows)
		dialogui.col_box.setValue(cols)
		dialogui.pixels_box.setValue(pixels)

		if dialog.exec_():
			rows=dialogui.row_box.value()
			cols=dialogui.col_box.value()
			pixels=dialogui.pixels_box.value()
			self.resetSwatches(rows,cols,pixels)

	def on_Palette_save_triggered(self,accept=True):
		if not accept:
			return

		filename=qtgui.QFileDialog.getSaveFileName(self,"Choose File Name",".","Palette save (*.pal)")
		if not filename:
			return
		if filename[-4:] != ".pal":
			filename+=".pal"

		self.savePalette(filename)

	def on_Palette_save_default_triggered(self,accept=True):
		if not accept:
			return

		self.savePalette(os.path.join("config","default.pal"))

	def savePalette(self,filename):
		outfile=qtcore.QFile(filename)
		if outfile.open(qtcore.QIODevice.WriteOnly):
			writer=PaletteXmlWriter(outfile)
			writer.logPalette(self.ui.swatch_frame.swatches,self.ui.swatch_frame.swatchsize)

	def on_Palette_load_default_triggered(self,accept=True):
		if not accept:
			return

		self.loadPalette(os.path.join("config","default.pal"))

	def on_Palette_load_triggered(self,accept=True):
		if not accept:
			return

		filename=qtgui.QFileDialog.getOpenFileName(self,"Choose Palette File To Load",".","Palette save (*.pal)")
		if not filename:
			return

		self.loadPalette(filename)

	def loadPalette(self,filename):
		infile=qtcore.QFile(filename)
		if infile.open(qtcore.QIODevice.ReadOnly):
			reader=PaletteParser(infile)
			colors=reader.getColors()
			self.ui.swatch_frame.setupSwatches(colors)
