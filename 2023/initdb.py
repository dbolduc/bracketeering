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
    path = '2023/data/draft.csv'
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
    path = '2023/data/seeds.txt'
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
# https://projects.fivethirtyeight.com/march-madness-api/2023/fivethirtyeight_ncaa_forecasts.csv
#
# (On Windows) pull the latest version from top level directory with:
# curl.exe --output 2023\data\fivethirtyeight_ncaa_forecasts.csv --url https://projects.fivethirtyeight.com/march-madness-api/2023/fivethirtyeight_ncaa_forecasts.csv
#
# Modifies the `Team` objects passed into this function to add: seeds, regions, slots, forecasts
def load538Forecast(teams_lookup):
    path = '2023/data/fivethirtyeight_ncaa_forecasts.csv'
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
        "West": 40,
        "East": 32,
        "South": 32,
        "Midwest": 24,
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
    path = '2023/data/streak.txt'
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
    path = "2023/data/cheat_sheet.txt"
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
            file.write("UVA Depth:    %s\n" % bracket.teamDepth(teams_lookup["Virginia"]))
            #file.write("VT Depth:     %s\n" % bracket.teamDepth(teams_lookup["Virginia Tech"]))
            file.write("Chalk Score:  %s\n" % str_chalk)
            file.write("538 Score:    %s\n" % str_538)
            file.write("HEAT Score:   %s\n" % str_heat)
            file.write("\n")

# Write in a different format that allows for sorting
def writeSortableCheatSheet(brackets, streak_gids):
    path = "2023/data/sortable_cheat_sheet.csv"
    with open(path, "w+") as file:
        file.write("ID,Chalk Score,538 Score,HEAT Score,Winner,Runner Up,Purdue Depth,UVA Depth,UCLA Depth,VCU Depth\n")
        for bracket in brackets:
            str_chalk = str(round(bracket.calcChalkScore(chalk), 2))
            str_538 = str(round(bracket.calc538Score(), 2))
            str_heat = str(round(bracket.calcHeatScore(streak_gids), 4))
            purdue = bracket.teamDepth(teams_lookup["Purdue"], True)
            uva = bracket.teamDepth(teams_lookup["Virginia"], True)
            #vt = bracket.teamDepth(teams_lookup["Virginia Tech"], True)
            vcu = bracket.teamDepth(teams_lookup["Virginia Commonwealth"], True)
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
            file.write("%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" % (str(bracket.bid), str_chalk, str_538, str_heat, ordered[0], ordered[1], purdue, uva, ucla, vcu))

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
def bracketCompare(b1: Bracket, b2: Bracket):
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
alex_sum_2_bracket_bucket = {}
alex_single_bracket_bucket = {}
#for bid in [9, 15, 1, 20]:
for bid in [5, 17, 2, 30]: # axally darren
    alex_sum_2_bracket_bucket[bid] = 0.0
    alex_single_bracket_bucket[bid] = 0.0

# returns {owner1: [[b1_pts, b1_id], [b2_pts, b2_id]], owner2: [b1, b2], ...}
def ownerBest2Brackets(truth: Bracket, owners):
    h = {}
    for o, v in owners.items():
        pts_ids = [[bracketCompare(truth, b), b.bid] for b in v.brackets]
        pts_ids.sort(reverse=True)
        h[o] = pts_ids[:2]
    return h

# returns {owner1: [b1, b2], owner2: [b1, b2], ...} that share the prize
def sumOf2Bonus(truth: Bracket, owners):
    h = ownerBest2Brackets(truth, owners)
    max_sum_2 = 0
    sum_2_owners = {}
    for o, v in h.items():
        score = v[0][0] + v[1][0]
        if score > max_sum_2:
            max_sum_2 = score
            sum_2_owners = {}
            sum_2_owners[o] = [v[0][1], v[1][1]]
        elif score == max_sum_2:
            sum_2_owners[o] = [v[0][1], v[1][1]]
    return sum_2_owners


