# Run this file from top level folder with:
# ```sh
# python3 initdb.py
# ```

from models import Team, Game, Bracket, Slot, Owner, kPointsPerRound
import math
import random
from collections import deque
import itertools
import copy

# ======== Initialization Methods ============

def loadDraft(brackets):
    owners = {}
    path = '2022/data/draft.csv'
    picks = open(path).read().split('\n')
    for pick in picks:
        if not pick or pick[0] == '#':
            continue
        owner, bid = pick.split(',')
        if owner not in owners:
            owners[owner] = Owner(owner)

        bracket = brackets[int(bid) - 1] # Brackets are 1-indexed
        bracket.owner = owner
        owners[owner].brackets.append(bracket)
    return owners

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
# (On Windows) pull the latest version from top level directory with:
# curl.exe --output 2022\data\fivethirtyeight_ncaa_forecasts.csv --url https://projects.fivethirtyeight.com/march-madness-api/2022/fivethirtyeight_ncaa_forecasts.csv
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

# Returns an ordered list of Game IDs that represent the streak order
def loadStreak():
    path = '2022/data/streak.txt'
    lines = open(path).read().split('\n')
    return [int(gid) for gid in lines if not gid.startswith("#")]

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

def truthPlus538Compare(game: Game) -> bool:
    if game.winner:
        return game.winner == game.team1
    return prob538Compare(game)

def generateBracket(games_src, sorted_gids, winner_f, bid: int = 0):
    bracket = Bracket(bid)

    # TODO : comment is stale. delete or update or something.
    #
    # Let's reverse the list so that we are counting down to the championship game.
    # Let's also make a copy because we will be writing values to `Game` objects,
    # and we do not want the original to be affected.
    games = copy.deepcopy(games_src)
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
def writeCheatSheet(brackets, streak_gids):
    path = "2022/data/cheat_sheet.txt"
    with open(path, "w+") as file:
        for bracket in brackets:
            str_chalk = str(round(bracket.calcChalkScore(chalk), 2))
            str_538 = str(round(bracket.calc538Score(), 2))
            str_heat = str(round(bracket.calcHeatScore(streak_gids), 4))

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
            file.write("HEAT Score:    %s\n" % str_heat)
            file.write("\n")

# Write in a different format that allows for sorting
def writeSortableCheatSheet(brackets, streak_gids):
    path = "2022/data/sortable_cheat_sheet.csv"
    with open(path, "w+") as file:
        file.write("ID,Chalk Score,538 Score,HEAT Score,Winner,Runner Up,Purdue Depth,VT Depth,UCLA Depth\n")
        for bracket in brackets:
            str_chalk = str(round(bracket.calcChalkScore(chalk), 2))
            str_538 = str(round(bracket.calc538Score(), 2))
            str_heat = str(round(bracket.calcHeatScore(streak_gids), 4))
            purdue = bracket.teamDepth(teams_lookup["Purdue"], True)
            vt = bracket.teamDepth(teams_lookup["Virginia Tech"], True)
            ucla = bracket.teamDepth(teams_lookup["UCLA"], True)

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
            file.write("%s,%s,%s,%s,%s,%s,%s,%s,%s\n" % (str(bracket.bid), str_chalk, str_538, str_heat, ordered[0], ordered[1], purdue, vt, ucla))

# ======== Monte Carlo Simulation ============

def bonusIndex(gid: int):
    round = 7 - gid.bit_length()
    # There are no bonuses awarded for getting the First 4 games (round 0) correct
    # or for getting the overall Winner correct (round 6)
    if round == 0 or round == 6:
        return None
    
    if round == 5: # Final 4 winners aka National Championship participants.
        return 1

    if round == 4: # Elite 8 winners aka Final 4 participants.
        return 2
    
    # TODO : Document. I am going to just assign each bonus a unique ID.
    # TODO : remember where this calculation comes from. Give examples?
    return 4 * round + gid // pow(2, 4 - round) - 3 # Duh...

# TODO : I think this method is associative
# Returns total points
def bracketCompare(b1: Bracket, b2: Bracket, streak_gids):
    # Game Points + Bonuses
    total_points = 0
    bonuses = {}
    for s1, s2 in zip(b1.slots, b2.slots):
        bonus_index = bonusIndex(s1.game.gid)
        if bonus_index and bonus_index not in bonuses:
            bonuses[bonus_index] = True

        # TODO : I do not understand how, but these are different objects
        # Let's compare team name
        #if s1.winner == s2.winner:
        if s1.winner.name == s2.winner.name:
            total_points += kPointsPerRound[s1.game.round]
        elif bonus_index:
            bonuses[bonus_index] = False

    # Sum Bonuses
    for bonus_achieved in bonuses.values():
        if bonus_achieved:
            total_points += 5
    
    return total_points

