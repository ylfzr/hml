import matplotlib
matplotlib.use('Agg')
import os
import sys
import json
import argparse
import time
import numpy as np
import tensorflow as tf
from tensorflow.python import debug as tf_debug

from misc.estimators import estimate_kld, compute_gaussian_kld


# initializer = tf.global_variables_initializer()
# saver = tf.train.Saver()

bsize_x = 1000
bsize_y = 1000
d = 32

x_ph = tf.placeholder(dtype=tf.float32, shape=[bsize_x, d])
y_ph = tf.placeholder(dtype=tf.float32, shape=[bsize_y, d])
kld = estimate_kld(x_ph, y_ph)


z_mu_ph = tf.placeholder(dtype=tf.float32, shape=[d])
z_log_sigma_ph = tf.placeholder(dtype=tf.float32, shape=[d])
ckld = compute_gaussian_kld(z_mu_ph, z_log_sigma_sq_ph)

compute_gaussian_kld

config = tf.ConfigProto()
config.gpu_options.allow_growth = True
with tf.Session(config=config) as sess:
    # sess.run(initializer)

    x = np.random.normal(0.0, 1.0, size=(bsize_x, d))
    y = np.random.normal(0.0, 1.0, size=(bsize_y, d))
    z = np.random.normal(0.5, 2.0, size=(bsize_y, d))

    feed_dict = {
        x_ph: x,
        y_ph: y
    }
    print(sess.run(kld, feed_dict=feed_dict))

    feed_dict = {
        x_ph: x,
        y_ph: z
    }
    print(sess.run(kld, feed_dict=feed_dict))


    feed_dict = {
        z_mu_ph: np.zeros((d,)),
        z_log_sigma_ph:np.zeros((d,)),
    }
    print(sess.run(ckld, feed_dict=feed_dict))

    feed_dict = {
        z_mu_ph: np.ones((d,)) * 0.5,
        z_log_sigma_ph:np.ones((d,)) * np.log(2.0),
    }
    print(sess.run(ckld, feed_dict=feed_dict))
