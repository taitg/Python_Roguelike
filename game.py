#!/usr/bin/python
#
# libtcod python GAME
#
 
import libtcodpy as libtcod
import math
import textwrap
import shelve
 
#actual size of the window
SCREEN_WIDTH = 176
SCREEN_HEIGHT = 96 # ratio equal to 1920x1080 (screen resolution)
START_FULLSCREEN = True
 
# size of the world and the map (world = 3D grid of maps)
WORLD_WIDTH = 30
WORLD_HEIGHT = 30
WORLD_DEPTH = 10
MAP_WIDTH = 176
MAP_HEIGHT = 80

# field of view
FOV_ALGO = 2 # fov_shadow
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 24

# frames-per-second maximum
LIMIT_FPS = 30
DEFAULT_ANIMATION_SPEED = 6

# number of frames to wait after moving/attacking (smaller number = faster)
DEFAULT_SPEED = 4
DEFAULT_ATTACK_SPEED = 20
PLAYER_SPEED = 2
PLAYER_ATTACK_SPEED = 15

# initial player stats
PLAYER_STARTING_HP = 1000
PLAYER_STARTING_DEF = 0
PLAYER_STARTING_POWER = 2
 
# sizes and coordinates relevant for the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 16
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1
INVENTORY_WIDTH = 50
CHARACTER_SCREEN_WIDTH = 30
LEVEL_SCREEN_WIDTH = 40
INSPECT_SCREEN_WIDTH = 40
 
# parameters for dungeon generator
ROOM_MAX_SIZE = 24
ROOM_MIN_SIZE = 8
MAX_ROOMS = 16
MIN_CORNER_SIZE = 0
MAX_CORNER_SIZE = 2
TUNNEL_MIN_WIDTH = 4
TUNNEL_MAX_WIDTH = 7
MIN_COLUMN_SIZE = 2
MAX_COLUMN_SIZE = 5
COLUMNS_PER_ROOM = 2
COLUMN_CHANCE = 75 # percent
WALL_CHANCE = 75 # percent
ROCKS_PER_ROOM = 2
GRAVEL_PER_ROOM = 1
MIN_DIST_TO_STAIRS = 50
 
# spell values
HEAL_AMOUNT = 40
LIGHTNING_DAMAGE = 9000
LIGHTNING_RANGE = 16
CONFUSE_RANGE = 16
CONFUSE_NUM_TURNS = 10
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 25
FIRENOVA_RADIUS = 8
FIRENOVA_DAMAGE = 9000
 
# experience and leveling
LEVEL_UP_BASE = 2000000
LEVEL_UP_FACTOR = 150
 
color_dark_wall = libtcod.darkest_sepia  #libtcod.Color(0, 0, 100)
color_light_wall = libtcod.dark_sepia    #libtcod.Color(130, 110, 50)   # former color values
color_dark_ground = libtcod.darker_grey  #libtcod.Color(50, 50, 150)
color_light_ground = libtcod.grey        #libtcod.Color(200, 180, 50)

 
class Tile:
    #a tile of the map and its properties
    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked
	self.path = False
 
        #all tiles start unexplored
	#self.explored = True
        self.explored = False
 
        #by default, if a tile is blocked, it also blocks sight
        if block_sight is None: block_sight = blocked
        self.block_sight = block_sight
 
class Rect:
    #a rectangle on the map. used to characterize a room.
    def __init__(self, x, y, w, h):
	self.w = w
	self.h = h
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h
 
    def center(self):
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return (center_x, center_y)
 
    def intersect(self, other):
        #returns true if this rectangle intersects with another one
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)
 
class Object:
    #this is a generic object: the player, a monster, an item, the stairs...
    #it's always represented by a character on screen.
    def __init__(self, x, y, x2, y2, char, name, color, blocks=False, always_visible=False, fighter=None, ai=None, item=None, equipment=None, effect=None, speed=DEFAULT_SPEED):
        self.x = x
        self.y = y
	self.x2 = x2
	self.y2 = y2
        self.char = char
        self.name = name
        self.color = color
        self.blocks = blocks
        self.always_visible = always_visible
        self.fighter = fighter
	self.effect = effect
        self.speed = speed
        self.wait = 0
	self.spell_wait = 0
	self.attack_wait = 0
	self.menu_wait = 0
	self.destx = -1
	self.desty = -1

        if self.fighter:  #let the fighter component know who owns it
            self.fighter.owner = self
 
        self.ai = ai
        if self.ai:  #let the AI component know who owns it
            self.ai.owner = self
 
        self.item = item
        if self.item:  #let the Item component know who owns it
            self.item.owner = self
 
        self.equipment = equipment
        if self.equipment:  #let the Equipment component know who owns it
            self.equipment.owner = self
 
            #there must be an Item component for the Equipment component to work properly
            self.item = Item()
            self.item.owner = self

	self.effect = effect
	if self.effect:
	    self.effect.owner = self
 
    def move(self, dx, dy):
        #move by the given amount, if the destination is not blocked
        if not is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy
	self.wait = self.speed
 
    def move_towards(self, target_x, target_y):
        #vector from this object to the target, and distance
        distx = target_x - self.x
        disty = target_y - self.y
        distance = math.sqrt(distx ** 2 + disty ** 2)
 
        #normalize it to length 1 (preserving direction), then round it and
        #convert to integer so the movement is restricted to the map grid
        dx = int(round(distx / distance))
        dy = int(round(disty / distance))

	# check if having corner issues and resolve, move if not
        if is_blocked(self.x + dx, self.y + dy):
            if distx != 0 and disty != 0:
                self.move(distx / abs(distx), 0)
                self.move(0, disty / abs(disty))
	    elif self != player: # swarming enemies
		self.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))	
        else:
            self.move(dx, dy)  


    def click_action(self):
	global mouse, fov_recompute

        if mouse.lbutton:
	    (x, y) = (mouse.cx, mouse.cy)
	    if x is not None and x > 0 and x < MAP_WIDTH - 1 and y is not None and y > 0 and y < MAP_HEIGHT - 1:
		# if there is a destination and you are not there then go towards it
		if self.x != x or self.y != y:
	   	    self.move_towards(x, y)
	    	    fov_recompute = True
	   	    effect_component = Effect('+','+', ' ', 1, True)
                    click_effect = Object(x, y, x, y, '+', '', libtcod.silver, always_visible=True, effect=effect_component)
                    objects.append(click_effect)

	if mouse.rbutton_pressed:
	    (x, y) = (mouse.cx, mouse.cy)	
	    if x is not None:
		# inspect what the player right clicked on  
		inspect(x, y)

    def teleport(self, x, y):
	global fov_recompute

	good_location = False
	while not good_location:
	    if x == -1: # get random coordinates if -1 is given
	        new_x = libtcod.random_get_int(0, 1, MAP_WIDTH - 1)
	    else:
		new_x = x
	    if y == -1:
	        new_y = libtcod.random_get_int(0, 1, MAP_HEIGHT - 1)
	    else:
		new_y = y
	    if not map[new_x][new_y].blocked:
		good_location = True
	    elif x != -1 or y != -1:
		break

	if good_location:
    	    for ix in range(-1,2): # make effect at starting location
		for iy in range(-1,2):
		    if not map[self.x + ix][self.y + iy].blocked and self.distance(self.x + ix, self.y + iy) <= 1:
    	    	        effect_component = Effect('*','.', ' ', 3, True)
    	    	        teleport_effect = Object(self.x + ix, self.y + iy, self.x + ix, self.y + iy, '*', 'smoke', libtcod.lightest_grey, always_visible=False, effect=effect_component)
    	    	        objects.append(teleport_effect)

	    self.move(new_x - self.x, new_y - self.y) # do the actual teleport
	    if self.name == 'player':
	        fov_recompute = True
	    self.spell_wait = 5

    	    for ix in range(-1, 2): # make effect at ending location
		for iy in range(-1, 2):
		    if not map[new_x + ix][new_y + iy].blocked and self.distance(new_x + ix, new_y + iy) <= 1:
    	    	        effect_component = Effect('*','.', ' ', 3, True)
    	    	        teleport_effect = Object(new_x + ix, new_y + iy, new_x + ix, new_y + iy, '*', 'smoke', libtcod.lightest_grey, always_visible=False, effect=effect_component)
    	    	        objects.append(teleport_effect)
	else:
	    msgbox('You cannot teleport to that location')

 
    def distance_to(self, other):
        #return the distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)
 
    def distance(self, x, y):
        #return the distance to some coordinates
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)
 
    def send_to_back(self):
        #make this object be drawn first, so all others appear above it if they're in the same tile.
        global objects
        objects.remove(self)
        objects.insert(0, self)
 
    def draw(self):
        #only show if it's visible to the player; or it's set to "always visible" and on an explored tile
        if (libtcod.map_is_in_fov(fov_map, self.x, self.y) or (self.always_visible and map[self.x][self.y].explored)):
            #set the color and then draw the character that represents this object at its position
            libtcod.console_set_default_foreground(con, self.color)
            libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)
 
    def clear(self):
        #erase the character that represents this object
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)


