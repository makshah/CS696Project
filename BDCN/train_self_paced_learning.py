#-*-coding:utf-8-*-
import numpy as np
import torch
import torch.optim as optim
import torch.nn as nn
from torch.autograd import Variable
from torch.nn import functional as F
import argparse
import time
import re
import os
import sys
import bdcn
import bdcn_fuzzy_SPL
from datasets.dataset import Data
from datasets.dataset_fuzzy_self_paced_learning import Data_Fuzzy_SPL
import cfg
import log
import math
import cv2

def adjust_learning_rate(optimizer, steps, step_size, gamma=0.1, logger=None):
    """Sets the learning rate to the initial LR decayed by 10 every 30 epochs"""

    for param_group in optimizer.param_groups:
        param_group['lr'] = param_group['lr'] * gamma
        if logger:
            logger.info('%s: %s' % (param_group['name'], param_group['lr']))


def cross_entropy_loss2d(inputs, targets, cuda=False, balance=1.1):
    """
    :param inputs: inputs is a 4 dimensional data nx1xhxw
    :param targets: targets is a 3 dimensional data nx1xhxw
    :return:
    """
    n, c, h, w = inputs.size()
    weights = np.zeros((n, c, h, w))
    for i in range(n):
        t = targets[i, :, :, :].cpu().data.numpy()
        pos = (t == 1).sum()
        neg = (t == 0).sum()
        valid = neg + pos
        weights[i, t == 1] = neg * 1. / valid
        weights[i, t == 0] = pos * balance / valid
    weights = torch.Tensor(weights)
    if cuda:
        weights = weights.cuda()
    inputs = torch.sigmoid(inputs)
    loss=nn.BCELoss(weights,reduction='sum')(inputs,targets)     #loss=nn.BCELoss(weights,size_average=False)(inputs,targets)
    return loss

def re_Dice_Loss(inputs, targets, cuda=False, balance=1.1):
    n, c, h, w = inputs.size()
    smooth=1
    inputs = torch.sigmoid(inputs)  # F.sigmoid(inputs)

    input_flat=inputs.view(-1)
    target_flat=targets.view(-1)

    intersecion=input_flat*target_flat
    unionsection=input_flat.pow(2).sum()+target_flat.pow(2).sum()+smooth
    loss=unionsection/(2*intersecion.sum()+smooth)
    loss=loss.sum()

    return loss

