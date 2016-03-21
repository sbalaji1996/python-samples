"""The ants module implements game logic for Ants Vs. SomeBees."""

import random
import sys
from ucb import main, interact, trace
from collections import OrderedDict


################
# Core Classes #
################


class Place:
    """A Place holds insects and has an exit to another Place."""

    def __init__(self, name, exit=None):
        """Create a Place with the given exit.

        name -- A string; the name of this Place.
        exit -- The Place reached by exiting this Place (may be None).
        """
        self.name = name
        self.exit = exit
        self.bees = []        # A list of Bees
        self.ant = None       # An Ant
        self.entrance = None  # A Place
        # Phase 1: Add an entrance to the exit

        if (self.exit != None):
            exit.entrance = self

    def add_insect(self, insect):
        """Add an Insect to this Place.

        There can be at most one Ant in a Place, unless exactly one of them is
        a BodyguardAnt (Phase 4), in which case there can be two. If add_insect
        tries to add more Ants than is allowed, an assertion error is raised.

        There can be any number of Bees in a Place.
        """
        if insect.is_ant:
            # Phase 4: Special handling for BodyguardAnt
    
            if (self.ant != None) and (self.ant.can_contain(insect)):
                self.ant.contain_ant(insect)
                insect.place = self
            elif (self.ant != None) and (insect.can_contain(self.ant)):
                insect.contain_ant(self.ant)
                self.ant = insect
                insect.place = self
            else:
                assert self.ant is None, 'Two ants in {0}'.format(self)
                self.ant = insect
        else:
            self.bees.append(insect)
        insect.place = self

    def remove_insect(self, insect):
        """Remove an Insect from this Place."""
        if insect.is_ant:
            assert self.ant == insect, '{0} is not in {1}'.format(insect, self)
            if insect.container is True:
                self.ant = insect.ant
            elif (isinstance(insect, QueenAnt)) and (not insect.imposter):
                return None
            else:
                self.ant = None
            # Phase 4: Special handling for BodyguardAnt and QueenAnt
        else:
            self.bees.remove(insect)

        insect.place = None

    def __str__(self):
        return self.name


class Insect:
    """An Insect, the base class of Ant and Bee, has armor and a Place."""

    is_ant = False
    watersafe = False

    def __init__(self, armor, place=None):
        """Create an Insect with an armor amount and a starting Place."""
        self.armor = armor
        self.place = place  # set by Place.add_insect and Place.remove_insect

    def reduce_armor(self, amount):
        """Reduce armor by amount, and remove the insect from its place if it
        has no armor remaining.

        >>> test_insect = Insect(5)
        >>> test_insect.reduce_armor(2)
        >>> test_insect.armor
        3
        """
        self.armor -= amount
        if self.armor <= 0:
            print('{0} ran out of armor and expired'.format(self))
            self.place.remove_insect(self)

    def action(self, colony):
        """The action performed each turn.

        colony -- The AntColony, used to access game state information.
        """

    def __repr__(self):
        cname = type(self).__name__
        return '{0}({1}, {2})'.format(cname, self.armor, self.place)


class Bee(Insect):
    """A Bee moves from place to place, following exits and stinging ants."""

    name = 'Bee'
    watersafe = True

    def sting(self, ant):
        """Attack an Ant, reducing the Ant's armor by 1."""
        ant.reduce_armor(1)

    def move_to(self, place):
        """Move from the Bee's current Place to a new Place."""
        self.place.remove_insect(self)
        place.add_insect(self)

    def blocked(self):
        """Return True if this Bee cannot advance to the next Place."""
        # Phase 3: Special handling for NinjaAnt

        if (self.place.ant is None) or (self.place.ant.blocks_path == False):
            return False
        return True

    def action(self, colony):
        """A Bee's action stings the Ant that blocks its exit if it is blocked,
        or moves to the exit of its current place otherwise.

        colony -- The AntColony, used to access game state information.
        """
        if self.blocked():
            self.sting(self.place.ant)
        elif self.place is not colony.hive and self.armor > 0:
            self.move_to(self.place.exit)


