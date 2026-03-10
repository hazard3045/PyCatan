# Initial Placement Strategy (`on_game_start`)
The final decision is based on maximizing the calculated score.

### 1. The Mathematical Formula
The score for a specific node $n$ is determined by the weighted sum of the production probabilities of the adjacent terrains, plus specific strategic bonuses:

$$Score(n) = \sum_{t \in T(n)} (P(t) \times W_{r_t}) + Harbor_{Bonus}$$

Where:

* $T(n)$: The set of terrain hexes (up to 3) touching node $n$.
* $P(t)$: The actual probability of the terrain (expressed in **Dots**, from 1 to 5).
* $W_{r_t}$: The genetic weight assigned to the resource produced by terrain $t$ (Wood, Clay, etc.).
* $Harbor_{Bonus}$: An added value if the node is located on a harbor.

---

### 2. Genetic Parameters (The Agent's DNA)

These parameters are stored in the `self.params` dictionary. The Genetic Algorithm (GA) modifies these values during training to discover the winning combination.

#### **Resource Weights**

These define the importance of each hex based on its output:
| Parameter | Resource | Default Value | Strategic Note |
| :--- | :--- | :--- | :--- |
| `weight_wood` | Wood | 1.0 | Crucial for roads and settlements (expansion). |
| `weight_clay` | Clay | 1.0 | Crucial for roads and settlements (expansion). |
| `weight_cereal` | Wheat | 1.0 | Needed for settlements, cities, and dev cards. |
| `weight_mineral` | Ore | 1.0 | Essential for cities and cards (late game). |
| `weight_wool` | Sheep | 0.8 | Generally more common, used for settlements/cards. |
| `start_harbour_bonus` | harbour | 1 | Represents the user's propensity to conquer ports early. |

#### **Strategic Modifiers**

These define the "personality" of the agent on the board:

* `weight_harbor`: A bonus given to coastal nodes with a harbor. A high value creates a "maritime" strategy.
* `road_strategy_center_control`: Weight given to the number of free exits a node has. Favors moving toward the center to avoid being blocked.
* `road_strategy_future_node`: The weight given to the quality of the *next* possible settlement (Distance-2 Lookahead).

---

### 3. Strategic Road Logic

To choose the direction of the first road, the agent uses a hybrid function:

1. **Lookahead ($D_2$):** It scans all nodes two roads away (where it can legally build the next settlement) and calculates their `evaluate_node` score.
2. **Centrality:** It rewards nodes with 3 connections instead of 2 (providing more escape options).
3. **Harbors:** If the road leads toward a harbor, it adds the genetic harbor weight.

---

### 4. Technical Implementation (Python)

The agent converts dice numbers (2-12) into **Dots** to create a linear scale of rarity:

* **2 or 12** $\rightarrow$ 1 Dot
* **6 or 8** $\rightarrow$ 5 Dots
* **7 (Desert)** $\rightarrow$ 0 Dots

---


#  Build Phase Strategy (on_build_phase)

The agent evaluates its current resources and legal moves to maximize its economic Return on Investment (ROI). This behavior is regulated by genetic "patience" parameters that simulate human-like resource management, allowing the agent to save for high-value upgrades rather than spending impulsively.

### 1. The Priority Hierarchy

The agent strictly follows a descending order of priorities. It systematically checks resources and board legality, ensuring optimal spending:

    City Upgrade (Top Priority)

    Town / Settlement: Built on the highest-scoring legal intersection, provided the agent is not saving for a City.

    Road: Used purely for strategic expansion to reach new building sites, provided the agent is not saving for a Town or a City.

    Development Card: Purchased as a last resort if resources are abundant but no board placements are legally possible.

 ### 2. Resource Management & Genetic Patience

    weight_city (City Patience)

    weight_town (Town Patience)

### 3. Strategic Road Expansion (pick_best_expansion_road)