class Effect:
    def __init__(self, char1, char2, charf, rotations, sendtoback=True, speed=DEFAULT_ANIMATION_SPEED):
	self.char1 = char1
	self.char2 = char2
	self.charf = charf
	self.rotations = rotations
	self.speed = speed
	self.sendtoback = sendtoback
	self.wait = 0
	self.finished = False

    def animate(self):

	if self.sendtoback:
	    self.owner.send_to_back()

	if self.rotations > 0:
	    if self.owner.char == self.char1:
                self.owner.char = self.char2
	    else:
                self.owner.char = self.char1
	    self.rotations -= 1
	elif self.rotations == 0:
	    self.owner.char = self.charf
	    self.owner.send_to_back()
	    self.finished = True
	elif self.rotations == -1:
	    if self.owner.char == self.char1:
                self.owner.char = self.char2
	    else:
                self.owner.char = self.char1
	#elif self.rotations == -2:
	    #self.owner.send_to_back()

	self.wait = self.speed
 
 
class Fighter:
    #combat-related properties and methods (monster, player, NPC).
    def __init__(self, hp, defense, power, xp, death_function=None, attack_speed=DEFAULT_ATTACK_SPEED):
        self.base_max_hp = hp
        self.hp = hp
        self.base_defense = defense
        self.base_power = power
        self.xp = xp
        self.death_function = death_function
        self.attack_speed = attack_speed
 
    @property
    def power(self):  #return actual power, by summing up the bonuses from all equipped items
        bonus = sum(equipment.power_bonus for equipment in get_all_equipped(self.owner))
        return self.base_power + bonus
 
    @property
    def defense(self):  #return actual defense, by summing up the bonuses from all equipped items
        bonus = sum(equipment.defense_bonus for equipment in get_all_equipped(self.owner))
        return self.base_defense + bonus
 
    @property
    def max_hp(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
        return self.base_max_hp + bonus
 
    def attack(self, target):
        #a simple formula for attack damage
        damage = self.power - target.fighter.defense
 
        if damage > 0:
            #make the target take some damage
	    if libtcod.map_is_in_fov(fov_map, self.owner.x, self.owner.y):
                message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.')
            target.fighter.take_damage(damage, self.owner.name)
        else:
	    if libtcod.map_is_in_fov(fov_map, self.owner.x, self.owner.y):
                message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!')
	self.owner.attack_wait = self.attack_speed
 
    def take_damage(self, damage, dealer):
	global damage_effect
        #apply damage if possible
        if damage > 0:
            self.hp -= damage
	    effect_component = Effect('X','X', ' ', 1, False, speed=2)
            damage_effect = Object(self.owner.x, self.owner.y, self.owner.x, self.owner.y, 'X', 'damage', libtcod.red, always_visible=False, effect=effect_component)
            objects.append(damage_effect)
 
            #check for death. if there's a death function, call it
            if self.hp <= 0:
                function = self.death_function
                if function is not None:
                    function(self.owner, dealer)
 
 
    def heal(self, amount):
        #heal by the given amount, without going over the maximum
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp


class projectile_ai():
    def __init__(self, ai_type, dx, dy, hits_player):
	self.ai_type = ai_type
	self.dx = dx
	self.dy = dy
	self.hits_player = hits_player
	self.expended = False

    def take_turn(self):
        projectile = self.owner

	if self.ai_type == 'arrow':
	    collided = None
	    for object in objects:
		if projectile.distance_to(object) <= 1 and object.fighter:
		    if self.hits_player:
		        collided = object
		    elif object != player:
			collided = object

	    if not self.expended:
	        if collided is None:
	            self.owner.move(self.dx, self.dy)
	        else:
		    projectile.effect.rotations = 0
		    self.expended = True
		    message('The arrow hit the ' + collided.name + ' for ' + str(player.fighter.power) + ' hit points.', libtcod.orange)
                    collided.fighter.take_damage(player.fighter.power, 'player')


class monster_ai():
    def __init__(self, ai_type):
	self.ai_type = ai_type

    def take_turn(self):
        monster = self.owner

	if self.ai_type == 'basic':
            #a basic monster takes its turn. if you can see it, it can see you
            if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):

                #move towards player if far away
                if monster.distance_to(player) >= 2:
                    monster.move_towards(player.x, player.y)
		    # set destination
		    monster.destx = player.x
		    monster.desty = player.y
 
                #close enough, attack! (if the player is still alive.)
                elif player.fighter.hp > 0:
                    monster.fighter.attack(player)

	    # if not in FOV keep heading to previous destination
	    elif monster.destx != -1 and monster.desty != -1:
	        if monster.x != monster.destx or monster.y != monster.desty:
	            monster.move_towards(monster.destx, monster.desty)
	        else:
		    # reset destination when it gets there
		    monster.destx = -1
		    monster.desty = -1

	    # if not in FOV and no destination just move randomly
	    else:
	        if libtcod.random_get_int(0, 0, 2) == 0:
	            monster.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))


	elif self.ai_type == 'passive':
	    if monster.distance_to(player) >= 2: # if player is not adjacent, 1 in 3 chance of doing something on its turn
	        if libtcod.random_get_int(0, 0, 2) == 0:
	            monster.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
	    elif player.fighter.hp > 0:
                monster.fighter.attack(player)


	elif self.ai_type == 'bat':
	    if monster.distance_to(player) >= 2: # if player is not adjacent, 1 in 3 chance of doing something on its turn
	        if libtcod.random_get_int(0, 0, 2) == 0:

		    stuck_in_web = False
		    for object in objects: # check if bat got stuck in a web, if so change color to web color
			if object.name == 'spider web' and monster.x == object.x and monster.y == object.y:
			    monster.color = libtcod.lighter_grey
			    stuck_in_web = True

		    if not stuck_in_web: # if not move randomly and change color to normal
			monster.color = libtcod.black
	                monster.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))

	    elif player.fighter.hp > 0:
                monster.fighter.attack(player)


	if self.ai_type == 'rat':
	    stuck_in_web = False
	    for object in objects: # check if bat got stuck in a web, if so change color to web color
		if object.name == 'spider web' and monster.x == object.x and monster.y == object.y:
		    monster.color = libtcod.lighter_grey
		    stuck_in_web = True

            if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):

                #move towards player if far away
                if monster.distance_to(player) >= 2 and monster.distance_to(player) < 8:
	    	    if not stuck_in_web:
			monster.color = libtcod.darker_sepia
                        monster.move_towards(player.x, player.y)
		    # set destination
		    monster.destx = player.x
		    monster.desty = player.y
 
                #close enough, attack! (if the player is still alive.)
                elif player.fighter.hp > 0 and monster.distance_to(player) <= 2:
                    monster.fighter.attack(player)

		else:
		    target = None
		    for object in objects: # see if there are any bats nearby, if so target the closest one
			if object.name == 'spider' and monster.distance_to(object) < 16:
			    if target is not None:
				if monster.distance_to(object) <= monster.distance_to(target):
			    	    target = object
			    else:
				target = object

		    if target is not None: # move towards or attack target if it exists
			if monster.distance_to(target) >= 2:
	    		    if not stuck_in_web:
				monster.color = libtcod.darker_sepia
			        monster.move_towards(target.x, target.y)
			elif target.fighter.hp > 0:
                   	    monster.fighter.attack(target)

	            else:
	                if libtcod.random_get_int(0, 0, 4) == 0:
	    		    if not stuck_in_web:
		                monster.color = libtcod.darker_sepia
	                        monster.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))

	    # if not in FOV keep heading to previous destination
	    elif monster.destx != -1 and monster.desty != -1:
	        if monster.x != monster.destx or monster.y != monster.desty:
	            monster.move_towards(monster.destx, monster.desty)
	        else:
		    # reset destination when it gets there
		    monster.destx = -1
		    monster.desty = -1

	    # if not in FOV and no destination just move randomly
	    else:
	        if libtcod.random_get_int(0, 0, 2) == 0:
	            monster.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))


	elif self.ai_type == 'spider':
	    if monster.distance_to(player) >= 2:
	        if libtcod.random_get_int(0, 0, 4) == 0: # if player is not adjacent, 1 in 5 chance of doing something on its turn

		    target = None
		    for object in objects: # see if there are any bats nearby, if so target the closest one
			if object.name == 'bat' and monster.distance_to(object) < 10:
			    if target is not None:
				if monster.distance_to(object) <= monster.distance_to(target):
			    	    target = object
			    else:
				target = object

		    if target is not None: # move towards or attack target if it exists
			if monster.distance_to(target) >= 2:
			    monster.move_towards(target.x, target.y)
			elif target.fighter.hp > 0:
                   	    monster.fighter.attack(target)
			    
		    else: # move randomly if no target
		        if map[monster.x - 1][monster.y].blocked or map[monster.x + 1][monster.y].blocked: # prefer walls
	                    monster.move(0, libtcod.random_get_int(0, -1, 1))
		        elif map[monster.x][monster.y - 1].blocked or map[monster.x][monster.y + 1].blocked:
	                    monster.move(libtcod.random_get_int(0, -1, 1), 0)
		        else:
	                    monster.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))

		    # choose a random "web shape"
		    if libtcod.random_get_int(0, 0, 3) == 0:
		        web_style = 185
		    else:
		        web_style = libtcod.random_get_int(0, 202, 204)

		    # make the web on a random spot adjacent to the spider
		    x = libtcod.random_get_int(0, self.owner.x - 1, self.owner.x + 1)
		    y = libtcod.random_get_int(0, self.owner.y - 1, self.owner.y + 1)
		    effect_component = Effect(web_style, web_style, ' ', 60, False)
                    web_effect = Object(x, y, x, y, '#', 'spider web', libtcod.lighter_grey, always_visible=False, effect=effect_component)
                    objects.append(web_effect)
		    web_effect.send_to_back()

	    elif player.fighter.hp > 0: # attack if next to the player
                monster.fighter.attack(player)

 