class Ant(Insect):
    """An Ant occupies a place and does work for the colony."""

    is_ant = True
    implemented = False  # Only implemented Ant classes should be instantiated
    damage = 0
    food_cost = 0
    blocks_path = True
    container = False

    def __init__(self, armor=1):
        """Create an Ant with an armor quantity."""
        Insect.__init__(self, armor)

    def can_contain(self, other):
        return (self.container) and (not other.container) and (not self.ant)


class HarvesterAnt(Ant):
    """HarvesterAnt produces 1 additional food per turn for the colony."""

    name = 'Harvester'
    implemented = True
    food_cost = 2

    def action(self, colony):
        """Produce 1 additional food for the colony.

        colony -- The AntColony, used to access game state information.
        """

        colony.food += 1
        return colony.food



def random_or_none(s):
    """Return a random element of sequence s, or return None if s is empty."""
    if s:
        return random.choice(s)


class ThrowerAnt(Ant):
    """ThrowerAnt throws a leaf each turn at the nearest Bee in its range."""

    name = 'Thrower'
    implemented = True
    damage = 1
    food_cost = 4


    max_range = 10
    min_range = 0

    def nearest_bee(self, hive):
        """Return the nearest Bee in a Place that is not the Hive, connected to
        the ThrowerAnt's Place by following entrances.

        This method returns None if there is no such Bee (or none in range).
        """

        i = 0
        nearest_place = self.place
        while (nearest_place.bees == []) and (nearest_place.entrance != hive):
            nearest_place = nearest_place.entrance
            i += 1
        if (nearest_place == hive):
            return None
        elif (self.min_range <= i) and (i <= self.max_range) and (nearest_place.bees != []):
            return random_or_none(nearest_place.bees)

    def throw_at(self, target):
        """Throw a leaf at the target Bee, reducing its armor."""
        if target is not None:
            target.reduce_armor(self.damage)

    def action(self, colony):
        """Throw a leaf at the nearest Bee in range."""
        self.throw_at(self.nearest_bee(colony.hive))


class Hive(Place):
    """The Place from which the Bees launch their assault.

    assault_plan -- An AssaultPlan; when & where bees enter the colony.
    """

    def __init__(self, assault_plan):
        self.name = 'Hive'
        self.assault_plan = assault_plan
        self.bees = []
        for bee in assault_plan.all_bees:
            self.add_insect(bee)
        # The following attributes are always None for a Hive
        self.entrance = None
        self.ant = None
        self.exit = None

    def strategy(self, colony):
        exits = [p for p in colony.places.values() if p.entrance is self]
        for bee in self.assault_plan.get(colony.time, []):
            bee.move_to(random.choice(exits))


class AntColony:
    """An ant collective that manages global game state and simulates time.

    Attributes:
    time -- elapsed time
    food -- the colony's available food total
    queen -- the place where the queen resides
    places -- A list of all places in the colony (including a Hive)
    bee_entrances -- A list of places that bees can enter
    """

    def __init__(self, strategy, hive, ant_types, create_places, food=2):
        """Create an AntColony for simulating a game.

        Arguments:
        strategy -- a function to deploy ants to places
        hive -- a Hive full of bees
        ant_types -- a list of ant constructors
        create_places -- a function that creates the set of places
        """
        self.time = 0
        self.food = food
        self.strategy = strategy
        self.hive = hive
        self.ant_types = OrderedDict((a.name, a) for a in ant_types)
        self.configure(hive, create_places)

    def configure(self, hive, create_places):
        """Configure the places in the colony."""
        self.queen = Place('AntQueen')
        self.places = OrderedDict()
        self.bee_entrances = []
        def register_place(place, is_bee_entrance):
            self.places[place.name] = place
            if is_bee_entrance:
                place.entrance = hive
                self.bee_entrances.append(place)
        register_place(self.hive, False)
        create_places(self.queen, register_place)

    def simulate(self):
        """Simulate an attack on the ant colony (i.e., play the game)."""
        while len(self.queen.bees) == 0 and len(self.bees) > 0:
            self.hive.strategy(self)    # Bees invade
            self.strategy(self)         # Ants deploy
            for ant in self.ants:       # Ants take actions
                if ant.armor > 0:
                    ant.action(self)
            for bee in self.bees:       # Bees take actions
                if bee.armor > 0:
                    bee.action(self)
            self.time += 1
        if len(self.queen.bees) > 0:
            print('The ant queen has perished. Please try again.')
        else:
            print('All bees are vanquished. You win!')

    def deploy_ant(self, place_name, ant_type_name):
        """Place an ant if enough food is available.

        This method is called by the current strategy to deploy ants.
        """
        constructor = self.ant_types[ant_type_name]
        if self.food < constructor.food_cost:
            print('Not enough food remains to place ' + ant_type_name)
        else:
            self.places[place_name].add_insect(constructor())
            self.food -= constructor.food_cost

    def remove_ant(self, place_name):
        """Remove an Ant from the Colony."""
        place = self.places[place_name]
        if place.ant is not None:
            place.remove_insect(place.ant)

    @property
    def ants(self):
        return [p.ant for p in self.places.values() if p.ant is not None]

    @property
    def bees(self):
        return [b for p in self.places.values() for b in p.bees]

    @property
    def insects(self):
        return self.ants + self.bees

    def __str__(self):
        status = ' (Food: {0}, Time: {1})'.format(self.food, self.time)
        return str([str(i) for i in self.ants + self.bees]) + status


