import sys
from canne import *
import os

mode = OperationMode(train=True,new_init=True,control=False)
synth = ANNeSynth(mode)

def main():
	synth.execute([])
	
if __name__ == '__main__':
	main()
