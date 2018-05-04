import random
import math
import os

import numpy as np
import pandas as pd

from pysc2.agents import base_agent
from pysc2.lib import actions
from pysc2.lib import features


#----------------------------Actions IDs---------------------
_NO_OP = actions.FUNCTIONS.no_op.id
_SELECT_POINT = actions.FUNCTIONS.select_point.id
_BUILD_SUPPLY_DEPOT = actions.FUNCTIONS.Build_SupplyDepot_screen.id
_BUILD_BARRACKS = actions.FUNCTIONS.Build_Barracks_screen.id
_TRAIN_MARINE = actions.FUNCTIONS.Train_Marine_quick.id
_SELECT_ARMY = actions.FUNCTIONS.select_army.id
_ATTACK_MINIMAP = actions.FUNCTIONS.Attack_minimap.id
_HARVEST_GATHER = actions.FUNCTIONS.Harvest_Gather_screen.id
_SMART_SELECT = actions.FUNCTIONS.Smart_screen.id
#________________________CHRIS ADDS + 3
_RALLY_CC = actions.FUNCTIONS.Rally_Workers_screen.id
_BUILD_SCV = actions.FUNCTIONS.Train_SCV_quick.id
# _BUILD_REFINERY = actions.FUNCTIONS.Build_Refinery_screen.id
############################################################

#----------------------------Features---------------------
_PLAYER_RELATIVE = features.SCREEN_FEATURES.player_relative.index
_UNIT_TYPE = features.SCREEN_FEATURES.unit_type.index
_PLAYER_ID = features.SCREEN_FEATURES.player_id.index
############################################################

#----------------------------Unit IDs---------------------
_PLAYER_SELF = 1
_PLAYER_HOSTILE = 4
_ARMY_SUPPLY = 5

_TERRAN_COMMANDCENTER = 18
_TERRAN_SCV = 45
_TERRAN_SUPPLY_DEPOT = 19
_TERRAN_BARRACKS = 21
_NEUTRAL_MINERAL_FIELD = 341
_NEUTRAL_VESPENEGEYSER = 342
# _TERRAN_REFINERY = 20
############################################################

#----------------------------Action Type IDs---------------------
_NOT_QUEUED = [0]
_QUEUED = [1]
_SELECT_ALL = [2]
############################################################

#----------------------------Pickle File Name---------------------
DATA_FILE = 'mod_agent_data'
############################################################

#----------------------------Actions---------------------
ACTION_DO_NOTHING = 'donothing'
ACTION_BUILD_SUPPLY_DEPOT = 'buildsupplydepot'
ACTION_BUILD_BARRACKS = 'buildbarracks'
ACTION_BUILD_MARINE = 'buildmarine'
ACTION_ATTACK = 'attack'
#________________________CHRIS ADDS
ACTION_RALLY_CC = 'rallycc'
ACTION_BUILD_SCV = 'buildscv'
# ACTION_BUILD_REFINERY = 'buildrefinery'
############################################################

#----------------------------Action Pool---------------------
smart_actions = [
    ACTION_DO_NOTHING,
    ACTION_BUILD_SUPPLY_DEPOT,
    ACTION_BUILD_BARRACKS,
    ACTION_BUILD_MARINE,
    ACTION_RALLY_CC,
    ACTION_BUILD_SCV
]

for mm_x in range(0, 64):
    for mm_y in range(0, 64):
        if (mm_x + 1) % 32 == 0 and (mm_y + 1) % 32 == 0:
            smart_actions.append(ACTION_ATTACK + '_' + str(mm_x - 16) + '_' + str(mm_y - 16))

############################################################