class ConfusedMonster:
    #AI for a temporarily confused monster (reverts to previous AI after a while).
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns
 
    def take_turn(self):
        if self.num_turns > 0:  #still confused...
            #move in a random direction, and decrease the number of turns confused
            self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
            self.num_turns -= 1
 
        else:  #restore the previous AI (this one will be deleted because it's not referenced anymore)
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)

class Item:
    #an item that can be picked up and used.
    def __init__(self, use_function=None):
        self.use_function = use_function
 
    def pick_up(self):
        #add to the player's inventory and remove from the map
        if len(inventory) >= 26:
            message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.red)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '!', libtcod.green)
 
            #special case: automatically equip, if the corresponding equipment slot is unused
            equipment = self.owner.equipment
            if equipment and get_equipped_in_slot(equipment.slot) is None:
                equipment.equip()
 
    def drop(self):
        #special case: if the object has the Equipment component, dequip it before dropping
        if self.owner.equipment:
            self.owner.equipment.dequip()
 
        #add to the map and remove from the player's inventory. also, place it at the player's coordinates
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '.', libtcod.yellow)
 
    def use(self):
        #special case: if the object has the Equipment component, the "use" action is to equip/dequip
        if self.owner.equipment:
            self.owner.equipment.toggle_equip()
            return
 
        #just call the "use_function" if it is defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner)  #destroy after use, unless it was cancelled for some reason
 
class Equipment:
    #an object that can be equipped, yielding bonuses. automatically adds the Item component.
    def __init__(self, slot, power_bonus=0, defense_bonus=0, max_hp_bonus=0):
        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus
        self.max_hp_bonus = max_hp_bonus
 
        self.slot = slot
        self.is_equipped = False
 
    def toggle_equip(self):  #toggle equip/dequip status
        if self.is_equipped:
            self.dequip()
        else:
            self.equip()
 
    def equip(self):
        #if the slot is already being used, dequip whatever is there first
        old_equipment = get_equipped_in_slot(self.slot)
        if old_equipment is not None:
            old_equipment.dequip()
 
        #equip object and show a message about it
        self.is_equipped = True
        message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', libtcod.light_green)
 
    def dequip(self):
        #dequip object and show a message about it
        if not self.is_equipped: return
        self.is_equipped = False
        message('Dequipped ' + self.owner.name + ' from ' + self.slot + '.', libtcod.light_yellow)
 
 
def get_equipped_in_slot(slot):  #returns the equipment in a slot, or None if it's empty
    for obj in inventory:
        if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
            return obj.equipment
    return None
 
def get_all_equipped(obj):  #returns a list of equipped items
    if obj == player:
        equipped_list = []
        for item in inventory:
            if item.equipment and item.equipment.is_equipped:
                equipped_list.append(item.equipment)
        return equipped_list
    else:
        return []  #other objects have no equipment
 
 
def is_blocked(x, y):
    #first test the map tile
    if map[x][y].blocked:
        return True
 
    #now check for any blocking objects
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True
 
    return False
 
def create_room(room):
    global map
    #go through the tiles in the rectangle and make them passable
    corner = libtcod.random_get_int(0, MIN_CORNER_SIZE, MAX_CORNER_SIZE)
    for ix in range(room.x1 + 1, room.x2):
        for iy in range(room.y1 + 1, room.y2):
	    if not ((ix <= room.x1 + corner or ix >= room.x2 - corner) and (iy <= room.y1 + corner or iy >= room.y2 - corner)):
                map[ix][iy].blocked = False
                map[ix][iy].block_sight = False

 
def create_h_tunnel(x1, x2, y, width):
    global map
    #horizontal tunnel. min() and max() are used in case x1>x2
    for ix in range(min(x1, x2), max(x1, x2) + 1):
	for iy in range(y - width/2, y + width/2 + 1):
            map[ix][iy].blocked = False
            map[ix][iy].block_sight = False
	    map[ix][iy].path = True
 
def create_v_tunnel(y1, y2, x, width):
    global map
    #vertical tunnel
    for iy in range(min(y1, y2), max(y1, y2) + 1):
	for ix in range(x - width/2, x + width/2 + 1):
            map[ix][iy].blocked = False
            map[ix][iy].block_sight = False
	    map[ix][iy].path = True
 
