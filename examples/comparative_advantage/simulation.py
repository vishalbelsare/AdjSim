"""Comparative Advantage Simulation

Illustrates the phenomenon of Ricardian Comparative Advantage in a free market trading environment.
See https://en.wikipedia.org/wiki/Comparative_advantage.
"""

# Standard.
import sys
import os
import copy
import math

# Third party.
import numpy as np
from adjsim import analysis, core, utility, decision, color
from matplotlib import pyplot


MAX_TRADE_AMOUNT = 10


def perception(simulation, source):
    return None

def loss(simulation, source):
    # Use change in commodities as loss.
    delta = source.commodities - source.previous_commodities
    source.previous_commodities = copy.copy(source.commodities)
    return -np.average(delta) if simulation.time > 1 else 0 # Ignore delta calculation of first timestep.

def trade_commodity(simulation, source):

    # Convenience variables.
    sell_commodity = source.trade_sell_commodity.value
    buy_commodity = source.trade_buy_commodity.value
    target_agent = simulation.trader_index[source.trade_target_index.value]

    # Agents can't trade with themselves.
    if target_agent == source:
        return

    # Remove the commodity from the selling agent.
    sell_amount = np.clip(source.trade_amount.value, 0, source.commodities[sell_commodity])
    sell_amount_converted = sell_amount * simulation.commodity_conversions[sell_commodity, buy_commodity]

    # Create Mediation Log Entry.
    mediation_log_entry = MediationLogEntry.from_agent(source)
    mediation_log_entry_inverse = MediationLogEntry.inverse(mediation_log_entry)

    # Make sure there is something to sell.
    if math.isclose(sell_amount, 0):
        return

    # Deduct sell amount.
    source.commodities[sell_commodity] -= sell_amount

    # Check to see if inverse exists
    existing_inverse = simulation.transaction_mediation_log.get(mediation_log_entry_inverse)
    if existing_inverse is not None:
        existing_converted = existing_inverse * simulation.commodity_conversions[buy_commodity, sell_commodity]

        # Perform transaction.
        if existing_inverse >= sell_amount_converted:
            simulation.transaction_mediation_log[mediation_log_entry_inverse] -= sell_amount_converted

            if simulation.transaction_mediation_log[mediation_log_entry_inverse] == 0:
                del simulation.transaction_mediation_log[mediation_log_entry_inverse]
            
            target_agent.commodities[sell_commodity] += sell_amount
            source.commodities[buy_commodity] += sell_amount_converted

            simulation.trackers["transaction"].on_transaction(Transaction(simulation, source.index, sell_commodity, sell_amount, target_agent.index, buy_commodity, sell_amount_converted))

        elif existing_inverse < sell_amount_converted:
            del simulation.transaction_mediation_log[mediation_log_entry_inverse]
            simulation.transaction_mediation_log[mediation_log_entry] = sell_amount - existing_converted

            target_agent.commodities[sell_commodity] += existing_converted
            source.commodities[buy_commodity] += existing_inverse

            simulation.trackers["transaction"].on_transaction(Transaction(simulation, source.index, sell_commodity, existing_converted, target_agent.index, buy_commodity, existing_inverse))
            
    else:
        existing_current = simulation.transaction_mediation_log.get(mediation_log_entry)
        if existing_current is None:
            simulation.transaction_mediation_log[mediation_log_entry] = sell_amount
        else:
            simulation.transaction_mediation_log[mediation_log_entry] += sell_amount


def allocate_production(simulation, source):
    if not source.production_allocation is None:
        return

    source.production_allocation = source.production_allocation_assignation.value

def done(simulation, source):
    source.step_complete = True


def pre_step(simulation, source):
    # Generate commodities.
    for agent in simulation.agents:
        if type(agent) == Trader:
            allocation = np.zeros((len(simulation.commodities),)) if agent.production_allocation is None else agent.production_allocation
            agent.commodities += agent.production_rates * allocation
            agent.production_allocation = None

    # Refund mediation log.
    for key, val in simulation.transaction_mediation_log.items():
        simulation.trader_index[key[0]].commodities[key[1]] += val

    # Clear mediation log.
    simulation.transaction_mediation_log = {}

class Transaction(object):
    def __init__(self, simulation, agent_a, commodity_a, amount_a, agent_b, commodity_b, amount_b):
        self.simulation = simulation

        self.agent_a = agent_a
        self.commodity_a = commodity_a
        self.amount_a = amount_a

        self.agent_b = agent_b
        self.commodity_b = commodity_b
        self.amount_b = amount_b

    def inverse(self):
        return Transaction(self.simulation, self.agent_b, self.commodity_b, self.amount_b, self.agent_a, self.commodity_b, self.amount_b)

    def __repr__(self):
        return """
        +-
        | Agent {} trades {} {}
        | Agent {} trades {} {}
        +-
        """.format(
            self.simulation.trader_index[self.agent_a].name, 
            self.simulation.commodities[self.commodity_a], 
            self.amount_a, 
            self.simulation.trader_index[self.agent_b].name, 
            self.simulation.commodities[self.commodity_b], 
            self.amount_b
        )