# returns {owner1: b1, owner2: b1, ...} that share the prize
def singleBonus(truth: Bracket, owners):
    h = ownerBest2Brackets(truth, owners)
    max_single = 0
    single_owners = {}
    for o, v in h.items():
        score = v[0][0]
        if score > max_single:
            max_single = score
            single_owners = {}
            single_owners[o] = v[0][1]
        elif score == max_single:
            single_owners[o] = v[0][1]
    return single_owners

# returns {owner1, owner2, ...} that share the prize
def eliteEightBonus(truth: Bracket, owners):
    h = {} # h[owner_name] = [owner best, owner worst, owner 2nd best, owner 2nd worst] 
    for o, v in owners.items():
        ee = []
        for b in v.brackets:
            ee.append(0)
            # Elite Eight winners = Games [8, 16)
            for g in range(8, 16):
                if b.slots[g-1].winner.name == truth.slots[g-1].winner.name:
                    ee[-1] += 1
        ee.sort()
        h[o] = [ee[3], ee[0], ee[2], ee[1]]
        print(o, h[o])
    
    owner_set = set(owners.keys())
    for i in range(4):
        next_owner_set = set()
        pick_max = i % 2 == 0
        if pick_max:
            ee = 0
            for o in owner_set:
                if h[o][i] > ee:
                    ee = h[o][i]
                    next_owner_set = set([o])
                elif h[o][i] == ee:
                    next_owner_set.add(o)
        else:
            ee = 8
            for o in owner_set:
                if h[o][i] < ee:
                    ee = h[o][i]
                    next_owner_set = set([o])
                elif h[o][i] == ee:            
                    next_owner_set.add(o)
        
        # update remaining owners
        owner_set = next_owner_set

        # break, if we have narrowed it down to one owner
        if len(owner_set) == 1:
            break
    
    return owner_set

def MC(n: int, owners, winner_f):
    # Initialize
    owner_sum_2_wins = {}
    owner_single_wins = {}
    for owner_name in owners.keys():
        owner_sum_2_wins[owner_name] = 0.0
        owner_single_wins[owner_name] = 0.0
        
    for _ in range(n):
        mc = generateBracket(games, sorted_gids, winner_f)
        sum_2_owners = []
        sum_2_score = 0
        single_owners = []
        single_score = 0

        # Determine win shares
        for owner_name, owner in owners.items():
            points = [[bracketCompare(bracket, mc), bracket.bid] for bracket in owner.brackets]
            points.sort(reverse=True)
            sum_2 = points[0][0] + points[1][0]
            single = points[0][0]
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
chalk = generateBracket(games, sorted_gids, chalkCompare)
streak_gids = loadStreak()

# ======== Loading Brackets ============

# TODO : Consider unfactoring the generation into a dedicated method (for cleanliness)
brackets = []
kGenerateBrackets = False
kGenerateCheatSheets = True
kBracketsPerOwner = 4
kNumOwners = 8
kTotalBrackets = kBracketsPerOwner * kNumOwners
for i in range(kTotalBrackets):
    bid = i + 1 # Brackets are 1-indexed
    path = "2023/data/brackets/%s.txt" % bid
    if kGenerateBrackets:
        b = generateBracket(games, sorted_gids, prob538Compare, bid)
        b.writeToFile(path)
    b = Bracket.readFromFile(teams_lookup, games, path)
    brackets.append(b)

if kGenerateCheatSheets:
    writeCheatSheet(brackets, streak_gids)
    writeSortableCheatSheet(brackets, streak_gids)

# Don't proceed if have not done the draft yet.
exit(0)

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

# TEMP : Elite Eight
elite_eight_shares = {}
for o in owners:
    elite_eight_shares[o] = [0.0, 0.0] # [total, weighted]

