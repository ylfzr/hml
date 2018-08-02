import numpy as np
import os
import tensorflow as tf
from tensorflow.contrib.framework.python.ops import arg_scope, add_arg_scope
from misc.layers import conv2d, deconv2d, dense
from misc.helpers import int_shape, get_name, get_trainable_variables
from misc.metrics import accuracy

class MAMLRegressor(object):

    def __init__(self, counters={}, user_mode='train'):
        self.counters = counters
        self.user_mode = user_mode

    def construct(self, regressor, task_type, obs_shape, label_shape=[], num_classes=1, alpha=0.01, inner_iters=1, eval_iters=10, nonlinearity=tf.nn.relu, bn=False, kernel_initializer=None, kernel_regularizer=None):

        self.regressor = regressor
        self.task_type = task_type
        if task_type == 'classification':
            self.error_func = tf.losses.softmax_cross_entropy
        elif task_type == 'regression':
            self.error_func = tf.losses.mean_squared_error
        else:
            raise Exception("Unknown task type")
        self.obs_shape = obs_shape
        self.label_shape = label_shape
        self.num_classes = num_classes
        self.alpha = alpha
        self.inner_iters = inner_iters
        self.eval_iters = eval_iters
        self.nonlinearity = nonlinearity
        self.bn = bn
        self.kernel_initializer = kernel_initializer
        self.kernel_regularizer = kernel_regularizer

        self.X_c = tf.placeholder(tf.float32, shape=tuple([None,]+obs_shape))
        self.y_c = tf.placeholder(tf.float32, shape=tuple([None,]+label_shape))
        self.X_t = tf.placeholder(tf.float32, shape=tuple([None,]+obs_shape))
        self.y_t = tf.placeholder(tf.float32, shape=tuple([None,]+label_shape))
        self.is_training = tf.placeholder(tf.bool, shape=())

        self.outputs = self._model()
        self.y_hat = self.outputs
        self.loss = self._loss()

        if self.task_type == 'classification':
            self._accuracy()
        elif self.task_type == 'regression':
            self.y_hat = self.outputs

        self.grads = tf.gradients(self.loss, get_trainable_variables([self.scope_name]), colocate_gradients_with_ops=True)

    def _model(self):
        default_args = {
            "nonlinearity": self.nonlinearity,
            "bn": self.bn,
            "kernel_initializer": self.kernel_initializer,
            "kernel_regularizer": self.kernel_regularizer,
            "is_training": self.is_training,
            "counters": self.counters,
            "num_classes": self.num_classes,
        }
        with arg_scope([self.regressor], **default_args):
            self.scope_name = get_name("maml_regressor", self.counters)
            with tf.variable_scope(self.scope_name):
                outputs = self.regressor(self.X_c)
                vars = get_trainable_variables([self.scope_name])
                outputs_t_arr = [self.regressor(self.X_t, params=vars.copy())]
                for k in range(1, max(self.inner_iters, self.eval_iters)+1):
                    loss = self.error_func(self.y_c, outputs)
                    grads = tf.gradients(loss, vars, colocate_gradients_with_ops=True)
                    vars = [v - self.alpha * g for v, g in zip(vars, grads)]
                    outputs = self.regressor(self.X_c, params=vars.copy())
                    outputs_t = self.regressor(self.X_t, params=vars.copy())
                    outputs_t_arr.append(outputs_t)
                self.eval_outputs = outputs_t_arr
                return outputs_t_arr[self.inner_iters]

    def _loss(self):
        self.losses = [self.error_func(self.y_t, o) for o in self.eval_outputs]
        return self.losses[1]
        #return self.error_func(labels=self.y_t, predictions=self.y_hat)

    def _accuracy(self):
        y_hat_arr = [tf.nn.softmax(o) for o in self.eval_outputs]
        self.y_hat = y_hat_arr[1]
        self.acc = accuracy(self.y_t, self.y_hat)
        self.accs = [accuracy(self.y_t, y_hat) for y_hat in y_hat_arr]

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


    def compute_loss(self, sess, X_c_value, y_c_value, X_t_value, y_t_value, is_training, step=None):
        feed_dict = {
            self.X_c: X_c_value,
            self.y_c: y_c_value,
            self.X_t: X_t_value,
            self.y_t: y_t_value,
            self.is_training: is_training,
        }
        if step is None:
            l = sess.run(self.loss, feed_dict=feed_dict)
        else:
            l = sess.run(self.losses[step], feed_dict=feed_dict)
        return l

    def compute_acc(self, sess, X_c_value, y_c_value, X_t_value, y_t_value, is_training, step=None):
        feed_dict = {
            self.X_c: X_c_value,
            self.y_c: y_c_value,
            self.X_t: X_t_value,
            self.y_t: y_t_value,
            self.is_training: is_training,
        }
        if step is None:
            l = sess.run(self.acc, feed_dict=feed_dict)
        else:
            l = sess.run(self.accs[step], feed_dict=feed_dict)
        return l



