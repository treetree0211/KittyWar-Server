import random

from logger import Logger
from network import Network, Flags
from enum import IntEnum
from threading import Lock


class Phases(IntEnum):

    SETUP = 0
    PRELUDE = 1
    ENACT_STRATS = 2
    POSTLUDE = 3


class Moves(IntEnum):

    @staticmethod
    def valid_move(move):
        return move in list(map(int, Moves))

    PURR = 0
    GUARD = 1
    SCRATCH = 2


class Player:

    def __init__(self, username, connection, cats):

        self.username = username
        self.connection = connection
        self.cats = cats

        self.__cat = None
        self.health = 0
        self.ddealt = 0
        self.ddodged = 0
        self.modifier = 1
        self.rability = 0

        self.chance_cards = []
        self.used_cards = []
        self.cooldowns = []

        self.move = None
        self.selected_chance = False
        self.ready = False

    @property
    def cat(self):
        return self.__cat

    @cat.setter
    def cat(self, cat):

        self.__cat = cat['cat_id']
        self.health = cat['health']

    @property
    def chance_card(self):

        last_index = len(self.chance_cards) - 1

        if last_index >= 0:
            return self.chance_cards[last_index]

        return None

    @property
    def used_card(self):

        last_index = len(self.used_cards) - 1

        if last_index >= 0:
            return self.used_cards[last_index]

        return None


