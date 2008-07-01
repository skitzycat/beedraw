import PyQt4.QtGui as qtgui
import PyQt4.QtCore as qtcore

class CanvasAdjustPreview(qtgui.QWidget):
	def __init__(self,replacingwidget,window):
		qtgui.QWidget.__init__(self,replacingwidget.parentWidget())

		self.setGeometry(replacingwidget.frameGeometry())
		self.setObjectName(replacingwidget.objectName())

		self.window=window

		self.previewimage=self.window.image.scaled(40,40,qtcore.Qt.IgnoreAspectRatio)

		self.imagewidth=self.window.image.width()
		self.imageheight=self.window.image.height()

		self.xoffset=20
		self.yoffset=20

		self.sizeratio=self.previewimage.width()/self.window.image.width()

		self.drawrect=qtcore.QRectF(self.xoffset,self.yoffset,self.previewimage.width(),self.previewimage.height())

		self.rectpen=qtgui.QPen(qtgui.darkMagenta)
		self.rectpen.setWidth(3)

		self.show()

	def paintEvent(self,event):
		painter=qtgui.QPainter()
		painter.begin(self)

		painter.drawImage(self.xoffset,self.yoffset)

		painter.setPen(self.rectpen)
		painter.drawRect(self.drawrect)

		painter.end()

	def newAdjustments(self,left,top,right,bottom):
		leftbound=(left*self.sizeratio)+self.xoffset
		topbound=(top*self.sizeratio)+self.yoffset
		width=(right+self.imagewidth-left)*self.sizeratio
		height=(bottom+self.imageheight-top)*self.sizeratio

		self.drawrect=qtcore.QRectF(leftbound,topbound,width,height)

		self.update()