def make_map(enter_from, prev_x, prev_y):
    global map, world, world_coordinates, objects, stairs
 
    #the list of objects with just the player
    objects = [player]
 
    # create new map if world coordinates are empty
    if world[world_coordinates[0]][world_coordinates[1]][world_coordinates[2]][0] is None:
	#fill map with "blocked" tiles
        map = [[Tile(True) for y in range(MAP_HEIGHT)] for x in range(MAP_WIDTH) ]
 
        rooms = []
        num_rooms = 0
        stairs_exist = False
 
        for r in range(MAX_ROOMS):
            #random width and height
            w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
            h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
            #random position without going out of the boundaries of the map
            x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
            y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
 
            #"Rect" class makes rectangles easier to work with
            new_room = Rect(x, y, w, h)
 
            # **DON'T** run through the other rooms and see if they intersect with this one
            failed = False

	    room_intersects = False
            for other_room in rooms:
                if new_room.intersect(other_room):
		    room_intersects = True
            #        failed = True
            #        break #nope
 
            if not failed: 
                #"paint" it to the map's tiles
                create_room(new_room)

                #center coordinates of new room
                (new_x, new_y) = new_room.center()

	        # create random walls in rooms that are bigger than average (in at least one dimension) and don't intersect
	        if not room_intersects:
		    building_w = int(w / 2)
		    building_h = int(h / 2)
		    building_x = int(x + ((w - building_w) / 2))
		    building_y = int(y + ((h - building_h) / 2))
		    if libtcod.random_get_int(0, 0, 100) >= (100 - WALL_CHANCE) and (w > (ROOM_MAX_SIZE + ROOM_MIN_SIZE) / 2 or h > (ROOM_MAX_SIZE + ROOM_MIN_SIZE) / 2):
		        for ix in range(building_w):
		    	    map[building_x + ix][building_y].blocked = True
		    	    map[building_x + ix][building_y].block_sight = True
		    	    map[building_x + ix][building_y + building_h].blocked = True
		    	    map[building_x + ix][building_y + building_h].block_sight = True
		        for iy in range(building_h):
		    	    map[building_x][building_y + iy].blocked = True
		    	    map[building_x][building_y + iy].block_sight = True
		    	    map[building_x + building_w][building_y + iy].blocked = True
		   	    map[building_x + building_w][building_y + iy].block_sight = True

    	            #create stairs at a random place near the center of a room that doesnt intersect
    	            for ix in range(new_x - libtcod.random_get_int(0, 2, 4), new_x + libtcod.random_get_int(0, 2, 4)):
		        if stairs_exist:
	                    break
	                for iy in range(new_y - libtcod.random_get_int(0, 2, 4), new_y + libtcod.random_get_int(0, 2, 4)):
	    	            if not map[ix][iy].blocked and not stairs_exist:
    		                stairs = Object(ix, iy, ix, iy, 18, 'stairs', libtcod.white, always_visible=True)
    		                objects.append(stairs)
    		                stairs.send_to_back()  #so it's drawn below the monsters
		                stairs_exist = True
		                break
 
                if num_rooms > 0:
                    #all rooms after the first: connect it to the previous room with a tunnel
 
                    #center coordinates of previous room
                    (prev_x, prev_y) = rooms[num_rooms-1].center()
 
                    #draw a coin (random number that is either 0 or 1)
                    if libtcod.random_get_int(0, 0, 1) == 1:
                    #first move horizontally, then vertically
                        create_h_tunnel(prev_x, new_x, prev_y, libtcod.random_get_int(0, TUNNEL_MIN_WIDTH, TUNNEL_MAX_WIDTH))
                        create_v_tunnel(prev_y, new_y, new_x, libtcod.random_get_int(0, TUNNEL_MIN_WIDTH, TUNNEL_MAX_WIDTH))
                    else:
                    #first move vertically, then horizontally
                        create_v_tunnel(prev_y, new_y, prev_x, libtcod.random_get_int(0, TUNNEL_MIN_WIDTH, TUNNEL_MAX_WIDTH))
                        create_h_tunnel(prev_x, new_x, new_y, libtcod.random_get_int(0, TUNNEL_MIN_WIDTH, TUNNEL_MAX_WIDTH))

                #add some contents to this room, such as monsters
                place_objects(new_room)
 
                #finally, append the new room to the list
                rooms.append(new_room)
                num_rooms += 1

        # make random columns, avoiding paths and objects
        for i in range(num_rooms * COLUMNS_PER_ROOM):
	    col_chance = libtcod.random_get_int(0, 0, 100)
    	    if col_chance > (100 - COLUMN_CHANCE):
	        good_location = False
	        while not good_location: # check if column will be on a path or a blocked space if so pick a new spot
	            col_x = libtcod.random_get_int(0, MAX_COLUMN_SIZE + 1, MAP_WIDTH - MAX_COLUMN_SIZE - 1)
	            col_y = libtcod.random_get_int(0, MAX_COLUMN_SIZE + 1, MAP_HEIGHT - MAX_COLUMN_SIZE - 1)
	            col_w = libtcod.random_get_int(0, MIN_COLUMN_SIZE, MAX_COLUMN_SIZE)
	            col_h = libtcod.random_get_int(0, MIN_COLUMN_SIZE, MAX_COLUMN_SIZE)
		    if not map[col_x][col_y].path and not map[col_x + col_w][col_y + col_h].path:
		        if not map[col_x][col_y].blocked and not map[col_x + col_w][col_y + col_h].blocked:
		            good_location = True

	        # make the column
	        for iw in range(0, col_w):
		    for ih in range(0, col_h):
		        for object in objects: # check if there's an object near the spot and if so don't block it
			    if object.distance(col_x + iw, col_y + ih) < 5:
			        good_location = False
			        break
		        if good_location:
	    	            map[col_x + iw][col_y + ih].blocked = True
	    	            map[col_x + iw][col_y + ih].block_sight = True

	# save the stuff for this world coordinate
	world[world_coordinates[0]][world_coordinates[1]][world_coordinates[2]][0] = map
	world[world_coordinates[0]][world_coordinates[1]][world_coordinates[2]][1] = objects
	world[world_coordinates[0]][world_coordinates[1]][world_coordinates[2]][2] = stairs

    else: # there is already a map for this world coordinate, so use it
	map = world[world_coordinates[0]][world_coordinates[1]][world_coordinates[2]][0]
	objects = world[world_coordinates[0]][world_coordinates[1]][world_coordinates[2]][1]
	stairs = world[world_coordinates[0]][world_coordinates[1]][world_coordinates[2]][2]

    # create portals/doors at the map's extremities
    top_y = 0
    bottom_y = 0
    left_x = 0
    right_x = 0

    for iy in range(0, MAP_HEIGHT):
	for ix in range(0, MAP_WIDTH):
	    if not map[ix][iy].blocked:
		if top_y == 0:
		    top_y = iy
		bottom_y = iy

    for ix in range(0, MAP_WIDTH):
	for iy in range(0, MAP_HEIGHT):
	    if not map[ix][iy].blocked:
		if left_x == 0:
		    left_x = ix
		right_x = ix

    for ix in range(MAP_WIDTH):
	if not map[ix][top_y].blocked and world_coordinates[1] > 0:
    	    topdoor = Object(ix, top_y, ix, top_y, 30, 'north door', libtcod.dark_grey, always_visible=True)
    	    objects.append(topdoor)
    	    topdoor.send_to_back()  #so it's drawn below the monsters
	if not map[ix][bottom_y].blocked and world_coordinates[1] < WORLD_HEIGHT - 1:
    	    bottomdoor = Object(ix, bottom_y, ix, bottom_y, 31, 'south door', libtcod.dark_grey, always_visible=True)
    	    objects.append(bottomdoor)
    	    bottomdoor.send_to_back()  #so it's drawn below the monsters

    for iy in range(MAP_HEIGHT):
	if not map[left_x][iy].blocked and world_coordinates[0] > 0:
    	    leftdoor = Object(left_x, iy, left_x, iy, 17, 'west door', libtcod.dark_grey, always_visible=True)
    	    objects.append(leftdoor)
    	    leftdoor.send_to_back()  #so it's drawn below the monsters
	if not map[right_x][iy].blocked and world_coordinates[0] < WORLD_WIDTH - 1:
    	    rightdoor = Object(right_x, iy, right_x, iy, 16, 'east door', libtcod.dark_grey, always_visible=True)
    	    objects.append(rightdoor)
    	    rightdoor.send_to_back()  #so it's drawn below the monsters

    # put the player in the right place, make sure they don't start in a wall
    good_location = False
    separation = 0
    if enter_from == 0:
	while not good_location:
	    if prev_x == -1 or prev_y == -1:
                player.x = libtcod.random_get_int(0, 3, MAP_WIDTH - 3)
                player.y = libtcod.random_get_int(0, 3, MAP_HEIGHT - 3)
	    else:
                player.x = libtcod.random_get_int(0, max(3, prev_x - separation), min(prev_x + separation, MAP_WIDTH - 3))
                player.y = libtcod.random_get_int(0, max(3, prev_y - separation), min(prev_y + separation, MAP_HEIGHT - 3))
		separation += 1
	    if player.distance_to(stairs) > MIN_DIST_TO_STAIRS:
	        if (not map[player.x][player.y].blocked) and (not map[player.x + 1][player.y].blocked) and (not map[player.x - 1][player.y].blocked) and (not map[player.x][player.y + 1].blocked) and (not map[player.x][player.y - 1].blocked):
		    good_location = True
    elif enter_from == 1:
	player.y = bottom_y
	while not good_location:
	    player.x = libtcod.random_get_int(0, max(1, prev_x - separation), min(prev_x + separation, MAP_WIDTH - 1))
	    separation += 1
	    if not map[player.x][player.y].blocked:
		good_location = True
    elif enter_from == 2:
	player.x = left_x
	while not good_location:
	    player.y = libtcod.random_get_int(0, max(1, prev_y - separation), min(prev_y + separation, MAP_HEIGHT - 1))
	    separation += 1
	    if not map[player.x][player.y].blocked:
		good_location = True
    elif enter_from == 3:
	player.y = top_y
	while not good_location:
	    player.x = libtcod.random_get_int(0, max(1, prev_x - separation), min(prev_x + separation, MAP_WIDTH - 1))
	    separation += 1
	    if not map[player.x][player.y].blocked:
		good_location = True
    elif enter_from == 4:
	player.x = right_x
	while not good_location:
	    player.y = libtcod.random_get_int(0, max(1, prev_y - separation), min(prev_y + separation, MAP_HEIGHT - 1))
	    separation += 1
	    if not map[player.x][player.y].blocked:
		good_location = True

 
def random_choice_index(chances):  #choose one option from list of chances, returning its index
    #the dice will land on some number between 1 and the sum of the chances
    dice = libtcod.random_get_int(0, 1, sum(chances))
 
    #go through all chances, keeping the sum so far
    running_sum = 0
    choice = 0
    for w in chances:
        running_sum += w
 
        #see if the dice landed in the part that corresponds to this choice
        if dice <= running_sum:
            return choice
        choice += 1
 
def random_choice(chances_dict):
    #choose one option from dictionary of chances, returning its key
    chances = chances_dict.values()
    strings = chances_dict.keys()
 
    return strings[random_choice_index(chances)]
 
def from_dungeon_level(table):
    #returns a value that depends on level. the table specifies what value occurs after each level, default is 0.
    for (value, level) in reversed(table):
        if dungeon_level >= level:
            return value
    return 0

 