class Match:

    def __init__(self):

        self.lock = Lock()
        self.match_valid = True

        self.phase = Phases.SETUP
        self.player1 = None
        self.player2 = None

    def process_request(self, username, request):

        if self.match_valid:

            player = self.get_player(username)
            phase_map[self.phase](player, request)

        return self.match_valid

    # Ends the match in an error
    def kill_match(self):

        self.match_valid = False
        self.alert_players(Flags.END_MATCH, 1, Flags.ERROR)

    def disconnect(self, username):

        Logger.log(username + " has disconnected from their match")
        Logger.log(username + " will be assessed with a loss")

        self.match_valid = False

        opponent = self.get_opponent(username)

        # The disconnected player gets a loss - notify the winning player
        response = Network.generate_responseb(Flags.END_MATCH, 1, Flags.SUCCESS)
        Network.send_data(opponent, response)

    # Phase before prelude for handling match preparation
    def setup(self, player, request):

        flag = request.flag
        if flag == Flags.SELECT_CAT:

            cat_id = Network.receive_data(player.connetion, request.size)
            valid_cat = self.select_cat(player, cat_id)

            if valid_cat:

                # Notify player selection was successful
                response = Network.generate_responseb(Flags.SELECT_CAT, Flags.ONE_BYTE, Flags.SUCCESS)
                Network.send_data(player.connection, response)

            else:

                # If not valid end match in an error
                Logger.log("Illegal cat selection from " +
                           player.username + ", ending match with error status")
                self.kill_match()

        elif flag == Flags.READY:

            # Set the player to ready and assign random ability
            players_ready = self.player_ready(player)

            Ability.random_ability(player)
            Chance.random_chances(player)

            # If both players are ready proceed to the next phase
            if players_ready:

                # Set and alert players of next phase
                self.next_phase(Phases.PRELUDE)

                # Do not proceed if someone did not select a cat but readied up
                if self.player1.cat and self.player2.cat:

                    self.post_setup()
                    self.gloria_prelude()

                else:
                    self.kill_match()

    # Notifies players about cats abilities and chances before game moves on
    def post_setup(self):

        # Send player2 player1's cat
        response = Network.generate_responseb(Flags.OP_CAT, Flags.ONE_BYTE, self.player1.cat)
        Network.send_data(self.player2.connection, response)

        # Send player1 player2's cat
        response = Network.generate_responseb(Flags.OP_CAT, Flags.ONE_BYTE, self.player2.cat)
        Network.send_data(self.player1.connection, response)

        # Send player1 their random ability
        response = Network.generate_responseb(Flags.GAIN_ABILITY, Flags.ONE_BYTE, self.player1.rability)
        Network.send_data(self.player1.connection, response)

        # Send player2 their random ability
        response = Network.generate_responseb(Flags.GAIN_ABILITY, Flags.ONE_BYTE, self.player2.rability)
        Network.send_data(self.player2.connection, response)

        # Send player1 their two random chance cards
        response = Network.generate_responseh(Flags.GAIN_CHANCES, Flags.TWO_BYTE)
        response.append(self.player1.chance_cards[0])
        response.append(self.player1.chance_cards[1])
        Network.send_data(self.player1.connection, response)

        # Send player2 their two random chance cards
        response = Network.generate_responseh(Flags.GAIN_CHANCES, Flags.TWO_BYTE)
        response.append(self.player2.chance_cards[0])
        response.append(self.player2.chance_cards[1])
        Network.send_data(self.player2.connection, response)

    # Activates any prelude passive abilities the players have
    def gloria_prelude(self):

        Logger.log("Prelude phase starting for " + self.player1.username +
                   ", " + self.player2.username)

        self.use_passive_ability(self.player1, self.player1.cat)
        self.use_passive_ability(self.player1, self.player1.rability)

        self.use_passive_ability(self.player2, self.player2.cat)
        self.use_passive_ability(self.player2, self.player2.rability)

    def prelude(self, player, request):

        flag = request.flag
        if flag == Flags.USE_ABILITY:
            self.use_active_ability(player, request)

        elif flag == Flags.READY:

            players_ready = self.player_ready(player)
            if players_ready:

                # Set and alert players of next phase
                self.next_phase(Phases.ENACT_STRATS)
                # self.gloria_enact_strats()

    def gloria_enact_strats(self):

        Logger.log("Enact Strategies phase starting for " + self.player1.username +
                   ", " + self.player2.username)

    def enact_strats(self, player, request):

        flag = request.flag
        if flag == Flags.SELECT_MOVE:

            move = Network.receive_data(player.connection, request.size)
            valid_move = self.select_move(player, move)

            response = Network.generate_responseh(Flags.SELECT_MOVE, Flags.ONE_BYTE)
            if valid_move:
                response.append(Flags.SUCCESS)
            else:
                response.append(Flags.FAILURE)

            Network.send_data(player.connection, response)

        elif flag == Flags.USE_CHANCE:

            chance = Network.receive_data(player.connection, request.size)

        elif flag == Flags.READY:

            players_ready = self.player_ready(player)
            if players_ready:
                pass

    def show_cards(self):
        pass

    def settle_strats(self):
        pass

    def gloria_postlude(self):
        pass

    def postlude(self):
        pass

    # Returns player one or two based on username
    def get_player(self, username):

        if self.player1.username == username:
            return self.player1
        else:
            return self.player2

    # Returns the player that does not have the specified username
    def get_opponent(self, username):

        if self.player1.username == username:
            return self.player2
        else:
            return self.player1

    # Sends a message to both players with or without a body
    def alert_players(self, flag, size=None, body=None):

        # Check if there is a body to send
        if size is None:
            response = Network.generate_responseh(flag, 0)

        else:
            response = Network.generate_responseb(flag, size, body)

        Network.send_data(self.player1.connection, response)
        Network.send_data(self.player2.connection, response)

    # Move onto the next phase specified and alert the players
    def next_phase(self, phase):

        self.reset_ready()
        self.phase = phase
        self.alert_players(Flags.NEXT_PHASE)

    # Set a player to ready and return whether both are ready or not
    def player_ready(self, player):

        player.ready = True
        return self.player1.ready and self.player2.ready

    # Sets both players to not ready
    def reset_ready(self):

        self.player1.ready = False
        self.player2.ready = False

    # Handles the user selecting a cat for the match
    @staticmethod
    def select_cat(player, cat_id):

        # Verify user can select the cat they have
        valid_cat = False
        for cat in player.cats:

            if cat['cat_id'] == cat_id:

                Logger.log(player.username + " has selected their cat" +
                           " - id: " + str(cat_id))

                player.cat = cat
                valid_cat = True
                break

        return valid_cat

    # Handles the user selecting a move
    @staticmethod
    def select_move(player, move):

        valid_move = Moves.valid_move(move)
        if valid_move:
            player.move = move

        return valid_move

    @staticmethod
    def select_chance(player, chance):

        if chance in Chance.chance_map:

            player.used_cards.append(chance)

    def use_passive_ability(self, player, ability_id):

        useable = not Ability.on_cooldown(player, ability_id)
        if useable and Ability.is_passive(ability_id):

            Logger.log(player.username +
                       " using passive ability - id: " + ability_id)

            ability_used = Ability.passive_map[ability_id](self.phase, player)
            if ability_used:

                opponent = self.get_opponent(player.username)
                Ability.network_responses(ability_id, player, opponent)

    def use_active_ability(self, player, request):

        ability_id = Network.receive_data(player.connection, request.size)

        # Verify the ability is useable - the player has the ability and not on cooldown
        useable = ability_id == player.cat or ability_id == player.rability
        useable = useable and not Ability.on_cooldown(player, ability_id)

        response = Network.generate_responseh(Flags.USE_ABILITY, Flags.ONE_BYTE)
        if useable and Ability.is_active(ability_id):

            Logger.log(player.username +
                       " using active ability - id: " + ability_id)

            ability_used = Ability.active_map[ability_id](self.phase, player)
            if ability_used:

                opponent = self.get_player(player.username)
                Ability.network_responses(ability_id, player, opponent)
                response.append(Flags.SUCCESS)

            else:
                response.append(Flags.FAILURE)

        else:
            response.append(Flags.FAILURE)

        Network.send_data(player.connection, response)

