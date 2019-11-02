# TODO add better input rep than flat to state?
# https://www.udemy.com/course/deep-reinforcement-learning-in-python

import tensorflow as tf
#tf.debugging.set_log_device_placement(True)
gpus = tf.config.experimental.list_physical_devices('GPU')
if gpus:
  try:
    # Currently, memory growth needs to be the same across GPUs
    for gpu in gpus:
      tf.config.experimental.set_memory_growth(gpu, True)
    logical_gpus = tf.config.experimental.list_logical_devices('GPU')
    print(len(gpus), "Physical GPUs,", len(logical_gpus), "Logical GPUs")
  except RuntimeError as e:
    # Memory growth must be set before GPUs have been initialized
    print(e)


from tensorflow.keras.backend import set_floatx
from tensorflow.keras.models import load_model
set_floatx('float64')
import numpy as np
from Env.Simulator_New import Simulator
import multiprocessing
import concurrent.futures
import itertools
from P_actor import ParameterAgent
from DQN import DQN_Agent
from Worker_constrained import Worker
from Worker_onlyDQN import Worker_DQN
import time
from tester import Tester
from utils import Plotter
from tensorflow.keras.optimizers import RMSprop



"""
KEY INPUTS
"""
alpha = 0.0001
beta = 0.001
env = Simulator()
n_continuous_actions = env.continuous_action_space.shape[0]
n_discrete_actions = env.discrete_action_space.n
state_shape = env.observation_space.shape
layer1_size = 100
layer2_size = 50
layer3_size = 50
max_global_steps = 50000 #100000
steps_per_update = 6
num_workers = multiprocessing.cpu_count()

global_counter = itertools.count()
global_counter2 = itertools.count()
max_global_steps2 = max_global_steps #100000
returns_list = []

# Build Models
with tf.device('/CPU:0'):
    param_model, param_optimizer = ParameterAgent(beta, n_continuous_actions, state_shape,
                                                                    "Param_model", layer1_size=layer1_size,
                                                                    layer2_size=layer2_size).build_network()
    dqn_model, dqn_optimizer = DQN_Agent(alpha, n_discrete_actions, n_continuous_actions, state_shape, "DQN_model",
                               layer1_size, layer2_size, layer3_size).build_network()
    #param_model = load_model("param_model.h5")
    #dqn_model = load_model("dqn_model.h5")
    # Create Workers
    start_time = time.time()
    workers = []
    for worker_id in range(num_workers):
        worker = Worker(
            name=f'worker {worker_id}',
            global_network_P=param_model,
            global_network_dqn=dqn_model,
            global_optimizer_P=param_optimizer,
            global_optimizer_dqn=dqn_optimizer,
            global_counter=global_counter,
            env=Simulator(),
            max_global_steps=max_global_steps,
            returns_list=returns_list,
            n_steps=steps_per_update)
        workers.append(worker)


    coord = tf.train.Coordinator()
    worker_fn = lambda worker_: worker_.run(coord)
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        executor.map(worker_fn, workers, timeout=10)

    run_time = time.time() - start_time
    print(f'runtime part 1 is {run_time/60} min')

    param_model.save("param_model.h5")
    """
    NOW DQN WITH PARAM NET FROZEN
    """
    # now keep param constant
    # Create Workers
    start_time = time.time()
    workers = []
    for worker_id in range(num_workers):
        worker = Worker_DQN(
            name=f'worker {worker_id}',
            global_network_P=param_model,
            global_network_dqn=dqn_model,
            global_optimizer_P=param_optimizer,
            global_optimizer_dqn=RMSprop(lr=0.01),
            global_counter=global_counter2,
            env=Simulator(),
            max_global_steps=max_global_steps2,
            returns_list=returns_list,
            n_steps=steps_per_update)
        workers.append(worker)


    coord = tf.train.Coordinator()
    worker_fn = lambda worker_: worker_.run(coord)
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        executor.map(worker_fn, workers, timeout=10)

    run_time = time.time() - start_time
    print(f'runtime part 2 is {run_time/60} min')


dqn_model.save("dqn_model.h5")
reward_data = np.array(returns_list)
np.savetxt("rewards.csv", reward_data, delimiter=",")

#plotter = Plotter(returns_list, len(returns_list)-1)
#plotter.plot(save=True)
plotter = Plotter(returns_list, len(returns_list)-1)
plotter.plot(save=True, freeze_point=round(max_global_steps*len(returns_list)/(max_global_steps2+max_global_steps)))

env = Tester(param_model, dqn_model, Simulator()).test()
env.split_order
env.sep_order