def place_objects(room):
    # this is where we decide the chance of each monster or item appearing.
 
    # maximum number of monsters per room
    max_monsters = from_dungeon_level([[2, 1], [3, 4], [5, 6], [7, 8]])
 
    # chance of each monster
    monster_chances = {}
    monster_chances['spider'] = 20
    monster_chances['bat'] = 40
    monster_chances['rat'] = from_dungeon_level([[60, 1], [40, 2], [20, 3], [0, 4]])
    monster_chances['snake'] = from_dungeon_level([[20, 2], [40, 3], [60, 4]])
    monster_chances['orc'] = from_dungeon_level([[20, 3], [40, 4], [60, 5], [80, 6], [100, 7]])
    monster_chances['troll'] = from_dungeon_level([[15, 3], [30, 5], [60, 7]])
    monster_chances['vampire bat'] = from_dungeon_level([[15, 7], [30, 8], [60, 9]])
 
    #maximum number of items per room
    max_items = from_dungeon_level([[1, 1], [2, 4]])
 
    #chance of each item (by default they have a chance of 0 at level 1, which then goes up)
    item_chances = {}
    item_chances['heal'] = 35  #healing potion always shows up, even if all other items have 0 chance
    item_chances['lightning'] = from_dungeon_level([[25, 4]])
    item_chances['fireball'] =  from_dungeon_level([[25, 6]])
    item_chances['confuse'] =   from_dungeon_level([[10, 2]])
    item_chances['sword'] =     from_dungeon_level([[5, 4]])
    item_chances['shield'] =    from_dungeon_level([[15, 8]])
 
 
    #choose random number of monsters
    num_monsters = libtcod.random_get_int(0, 0, max_monsters)
 
    for i in range(num_monsters):
        #choose random spot for this monster
	if not room is None:
            x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
            y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
	else:
	    good_location = False
	    while not good_location:
		x = libtcod.random_get_int(0, 1, MAP_WIDTH - 1)
		y = libtcod.random_get_int(0, 1, MAP_HEIGHT - 1)
		if not map[x][y].blocked:
		    good_location = True
 
        #only place it if the tile is not blocked
        if not is_blocked(x, y):
            choice = random_choice(monster_chances)

            if choice == 'spider':
		effect_component = effect_component = Effect('m', 'M', '%', -1, False)
                fighter_component = Fighter(hp=5, defense=0, power=1, xp=5, death_function=monster_death)
                ai_component = monster_ai('spider')
                monster = Object(x, y, x, y, 'm', 'spider', libtcod.black,
                                 blocks=True, fighter=fighter_component, ai=ai_component, effect=effect_component, speed=60)

            if choice == 'bat':
		effect_component = effect_component = Effect('v', '^', '%', -1, False)
                fighter_component = Fighter(hp=5, defense=0, power=1, xp=5, death_function=monster_death)
                ai_component = monster_ai('bat')
                monster = Object(x, y, x, y, '^', 'bat', libtcod.black,
                                 blocks=True, fighter=fighter_component, ai=ai_component, effect=effect_component, speed=5)

            if choice == 'rat':
		effect_component = effect_component = Effect('q', 'Q', '%', -1, False)
                fighter_component = Fighter(hp=10, defense=0, power=2, xp=10, death_function=monster_death)
                ai_component = monster_ai('rat')
                monster = Object(x, y, x, y, 'Q', 'rat', libtcod.darker_sepia,
                                 blocks=True, fighter=fighter_component, ai=ai_component, effect=effect_component, speed=5)

            if choice == 'snake':
		effect_component = effect_component = Effect('s', '~', '%', -1, False)
                fighter_component = Fighter(hp=10, defense=0, power=2, xp=10, death_function=monster_death)
                ai_component = monster_ai('basic')
                monster = Object(x, y, x, y, 's', 'snake', libtcod.dark_lime,
                                 blocks=True, fighter=fighter_component, ai=ai_component, effect=effect_component, speed=6)

            if choice == 'orc':
		effect_component = effect_component = Effect('o', '0', '%', -1, False)
                fighter_component = Fighter(hp=20, defense=0, power=2, xp=40, death_function=monster_death)
                ai_component = monster_ai('basic')
                monster = Object(x, y, x, y, 'o', 'orc', libtcod.darker_green,
                                 blocks=True, fighter=fighter_component, ai=ai_component, effect=effect_component, speed=5)
 
            elif choice == 'troll':
		effect_component = effect_component = Effect('t', 'T', '%', -1, False)
                fighter_component = Fighter(hp=30, defense=2, power=5, xp=150, death_function=monster_death)
                ai_component = monster_ai('basic')
                monster = Object(x, y, x, y, 'T', 'troll', libtcod.dark_cyan,
                                 blocks=True, fighter=fighter_component, ai=ai_component, effect=effect_component)

            elif choice == 'vampire bat':
		effect_component = effect_component = Effect('^', 'v', '%', -1, False)
                fighter_component = Fighter(hp=40, defense=2, power=10, xp=400, death_function=monster_death)
                ai_component = monster_ai('basic')
                monster = Object(x, y, x, y, '^', 'vampire bat', libtcod.dark_red,
                                 blocks=True, fighter=fighter_component, ai=ai_component, effect=effect_component, speed=3)
 
            objects.append(monster)

    for i in range(ROCKS_PER_ROOM):
	good_location = False
	while not good_location:
	    x = libtcod.random_get_int(0, 1, MAP_WIDTH - 1)
	    y = libtcod.random_get_int(0, 1, MAP_HEIGHT - 1)
	    if not map[x][y].blocked:
		good_location = True
        rock_style = libtcod.random_get_int(0, 226, 232)
        rock = Object(x, y, x, y, rock_style, 'rock', libtcod.dark_grey, always_visible=True)
        objects.append(rock)
        rock.send_to_back()

    for i in range(GRAVEL_PER_ROOM):
	good_location = False
	while not good_location:
	    x = libtcod.random_get_int(0, 1, MAP_WIDTH - 1)
	    y = libtcod.random_get_int(0, 1, MAP_HEIGHT - 1)
	    if not map[x][y].blocked:
		good_location = True
	gravel_style = libtcod.random_get_int(0, 176, 178)
        gravel = Object(x, y, x, y, gravel_style, 'gravel', libtcod.dark_grey, always_visible=True)
        objects.append(gravel)
        gravel.send_to_back()
 
    #choose random number of items
    num_items = libtcod.random_get_int(0, 0, max_items)
 
    for i in range(num_items):
        #choose random spot for this item
	if not room is None:
            x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
            y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
	else:
	    good_location = False
	    while not good_location:
		x = libtcod.random_get_int(0, 1, MAP_WIDTH - 1)
		y = libtcod.random_get_int(0, 1, MAP_HEIGHT - 1)
		if not map[x][y].blocked:
		    good_location = True
 
        #only place it if the tile is not blocked
        if not is_blocked(x, y):
            choice = random_choice(item_chances)
            if choice == 'heal':
                #create a healing potion
                item_component = Item(use_function=cast_heal)
                item = Object(x, y, x, y, '!', 'healing potion', libtcod.violet, item=item_component)
 
            elif choice == 'lightning':
                #create a lightning bolt scroll
                item_component = Item(use_function=cast_lightning)
                item = Object(x, y, x, y, '#', 'scroll of lightning bolt', libtcod.light_yellow, item=item_component)
 
            elif choice == 'fireball':
                #create a fireball scroll
                item_component = Item(use_function=cast_fireball)
                item = Object(x, y, x, y, '#', 'scroll of fireball', libtcod.light_yellow, item=item_component)
 
            elif choice == 'confuse':
                #create a confuse scroll
                item_component = Item(use_function=cast_confuse)
                item = Object(x, y, x, y, '#', 'scroll of confusion', libtcod.light_yellow, item=item_component)
 
            elif choice == 'sword':
                #create a sword
                equipment_component = Equipment(slot='right hand', power_bonus=3)
                item = Object(x, y, x, y, '/', 'sword', libtcod.sky, equipment=equipment_component)
 
            elif choice == 'shield':
                #create a shield
                equipment_component = Equipment(slot='left hand', defense_bonus=1)
                item = Object(x, y, x, y, '[', 'shield', libtcod.darker_orange, equipment=equipment_component)
 
            objects.append(item)
            item.send_to_back()  #items appear below other objects
            item.always_visible = True  #items are visible even out-of-FOV, if in an explored area
 
 
def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    #render a bar (HP, experience, etc). first calculate the width of the bar
    bar_width = int(float(value) / maximum * total_width)
 
    #render the background first
    libtcod.console_set_default_background(panel, back_color)
    libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)
 
    #now render the bar on top
    libtcod.console_set_default_background(panel, bar_color)
    if bar_width > 0:
        libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
 
    #finally, some centered text with the values
    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER,
                                 name + ': ' + str(value) + '/' + str(maximum))
 
def get_names_under_mouse():
    global mouse
    #return a string with the names of all objects under the mouse
 
    (x, y) = (mouse.cx, mouse.cy)
 
    #create a list with the names of all objects at the mouse's coordinates and in FOV
    names = [obj.name for obj in objects
             if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y) and obj.name != '' and obj.name != ' ']
 
    names = ', '.join(names)  #join the names, separated by commas
    return names.capitalize()
 
def render_all():
    global fov_map, color_dark_wall, color_light_wall
    global color_dark_ground, color_light_ground
    global fov_recompute
 
    if fov_recompute:
        #recompute FOV if needed (the player moved or something)
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
 
        #go through all tiles, and set their background color according to the FOV
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                visible = libtcod.map_is_in_fov(fov_map, x, y)
                wall = map[x][y].block_sight
                if not visible:
                    #if it's not visible right now, the player can only see it if it's explored
                    if map[x][y].explored:
                        if wall:
                            libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
                        else:
                            libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
                else:
                    #it's visible
                    if wall:
                        libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET )
                    else:
                        libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET )
                        #since it's visible, explore it
                    map[x][y].explored = True
 
    #draw all objects in the list, except the player. we want it to
    #always appear over all other objects! so it's drawn later.
#    for object in objects:
#        if object != player:
#            object.draw()
#    player.draw()

    for object in objects: # just draw them all, we want some things in front of the player
        object.draw()
 
    #blit the contents of "con" to the root console
    libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)
 
    #prepare to render the GUI panel
    libtcod.console_set_default_background(panel, libtcod.black)
    libtcod.console_clear(panel)
 
    #print the game messages, one line at a time
    y = 1
    for (line, color) in game_msgs:
        libtcod.console_set_default_foreground(panel, color)
        libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT,line)
        y += 1
 
    #show the player's stats
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
               libtcod.light_red, libtcod.darker_red)
    libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, 'Dungeon level ' + str(dungeon_level))
 
    #display names of objects under the mouse
    libtcod.console_set_default_foreground(panel, libtcod.light_gray)
    libtcod.console_print_ex(panel, 5, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())
 
    #blit the contents of "panel" to the root console
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)
 
 
def message(new_msg, color = libtcod.white):
    #split the message if necessary, among multiple lines
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
 
    for line in new_msg_lines:
        #if the buffer is full, remove the first line to make room for the new one
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]
 
        #add the new line as a tuple, with the text and the color
        game_msgs.append( (line, color) )
 
 
