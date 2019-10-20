import scipy.io as sio
import os
from PIL import Image

dataset_part = ['test','train','val']
sample = {'x':'images','y':'groundTruth'}
file_extension = {'x':'.jpg','y':'.mat'}
root_path = "../data/BSR/BSDS500/data/"

def firstImg(img):
    return img['groundTruth'][0][0][0][0][1] * 255
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
                img = firstImg(mat)
                im = Image.fromarray(img)
                im.save(os.path.join(root_path,sample['y'],part)+"/"+name+file_extension['x'])
