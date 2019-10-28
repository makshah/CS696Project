import scipy.io as sio
import os
from PIL import Image
import numpy as np
dataset_part = ['test','train','val']
sample = {'x':'images','y':'groundTruth'}
file_extension = {'x':'.jpg','y':'.mat'}
root_path = "../data/BSR/BSDS500/data/"

def firstImg(img):
    # print(type(img['groundTruth'][0][0][0][0][1] * 255))
    return img['groundTruth'][0][0][0][0][1] * 255
    # print(img)
def meanImg(img):
    tmp = []
    for i in range(len(img['groundTruth'][0])):
        tmp.append(img['groundTruth'][0][i][0][0][1] * 255)
    tmp = np.asarray(tmp)
    mean = tmp.mean(0)
    print(mean.shape)
    return mean
for part in dataset_part:
    with open(root_path+part+"_pair.lst","w") as f:
        folder_path = os.path.join(root_path,sample['y'],part)
        files = os.listdir(folder_path)
        for file in files:
            name = os.path.splitext(file)[0]
            ext = os.path.splitext(file)[1]
            if ext==".mat":
                path = os.path.join(root_path,sample['y'],part)+"/"+file
                mat = sio.loadmat(path)
                # img = firstImg(mat)
                img = meanImg(mat)
                im = Image.fromarray(img)
                im = im.convert('RGB')
                im.save(os.path.join(root_path,sample['y'],part)+"/"+name+file_extension['x'])