def ant_types():
    """Return a list of all implemented Ant classes."""
    all_ant_types = []
    new_types = [Ant]
    while new_types:
        new_types = [t for c in new_types for t in c.__subclasses__()]
        all_ant_types.extend(new_types)
    return [t for t in all_ant_types if t.implemented]

def interactive_strategy(colony):
    """A strategy that starts an interactive session and lets the user make
    changes to the colony.

    For example, one might deploy a ThrowerAnt to the first tunnel by invoking
    colony.deploy_ant('tunnel_0_0', 'Thrower')
    """
    print('colony: ' + str(colony))
    msg = '<Control>-D (<Control>-Z <Enter> on Windows) completes a turn.\n'
    interact(msg)

def start_with_strategy(args, strategy):
    """Reads command-line arguments and starts a game with those options."""
    import argparse
    parser = argparse.ArgumentParser(description="Play Ants vs. SomeBees")
    parser.add_argument('-f', '--full', action='store_true',
                        help='loads a full layout and assault plan')
    parser.add_argument('-w', '--water', action='store_true',
                        help='loads a full layout with water')
    parser.add_argument('-i', '--insane', action='store_true',
                        help='loads a difficult assault plan')
    parser.add_argument('--food', type=int,
                        help='number of food to start with', default=2)
    args = parser.parse_args()

    assault_plan = make_test_assault_plan()
    layout = test_layout
    food = args.food
    if args.full:
        assault_plan = make_full_assault_plan()
        layout = dry_layout
    if args.water:
        layout = wet_layout
    if args.insane:
        assault_plan = make_insane_assault_plan()
    hive = Hive(assault_plan)
    AntColony(strategy, hive, ant_types(), layout, food).simulate()


###########
# Layouts #
###########

def wet_layout(queen, register_place, length=8, tunnels=3, moat_frequency=3):
    """Register a mix of wet and and dry places."""
    for tunnel in range(tunnels):
        exit = queen
        for step in range(length):
            if moat_frequency != 0 and (step + 1) % moat_frequency == 0:
                exit = Water('water_{0}_{1}'.format(tunnel, step), exit)
            else:
                exit = Place('tunnel_{0}_{1}'.format(tunnel, step), exit)
            register_place(exit, step == length - 1)

def dry_layout(queen, register_place, length=8, tunnels=3):
    """Register dry tunnels."""
    wet_layout(queen, register_place, length, tunnels, 0)

def test_layout(queen, register_place, length=8):
    """Register a single dry tunnel."""
    dry_layout(queen, register_place, length, 1)


#################
# Assault Plans #
#################


