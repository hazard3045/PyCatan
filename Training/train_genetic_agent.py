
"""
train_genetic_agent.py

This script allows you to train an agent for the game Catan using a genetic algorithm with the DEAP library.

- The agent is represented by a set of parameters (chromosome).
- The genetic algorithm optimizes these parameters to maximize the agent's performance.
- The script is heavily commented for clarity.

Requirements:
- Install the DEAP library: pip install deap
- Adapt the evaluation function to your environment (game simulation, scoring, etc.)
"""

# Add project root to sys.path for module imports
import sys
import os
import multiprocessing
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import random
from deap import base, creator, tools, algorithms
from Agents.MioAgente import MioAgente
import sys

# Import for simulation and game management
from Managers.GameDirector import GameDirector
from Opponents.AlexPelochoJaimeAgent import AlexPelochoJaimeAgent as a1
from Opponents.CarlesZaidaAgent import CarlesZaidaAgent as a2
from Opponents.CrabisaAgent import CrabisaAgent as a3
from Opponents.EdoAgent import EdoAgent as a4
from Opponents.PabloAleixAlexAgent import PabloAleixAlexAgent as a5
from Opponents.RandomAgent import RandomAgent as a6
from Opponents.SigmaAgent import SigmaAgent as a7
from Opponents.TristanAgent import TristanAgent as a8
 

# Define the problem: maximize the agent's performance
# Guard against re-creation when workers import this module (multiprocessing on Windows)
if not hasattr(creator, 'FitnessMax'):
    creator.create("FitnessMax", base.Fitness, weights=(1.0,))
if not hasattr(creator, 'Individual'):
    creator.create("Individual", list, fitness=creator.FitnessMax)

# Dictionary of the different parameters to optimize with their respective ranges (0, 1)
dict_parameters = {
    "sum_probability_weight": (0, 10),
    "new_resources_weight": (0, 10),
    "distance_weight": (0, 10),
    "harbor_weight": (0, 10),
    "street_weight": (0, 10),
    "colony_weight": (0, 10),
    "city_weight": (0, 10),
    "lumber_a": (0, 10),
    "brick_a": (0, 10),
    "wool_a": (0, 10),
    "grain_a": (0, 10),
    "ore_a": (0, 10),
    "lumber_b": (0, 10),
    "brick_b": (0, 10),
    "wool_b": (0, 10),
    "grain_b": (0, 10),
    "ore_b": (0, 10),
    "ratio_resources_weight": (0, 10),
    "need_for_resources_weight": (0, 10),
    "position_player_weight": (0, 10),
    "number_of_cards_weight": (0, 10),
    "need_resources_stolen_weight": (0, 10),
    "steal_from_player_weight": (0, 10),
    "defense_weight": (0, 10),
    "need_for_roads_weight": (0, 10)
}
IND_SIZE = len(dict_parameters)

def find_winner(trace):
    """Retourne l'identifiant du joueur gagnant ('J0', 'J1', ...) depuis une trace JSON."""
    for round_key in sorted([k for k in trace['game'].keys() if k.startswith('round_')]):
        round_data = trace['game'][round_key]
        for turn_key in ['turn_P0', 'turn_P1', 'turn_P2', 'turn_P3']:
            if turn_key in round_data and 'end_turn' in round_data[turn_key]:
                vp = round_data[turn_key]['end_turn'].get('victory_points', {})
                for player_id, points in vp.items():
                    if int(points) >= 10:
                        return player_id
    return None


# Function to generate a random individual
def generate_individual():
    """
    Generate a random individual based on the defined parameters and their ranges.
    Returns:
        list: An individual represented as a list of parameter values.
    """
    return [random.uniform(min_val, max_val) for min_val, max_val in dict_parameters.values()]

