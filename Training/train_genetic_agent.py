
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
from Agents.AlexPelochoJaimeAgent import AlexPelochoJaimeAgent as a1
from Agents.CarlesZaidaAgent import CarlesZaidaAgent as a2
from Agents.CrabisaAgent import CrabisaAgent as a3
from Agents.EdoAgent import EdoAgent as a4
from Agents.PabloAleixAlexAgent import PabloAleixAlexAgent as a5
from Agents.RandomAgent import RandomAgent as a6
from Agents.SigmaAgent import SigmaAgent as a7
from Agents.TristanAgent import TristanAgent as a8
 

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
    "road_strategy_future_node":    (0, 3),
    # Flat bonus for a road leading toward a harbor node — same scale as path scores (~10-50)
    "weight_harbor":                (0, 20),
    # Center control: connections (2-3) * w → keep small relative to other path scores
    "road_strategy_center_control": (0, 5),
    # Build strategy priorities — used both as multipliers AND probability thresholds
    # (random.random() < w_city), so MUST stay in [0, 1]
    "city_weight":                  (0, 1),
    "town_weight":                  (0, 1),
    # Probability threshold for robber anxiety — MUST stay in [0, 1]
    "weight_robber_anxiety":        (0, 1),
    # Road building card scoring multipliers
    # weight_material_diversity * 2.5 per new resource type found
    "weight_material_diversity":    (0, 4),
    # weight_block_opponent * 3.5 per opponent node
    "weight_block_opponent":        (0, 4),
    # weight_road_expansion * len(adjacent) ≈ * 3
    "weight_road_expansion":        (0, 4),
    "weight_dev_card_urgency":       (0, 1),
    "weight_victory_near_threshold": (0, 10),
    "army_weight":                   (0, 1),
}
IND_SIZE = len(dict_parameters)

# Genetic algorithm parameters
N_games_per_evaluation = 50  # Number of games to simulate for each evaluation
POP_SIZE = 60   # Population size
N_GEN = 50       # Number of generations
CXPB = 0.7         # Crossover probability
MUTPB = 0.3        # Mutation probability
RATE = 0.1         # Mutation strength 
WEIGHT_VP = 1.0      # Weight for victory points in fitness
WEIGHT_WIN = 5.0     # Additional weight for winning (adjust as needed)

# Game configurations: rotating positions + diverse opponent combos.

import itertools as _itertools
_ALL_OPP_COMBOS = list(_itertools.combinations(range(8), 3))  # 56 combos C(8,3)
FIXED_GAME_CONFIGS = [
    (i % 4, _ALL_OPP_COMBOS[i % len(_ALL_OPP_COMBOS)])
    for i in range(N_games_per_evaluation)
]

def _get_last_vp(trace):
    """Retourne le dict victory_points du dernier tour de la trace."""
    last_round = max(trace['game'].keys(), key=lambda r: int(r.split('_')[-1]))
    last_turn = max(trace['game'][last_round].keys(), key=lambda t: int(t.split('_')[-1].lstrip('P')))
    return trace['game'][last_round][last_turn]['end_turn']['victory_points']


def make_mioagente_class(params):
    """Returns a MioAgente subclass with params baked in, usable as a plain class by AgentManager."""
    class _ParametrizedMioAgente(MioAgente):
        def __init__(self, agent_id):
            super().__init__(agent_id, params=params)
    return _ParametrizedMioAgente

def find_winner(trace):
    """Retourne l'identifiant du joueur gagnant ('J0', 'J1', ...) depuis une trace JSON."""
    vp = _get_last_vp(trace)
    return max(vp, key=lambda player: int(vp[player]))


def get_final_vp(trace, player='J0'):
    """Retourne les points de victoire finaux du joueur donné depuis une trace JSON."""
    vp = _get_last_vp(trace)
    return int(vp.get(player, 0))