def train(model, args):
    data_root = cfg.config[args.dataset]['data_root']
    data_lst = cfg.config[args.dataset]['data_lst']
    if 'Multicue' in args.dataset:
        data_lst = data_lst % args.k
    mean_bgr = np.array(cfg.config[args.dataset]['mean_bgr'])
    yita = args.yita if args.yita else cfg.config[args.dataset]['yita']
    crop_size = args.crop_size
    # train_img = Data(data_root, data_lst, yita, mean_bgr=mean_bgr, crop_size=crop_size)
    train_img = Data_Fuzzy_SPL(data_root, data_lst, yita, mean_bgr=mean_bgr, crop_size=crop_size)
    trainloader = torch.utils.data.DataLoader(train_img,
        batch_size=args.batch_size, shuffle=True, num_workers=0)  #num_workers=5

    params_dict = dict(model.named_parameters())
    base_lr = args.base_lr
    weight_decay = args.weight_decay
    logger = args.logger
    params = []
    for key, v in params_dict.items():
        if re.match(r'conv[1-5]_[1-3]_down', key):
            if 'weight' in key:
                params += [{'params': v, 'lr': base_lr*0.1, 'weight_decay': weight_decay*1, 'name': key}]
            elif 'bias' in key:
                params += [{'params': v, 'lr': base_lr*0.2, 'weight_decay': weight_decay*0, 'name': key}]
        elif re.match(r'.*conv[1-4]_[1-3]', key):
            if 'weight' in key:
                params += [{'params': v, 'lr': base_lr*1, 'weight_decay': weight_decay*1, 'name': key}]
            elif 'bias' in key:
                params += [{'params': v, 'lr': base_lr*2, 'weight_decay': weight_decay*0, 'name': key}]
        elif re.match(r'.*conv5_[1-3]', key):
            if 'weight' in key:
                params += [{'params': v, 'lr': base_lr*100, 'weight_decay': weight_decay*1, 'name': key}]
            elif 'bias' in key:
                params += [{'params': v, 'lr': base_lr*200, 'weight_decay': weight_decay*0, 'name': key}]
        elif re.match(r'score_dsn[1-5]', key):
            if 'weight' in key:
                params += [{'params': v, 'lr': base_lr*0.01, 'weight_decay': weight_decay*1, 'name': key}]
            elif 'bias' in key:
                params += [{'params': v, 'lr': base_lr*0.02, 'weight_decay': weight_decay*0, 'name': key}]
        elif re.match(r'upsample_[248](_5)?', key):
            if 'weight' in key:
                params += [{'params': v, 'lr': base_lr*0, 'weight_decay': weight_decay*0, 'name': key}]
            elif 'bias' in key:
                params += [{'params': v, 'lr': base_lr*0, 'weight_decay': weight_decay*0, 'name': key}]
        elif re.match(r'.*msblock[1-5]_[1-3]\.conv', key):
            if 'weight' in key:
                params += [{'params': v, 'lr': base_lr*1, 'weight_decay': weight_decay*1, 'name': key}]
            elif 'bias' in key:
                params += [{'params': v, 'lr': base_lr*2, 'weight_decay': weight_decay*0, 'name': key}]
        else:
            if 'weight' in key:
                params += [{'params': v, 'lr': base_lr*0.001, 'weight_decay': weight_decay*1, 'name': key}]
            elif 'bias' in key:
                params += [{'params': v, 'lr': base_lr*0.002, 'weight_decay': weight_decay*0, 'name': key}]
    optimizer = torch.optim.SGD(params, momentum=args.momentum,
        lr=args.base_lr, weight_decay=args.weight_decay)
    start_step = 1
    mean_loss = []
    cur = 0
    pos = 0
    data_iter = iter(trainloader)
    iter_per_epoch = len(trainloader)
    logger.info('*'*40)
    logger.info('train images in all are %d ' % iter_per_epoch)
    logger.info('*'*40)
    for param_group in optimizer.param_groups:
        if logger:
            logger.info('%s: %s' % (param_group['name'], param_group['lr']))
    start_time = time.time()
    if args.cuda:
        model.cuda()
    if args.resume:
        logger.info('resume from %s' % args.resume)
        state = torch.load(args.resume)
        start_step = state['step']
        optimizer.load_state_dict(state['solver'])
        model.load_state_dict(state['param'])
    model.train()
    batch_size = args.iter_size * args.batch_size

    print("data_size: ",len(train_img))
    Vi = [1]*len(train_img)
    with open("spl.csv","w") as file:
        for step in range(start_step, args.max_iter + 1):
            optimizer.zero_grad()
            batch_loss = 0
            # debug
            print("step:\t", step)
            for i in range(args.iter_size):
                if cur == iter_per_epoch:
                    cur = 0
                    data_iter = iter(trainloader)
                images, labels, data_index = next(data_iter)
                if args.cuda:
                    images, labels = images.cuda(), labels.cuda()
                    data_index = data_index.cuda()
                images, labels = Variable(images), Variable(labels)
                data_index = Variable(data_index)
                out = model(images)
                loss = 0

                side_weight=np.arange(args.side_weight,1,(1-args.side_weight)/10)
                for k in range(10):
                    loss += side_weight[i]*cross_entropy_loss2d(out[k], labels, args.cuda, args.balance)/batch_size
                loss += args.fuse_weight*cross_entropy_loss2d(out[-1], labels, args.cuda, args.balance)/batch_size\
                        +args.reDice_weight*re_Dice_Loss(out[-1], labels, args.cuda, args.balance)/batch_size

                # if loss < (2000+0.05*step):
                #     loss_spl = loss
                # else:
                #     loss_spl = Variable(torch.tensor(0.0),requires_grad=True)
                # loss_spl = loss if loss < (400+500*(1+math.exp(-0.0002*step)))
                # loss_spl = loss*out[-1] - out[-1]*(500+500*(1+math.exp(-0.0002*step)))
                K = 2000 + 0.05 * step
                loss_spl = loss*Vi[data_index]-K*Vi[data_index]
                if loss < K:
                    Vi[data_index] = 1
                else:
                    Vi[data_index] = 0

                file.write("%s,%s,%s\n"%(float(data_index),float(loss),float(loss_spl)))
                loss_spl.backward()
                batch_loss +=loss_spl.item()       #loss.data[0]  #not suitable for pytorch0.5
                # loss.backward()
                # batch_loss += loss.item()  # loss.data[0]  #not suitable for pytorch0.5
                cur += 1
            # update parameter

            """"---------------------------------commented for curriculum learning--------------------------------------"""

            optimizer.step()
            if len(mean_loss) < args.average_loss:
                mean_loss.append(batch_loss)
            else:
                mean_loss[pos] = batch_loss
                pos = (pos + 1) % args.average_loss
            if step % args.step_size == 0:
                adjust_learning_rate(optimizer, step, args.step_size, args.gamma)
            if step % args.snapshots == 0:
                torch.save(model.state_dict(), '%s/bdcn_%d.pth' % (args.param_dir, step))
                state = {'step': step+1,'param':model.state_dict(),'solver':optimizer.state_dict()}
                torch.save(state, '%s/bdcn_%d.pth.tar' % (args.param_dir, step))
            if step % args.display == 0:
                tm = time.time() - start_time
                logger.info('iter: %d, lr: %e, loss: %f, time using: %f(%fs/iter)' % (step,
                    optimizer.param_groups[0]['lr'], np.mean(mean_loss), tm, tm/args.display))
                start_time = time.time()

