import tensorflow as tf 
import numpy as np 
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import animation
import os
import librosa
import sys
import scipy as sci
import soundfile as sf
from time import time

def do_rtpghi_gaussian_window(mag,len_window,hop_length_):
	threshold = 1e-3
	pie = np.pi
	relative_height = 0.01
	width_ = (len_window/2)/np.sqrt(-2*np.log(relative_height))
	gaussian_window = sci.signal.get_window(('gaussian',width_),len_window)
	mag = np.clip(mag, threshold, None)
	log_mag = np.log(mag)
	qwe = np.shape(log_mag)
	recon_phase_der = np.zeros(qwe)
	recon_phase_output =  np.zeros(qwe)# np.random.uniform(low=0,high=2*pie,size=qwe)
	M_freqs = qwe[0]
	N_frames = qwe[1]
	freq_time_ratio = -1*(pie/4)*(np.power(len_window,2)/np.log(relative_height))
	scale_constant_6 = (hop_length_*M_freqs)/(-2*freq_time_ratio)

	#This is Equation 6 from the paper, which requires no look-ahead frames
	for ii in range(1,M_freqs-1):
		recon_phase_der[ii,:] = scale_constant_6*(log_mag[ii+1,:]-log_mag[ii-1,:])+(pie*hop_length_*ii/(M_freqs))
	for jj in range(1,N_frames-1):
		bins_to_randomize = mag[:,jj]==threshold
		recon_phase_output[:,jj] = recon_phase_output[:,jj-1]+0.5*(recon_phase_der[:,jj-1]+recon_phase_der[:,jj])
		#recon_phase_output[bins_to_randomize,jj] = np.random.uniform(low=0,high=2*pie,size=np.shape(log_mag[mag[:,jj]==threshold,jj])) 
	E = mag*np.exp(1j*recon_phase_output)
	return librosa.istft(E, hop_length=hop_length_)

#Topology AutoEncoder:
#Generating weights for the fully connected layers fc- refers to the -th fully connected layer's neuron width
class Topology:
	def __init__(self,input_size):
		##Calculated Below
		self.fc = np.zeros((15)).astype(int)
		self.b = {}
		self.W_fc = {}
		self.output_size = 2049
		self.input_size = input_size

		##Constant Values belonging to topology:
		self.chkpt_name = 'checkpoints'
		self.min_HL = 8
		self.epochs = 300 #Number of epochs the ANN is trained for - 300 should be sufficient
		self.learning_rate_adam = 1e-3 #ADAM learning rate - 1e-3 was found to produce robust ANNs
		self.l2_lamduh = 1e-16 #Lamda value for L1 Regularization
		self.batch_size = 200 #Typical batch size for ADAM useage
		self.fc = [1000,512,256,128,64,32,16,8,16,32,64,128,256,512,1024]
		
		for i in range(15):
			self.b[i] =self.getBiasVariable(self.fc[i],'b_' + str(i))
		self.b[15] = self.getBiasVariable(self.output_size,'b_13')

		#Making weight variables
		self.W_fc[0] = self.getWeightVariable([self.input_size, self.fc[0]],'W_fc1')
		for i in range(1,15):
			self.W_fc[i] = self.getWeightVariable([self.fc[i - 1],self.fc[i]],'W_fc' + str(i + 1))
		self.W_fc[15] = self.getWeightVariable([self.fc[14], self.output_size],'W_fc14')

	def getBiasVariable(self,shape_, name_): 
		initial = tf.truncated_normal([shape_], name=name_, stddev=0.15) #Initialized with a truncated normal random variable
		return tf.Variable(initial)

	#Creates weight variables for the ANN and groups them in a collection for use in L2 regularization
	def getWeightVariable(self,shape_, name_): 
		initial = tf.truncated_normal(shape_, name=name_, stddev=0.15) #Initialized with a truncated normal random variable
		tf.add_to_collection('l2', tf.reduce_sum(tf.pow(initial,2))) #Adding to L2 collection, summing squares
		return tf.Variable(initial)

class OperationMode:
	def __init__(self,train=False,new_init=False,validation=False,control=False,bias=False):
		self.train = train
		self.new_init = new_init
		self.validation = validation
		self.control = control
		self.bias = bias