#----------------------------Q Learning Class---------------------
# Stolen from https://github.com/MorvanZhou/Reinforcement-learning-with-tensorflow
class QLearningTable:
    def __init__(self, actions, learning_rate=0.1, reward_decay=0.7, e_greedy=0.6):
        self.actions = actions  # a list
        self.lr = learning_rate
        self.gamma = reward_decay
        self.epsilon = e_greedy
        self.q_table = pd.DataFrame(columns=self.actions, dtype=np.float64)
        self.disallowed_actions = {}

    def choose_action(self, observation, excluded_actions=[]):
        self.check_state_exist(observation)

        self.disallowed_actions[observation] = excluded_actions

        state_action = self.q_table.ix[observation, :]

        for excluded_action in excluded_actions:
            del state_action[excluded_action]

        if np.random.uniform() < self.epsilon:
            # some actions have the same value
            state_action = state_action.reindex(np.random.permutation(state_action.index))

            action = state_action.idxmax()
        else:
            action = np.random.choice(state_action.index)

        return action

    def learn(self, s, a, r, s_):
        if s == s_:
            return

        self.check_state_exist(s_)
        self.check_state_exist(s)

        q_predict = self.q_table.ix[s, a]

        s_rewards = self.q_table.ix[s_, :]

        if s_ in self.disallowed_actions:
            for excluded_action in self.disallowed_actions[s_]:
                del s_rewards[excluded_action]

        if s_ != 'terminal':
            q_target = r + self.gamma * s_rewards.max()
        else:
            q_target = r  # next state is terminal

        # update
        self.q_table.ix[s, a] += self.lr * (q_target - q_predict)

    def check_state_exist(self, state):
        if state not in self.q_table.index:
            # append new state to q table
            self.q_table = self.q_table.append(pd.Series([0] * len(self.actions), index=self.q_table.columns, name=state))

############################################################

#----------------------------Agent Class---------------------
class SparseAgent(base_agent.BaseAgent):
    def __init__(self):
        super(SparseAgent, self).__init__()

        self.qlearn = QLearningTable(actions=list(range(len(smart_actions))))

        self.previous_action = None
        self.previous_state = None

        self.cc_y = None
        self.cc_x = None

        self.move_number = 0

        if os.path.isfile(DATA_FILE + '.gz'):
            self.qlearn.q_table = pd.read_pickle(DATA_FILE + '.gz', compression='gzip')

    def transformDistance(self, x, x_distance, y, y_distance):
        if not self.base_top_left:
            return [x - x_distance, y - y_distance]

        return [x + x_distance, y + y_distance]

    def transformLocation(self, x, y):
        if not self.base_top_left:
            return [64 - x, 64 - y]

        return [x, y]

    def splitAction(self, action_id):
        smart_action = smart_actions[action_id]

        x = 0
        y = 0
        if '_' in smart_action:
            smart_action, x, y = smart_action.split('_')

        return (smart_action, x, y)

#----------------------------Main Action Logic---------------------
    def step(self, obs):
        super(SparseAgent, self).step(obs)

#MOVE last -------------------------------------------------

        if obs.last():
            reward = obs.reward
            fd = open('chris_mod_agent_res.csv', 'a')
            fd.write(str(reward))
            fd.write('\n')
            fd.close()

            self.qlearn.learn(str(self.previous_state), self.previous_action, reward, 'terminal')

            self.qlearn.q_table.to_pickle(DATA_FILE + '.gz', 'gzip')

            self.previous_action = None
            self.previous_state = None

            self.move_number = 0

            return actions.FunctionCall(_NO_OP, [])

        unit_type = obs.observation['screen'][_UNIT_TYPE]