# Agent evaluation function
def evaluate_agent(individual):
    """
    Evaluates the agent's performance.
    Replace this function with a real game simulation or scoring.
    Here, a dummy function is used for the example.
    """
    import json
    import shutil
    import gc
    opponents_classes = [a1, a2, a3, a4, a5, a6, a7, a8]
    victories = 0
    n_games = N_games_per_evaluation
    params = dict(zip(dict_parameters.keys(), individual))

    # Seed de base propre à cet individu pour diversifier les parties entre individus
    base_seed = hash(tuple(round(x, 6) for x in individual)) & 0xFFFFFF
    for i in range(n_games):
        random.seed(base_seed + i)
        # Crée un agent neuf à chaque partie pour éviter l'accumulation d'état
        agent = MioAgente(agent_id=0, params=params)
        chosen_opponents = random.sample(opponents_classes, 3)
        opponents = [cls(j+1) for j, cls in enumerate(chosen_opponents)]
        players = [agent] + opponents

        game_director = GameDirector(players, max_rounds=200)
        # Chemin exact du répertoire de traces propre à ce GameDirector
        # (safe en parallèle : chaque instance crée son propre dossier horodaté)
        trace_path = game_director.trace_loader.full_path
        game_director.game_start(i, print_outcome=False)

        # Lecture du fichier JSON via le chemin connu — aucun scan de dossier
        try:
            game_file = trace_path / f'game_{i}.json'
            with open(game_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if find_winner(data) == 'J0':
                victories += 1
            del data
        except Exception as e:
            print(f"Error reading game trace: {e}", file=sys.stderr)

        # Supprime le répertoire de traces immédiatement après lecture
        shutil.rmtree(trace_path, ignore_errors=True)

        # Libère explicitement les objets pour éviter les fuites mémoire
        del game_director, agent, players, opponents
        gc.collect()

    return (victories,)

# DEAP toolbox initialization
toolbox = base.Toolbox()
toolbox.register("individual", tools.initIterate, creator.Individual, generate_individual)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)
toolbox.register("evaluate", evaluate_agent)
toolbox.register("mate", tools.cxBlend, alpha=0.5)  # Croisement blend
# Mutation: adds Gaussian noise to each gene
toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=1.0, indpb=0.2)
toolbox.register("select", tools.selTournament, tournsize=3)

# Genetic algorithm parameters
POP_SIZE = 50      # Population size
N_GEN = 20        # Number of generations
CXPB = 0.5         # Crossover probability
MUTPB = 0.2        # Mutation probability
N_games_per_evaluation = 20  # Number of games to simulate for each evaluation

if __name__ == "__main__":
    # Parallélise les évaluations sur les cœurs disponibles (50% pour ne pas saturer la RAM)
    porcentaje_workers = 0.5
    workers = max(1, int((os.cpu_count() or 1) * porcentaje_workers))
    pool = multiprocessing.Pool(processes=workers)
    toolbox.register("map", pool.map)

    # Create the initial population
    population = toolbox.population(n=POP_SIZE)

    # Evaluate the initial population before the first generation
    fits = toolbox.map(toolbox.evaluate, population)
    for ind, fit in zip(population, fits):
        ind.fitness.values = fit

    # Statistics to track evolution
    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", lambda x: sum(v[0] for v in x) / len(x))
    stats.register("max", lambda x: max(v[0] for v in x))
    stats.register("min", lambda x: min(v[0] for v in x))

    # Record the best individuals
    hall_of_fame = tools.HallOfFame(1)

    # Manual loop for GA to print stats each generation
    for gen in range(N_GEN):
        offspring = algorithms.varAnd(population, toolbox, cxpb=CXPB, mutpb=MUTPB)
        # Clamp each parameter to its bounds after mutation
        for ind in offspring:
            for i, (min_val, max_val) in enumerate(dict_parameters.values()):
                ind[i] = max(min(ind[i], max_val), min_val)
        fits = toolbox.map(toolbox.evaluate, offspring)
        for ind, fit in zip(offspring, fits):
            ind.fitness.values = fit
        population = toolbox.select(offspring, k=len(population))
        hall_of_fame.update(population)
        record = stats.compile(population)
        print(f"Génération {gen+1}: avg={record['avg']:.2f}, max={record['max']}, min={record['min']}")

    # Display the results
    print("\nBest individual found:", hall_of_fame[0])
    print("Fitness:", hall_of_fame[0].fitness.values[0])

    pool.close()
    pool.join()

    # Save the best agent (example)
    with open("best_agent.txt", "w") as f:
        f.write(str(hall_of_fame[0]))

    # Tips:
    # - Adapt the evaluate_agent function to simulate a real game.
    # - Use the optimized parameters to configure your Catan agent.
    # - Explore other genetic operators as needed.
