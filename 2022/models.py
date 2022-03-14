# These classes are the predecessors to Django Models

class Team(object):
    def __init__(self, name: str, overall_seed: int):
        self.name = name
        self.overall_seed = overall_seed

        # The following fields are filled in by load538Forecast()
        self.seed = None
        self.region = None
        self.slot = None
        self.play_in = None
        self.forecast = None

    def __str__(self):
        return "%s %s" % (self.seed, self.name)

class Game(object):
    def __init__(self, gid: int):
        self.gid = gid
        self.winner = None
        self.team1 = None
        self.team2 = None

class Bracket(object):
    def __init__(self, bid: int):
        self.bid = bid
        self.owner = None
        self.slots = []

    # DEBUG : print just so I can verify the generator works.
    def __str__(self):
        ret = "Bracket: " + str(self.bid) + "\n"
        for slot in self.slots:
            ret += str(slot)
            ret += " "
            x = slot.game.gid
            # Add a new line for each round of tournament
            if (x and (not(x & (x - 1)))):
                ret += "\n"
        return ret

    # TODO : I am going to want to be able to write these to a file
    def export(self, path: str):
        pass

class Slot(object):
    def __init__(self, bracket: Bracket, winner: Team, game: Game):
        self.bracket = bracket
        self.winner = winner
        self.game = game
    
    def __str__(self):
        return "Game: %s | Winner: %s" % (self.game.gid, self.winner)