#!/usr/bin/env python
'''
Code for running RL + solar tracking experiments.

Author: Emily Reif + David Abel
'''

# Python imports.
import datetime

# simple_rl imports.
from simple_rl.run_experiments import run_agents_on_mdp
from simple_rl.agents import RandomAgent, FixedPolicyAgent, LinearApproxQLearnerAgent, LinearApproxSarsaAgent, LinUCBAgent

# Local imports.
from solarOOMDP.SolarOOMDPClass import SolarOOMDP
from solarOOMDP.PanelClass import Panel
from SolarTrackerClass import SolarTracker
import tracking_baselines as tb

def _make_mdp(loc, percept_type, panel_step, reflective_index=0.5):
    '''
    Args:
        loc (str)
        percept_type (str): One of 'sun_percept', 'image_percept', or 'image_cloud_percept'.
        panel_step (int)

    Returns:
        (solarOOMDP)
    '''
    #panel information
    #TODO: check actuator force - how does it scale with panel mass?
    panel = Panel(1, 1, 10, 0.22, 1500, 0.10, 0.5, 0.1, 0.5)
    
    # Percepts.
    try:
        image_mode, cloud_mode, = {
            "sun_percept":(False, False),
            "image_percept":(True, False),
            "image_cloud_percept":(True, True),
        }[percept_type]
    except KeyError:
        print "Error: percept type unknown ('" + str(percept_type) + "''). Choose one of: ['sun_percept', 'image_percept', 'image_cloud_percept']."
        quit()

    # Location.
    if loc == "australia":
        date_time = datetime.datetime(day=1, hour=1, month=1, year=2015)
        lat, lon = -34.25, 142.17
    elif loc == "iceland":
        date_time = datetime.datetime(day=3, hour=16, month=7, year=2020)
        lat, lon = 64.1265, -21.8174
    elif loc == "nyc":
        date_time = datetime.datetime(day=1, hour=1, month=2, year=2015)
        lat, lon = 40.7, 74.006

    # Make MDP.
    solar_mdp = SolarOOMDP(date_time=date_time, \
        panel=panel, \
        timestep=10.0, \
        latitude_deg=lat, \
        longitude_deg=lon, \
        panel_step=panel_step, \
        image_mode=image_mode, \
        cloud_mode=cloud_mode, \
        reflective_index=reflective_index)

    return solar_mdp

def _setup_agents(solar_mdp, test_both_axes=False, reflective_index_exp=False):
    '''
    Args:
        solar_mdp (SolarOOMDP)
        reflective_index_exp (bool): If true renames agents according to the reflective_index of the solar_mdp

    Returns:
        (list): of Agents
    '''
    # Get relevant MDP params.
    actions, gamma, panel_step = solar_mdp.get_actions(), solar_mdp.get_gamma(), solar_mdp.get_panel_step()
    saxis_actions = solar_mdp.get_single_axis_actions()

    # Setup fixed agent.
    static_agent = FixedPolicyAgent(tb.static_policy, name="fixed-panel")
    optimal_agent = FixedPolicyAgent(tb.optimal_policy, name="optimal")

    # Grena single axis and double axis trackers from time/loc.
    grena_tracker_s = SolarTracker(tb.grena_tracker, panel_step=panel_step, dual_axis=False)
    grena_tracker_s_agent = FixedPolicyAgent(grena_tracker_s.get_policy(), name="grena-tracker-single")
    grena_tracker_d = SolarTracker(tb.grena_tracker, panel_step=panel_step, dual_axis=True)
    grena_tracker_d_agent = FixedPolicyAgent(grena_tracker_d.get_policy(), name="grena-tracker")

    # Setup RL agents
    alpha, epsilon = 0.6, 0.6
    lin_ucb_agent_s = LinUCBAgent(saxis_actions, name="lin-ucb-single")
    lin_ucb_agent_d = LinUCBAgent(actions, name="lin-ucb") #, alpha=0.2) #, alpha=0.2)
    ql_lin_approx_agent_s = LinearApproxQLearnerAgent(saxis_actions, name="ql-lin-single-$\gamma=0$", alpha=alpha, epsilon=epsilon, gamma=gamma, rbf=True)
    ql_lin_approx_agent_d = LinearApproxQLearnerAgent(actions, name="ql-lin-g0", alpha=alpha, epsilon=epsilon, gamma=0, rbf=True, anneal=True)
    sarsa_lin_rbf_agent_s = LinearApproxSarsaAgent(saxis_actions, name="sarsa-lin-single", alpha=alpha, epsilon=epsilon, gamma=gamma, rbf=True)
    sarsa_lin_rbf_agent_d = LinearApproxSarsaAgent(actions, name="sarsa-lin", alpha=alpha, epsilon=epsilon, gamma=gamma, rbf=True, anneal=True)

    if test_both_axes:
        # Axis comparison experiment.
        grena_tracker_d_agent.name += "-double"
        lin_ucb_agent_d.name += "-double"
        sarsa_lin_rbf_agent_d.name += "-double"
        ql_lin_approx_agent_d.name += "-double"
        agents = [grena_tracker_s_agent, grena_tracker_d_agent, lin_ucb_agent_s, lin_ucb_agent_d, sarsa_lin_rbf_agent_s, sarsa_lin_rbf_agent_d, ql_lin_approx_agent_s, ql_lin_approx_agent_d]
    elif reflective_index_exp:
        # Reflective index experiment.
        grena_tracker_d_agent.name += "-" + str(solar_mdp.get_reflective_index())
        sarsa_lin_rbf_agent_d.name += "-" + str(solar_mdp.get_reflective_index())
        agents = [grena_tracker_d_agent, sarsa_lin_rbf_agent_d]
    else:
        # Regular experiments.
        agents = [sarsa_lin_rbf_agent_d, ql_lin_approx_agent_d, lin_ucb_agent_d]
        fixed_agents = [grena_tracker_d_agent, static_agent]
        agents = agents + fixed_agents

    return agents


def setup_experiment(percept_type, loc="australia", test_both_axes=False, reflective_index=None):
    '''
    Args:
        percept_type (str): One of 'sun_percept', 'image_percept', or 'image_cloud_percept'.
        loc (str): one of ['australia', 'iceland', 'nyc']
        test_both_axes (bool)
        reflective_index_exp (float): If true, runs the reflective index experiment.

    Returns:
        (tuple):
            [1]: (list of Agents)
            [2]: MDP
    '''

    # Setup MDP.
    solar_mdps = []
    if reflective_index is not None:
        solar_mdp = _make_mdp(loc, percept_type, panel_step=2.0, reflective_index=reflective_index)
    else:
        solar_mdp = _make_mdp(loc, percept_type, panel_step=2.0)

    agents = _setup_agents(solar_mdp, test_both_axes=test_both_axes, reflective_index_exp=reflective_index is not None)
    
    return agents, solar_mdp

def main():

    # Setup experiment parameters, agents, mdp.
    loc, steps = "nyc", 6*24
    sun_agents, sun_solar_mdp = setup_experiment("sun_percept", loc=loc)

    # # Run experiments.
    run_agents_on_mdp(sun_agents, sun_solar_mdp, instances=10, episodes=1, steps=steps, clear_old_results=True)

    
if __name__ == "__main__":
    main()
