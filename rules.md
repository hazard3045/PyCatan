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