#MOVE first -------------------------------------------------

        if obs.first():
            player_y, player_x = (obs.observation['minimap'][_PLAYER_RELATIVE] == _PLAYER_SELF).nonzero()
            self.base_top_left = 1 if player_y.any() and player_y.mean() <= 31 else 0

            self.cc_y, self.cc_x = (unit_type == _TERRAN_COMMANDCENTER).nonzero()

        cc_y, cc_x = (unit_type == _TERRAN_COMMANDCENTER).nonzero()
        cc_count = 1 if cc_y.any() else 0

        depot_y, depot_x = (unit_type == _TERRAN_SUPPLY_DEPOT).nonzero()
        supply_depot_count = int(round(len(depot_y) / 69))

        barracks_y, barracks_x = (unit_type == _TERRAN_BARRACKS).nonzero()
        barracks_count = int(round(len(barracks_y) / 137))

        # refinery_y, refinery_x = (unit_type == _TERRAN_REFINERY).nonzero()
        # refinery_count = int(round(len(barracks_y) / 137))

        mining_vespene_ct = 0

        supply_used = obs.observation['player'][3]
        supply_limit = obs.observation['player'][4]
        army_supply = obs.observation['player'][5]
        worker_supply = obs.observation['player'][6]

        supply_free = supply_limit - supply_used

        #________________________CHRIS ADDS
        cc_rallied = 0
        army_supply = obs.observation['player'][8]

#MOVE 0 -------------------------------------------------

        if self.move_number == 0:
            self.move_number += 1

            current_state = np.zeros(15)
            current_state[0] = cc_count
            current_state[1] = supply_depot_count
            current_state[2] = barracks_count
            current_state[3] = obs.observation['player'][_ARMY_SUPPLY]
            #________________________CHRIS ADDS
            current_state[4] = cc_rallied
            current_state[5] = worker_supply
            current_state[6] = army_supply
            # current_state[7] = refinery_count

            hot_squares = np.zeros(4)
            enemy_y, enemy_x = (obs.observation['minimap'][_PLAYER_RELATIVE] == _PLAYER_HOSTILE).nonzero()
            for i in range(0, len(enemy_y)):
                y = int(math.ceil((enemy_y[i] + 1) / 32))
                x = int(math.ceil((enemy_x[i] + 1) / 32))

                hot_squares[((y - 1) * 2) + (x - 1)] = 1

            if not self.base_top_left:
                hot_squares = hot_squares[::-1]

            for i in range(0, 4):
                current_state[i + 7] = hot_squares[i]

            green_squares = np.zeros(4)
            friendly_y, friendly_x = (obs.observation['minimap'][_PLAYER_RELATIVE] == _PLAYER_SELF).nonzero()
            for i in range(0, len(friendly_y)):
                y = int(math.ceil((friendly_y[i] + 1) / 32))
                x = int(math.ceil((friendly_x[i] + 1) / 32))

                green_squares[((y - 1) * 2) + (x - 1)] = 1

            if not self.base_top_left:
                green_squares = green_squares[::-1]

            for i in range(0, 4):
                current_state[i + 11] = green_squares[i]

            if self.previous_action is not None:
                self.qlearn.learn(str(self.previous_state), self.previous_action, 0, str(current_state))

            excluded_actions = []
            if supply_depot_count == 10 or worker_supply == 0:
                excluded_actions.append(1)

            if supply_depot_count == 0 or barracks_count == 3 or worker_supply == 0:
                excluded_actions.append(2)

            if supply_free == 0 or barracks_count == 0:
                excluded_actions.append(3)
                excluded_actions.append(5)

            if army_supply == 0:
                excluded_actions.append(6)
                excluded_actions.append(7)
                excluded_actions.append(8)
                excluded_actions.append(9)

            if cc_rallied == 1:
                excluded_actions.append(4)

            rl_action = self.qlearn.choose_action(str(current_state), excluded_actions)

            self.previous_state = current_state
            self.previous_action = rl_action

            smart_action, x, y = self.splitAction(self.previous_action)

            if smart_action == ACTION_RALLY_CC or smart_action == ACTION_BUILD_SCV:
                if cc_y.any():
                    target = [cc_x.mean(), cc_y.mean()]

                    return actions.FunctionCall(_SELECT_POINT, [_SELECT_ALL, target])

            elif smart_action == ACTION_BUILD_BARRACKS or smart_action == ACTION_BUILD_SUPPLY_DEPOT:
                unit_y, unit_x = (unit_type == _TERRAN_SCV).nonzero()
                if unit_y.any():
                    i = random.randint(0, len(unit_y) - 1)
                    target = [unit_x[i], unit_y[i]]

                    return actions.FunctionCall(_SELECT_POINT, [_NOT_QUEUED, target])

            elif smart_action == ACTION_BUILD_MARINE:
                if barracks_y.any():
                    i = random.randint(0, len(barracks_y) - 1)
                    target = [barracks_x[i], barracks_y[i]]

                    return actions.FunctionCall(_SELECT_POINT, [_SELECT_ALL, target])

            elif smart_action == ACTION_ATTACK:
                if _SELECT_ARMY in obs.observation['available_actions']:
                    return actions.FunctionCall(_SELECT_ARMY, [_NOT_QUEUED])