@add_arg_scope
def mlp5(X, params=None, num_classes=1, nonlinearity=None, bn=True, kernel_initializer=None, kernel_regularizer=None, is_training=False, counters={}):
    name = get_name("mlp5", counters)
    print("construct", name, "...")
    if params is not None:
        params.reverse()
    with tf.variable_scope(name):
        default_args = {
            "nonlinearity": nonlinearity,
            "bn": bn,
            "kernel_initializer": kernel_initializer,
            "kernel_regularizer": kernel_regularizer,
            "is_training": is_training,
            "counters": counters,
        }
        with arg_scope([dense], **default_args):
            batch_size = tf.shape(X)[0]
            size = 256
            outputs = X
            for k in range(4):
                if params is not None:
                    outputs = dense(outputs, size, W=params.pop(), b=params.pop())
                else:
                    outputs = dense(outputs, size)
            if params is not None:
                outputs = dense(outputs, 1, nonlinearity=None, W=params.pop(), b=params.pop())
            else:
                outputs = dense(outputs, 1, nonlinearity=None)
            outputs = tf.reshape(outputs, shape=(batch_size,))
            if params is not None:
                assert len(params)==0, "{0}: feed-in parameter list is not empty".format(name)
            return outputs


@add_arg_scope
def mlp2(X, params=None, num_classes=1, nonlinearity=None, bn=True, kernel_initializer=None, kernel_regularizer=None, is_training=False, counters={}):
    "Replicate Finn's MAML paper"
    name = get_name("mlp2", counters)
    print("construct", name, "...")
    if params is not None:
        params.reverse()
    with tf.variable_scope(name):
        default_args = {
            "nonlinearity": nonlinearity,
            "bn": bn,
            "kernel_initializer": kernel_initializer,
            "kernel_regularizer": kernel_regularizer,
            "is_training": is_training,
            "counters": counters,
        }
        with arg_scope([dense], **default_args):
            batch_size = tf.shape(X)[0]
            size = 40
            outputs = X
            for k in range(2):
                if params is not None:
                    outputs = dense(outputs, size, W=params.pop(), b=params.pop())
                else:
                    outputs = dense(outputs, size)
            if params is not None:
                outputs = dense(outputs, 1, nonlinearity=None, W=params.pop(), b=params.pop())
            else:
                outputs = dense(outputs, 1, nonlinearity=None)
            outputs = tf.reshape(outputs, shape=(batch_size,))
            if params is not None:
                assert len(params)==0, "{0}: feed-in parameter list is not empty".format(name)
            return outputs


@add_arg_scope
def omniglot_conv(X, params=None, num_classes=1, nonlinearity=None, bn=True, kernel_initializer=None, kernel_regularizer=None, is_training=False, counters={}):
    name = get_name("omniglot_conv", counters)
    print("construct", name, "...")
    if params is not None:
        params.reverse()
    with tf.variable_scope(name):
        default_args = {
            "nonlinearity": nonlinearity,
            "bn": bn,
            "kernel_initializer": kernel_initializer,
            "kernel_regularizer": kernel_regularizer,
            "is_training": is_training,
            "counters": counters,
        }
        with arg_scope([conv2d, dense], **default_args):
            outputs = X
            if params is None:
                outputs = conv2d(outputs, 64, filter_size=[3,3], stride=[1,1], pad="SAME")
                outputs = conv2d(outputs, 64, filter_size=[3,3], stride=[2,2], pad="SAME")
                outputs = conv2d(outputs, 128, filter_size=[3,3], stride=[1,1], pad="SAME")
                outputs = conv2d(outputs, 128, filter_size=[3,3], stride=[2,2], pad="SAME")
                outputs = conv2d(outputs, 256, filter_size=[4,4], stride=[1,1], pad="VALID")
                outputs = conv2d(outputs, 256, filter_size=[4,4], stride=[1,1], pad="VALID")
                outputs = tf.reshape(outputs, [-1, 256])
                y = dense(outputs, num_classes, nonlinearity=None, bn=False)
            else:
                outputs = conv2d(outputs, 64, W=params.pop(), b=params.pop(), filter_size=[3,3], stride=[1,1], pad="SAME")
                outputs = conv2d(outputs, 64, W=params.pop(), b=params.pop(), filter_size=[3,3], stride=[2,2], pad="SAME")
                outputs = conv2d(outputs, 128, W=params.pop(), b=params.pop(), filter_size=[3,3], stride=[1,1], pad="SAME")
                outputs = conv2d(outputs, 128, W=params.pop(), b=params.pop(), filter_size=[3,3], stride=[2,2], pad="SAME")
                outputs = conv2d(outputs, 256, W=params.pop(), b=params.pop(), filter_size=[4,4], stride=[1,1], pad="VALID")
                outputs = conv2d(outputs, 256, W=params.pop(), b=params.pop(), filter_size=[4,4], stride=[1,1], pad="VALID")
                outputs = tf.reshape(outputs, [-1, 256])
                y = dense(outputs, num_classes, W=params.pop(), b=params.pop(), nonlinearity=None, bn=False)
                assert len(params)==0, "{0}: feed-in parameter list is not empty".format(name)
            return y
