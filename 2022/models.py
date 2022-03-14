# These classes are the predecessors to Django Models

from collections import deque

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

        # The following fields are filled in by loadGames()
        self.first_game = None

    def __str__(self):
        return "%s %s" % (self.seed, self.name)

class Game(object):
    def __init__(self, gid: int):
        self.gid = gid
        self.winner = None
        self.team1 = None
        self.team2 = None

class Bracket(object):
    def __init__(self, bid: int = 0):
        self.bid = bid
        self.owner = None
        self.slots = deque()

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

    def writeToFile(self, path: str):
        with open(path, "w+") as file:
            file.write("%s" % str(self.bid))
            file.writelines(["\n%s,%s" % (str(s.game.gid),s.winner.name) for s in self.slots])

    def readFromFile(self, teams_lookup, games, path: str):
        lines = open(path).read().split('\n')
        for i, line in enumerate(lines):
            if i == 0:
                self.bid = int(line)
                continue
            [gid, team_name] = line.split(',')
            self.slots.append(Slot(self, teams_lookup[team_name], games[int(gid)]))

    # TODO : I am not sure this should be a member function
    def teamDepth(self, team: Team):
        # Skip this case where game id != slot index.
        # The only teams I care about are VT and Purdue.
        if team.play_in:
            return "Who cares?"

        round = 0
        gid = team.first_game.gid
        slot = self.slots[gid - 1] # gid is 1-indexed; self.slots is 0-indexed.
        while slot.winner == team:
            round += 1
            gid //= 2
            if gid < 0:
                break
            slot = self.slots[gid - 1]
        
        return ["Round of 64", "Round of 32", "Sweet 16", "Elite 8", "Final 4", "Championship", "Winner"][round]

    # TODO : consolidate cheat sheet information
    def cheat_sheet(self):
        pass

class Slot(object):
    def __init__(self, bracket: Bracket, winner: Team, game: Game):
        self.bracket = bracket
        self.winner = winner
        self.game = game
    
    def __str__(self):
        return "Game: %s | Winner: %s" % (self.game.gid, self.winner)