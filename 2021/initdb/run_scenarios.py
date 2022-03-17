from bracketeering.models import *

probs = {}
probs_file = open('initdb/data/e8_probs.csv').read()
lines = probs_file.split('\n')
for line in lines:
    if line:
        vals = line.split(',')
        probs[(vals[0], vals[1])] = float(vals[2])
        probs[(vals[1], vals[0])] = 1. - float(vals[2])

points_per_game = [5, 5, 5, 5, 8, 8, 13] # [G7, G6, ... , G1]
brackets = Bracket.objects.all().order_by('bid')
final_7_games = Game.objects.filter(gid__lte=7).order_by('-gid')
for g in final_7_games:
    print(g.gid, g.get_matchup_str())

owners = {} # owners[name] = [b1, b2, b3, b4]
slots = {} # slots[(bid, j)] = slot. j is related to gid
for i, b in enumerate(brackets):
    # init owners
    name = b.owner.name
    if name not in owners:
        owners[name] = []
    owners[b.owner.name].append(b.bid) 

    # init slots
    for j, g in enumerate(final_7_games):
        slots[(b.bid, j)] = Slot.objects.get(bracket=b, game=g)

scenarios = []
for i in range(128):
    # generate winners list. calculate probability of outcome.
    winners = []
    prob = 1.
    for j in range(7):
        g = final_7_games[j]
        if g.winner:
            winners.append(g.winner)
        else:
            if g.team1:
                team1 = g.team1
            else:
                team1 = winners[2 * j - 8]
            if g.team2:
                team2 = g.team2
            else:
                team2 = winners[2 * j - 7]


            if i & 1 << j:
                prob *= probs[(team1.name, team2.name)]
                winners.append(team1)
            else:
                prob *= probs[(team2.name, team1.name)]
                winners.append(team2)
    print(winners)


    # calculate bracket pts for each bracket
    bracket_pts = []
    for b in brackets:
        hits = []
        for j, w in enumerate(winners):
            # NOTE : the space could be cut down significantly here. but brute force is fine.
            #s = Slot.objects.get(bracket=b, game=final_7_games[j])
            s = slots[(b.bid, j)]
            hits.append(s.winner == w)

        # dirty points calculation
        cur_pts = b.get_points()
        for j in range(7):
            if hits[j]:
                cur_pts += points_per_game[j]
        if hits[0] and hits[1] and hits[2] and hits[3]: # Final Four bonus
            cur_pts += 5
        if hits[4] and hits[5]:
            cur_pts += 5
        bracket_pts.append(cur_pts)
        #print(b.bid, cur_pts)


    # process owner winnings
    best_bracket = [0, "", ""] # ["owner", pts, "bid"] strings separated by pipes in case of tie
    best_sum_of_2 = [0, "", ""] # ["owner", pts, "bid1,bid2"] strings separated by pipes in case of tie

    for owner in owners:
        owner_bs = []
        for bid in owners[owner]:
            owner_bs.append((bracket_pts[bid - 1], bid)) # bracket_index + 1 = bracket's bid
        owner_bs.sort()

        if owner_bs[-1][0] > best_bracket[0]:
            best_bracket = [owner_bs[-1][0], owner, str(owner_bs[-1][1])]
        elif owner_bs[-1][0] == best_bracket[0]:
            best_bracket[1] += "|" + owner
            best_bracket[2] += "|" + str(owner_bs[-1][1])

        owner_sum_of_2 = owner_bs[-1][0] + owner_bs[-2][0]
        if owner_sum_of_2 > best_sum_of_2[0]:
            best_sum_of_2 = [owner_sum_of_2, owner, str(owner_bs[-1][1]) + "&" + str(owner_bs[-2][1])]
        elif owner_sum_of_2 == best_sum_of_2[0]:
            best_sum_of_2[1] += "|" + owner
            best_sum_of_2[2] += "|" + str(owner_bs[-1][1]) + "&" + str(owner_bs[-2][1])

        #print(owner, owner_bs)
    #print(best_bracket)
    #print(best_sum_of_2)

    scenarios.append([winners, prob, best_sum_of_2, best_bracket])


# consolidate all scenarios ?
headers = [
        'FF Midwest (G7)',
        'FF South (G6)',
        'FF East (G5)',
        'FF West (G4)',
        'Right Half (G3)',
        'Left Half (G2)',
        'Champion (G1)',
        'Probability',
        'Sum of 2 Points',
        'Sum of 2 Winner',
        'Sum of 2 ID1+ID2',
        'Best Bracket Points',
        'Best Bracket Winner',
        'Best Bracket ID']

f = open('initdb/scenarios.csv', 'w')
#f.write('FF Midwest (G7),FF South (G6),FF East (G5),FF West (G4),Right Half (G3),Left Half (G2),Champion (G1),Probability,Sum of 2 Winner,Sum of 2 Points,Sum of 2 ID1,Sum of 2 ID2,Best Bracket Winner,Best Bracket Points,Best Bracket ID\n')
for header in headers:
    f.write(header)
    f.write(",")
f.write("\n")

for scenario in scenarios:
    for winner in scenario[0]:
        f.write(winner.name)
        f.write(",")
    f.write(str(scenario[1]))
    f.write(",")
    for val in scenario[2]:
        f.write(str(val))
        f.write(",")
    for val in scenario[3]:
        f.write(str(val))
        f.write(",")
    f.write("\n")

f.close()



