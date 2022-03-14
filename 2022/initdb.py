# Run this file from top level folder with:
# ```sh
# python3 initdb.py
# ```

from models import Team, Game, Bracket, Slot
import math
import random
from collections import deque
import itertools

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
        teams_lookup[name].rating = float(vals[keys['team_rating']])
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

        # (For convenience computing team depth in a given bracket)
        team.first_game = games[gid]

    # TODO : My tentative hope is that I can read this file every day to update the full database.
    #        (Or if I am lucky, every few minutes, if 538 updates it that frequently (and doesn't lock me out))
    #
    #        So, what I might want to do is continue processing past the empty (initial) bracket,
    #        and see if I can set the winners of games that are already known.
    #
    #        For now though, let's initialize the future games.
    for gid in range(1, 32):
        games[gid] = Game(gid=gid)

    return games

def chalkCompare(game: Game) -> bool:
    return game.team1.overall_seed < game.team2.overall_seed

def antiChalkCompare(game: Game) -> bool:
    return not chalkCompare(game)

def absolute538Compare(game: Game) -> bool:
    return game.team1.rating > game.team2.rating

def prob538Compare(game: Game) -> bool:
    r1 = game.team1.rating
    r2 = game.team2.rating
    p1_wins = 1.0 / (1.0 + math.exp((r2-r1)*.175))
    return random.random() < p1_wins

def generateBracket(games_src, sorted_gids, winner_f, bid: int = 0):
    bracket = Bracket(bid)

    # TODO : comment is stale. delete or update or something.
    #
    # Let's reverse the list so that we are counting down to the championship game.
    # Let's also make a copy because we will be writing values to `Game` objects,
    # and we do not want the original to be affected.
    games = games_src.copy()
    for gid in sorted_gids:
        game = games[gid]
        team1_wins = winner_f(game)
        winner = game.team2
        if team1_wins:
            winner = game.team1

        # Add the slot to the bracket
        bracket.slots.appendleft(Slot(bracket, winner, game))

        # Propogate the winning team to the next round, unless this is the final game.
        if gid == 1:
            continue
        next_gid = gid // 2
        is_next_team1 = gid % 2 == 0
        if is_next_team1:
            games[next_gid].team1 = winner
        else:
            games[next_gid].team2 = winner

    return bracket

# Generate a cheat sheet with relevant information to make drafting easier.
def writeCheatSheet(brackets):
    path = "2022/data/cheat_sheet.txt"
    with open(path, "w+") as file:
        for bracket in brackets:
            str_chalk = str(round(bracket.calcChalkScore(chalk), 2))
            str_538 = str(round(bracket.calc538Score(), 2))

            # Extract the winners from the Elite Eight and on...
            #
            # I will just order the top 7 teams in a list with no repeats
            # then report them in order.
            # 
            # The top 7 teams are those that the bracket has winning in the final 15 games.
            seen = set()
            ordered = []
            for slot in itertools.islice(bracket.slots, 0, 15):
                if slot.winner.name in seen:
                    continue
                seen.add(slot.winner.name)
                ordered.append(str(slot.winner))

            # Write the information to the file
            file.write("ID: %s\n" % str(bracket.bid))
            file.write("Winner:       %s\n" % ordered[0])
            file.write("Runner Up:    %s\n" % ordered[1])
            file.write("Final Four:   %s\n" % ", ".join(ordered[2:4]))
            file.write("Elite Eight:  %s\n" % ", ".join(ordered[4:8]))
            file.write("Purdue Depth: %s\n" % bracket.teamDepth(teams_lookup["Purdue"]))
            file.write("VT Depth:     %s\n" % bracket.teamDepth(teams_lookup["Virginia Tech"]))
            file.write("Chalk Score:  %s\n" % str_chalk)
            file.write("538 Score:    %s\n" % str_538)
            file.write("\n")

# Write in a different format that allows sorting on (Chalk|538) Score / (VT|Purdue) Depth / Winner / etc.
def writeSortableCheatSheet(brackets):
    path = "2022/data/sortable_cheat_sheet.csv"
    with open(path, "w+") as file:
        #headers=["ID", "Chalk Score", "538 Score", "Winner", "Runner Up", "Purdue Depth", "VT Depth"]
        file.write("ID,Chalk Score,538 Score,Winner,Runner Up,Purdue Depth,VT Depth\n")
        for bracket in brackets:
            str_chalk = str(round(bracket.calcChalkScore(chalk), 2))
            str_538 = str(round(bracket.calc538Score(), 2))
            purdue = bracket.teamDepth(teams_lookup["Purdue"], True)
            vt = bracket.teamDepth(teams_lookup["Virginia Tech"], True)

            # Extract the winners from the Elite Eight and on...
            # I will just order the top 7 teams in a list with no repeats
            # then report them in order.
            seen = set()
            ordered = []
            for slot in itertools.islice(bracket.slots, 0, 3):
                if slot.winner.name in seen:
                    continue
                seen.add(slot.winner.name)
                ordered.append(str(slot.winner))

            # Write the information to the file
            file.write("%s,%s,%s,%s,%s,%s,%s\n" % (str(bracket.bid), str_chalk, str_538, ordered[0], ordered[1], purdue, vt))


# ======== Main Execution ============

teams, teams_lookup = loadTeams()
load538Forecast(teams_lookup)
games = loadGames(teams)
sorted_gids = sorted(games.keys(), reverse=True)
chalk = generateBracket(games, sorted_gids, chalkCompare)
anti_chalk = generateBracket(games, sorted_gids, antiChalkCompare)
#absolute_538 = generateBracket(games, sorted_gids, absolute538Compare)

# ======== Loading Brackets ============

# TODO : Consider unfactoring the generation into a dedicated method (for cleanliness)
brackets = []
kGenerateBrackets = False
kBracketsPerOwner = 4
kNumOwners = 8
kTotalBrackets = kBracketsPerOwner * kNumOwners
for i in range(kTotalBrackets):
    bid = i + 1 # Brackets are 1-indexed
    path = "2022/data/brackets/%s.txt" % bid
    if kGenerateBrackets:
        b = generateBracket(games, sorted_gids, prob538Compare, bid)
        b.writeToFile(path)
    b = Bracket.readFromFile(teams_lookup, games, path)
    brackets.append(b)

writeCheatSheet(brackets)
writeSortableCheatSheet(brackets)