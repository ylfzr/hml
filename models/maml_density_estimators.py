import numpy as np
import os
import tensorflow as tf
from tensorflow.contrib.framework.python.ops import arg_scope, add_arg_scope
from misc.layers import conv2d, deconv2d, dense
from misc.helpers import int_shape, get_name, get_trainable_variables

class MAMLRegressor(object):

    def __init__(self, counters={}, user_mode='train'):
        self.counters = counters
        self.user_mode = user_mode

    def construct(self, regressor, error_func, obs_shape, alpha=0.01, inner_iters=1, eval_iters=10, nonlinearity=tf.nn.relu, bn=False, kernel_initializer=None, kernel_regularizer=None):

        self.regressor = regressor
        self.error_func = error_func
        self.obs_shape = obs_shape
        self.alpha = alpha
        self.inner_iters = inner_iters
        self.eval_iters = eval_iters
        self.nonlinearity = nonlinearity
        self.bn = bn
        self.kernel_initializer = kernel_initializer
        self.kernel_regularizer = kernel_regularizer

        self.X_c = tf.placeholder(tf.float32, shape=tuple([None,]+obs_shape))
        self.y_c = tf.placeholder(tf.float32, shape=(None,))
        self.X_t = tf.placeholder(tf.float32, shape=tuple([None,]+obs_shape))
        self.y_t = tf.placeholder(tf.float32, shape=(None,))
        self.is_training = tf.placeholder(tf.bool, shape=())

        self.outputs = self._model()
        self.y_hat = self.outputs
        self.loss = self._loss()

        self.grads = tf.gradients(self.loss, get_trainable_variables([self.scope_name]), colocate_gradients_with_ops=True)

    def _model(self):
        default_args = {
            "nonlinearity": self.nonlinearity,
            "bn": self.bn,
            "kernel_initializer": self.kernel_initializer,
            "kernel_regularizer": self.kernel_regularizer,
            "is_training": self.is_training,
            "counters": self.counters,
        }
        with arg_scope([self.regressor], **default_args):
            self.scope_name = get_name("maml_regressor", self.counters)
            with tf.variable_scope(self.scope_name):
                y_hat = self.regressor(self.X_c)
                vars = get_trainable_variables([self.scope_name])
                y_hat_t_arr = [self.regressor(self.X_t, params=vars.copy())]
                for k in range(1, max(self.inner_iters, self.eval_iters)+1):
                    loss = self.error_func(labels=self.y_c, predictions=y_hat)
                    grads = tf.gradients(loss, vars, colocate_gradients_with_ops=True)
                    vars = [v - self.alpha * g for v, g in zip(vars, grads)]
                    y_hat = self.regressor(self.X_c, params=vars.copy())
                    y_hat_t = self.regressor(self.X_t, params=vars.copy())
                    y_hat_t_arr.append(y_hat_t)
                self.eval_y_hats = y_hat_t_arr
                return y_hat_t_arr[self.inner_iters]

    def _loss(self):
        return self.error_func(labels=self.y_t, predictions=self.preds)


    def predict(self, sess, X_c_value, y_c_value, X_t_value, step=None):
        feed_dict = {
            self.X_c: X_c_value,
            self.y_c: y_c_value,
            self.X_t: X_t_value,
            # self.y_t: np.zeros((X_t_value.shape[0],)),
            self.is_training: False,
        }
        if step is None:
            preds= sess.run(self.y_hat, feed_dict=feed_dict)
        else:
            preds= sess.run(self.eval_y_hats[step], feed_dict=feed_dict)
        return preds


    def compute_loss(self, sess, X_c_value, y_c_value, X_t_value, y_t_value, is_training):
        feed_dict = {
            self.X_c: X_c_value,
            self.y_c: y_c_value,
            self.X_t: X_t_value,
            self.y_t: y_t_value,
            self.is_training: is_training,
        }
        l = sess.run(self.loss, feed_dict=feed_dict)
        return l
