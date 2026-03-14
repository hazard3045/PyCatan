
# Add project root for module imports.
import sys
import os
import multiprocessing
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import random
from deap import base, creator, tools, algorithms
from Agents.MioAgente import MioAgente

# Simulation and game management imports.
from Managers.GameDirector import GameDirector
from Agents.AlexPelochoJaimeAgent import AlexPelochoJaimeAgent as a1
from Agents.CarlesZaidaAgent import CarlesZaidaAgent as a2
from Agents.CrabisaAgent import CrabisaAgent as a3
from Agents.EdoAgent import EdoAgent as a4
from Agents.PabloAleixAlexAgent import PabloAleixAlexAgent as a5
from Agents.RandomAgent import RandomAgent as a6
from Agents.SigmaAgent import SigmaAgent as a7
from Agents.TristanAgent import TristanAgent as a8
 

# Guard against re-creation when workers import this module (multiprocessing on Windows).
if not hasattr(creator, 'FitnessMax'):
    creator.create("FitnessMax", base.Fitness, weights=(1.0,))
if not hasattr(creator, 'Individual'):
    creator.create("Individual", list, fitness=creator.FitnessMax)

# Parameter search space.
dict_parameters = {
    "weight_wood":                  (0, 10),
    "weight_clay":                  (0, 10),
    "weight_cereal":                (0, 10),
    "weight_mineral":               (0, 10),
    "weight_wool":                  (0, 10),
    "start_harbor_bonus":           (0, 20),
    "road_strategy_future_node":    (0, 3),
    "weight_harbor":                (0, 20),
    "road_strategy_center_control": (0, 5),
    "city_weight":                  (0, 1),
    "town_weight":                  (0, 1),
    "weight_robber_anxiety":        (0, 1),
    "weight_material_diversity":    (0, 4),
    "weight_block_opponent":        (0, 4),
    "weight_road_expansion":        (0, 4),
    "weight_dev_card_urgency":       (0, 1),
    "weight_victory_near_threshold": (0, 10),
    "army_weight":                   (0, 1),
}
IND_SIZE = len(dict_parameters)

# Genetic algorithm settings.
N_games_per_evaluation = 50  # Number of games to simulate for each evaluation
POP_SIZE = 60   # Population size
N_GEN = 30       # Number of generations
CXPB = 0.7         # Crossover probability
MUTPB = 0.3        # Mutation probability
RATE = 0.1         # Mutation strength 
WEIGHT_VP = 1.0      # Weight for victory points in fitness
WEIGHT_WIN = 5.0     # Additional weight for winning 
porcentaje_workers = 0.85


# Fixed game configurations per generation for fair comparisons.
import itertools as _itertools
_ALL_OPP_COMBOS = list(_itertools.combinations(range(8), 3)) 
FIXED_GAME_CONFIGS = [
    (i % 4, _ALL_OPP_COMBOS[i % len(_ALL_OPP_COMBOS)])
    for i in range(N_games_per_evaluation)
]

def _get_last_vp(trace):
    """Return the victory_points dictionary from the last turn in the trace."""
    last_round = max(trace['game'].keys(), key=lambda r: int(r.split('_')[-1]))
    last_turn = max(trace['game'][last_round].keys(), key=lambda t: int(t.split('_')[-1].lstrip('P')))
    return trace['game'][last_round][last_turn]['end_turn']['victory_points']


def make_mioagente_class(params):
    """
    Create a MioAgente subclass with fixed params for AgentManager.
    This allows the GameDirector to instantiate agents with the same parameters without
    needing to pass them explicitly each time as we encounter a problem this way.
    """
    class _ParametrizedMioAgente(MioAgente):
        def __init__(self, agent_id):
            super().__init__(agent_id, params=params)
    return _ParametrizedMioAgente

def find_winner(trace):
    """Return the winner player ID ('J0', 'J1', ...) from a JSON trace."""
    vp = _get_last_vp(trace)
    return max(vp, key=lambda player: int(vp[player]))


def get_final_vp(trace, player='J0'):
    """Return final victory points for a given player from a JSON trace."""
    vp = _get_last_vp(trace)
    return int(vp.get(player, 0))

def mutate_scaled(individual, indpb, rate = 0.1):
    """Mutate each gene with strength proportional to its value range."""
    for i, (min_val, max_val) in enumerate(dict_parameters.values()):
        if random.random() < indpb:
            sigma = (max_val - min_val) * rate
            individual[i] += random.gauss(0, sigma)
            individual[i] = max(min(individual[i], max_val), min_val)
    return individual,

def generate_individual():
    """
    Generate a random individual based on the defined parameters and their ranges.
    Returns:
        list: An individual represented as a list of parameter values.
    """
    return [random.uniform(min_val, max_val) for min_val, max_val in dict_parameters.values()]

