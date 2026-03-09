import random

from Classes.Constants import DevelopmentCardConstants, HarborConstants, MaterialConstants, BuildConstants, TerrainConstants
from Classes.Materials import Materials
from Classes.TradeOffer import TradeOffer
from Classes.Hand import Hand
from Interfaces.AgentInterface import AgentInterface


class MioAgente(AgentInterface):
    """
    Es necesario poner super().nombre_de_funcion() para asegurarse de que coge la función del padre
    """
    town_number = 0
    material_given_more_than_three = None
    # Son los materiales más necesarios en construcciones, luego se piden con year of plenty para tener en mano
    year_of_plenty_material_one = MaterialConstants.CEREAL
    year_of_plenty_material_two = MaterialConstants.MINERAL

    def __init__(self, agent_id, params=None):
        super().__init__(agent_id)
        self.params = params if params is not None else {}

    #calculate the probability dots for a given dice roll
    def get_probability_dots(self, roll):
        if roll == 0 or roll == 7:
            return 0
        # The math trick to get dots: 6 - absolute distance from 7
        return 6 - abs(7 - roll)

    #Calculate the score of a node
    def evaluate_node(self, node_id):
        score = 0.0
        
        # 1.Recupera i pesi genetici per ogni risorsa
        w_wood = self.params.get('weight_wood', 1.0)
        w_clay = self.params.get('weight_clay', 1.0)
        w_cereal = self.params.get('weight_cereal', 1.0)
        w_mineral = self.params.get('weight_mineral', 1.0)
        w_wool = self.params.get('weight_wool', 0.8)
        w_harbor = self.params.get('start_harbor_bonus', 1.5)
        
        weights = {
            TerrainConstants.WOOD: w_wood,
            TerrainConstants.CLAY: w_clay,
            TerrainConstants.CEREAL: w_cereal,
            TerrainConstants.MINERAL: w_mineral,
            TerrainConstants.WOOL: w_wool,
            TerrainConstants.DESERT: 0.0
        }
        
        # 2. Evaluate surrounding terrain
        contacting_terrains = self.board.nodes[node_id]['contacting_terrain']
        
        for terrain_id in contacting_terrains:
            terrain_info = self.board.terrain[terrain_id]
            
            # Get the dice roll probability and convert it to dots (1-6)
            roll = terrain_info['probability']
            dots = self.get_probability_dots(roll)
            
            # Get resource type
            res_type = terrain_info['terrain_type']
            
            # Multiply probability by the genetic importance of the resource
            res_weight = weights.get(res_type, 0.0)
            #Sum of Prob(t) + Weight(t) for each terrain t contacting the node
            score += (dots * res_weight)
            
        # 3. Evaluate Harbor Bonus
        harbor_type = self.board.nodes[node_id]['harbor']
        #If it's an harbour that gives a bonus for a resource we care about, add the harbor bonus
        if harbor_type != HarborConstants.NONE:
            # Add a flat bonus if the node has a harbor
            score += w_harbor
        #return the final score for the node
        return score

    #select the best road to build based on the strategic evaluation of the adjacent nodes
    def select_strategic_road(self, start_node_id):

        #find all adj node from the starting node
        possible_adjacent_nodes = self.board.nodes[start_node_id]['adjacent']
        
        # Genetic parameters to balance the different road strategies
        w_future_node = self.params.get('road_strategy_future_node', 1.0)
        w_harbor = self.params.get('weight_harbor', 1.5)
        w_center = self.params.get('road_strategy_center_control', 0.5)
        
        best_road_destination = -1
        highest_score = -float('inf')
        
        for adj_node in possible_adjacent_nodes:
            path_score = 0.0
            
            # --- STRATEGY 1: Center Control (Degrees of Freedom) ---
            connections = len(self.board.nodes[adj_node]['adjacent'])
            #(3 o 2) * center => NOT much helpfull
            path_score += (connections * w_center)
            
            # --- STRATEGY 2: Harbor Hunting ---
            #If it's an harbour that gives a bonus for a resource we care about, add the harbor bonus
            if self.board.nodes[adj_node]['harbor'] != HarborConstants.NONE:
                path_score += w_harbor
                
            # --- STRATEGY 3: Distance 2 Lookahead ---
            # Find the best legal settlement spot 2 roads away
            dist_2_nodes = self.board.nodes[adj_node]['adjacent']
            best_dist_2_score = 0.0
            
            for d2_node in dist_2_nodes:
                if d2_node == start_node_id:
                    continue
                # If legal to build a settlement here
                #If noones is here and there are no adjacent settlements, it's a valid future node
                if self.board.nodes[d2_node]['player'] == -1 and self.board.empty_adjacent_nodes(d2_node):
                    future_score = self.evaluate_node(d2_node)
                    if future_score > best_dist_2_score:
                        #update the best score for this distance-2 node if needed
                        best_dist_2_score = future_score
                        
            # Add the weighted future score to the path score
            path_score += (best_dist_2_score * w_future_node)
            
            # Final comparison
            if path_score > highest_score:
                highest_score = path_score
                best_road_destination = adj_node
                
        # Fallback
        if best_road_destination == -1:
            import random
            best_road_destination = random.choice(possible_adjacent_nodes)
            
        return best_road_destination

    def pick_best_expansion_road(self, valid_roads):
        best_road = valid_roads[0]
        highest_potential = -float('inf')
        
        for road in valid_roads:
            # We look at the 'finishing_node' (where the road ends)
            target_node = road['finishing_node']
            
            # The score is a mix of the node itself and its neighbors (future potential)
            potential_score = self.evaluate_node(target_node)
            
            # Look at adjacent nodes of the finishing node to see if they are good spots
            for future_node in self.board.nodes[target_node]['adjacent']:
                if self.board.nodes[future_node]['player'] == -1:
                    potential_score += (self.evaluate_node(future_node) * 0.5)
            
            if potential_score > highest_potential:
                highest_potential = potential_score
                best_road = road
                
        return best_road

    def get_exchange_rate(self, material_index):
        """
        Calculates the exchange rate for a given material based on owned harbors.
        Checks the specific dictionary mapping nodes to HarborConstants.
        """
        best_rate = 4 # Default bank trade is 4:1
        
        # Mappa fissa dei porti (Node_ID -> HarborConstant)
        harbors_map = {
            0: HarborConstants.WOOD, 1: HarborConstants.WOOD,
            3: HarborConstants.CEREAL, 4: HarborConstants.CEREAL,
            14: HarborConstants.CLAY, 15: HarborConstants.CLAY,
            28: HarborConstants.MINERAL, 38: HarborConstants.MINERAL,
            50: HarborConstants.WOOL, 51: HarborConstants.WOOL,
            7: HarborConstants.ALL, 17: HarborConstants.ALL, 26: HarborConstants.ALL, 
            37: HarborConstants.ALL, 45: HarborConstants.ALL, 46: HarborConstants.ALL, 
            47: HarborConstants.ALL, 48: HarborConstants.ALL
        }
        
        # Iterate through the list of nodes using enumerate to get both index (node_id) and the node object
        for node_id, node in enumerate(self.board.nodes):
            
            # If we own a settlement or city on this node
            if node['player'] == self.id:
                
                # Check if this specific node ID has a harbor attached to it
                if node_id in harbors_map:
                    harbor_type = harbors_map[node_id]
                    
                    # If we have the specific 2:1 harbor for the material we want to give
                    if harbor_type == material_index:
                        return 2 # Best possible rate, we can return immediately
                        
                    # If we have a generic 3:1 harbor
                    elif harbor_type == HarborConstants.ALL:
                        best_rate = 3 # Save it, but keep checking in case we have a 2:1 elsewhere
                        
        return best_rate

    def on_trade_offer(self, board_instance, offer, player_id):
        # 'offer.gives' is what the opponent is giving TO US.
        # 'offer.receives' is what the opponent wants FROM US.
        opponent_gives = offer.gives 
        opponent_wants = offer.receives

        # --- STEP 1: Recalculate Genetic Goals ---
        w_city = self.params.get('city_weight', 0.5)
        w_town = self.params.get('town_weight', 0.5)

        city_progress = (min(self.hand.resources.mineral, 3) + min(self.hand.resources.cereal, 2)) / 5.0
        town_progress = (min(self.hand.resources.wood, 1) + min(self.hand.resources.clay, 1) + 
                         min(self.hand.resources.cereal, 1) + min(self.hand.resources.wool, 1)) / 4.0

        city_score = city_progress * w_city
        town_score = town_progress * w_town

        target_index = -1 
        target_is_city = False
        target_is_town = False

        if city_score > town_score and city_score > 0:
            target_is_city = True
            if self.hand.resources.mineral < 3:
                target_index = 1 
            elif self.hand.resources.cereal < 2:
                target_index = 0 
                
        elif town_score >= city_score and town_score > 0:
            target_is_town = True
            if self.hand.resources.wood == 0: target_index = 3
            elif self.hand.resources.clay == 0: target_index = 2
            elif self.hand.resources.cereal == 0: target_index = 0
            elif self.hand.resources.wool == 0: target_index = 4

        # --- STEP 2: Identify Surplus and Protected Resources ---
        my_res = [
            self.hand.resources.cereal,
            self.hand.resources.mineral,
            self.hand.resources.clay,
            self.hand.resources.wood,
            self.hand.resources.wool
        ]
        
        is_protected = [False, False, False, False, False]
        if target_is_city: 
            is_protected[0] = True 
            is_protected[1] = True 
        elif target_is_town:
            is_protected[0] = True 
            is_protected[2] = True 
            is_protected[3] = True 
            is_protected[4] = True 

        # Find ALL resources that are in surplus (not protected and count > 0)
        surplus_indices = []
        for i in range(5):
            if not is_protected[i] and my_res[i] > 0 and i != target_index:
                surplus_indices.append(i)

        opp_gives_arr = [opponent_gives.cereal, opponent_gives.mineral, opponent_gives.clay, opponent_gives.wood, opponent_gives.wool]
        opp_wants_arr = [opponent_wants.cereal, opponent_wants.mineral, opponent_wants.clay, opponent_wants.wood, opponent_wants.wool]

        takes_protected = any(opp_wants_arr[i] > 0 and is_protected[i] for i in range(5))
        gives_target = (target_index != -1 and opp_gives_arr[target_index] > 0)

        # --- STEP 3: Robber Anxiety ---
        w_anxiety = self.params.get('weight_robber_anxiety', 0.5)
        total_cards = sum(my_res)
        cards_we_get = sum(opp_gives_arr)
        cards_we_give = sum(opp_wants_arr)
        new_total = total_cards + cards_we_get - cards_we_give

        if new_total > 7 and cards_we_get >= cards_we_give and random.random() < w_anxiety:
            return False

        # --- STEP 4: Accept or Counter-Offer ---

        # 1. ACCEPT: Perfect trade
        if gives_target and not takes_protected:
            return True
            
        # 2. COUNTER-OFFER: "The Sweetener" (Scenario 1 & 2)
        if target_index != -1 and len(surplus_indices) > 0:
            if takes_protected or not gives_target:
                gives_array = [0, 0, 0, 0, 0]
                receives_array = [0, 0, 0, 0, 0]
                
                # We offer 1 unit of our BEST surplus
                primary_surplus = max(surplus_indices, key=lambda idx: my_res[idx])
                gives_array[primary_surplus] = 1
                
                # ADD SWEETENER: If we have another different surplus, we add 1 unit of that too!
                # This implements your "Scenario 1+: offering an extra thing if I have it"
                for extra_idx in surplus_indices:
                    if extra_idx != primary_surplus:
                        gives_array[extra_idx] = 1
                        break # We only add ONE extra type of resource to avoid being too poor
                
                receives_array[target_index] = 1
                
                new_gives = Materials(gives_array[0], gives_array[1], gives_array[2], gives_array[3], gives_array[4])
                new_receives = Materials(receives_array[0], receives_array[1], receives_array[2], receives_array[3], receives_array[4])
                
                return TradeOffer(new_gives, new_receives)

        return False

    def on_turn_start(self):
        # self.development_cards_hand.add_card(DevelopmentCard(99, 0, 0))
        if len(self.development_cards_hand.hand) and random.randint(0, 1):
            return self.development_cards_hand.select_card(0)
        return None

    def on_having_more_than_7_materials_when_thief_is_called(self):
        # 1. Retrieve the complete DNA: Atomic resource weights
        # These are the specific genetic parameters for each material
        w_cereal = self.params.get('weight_cereal', 0.5)
        w_mineral = self.params.get('weight_mineral', 0.5)
        w_clay = self.params.get('weight_clay', 0.5)
        w_wood = self.params.get('weight_wood', 0.5)
        w_wool = self.params.get('weight_wool', 0.5)

        # Also retrieve the macro-strategy weights
        w_city = self.params.get('city_weight', 0.5)
        w_town = self.params.get('town_weight', 0.5)

        # 2. Map resource indices to their genetic weights for sorting
        # Index: 0:Cereal, 1:Mineral, 2:Clay, 3:Wood, 4:Wool
        genetic_map = {
            0: w_cereal,
            1: w_mineral,
            2: w_clay,
            3: w_wood,
            4: w_wool
        }

        # 3. Calculate current strategy based on progress and macro-weights
        city_progress = (min(self.hand.resources.mineral, 3) + min(self.hand.resources.cereal, 2)) / 5.0
        town_progress = (min(self.hand.resources.wood, 1) + min(self.hand.resources.clay, 1) + 
                         min(self.hand.resources.cereal, 1) + min(self.hand.resources.wool, 1)) / 4.0

        is_city_priority = (city_progress * w_city) > (town_progress * w_town)

        # 4. Define the Rule-Mandated Discard Amount
        to_discard = self.hand.get_total() // 2

        # 5. Execution: Discarding by Genetic Priority
        for _ in range(to_discard):
            # We create a list of available resources
            available_indices = []
            if self.hand.resources.cereal > 0: available_indices.append(0)
            if self.hand.resources.mineral > 0: available_indices.append(1)
            if self.hand.resources.clay > 0: available_indices.append(2)
            if self.hand.resources.wood > 0: available_indices.append(3)
            if self.hand.resources.wool > 0: available_indices.append(4)

            # --- DYNAMIC GENETIC FILTER ---
            def is_essential(idx):
                if is_city_priority:
                    return (idx == 0 and self.hand.resources.cereal <= 2) or \
                           (idx == 1 and self.hand.resources.mineral <= 3)
                else:
                    return (idx == 0 and self.hand.resources.cereal <= 1) or \
                           (idx == 2 and self.hand.resources.clay <= 1) or \
                           (idx == 3 and self.hand.resources.wood <= 1) or \
                           (idx == 4 and self.hand.resources.wool <= 1)

            # Split available resources into two tiers
            surplus = [i for i in available_indices if not is_essential(i)]
            essentials = [i for i in available_indices if is_essential(i)]

            # Pick the victim:
            # First, check surplus. If empty, check essentials.
            # In both cases, we pick the one with the LOWEST genetic weight.
            if surplus:
                target_idx = min(surplus, key=lambda i: genetic_map[i])
            else:
                target_idx = min(essentials, key=lambda i: genetic_map[i])

            self.hand.remove_material(target_idx, 1)

        return self.hand

    def on_moving_thief(self):
        # 1. Retrieve the DNA: Atomic resource weights
        w_cereal = self.params.get('weight_cereal', 0.5)
        w_mineral = self.params.get('weight_mineral', 0.5)
        w_clay = self.params.get('weight_clay', 0.5)
        w_wood = self.params.get('weight_wood', 0.5)
        w_wool = self.params.get('weight_wool', 0.5)
        
        genetic_weights = [w_cereal, w_mineral, w_clay, w_wood, w_wool]

        best_terrain = -1
        target_player = -1
        max_threat_score = -1

        # 2. Iterate through all hexes (0-18)
        for t_idx in range(19):
            terrain_data = self.board.terrain[t_idx]
            
            res_type = terrain_data.get('terrain_type', terrain_data.get('type', -1))
            
            # Skip desert or if the thief is already there
            if res_type == -1 or terrain_data.get('has_thief', False):
                continue
            
            material_value = genetic_weights[res_type] if 0 <= res_type < 5 else 0.1
            num = terrain_data.get('probability', terrain_data.get('number', 0))
            prob_score = self.get_probability_dots(num)

            # 3. Target Filtering: Check for enemies and avoid self-blocking
            enemies_on_hex = []
            is_self_present = False
            
            for node_idx in terrain_data['contacting_nodes']:
                p_id = self.board.nodes[node_idx]['player']
                
                # FIX: Use self.id instead of self.my_id
                if p_id == self.id:
                    is_self_present = True
                    break 
                elif p_id != -1:
                    enemies_on_hex.append(p_id)

            # 4. Scoring logic (Sabotage Vector)
            if not is_self_present and enemies_on_hex:
                threat_score = material_value * prob_score * len(enemies_on_hex)
                
                if threat_score > max_threat_score:
                    max_threat_score = threat_score
                    best_terrain = t_idx
                    target_player = enemies_on_hex[0]

        # 5. Emergency Fallback: If no ideal target is found, pick the desert or 0
        if best_terrain == -1:
            return {'terrain': 0, 'player': -1}

        return {'terrain': best_terrain, 'player': target_player}

    def on_turn_end(self):
        if len(self.development_cards_hand.hand) and random.randint(0, 1):
            return self.development_cards_hand.select_card(0)
        return None

    def on_commerce_phase(self):
        # 1. Play Monopoly if we recently gifted >3 resources of the same type
        if self.material_given_more_than_three is not None:
            if len(self.development_cards_hand.hand):
                for i in range(0, len(self.development_cards_hand.hand)):
                    if self.development_cards_hand.hand[i].effect == DevelopmentCardConstants.MONOPOLY_EFFECT:
                        return self.development_cards_hand.select_card(i)

        # --- STEP 1: Robber Anxiety (The 7-Card Threshold) ---
        w_anxiety = self.params.get('weight_robber_anxiety', 0.5)
        
        # Calculate total cards in hand
        total_cards = (self.hand.resources.cereal + self.hand.resources.mineral + 
                       self.hand.resources.clay + self.hand.resources.wood + self.hand.resources.wool)
        
        # The agent panics if it has more than 7 cards and the genetic roll succeeds
        is_anxious = (total_cards > 7) and (random.random() < w_anxiety)

        # --- STEP 2: Identify Goal using Genetics ---
        w_city = self.params.get('weight_of_city', 0.5)
        w_town = self.params.get('weight_town', 0.5)

        target_index = -1 
        target_is_city = False
        target_is_town = False
        
        # Calculate progress towards each building type (Percentage from 0.0 to 1.0)
        city_progress = (min(self.hand.resources.mineral, 3) + min(self.hand.resources.cereal, 2)) / 5.0
        town_progress = (min(self.hand.resources.wood, 1) + min(self.hand.resources.clay, 1) + 
                         min(self.hand.resources.cereal, 1) + min(self.hand.resources.wool, 1)) / 4.0

        # Apply genetic weights to calculate the absolute "Desire" for each goal
        city_score = city_progress * w_city
        town_score = town_progress * w_town

        # Decide objective based on the highest genetic desire
        if city_score > town_score and city_score > 0:
            target_is_city = True
            if self.hand.resources.mineral < 3:
                target_index = 1 # Need Mineral
            elif self.hand.resources.cereal < 2:
                target_index = 0 # Need Cereal
                
        elif town_score >= city_score and town_score > 0:
            target_is_town = True
            if self.hand.resources.wood == 0:
                target_index = 3 # Need Wood
            elif self.hand.resources.clay == 0:
                target_index = 2 # Need Clay
            elif self.hand.resources.cereal == 0:
                target_index = 0 # Need Cereal
            elif self.hand.resources.wool == 0:
                target_index = 4 # Need Wool

        # If we are panicking but don't have a specific target, we pick Mineral (most valuable)
        # just to force a trade and reduce our hand size!
        if is_anxious and target_index == -1:
            target_index = 1 

        if target_index == -1:
            return None

        # --- STEP 3: Identify Surplus and Protect Goal Resources ---
        my_res = [
            self.hand.resources.cereal,
            self.hand.resources.mineral,
            self.hand.resources.clay,
            self.hand.resources.wood,
            self.hand.resources.wool
        ]
        
        # We protect our resources ONLY if we are NOT panicking about the robber.
        # If we are anxious, survival comes first: we are willing to trade our savings to avoid losing half our hand.
        if not is_anxious:
            if target_is_city: 
                my_res[0] = 0 # Protect Cereal
                my_res[1] = 0 # Protect Mineral
                
            if target_is_town:
                my_res[0] = 0 # Protect Cereal
                my_res[2] = 0 # Protect Clay
                my_res[3] = 0 # Protect Wood
                my_res[4] = 0 # Protect Wool

        # Find the resource we have the most of (that isn't protected)
        surplus_amount = 0
        surplus_index = -1
        for i in range(5):
            if my_res[i] > surplus_amount and i != target_index:
                surplus_amount = my_res[i]
                surplus_index = i

        # --- STEP 4: Create the TradeOffer (Maritime or Panic Domestic) ---
        if surplus_index != -1:
            
            # 1. MARITIME TRADE (Priority & Panic Saver)
            exchange_rate = self.get_exchange_rate(surplus_index)
            
            # If we have enough for a bank/port trade, do it

    def on_build_phase(self, board_instance):
        self.board = board_instance
        
        w_city = self.params.get('city_weight', 0.5)
        w_town = self.params.get('town_weight', 0.5)

        # 1. Always check if we have development cards to play first
        #if len(self.development_cards_hand.hand) and random.randint(0, 1):
        #    return self.development_cards_hand.select_card(0)

        # --- STRATEGY: Hierarchy of Needs ---
        
        # 2. Priority: CITIES (Maximum ROI)
        # If we have resources for a city, build it on our most productive node
        if self.hand.resources.has_more(BuildConstants.CITY):
            valid_city_nodes = self.board.valid_city_nodes(self.id)
            if valid_city_nodes:
                # Find the node that gives us the highest score based on our DNA
                best_city_node = max(valid_city_nodes, key=lambda node_id: self.evaluate_node(node_id))
                return {'building': BuildConstants.CITY, 'node_id': best_city_node}
        
        # The agent is closed to city if he has 2 mineral and has all the cereal
        is_close_to_city = (self.hand.resources.mineral >= 2 and self.hand.resources.cereal >= 2)
        saving_for_city = is_close_to_city and (random.random() < w_city)
        #if he doesn't need to save for city, he can build a settlement if he has the resources
        # 3. Priority: SETTLEMENTS (TOWNS)
        # Expansion is key to increase resource diversity
        if not saving_for_city:
            if self.hand.resources.has_more(BuildConstants.TOWN):
                valid_town_nodes = self.board.valid_town_nodes(self.id)
                if valid_town_nodes:
                    best_town_node = max(valid_town_nodes, key=lambda node_id: self.evaluate_node(node_id))
                    return {'building': BuildConstants.TOWN, 'node_id': best_town_node}

        # 4. Priority: ROADS (Strategic Expansion)
        # Build roads only if we have the resources and a place to go
        # 3. PRIORITY: ROAD
        # Check if we should save for a TOWN (Wood >= 1 or Clay >= 1)
        is_close_to_town = (self.hand.resources.wood >= 1 and self.hand.resources.clay >= 1 and self.hand.resources.cereal >= 1)
        saving_for_town = is_close_to_town and (random.random() < w_town)

        if not saving_for_town and not saving_for_city:
            if self.hand.resources.has_more(BuildConstants.ROAD):
                valid_roads = self.board.valid_road_nodes(self.id)
                if valid_roads:
                    # Use a specific logic to choose the road that leads to the best future node
                    best_road = self.pick_best_expansion_road(valid_roads)
                    return {
                        'building': BuildConstants.ROAD,
                        'node_id': best_road['starting_node'],
                        'road_to': best_road['finishing_node']
                    }

        # 5. Last Resort: DEVELOPMENT CARDS
        # If we have leftovers and can't build on the board, buy a card
        if self.hand.resources.has_more(BuildConstants.CARD):
            return {'building': BuildConstants.CARD}

        return None

    def on_game_start(self, board_instance):
        self.board = board_instance

        # 1. Get all legal starting nodes
        possibilities = self.board.valid_starting_nodes()
        
        best_node_id = -1
        highest_score = -float('inf')

        # 2. Find the node with the highest strategic score
        for node_id in possibilities:
            node_score = self.evaluate_node(node_id)
            if node_score > highest_score:
                highest_score = node_score
                best_node_id = node_id
                
        # Fallback just in case (extremely rare)
        if best_node_id == -1:
            best_node_id = random.choice(possibilities)
            
        self.town_number += 1
        
        best_road_to_id = self.select_strategic_road(best_node_id)
            
        return best_node_id, best_road_to_id

    def on_year_of_plenty_card_use(self):
        # 1. Retrieve DNA weights
        w_city = self.params.get('city_weight', 0.5)
        w_town = self.params.get('town_weight', 0.5)

        # Index Mapping: 0:Cereal, 1:Mineral, 2:Clay, 3:Wood, 4:Wool
        city_req = [2, 3, 0, 0, 0]
        town_req = [1, 0, 1, 1, 1]
        
        current_res = [
            self.hand.resources.cereal, self.hand.resources.mineral,
            self.hand.resources.clay, self.hand.resources.wood, self.hand.resources.wool
        ]

        # 2. Calculate Desire based on progress
        city_prog = sum(min(current_res[i], city_req[i]) for i in range(5)) / 5.0
        town_prog = sum(min(current_res[i], town_req[i]) for i in range(5)) / 4.0
        
        # Decide goal based on highest weighted desire
        target_goal = city_req if (city_prog * w_city) >= (town_prog * w_town) else town_req
        
        missing_materials = []
        for i in range(5):
            needed = max(0, target_goal[i] - current_res[i])
            for _ in range(needed):
                missing_materials.append(i)

        # 3. Selection
        if len(missing_materials) >= 2:
            return {'material': missing_materials[0], 'material_2': missing_materials[1]}
        elif len(missing_materials) == 1:
            return {'material': missing_materials[0], 'material_2': 1} # Mineral as fallback
        else:
            return {'material': 1, 'material_2': 0} # Default to Ore and Wheat

    def on_monopoly_card_use(self):
        """
        Strategic Monopoly logic: calculates a score for each resource based on 
        internal needs (DNA) and enemy map abundance (Sabotage).
        """
        # 1. Retrieve DNA priorities and atomic weights
        # Using the standardized parameter names from your previous successful tests
        w_city = self.params.get('city_weight', 0.5)
        w_town = self.params.get('town_weight', 0.5)
        
        # Resource weights: 0:Cereal, 1:Mineral, 2:Clay, 3:Wood, 4:Wool
        w_res = [
            self.params.get('weight_cereal', 0.5),
            self.params.get('weight_mineral', 0.5),
            self.params.get('weight_clay', 0.5),
            self.params.get('weight_wood', 0.5),
            self.params.get('weight_wool', 0.5)
        ]

        # 2. Internal Necessity Score (Gap Analysis)
        current_res = [
            self.hand.resources.cereal, self.hand.resources.mineral,
            self.hand.resources.clay, self.hand.resources.wood, self.hand.resources.wool
        ]
        
        # Determine current priority goal based on weighted progress
        city_prog = (min(current_res[1], 3) + min(current_res[0], 2)) / 5.0
        town_prog = (min(current_res[3], 1) + min(current_res[2], 1) + 
                     min(current_res[0], 1) + min(current_res[4], 1)) / 4.0
        
        is_city_priority = (city_prog * w_city) > (town_prog * w_town)
        needed_counts = [2, 3, 0, 0, 0] if is_city_priority else [1, 0, 1, 1, 1]

        # 3. Enemy Map Presence Score (Sabotage Vector)
        # We analyze the board to estimate which resources opponents are likely holding
        enemy_production_potential = [0, 0, 0, 0, 0]
        
        for t_idx in range(19):
            terrain_data = self.board.terrain[t_idx]
            # Handle potential key differences ('type' or 'material')
            res_type = terrain_data.get('type', terrain_data.get('material', -1))
            
            # Skip non-resource hexes (Desert)
            if res_type == -1 or res_type >= 5: 
                continue 
            
            # Probability based on dice number
            num = terrain_data.get('number', 0)
            prob = 6 - abs(7 - num) if num != 0 else 0
            
            # Count enemy settlements/cities on this hex
            for node_idx in terrain_data['contacting_nodes']:
                p_id = self.board.nodes[node_idx]['player']
                if p_id != -1 and p_id != self.id:
                    # Higher probability of enemy possession if they have buildings on high-dot hexes
                    enemy_production_potential[res_type] += prob

        # 4. Final Scoring Function
        best_material = 1 # Default to Mineral
        max_score = -1

        for i in range(5):
            # Deficiency: How many units are missing for the current genetic goal?
            deficiency = max(0, needed_counts[i] - current_res[i])
            
            # Sabotage: How much impact will this have on opponents' hands?
            sabotage_value = enemy_production_potential[i]
            
            # SCORE = (Need * DNA_Weight) + (Enemy_Wealth * 0.5)
            # This ensures we pick what we need, but favor resources that hurt others more.
            score = (deficiency * (w_res[i] + 0.1)) + (sabotage_value * 0.5)
            
            if score > max_score:
                max_score = score
                best_material = i

        # Return the integer index of the chosen material (0-4)
        return best_material
   
    def on_road_building_card_use(self):
        # Retrieve all valid road placement options
        valid_roads = self.board.valid_road_nodes(self.id)
        if not valid_roads:
            return None

        # 1. Retrieve genetic parameters 
        w_div = self.params.get('weight_material_diversity', 0.4)
        w_block = self.params.get('weight_block_opponent', 0.4)
        w_exp = self.params.get('weight_road_expansion', 0.6)

        # 2. Identify materials already produced by our network 
        my_materials = set()
        for node in self.board.nodes:
            if node['player'] == self.id:
                for terrain_idx in node['contacting_terrain']:
                    t_type = self.board.terrain[terrain_idx].get('terrain_type', -1)
                    if t_type != -1: 
                        my_materials.add(t_type)

        # 3. Score each valid road individually
        scored_roads = []
        for road in valid_roads:
            score = 0
            target_node_id = road['finishing_node']
            target_node = self.board.nodes[target_node_id]

            # --- DIVERSITY SCORE ---
            # Check if this road leads to a new resource type [cite: 36, 167]
            for terrain_idx in target_node['contacting_terrain']:
                t_type = self.board.terrain[terrain_idx].get('terrain_type', -1)
                if t_type != -1 and t_type not in my_materials:
                    score += 2.5 * w_div 

            # --- BLOCKING SCORE ---
            # Check if this node is a potential spot for any opponent [cite: 44, 163]
            for p_id in range(4):
                if p_id != self.id:
                    # If an opponent could build here, blocking it is valuable
                    if target_node_id in self.board.valid_town_nodes(p_id):
                        score += 3.5 * w_block 

            # --- EXPANSION SCORE ---
            # Reward nodes that have more exit routes (centrality) [cite: 163]
            score += len(target_node['adjacent']) * w_exp
            
            scored_roads.append({'road': road, 'score': score})

        # Sort roads by score descending
        scored_roads.sort(key=lambda x: x['score'], reverse=True)

        # 4. Return the best two roads found 
        # Road 1 is the absolute best
        r1 = scored_roads[0]['road']
        
        # Road 2 is the second best (if available)
        if len(scored_roads) > 1:
            r2 = scored_roads[1]['road']
            return {
                'node_id': r1['starting_node'], 'road_to': r1['finishing_node'],
                'node_id_2': r2['starting_node'], 'road_to_2': r2['finishing_node']
            }
        else:
            return {
                'node_id': r1['starting_node'], 'road_to': r1['finishing_node'],
                'node_id_2': None, 'road_to_2': None
            }