def player_move_or_attack(dx, dy):
    global fov_recompute
 
    #the coordinates the player is moving to/attacking
    x = player.x + dx
    y = player.y + dy

    blade_equipped = False
    bow_equipped = False

    for item in inventory:
        if item.equipment and item.equipment.is_equipped:
            if item.name == 'bow':
		bow_equipped = True
	    elif item.name == 'dagger' or item.name == 'sword':
		blade_equipped = True
 
    if blade_equipped:
        #try to find an attackable object there
        target = None
        for object in objects:
            if object.fighter and object.x == x and object.y == y:
                target = object
                break
 
        #attack if target found, move otherwise
        if target is not None:
            player.fighter.attack(target)
        else:
            player.move(dx, dy)
            fov_recompute = True

    elif bow_equipped:
#	if dx < 0: # set arrow character based on direction (diagonals get x-direction arrows)
#	    arrow_style = 27
#	elif dx > 0:
#	    arrow_style = 26
#	elif dy < 0:
#	    arrow_style = 24
#	elif dy > 0:
#	    arrow_style = 25

	# set arrow character based on direction (diagonals get random appropriate direction)
	if dx < 0 and dy == 0: 
	    arrow_style = 27 # west
	elif dx > 0 and dy == 0:
	    arrow_style = 26 # east
	elif dy < 0 and dx == 0:
	    arrow_style = 24 # north
	elif dy > 0 and dx == 0:
	    arrow_style = 25 # south
	elif dx < 0 and dy < 0:
	    if libtcod.random_get_int(0, 0, 1) == 0: arrow_style = 24
	    else: arrow_style = 27 # northwest
	elif dx > 0 and dy < 0:
	    if libtcod.random_get_int(0, 0, 1) == 0: arrow_style = 24
	    else: arrow_style = 26 # northeast
	elif dx > 0 and dy > 0:
	    if libtcod.random_get_int(0, 0, 1) == 0: arrow_style = 25
	    else: arrow_style = 26 # southeast
	elif dx < 0 and dy > 0:
	    if libtcod.random_get_int(0, 0, 1) == 0: arrow_style = 25
	    else: arrow_style = 27 # southwest

        effect_component = effect_component = Effect(arrow_style, arrow_style, ' ', libtcod.random_get_int(0, 20, 40), True)
        ai_component = projectile_ai('arrow', dx, dy, False)
	arrow = Object(player.x + dx, player.y + dy, player.x + dx, player.y + dy, arrow_style, 'arrow', libtcod.darker_sepia, blocks=False, ai=ai_component, effect=effect_component, speed=1)
	objects.append(arrow)

    else: # just move if none of the above are equipped
        player.move(dx, dy)
        fov_recompute = True

    player.attack_wait = player.fighter.attack_speed
 
 
def menu(header, options, width):
    if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')
 
    #calculate total height for the header (after auto-wrap) and one line per option
    header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
    if header == '':
        header_height = 0
    height = len(options) + header_height
 
    #create an off-screen console that represents the menu's window
    window = libtcod.console_new(width, height)
 
    #print the header, with auto-wrap
    libtcod.console_set_default_foreground(window, libtcod.white)
    libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)
 
    #print all the options
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ') ' + option_text
        libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
        y += 1
        letter_index += 1
 
    #blit the contents of "window" to the root console
    x = SCREEN_WIDTH/2 - width/2
    y = SCREEN_HEIGHT/2 - height/2
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)
 
    #present the root console to the player and wait for a key-press
    libtcod.console_flush()
    key = libtcod.console_wait_for_keypress(True)

#    key = libtcod.console_check_for_keypress()
#    libtcod.sys_wait_for_event(libtcod.EVENT_KEY_RELEASE | libtcod.EVENT_MOUSE_RELEASE, key, libtcod.Mouse(), True)
 
    if key.vk == libtcod.KEY_ENTER and key.lalt:  #(special case) Alt+Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen)
 
    #convert the ASCII code to an index; if it corresponds to an option, return it
    index = key.c - ord('a')
    if index >= 0 and index < len(options): return index
    return None
 
