
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

# Dictionary of the different parameters to optimize with their respective ranges
# Keys MUST match exactly the self.params.get('key') calls in MioAgente.py
dict_parameters = {
    # Resource weights — multiplied by probability dots (0-6) for up to 3 terrains per node
    # Max raw contribution per resource: 6 * 10 = 60 per terrain
    "weight_wood":                  (0, 10),
    "weight_clay":                  (0, 10),
    "weight_cereal":                (0, 10),
    "weight_mineral":               (0, 10),
    "weight_wool":                  (0, 10),
    # Flat bonus added to node score when a harbor is present
    # Should be on the same scale as resource scores (a good node ≈ 30-80) → 0-20
    "start_harbor_bonus":           (0, 20),
    # Road strategy: future node score is 30-80 → weight in (0, 1) to avoid overriding resource logic
    "road_strategy_future_node":    (0, 1),
    # Flat bonus for a road leading toward a harbor node — same scale as path scores (~10-50)
    "weight_harbor":                (0, 20),
    # Center control: connections (2-3) * w → keep small relative to other path scores
    "road_strategy_center_control": (0, 5),
    # Build strategy priorities — relative weights, same scale is fine
    "city_weight":                  (0, 10),
    "town_weight":                  (0, 10),
    # Probability threshold for robber anxiety — MUST stay in [0, 1]
    "weight_robber_anxiety":        (0, 1),
    # Road building card scoring multipliers
    # weight_material_diversity * 2.5 per new resource type found
    "weight_material_diversity":    (0, 4),
    # weight_block_opponent * 3.5 per opponent node
    "weight_block_opponent":        (0, 4),
    # weight_road_expansion * len(adjacent) ≈ * 3
    "weight_road_expansion":        (0, 4),
}
IND_SIZE = len(dict_parameters)
N_games_per_evaluation =  20 # Number of games to simulate for each evaluation

def _get_last_vp(trace):
    """Retourne le dict victory_points du dernier tour de la trace."""
    last_round = max(trace['game'].keys(), key=lambda r: int(r.split('_')[-1]))
    last_turn = max(trace['game'][last_round].keys(), key=lambda t: int(t.split('_')[-1].lstrip('P')))
    return trace['game'][last_round][last_turn]['end_turn']['victory_points']


def find_winner(trace):
    """Retourne l'identifiant du joueur gagnant ('J0', 'J1', ...) depuis une trace JSON."""
    vp = _get_last_vp(trace)
    return max(vp, key=lambda player: int(vp[player]))


def get_final_vp(trace, player='J0'):
    """Retourne les points de victoire finaux du joueur donné depuis une trace JSON."""
    vp = _get_last_vp(trace)
    return int(vp.get(player, 0))


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
    total_vp = 0
    n_games = N_games_per_evaluation
    params = dict(zip(dict_parameters.keys(), individual))

    # Seed de base propre à cet individu pour diversifier les parties entre individus
    base_seed = hash(tuple(round(x, 6) for x in individual)) & 0xFFFFFF
    import time
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
            total_vp += get_final_vp(data, player='J0')
            if find_winner(data) == 'J0':
                victories += 1
            del data
        except Exception as e:
            print(f"Error reading game trace: {e}", file=sys.stderr)

        # Supprime le répertoire de traces immédiatement après lecture
        shutil.rmtree(trace_path, ignore_errors=True)

        # Libère explicitement les objets pour éviter les fuites mémoire
       # del game_director, agent, players, opponents
    # gc.collect()

    # Fitness = moyenne des VP normalisés sur 10 (moins bruité que le taux de victoire binaire)
    # σ VP ≈ 2 → σ fitness ≈ 2/(10*√n) ≈ 0.037 pour n=30, contre 0.09 pour win/loss
    return (total_vp / (n_games * 10),)

# DEAP toolbox initialization
toolbox = base.Toolbox()
toolbox.register("individual", tools.initIterate, creator.Individual, generate_individual)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)
toolbox.register("evaluate", evaluate_agent)
toolbox.register("mate", tools.cxBlend, alpha=0.5)  # Croisement blend
# Mutation: adds Gaussian noise to each gene
toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=0.5, indpb=0.2)
toolbox.register("select", tools.selTournament, tournsize=2)

# Genetic algorithm parameters
POP_SIZE = 30   # Population size
N_GEN = 50       # Number of generations
CXPB = 0.6         # Crossover probability
MUTPB = 0.2        # Mutation probability
N_games_per_evaluation = 30  # Number of games to simulate for each evaluation


if __name__ == "__main__":

    # Parallélise les évaluations sur les cœurs disponibles (50% pour ne pas saturer la RAM)
    porcentaje_workers = 0.8
    workers = max(1, int((os.cpu_count() or 1) * porcentaje_workers))
    pool = multiprocessing.Pool(processes=workers, maxtasksperchild=5)
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

    import time
    try:
        import psutil
        psutil_available = True
    except ImportError:
        psutil_available = False
        print("psutil non installé : la mémoire et les processus ne seront pas affichés.")

    # Manual loop for GA to print stats each generation
    for gen in range(N_GEN):
        start_time = time.time()
        offspring = algorithms.varAnd(population, toolbox, cxpb=CXPB, mutpb=MUTPB)
        # Clamp each parameter to its bounds after mutation
        for ind in offspring:
            for i, (min_val, max_val) in enumerate(dict_parameters.values()):
                ind[i] = max(min(ind[i], max_val), min_val)
        fits = toolbox.map(toolbox.evaluate, offspring)
        for ind, fit in zip(offspring, fits):
            ind.fitness.values = fit
        population = toolbox.select(offspring, k=len(population))
        # Élitisme : réinjecte le meilleur individu de tous les temps dans la population
        if len(hall_of_fame) > 0:
            population[0] = toolbox.clone(hall_of_fame[0])
        hall_of_fame.update(population)
        record = stats.compile(population)
        end_time = time.time()
        elapsed = end_time - start_time
        speed = elapsed / len(offspring) if len(offspring) > 0 else 0
        mem_str = ""
        proc_str = ""
        if psutil_available:
            process = psutil.Process(os.getpid())
            mem_mb = process.memory_info().rss / 1024 / 1024
            mem_str = f" | RAM: {mem_mb:.2f} MB"
            # Compte les processus Python actifs
            python_procs = [p for p in psutil.process_iter(['name']) if p.info['name'] and 'python' in p.info['name'].lower()]
            proc_str = f" | Python procs: {len(python_procs)}"
        print(f"Génération {gen+1}: avg={record['avg']:.2f}, max={record['max']}, min={record['min']} | Temps: {elapsed:.2f}s | Vitesse: {speed:.2f}s/individu{mem_str}{proc_str}")

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