phase_map = {

    Phases.SETUP: Match.setup,
    Phases.PRELUDE: Match.prelude,
    Phases.ENACT_STRATS: Match.enact_strats,
    Phases.POSTLUDE: Match.postlude
}


class Abilities(IntEnum):

    Rejuvenation = 0
    Gentleman = 1
    Attacker = 6
    Critical = 7


class Ability:

    # Returns true if the ability is an active ability
    @staticmethod
    def is_active(ability_id):
        return ability_id in Ability.active_map

    # Returns true if the ability is a passive ability
    @staticmethod
    def is_passive(ability_id):
        return ability_id in Ability.passive_map

    # Checks if an ability is on cooldown
    @staticmethod
    def on_cooldown(player, ability_id):

        cd = False
        for cooldown in player.cooldowns:

            if cooldown[0] == ability_id:
                cd = True
                break

        return cd

    # Gives a random ability to the given player
    @staticmethod
    def random_ability(player):

        ability_id = random.randrange(6, 8)
        player.rability = ability_id

        Logger.log(player.username + " received random ability: " + str(ability_id))

    # Ability 00 - Rejuvenation
    # Gain 1 HP - Postlude - Cooldown: 2
    @staticmethod
    def a_ability00(phase, player):

        ability_used = False
        if phase == Phases.POSTLUDE:

            player.health += 1
            player.cooldowns.append((Abilities.Rejuvenation, 3))

            ability_used = True
            Logger.log(player.username + " used Rejuvenation +1 Health Point")

        return ability_used

    # Ability 07 - Critical Hit
    # Modifier x2 - PRELUDE - Cooldown: 2
    @staticmethod
    def a_ability07(phase, player):

        ability_used = False
        if phase == Phases.PRELUDE:

            player.modifier *= 2
            player.cooldowns.append((Abilities.Critical, 3))

            ability_used = True
            Logger.log(player.username + " used Critical Hit 2x Damage")

        return ability_used

    # Ability 01 - Gentleman
    # chance gained on condition - POSTLUDE
    # condition: damage dodged >= 2
    @staticmethod
    def p_ability01(phase, player):

        ability_used = False
        if phase == Phases.POSTLUDE:
            if player.ddodged >= 2:

                chance_card = random.randrange(0, 9)
                player.chance_cards.append(chance_card)

                ability_used = True
                Logger.log(player.username + " used Gentleman +1 Chance Card")

        return ability_used

    # Ability 06 - Attacker
    # chance gained on condition - POSTLUDE
    # condition: damage dealt >= 2
    @staticmethod
    def p_ability06(phase, player):

        ability_used = False
        if phase == Phases.POSTLUDE:
            if player.ddealt >= 2:

                chance_card = random.randrange(0, 9)
                player.chance_cards.append(chance_card)

                ability_used = True
                Logger.log(player.username + " used Attacker +1 Chance Card")

        return ability_used

    @staticmethod
    def network_responses(ability_id, player, opponent):

        player_response = None
        opponent_response = None

        # Notify player and opponent about 1 HP gain
        if ability_id == Abilities.Rejuvenation:

            player_response = Network.generate_responseb(
                Flags.GAIN_HP, Flags.ONE_BYTE, 1)

            opponent_response = Network.generate_responseb(
                Flags.OP_GAIN_HP, Flags.ONE_BYTE, 1)

        # Notify player and opponent about new damage modifier
        elif ability_id == Abilities.Critical:

            player_response = Network.generate_responseb(
                Flags.DMG_MODIFIED, Flags.ONE_BYTE, player.modifier)

            opponent_response = Network.generate_responseb(
                Flags.OP_DMG_MODIFIED, Flags.ONE_BYTE, player.modifier)

        # Notify player and opponent about 1 chance card gain
        elif ability_id == Abilities.Gentleman or \
                ability_id == Abilities.Attacker:

            player_response = Network.generate_responseb(
                Flags.GAIN_CHANCE, Flags.ONE_BYTE, player.chance_card)

            opponent_response = Network.generate_responseh(
                Flags.OP_GAIN_CHANCE, Flags.ZERO_BYTE)

        if player_response:
            Network.send_data(player.connection, player_response)

        if opponent_response:
            Network.send_data(opponent.connection, opponent_response)

    active_map = {

        Abilities.Rejuvenation: a_ability00,
        Abilities.Critical: a_ability07
    }

    passive_map = {

        Abilities.Gentleman: p_ability01,
        Abilities.Attacker: p_ability06
    }


