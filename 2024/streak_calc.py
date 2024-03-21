# This thing calculates how many games it takes for each bracket to be unique. i.e. to have its own sequence. This is a prerequisite to winning the streak award.
# Well, that is the intention. I haven't actually tested the code. I write code good tho.
# TODO : Add this to the pre-draft cheat sheet.

year = "2024"

def loadStreak():
    path = year + '/data/streak.txt'
    lines = open(path).read().split('\n')
    return [int(gid) for gid in lines if not gid.startswith("#")]

streak_gids = loadStreak()

real_brackets = []
for i in range(1,33):
    b = open(year + "/data/brackets/" + str(i) + ".txt").read().split('\n')
    real_brackets.append(b)

uniqueness = {}

groups = [real_brackets]
for i, gid in enumerate(streak_gids):
    regroups = []
    for group in groups:
        winners = {}
        for bracket in group:
            winner = bracket[gid]
            if winner not in winners:
                winners[winner] = []
            winners[winner].append(bracket)
        for brackets in winners.values():
            if len(brackets) == 1:
                uniqueness[brackets[0][0]] = i+1
            else:
                regroups.append(brackets)
    groups = regroups

for b in real_brackets:
    print(uniqueness[b[0]])