class TransactionTracker(analysis.Tracker):
    def __init__(self):
        self.data = []
        self._commodities = None

    def __call__(self, simulation):
        self.data.append([])

        if self._commodities is None:
            self._commodities = simulation.commodities

    def on_transaction(self, transaction):
        self.data[-1].append(transaction)

    def __repr__(self):
        return self.data.__repr__()

    def plot(self, block=True):
        pyplot.style.use('ggplot')

        commodity_log_list = [[] for _ in self._commodities]

        for transactions in self.data:
            # Initialize commodity list for current timestep.
            for commodity_log in commodity_log_list:
                commodity_log.append(0)
            
            # Add transactions to log.
            for transaction in transactions:
                commodity_log_list[transaction.commodity_a][-1] += transaction.amount_a
                commodity_log_list[transaction.commodity_b][-1] += transaction.amount_b

        for i in range(len(commodity_log_list)):
            line, = pyplot.plot(commodity_log_list[i], label=self._commodities[i])
            line.set_antialiased(True)

        pyplot.xlabel('Timestep')
        pyplot.ylabel('Quantity Traded')
        pyplot.title('Commodity Trade Log')
        pyplot.legend()

        pyplot.show(block=block)

class AllocationTracker(analysis.Tracker):
    def __init__(self):
        self.data = {}

    def __call__(self, simulation):
        for agent in simulation.agents:
            # Only process traders.
            if not isinstance(agent, Trader):
                continue

            # New trader entry.
            existing_trader = self.data.get(agent)
            if existing_trader is None:
                self.data[agent] = dict([(name, []) for name in simulation.commodities])

            # Store allocation per commodity.
            for i in range(len(simulation.commodities)):
                new_val = 0 if agent.production_allocation is None else agent.production_allocation[i]
                self.data[agent][simulation.commodities[i]].append(new_val)
            

    def plot(self, block=True):
        pyplot.style.use('ggplot')

        # New plot for each agent.
        for agent, entry in self.data.items():
            # Plot all commodities.
            for commodity, allocation in entry.items():
                line, = pyplot.plot(allocation, label=commodity)
                line.set_antialiased(True)

            pyplot.xlabel('Timestep')
            pyplot.ylabel('Production Allocation')
            pyplot.title(agent.name + ' Commodity Production Allocation')
            pyplot.legend()

            pyplot.show(block=block)

        # Plot running averages.
        for agent, entry in self.data.items():
            # Plot all commodities.
            for commodity, allocation in entry.items():
                line, = pyplot.plot(AllocationTracker.running_mean(allocation, 500), label=commodity)
                line.set_antialiased(True)

            pyplot.xlabel('Timestep')
            pyplot.ylabel('Average Production Allocation')
            pyplot.title(agent.name + ' Average Commodity Production Allocation')
            pyplot.legend()

            pyplot.show(block=block)
    
    @staticmethod
    def running_mean(x, N):
        cumsum = np.cumsum(np.insert(x, 0, 0)) 
        return (cumsum[N:] - cumsum[:-N]) / float(N)

class MediationLogEntry(object):
    @staticmethod
    def from_agent(agent):
        return (agent.index, agent.trade_sell_commodity.value, agent.trade_target_index.value, agent.trade_buy_commodity.value)

    @staticmethod
    def inverse(entry):
        return (entry[2], entry[3], entry[0], entry[1])


class Trader(core.Agent):
    def __init__(self, simulation, name, production_rates, total_num_traders, index=None):
        super().__init__()

        self.name = name
        self.commodities = np.zeros([len(simulation.commodities)], dtype=np.float_)
        self.production_rates = production_rates
        self.production_capacity = len(production_rates)
        self.production_allocation = None
        self.index = index

        self.trade_sell_commodity = decision.DecisionMutableInt(0, len(simulation.commodities) - 1, 0.5)
        self.trade_buy_commodity = decision.DecisionMutableInt(0, len(simulation.commodities) - 1, 0.5)
        self.trade_target_index = decision.DecisionMutableInt(0, total_num_traders - 1, 0.5)
        self.trade_amount = decision.DecisionMutableFloat(0, MAX_TRADE_AMOUNT, 2)
        sum_constraint = decision.PositiveSumConstraint(self.production_capacity)
        self.production_allocation_assignation = decision.DecisionMutableFloatArray((len(simulation.commodities),), sum_constraint, 0.5)

        self.previous_commodities = production_rates # Initial value doesnt matter here.

        io_file_name = "trader-{}.qlearning.pkl".format(self.name)
        self.decision = decision.PerturbativeQLearningDecision(perception, loss, simulation,
            input_file_name=io_file_name, output_file_name=io_file_name, 
            nonconformity_probability=.9 if simulation.is_training else 0.4,
            discount_factor=0,
            perturbation_config=decision.PerturbativeQLearningDecision.Config(0.1, 0.4, 0.9))
        simulation.trackers["qlearning_" + name] = analysis.QLearningHistoryTracker(self.decision)

        self.actions["done"] = done
        self.actions["trade_commodity"] = trade_commodity
        self.actions["allocate_production"] = allocate_production
        

class Meta(core.Agent):
    def __init__(self):
        super().__init__()

        self.order = -1

        self.decision = decision.RandomSingleCastDecision()

        self.actions["pre_step"] = pre_step


class TraderSimulation(core.Simulation):

    def __init__(self, templates, commodities, commodity_conversions, is_training=True):
        super().__init__()

        self.trader_index = []
        self.transaction_mediation_log = {}
        self.is_training = is_training
        self.commodities = commodities
        self.commodity_conversions = commodity_conversions
        
        self.trackers["transaction"] = TransactionTracker()
        self.trackers["allocation"] = AllocationTracker()

        for template in templates:
            trader = Trader(self, template[0], template[1], len(templates))
            self.trader_index.append(trader)
            trader.index = len(self.trader_index) - 1

            self.agents.add(trader)

        self.agents.add(Meta())

