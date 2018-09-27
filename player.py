import sys
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4 import QtGui
from canne import *
import os
import pygame

mode = OperationMode(train=False,new_init=False,control=True)
synth = ANNeSynth(mode)

class sliderGui(QWidget):
	def __init__(self, parent = None):
		super(sliderGui, self).__init__(parent)
		layout = QVBoxLayout()
		layout2 = QHBoxLayout()
		
		self.generateButton = QtGui.QPushButton('Save', self)
		self.generateButton.clicked.connect(self.generate)
		
		self.playButton = QtGui.QPushButton('Pause',self)
		self.playButton.clicked.connect(self.pause)

		layout = QtGui.QVBoxLayout(self)
		layout.addWidget(self.playButton)
		layout.addWidget(self.generateButton)
		layout.addLayout(layout2)

		self.s1 = QSlider(Qt.Vertical)
		self.s2 = QSlider(Qt.Vertical)
		self.s3 = QSlider(Qt.Vertical)
		self.s4 = QSlider(Qt.Vertical)
		self.s5 = QSlider(Qt.Vertical)
		self.s6 = QSlider(Qt.Vertical)
		self.s7 = QSlider(Qt.Vertical)
		self.s8 = QSlider(Qt.Vertical)
		self.s9 = QSlider(Qt.Horizontal)

		self.addSlider(self.s1,layout2)
		self.addSlider(self.s2,layout2)
		self.addSlider(self.s3,layout2)
		self.addSlider(self.s4,layout2)
		self.addSlider(self.s5,layout2)
		self.addSlider(self.s6,layout2)
		self.addSlider(self.s7,layout2)
		self.addSlider(self.s8,layout2)
		self.addSlider(self.s9,layout2)
		self.s9.setMinimum(-30)
		self.s9.setMaximum(30)
		self.s9.setValue(0)
		self.s9.setTickInterval(3)

		self.setLayout(layout)
		self.setWindowTitle("CANNe")

	def addSlider(self,slider,layout):
		slider.setMinimum(0)
		slider.setMaximum(40)
		slider.setValue(10)
		slider.setTickPosition(QSlider.TicksBelow)
		slider.setTickInterval(2)
		layout.addWidget(slider)
		slider.sliderReleased.connect(self.valuechange)		

	def valuechange(self):
		tmp = np.zeros((1,9))
		tmp[0,0] = self.s1.value()
		tmp[0,1] = self.s2.value()
		tmp[0,2] = self.s3.value()
		tmp[0,3] = self.s4.value()
		tmp[0,4] = self.s5.value()
		tmp[0,5] = self.s6.value()
		tmp[0,6] = self.s7.value()
		tmp[0,7] = self.s8.value()
		tmp /= 10.
		tmp[0,8] = 2*self.s9.value()
		synth.play_synth(tmp)
		pygame.mixer.music.load('loop.wav')
		pygame.mixer.music.play(-1)


	def generate(self):
		tmp = np.zeros((1,9))
		tmp[0,0] = self.s1.value()
		tmp[0,1] = self.s2.value()
		tmp[0,2] = self.s3.value()
		tmp[0,3] = self.s4.value()
		tmp[0,4] = self.s5.value()
		tmp[0,5] = self.s6.value()
		tmp[0,6] = self.s7.value()
		tmp[0,7] = self.s8.value()
		tmp /= 10.
		tmp[0,8] = self.s9.value()
		text, ok = QInputDialog.getText(self, 'Save File', 'Enter filename:')
		if ok:
			filename_=str(text)
			synth.execute(tmp,filename_)

		

	def pause(self):
		pygame.mixer.music.stop()


def main():
	synth.load_weights_into_memory()
	pygame.init()
	pygame.mixer.init(channels=1)
	app = QApplication(sys.argv)
	ex = sliderGui()
	ex.show()
	sys.exit(app.exec_())
	
if __name__ == '__main__':
	main()