# TODO : Document more and better
# TODO (with infinite time) : Turn this into a Dataproc job that can run in parallel.
# 
# For now it will generate n brackets based on 538's pre-tournament projections.
# It does not update team scores as the simulation progresses.
# (E.g. If you know Team A has beaten Team B, then you will think Team A is a little bit stronger in the next round)
#
# n = number of simulations
# brackets = list of brackets
# ################f = function over brackets
#
#
# TODO : Return value is stale. But I probably want what the documentation says, not what the code says.
# returns h[bid] = [sum_2 wins, best bracket wins]
#
# TODO : generalize. Eventually I would want to operate on a "League" and compute all payouts.
def MC(n: int, owners, streak_gids):
    # Initialize
    owner_sum_2_wins = {}
    owner_single_wins = {}
    for owner_name in owners.keys():
        owner_sum_2_wins[owner_name] = 0.0
        owner_single_wins[owner_name] = 0.0
        
    for _ in range(n):
        mc = generateBracket(games, sorted_gids, truthPlus538Compare)
        sum_2_owners = []
        sum_2_score = 0
        single_owners = []
        single_score = 0

        # Determine win shares
        for owner_name, owner in owners.items():
            points = [bracketCompare(bracket, mc, streak_gids) for bracket in owner.brackets]
            points.sort(reverse=True)
            sum_2 = points[0] + points[1]
            single = points[0]
            if sum_2 > sum_2_score:
                sum_2_score = sum_2
                sum_2_owners = [owner_name]
            elif sum_2 == sum_2_score:
                sum_2_owners.append(owner_name)
            if single > single_score:
                single_score = single
                single_owners = [owner_name]
            elif single == single_score:
                single_owners.append(owner_name)
        
        # Accumulate
        for sum_2_winner in sum_2_owners:
            owner_sum_2_wins[sum_2_winner] += 1.0 / len(sum_2_owners)
        for single_winner in single_owners:
            owner_single_wins[single_winner] += 1.0 / len(single_owners)
        
    return [owner_sum_2_wins, owner_single_wins]
        

    

# ======== Main Execution ============

teams, teams_lookup = loadTeams()
load538Forecast(teams_lookup)
games = loadGames(teams)
sorted_gids = sorted(games.keys(), reverse=True)
streak_gids = loadStreak()
chalk = generateBracket(games, sorted_gids, chalkCompare)

# ======== Loading Brackets ============

# TODO : Consider unfactoring the generation into a dedicated method (for cleanliness)
brackets = []
kGenerateBrackets = False
kGenerateCheatSheets = False
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

kGenerateCheatSheets = False
if kGenerateCheatSheets:
    writeCheatSheet(brackets, streak_gids)
    writeSortableCheatSheet(brackets, streak_gids)

owners = loadDraft(brackets)

# Catch up with the games that have happened
for gid in sorted_gids:
    game = games[gid]
    if not game.team1 or not game.team2:
        continue
    if game.team1.forecast[game.round] == 1:
        game.winner = game.team1
    if game.team2.forecast[game.round] == 1:
        game.winner = game.team2
    
    # Propogate the winning team to the next round, unless this is the final game.
    if gid == 1:
        continue
    next_gid = gid // 2
    is_next_team1 = gid % 2 == 0
    if is_next_team1:
        games[next_gid].team1 = game.winner
    else:
        games[next_gid].team2 = game.winner

# TEMP : Catch up with today's games.
#games[25].winner = games[25].team2 # Houston < Illinois

n = 10000
live_game = games[25]
for game_winner in [live_game.team1, live_game.team2]:
    live_game.winner = game_winner

    sims = MC(n, owners, streak_gids)
    print("IF %s WINS | n = %s" % (game_winner, n))
    print("Owner".ljust(10), "Sum of 2".ljust(10), "Best".ljust(10), "$$$".ljust(10))
    for owner in owners.values():
        sum_2 = sims[0][owner.name]
        single = sims[1][owner.name]
        yuge = (sum_2 * 100 + single * 20) / n
        print(owner.name.ljust(10), str(round(sum_2, 2)).ljust(10), str(round(single, 2)).ljust(10), str(round(yuge, 2)).ljust(10))
    print()