When the agent decides to build a road (and is not saving its resources for buildings), it does not pick a random legal path. It uses a lookahead algorithm to act as a strategic compass.

For every legal road placement, the agent evaluates the finishing node (where the road ends):

    It calculates the evaluate_node() score of the immediate destination.

    It scans the empty adjacent nodes of that destination (where future settlements could be built) and adds 0.5× their potential score.

    The agent ultimately builds the road that yields the highest combined future potential.

---

## 💱 Commerce Phase Strategy (`on_commerce_phase`)

The commerce phase represents a shift from random, aimless trading to a highly focused **Targeted Trade** system. The agent acts exclusively to fulfill its immediate strategic needs, driven entirely by its genetic parameters, while actively preventing the accidental strengthening of its opponents.

### 1. Genetic Trade Targeting (Continuous Evaluation)
The agent calculates the percentage of completion for both a City (out of 5 cards) and a Town (out of 4 cards) and multiplies it by the respective genetic parameter to calculate a final "Desire Score":

$Desire_{City} = \left( \frac{\min(Mineral, 3) + \min(Cereal, 2)}{5} \right) \times weight\_of\_city$
$Desire_{Town} = \left( \frac{\min(Wood, 1) + \min(Clay, 1) + \min(Cereal, 1) + \min(Wool, 1)}{4} \right) \times weight\_town$

The agent automatically targets the missing resource for the objective that yields the highest $Desire$ score.

### Genetic Parameters Used in Commerce Phase

| Parameter | Function / Role | Strategic Reasoning (Why it is used) |
| --- | --- | --- |
| **`city_weight`** | Multiplier for the City progress score. | Prevents "threshold flip-flopping." If the AI has a high weight for cities, it will stubbornly seek Ore/Wheat even if it only holds a single card, refusing to be distracted by random Wood/Clay pickups. |
| **`town_weight`** | Multiplier for the Town progress score. | Allows the evolutionary algorithm to create expansionist agents. A high weight here forces the agent to trade away Ore/Wheat to aggressively claim territory before opponents do. |
| **`weight_robber_anxiety`** | Risk management modifier for hand size (> 7 cards). | Simulates the fear of the Robber. When triggered, the agent disables its resource protection algorithms and initiates a "Fire Sale" (Panic Trade). This tempts opponents to accept the trade, allowing the agent to intentionally shrink its hand size to 7 or fewer cards and survive a "7" dice roll. |
### 2. Surplus Identification & Resource Protection

Once an objective is locked in, the agent scans its hand to find the most abundant resource (Surplus) to offer. To prevent self-sabotage, it applies a strict **Protection Filter**:

* If targeting a **City**, it forces its internal evaluation count of Cereal and Mineral to 0.
* If targeting a **Town**, it forces Clay, Wood, Cereal, and Wool to 0.
* This guarantees the agent will never accidentally offer the exact materials it is trying to save, picking only from truly useless surplus resources.

### 3. Maritime vs. Domestic Trade Prioritization

When the agent determines its surplus, it explicitly prioritizes **Maritime Trade** (trading with the bank or controlled ports) over **Domestic Trade** (player-to-player offers).

* **Dynamic Exchange Rates:** The agent actively scans its built nodes (`get_exchange_rate`) to calculate the exact cost of trading its surplus resource by checking the `self.harbors` map (evaluating 2:1 specialized ports, 3:1 generic ports, and the default 4:1 bank rate).
* **Zero-Sum Advantage:** If the agent holds enough surplus to meet its maritime exchange rate, it executes the trade directly with the board (`{'gives': surplus, 'receives': target}`). This acquires the targeted resource without funneling any useful cards to opponents.
* **Domestic Fallback:** Only if the agent falls short of the maritime threshold will it construct a 1:1 `TradeOffer` and broadcast it to the other players as a last resort.

### 4. The Monopoly Ambush (Card Synergy)