def inventory_menu(header):
    #show a menu with each item of the inventory as an option
    if len(inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = []
        for item in inventory:
            text = item.name
            #show additional information, in case it's equipped
            if item.equipment and item.equipment.is_equipped:
                text = text + ' (on ' + item.equipment.slot + ')'
            options.append(text)
 
    index = menu(header, options, INVENTORY_WIDTH)
 
    #if an item was chosen, return it
    if index is None or len(inventory) == 0: return None
    return inventory[index].item

def world_map():
    # show a ghetto version of the world map as a menu thing
    map_string = '\n'
    for i in range(((WORLD_WIDTH + 2)/ 2) - 3):
	map_string = map_string + ' '
    map_string = map_string + 'World Map\n\n'

    for i in range(WORLD_WIDTH + 2):
	if i == 0: map_string = map_string + ' ' + chr(218)
	elif i == WORLD_WIDTH + 1: map_string = map_string + chr(191)
        else: map_string = map_string + chr(196)

    for iy in range(WORLD_HEIGHT):
	tmp_string = ''
        for ix in range(WORLD_WIDTH):
	    if world_coordinates[0] == ix and world_coordinates[1] == iy:
                tmp_string = tmp_string + 'X'
	    elif world[ix][iy][world_coordinates[2]][0] is not None:
                tmp_string = tmp_string + chr(224) #chr(225)
	    else:
                tmp_string = tmp_string + ' ' #chr(224)
	map_string = map_string + '\n ' + chr(179) + tmp_string + chr(179)

    for i in range(WORLD_WIDTH + 2):
	if i == 0: map_string = map_string + '\n ' + chr(192)
	elif i == WORLD_WIDTH + 1: map_string = map_string + chr(217)
        else: map_string = map_string + chr(196)

    map_string = map_string + '\n\n  Dungeon level:     ' + str(dungeon_level)
    map_string = map_string + '\n\n  World coordinates: ' + str(world_coordinates)
    map_string = map_string + '\n'

    msgbox(map_string, max(32, WORLD_WIDTH + 4))

def inspect(x, y):
    # inspect the object(s) at specified location
    inspected_object = ''
    for object in objects:
	if object.x == x and object.y == y and inspected_object == '':
	    inspected_object = object.name.capitalize()
    if inspected_object == '': # if nothing right under cursor, check adjacent squares
	for object in objects:
	    for ix in range(-1,2):
		for iy in range(-1,2):
	            if object.x == x + ix and object.y == y + iy and inspected_object == '':
	        	inspected_object = object.name.capitalize()
    if inspected_object == '': # if no objects at all detected under cursor, check if there's a wall
	for ix in range(-1,2):
	    for iy in range(-1,2):
		if map[x + ix][y + iy].blocked:
		    inspected_object = 'Wall'

    for ix in range(-1,2):
	for iy in range(-1,2):
    	    effect_component = Effect('?','?', ' ', 1, True)
    	    inspect_effect = Object(x + ix, y + iy, x + ix, y + iy, '?', 'inspect', libtcod.green, always_visible=True, effect=effect_component)
    	    objects.append(inspect_effect)
	    inspect_effect.send_to_back()
    render_all()

    if inspected_object == '':
	menu('\n Nothing there\n\n        (Press any key)\n', [], INSPECT_SCREEN_WIDTH)
    else:
        menu('\n ' + inspected_object + '\n\n        (Press any key)\n', [], INSPECT_SCREEN_WIDTH)
 
def msgbox(text, width=50):
    menu(text, [], width)  #use menu() as a sort of "message box"
 
def handle_keys():
    global key
 
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        #Alt+Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
 
    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit'  #exit game
 
    if game_state == 'playing':
	key_char = chr(key.c)

	if player.wait == 0:
            # move player by mouse
	    player.click_action()
	else:
	    player.wait -= 1

	if player.attack_wait == 0:
	    # attack with weapon
            if key.vk == libtcod.KEY_UP or key_char == 'w':
                player_move_or_attack(0, -1)
            if key.vk == libtcod.KEY_DOWN or key_char == 's':
                player_move_or_attack(0, 1)
            if key.vk == libtcod.KEY_LEFT or key_char == 'a':
                player_move_or_attack(-1, 0)
            if key.vk == libtcod.KEY_RIGHT or key_char == 'd':
                player_move_or_attack(1, 0)
            if key_char == 'q':
                player_move_or_attack(-1, -1)
            if key_char == 'e':
                player_move_or_attack(1, -1)
            if key_char == 'z':
                player_move_or_attack(-1, 1)
            if key_char == 'c':
                player_move_or_attack(1, 1)
	else:
	    player.attack_wait -= 1

	if player.spell_wait == 0:
	    # spellcasting
            if key_char == 'x': cast_lightning()

            if key_char == 'r': cast_firenova()

            if key_char == 'h': cast_heal()

	    if key_char == 't': player.teleport(-1, -1) # tele to a random unblocked spot
	    if key.vk == libtcod.KEY_KPADD: enter_portal(0)
	    if key.vk == libtcod.KEY_KP8: enter_portal(1)
	    if key.vk == libtcod.KEY_KP6: enter_portal(2)
	    if key.vk == libtcod.KEY_KP2: enter_portal(3)
	    if key.vk == libtcod.KEY_KP4: enter_portal(4)

	else:
	    player.spell_wait -= 1
 
	if player.menu_wait == 0:
            if key_char == 'i':
                #show the inventory; if an item is selected, use it
                chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.use()
		player.menu_wait = 2
 
            if key_char == 'o':
                #show the inventory; if an item is selected, drop it
                chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.drop()
		player.menu_wait = 2
 
            if key_char == 'g':
                #show character information
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msgbox('Character Information\n\nLevel: ' + str(player.level) + '\nExperience: ' + str(player.fighter.xp) +
                       '\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(player.fighter.max_hp) +
                       '\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)
		player.menu_wait = 2

            if key_char == 'm':
                #show ghetto world map
	        world_map()
		player.menu_wait = 5
	else:
	    player.menu_wait -= 1

        if key_char == 'f':
            #pick up an item
            for object in objects:  #look for an item in the player's tile
                if object.x == player.x and object.y == player.y and object.item:
                    object.item.pick_up()
                    break

        if key_char == ' ':
            #go up stairs, if the player is on them or next to them
	    if player.distance_to(stairs) <= 1:
                enter_portal(0)

            #go through door if standing at one
	    for object in objects:  #look for a portal in the player's tile
                if object.x == player.x and object.y == player.y:
		    if object.name == 'north door':
                        enter_portal(1)
		    elif object.name == 'east door':
                        enter_portal(2)
		    elif object.name == 'south door':
                        enter_portal(3)
		    elif object.name == 'west door':
                        enter_portal(4)
                    break

 
def check_level_up():
    #see if the player's experience is enough to level-up
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    if player.fighter.xp >= level_up_xp:
        #it is! level up and ask to raise some stats
        player.level += 1
        player.fighter.xp -= level_up_xp
        message('Your battle skills grow stronger! You reached level ' + str(player.level) + '!', libtcod.yellow)
 
        choice = None
        while choice == None:  #keep asking until a choice is made
            choice = menu('Level up! Choose a stat to raise:\n',
                          ['Constitution (+20 HP, from ' + str(player.fighter.max_hp) + ')',
                           'Strength (+1 attack, from ' + str(player.fighter.power) + ')',
                           'Agility (+1 defense, from ' + str(player.fighter.defense) + ')'], LEVEL_SCREEN_WIDTH)
 
        if choice == 0:
            player.fighter.base_max_hp += 20
            player.fighter.hp += 20
        elif choice == 1:
            player.fighter.base_power += 1
        elif choice == 2:
            player.fighter.base_defense += 1
 
def player_death(player):
    #the game ended!
    global game_state
    message('You died!', libtcod.red)
    game_state = 'dead'
 
    #for added effect, transform the player into a corpse!
    player.effect.rotations = -2
    player.char = '%'
    player.color = libtcod.dark_red
 
def monster_death(monster, killer):
    #transform it into a nasty corpse! it doesn't block, can't be attacked and doesn't move
    if killer == 'player':
        message('The ' + monster.name + ' is dead! You gain ' + str(monster.fighter.xp) + ' experience points.', libtcod.yellow)
        player.fighter.xp += monster.fighter.xp
    elif libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
	message('The ' + killer + ' killed the ' + monster.name + '!', libtcod.orange)

    if monster.effect:
	monster.effect.rotations = -2
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'Remains of ' + monster.name
    monster.send_to_back()
 
def target_tile(max_range=None):
    global key, mouse
    #return the position of a tile left-clicked in player's FOV (optionally in a range), or (None,None) if right-clicked.
    while True:
        #render the screen. this erases the inventory and shows the names of objects under the mouse.
        libtcod.console_flush()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
        render_all()
 
        (x, y) = (mouse.cx, mouse.cy)
 
        if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
            return (None, None)  #cancel if the player right-clicked or pressed Escape
 
        #accept the target if the player clicked in FOV, and in case a range is specified, if it's in that range
        if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and
                (max_range is None or player.distance(x, y) <= max_range)):
            return (x, y)
 
def target_monster(max_range=None):
    #returns a clicked monster inside FOV up to a range, or None if right-clicked
    while True:
        (x, y) = target_tile(max_range)
        if x is None:  #player cancelled
            return None
 
        #return the first clicked monster, otherwise continue looping
        for obj in objects:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj
 
def closest_monster(max_range):
    #find closest enemy, up to a maximum range, and in the player's FOV
    closest_enemy = None
    closest_dist = max_range + 1  #start with (slightly more than) maximum range
 
    for object in objects:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            #calculate distance between this object and the player
            dist = player.distance_to(object)
            if dist < closest_dist:  #it's closer, so remember it
                closest_enemy = object
                closest_dist = dist
    return closest_enemy
 
def cast_heal():
    #heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', libtcod.red)
	player.spell_wait = 10
        return 'cancelled'
 
    message('Your wounds start to feel better!', libtcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)

    for ix in range(-1,2): # make effect
        for iy in range(-1,2):
	    if not map[player.x + ix][player.y + iy].blocked and player.distance(player.x + ix, player.y + iy) <= 1: # and libtcod.random_get_int(0, 0, 3) > 0:
		heal_color = libtcod.crimson * libtcod.random_get_float(0, 1, 4)
    	        effect_component = Effect('+','`', ' ', libtcod.random_get_int(0, 1, 4), True)
    	        heal_effect = Object(player.x + ix, player.y + iy, player.x + ix, player.y + iy, '+', 'healing', heal_color, always_visible=False, effect=effect_component)
    	        objects.append(heal_effect)

    player.spell_wait = 10
 
def cast_lightning():
    #find closest enemy (inside a maximum range) and damage it
    monster = closest_monster(LIGHTNING_RANGE)
    if monster is None:  #no enemy found within maximum range
        #message('No enemy is close enough to strike.', libtcod.red)
        #draw lightning around self
        for ix in range(player.x-1,player.x+2):
	    for iy in range(player.y-1,player.y+2):
		if not map[ix][iy].blocked and libtcod.random_get_int(0, 0, 3) > 0:
		    if libtcod.random_get_int(0, 0, 1) == 0: 
			lightning_color = libtcod.light_yellow
			lightning_start = '*'
		    else: 
			lightning_color = libtcod.yellow
			lightning_start = '#'
	            effect_component = Effect('*','#', ' ', libtcod.random_get_int(0, 1, 3), True)
                    lightning = Object(ix, iy, ix, iy, lightning_start, 'lightning', lightning_color, always_visible=False, effect=effect_component)
                    objects.append(lightning)
	player.spell_wait = 15
        return 'cancelled'
 
    #zap it!
    message('A lighting bolt strikes the ' + monster.name + '! The damage is '
            + str(LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
    monster.fighter.take_damage(LIGHTNING_DAMAGE, 'player')

    #draw lightning around monster
    for ix in range(monster.x-1,monster.x+2):
	for iy in range(monster.y-1,monster.y+2):
	    if not map[ix][iy].blocked and libtcod.random_get_int(0, 0, 3) > 0:
		if libtcod.random_get_int(0, 0, 1) == 0: 
		    lightning_color = libtcod.light_yellow
		    lightning_start = '*'
		else: 
		    lightning_color = libtcod.yellow
		    lightning_start = '#'
	        effect_component = Effect('*','#', ' ', libtcod.random_get_int(0, 1, 4), True)
                lightning = Object(ix, iy, ix, iy, '*', 'lightning', lightning_color, always_visible=False, effect=effect_component)
                objects.append(lightning)

    #draw lightning in a line toward monster
    libtcod.line_init(player.x, player.y, monster.x ,monster.y)
    x, y = libtcod.line_step() # update player cell here
    while not x is None:
	if not map[x][y].blocked:
	    if libtcod.random_get_int(0, 0, 1) == 0: 
		lightning_color = libtcod.light_yellow
		lightning_start = '*'
	    else: 
		lightning_color = libtcod.yellow
		lightning_start = '#'
	    effect_component = Effect('*','#', ' ', libtcod.random_get_int(0, 1, 2), True)
            lightning = Object(x, y, x, y, '*', 'lightning', lightning_color, always_visible=False, effect=effect_component)
            objects.append(lightning)
        x, y = libtcod.line_step()

    # cast again if another enemy is in range
#    if closest_monster(LIGHTNING_RANGE) is not None: 
#        cast_lightning()

    player.spell_wait = 15
        
 
def cast_firenova():
    for ix in range(max(1, player.x - FIRENOVA_RADIUS), min(MAP_WIDTH - 1, player.x + FIRENOVA_RADIUS)):
	for iy in range(max(1, player.y - FIRENOVA_RADIUS), min(MAP_HEIGHT - 1, player.y + FIRENOVA_RADIUS)):
	    # draw flames within box and within range
	    if player.distance(ix, iy) <= FIRENOVA_RADIUS and not map[ix][iy].blocked and libtcod.map_is_in_fov(fov_map, ix, iy):
		# get random flame color based on distance from source
		flame_color = libtcod.flame * libtcod.random_get_float(0, (player.distance(ix, iy) / 4) + 1, player.distance(ix, iy) / 2) #libtcod.random_get_float(0, 1, 3)
		if libtcod.random_get_int(0, 0, 3) > 0: flame_start = '$'
		else: flame_start = '*'
	        effect_component = Effect('$','*', ' ', libtcod.random_get_int(0, 1, 5), True)
                firenova = Object(ix, iy, ix, iy, flame_start, 'fire nova', flame_color, always_visible=False, effect=effect_component)
                objects.append(firenova)

    for object in objects:  #damage every fighter in range, excluding the player
        if object.distance(player.x, player.y) <= FIRENOVA_RADIUS and object.fighter and not object == player:
            message('The ' + object.name + ' gets burned for ' + str(FIRENOVA_DAMAGE) + ' hit points.', libtcod.orange)
            object.fighter.take_damage(FIRENOVA_DAMAGE, 'player')

    player.spell_wait = 30


def cast_fireball():
    #ask the player for a target tile to throw a fireball at
    message('Left-click a target tile for the fireball, or right-click to cancel.', libtcod.light_cyan)
    (x, y) = target_tile()
    if x is None: return 'cancelled'
    message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)
 
    for obj in objects:  #damage every fighter in range, including the player
        if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
            message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.orange)
            obj.fighter.take_damage(FIREBALL_DAMAGE, 'player')

    player.spell_wait = 30
 
def cast_confuse():
    #ask the player for a target to confuse
    message('Left-click an enemy to confuse it, or right-click to cancel.', libtcod.light_cyan)
    monster = target_monster(CONFUSE_RANGE)
    if monster is None: return 'cancelled'
 
    #replace the monster's AI with a "confused" one; after some turns it will restore the old AI
    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster  #tell the new component who owns it
    message('The eyes of the ' + monster.name + ' look vacant, as he starts to stumble around!', libtcod.light_green)

    player.spell_wait = 30
 
 
def save_game():
    #open a new empty shelve (possibly overwriting an old one) to write the game data
    file = shelve.open('savegame', 'n')
    file['map'] = map
    file['objects'] = objects
    file['player_index'] = objects.index(player)  #index of player in objects list
    file['stairs_index'] = objects.index(stairs)  #same for the stairs
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file['dungeon_level'] = dungeon_level # fix this: replace with world coordinate z variable?
    file['world_coordinates'] = world_coordinates
    file['world'] = world
    file.close()
 
def load_game():
    #open the previously saved shelve and load the game data
    global map, world, world_coordinates, objects, player, stairs, inventory, game_msgs, game_state, dungeon_level
 
    file = shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']]  #get index of player in objects list and access it
    stairs = objects[file['stairs_index']]  #same for the stairs
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    dungeon_level = file['dungeon_level']
    world_coordinates = file['world_coordinates']
    world = file['world']
    file.close()
 
    initialize_fov()
 
def new_game():
    global player, inventory, game_msgs, game_state, dungeon_level, map, world, world_coordinates
 
    #create object representing the player
    effect_component = effect_component = Effect('@', 'g', '%', -1, False)
    fighter_component = Fighter(hp=PLAYER_STARTING_HP, defense=PLAYER_STARTING_DEF, power=PLAYER_STARTING_POWER, xp=0, death_function=player_death, attack_speed=PLAYER_ATTACK_SPEED)
    player = Object(0, 0, 0, 0, '@', 'player', libtcod.white, blocks=True, fighter=fighter_component, effect=effect_component, speed=PLAYER_SPEED)
 
    player.level = 1
 
    #generate map (at this point it's not drawn to the screen)
    dungeon_level = 1
    world = [[[[None, None, None] for z in range(WORLD_DEPTH)] for y in range(WORLD_HEIGHT)] for x in range(WORLD_WIDTH) ] # map, objects, stairs for each x, y, z
    world_coordinates = [WORLD_WIDTH / 2, WORLD_HEIGHT / 2, 0]
    make_map(0, -1, -1)
    world[WORLD_WIDTH / 2][WORLD_HEIGHT / 2][0][0] = map
    initialize_fov()
 
    game_state = 'playing'
    inventory = []
 
    #create the list of game messages and their colors, starts empty
    game_msgs = []
 
    #a warm welcoming message!
    message('Welcome stranger! Prepare to perish in the Tombs of YOUR MOTHER.', libtcod.red)
 
    #initial equipment: a dagger and a bow
    equipment_component = Equipment(slot='right hand', power_bonus=2)
    obj = Object(0, 0, 0, 0, '-', 'dagger', libtcod.sky, equipment=equipment_component)
    inventory.append(obj)
    equipment_component.equip()
    obj.always_visible = True

    equipment_component = Equipment(slot='right hand', power_bonus=2)
    obj = Object(0, 0, 0, 0, '-', 'bow', libtcod.sepia, equipment=equipment_component)
    inventory.append(obj)
    #equipment_component.equip()
    obj.always_visible = True
 
def enter_portal(direction):
    #advance to the next level
    global dungeon_level, world_coordinates
    if direction == 0:
	if world_coordinates[2] < WORLD_DEPTH - 1:
            message('You take a moment to rest, and recover your strength.', libtcod.light_violet)
            player.fighter.heal(player.fighter.max_hp / 2)  #heal the player by 50%
            message('After a rare moment of peace, you descend deeper into the heart of YOUR MOTHER...', libtcod.red)
            dungeon_level += 1
	    world_coordinates[2] += 1
            message('You traveled up.   ', libtcod.white)
            make_map(0, player.x, player.y)  #create a fresh new level!
            initialize_fov()
	else:
	    message('A strange force prevents you from ascending BECAUSE YOU ARE A NOOB.', libtcod.red) 
    else:
	if direction == 1:
	    if world_coordinates[1] > 0:
	        world_coordinates[1] -= 1
	        message('You traveled north.  ', libtcod.white)  
	elif direction == 2:
	    if world_coordinates[0] < WORLD_WIDTH - 1:
	        world_coordinates[0] += 1   
	        message('You traveled east.   ', libtcod.white)
	elif direction == 3:
	    if world_coordinates[1] < WORLD_HEIGHT - 1:
	        world_coordinates[1] += 1
	        message('You traveled south.  ', libtcod.white)   
	elif direction == 4:
	    if world_coordinates[0] > 0:
	        world_coordinates[0] -= 1  
	        message('You traveled west.   ', libtcod.white)  
        make_map(direction, player.x, player.y)
        initialize_fov()

 
def initialize_fov():
    global fov_recompute, fov_map
    fov_recompute = True
 
    #create the FOV map, according to the generated map
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
 
    libtcod.console_clear(con)  #unexplored areas start black (which is the default background color)
 
def play_game():
    global key, mouse
 
    player_action = None
    mouse = libtcod.Mouse()
    key = libtcod.Key()

    # main loop
    while not libtcod.console_is_window_closed():
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)

        # render the screen
        render_all()
        libtcod.console_flush()
 
        # level up if needed
        check_level_up()
 
        # erase all objects at their old locations, before they move
        for object in objects:
            object.clear()
 
        # handle keys and exit game if needed
        player_action = handle_keys()
        if player_action == 'exit':
            break
 
        # let monsters take their turn
        if game_state == 'playing':
            for object in objects:
                if object.ai:
                    if object.wait > 0:  # don't take a turn yet if still waiting
                        object.wait -= 1
		    elif object.attack_wait > 0:
			object.attack_wait -= 1
                    else:
                        object.ai.take_turn()
		if object.effect:
                    if object.effect.wait > 0:  # don't animate yet if still waiting
                        object.effect.wait -= 1
                    else:
                        object.effect.animate()
		    if object.char == ' ' and object.effect.finished:
			objects.remove(object) # delete unused effect objects

 
