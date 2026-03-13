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
    year_of_plenty_material_one = MaterialConstants.CEREAL
    year_of_plenty_material_two = MaterialConstants.MINERAL

    def __init__(self, agent_id, params=None):
        super().__init__(agent_id)
        self.params = params if params is not None else {
            'weight_wood': 6.568750632960386,
            'weight_clay': 4.66442338444247, 
            'weight_cereal': 5.305953437314006,
            'weight_mineral': 3.387812567714149, 
            'weight_wool': 3.1075015495780507, 
            'start_harbor_bonus': 16.344596254319285, 
            'road_strategy_future_node': 1.483589167480914, 
            'weight_harbor': 10.886618404383896, 
            'road_strategy_center_control': 2.481644577618161, 
            'city_weight': 0.16384590599575968, 
            'town_weight': 0.10901757499241133,
            'weight_robber_anxiety': 0.42347549120211586,
            'weight_material_diversity': 3.399179959408462,
            'weight_block_opponent': 1.8438071797096436, 
            'weight_road_expansion': 1.5011268520766052,
            'weight_dev_card_urgency': 0.31924169849761164,
            'weight_victory_near_threshold': 2.6455338265333177,
            'army_weight': 0.4522223194530034
        }

    #calculate the probability dots for a given dice roll
    def get_probability_dots(self, roll):
        if roll == 0 or roll == 7:
            return 0
        # The math trick to get dots: 6 - absolute distance from 7
        return 6 - abs(7 - roll)

    # Calculate the score of a node considering Resource Diversity
    def evaluate_node(self, node_id):
        score = 0.0
        
        w_wood = self.params.get('weight_wood', 1.0)
        w_clay = self.params.get('weight_clay', 1.0)
        w_cereal = self.params.get('weight_cereal', 1.0)
        w_mineral = self.params.get('weight_mineral', 1.0)
        w_wool = self.params.get('weight_wool', 0.8)
        w_harbor = self.params.get('start_harbor_bonus', 1.5)
        w_diversity = self.params.get('weight_material_diversity', 2.0)
        
        weights = {
            TerrainConstants.WOOD: w_wood,
            TerrainConstants.CLAY: w_clay,
            TerrainConstants.CEREAL: w_cereal,
            TerrainConstants.MINERAL: w_mineral,
            TerrainConstants.WOOL: w_wool,
            TerrainConstants.DESERT: 0.0
        }
        
        currently_produced_types = set()
        for node in self.board.nodes:
            if node['player'] == self.id:
                for terrain_idx in node['contacting_terrain']:
                    res_type = self.board.terrain[terrain_idx].get('terrain_type', -1)
                    if res_type != -1:
                        currently_produced_types.add(res_type)

        contacting_terrains = self.board.nodes[node_id]['contacting_terrain']
        
        for terrain_id in contacting_terrains:
            terrain_info = self.board.terrain[terrain_id]
            roll = terrain_info['probability']
            dots = self.get_probability_dots(roll)
            res_type = terrain_info['terrain_type']

            res_weight = weights.get(res_type, 0.0)
            
            #diversity resource logic
            diversity_bonus = 1.0
            if res_type not in currently_produced_types and res_type != TerrainConstants.DESERT:
                diversity_bonus += w_diversity
    
            score += (dots * res_weight * diversity_bonus)

        harbor_type = self.board.nodes[node_id]['harbor']
        if harbor_type != HarborConstants.NONE:
            score += w_harbor
            
        return score

    def select_strategic_road(self, start_node_id):

        possible_adjacent_nodes = self.board.nodes[start_node_id]['adjacent']
        
        w_future_node = self.params.get('road_strategy_future_node', 1.0)
        w_harbor = self.params.get('weight_harbor', 1.5)
        w_center = self.params.get('road_strategy_center_control', 0.5)
        
        best_road_destination = -1
        highest_score = -float('inf')
        
        for adj_node in possible_adjacent_nodes:
            path_score = 0.0

            connections = len(self.board.nodes[adj_node]['adjacent'])
            path_score += (connections * w_center)
            if self.board.nodes[adj_node]['harbor'] != HarborConstants.NONE:
                path_score += w_harbor
                
            dist_2_nodes = self.board.nodes[adj_node]['adjacent']
            best_dist_2_score = 0.0
            
            for d2_node in dist_2_nodes:
                if d2_node == start_node_id:
                    continue

                if self.board.nodes[d2_node]['player'] == -1 and self.board.empty_adjacent_nodes(d2_node):
                    future_score = self.evaluate_node(d2_node)
                    if future_score > best_dist_2_score:
                        best_dist_2_score = future_score

            path_score += (best_dist_2_score * w_future_node)

            if path_score > highest_score:
                highest_score = path_score
                best_road_destination = adj_node

        if best_road_destination == -1:
            import random
            best_road_destination = random.choice(possible_adjacent_nodes)
            
        return best_road_destination

    def pick_best_expansion_road(self, valid_roads):
        best_road = valid_roads[0]
        highest_potential = -float('inf')
        
        for road in valid_roads:
            target_node = road['finishing_node']
            potential_score = self.evaluate_node(target_node)
            for future_node in self.board.nodes[target_node]['adjacent']:
                if self.board.nodes[future_node]['player'] == -1:
                    potential_score += (self.evaluate_node(future_node) * 0.5)
            
            if potential_score > highest_potential:
                highest_potential = potential_score
                best_road = road
                
        return best_road

    def get_exchange_rate(self, material_index):
        best_rate = 4 
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
        
        for node_id, node in enumerate(self.board.nodes):
            
            if node['player'] == self.id:
                if node_id in harbors_map:
                    harbor_type = harbors_map[node_id]
                    if harbor_type == material_index:
                        return 2 
                    elif harbor_type == HarborConstants.ALL:
                        best_rate = 3
        return best_rate

    def on_trade_offer(self, board_instance, offer, player_id):
        
        opponent_gives = offer.gives 
        opponent_wants = offer.receives

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

        surplus_indices = []
        for i in range(5):
            if not is_protected[i] and my_res[i] > 0 and i != target_index:
                surplus_indices.append(i)

        opp_gives_arr = [opponent_gives.cereal, opponent_gives.mineral, opponent_gives.clay, opponent_gives.wood, opponent_gives.wool]
        opp_wants_arr = [opponent_wants.cereal, opponent_wants.mineral, opponent_wants.clay, opponent_wants.wood, opponent_wants.wool]

        takes_protected = any(opp_wants_arr[i] > 0 and is_protected[i] for i in range(5))
        gives_target = (target_index != -1 and opp_gives_arr[target_index] > 0)

        w_anxiety = self.params.get('weight_robber_anxiety', 0.5)
        total_cards = sum(my_res)
        cards_we_get = sum(opp_gives_arr)
        cards_we_give = sum(opp_wants_arr)
        new_total = total_cards + cards_we_get - cards_we_give

        if new_total > 7 and cards_we_get >= cards_we_give and random.random() < w_anxiety:
            return False

        if gives_target and not takes_protected:
            return True
            
        if target_index != -1 and len(surplus_indices) > 0:
            if takes_protected or not gives_target:
                gives_array = [0, 0, 0, 0, 0]
                receives_array = [0, 0, 0, 0, 0]
                
                primary_surplus = max(surplus_indices, key=lambda idx: my_res[idx])
                gives_array[primary_surplus] = 1
                for extra_idx in surplus_indices:
                    if extra_idx != primary_surplus:
                        gives_array[extra_idx] = 1
                        break 
                
                receives_array[target_index] = 1
                
                new_gives = Materials(gives_array[0], gives_array[1], gives_array[2], gives_array[3], gives_array[4])
                new_receives = Materials(receives_array[0], receives_array[1], receives_array[2], receives_array[3], receives_array[4])
                
                return TradeOffer(new_gives, new_receives)

        return False

    def on_having_more_than_7_materials_when_thief_is_called(self):
        w_cereal = self.params.get('weight_cereal', 0.5)
        w_mineral = self.params.get('weight_mineral', 0.5)
        w_clay = self.params.get('weight_clay', 0.5)
        w_wood = self.params.get('weight_wood', 0.5)
        w_wool = self.params.get('weight_wool', 0.5)

        w_city = self.params.get('city_weight', 0.5)
        w_town = self.params.get('town_weight', 0.5)

        genetic_map = {
            0: w_cereal,
            1: w_mineral,
            2: w_clay,
            3: w_wood,
            4: w_wool
        }
        city_progress = (min(self.hand.resources.mineral, 3) + min(self.hand.resources.cereal, 2)) / 5.0
        town_progress = (min(self.hand.resources.wood, 1) + min(self.hand.resources.clay, 1) + 
                         min(self.hand.resources.cereal, 1) + min(self.hand.resources.wool, 1)) / 4.0

        is_city_priority = (city_progress * w_city) > (town_progress * w_town)

        to_discard = self.hand.get_total() // 2
        for _ in range(to_discard):
            available_indices = []
            if self.hand.resources.cereal > 0: available_indices.append(0)
            if self.hand.resources.mineral > 0: available_indices.append(1)
            if self.hand.resources.clay > 0: available_indices.append(2)
            if self.hand.resources.wood > 0: available_indices.append(3)
            if self.hand.resources.wool > 0: available_indices.append(4)
            def is_essential(idx):
                if is_city_priority:
                    return (idx == 0 and self.hand.resources.cereal <= 2) or \
                           (idx == 1 and self.hand.resources.mineral <= 3)
                else:
                    return (idx == 0 and self.hand.resources.cereal <= 1) or \
                           (idx == 2 and self.hand.resources.clay <= 1) or \
                           (idx == 3 and self.hand.resources.wood <= 1) or \
                           (idx == 4 and self.hand.resources.wool <= 1)
            surplus = [i for i in available_indices if not is_essential(i)]
            essentials = [i for i in available_indices if is_essential(i)]
            if surplus:
                target_idx = min(surplus, key=lambda i: genetic_map[i])
            else:
                target_idx = min(essentials, key=lambda i: genetic_map[i])

            self.hand.remove_material(target_idx, 1)

        return self.hand

    def on_moving_thief(self):
        w_cereal = self.params.get('weight_cereal', 0.5)
        w_mineral = self.params.get('weight_mineral', 0.5)
        w_clay = self.params.get('weight_clay', 0.5)
        w_wood = self.params.get('weight_wood', 0.5)
        w_wool = self.params.get('weight_wool', 0.5)
        
        genetic_weights = [w_cereal, w_mineral, w_clay, w_wood, w_wool]

        best_terrain = -1
        target_player = -1
        max_threat_score = -1
        for t_idx in range(19):
            terrain_data = self.board.terrain[t_idx]
            
            res_type = terrain_data.get('terrain_type', terrain_data.get('type', -1))
            
            if res_type == -1 or terrain_data.get('has_thief', False):
                continue
            
            material_value = genetic_weights[res_type] if 0 <= res_type < 5 else 0.1
            num = terrain_data.get('probability', terrain_data.get('number', 0))
            prob_score = self.get_probability_dots(num)
            enemies_on_hex = []
            is_self_present = False
            
            for node_idx in terrain_data['contacting_nodes']:
                p_id = self.board.nodes[node_idx]['player']
                if p_id == self.id:
                    is_self_present = True
                    break 
                elif p_id != -1:
                    enemies_on_hex.append(p_id)

            if not is_self_present and enemies_on_hex:
                threat_score = material_value * prob_score * len(enemies_on_hex)
                
                if threat_score > max_threat_score:
                    max_threat_score = threat_score
                    best_terrain = t_idx
                    target_player = enemies_on_hex[0]
        if best_terrain == -1:
            return {'terrain': 0, 'player': -1}

        return {'terrain': best_terrain, 'player': target_player}

    def on_commerce_phase(self):
        if self.material_given_more_than_three is not None:
            if len(self.development_cards_hand.hand):
                for i in range(0, len(self.development_cards_hand.hand)):
                    if self.development_cards_hand.hand[i].effect == DevelopmentCardConstants.MONOPOLY_EFFECT:
                        return self.development_cards_hand.select_card(i)
        w_anxiety = self.params.get('weight_robber_anxiety', 0.5)

        total_cards = (self.hand.resources.cereal + self.hand.resources.mineral + 
                       self.hand.resources.clay + self.hand.resources.wood + self.hand.resources.wool)
        
        is_anxious = (total_cards > 7) and (random.random() < w_anxiety)

        w_city = self.params.get('city_weight', 0.5)
        w_town = self.params.get('town_weight', 0.5)

        target_index = -1 
        target_is_city = False
        target_is_town = False
        
        city_progress = (min(self.hand.resources.mineral, 3) + min(self.hand.resources.cereal, 2)) / 5.0
        town_progress = (min(self.hand.resources.wood, 1) + min(self.hand.resources.clay, 1) + 
                         min(self.hand.resources.cereal, 1) + min(self.hand.resources.wool, 1)) / 4.0

        city_score = city_progress * w_city
        town_score = town_progress * w_town

        if city_score > town_score and city_score > 0:
            target_is_city = True
            if self.hand.resources.mineral < 3:
                target_index = 1 
            elif self.hand.resources.cereal < 2:
                target_index = 0 
                
        elif town_score >= city_score and town_score > 0:
            target_is_town = True
            if self.hand.resources.wood == 0:
                target_index = 3 
            elif self.hand.resources.clay == 0:
                target_index = 2 
            elif self.hand.resources.cereal == 0:
                target_index = 0 
            elif self.hand.resources.wool == 0:
                target_index = 4 

        if is_anxious and target_index == -1:
            target_index = 1 

        if target_index == -1:
            return None

        my_res = [
            self.hand.resources.cereal,
            self.hand.resources.mineral,
            self.hand.resources.clay,
            self.hand.resources.wood,
            self.hand.resources.wool
        ]
        
        if not is_anxious:
            if target_is_city: 
                my_res[0] = 0 
                my_res[1] = 0 
                
            if target_is_town:
                my_res[0] = 0
                my_res[2] = 0 
                my_res[3] = 0 
                my_res[4] = 0 

        surplus_amount = 0
        surplus_index = -1
        for i in range(5):
            if my_res[i] > surplus_amount and i != target_index:
                surplus_amount = my_res[i]
                surplus_index = i

        if surplus_index != -1:

            exchange_rate = self.get_exchange_rate(surplus_index)

            if surplus_amount >= exchange_rate:

                gives = [0,0,0,0,0]
                receives = [0,0,0,0,0]

                gives[surplus_index] = exchange_rate
                receives[target_index] = 1

                return TradeOffer(
                    Materials(*gives),
                    Materials(*receives)
                )
            else:

                gives = [0,0,0,0,0]
                receives = [0,0,0,0,0]

                gives[surplus_index] = 1
                receives[target_index] = 1

                return TradeOffer(
                    Materials(*gives),
                    Materials(*receives)
                )
        return None

    def on_build_phase(self, board_instance):
        self.board = board_instance
        
        w_city = self.params.get('city_weight', 0.5)
        w_town = self.params.get('town_weight', 0.5)

        if self.hand.resources.has_more(BuildConstants.CITY):
            valid_city_nodes = self.board.valid_city_nodes(self.id)
            if valid_city_nodes:
                best_city_node = max(valid_city_nodes, key=lambda node_id: self.evaluate_node(node_id))
                return {'building': BuildConstants.CITY, 'node_id': best_city_node}
      
        is_close_to_city = (self.hand.resources.mineral >= 2 and self.hand.resources.cereal >= 2)
        saving_for_city = is_close_to_city and (random.random() < w_city)
        if not saving_for_city:
            if self.hand.resources.has_more(BuildConstants.TOWN):
                valid_town_nodes = self.board.valid_town_nodes(self.id)
                if valid_town_nodes:
                    best_town_node = max(valid_town_nodes, key=lambda node_id: self.evaluate_node(node_id))
                    return {'building': BuildConstants.TOWN, 'node_id': best_town_node}

        is_close_to_town = (self.hand.resources.wood >= 1 and self.hand.resources.clay >= 1 and self.hand.resources.cereal >= 1)
        saving_for_town = is_close_to_town and (random.random() < w_town)

        if not saving_for_town and not saving_for_city:
            if self.hand.resources.has_more(BuildConstants.ROAD):
                valid_roads = self.board.valid_road_nodes(self.id)
                if valid_roads:
                    best_road = self.pick_best_expansion_road(valid_roads)
                    return {
                        'building': BuildConstants.ROAD,
                        'node_id': best_road['starting_node'],
                        'road_to': best_road['finishing_node']
                    }
        if self.hand.resources.has_more(BuildConstants.CARD):
            return {'building': BuildConstants.CARD}

        return None


    def on_game_start(self, board_instance):

        self.board = board_instance
        possibilities = self.board.valid_starting_nodes()
        
        best_node_id = -1
        highest_score = -float('inf')
        for node_id in possibilities:
            node_score = self.evaluate_node(node_id)
            if node_score > highest_score:
                highest_score = node_score
                best_node_id = node_id
        if best_node_id == -1:
            best_node_id = random.choice(possibilities)
            
        self.town_number += 1
        
        best_road_to_id = self.select_strategic_road(best_node_id)
            
        return best_node_id, best_road_to_id

    def on_year_of_plenty_card_use(self):
        w_city = self.params.get('city_weight', 0.5)
        w_town = self.params.get('town_weight', 0.5)

        city_req = [2, 3, 0, 0, 0]
        town_req = [1, 0, 1, 1, 1]
        
        current_res = [
            self.hand.resources.cereal, self.hand.resources.mineral,
            self.hand.resources.clay, self.hand.resources.wood, self.hand.resources.wool
        ]

        city_prog = sum(min(current_res[i], city_req[i]) for i in range(5)) / 5.0
        town_prog = sum(min(current_res[i], town_req[i]) for i in range(5)) / 4.0

        target_goal = city_req if (city_prog * w_city) >= (town_prog * w_town) else town_req
        
        missing_materials = []
        for i in range(5):
            needed = max(0, target_goal[i] - current_res[i])
            for _ in range(needed):
                missing_materials.append(i)

        if len(missing_materials) >= 2:
            return {'material': missing_materials[0], 'material_2': missing_materials[1]}
        elif len(missing_materials) == 1:
            return {'material': missing_materials[0], 'material_2': 1}
        else:
            return {'material': 1, 'material_2': 0} 

    def on_monopoly_card_use(self):
        w_city = self.params.get('city_weight', 0.5)
        w_town = self.params.get('town_weight', 0.5)

        w_res = [
            self.params.get('weight_cereal', 0.5),
            self.params.get('weight_mineral', 0.5),
            self.params.get('weight_clay', 0.5),
            self.params.get('weight_wood', 0.5),
            self.params.get('weight_wool', 0.5)
        ]

        current_res = [
            self.hand.resources.cereal, self.hand.resources.mineral,
            self.hand.resources.clay, self.hand.resources.wood, self.hand.resources.wool
        ]

        city_prog = (min(current_res[1], 3) + min(current_res[0], 2)) / 5.0
        town_prog = (min(current_res[3], 1) + min(current_res[2], 1) + 
                     min(current_res[0], 1) + min(current_res[4], 1)) / 4.0
        
        is_city_priority = (city_prog * w_city) > (town_prog * w_town)
        needed_counts = [2, 3, 0, 0, 0] if is_city_priority else [1, 0, 1, 1, 1]

        enemy_production_potential = [0, 0, 0, 0, 0]
        
        for t_idx in range(19):
            terrain_data = self.board.terrain[t_idx]
            res_type = terrain_data.get('type', terrain_data.get('material', -1))
            if res_type == -1 or res_type >= 5: 
                continue 
            num = terrain_data.get('number', 0)
            prob = 6 - abs(7 - num) if num != 0 else 0
            
            for node_idx in terrain_data['contacting_nodes']:
                p_id = self.board.nodes[node_idx]['player']
                if p_id != -1 and p_id != self.id:
                    enemy_production_potential[res_type] += prob
        best_material = 1
        max_score = -1

        for i in range(5):
            deficiency = max(0, needed_counts[i] - current_res[i])
            sabotage_value = enemy_production_potential[i]
            score = (deficiency * (w_res[i] + 0.1)) + (sabotage_value * 0.5)
            
            if score > max_score:
                max_score = score
                best_material = i

        return best_material
   
    def on_road_building_card_use(self):
        valid_roads = self.board.valid_road_nodes(self.id)
        if not valid_roads:
            return None
        w_div = self.params.get('weight_material_diversity', 0.4)
        w_block = self.params.get('weight_block_opponent', 0.4)
        w_exp = self.params.get('weight_road_expansion', 0.6) 
        my_materials = set()
        for node in self.board.nodes:
            if node['player'] == self.id:
                for terrain_idx in node['contacting_terrain']:
                    t_type = self.board.terrain[terrain_idx].get('terrain_type', -1)
                    if t_type != -1: 
                        my_materials.add(t_type)
        scored_roads = []
        for road in valid_roads:
            score = 0
            target_node_id = road['finishing_node']
            target_node = self.board.nodes[target_node_id]

            for terrain_idx in target_node['contacting_terrain']:
                t_type = self.board.terrain[terrain_idx].get('terrain_type', -1)
                if t_type != -1 and t_type not in my_materials:
                    score += 2.5 * w_div 

            for p_id in range(4):
                if p_id != self.id:
                    if target_node_id in self.board.valid_town_nodes(p_id):
                        score += 3.5 * w_block 

            score += len(target_node['adjacent']) * w_exp
            
            scored_roads.append({'road': road, 'score': score})

        scored_roads.sort(key=lambda x: x['score'], reverse=True)

        r1 = scored_roads[0]['road']

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
        
    def on_turn_start(self):

        w_army = self.params.get('army_weight', 0.5)

        knight_cards = self.development_cards_hand.find_card_by_effect(DevelopmentCardConstants.KNIGHT_EFFECT)
        
        if len(knight_cards) == 0:
            return None
        if self.check_if_important_hex_is_blocked(w_army):
            return knight_cards[0]

        return None

    def check_if_important_hex_is_blocked(self, w_army):
    
        robber_hex_id = -1
        for t in self.board.terrain:
            if t['has_thief']:
                robber_hex_id = t['id']
                break
                
        if robber_hex_id == -1:
            return False 

        blocked_hex_data = self.board.terrain[robber_hex_id]

        prob_map = {2: 1, 12: 1, 3: 2, 11: 2, 4: 3, 10: 3, 5: 4, 9: 4, 6: 5, 8: 5}
        hex_pips = prob_map.get(blocked_hex_data['probability'], 0)
        
        our_production_multiplier = 0
        
        for node_id in blocked_hex_data['contacting_nodes']:
            node = self.board.nodes[node_id]
            if node['player'] == self.id:
                building_value = 2 if node['has_city'] else 1
                our_production_multiplier += building_value

        production_impact = hex_pips * our_production_multiplier

        base_threshold = 6.5
        effective_threshold = base_threshold - (w_army * 4.0)

        return production_impact >= effective_threshold

    def on_turn_end(self):

        if not self.development_cards_hand.hand:
            return None
        w_urgency = self.params.get('weight_dev_card_urgency', 0.3)
        w_victory_boost = self.params.get('weight_victory_near_threshold', 1.5)
        
        current_points = 0
        for node in self.board.nodes:
            if node['player'] == self.id:
                current_points += 2 if node.get('has_city', False) else 1
   
        if current_points >= 8:
            w_urgency *= w_victory_boost

        for i, card in enumerate(self.development_cards_hand.hand):
            if card.effect == DevelopmentCardConstants.VICTORY_POINT_EFFECT:
                continue
            if random.random() < w_urgency:
                return self.development_cards_hand.select_card(i)

        return None