#MOVE 1 -------------------------------------------------

        elif self.move_number == 1:
            self.move_number += 1

            smart_action, x, y = self.splitAction(self.previous_action)

            #Rally CC
            if smart_action == ACTION_RALLY_CC:
                if cc_count == 1 and _RALLY_CC in obs.observation['available_actions']:
                    if _HARVEST_GATHER in obs.observation['available_actions']:
                        unit_y, unit_x = (unit_type == _NEUTRAL_MINERAL_FIELD).nonzero()

                        if unit_y.any():
                            i = random.randint(0, len(unit_y) - 1)
                            m_x = unit_x[i]
                            m_y = unit_y[i]
                            target = [int(m_x), int(m_y)]
                            cc_rallied = 1

                            return actions.FunctionCall(_RALLY_CC, [_NOT_QUEUED, target])

            #Build Refinery
            # elif smart_action == ACTION_BUILD_REFINERY:
            #     if _BUILD_REFINERY in obs.observation['available_actions']:
            #         unit_y, unit_x = (unit_type == _NEUTRAL_VESPENEGEYSER).nonzero()
            #         if unit_y.any():
            #             i = random.randint(0, len(unit_y) - 1)
            #
            #             m_x = unit_x[i]
            #             m_y = unit_y[i]
            #
            #             target = [int(m_x), int(m_y)]
            #
            #             return actions.FunctionCall(_BUILD_REFINERY, [_QUEUED, target])

            #Build SCV
            elif smart_action == ACTION_BUILD_SCV:
                if _BUILD_SCV in obs.observation['available_actions']:
                    return actions.FunctionCall(_BUILD_SCV, [_QUEUED])

            #Build Supply Depot limit 10
            elif smart_action == ACTION_BUILD_SUPPLY_DEPOT:
                if supply_depot_count < 10 and _BUILD_SUPPLY_DEPOT in obs.observation['available_actions']:
                    if self.cc_y.any():
                        if supply_depot_count == 0:
                            target = self.transformDistance(round(self.cc_x.mean()), -35, round(self.cc_y.mean()), 0)
                        elif supply_depot_count == 1:
                            target = self.transformDistance(round(self.cc_x.mean()), -25, round(self.cc_y.mean()), -25)
                        elif supply_depot_count == 2:
                            target = self.transformDistance(round(self.cc_x.mean()), -15, round(self.cc_y.mean()), 20)
                        elif supply_depot_count == 3:
                            target = self.transformDistance(round(self.cc_x.mean()), -15, round(self.cc_y.mean()), 25)
                        elif supply_depot_count == 4:
                            target = self.transformDistance(round(self.cc_x.mean()), -10, round(self.cc_y.mean()), 25)
                        elif supply_depot_count == 5:
                            target = self.transformDistance(round(self.cc_x.mean()), -10, round(self.cc_y.mean()), 20)
                        elif supply_depot_count == 6:
                            target = self.transformDistance(round(self.cc_x.mean()), 0, round(self.cc_y.mean()), 20)
                        elif supply_depot_count == 7:
                            target = self.transformDistance(round(self.cc_x.mean()), 0, round(self.cc_y.mean()), 25)
                        elif supply_depot_count == 8:
                            target = self.transformDistance(round(self.cc_x.mean()), 5, round(self.cc_y.mean()), 25)
                        elif supply_depot_count == 9:
                            target = self.transformDistance(round(self.cc_x.mean()), 10, round(self.cc_y.mean()), 20)

                        return actions.FunctionCall(_BUILD_SUPPLY_DEPOT, [_NOT_QUEUED, target])

            #Build Barracks limit 3
            elif smart_action == ACTION_BUILD_BARRACKS:
                if barracks_count < 3 and _BUILD_BARRACKS in obs.observation['available_actions']:
                    if self.cc_y.any():
                        if  barracks_count == 0:
                            target = self.transformDistance(round(self.cc_x.mean()), 15, round(self.cc_y.mean()), -9)
                        elif  barracks_count == 1:
                            target = self.transformDistance(round(self.cc_x.mean()), 15, round(self.cc_y.mean()), 12)
                        elif  barracks_count == 2:
                            target = self.transformDistance(round(self.cc_x.mean()), 15, round(self.cc_y.mean()), 18)
                        return actions.FunctionCall(_BUILD_BARRACKS, [_NOT_QUEUED, target])

            #Build Marine
            elif smart_action == ACTION_BUILD_MARINE:
                if _TRAIN_MARINE in obs.observation['available_actions']:
                    return actions.FunctionCall(_TRAIN_MARINE, [_QUEUED])

            #Attack
            elif smart_action == ACTION_ATTACK:
                do_it = True

                if len(obs.observation['single_select']) > 0 and obs.observation['single_select'][0][0] == _TERRAN_SCV:
                    do_it = False

                if len(obs.observation['multi_select']) > 0 and obs.observation['multi_select'][0][0] == _TERRAN_SCV:
                    do_it = False

                if do_it and _ATTACK_MINIMAP in obs.observation["available_actions"]:
                    x_offset = random.randint(-1, 1)
                    y_offset = random.randint(-1, 1)

                    return actions.FunctionCall(_ATTACK_MINIMAP, [_NOT_QUEUED, self.transformLocation(int(x) + (x_offset * 8), int(y) + (y_offset * 8))])

