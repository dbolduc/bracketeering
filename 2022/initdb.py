# Run this file from top level folder with:
# ```sh
# python3 initdb.py
# ```

from models import Team, Game

# ======== Initialization Methods ============

def loadTeams():
    path = '2022/data/seeds.txt'
    team_names = open(path).read().split('\n')
    teams = []
    teams_lookup = {}
    current_seed = 1
    for team_name in team_names:
        if not team_name or team_name[0] == '#':
            continue
        team = Team(overall_seed=current_seed, name=team_name)
        teams.append(team)
        teams_lookup[team_name] = team
        current_seed += 1
    return teams, teams_lookup

# Read 538's projection data sourced from:
# https://projects.fivethirtyeight.com/march-madness-api/2022/fivethirtyeight_ncaa_forecasts.csv
#
# Modifies the `Team` objects passed into this function to add: seeds, regions, slots, forecasts
def load538Forecast(teams_lookup):
    path = '2022/data/fivethirtyeight_ncaa_forecasts.csv'
    raw_data = open(path).read().split('\n')

    # Interact with the headers, so the code is easier to read.
    keys = {}
    headers = raw_data[0].split(',')
    for i, header in enumerate(headers):
        keys[header] = i

    # The forecast appends past predictions as the tournament progresses.
    # Skip the header, and only use the most recent data. (The first 68 lines).
    for line in raw_data[1 : 69]:
        vals = line.split(',')
        name = vals[keys['team_name']]
        teams_lookup[name].forecast = [float(x) for x in vals[keys['rd1_win'] : keys['rd7_win'] + 1]]
        teams_lookup[name].seed = vals[keys['team_seed']]
        teams_lookup[name].region = vals[keys['team_region']]
        teams_lookup[name].slot = int(vals[keys['team_slot']])
        teams_lookup[name].play_in = vals[keys['playin_flag']] == "1"

# Define the official bracket matchups, by initializing a set of games.
# The information for the bracket is contained in the `team_slot` fields provided by 538.
#
# Essentially, I will loop over the teams, and determine what `Game` they play in, and
# whether they are `team1` or `team2` in that `Game`.
def loadGames(teams):
    games = {}

    # 538 orders the regions differently than I do.
    offsets = {
        "West": 32,
        "East": 32,
        "South": 24,
        "Midwest": 40,
    }

    for team in teams:
        gid = team.slot // 4 + offsets[team.region]
        is_team1 = team.slot % 4 == 0

        # First Four teams are special. They play for the team2 slot of the game in the Round of 64.
        if team.play_in:
            gid = 2 * gid + 1
            is_team1 = team.slot % 2 == 0

        # Create Game if it does not yet exist
        if gid not in games:
            games[gid] = Game(gid=gid)
        
        # Set this teams entry
        if is_team1:
            games[gid].team1 = team
        else:
            games[gid].team2 = team

        # TODO : My tentative hope is that I can read this file every day to update the full database.
        #        (Or if I am lucky, every few minutes, if 538 updates it that frequently (and doesn't lock me out))
        #
        #        So, what I might want to do is continue processing past the empty (initial) bracket,
        #        and see if I can set the winners of games that are already known.
    return games

# ======== Main Execution ============

teams, teams_lookup = loadTeams()
load538Forecast(teams_lookup)
games = loadGames(teams)

# DEBUG : print
sorted_games = sorted(games.values(), key=lambda x: x.gid)
for game in sorted_games:
    print("Game: ", game.gid)
    print("Team1: ", game.team1)
    print("Team2: ", game.team2)
    print("")