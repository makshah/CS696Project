import os
dataset_part = ['test','train','val']
sample = {'x':'images','y':'groundTruth'}
file_extension = {'x':'.jpg','y':'.mat'}
root_path = "../data/BSR/BSDS500/data/"
for part in dataset_part:
    with open(root_path+part+"_pair.lst","w") as f:
        folder_path = os.path.join(root_path,sample['x'],part)
        files = os.listdir(folder_path)
        for file in files:
            name = os.path.splitext(file)[0]
            if name != "Thumbs":
                f.write(os.path.join(sample['x'],part)+"/"+name+file_extension['x']+" "+\
                        os.path.join(sample['y'],part)+"/"+name+file_extension['x']+"\n")
