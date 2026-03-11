"""
train_genetic_agent_diag.py — VERSION DIAGNOSTIC

Objectif : identifier pourquoi tous les individus obtiennent le même fitness
malgré des paramètres différents.

3 niveaux de diagnostic activables indépendamment :
  DIAG_POPULATION  → diversité des gènes dans la population
  DIAG_EVALUATION  → détail avg_vp / win_rate / fitness par individu
  DIAG_CONTRAST    → 2 individus extrêmes jouent la même partie, on compare leurs VP
"""

import sys, os, multiprocessing, random, itertools, time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from deap import base, creator, tools, algorithms
from Agents.MioAgente import MioAgente
from Managers.GameDirector import GameDirector
from Agents.AlexPelochoJaimeAgent import AlexPelochoJaimeAgent as a1
from Agents.CarlesZaidaAgent import CarlesZaidaAgent as a2
from Agents.CrabisaAgent import CrabisaAgent as a3
from Agents.EdoAgent import EdoAgent as a4
from Agents.PabloAleixAlexAgent import PabloAleixAlexAgent as a5
from Agents.RandomAgent import RandomAgent as a6
from Agents.SigmaAgent import SigmaAgent as a7
from Agents.TristanAgent import TristanAgent as a8

# ──────────────────────────────────────────────
# INTERRUPTEURS DIAGNOSTIC  (True = activé)
# ──────────────────────────────────────────────
DIAG_POPULATION = True   # std/min/max de chaque gène dans la population
DIAG_EVALUATION = True   # avg_vp, win_rate, fitness bruts pour chaque individu évalué
DIAG_CONTRAST   = True   # compare 2 individus extrêmes sur les 3 premières parties
DIAG_GEN_FREQ   = 1      # fréquence (toutes les N générations) pour DIAG_POPULATION

# ──────────────────────────────────────────────
# DEAP creators
# ──────────────────────────────────────────────
if not hasattr(creator, 'FitnessMax'):
    creator.create("FitnessMax", base.Fitness, weights=(1.0,))
if not hasattr(creator, 'Individual'):
    creator.create("Individual", list, fitness=creator.FitnessMax)

# ──────────────────────────────────────────────
# PARAMÈTRES
# ──────────────────────────────────────────────
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
    "weight_dev_card_urgency":      (0, 1),
    "weight_victory_near_threshold":(0, 10),
    "army_weight":                  (0, 1),
}
PARAM_KEYS = list(dict_parameters.keys())
IND_SIZE   = len(dict_parameters)

N_games_per_evaluation = 5
POP_SIZE   = 10
N_GEN      = 5
CXPB       = 0.7
MUTPB      = 0.25
RATE       = 0.1
WEIGHT_VP  = 1.0
WEIGHT_WIN = 5.0

_ALL_OPP_COMBOS = list(itertools.combinations(range(8), 3))
FIXED_GAME_CONFIGS = [
    (i % 4, _ALL_OPP_COMBOS[i % len(_ALL_OPP_COMBOS)])
    for i in range(N_games_per_evaluation)
]
OPPONENTS_CLASSES = [a1, a2, a3, a4, a5, a6, a7, a8]

# ──────────────────────────────────────────────
# UTILITAIRES TRACE
# ──────────────────────────────────────────────
def _get_last_vp(trace):
    last_round = max(trace['game'].keys(), key=lambda r: int(r.split('_')[-1]))
    last_turn  = max(trace['game'][last_round].keys(),
                     key=lambda t: int(t.split('_')[-1].lstrip('P')))
    return trace['game'][last_round][last_turn]['end_turn']['victory_points']

def find_winner(trace):
    vp = _get_last_vp(trace)
    return max(vp, key=lambda p: int(vp[p]))

def get_final_vp(trace, player='J0'):
    vp = _get_last_vp(trace)
    return int(vp.get(player, 0))

# ──────────────────────────────────────────────
# MUTATION
# ──────────────────────────────────────────────
def mutate_scaled(individual, indpb, rate=0.1):
    for i, (min_val, max_val) in enumerate(dict_parameters.values()):
        if random.random() < indpb:
            sigma = (max_val - min_val) * rate
            individual[i] += random.gauss(0, sigma)
            individual[i]  = max(min(individual[i], max_val), min_val)
    return individual,

def generate_individual():
    return [random.uniform(lo, hi) for lo, hi in dict_parameters.values()]

