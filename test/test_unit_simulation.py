import sys
import os
import pytest
import random

import numpy as np

from . import common

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_trivial():
    from adjsim import simulation

    test_sim = simulation.Simulation()

    common.step_simulate_interpolation(test_sim)

    assert test_sim.time == common.INTERPOLATION_NUM_TIMESTEP

def test_valid_end_condition():
    from adjsim import simulation

    test_sim = simulation.Simulation()
    test_sim.end_condition = lambda env: env.time == common.INTERPOLATION_NUM_TIMESTEP - 1

    common.step_simulate_interpolation(test_sim)

    assert test_sim.time == common.INTERPOLATION_NUM_TIMESTEP

def test_invalid_end_condition():
    from adjsim import simulation, utility

    test_sim = simulation.Simulation()
    test_sim.end_condition = True

    with pytest.raises(utility.InvalidEndConditionException):
        common.step_simulate_interpolation(test_sim)



def test_visual_trivial():
    from adjsim import simulation, analysis, utility

    test_sim = simulation.VisualSimulation()
    test_sim._wait_on_visual_init = 0
    common.step_simulate_interpolation(test_sim)


def test_visual_move():
    from adjsim import simulation, analysis, utility

    def move(env, source):
        source.x += 10
        source.y += 10

    class TestAgent(simulation.VisualAgent):
        def __init__(self, x, y):
            super().__init__(pos=np.array([x, y]))
            self.actions["move"] = move


    test_sim = simulation.VisualSimulation()
    test_sim._wait_on_visual_init = 0
    test_sim.agents.add(TestAgent(0, 0))
    test_sim.agents.add(TestAgent(0, -10))

    common.step_simulate_interpolation(test_sim)

def test_visual_color():
    from adjsim import simulation, analysis, utility
    from PyQt5 import QtGui

    def change(env, source):
        if env.time % 2:
            source.color = QtGui.QColor(utility.BLUE_DARK)
        else:
            source.color = QtGui.QColor(utility.RED_DARK)

    class TestAgent(simulation.VisualAgent):
        def __init__(self, x, y):
            super().__init__(pos=np.array([x, y]))
            self.actions["change"] = change


    test_sim = simulation.VisualSimulation()
    test_sim._wait_on_visual_init = 0
    test_sim.agents.add(TestAgent(0, 0))

    common.step_simulate_interpolation(test_sim)

def test_visual_order():
    from adjsim import simulation, analysis, utility
    from PyQt5 import QtGui

    order_log = []
    orders = [i for i in range(5)]

    def log(env, source):
        order_log.append(source.order)
        source.order = orders[source.index]

    def shuffle(env, source):
        random.shuffle(orders)

    class TestAgent(simulation.Agent):
        def __init__(self, order):
            super().__init__()
            self.actions["log"] = log
            self.order = order
            self.index = order

    class Shuffler(simulation.Agent):
        def __init__(self):
            super().__init__()
            self.actions["shuffle"] = shuffle
            self.order = 10

    test_sim = simulation.Simulation()
    test_sim.agents.add(Shuffler())

    for i in orders:
        test_sim.agents.add(TestAgent(i))

    common.step_simulate_interpolation(test_sim)

    assert order_log == [i for i in range(5)]*common.INTERPOLATION_NUM_TIMESTEP


    
    
    


    