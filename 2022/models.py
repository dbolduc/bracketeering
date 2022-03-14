# These classes are the predecessors to Django Models

class Team(object):
    def __init__(self, name: str, overall_seed: int):
        self.name = name
        self.overall_seed = overall_seed

        # The following fields are filled in by load538Forecast()
        self.seed = None
        self.region = None
        self.slot = None
        self.forecast = None

    def __str__(self):
        return str(self.seed) + " " + self.name

class Game(object):
    def __init__(self, gid: int, team1: Team = None, team2: Team = None):
        self.gid = gid
        self.winner = None
        self.team1 = team1
        self.team2 = team2