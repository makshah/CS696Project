import numpy as np
import torch
import torch.optim as optim
import torch.nn as nn
from torch.autograd import Variable
from torch.nn import functional as F
import time
import re
import os
import sys
import bdcn
from datasets.dataset import Data
import argparse
import cfg
import matplotlib.image as mpimg
import cv2
from PIL import Image
from matplotlib import pyplot as plt

def sigmoid(x):
    return 1./(1+np.exp(np.array(-1.*x)))


def test(model, args):
    test_root = cfg.config_test[args.dataset]['data_root']
    # test_root = cfg.config[args.dataset]['data_root']
    test_lst = cfg.config_test[args.dataset]['data_lst']
    # test_lst = cfg.config[args.dataset]['data_lst']
    # test_name_lst = os.path.join(test_root, 'train_pair.lst')   #'voc_valtest.txt'
    test_name_lst = os.path.join(test_root, 'test.lst')
    if 'Multicue' in args.dataset:
        test_lst = test_lst % args.k
        test_name_lst = os.path.join(test_root, 'test%d_id.txt'%args.k)
    mean_bgr = np.array(cfg.config_test[args.dataset]['mean_bgr'])
    test_img = Data(test_root, test_lst, mean_bgr=mean_bgr)
    testloader = torch.utils.data.DataLoader(
        test_img, batch_size=1, shuffle=False, num_workers=0)  #num_workers=8
    nm = np.loadtxt(test_name_lst, dtype=str)
    print(len(testloader), len(nm))
    assert len(testloader) == len(nm)
    save_res = True
    save_dir = args.res_dir
    if not os.path.exists(save_dir):
        os.mkdir(save_dir)
    if args.cuda:
        model.cuda()
    model.eval()
    data_iter = iter(testloader)
    iter_per_epoch = len(testloader)
    start_time = time.time()
    all_t = 0
    # print("data_iter: ", data_iter.__next__())
    print(testloader)
    for i, (data, _) in enumerate(testloader):
        print("index: ", i)
        if args.cuda:
            data = data.cuda()
        data = Variable(data)     #, volatile=True
        tm = time.time()
        out = model(data)
        fuse = torch.sigmoid(out[-1]).cpu().data.numpy()[0, 0, :, :]
        if not os.path.exists(os.path.join(save_dir, 'fuse')):
            os.mkdir(os.path.join(save_dir, 'fuse'))
        try:
            # print(fuse)
            pic = Image.fromarray(fuse*255)
            pic = pic.convert('L')
            # print(pic)
            pic.save(os.path.join(save_dir, 'fuse', '%s.png'%nm[i][0][:-4]),"PNG")
            # cv2.imwrite(os.path.join(save_dir, 'fuse', '%s.png'%nm[i][0]), 255-fuse*255)
        except Exception as e:
            print(e)
            print("not write",i)
        
        all_t += time.time() - tm
       
    print(all_t)
    print('Overall Time use: ', time.time() - start_time)

def main():
    import time
    print(time.localtime())
    args = parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = args.gpu
    model = bdcn.BDCN()
    model.load_state_dict(torch.load('%s' % (args.model),map_location='cpu'))
    test(model, args)

def parse_args():
    parser = argparse.ArgumentParser('test BDCN')
    parser.add_argument('-d', '--dataset', type=str, choices=cfg.config_test.keys(),
        default='face_real', help='The dataset to train')
    parser.add_argument('-c', '--cuda', action='store_true',default=True,
        help='whether use gpu to train network')
    parser.add_argument('-g', '--gpu', type=str, default='0',
        help='the gpu id to train net')
    parser.add_argument('-m', '--model', type=str, default='params/bdcn_4000.pth',
    # parser.add_argument('-m', '--model', type=str, default='params/bdcn_1000.pth',
        help='the model to test')
    parser.add_argument('--res-dir', type=str, default='results',
        help='the dir to store result')
    parser.add_argument('-k', type=int, default=1,
        help='the k-th split set of multicue')
    return parser.parse_args()

if __name__ == '__main__':
    main()