#MOVE 2 -------------------------------------------------

        elif self.move_number == 2:
            self.move_number = 0

            smart_action, x, y = self.splitAction(self.previous_action)

            #Mine Minerals
            if smart_action == ACTION_BUILD_BARRACKS or smart_action == ACTION_BUILD_SUPPLY_DEPOT:
                if _HARVEST_GATHER in obs.observation['available_actions']:
                    unit_y, unit_x = (unit_type == _NEUTRAL_MINERAL_FIELD).nonzero()

                    if unit_y.any():
                        i = random.randint(0, len(unit_y) - 1)

                        m_x = unit_x[i]
                        m_y = unit_y[i]

                        target = [int(m_x), int(m_y)]

                        return actions.FunctionCall(_HARVEST_GATHER, [_QUEUED, target])

#MOVE 3, removed to integrate with dev api ------------------------------------------------

        # elif self.move_number == 3:
        #     self.move_number = 0
        #
        #     if mining_vespene_ct < 3:
        #         smart_action, x, y = self.splitAction(self.previous_action)
        #
        #         #Mine Vespene Gas
        #         unit_y, unit_x = (unit_type == _TERRAN_REFINERY).nonzero()
        #
        #         if unit_y.any():
        #             i = random.randint(0, len(unit_y) - 1)
        #
        #             m_x = unit_x[i]
        #             m_y = unit_y[i]
        #
        #             target = [int(m_x), int(m_y)]
        #
        #             mining_vespene_ct += 1
        #
        #             return actions.FunctionCall(_SMART_SELECT, [_QUEUED, target])

#MOVE NoAction -------------------------------------------------
        #Do Nothing
        return actions.FunctionCall(_NO_OP, [])