def evaluate_agent(args):
    """
    Evaluates the agent over FIXED_GAME_CONFIGS (rotating positions, diverse opponents).
    Games are genuinely random (no fixed seed) so the board layout, dice rolls, and
    card draws vary — this ensures the agent's params actually influence outcomes.
    With 50 games the average VP is a reliable signal of true performance.
    """
    individual, gen = args
    import json
    import shutil
    opponents_classes = [a1, a2, a3, a4, a5, a6, a7, a8]
    params = dict(zip(dict_parameters.keys(), individual))
    total_vp = 0
    victories = 0

    for i, (position, opp_indices) in enumerate(FIXED_GAME_CONFIGS):
        random.seed((gen * 1000) + i)

        opp_ids = [j for j in range(4) if j != position]
        MioAgenteClass = make_mioagente_class(params)

        agents_classes = [None] * 4
        agents_classes[position] = MioAgenteClass
        for k, opp_idx in enumerate(opp_indices):
            agents_classes[opp_ids[k]] = opponents_classes[opp_idx]

        game_director = GameDirector(agents=agents_classes, max_rounds=200)
        trace_path = game_director.trace_loader.full_path
        game_director.game_start(i, print_outcome=False)

        agent_id = f"J{position}"
        try:
            game_file = trace_path / f'game_{i}.json'
            with open(game_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            total_vp += get_final_vp(data, player=agent_id)

            if find_winner(data) == agent_id:
                victories += 1

            del data
        except Exception as e:
            print(f"Error reading game trace: {e}", file=sys.stderr)

        shutil.rmtree(trace_path, ignore_errors=True)

    avg_vp = total_vp / N_games_per_evaluation
    win_rate = victories / N_games_per_evaluation

    fitness_score = avg_vp * WEIGHT_VP + win_rate * 10 * WEIGHT_WIN
    return (fitness_score,)



# DEAP toolbox setup.
toolbox = base.Toolbox()
toolbox.register("individual", tools.initIterate, creator.Individual, generate_individual)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)
toolbox.register("evaluate", evaluate_agent)
toolbox.register("mate", tools.cxBlend, alpha=0.3)
toolbox.register("mutate", mutate_scaled, indpb=0.2 , rate = RATE)
toolbox.register("select", tools.selTournament, tournsize=3)




if __name__ == "__main__":

    # Parallelize evaluations across available CPU cores.
    workers = max(1, int((os.cpu_count() or 1) * porcentaje_workers))
    pool = multiprocessing.Pool(processes=workers, maxtasksperchild=2)
    toolbox.register("map", pool.map)
    

    population = toolbox.population(n=POP_SIZE)

    fits = pool.map(evaluate_agent, [(ind, -1) for ind in population])
    for ind, fit in zip(population, fits):
        ind.fitness.values = fit

    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", lambda x: sum(v[0] for v in x) / len(x))
    stats.register("max", lambda x: max(v[0] for v in x))
    stats.register("min", lambda x: min(v[0] for v in x))

    hall_of_fame = tools.HallOfFame(1)

    import time
    gen_times = []
    try:
        import psutil
        psutil_available = True
    except ImportError:
        psutil_available = False

    for gen in range(N_GEN):
        start_time = time.time()
        
        # Keep top individuals unchanged.
        elites = tools.selBest(population, 2)
        clones_elites = list(map(toolbox.clone, elites))
        
        # Select parents for the rest of the population.
        parents = toolbox.select(population, len(population) - 2)
        offspring = list(map(toolbox.clone, parents))
        
        offspring = algorithms.varAnd(offspring, toolbox, cxpb=CXPB, mutpb=MUTPB)
        
        # Clamp values to valid parameter ranges after crossover/mutation.
        for ind in offspring:
            for i, (min_val, max_val) in enumerate(dict_parameters.values()):
                ind[i] = max(min(ind[i], max_val), min_val)
                
        # Reinsert elites.
        offspring.extend(clones_elites)
        
        # Re-evaluate all individuals, including elites.
        fits = pool.map(evaluate_agent, [(ind, gen) for ind in offspring])
        for ind, fit in zip(offspring, fits):
            ind.fitness.values = fit
            
        # Replace current population.
        population[:] = offspring
        
        # Update stats.
        hall_of_fame.update(population)
        record = stats.compile(population)
        
        end_time = time.time()
        elapsed = end_time - start_time
        speed = elapsed / len(offspring) if len(offspring) > 0 else 0
        gen_times.append(elapsed)

        gens_remaining = N_GEN - (gen + 1)
        avg_gen_time = sum(gen_times) / len(gen_times)
        eta_seconds = avg_gen_time * gens_remaining
        eta_h = int(eta_seconds // 3600)
        eta_m = int((eta_seconds % 3600) // 60)
        eta_s = int(eta_seconds % 60)
        eta_str = f"{eta_h:02d}:{eta_m:02d}:{eta_s:02d}"

        # Save current best individual.
        with open("current_best_agent.txt", "w") as f:
            f.write(str(hall_of_fame[0]))

        print(f"Generation {gen+1}/{N_GEN}: avg={record['avg']:.2f}, max={record['max']}, min={record['min']} | {elapsed:.1f}s ({speed:.2f}s/ind) | ETA: {eta_str}")

    print("\nBest individual found:", hall_of_fame[0])
    print("Fitness:", hall_of_fame[0].fitness.values[0])

    pool.close()
    pool.join()

    # Save final best individual.
    with open("best_agent.txt", "w") as f:
        f.write(str(hall_of_fame[0]))