games[11].winner = games[11].team2   # Purdue < St. Peter's
games[14].winner = games[14].team1   # Kansas > Providence
games[10].winner = games[10].team1   # UNC > UCLA
games[15].winner = games[15].team2   # ISU > Miami

sim_gids = [7,6,5,4,3,2,1]
sims_per_scenario = 1 #5000
scenarios = 1 << len(sim_gids) # 2^|G|
# Process sim_gids into a better form:
sim_gids_lookup = {}
for i, gid in enumerate(sim_gids):
    sim_gids_lookup[gid] = i

# Loop over scenarios. the ith bit of scenario says who wins the ith game of sim_gids
for scenario in range(scenarios):
    # Define who wins
    def f(game: Game) -> bool:
        if game.gid in sim_gids_lookup:
            i = sim_gids_lookup[game.gid]
            return (scenario >> i) & 1 == 1
        return truthPlus538Compare(game)
    
    # Run simulation
    #sims = MC(sims_per_scenario, owners, f)

    # Determine raw probability of this happening
    p = 1.0
    for i, gid in enumerate(sim_gids):
        game = games[gid]


        # TODO : Would want to just look at the mc bracket's slots[2*n] and slots[2*n+1]
        # DEBUG
        p = 1/128
        continue



        r1 = game.team1.rating
        r2 = game.team2.rating
        p1_wins = 1.0 / (1.0 + math.exp((r2-r1)*.175))
        team1_wins = (scenario >> i) & 1 == 1
        if team1_wins:
            p *= p1_wins
        else:
            p *= (1.0 - p1_wins)

    # Print things nicely
    # TODO : Calculate probability of scenario happening?
    scenario_winners = []
    for i, gid in enumerate(sim_gids):
        team1_wins = (scenario >> i) & 1 == 1
        if team1_wins:
            scenario_winners.append(str(games[gid].team1))
        else:
            scenario_winners.append(str(games[gid].team2))

    #print("IF", " AND ".join(scenario_winners), "(p=%s)" % (str(round(p, 5))))
    # DEBUG : Elite Eight : regenerate bracket
    mc = generateBracket(games, sorted_gids, f)
    #ee = eliteEightBonus(mc, owners)
    #ee_winner_str = "|".join([w for w in ee])
    #print(",".join([ee_winner_str, str(p)] + scenario_winners))

    mc_winners = [str(mc.slots[i-1].winner) for i in sim_gids]
    sum_2 = sumOf2Bonus(mc, owners)
    sum_2_winners = "|".join(["%s: %s+%s" % (o, v[0], v[1]) for o, v in sum_2.items()])
    single = singleBonus(mc, owners)
    single_winners = "|".join(["%s: %s" % (o, v) for o, v in single.items()])
    print(",".join([sum_2_winners, single_winners, str(p)] + mc_winners))

    #for o in ee:
    #    elite_eight_shares[o][0] += 1.0 / len(ee)
    #    elite_eight_shares[o][1] += p / len(ee)
    #print("")
    continue

    print("OWNER".ljust(10), "SUM OF 2".ljust(10), "BEST".ljust(10), "$$$".ljust(10))
    for owner in owners.values():
        sum_2 = sims[0][owner.name]
        single = sims[1][owner.name]
        yuge = (sum_2 * 100 + single * 20) / sims_per_scenario
        print(owner.name.ljust(10), str(round(sum_2, 2)).ljust(10), str(round(single, 2)).ljust(10), str(round(yuge, 2)).ljust(10))
    print()

#print("Elite Eight Bonus Scenarios")
#print("OWNER".ljust(10), "Total".ljust(10), "Weighted".ljust(10))
#for owner in owners.values():
#    w0 = elite_eight_shares[owner.name][0]
#    w1 = elite_eight_shares[owner.name][1] * 16
#    print(owner.name.ljust(10), str(round(w0, 2)).ljust(10), str(round(w1, 2)).ljust(10))
#print()
