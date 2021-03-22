# Estimate optimal initial learning rate
import tensorflow as tf
import tensorflow.keras.backend as K
import matplotlib.pyplot as plt
import math
import numpy as np
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '1'  # avoid printing GPU info messages
os.environ['KMP_DUPLICATE_LIB_OK'] = '1'  # MacOS pb
from dataset import BatchMaker
from models  import *


def find_best_lr(wrapp, n_objs, im_dims, batch_size, mode='decode', custom=True, from_scratch=False):
  
  # Simulation parameters
  n_samples = 100   # how many lrs are tried
  init_lr   = 1e-7  # smallest lr tried
  stop_lr   = 1e-0  # largest lr tried

  # Learning devices
  decay_rate = stop_lr/init_lr
  scheduler  = tf.keras.optimizers.schedules.ExponentialDecay(
    init_lr, n_samples, decay_rate, staircase=False, name=None)
  optim = tf.keras.optimizers.Adam(scheduler)

  # Load checkpoint if necessary
  if not from_scratch or mode == 'decode':
    print('\nLoading trained reconstruction weights...')
    model_dir  = '%s/%s/ckpt_model' % (os.getcwd(), wrapp.model_name)
    ckpt_model = tf.train.Checkpoint(net=wrapp.model)
    mngr_model = tf.train.CheckpointManager(ckpt_model, directory=model_dir, max_to_keep=1)
    ckpt_model.restore(mngr_model.latest_checkpoint)
    if not from_scratch and mode == 'decode':
      print('\nLoading trained decoding weights...')
      decoder_dir  = '%s/%s/ckpt_decod' % (os.getcwd(), wrapp.model_name)
      ckpt_decoder = tf.train.Checkpoint(net=wrapp.decoder)
      mngr_decoder = tf.train.CheckpointManager(ckpt_decoder, directory=decoder_dir, max_to_keep=1)
      ckpt_decoder.restore(mngr_decoder.latest_checkpoint)
  if not os.path.exists('./%s' % (wrapp.model_name,)):
    os.mkdir('./%s' % (wrapp.model_name,))

  # Run batches with increasing learning rates
  batch_maker = BatchMaker(mode, n_objs, batch_size, wrapp.n_frames, im_dims)
  lrs         = []
  losses      = []
  for s in range(n_samples):

    # Compute loss
    if mode == 'recons':
      batch = batch_maker.generate_batch()[0]
      loss  = wrapp.train_step(tf.stack(batch, axis=1)/255, s, optim)
    elif mode == 'decode':
      batch, labels = batch_maker.generate_batch()
      acc, loss     = wrapp.train_step(tf.stack(batch, axis=1)/255, s, optim, labels)
    
    # Record loss
    losses.append(loss.numpy())
    updated_lr = optim._decayed_lr(tf.float32).numpy()
    lrs.append(updated_lr)
    lr_str = "{:.2e}".format(updated_lr)
    print('\rSample %03i/%03i, lr = %s, %s loss = %.4f' % (s+1, n_samples, lr_str, mode, loss), end='')

  # Figure out best lr and plot loss vs learning rate
  lr_for_min_loss = lrs[np.argmin(losses)]
  lr_opt          = lr_for_min_loss/10
  print('\nMin loss for lr = %s, opt lr = %s' %(lr_for_min_loss, lr_opt)) 
  wrapp.plot_results(lrs, losses, 'lr', 'loss', mode)

  # Return best lr
  return lr_opt


if __name__ == '__main__':

  train_mode  = 'recons'          # can be 'recons' or 'decode'
  crit_type   = 'entropy_thresh'  # can be 'entropy', 'entropy_threshold', 'prediction_error'
  n_objs      = 2                 # number of moving object in each sample
  im_dims     = (64, 64, 1)       # image dimensions
  n_frames    = 10                # frames in the input sequences
  batch_size  = 16                # sample sequences sent in parallel
  model, name = PredNet((im_dims[-1], 32, 64, 128), (im_dims[-1], 32, 64, 128)), 'prednet2'
  decoder     = simple_decoder()
  wrapp       = Wrapper(model, my_recons, decoder, crit_type, n_frames, name)
  init_lr     = find_best_lr(wrapp, n_objs, im_dims, batch_size, mode=train_mode, custom=False, from_scratch=True)
  