class ANNeSynth:
	def __init__(self,operationMode):
		self._operationMode = operationMode
		self._sess = tf.Session()

		#Load the stft so we have an input_size (from the topology)
		self.loadDataSet()

		##Generating placeholders for the input and label data
		self.x_ = tf.placeholder(tf.float32, shape=[None, self.topology.input_size])
		self.y_ = tf.placeholder(tf.float32, shape=[None, self.topology.output_size])
		self.controller = tf.placeholder(tf.float32, shape=[None, self.topology.min_HL])
		##
		self.makeTensorFlowLayers()


	def loadDataSet(self):
		#Loading 95,443 Magnitude STFT frames saved as .npy (Loading in data)
		filename = 'synth_frames.npy'	#Static Data used for training net
		data_path = os.path.join(os.getcwd(),filename)
		self.frames = np.load(data_path)
		self.frames = np.asarray(self.frames)
		n_mels_ = 512
		n_mfccs_ = 256
		mel_append = librosa.feature.melspectrogram(S=np.transpose(self.frames),n_mels = n_mels_)
		mfcc_append = np.transpose(librosa.feature.mfcc(S=librosa.core.power_to_db(mel_append), n_mfcc = n_mfccs_))
		mfcc_append = mfcc_append[:,26:]
		mel_append = np.transpose(mel_append)
		first_diff = np.diff(self.frames)
		second_diff = np.diff(self.frames, n=2)
		#self.frames = np.hstack((self.frames,first_diff))
		#self.frames = np.hstack((self.frames, second_diff))
		#self.frames = np.hstack((self.frames,mfcc_append))
		#self.frames = np.hstack((self.frames,mel_append))
		print(np.shape(self.frames))
		self.validate = self.frames[84712:,:]
		self.topology = Topology(np.shape(self.frames)[1])

	def recurseThroughLayer(self,layer,i,desired_stop):
		Product = tf.matmul(layer,self.topology.W_fc[i])
		
		if(self._operationMode.bias):
			new_layer = tf.nn.relu(tf.add(Product,self.topology.b[i]))
		else:
			new_layer = tf.nn.relu(tf.add(Product,0))

		if(i == desired_stop):
			return new_layer
		else:
			return self.recurseThroughLayer(new_layer,i + 1,desired_stop)

	def makeTensorFlowLayers(self):
		##Making the tensorflow layers from bias and weight variables
		initialLayer = tf.nn.relu(tf.add(tf.matmul(self.x_, self.topology.W_fc[0]),self.topology.b[0]))
		initialLayer2 = tf.nn.relu(tf.add(tf.matmul(self.controller, self.topology.W_fc[8]),self.topology.b[8]))
		self.modulators = tf.placeholder(tf.float32, shape=[None, self.topology.fc[7]])
		self.outputLayer = self.recurseThroughLayer(initialLayer,1,15)
		self.outputLayer2 = self.recurseThroughLayer(initialLayer2,9,15)
		self.initfilter = tf.multiply(self.recurseThroughLayer(initialLayer,1,7),self.modulators)
		self.outputLayer4 = self.recurseThroughLayer(self.initfilter,8,15)

	def trainNeuralNetwork(self):
		#Splitting self.frames into different buffers
		train = self.frames[:78991,:]
		test = self.frames[78991:84712,:]
		validate = self.frames[84712:,:]
		
		#Generating Parameters for the Neural Network and Initializing the Net
		total_batches = int(len(train)/self.topology.batch_size) #Number of batches per epoch
		l2 = tf.reduce_sum(tf.get_collection('l2')) 
		# loss2 = tf.reduce_mean(tf.pow(y_ - output_, 2)) # MSE error
		
		subt = self.y_ - self.outputLayer
		arg1 = tf.pow(subt, 2)
		arg2 = tf.reduce_mean(tf.pow(self.y_,2))
		self.loss2 = tf.divide(tf.reduce_mean(arg1),arg2) #Spectral Convergence calculation for input and output magnitude STFT frames
		self.loss3 = tf.reduce_mean(arg1)
		self.loss4 = tf.reduce_mean(tf.abs(subt))
		loss = self.loss2+self.topology.l2_lamduh*l2 #Imposing L2 penalty
		train_step = tf.train.AdamOptimizer(self.topology.learning_rate_adam).minimize(loss)

		###Loads the trained neural network into memory
		if self._operationMode.new_init:
			self._sess.run(tf.global_variables_initializer())
		else:
			ckpt = tf.train.latest_checkpoint(self.topology.chkpt_name) 
			self.saver.restore(self._sess, ckpt)
		#Trains the neural net for the number of epochs specified above
		#Prints test accuracy every 10th epoch
		text_file = open("metrics.txt", "a") 
		for i in tqdm(range(self.topology.epochs)):
			frames = np.random.permutation(train) #permuting the training data between epochs improves ADAM's performance
			for _ in range(total_batches):
				batch = frames[_*self.topology.batch_size:_*self.topology.batch_size+self.topology.batch_size] #Generates batch of size batch_size for training
				self._sess.run(train_step, feed_dict={self.x_:batch, self.y_:batch[:,0:self.topology.output_size]})
			tes = np.reshape(test[:,:],[-1,self.topology.input_size]) #Reshaping test array to fit with TF 
			if i%10 == 9:
				self.saver.save(self._sess, self.topology.chkpt_name+'/my-model', global_step=i)
				temp_value = self._sess.run(self.loss2, feed_dict={self.x_:tes, self.y_:test[:,0:self.topology.output_size]})
				text_file.write('\n%g'% i)
				text_file.write('\ntest accuracy %g'% temp_value)
		#print('test accuracy %g'% self._sess.run(self.loss2, feed_dict={self.x_:tes, self.y_:test[:,0:self.topology.output_size]}))
		print('Training Complete \n Evaluating Model')
		text_file.write('\n%g'% i)
		val = np.reshape(validate[:,:],[-1,self.topology.input_size])
		temp_value = self._sess.run(self.loss2, feed_dict={self.x_:val, self.y_:validate[:,0:self.topology.output_size]})
		text_file.write('\nvalidation accuracy %g'% temp_value)
		text_file.close()
		self.plotTrainingFigures()

	def plotTrainingFigures(self):
		#Plots 5 examples of the ANN's output given a magnitude STFT frame as input as 5 separate pdfs
		#Dependent on the matplotlib library
		test = np.asarray(self.validate) #This is not a good move DON'T KNOW WHY IT'S HERE
		for disp in range(10):
			x_axis = np.arange(self.topology.output_size) #X-axis for magnitude response
			orig = np.reshape(test[disp*200+200,:],[-1,self.topology.input_size]) #Pulling frames from the 'test' batch for plotting
			orig_hat = np.reshape(self._sess.run(self.outputLayer,feed_dict={self.x_:orig}),[self.topology.output_size,-1]) #Processing frame using ANN
			plt.figure(1)
			plt.subplot(211)
			plt.plot(x_axis,np.transpose(orig[:,0:self.topology.output_size]),color='b') #Plots the original magnitude STFT frame
			plt.ylim([0,1.2])
			plt.subplot(212)
			plt.plot(x_axis,orig_hat,color='r') #Plots the output magnitude STFT frame
			plt.tight_layout()
			plt.ylim([0,1.2])
			plotname = 'HL'+str(self.topology.fc[0])+'-'+str(self.topology.fc[1])+'-'+str(self.topology.fc[2])+'-'+str(disp)+'.pdf'
			plt.savefig(plotname, format = 'pdf', bbox_inches='tight')
			plt.clf()
			print('Plotting Finished')

	def execute(self,values):
		self.saver = tf.train.Saver()
		if not self._operationMode.train:
			ckpt = tf.train.latest_checkpoint(self.topology.chkpt_name) 
			self.saver.restore(self._sess, ckpt)
		else:
			self.trainNeuralNetwork()

		#Prints validation accuracy of the trained ANN
		if self._operationMode.validation:
			print('validation accuracy %g'% self._sess.run(self.loss2, feed_dict={
				self.x_:self.validate, self.y_:self.validate[:,0:self.topology.output_size]}))

		if self._operationMode.control:
			len_window = 4096 #Specified length of analysis window
			hop_length = 1024 #Specified percentage hop length between windows
			threshold = 1e-4
			pie = np.pi
			relative_height = 0.01
			width_ = (len_window/2)/np.sqrt(-2*np.log(relative_height))
			gaussian_window = sci.signal.get_window(('gaussian',width_),len_window)
			
			t = time()
			seed_ = np.random.randint(1, high=2000)
			n_frames = 250
			mag_buffer = np.zeros((self.topology.output_size,1))
			np.random.seed(seed_)
			activations = values[:,0:8]
			print(values)
			for ii in range(n_frames):
				orig_hat = np.reshape(self._sess.run(self.outputLayer2,feed_dict={self.controller:activations}),[self.topology.output_size,-1])
				mag_buffer = np.hstack((mag_buffer,orig_hat))
			
			mag_buffer = 50*mag_buffer#*np.random.uniform(low=0.999, high=1.001, size=np.shape(mag_buffer))#+np.random.uniform(low=1,high=20,size=np.shape(mag_buffer))
			bass_boost = (np.exp(np.linspace(0.95,-0.95,self.topology.output_size)))
			for ii in range(n_frames):
				mag_buffer[:,ii] = np.roll(mag_buffer[:,ii],int(values[:,8]))*bass_boost


			T = do_rtpghi_gaussian_window(mag_buffer, len_window,hop_length) #Initializes phase
			T = 0.8*T/np.max(np.abs(T))
			#T_out = griffinlim_gaussian(mag_buffer,window=gaussian_window,n_fft=len_window,n_iter=15) #refines phase for n iterations
			#librosa.output.write_wav(os.path.join(os.getcwd(),'function_test.wav'),T,sr=44100) #Write output
			sf.write('function_test.wav', T, 44100, subtype='PCM_16')  #Must be 16bit PCM to work with pygame
			elapsed = time() - t
			print('Method took '+str(elapsed)+' seconds to process the whole file')
			print('The whole file is '+str(len(T)/44100)+' seconds long')
