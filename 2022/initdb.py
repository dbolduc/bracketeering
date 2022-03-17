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
# Returns [total points, initial streak]
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

    # Initial Streak
    initial_streak = 0
    for gid in streak_gids:
        slot_index = gid - 1 # Slots are 0-indexed; Games are 1-indexed.
        # TODO : I do not understand how, but these are different objects
        # Let's compare team name
        #if b1.slots[slot_index].winner == b2.slots[slot_index].winner:
        if b1.slots[slot_index].winner.name == b2.slots[slot_index].winner.name:
            initial_streak += 1
        else:
            break
    
    return [total_points, initial_streak]

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
# returns h[bid] = [best bracket wins, streak wins]
#
# TODO : generalize. Eventually I would want to operate on a "League" and compute all payouts.
def MC(n: int, brackets, streak_gids):
    point_bucket = {}
    streak_bucket = {}
    for bracket in brackets:
        point_bucket[bracket.bid] = 0.0
        # TODO : For now we will just share the splits.
        # The real rules will keep going until one remains.
        streak_bucket[bracket.bid] = 0.0

    for _ in range(n):
        mc = generateBracket(games, sorted_gids, prob538Compare)
        max_points = 0
        max_points_bids = []
        max_streak = 0
        max_streak_bids = []
        for bracket in brackets:
            points, streak = bracketCompare(bracket, mc, streak_gids)
            if points > max_points:
                max_points = points
                max_points_bids = [bracket.bid]
            elif points == max_points:
                max_points_bids.append(bracket.bid)
            if streak > max_streak:
                max_streak = streak
                max_streak_bids = [bracket.bid]
            elif streak == max_streak:
                max_streak_bids.append(bracket.bid)

        # Accumulate results into buckets
        point_sharers = len(max_points_bids)
        for bid in max_points_bids:
            point_bucket[bid] += 1.0 / point_sharers
        streak_sharers = len(max_streak_bids)
        for bid in max_streak_bids:
            streak_bucket[bid] += 1.0 / streak_sharers
    
    return [point_bucket, streak_bucket]
        

    

# ======== Main Execution ============

teams, teams_lookup = loadTeams()
load538Forecast(teams_lookup)
games = loadGames(teams)
sorted_gids = sorted(games.keys(), reverse=True)
streak_gids = loadStreak()
chalk = generateBracket(games, sorted_gids, chalkCompare)
#anti_chalk = generateBracket(games, sorted_gids, antiChalkCompare)
#absolute_538 = generateBracket(games, sorted_gids, absolute538Compare)

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

for owner in owners.values():
    print(owner.name)
    for bracket in owner.brackets:
        team = bracket.slots[-4].winner
        print("Bracket %s Winner: %s | Depth: %s" % (bracket.bid, team.name, bracket.teamDepth(team)))
    print()

#x = bracketCompare(brackets[1], brackets[1])
#print(x)
#x = bracketCompare(brackets[1], brackets[2])
#print(x)

#x = MC(10000, brackets, streak_gids)
#print("\n\n")
#print("Points: ", x[0])
#print("\n\n")
#print("Streaks: ", x[1])