class AssaultPlan(dict):
    """The Bees' plan of attack for the Colony.  Attacks come in timed waves.

    An AssaultPlan is a dictionary from times (int) to waves (list of Bees).

    >>> AssaultPlan().add_wave(4, 2)
    {4: [Bee(3, None), Bee(3, None)]}
    """

    def __init__(self, bee_armor=3):
        self.bee_armor = bee_armor

    def add_wave(self, time, count):
        """Add a wave at time with count Bees that have the specified armor."""
        bees = [Bee(self.bee_armor) for _ in range(count)]
        self.setdefault(time, []).extend(bees)
        return self

    @property
    def all_bees(self):
        """Place all Bees in the hive and return the list of Bees."""
        return [bee for wave in self.values() for bee in wave]

def make_test_assault_plan():
    return AssaultPlan().add_wave(2, 1).add_wave(3, 1)

def make_full_assault_plan():
    plan = AssaultPlan().add_wave(2, 1)
    for time in range(3, 15, 2):
        plan.add_wave(time, 1)
    return plan.add_wave(15, 8)

def make_insane_assault_plan():
    plan = AssaultPlan(4).add_wave(1, 2)
    for time in range(3, 15):
        plan.add_wave(time, 1)
    return plan.add_wave(15, 20)

##############
# Extensions #
##############

class Water(Place):
    """Water is a place that can only hold 'watersafe' insects."""

    def add_insect(self, insect):
        """Add insect if it is watersafe, otherwise reduce its armor to 0."""
        print('added', insect, insect.watersafe)

        Place.add_insect(self, insect)
        if (insect.watersafe == False):
            insect.reduce_armor(insect.armor)

class FireAnt(Ant):
    """FireAnt cooks any Bee in its Place when it expires."""

    name = 'Fire'
    damage = 3
    implemented = False

    food_cost = 6

    def reduce_armor(self, amount):

        self.armor -= amount
        i = 0
        len_bees = len(self.place.bees)

        if (self.place.bees != []) and (self.armor <= 0):
            while (i < len_bees):
                if (self.place.bees[i].armor <= self.damage):
                    self.place.bees[i].reduce_armor(self.damage)
                    len_bees -= 1
                    i -= 1
                else:
                    self.place.bees[i].reduce_armor(self.damage)
                i += 1

class LongThrower(ThrowerAnt):
    """A ThrowerAnt that only throws leaves at Bees at least 4 places away."""

    name = 'Long'
    implemented = True
    food_cost = 3
    min_range = 4

    def nearest_bee(self, hive):
        i = 0
        nearest_place = self.place
        while (nearest_place.entrance != hive):
            nearest_place = nearest_place.entrance
            i += 1
            if (self.min_range <= i) and (nearest_place.bees != []):
                return random_or_none(nearest_place.bees)
            elif (nearest_place == hive):
                return None


class ShortThrower(ThrowerAnt):
    """A ThrowerAnt that only throws leaves at Bees less than 3 places away."""

    name = 'Short'
    implemented = True
    food_cost = 3
    max_range = 2

# The WallAnt class
class WallAnt(Ant):
    name = 'Wall'
    implemented = True
    food_cost = 4

    def __init__(self, armor = 4):
        Insect.__init__(self, armor)


class NinjaAnt(Ant):
    """NinjaAnt does not block the path and damages all bees in its place."""

    name = 'Ninja'
    damage = 1
    implemented = True
    blocks_path = False
    food_cost = 6

    def action(self, colony):

        i = 0
        len_bees = len(self.place.bees)

        if (len_bees != []):
            while (i < len_bees):
                if (self.place.bees[i].armor <= self.damage):
                    self.place.bees[i].reduce_armor(self.damage)
                    i -= 1
                    len_bees -= 1
                else:
                    self.place.bees[i].reduce_armor(self.damage)
                i += 1


# The ScubaThrower class
class ScubaThrower(ThrowerAnt):
    name = 'Scuba'
    implemented = True
    watersafe = True
    food_cost = 5


