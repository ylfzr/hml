import sys
import random
import time
import numpy as np
import tensorflow as tf
from misc.optimizers import adam_updates

def cosort_x(x, y):
    p = np.argsort(x)
    return x[p], y[p]

class MetaLearner(object):

    def __init__(self, session, parallel_models, optimize_op, train_set=None, eval_set=None, variables=None, lr=0.001, device_type='gpu', tags=["test"], cdir="", rdir=""):

        self.session = session
        self.parallel_models = parallel_models
        self.nr_model = len(parallel_models)
        if variables is not None:
            self.variables = variables
        else:
            self.variables = tf.trainable_variables()
        self.optimize_op = optimize_op
        self.clock = time.time()
        self.train_set = train_set
        self.eval_set = eval_set

        self.lr = lr
        self.save_dir = self.train_set.dataset_name + "-" + "-".join(tags)

        grads = []
        for i in range(self.nr_model):
            grads.append(self.parallel_models[i].grads)
        with tf.device('/' + device_type + ':0'):
            for i in range(1, self.nr_model):
                for j in range(len(grads[0])):
                    grads[0][j] += grads[i][j]
                    # try:
                    #     grads[0][j] += grads[i][j]
                    # except:
                    #     grads[0][j] = 0.
        self.aggregated_grads = grads[0]

        self.optimize_op = adam_updates(variables, self.aggregated_grads, lr=self.lr)


    def qclock(self):
        cur_time = time.time()
        tdiff = cur_time - self.clock
        self.clock = cur_time
        return tdiff

    def set_session(self, sess):
        self.session = sess

    def get_session(self):
        return self.session

    def train(self, meta_batch, gen_num_shots, gen_test_shots):
        assert meta_batch==self.nr_model, "nr_model != meta_batch"
        tasks = self.train_set.sample(meta_batch)
        feed_dict = {}
        for i, task in enumerate(tasks):
            num_shots = gen_num_shots()
            test_shots = gen_test_shots()

            X_c_value, y_c_value, X_t_value, y_t_value = task.sample(num_shots, test_shots)
            X_value = np.concatenate([X_c_value, X_t_value], axis=0)
            y_value = np.concatenate([y_c_value, y_t_value], axis=0)
            feed_dict.update({
                self.parallel_models[i].X_c: X_c_value,
                self.parallel_models[i].y_c: y_c_value,
                self.parallel_models[i].X_t: X_t_value,
                self.parallel_models[i].y_t: y_t_value,
                self.parallel_models[i].is_training: True,
            })
        self.get_session().run(self.optimize_op, feed_dict=feed_dict)



    def evaluate(self, eval_samples, gen_num_shots, gen_test_shots):
        evals = []
        eval_meta_batch = eval_samples // self.nr_model
        for i in range(eval_meta_batch):
            tasks = self.eval_set.sample(self.nr_model)
            num_shots = gen_num_shots()
            test_shots = gen_test_shots()

            run_ops, feed_dict = [], {}
            for k, task in enumerate(tasks):
                X_c_value, y_c_value, X_t_value, y_t_value = task.sample(num_shots, test_shots)
                X_value = np.concatenate([X_c_value, X_t_value], axis=0)
                y_value = np.concatenate([y_c_value, y_t_value], axis=0)
                ## !! training data is not included in the evaluation, different from neural process
                ops, d = self.parallel_models[k].evaluate_metrics(X_c_value, y_c_value, X_t_value, y_t_value, step=1)
                run_ops += ops
                feed_dict.update(d)
                ops, d = self.parallel_models[k].evaluate_metrics(X_c_value, y_c_value, X_t_value, y_t_value, step=2)
                run_ops += ops
                feed_dict.update(d)
                ops, d = self.parallel_models[k].evaluate_metrics(X_c_value, y_c_value, X_t_value, y_t_value, step=3)
                run_ops += ops
                feed_dict.update(d)
            ls = np.array(self.get_session().run(run_ops, feed_dict=feed_dict))
            ls = np.reshape(ls, (self.nr_model, len(ls)//self.nr_model))
            ls = np.mean(ls, axis=0)
            evals.append(ls)
        return np.mean(evals, axis=0)


    def visualise(self, save_name):
        pass

    def run_train(self):
        pass