def main_menu():
    img = libtcod.image_load('menu_background.png')
 
    while not libtcod.console_is_window_closed():
        #show the background image, at twice the regular console resolution
        libtcod.image_blit_2x(img, 0, 0, 0)
 
        #show the game's title, and some credits!
        libtcod.console_set_default_foreground(0, libtcod.light_yellow)
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-6, libtcod.BKGND_NONE, libtcod.CENTER, 'TOMBS OF YOUR MOTHER')
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER, 'By GT')
 
        #show options and wait for the player's choice
        choice = menu('', ['New game', 'Load game', 'Save and continue', 'Save and quit', 'Quit'], 30)
 
        if choice == 0:  # new game
	    new_game()
            play_game()

        elif choice == 1:  # load last game
            try:
                load_game()
            except:
                msgbox('\n No saved game to load.\n', 24)
                continue
            play_game()

        elif choice == 2:  # just save
	    try:
	        save_game()
            except:
                msgbox('\n No game to save.\n', 24)
                continue
            play_game()

        elif choice == 3:  # save and quit
	    try:
	        save_game()
            except:
                msgbox('\n No game to save.\n', 24)
            break

        elif choice == 4:  # just quit
            break
 
libtcod.console_set_custom_font('fonts/consolas10x10_gs_tc.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python libtcod game', False)
libtcod.sys_set_fps(LIMIT_FPS)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)
libtcod.console_set_fullscreen(START_FULLSCREEN)
 
main_menu()