class HungryAnt(Ant):
    """HungryAnt will take three turns to digest a Bee in its place.
    While digesting, the HungryAnt can't eat another Bee.
    """
    name = 'Hungry'
    implemented = False
    time_to_digest = 3
    food_cost = 4

    def __init__(self):
        Ant.__init__(self)

        self.digest = 0

    def eat_bee(self, bee):

        bee.reduce_armor(bee.armor)

    def action(self, colony):

        if (self.digest > 0):
            self.digest -= 1
        else:
            if (self.place.bees != []):
                self.eat_bee(random_or_none(self.place.bees))
                self.digest = self.time_to_digest


class BodyguardAnt(Ant):
    """BodyguardAnt provides protection to other Ants."""
    name = 'Bodyguard'
    implemented = True
    food_cost = 4
    container = True

    def __init__(self):
        Ant.__init__(self, 2)
        self.ant = None  # The Ant hidden in this bodyguard

    def contain_ant(self, ant):
        self.ant = ant

    def action(self, colony):

        if (self.ant != None):
            self.ant.action(colony)

class LaserAnt(ThrowerAnt):
    """
    This class is optional. No tests are provided for this class.
    """
    name = 'Laser'
    distance_weakening = 0.3
    insects_shot_weakening = 0.5
    implemented = False

class QueenPlace:
    """A place that represents both places in which the bees find the queen.

    (1) The original colony queen location at the end of all tunnels, and
    (2) The place in which the QueenAnt resides.
    """
    def __init__(self, colony_queen, ant_queen):

        self.colony_queen = colony_queen
        self.ant_queen = ant_queen


    @property
    def bees(self):

        total = []
        if self.colony_queen.bees != []:
            total += self.colony_queen.bees
        if self.ant_queen.bees != []:
            total += self.ant_queen.bees

        return total

class QueenAnt(ScubaThrower):  # You should change this line
    """The Queen of the colony.  The game is over if a bee enters her place."""

    name = 'Queen'

    implemented = True
    exists = False
    food_cost = 6
    strength = []
    imposter = False

    def __init__(self, armor=1):
        super(ScubaThrower, self).__init__(armor)
        if not QueenAnt.exists:
            QueenAnt.exists = True
        else:
            self.imposter = True


    def action(self, colony):
        """A queen ant throws a leaf, but also doubles the damage of ants
        in her tunnel.

        Impostor queens do only one thing: reduce their own armor to 0.
        """
        if (not hasattr(colony.queen, 'QueenPlace')):
            colony.queen = QueenPlace(colony.queen, self.place)

        if (self.imposter == True):
            self.reduce_armor(self.armor)

        else:

            def strength_check(place):

                if (current_place.ant != None) and (current_place.ant not in self.strength):
                    current_place.ant.damage = current_place.ant.damage * 2
                    self.strength.append(current_place.ant)

                    if (current_place.ant.container == True) and (current_place.ant.ant) and (current_place.ant.ant not in self.strength):
                        current_place.ant.ant.damage = current_place.ant.ant.damage * 2
                        self.strength.append(current_place.ant.ant)

            current_place = self.place
            
            super(ScubaThrower, self).action(colony)

            if (current_place.ant.container == True) and (current_place.ant not in self.strength):
                current_place.ant.damage = current_place.ant.damage * 2
                self.strength.append(current_place.ant)

            while (current_place.entrance != None):
                current_place = current_place.entrance
                strength_check(current_place)

            current_place = self.place

            while (current_place.exit != None):
                current_place = current_place.exit
                strength_check(current_place)


class AntRemover(Ant):
    """Allows the player to remove ants from the board in the GUI."""

    name = 'Remover'
    implemented = False

    def __init__(self):
        Ant.__init__(self, 0)


##################
# Status Effects #
##################

def make_slow(action):
    """Return a new action method that calls action every other turn.

    action -- An action method of some Bee
    """



def make_stun(action):
    """Return a new action method that does nothing.

    action -- An action method of some Bee
    """

def apply_effect(effect, bee, duration):
    """Apply a status effect to a Bee that lasts for duration turns."""


class SlowThrower(ThrowerAnt):
    """ThrowerAnt that causes Slow on Bees."""




class StunThrower(ThrowerAnt):
    """ThrowerAnt that causes Stun on Bees."""
@main
def run(*args):
    start_with_strategy(args, interactive_strategy)
