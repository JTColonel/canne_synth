import sys
from canne import *
import os

mode = OperationMode(train=True,new_init=True,control=False)
synth = ANNeSynth(mode)

def main():
	#pygame.mixer.pre_init(frequency=44100, size=-16, channels=1)
	synth.execute([])
	
	
if __name__ == '__main__':
	main()