Before initiating any standard trades, the agent executes a highly aggressive check for development card synergy. If the agent recently traded away a large quantity of a specific resource (more than 3) to another player, it immediately searches its hand for a **Monopoly** card. If found, it plays it to instantly steal back all the resources it just traded away, creating a massive net positive in resource economy.

---

Ecco il documento sintetico e professionale per il tuo report riguardante la fase di negoziazione passiva.

---

# 🤝 Passive Trade Negotiation (`on_trade_offer`)

The `on_trade_offer` method acts as a strategic gatekeeper, evaluating incoming proposals from opponents. Rather than blindly accepting, the agent employs a reactive negotiation strategy driven by its genetic priorities.

### 1. Goal-Oriented Evaluation

The agent instantly synchronizes the incoming offer with its internal genetic goals (`city_weight` and `town_weight`). It recalculates its building progress and checks the proposed trade against two filters:

* **The Protection Filter:** Any trade requesting resources critical to the agent's current genetic objective is automatically flagged for rejection or re-negotiation.
* **The Strategic Alignment:** A trade is only accepted if it explicitly delivers a resource required to advance the higher-scored objective.

### 2. Defensive Risk Assessment

The agent incorporates the `weight_robber_anxiety` parameter as a final sanity check. Before committing to a trade, it calculates the `new_total` hand size. If accepting the trade pushes the agent’s hand size above 7 cards, the agent evaluates the risk of a "7" dice roll. If the anxiety threshold is triggered, it will reject an otherwise "good" trade to avoid losing half its resources to the Robber.

### 3. The "Sweetened" Counter-Offer

If an offer is sub-optimal but the opponent possesses a required resource, the agent does not simply reject. It attempts to "redirect" the deal into a beneficial counter-offer:

* **Redirection:** If the opponent offers a useless resource but needs the agent's surplus, the agent refuses the original deal and proposes a strict 1:1 exchange for its target resource.
* **The Sweetener (2:1 Logic):** To ensure a higher probability of success, the agent will bundle multiple surplus resources (e.g., offering a combination of two different useless materials) in exchange for the single resource it needs. This effectively "sweetens" the deal for the opponent while protecting the agent's core build requirements.

### Genetic Parameter Influence

| Parameter | Impact on Negotiation |
| --- | --- |
| **`city_weight`** | Directly dictates which resources are considered "Protected" (Minerals/Cereals). Influences the decision to accept or counter-offer for City components. |
| **`town_weight`** | Directly dictates which resources are considered "Protected" (Wood/Clay/Wool). Influences the decision to accept or counter-offer for Town components. |
| **`weight_robber_anxiety`** | Acts as a hard veto for any trade that increases hand size above 7, effectively putting safety over expansion when the threat level is high. |

---

# 🛡️ Strategic Discard Management

To ensure maximum survival during the Robber's activation, the agent implements a hierarchical discard logic that directly manipulates its Hand object. This method prioritizes the retention of "Win-Condition" resources based on genetic scoring.
1. Direct Hand Manipulation

2. Goal-Based Hierarchy

The agent performs a "Genetic Triage" before discarding:

    City Priority: If the city_weight score is dominant, the agent creates a defensive shell around Minerals and Cereals. It systematically removes Wool, Clay, and Wood (in that order) until the hand size is exactly 7.

    Town Priority: If town_weight is higher, the agent protects the balance of Wood, Clay, Cereal, and Wool, identifying Minerals as the primary disposable resource. 
    
3. Surplus vs. Essential Sacrifice

The removal loop is designed to strip away surplus first (e.g., discarding a 3rd Cereal only after all Wool is gone). If the agent is forced to discard essential materials, it does so by following the reverse order of building importance, preserving the rarest required materials until the very last iteration of the loop.

# 🕵️ Aggressive Robber Placement (on_moving_thief)

The agent's strategy for moving the Robber has evolved from a random assignment to a Genetic Threat Analysis.
## 1. Resource Sabotage

