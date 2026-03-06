import random

from Classes.Constants import HarborConstants, MaterialConstants, BuildConstants, TerrainConstants
from Classes.Materials import Materials
from Classes.TradeOffer import TradeOffer
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
        w_harbor = self.params.get('road_strategy_harbor_hunt', 1.5)
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

    def on_trade_offer(self, board_instance, offer=TradeOffer(), player_id=int):
        answer = random.randint(0, 2)
        if answer:
            if answer == 2:
                gives = Materials(random.randint(0, self.hand.resources.cereal),
                                  random.randint(0, self.hand.resources.mineral),
                                  random.randint(0, self.hand.resources.clay),
                                  random.randint(0, self.hand.resources.wood),
                                  random.randint(0, self.hand.resources.wool))
                receives = Materials(random.randint(0, self.hand.resources.cereal),
                                     random.randint(0, self.hand.resources.mineral),
                                     random.randint(0, self.hand.resources.clay),
                                     random.randint(0, self.hand.resources.wood),
                                     random.randint(0, self.hand.resources.wool))
                return TradeOffer(gives, receives)
            else:
                return True
        else:
            return False

    def on_turn_start(self):
        # self.development_cards_hand.add_card(DevelopmentCard(99, 0, 0))
        if len(self.development_cards_hand.hand) and random.randint(0, 1):
            return self.development_cards_hand.select_card(0)
        return None

    def on_having_more_than_7_materials_when_thief_is_called(self):
        return self.hand

    def on_moving_thief(self):
        terrain = random.randint(0, 18)
        player = -1
        for node in self.board.terrain[terrain]['contacting_nodes']:
            if self.board.nodes[node]['player'] != -1:
                player = self.board.nodes[node]['player']
        return {'terrain': terrain, 'player': player}

    def on_turn_end(self):
        if len(self.development_cards_hand.hand) and random.randint(0, 1):
            return self.development_cards_hand.select_card(0)
        return None

    def on_commerce_phase(self):
        if len(self.development_cards_hand.hand) and random.randint(0, 1):
            return self.development_cards_hand.select_card(0)

        answer = random.randint(0, 1)
        if answer:
            if self.hand.resources.cereal >= 4:
                return {'gives': MaterialConstants.CEREAL, 'receives': MaterialConstants.MINERAL}
            if self.hand.resources.mineral >= 4:
                return {'gives': MaterialConstants.MINERAL, 'receives': MaterialConstants.CEREAL}
            if self.hand.resources.clay >= 4:
                return {'gives': MaterialConstants.CLAY, 'receives': MaterialConstants.CEREAL}
            if self.hand.resources.wood >= 4:
                return {'gives': MaterialConstants.WOOD, 'receives': MaterialConstants.CEREAL}
            if self.hand.resources.wool >= 4:
                return {'gives': MaterialConstants.WOOL, 'receives': MaterialConstants.CEREAL}

            return None
        else:
            gives = Materials(random.randint(0, self.hand.resources.cereal),
                              random.randint(0, self.hand.resources.mineral),
                              random.randint(0, self.hand.resources.clay),
                              random.randint(0, self.hand.resources.wood),
                              random.randint(0, self.hand.resources.wool))
            receives = Materials(random.randint(0, self.hand.resources.cereal),
                                 random.randint(0, self.hand.resources.mineral),
                                 random.randint(0, self.hand.resources.clay),
                                 random.randint(0, self.hand.resources.wood),
                                 random.randint(0, self.hand.resources.wool))
            trade_offer = TradeOffer(gives, receives)
            return trade_offer

    def on_build_phase(self, board_instance):
        self.board = board_instance

        if len(self.development_cards_hand.hand) and random.randint(0, 1):
            return self.development_cards_hand.select_card(0)

        answer = random.randint(0, 2)
        # Pueblo / carretera
        if self.hand.resources.has_more(BuildConstants.TOWN) and answer == 0:
            answer = random.randint(0, 1)
            # Elegimos aleatoriamente si hacer un pueblo o una carretera
            if answer:
                valid_nodes = self.board.valid_town_nodes(self.id)
                if len(valid_nodes):
                    town_node = random.randint(0, len(valid_nodes) - 1)
                    return {'building': BuildConstants.TOWN, 'node_id': valid_nodes[town_node]}
            else:
                valid_nodes = self.board.valid_road_nodes(self.id)
                if len(valid_nodes):
                    road_node = random.randint(0, len(valid_nodes) - 1)
                    return {'building': BuildConstants.ROAD,
                            'node_id': valid_nodes[road_node]['starting_node'],
                            'road_to': valid_nodes[road_node]['finishing_node']}

        # Ciudad
        elif self.hand.resources.has_more(BuildConstants.CITY) and answer == 1:
            valid_nodes = self.board.valid_city_nodes(self.id)
            if len(valid_nodes):
                city_node = random.randint(0, len(valid_nodes) - 1)
                return {'building': BuildConstants.CITY, 'node_id': valid_nodes[city_node]}

        # Carta de desarrollo
        elif self.hand.resources.has_more(BuildConstants.CARD) and answer == 2:
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

    def on_monopoly_card_use(self):
        material = random.randint(0, 4)
        return material

    # noinspection DuplicatedCode
    def on_road_building_card_use(self):
        valid_nodes = self.board.valid_road_nodes(self.id)
        if len(valid_nodes) > 1:
            while True:
                road_node = random.randint(0, len(valid_nodes) - 1)
                road_node_2 = random.randint(0, len(valid_nodes) - 1)
                if road_node != road_node_2:
                    return {'node_id': valid_nodes[road_node]['starting_node'],
                            'road_to': valid_nodes[road_node]['finishing_node'],
                            'node_id_2': valid_nodes[road_node_2]['starting_node'],
                            'road_to_2': valid_nodes[road_node_2]['finishing_node'],
                            }
        elif len(valid_nodes) == 1:
            return {'node_id': valid_nodes[0]['starting_node'],
                    'road_to': valid_nodes[0]['finishing_node'],
                    'node_id_2': None,
                    'road_to_2': None,
                    }
        return None

    def on_year_of_plenty_card_use(self):
        material, material2 = random.randint(0, 4), random.randint(0, 4)
        return {'material': material, 'material_2': material2}