def main():
    args = parse_args()
    logger = log.get_logger(args.log)
    args.logger = logger
    logger.info('*'*80)
    logger.info('the args are the below')
    logger.info('*'*80)
    for x in args.__dict__:
        logger.info(x+','+str(args.__dict__[x]))
    logger.info(cfg.config[args.dataset])
    logger.info('*'*80)
    os.environ['CUDA_VISIBLE_DEVICES'] = args.gpu
    if not os.path.exists(args.param_dir):
        os.mkdir(args.param_dir)
    torch.manual_seed(int(time.time()))
    model = bdcn.BDCN(pretrain=args.pretrain, logger=logger)
    if args.complete_pretrain:
        model.load_state_dict(torch.load(args.complete_pretrain))
    logger.info(model)
    train(model, args)

def parse_args():
    parser = argparse.ArgumentParser(description='Train BDCN for different args')
    parser.add_argument('-d', '--dataset', type=str, choices=cfg.config.keys(),
        default='bsds500', help='The dataset to train')
    parser.add_argument('--param-dir', type=str, default='params',
        help='the directory to store the params')
    parser.add_argument('--lr', dest='base_lr', type=float, default=1e-6,
        help='the base learning rate of model')
    parser.add_argument('-m', '--momentum', type=float, default=0.9,
        help='the momentum')
    parser.add_argument('-c', '--cuda', action='store_true',default=True,   #usage: -c,not use in default
        help='whether use gpu to train network')
    parser.add_argument('-g', '--gpu', type=str, default='0',
        help='the gpu id to train net')
    parser.add_argument('--weight-decay', type=float, default=0.0002,
        help='the weight_decay of net')
    parser.add_argument('-r', '--resume', type=str, default=None,
        help='whether resume from some, default is None')
    parser.add_argument('-p', '--pretrain', type=str, default=None,
        help='init net from pretrained model default is None')
    parser.add_argument('--max-iter', type=int, default=40000,
        help='max iters to train network, default is 40000')
    parser.add_argument('--iter-size', type=int, default=10,
        help='iter size equal to the batch size, default 10')
    parser.add_argument('--average-loss', type=int, default=50,
        help='smoothed loss, default is 50')
    parser.add_argument('-s', '--snapshots', type=int, default=500,  #1000
        help='how many iters to store the params, default is 1000')
    parser.add_argument('--step-size', type=int, default=10000,
        help='the number of iters to decrease the learning rate, default is 10000')
    parser.add_argument('--display', type=int, default=20,
        help='how many iters display one time, default is 20')
    parser.add_argument('-b', '--balance', type=float, default=1.1,
        help='the parameter to balance the neg and pos, default is 1.1')
    parser.add_argument('-l', '--log', type=str, default='log.txt',
        help='the file to store log, default is log.txt')
    parser.add_argument('-k', type=int, default=1,
        help='the k-th split set of multicue')
    parser.add_argument('--batch-size', type=int, default=1,
        help='batch size of one iteration, default 1')
    parser.add_argument('--crop-size', type=int, default=None,
        help='the size of image to crop, default not crop')
    parser.add_argument('--yita', type=float, default=None,
        help='the param to operate gt, default is data in the config file')
    parser.add_argument('--complete-pretrain', type=str, default=None,
        help='finetune on the complete_pretrain, default None')
    parser.add_argument('--side-weight', type=float, default=0.2,
        help='the loss weight of sideout, default 0.5')
    parser.add_argument('--fuse-weight', type=float, default=1.1,
        help='the loss weight of fuse, default 1.1')
    parser.add_argument('--reDice-weight', type=float, default=100,  # add the weight parameter
                        help='the loss weight of fuse, default 10')
    parser.add_argument('--gamma', type=float, default=0.1,
        help='the decay of learning rate, default 0.1')
    return parser.parse_args()

if __name__ == '__main__':
    main()