class Chances(IntEnum):

    DOUBLE_PURR = 0
    GUARANTEED_PURR = 1
    PURR_DRAW = 2
    REVERSE_SCRATCH = 3
    GUARD_HEAL = 4
    GUARD_DRAW = 5
    NO_REVERSE = 6
    NO_GUARD = 7
    DOUBLE_SCRATCH = 8


class Chance:

    @staticmethod
    def random_chances(player):

        chance_card = random.randrange(0, 9)
        player.chance_cards.append(chance_card)

        chance_card = random.randrange(0, 9)
        player.chance_cards.append(chance_card)

    @staticmethod
    def has_chance(player, chance):
        return player.chance_cards.count(chance) != 0

    # Chance 00 - Double Purring
    # Gain 2 HP if you don't get attacked
    def chance_00(self, move, player):
        # TODO
        pass

    # Chance 01 - Guaranteed Purring
    # Gain 1 HP no matter what
    def chance_01(self, move, player):
        # TODO
        pass

    # Chance 02 - Purr and Draw
    # Gain 1 chance card if you heal
    def chance_02(self, move, player):
        # TODO
        pass

    # Chance 03 - Reverse Scratch
    # Reverse the damage
    def chance_03(self, move, player):
        # TODO
        pass

    # Chance 04 - Guard and Heal
    # Gain 1 HP if you dodge
    def chance_04(self, move, player):
        # TODO
        pass

    # Chance 05 - Guard and Draw
    # Gain 1 chance card if you dodge
    def chance_05(self, move, player):
        # TODO
        pass

    # Chance 06 - Cant't reverse
    # Can't reverse the damage
    def chance_06(self, move, player):
        # TODO
        pass

    # Chance 07 - Can't Guard
    # Scratch can't be dodged
    def chance_07(self, move, player):
        # TODO
        pass

    # Chance 08 - Double Scratch
    # Scratch twice - x2 Damage
    def chance_08(self, move, player):
        # TODO
        pass

    chance_map = {

        Chances.DOUBLE_PURR: chance_00,
        Chances.GUARANTEED_PURR: chance_01,
        Chances.PURR_DRAW: chance_02,
        Chances.REVERSE_SCRATCH: chance_03,
        Chances.GUARD_HEAL: chance_04,
        Chances.GUARD_DRAW: chance_05,
        Chances.NO_REVERSE: chance_06,
        Chances.NO_GUARD: chance_07,
        Chances.DOUBLE_SCRATCH: chance_08
    }