It prioritizes placing the Robber on hexes that produce these high-value resources for opponents, effectively creating a resource scarcity for competitors.

## 2. Probability & Impact

Each terrain is assigned a Threat Score based on:

    Dice Frequency: Hexes with high-probability numbers (6, 8, 5, 9) are prioritized.

    Occupancy: The agent targets hexes where multiple opponents have settled, maximizing the disruptive impact of the Robber.

    Self-Preservation: A mandatory filter prevents the agent from ever placing the Robber on a hex where it has its own settlements or cities.

## 3. Target Selection

If multiple opponents are adjacent to the chosen hex, the agent selects the primary target based on the game state, ensuring that the most advanced player is hindered.

# 💎 Aggressive Monopoly Scoring (on_monopoly_card_use)

The agent now employs a multi-factor scoring function to maximize the impact of the Monopoly development card, shifting from simple utility to Strategic Economic Sabotage.
## 1. Triangulation Logic

The scoring function evaluates each resource by combining three distinct vectors:

    The Deficiency Vector: Calculates the gap between the current Hand and the materials required for the next building goal (weight_of_city or weight_town).

    The Genetic Vector: Integrates the atomic weights of resources (e.g., weight_mineral) to align the choice with the agent's long-term DNA strategy.

    The Sabotage Vector: Analyzes the board's topology to identify which resources opponents are most likely to possess in abundance, based on their settlement positions and hex probabilities.

Certamente. Ecco la sezione del report in formato Markdown dedicata al metodo `on_road_building_card_use`. Ho messo in risalto i parametri genetici e la logica di scoring per spiegare come l'agente trasforma una carta sviluppo in un vantaggio territoriale e tattico.

---

# 🏗️ Strategic Infrastructure Expansion (`on_road_building_card_use`)

The scoring function for this method is driven by three key genetic weights:

1. **`weight_road_expansion`**:
* **Role**: Focuses on the continuity of the road network.
* **Impact**: Higher values prioritize connecting the two new roads into a single segment or attaching them to the existing longest path. This is the primary driver for securing the **Longest Road** trophy (+2 Victory Points).

2. **`weight_material_diversity`**:
* **Role**: Promotes economic self-sufficiency.
* **Impact**: Grants a scoring bonus if a road leads to a node adjacent to a resource type that the agent does **not** yet produce. This ensures the agent expands toward variety rather than redundancy.

3. **`weight_block_opponent`**:
* **Role**: Governs aggressive territorial denial.
* **Impact**: Analyzes if the potential placement occupies a "bottleneck" or a high-value node that an opponent could have built upon. If this weight is high, the agent will prioritize "murando" (walling off) competitors over its own optimal growth.



### 🔍 The Scoring Algorithm

For every possible pair of roads $(r_1, r_2)$, the agent calculates a total score based on the following logic:

* **Concatenation Bonus**: If the two roads are continuous, a significant multiplier based on `weight_road_expansion` is applied.
* **Discovery Bonus**: Each unique resource adjacent to the new nodes that is missing from the agent's current production adds a value scaled by `weight_material_diversity`.
* **Sabotage Multiplier**: The agent identifies if the target nodes are currently reachable by opponents. Occupying these nodes triggers a defensive bonus scaled by `weight_block_opponent`.



# All parameters
new_resources_weight 
distance_weight = 1.0
harbor_weight = 1.0
street_weight = 1.0 
town_weight = 1.0 -
city_weight = 1.0 -
lumber_a=1.0
brick_a=1.0
wool_a=1.0
grain_a=1.0
ore_a=1.0
lumber_b=1.0   #legname
brick_b=1.0
wool_b=1.0
grain_b=1.0
ore_b=1.
ratio_resources_weight = 1.0
need_for_resources_weight = 1.0
position_player_weight = 1.0
number_of_cards_weight = 1.0
need_resources_stolen_weight = 1.0
steal_from_player_weight = 1.0
defense_weight = 1.0
need_for_roads_weight = 1.0