def mutate_scaled(individual, indpb, rate = 0.1):
    """Mute chaque gène avec une force proportionnelle à sa plage de valeurs."""
    for i, (min_val, max_val) in enumerate(dict_parameters.values()):
        if random.random() < indpb:
            # Force de mutation : 10% de l'amplitude totale du paramètre
            sigma = (max_val - min_val) * rate
            individual[i] += random.gauss(0, sigma)
            # On s'assure de rester strictement dans les bornes définies
            individual[i] = max(min(individual[i], max_val), min_val)
    return individual,

# Function to generate a random individual
def generate_individual():
    """
    Generate a random individual based on the defined parameters and their ranges.
    Returns:
        list: An individual represented as a list of parameter values.
    """
    return [random.uniform(min_val, max_val) for min_val, max_val in dict_parameters.values()]

# Agent evaluation function
def evaluate_agent(args):
    """
    Evaluates the agent over FIXED_GAME_CONFIGS (rotating positions, diverse opponents).
    Games are genuinely random (no fixed seed) so the board layout, dice rolls, and
    card draws vary — this ensures the agent's params actually influence outcomes.
    With 20 games the average VP is a reliable signal of true performance.
    """
    individual, gen = args
    import json
    import shutil
    opponents_classes = [a1, a2, a3, a4, a5, a6, a7, a8]
    params = dict(zip(dict_parameters.keys(), individual))
    total_vp = 0
    victories = 0  # Nouveau compteur de victoires  

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

    fitness_score = avg_vp * WEIGHT_VP + win_rate *10* WEIGHT_WIN  # Combine VP and win rate into a single fitness score
    return (fitness_score,)



# DEAP toolbox initialization
toolbox = base.Toolbox()
toolbox.register("individual", tools.initIterate, creator.Individual, generate_individual)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)
toolbox.register("evaluate", evaluate_agent)
toolbox.register("mate", tools.cxBlend, alpha=0.3)  # Croisement blend
# Mutation: adds Gaussian noise to each gene
toolbox.register("mutate", mutate_scaled, indpb=0.2 , rate = RATE)
toolbox.register("select", tools.selTournament, tournsize=3)




if __name__ == "__main__":

    # Parallélise les évaluations sur les cœurs disponibles (50% pour ne pas saturer la RAM)
    porcentaje_workers = 0.85
    workers = max(1, int((os.cpu_count() or 1) * porcentaje_workers))
    pool = multiprocessing.Pool(processes=workers, maxtasksperchild=2)
    toolbox.register("map", pool.map)
    

    # Create the initial population
    population = toolbox.population(n=POP_SIZE)

    # Evaluate the initial population before the first generation (generation -1)
    fits = pool.map(evaluate_agent, [(ind, -1) for ind in population])
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

    for gen in range(N_GEN):
        start_time = time.time()
        
        # --- 1. ÉLITISME SÉCURISÉ ---
        # On sauvegarde les 2 meilleurs individus de la génération actuelle
        elites = tools.selBest(population, 2)
        clones_elites = list(map(toolbox.clone, elites))
        
        # --- 2. SÉLECTION ---
        # On sélectionne les parents pour le reste de la population
        parents = toolbox.select(population, len(population) - 2)
        offspring = list(map(toolbox.clone, parents))
        
        # --- 3. CROISEMENT ET MUTATION ---
        offspring = algorithms.varAnd(offspring, toolbox, cxpb=CXPB, mutpb=MUTPB)
        
        # --- NOUVEAU : RÉPARATION DE L'ADN (Clamping) ---
        # On s'assure que le croisement cxBlend n'a pas créé de valeurs aberrantes
        for ind in offspring:
            for i, (min_val, max_val) in enumerate(dict_parameters.values()):
                ind[i] = max(min(ind[i], max_val), min_val)
                
        # --- 4. RECOMBINAISON ---
        # On réintègre nos élites pures avec les enfants mutés/croisés
        offspring.extend(clones_elites)
        
        # --- 5. ÉVALUATION ---
        # Tout le monde rejoue (même les élites, pour prouver que ce n'était pas de la chance)
        fits = pool.map(evaluate_agent, [(ind, gen) for ind in offspring])
        for ind, fit in zip(offspring, fits):
            ind.fitness.values = fit
            
        # 6. REMPLACEMENT
        population[:] = offspring
        
        # Mise à jour des statistiques
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
