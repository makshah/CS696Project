import matplotlib
import numpy as np
import pandas as pd
csv = pd.read_csv("./results/spl2.csv",names=["index","loss","weight","loss_overall"])
data_size = 20
for i in range(data_size):
    mat = csv[csv["index"]==i]
    print(mat)
# print(csv)