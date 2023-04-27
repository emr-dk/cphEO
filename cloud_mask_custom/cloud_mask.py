from s2cloudless  import S2PixelCloudDetector, CloudMaskRequest
from ndvi_emil import masker
import os
import numpy as np
from skimage import io

my_file = 'data/S2A_MSIL1C_20171027T103131_N0206_R108_T33UUB_20171027T141000.SAFE/GRANULE/L1C_T33UUB_A012260_20171027T103128/IMG_DATA/'

def clip_images():
	for file in os.listdir(my_file):
		my_name = my_file + str(file)
		masker(my_name,"output")
		print(file)


def cloud_detector():
	cloud_detector = S2PixelCloudDetector(threshold=0.4, average_over=4, dilation_size=2)
	pass

cloud_detector = S2PixelCloudDetector(threshold=0.4,average_over=4, dilation_size=2)
input_dir = 'output/T33UUB'
list_files = np.array([io.imread(input_dir + "/" +file) for file in os.listdir(input_dir)])
print(list_files.shape)
#print(list_files)


for file in os.listdir(input_dir):
	my_file = input_dir + "/" + str(file)
	my_image = io.imread(my_file)
	print(my_image.shape)
#print(type(my_image))
	cloud_probs = cloud_detector.get_cloud_probability_maps(np.reshape(my_image,4)
#print(cloud_probs)
#if index == 1:
#	break