def make_mioagente_class(params):
    """Returns a MioAgente subclass with params baked in, usable as a plain class by AgentManager."""
    class _ParametrizedMioAgente(MioAgente):
        def __init__(self, agent_id):
            super().__init__(agent_id, params=params)
    return _ParametrizedMioAgente

# ──────────────────────────────────────────────
# ÉVALUATION  (avec diagnostic optionnel)
# ──────────────────────────────────────────────
def evaluate_agent(args):
    import json, shutil
    individual, gen = args

    params    = dict(zip(PARAM_KEYS, individual))
    total_vp  = 0
    victories = 0
    per_game_vp = []  # pour DIAG_EVALUATION


    for i, (position, opp_indices) in enumerate(FIXED_GAME_CONFIGS):
        seed_val = (gen * 1000) + i
        random.seed(seed_val)

        opp_ids   = [j for j in range(4) if j != position]
        MioAgenteClass = make_mioagente_class(params)

        # ── DIAG : les params arrivent-ils vraiment à l'agent ? ──
        if DIAG_EVALUATION and i == 0 and gen <= 0:
            sample_agent = MioAgenteClass(position)
            missing = [k for k in PARAM_KEYS if k not in sample_agent.params]
            if missing:
                print(f"  [DIAG][PARAMS MANQUANTS] {missing}", flush=True)
            else:
                sample = {k: round(sample_agent.params[k], 3) for k in PARAM_KEYS[:4]}
                print(f"  [DIAG][PARAMS OK] échantillon agent partie 0 : {sample}", flush=True)

        agents_classes = [None] * 4
        agents_classes[position] = MioAgenteClass
        for k, opp_idx in enumerate(opp_indices):
            agents_classes[opp_ids[k]] = OPPONENTS_CLASSES[opp_idx]

        game_director = GameDirector(agents=agents_classes, max_rounds=200)
        trace_path    = game_director.trace_loader.full_path
        game_director.game_start(i, print_outcome=False)

        agent_id = f"J{position}"
        try:
            with open(trace_path / f'game_{i}.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            vp = get_final_vp(data, player=agent_id)
            total_vp  += vp
            per_game_vp.append(vp)
            if find_winner(data) == agent_id:
                victories += 1
            del data
        except Exception as e:
            print(f"  [DIAG][ERREUR TRACE] partie {i} : {e}", file=sys.stderr)
            per_game_vp.append(-1)

        shutil.rmtree(trace_path, ignore_errors=True)

    avg_vp   = total_vp / N_games_per_evaluation
    win_rate = victories / N_games_per_evaluation
    fitness  = avg_vp * WEIGHT_VP + win_rate * WEIGHT_WIN

    # ── DIAG : composantes brutes du fitness ──
    if DIAG_EVALUATION:
        vp_std = (sum((v - avg_vp)**2 for v in per_game_vp) / len(per_game_vp)) ** 0.5
        ind_id = hash(tuple(round(x, 4) for x in individual)) & 0xFFFF
        print(
            f"  [DIAG][EVAL] ind#{ind_id:05d} | "
            f"avg_vp={avg_vp:.2f}  win_rate={win_rate:.2f}  "
            f"fitness={fitness:.2f}  vp_std={vp_std:.2f}  "
            f"vp_range=[{min(per_game_vp)},{max(per_game_vp)}]",
            flush=True
        )

    return (fitness,)


# ──────────────────────────────────────────────
# DIAGNOSTIC CONTRASTE  (2 individus extrêmes)
# ──────────────────────────────────────────────
def run_contrast_diagnostic(population, gen):
    """
    Prend le meilleur et le pire individu, les fait jouer les 3 premières parties
    avec le même seed, et compare leurs VP partie par partie.
    → Si VP identiques : les params n'influencent PAS les décisions.
    → Si VP différents : le signal existe, le problème est ailleurs.
    """
    import json, shutil

    sorted_pop = sorted(population, key=lambda ind: ind.fitness.values[0])
    worst = sorted_pop[0]
    best  = sorted_pop[-1]

    print(f"\n{'='*60}", flush=True)
    print(f"[DIAG][CONTRASTE] Génération {gen+1}", flush=True)
    print(f"  Meilleur  fitness={best.fitness.values[0]:.2f}  "
          f"| city_weight={best[PARAM_KEYS.index('city_weight')]:.3f}  "
          f"| weight_cereal={best[PARAM_KEYS.index('weight_cereal')]:.3f}", flush=True)
    print(f"  Pire      fitness={worst.fitness.values[0]:.2f}  "
          f"| city_weight={worst[PARAM_KEYS.index('city_weight')]:.3f}  "
          f"| weight_cereal={worst[PARAM_KEYS.index('weight_cereal')]:.3f}", flush=True)

    # Vérifie que les params sont réellement différents
    diffs = [(PARAM_KEYS[i], round(best[i]-worst[i], 3))
             for i in range(IND_SIZE) if abs(best[i]-worst[i]) > 0.01]
    if not diffs:
        print("  ⚠️  [CONTRASTE] Les deux individus ont des params IDENTIQUES → "
              "problème de génération/clonage !", flush=True)
        print(f"{'='*60}\n", flush=True)
        return
    print(f"  Différences de gènes (best - worst) : {diffs[:6]}{'...' if len(diffs)>6 else ''}",
          flush=True)

    # Joue 3 parties avec seed fixe pour les deux
    N_contrast = 3
    print(f"  {'Partie':<8} {'VP_best':<10} {'VP_worst':<10} {'Δ':>6}", flush=True)
    print(f"  {'-'*36}", flush=True)

    for i in range(N_contrast):
        position, opp_indices = FIXED_GAME_CONFIGS[i]
        opp_ids = [j for j in range(4) if j != position]

        vps = {}
        for label, ind in [('best', best), ('worst', worst)]:
            params = dict(zip(PARAM_KEYS, ind))
            random.seed(i * 999)  # seed identique pour les deux

            MioAgenteClass = make_mioagente_class(params)
            agents_classes = [None] * 4
            agents_classes[position] = MioAgenteClass
            for k, opp_idx in enumerate(opp_indices):
                agents_classes[opp_ids[k]] = OPPONENTS_CLASSES[opp_idx]

            gd         = GameDirector(agents=agents_classes, max_rounds=200)
            trace_path = gd.trace_loader.full_path
            gd.game_start(i, print_outcome=False)
            agent_id   = f"J{position}"

            try:
                with open(trace_path / f'game_{i}.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                vps[label] = get_final_vp(data, player=agent_id)
                del data
            except Exception as e:
                vps[label] = -1
                print(f"  [CONTRASTE][ERREUR] {e}", file=sys.stderr)
            shutil.rmtree(trace_path, ignore_errors=True)

        delta = vps['best'] - vps['worst']
        flag  = " ← IDENTIQUES ⚠️" if delta == 0 else ""
        print(f"  partie {i:<3} | VP_best={vps['best']:<5} VP_worst={vps['worst']:<5} "
              f"Δ={delta:>+3}{flag}", flush=True)

    print(f"{'='*60}\n", flush=True)


# ──────────────────────────────────────────────
# DIAGNOSTIC POPULATION (diversité des gènes)
# ──────────────────────────────────────────────
def run_population_diagnostic(population, gen):
    import statistics
    print(f"\n[DIAG][POPULATION] Génération {gen+1} — diversité des gènes", flush=True)
    print(f"  {'Paramètre':<35} {'min':>7} {'max':>7} {'avg':>7} {'std':>7}", flush=True)
    print(f"  {'-'*63}", flush=True)

    all_zero_params  = []
    no_variance_params = []

    for idx, key in enumerate(PARAM_KEYS):
        vals = [ind[idx] for ind in population]
        lo, hi = dict_parameters[key]
        mn  = min(vals)
        mx  = max(vals)
        avg = sum(vals) / len(vals)
        std = statistics.stdev(vals) if len(vals) > 1 else 0.0
        flag = ""
        if std < 0.01 * (hi - lo):  # std < 1% de l'amplitude → quasi-constant
            no_variance_params.append(key)
            flag = " ← ⚠️ SANS VARIANCE"
        if mx < 0.01 * (hi - lo):   # tous proches de 0
            all_zero_params.append(key)
            flag = " ← ⚠️ TOUS À ZÉRO"
        print(f"  {key:<35} {mn:>7.3f} {mx:>7.3f} {avg:>7.3f} {std:>7.3f}{flag}",
              flush=True)

    if no_variance_params:
        print(f"\n  ⚠️  Paramètres sans variance : {no_variance_params}", flush=True)
    if all_zero_params:
        print(f"  ⚠️  Paramètres tous à zéro   : {all_zero_params}", flush=True)

    # Vérifie si des individus sont identiques (clones)
    fingerprints = [tuple(round(x, 4) for x in ind) for ind in population]
    unique = len(set(fingerprints))
    print(f"\n  Individus uniques : {unique}/{len(population)}", flush=True)
    if unique < len(population) * 0.5:
        print(f"  ⚠️  PLUS DE 50% DE CLONES — problème de diversité génétique !", flush=True)
    print("", flush=True)


# ──────────────────────────────────────────────
# TOOLBOX
# ──────────────────────────────────────────────
toolbox = base.Toolbox()
toolbox.register("individual", tools.initIterate, creator.Individual, generate_individual)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)
toolbox.register("evaluate", evaluate_agent)
toolbox.register("mate", tools.cxBlend, alpha=0.3)
toolbox.register("mutate", mutate_scaled, indpb=0.2, rate=RATE)
toolbox.register("select", tools.selTournament, tournsize=3)


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
if __name__ == "__main__":

    try:
        import psutil
        psutil_available = True
    except ImportError:
        psutil_available = False

    porcentaje_workers = 0.85
    workers = max(1, int((os.cpu_count() or 1) * porcentaje_workers))
    pool = multiprocessing.Pool(processes=workers, maxtasksperchild=2)
    toolbox.register("map", pool.map)

    population = toolbox.population(n=POP_SIZE)

    # ── Évaluation initiale ──
    print(">>> Évaluation de la population initiale (gen=-1) ...", flush=True)
    fits = pool.map(evaluate_agent, [(ind, -1) for ind in population])
    for ind, fit in zip(population, fits):
        ind.fitness.values = fit

    # ── Diagnostic initial ──
    if DIAG_POPULATION:
        run_population_diagnostic(population, gen=-1)

    # ── Fitness de la pop initiale ──
    all_fits = [ind.fitness.values[0] for ind in population]
    fit_std  = (sum((f - sum(all_fits)/len(all_fits))**2
                    for f in all_fits) / len(all_fits)) ** 0.5
    print(f">>> Pop initiale — fitness std={fit_std:.3f}  "
          f"(si ~0 : tous les individus ont le même fitness ← BUG)", flush=True)

    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", lambda x: round(sum(v[0] for v in x) / len(x), 2))
    stats.register("max", lambda x: round(max(v[0] for v in x), 2))
    stats.register("min", lambda x: round(min(v[0] for v in x), 2))
    stats.register("std", lambda x: round((sum((v[0]-sum(vv[0] for vv in x)/len(x))**2
                                              for v in x)/len(x))**0.5, 3))

    hall_of_fame = tools.HallOfFame(1)

    for gen in range(N_GEN):
        start_time = time.time()

        # ── Élitisme ──
        elites       = tools.selBest(population, 2)
        clones_elites = list(map(toolbox.clone, elites))

        # ── Sélection + opérateurs génétiques ──
        parents  = toolbox.select(population, len(population) - 2)
        offspring = list(map(toolbox.clone, parents))
        offspring = algorithms.varAnd(offspring, toolbox, cxpb=CXPB, mutpb=MUTPB)

        # Clamping
        for ind in offspring:
            for i, (lo, hi) in enumerate(dict_parameters.values()):
                ind[i] = max(min(ind[i], hi), lo)

        offspring.extend(clones_elites)

        # ── Évaluation ──
        fits = pool.map(evaluate_agent, [(ind, gen) for ind in offspring])
        for ind, fit in zip(offspring, fits):
            ind.fitness.values = fit

        population[:] = offspring
        hall_of_fame.update(population)
        record = stats.compile(population)

        elapsed = time.time() - start_time
        speed   = elapsed / len(offspring)

        mem_str = ""
        if psutil_available:
            mem_mb  = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
            mem_str = f" | RAM: {mem_mb:.0f}MB"

        print(
            f"Génération {gen+1:>3}: "
            f"avg={record['avg']:>6.2f}  max={record['max']:>6.2f}  "
            f"min={record['min']:>6.2f}  std={record['std']:>6.3f}"
            f" | {elapsed:.1f}s ({speed:.2f}s/ind){mem_str}",
            flush=True
        )

        # ── Diagnostics périodiques ──
        if DIAG_POPULATION and (gen % DIAG_GEN_FREQ == 0):
            run_population_diagnostic(population, gen)

        if DIAG_CONTRAST and (gen % DIAG_GEN_FREQ == 0):
            run_contrast_diagnostic(population, gen)

    print(f"\nMeilleur individu : {hall_of_fame[0]}")
    print(f"Fitness           : {hall_of_fame[0].fitness.values[0]:.2f}")

    pool.close()
    pool.join()

    with open("best_agent.txt", "w") as f:
        f.write(str(hall_of_fame[0]))