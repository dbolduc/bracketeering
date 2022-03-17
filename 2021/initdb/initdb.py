from bracketeering.models import Owner, Team, Bracket, Game, Slot

#print(Owner.objects.all())

def deleteAll():
    print("Deleting all table content")
    Owner.objects.all().delete()
    Team.objects.all().delete()
    Bracket.objects.all().delete()
    Slot.objects.all().delete()
    Game.objects.all().delete()

def loadTeams():
    print("Loading Teams...")
    path = 'initdb/data/seeds.txt'
    team_strs = open(path).read().split('\n')
    for i, name in enumerate(team_strs):
        overall_seed = i + 1
        n = 3
        if overall_seed > 44:
            n = 1
        if overall_seed > 66:
            n = -1
        seed = (overall_seed + n)//4
        team = Team(overall_seed=overall_seed, seed=seed, name=name)
        team.save()
    #print(Team.objects.all())

def loadGames():
    path = 'initdb/data/games.csv'
    lines = open(path).read().split('\n')
    h = {}
    for i, line in enumerate(lines):
        if line == '':
            continue
        gid_str, name = line.split(',')
        gid = int(gid_str)
        if gid not in h:
            h[gid] = []
        h[gid].append(name)

    for gid in range(1, 64):
        game = Game(gid=gid)
        if gid in h:
            game.team1 = Team.get_by_name(h[gid][0])
            if h[gid][1] != 'None':
                game.team2 = Team.get_by_name(h[gid][1])
        game.save()
    for gid in range(65, 97, 8):
        team1 = Team.get_by_name(h[gid][0])
        team2 = Team.get_by_name(h[gid][1])
        game = Game(gid=gid, team1=team1, team2=team2)
        game.save()
    #print(Game.objects.all())



def loadOwners():
    print("Loading Owners...")
    for in_name in ["Alex", "Austin", "Bill", "Daniel", "Darren", "Mookie", "Sangburm"]:
        owner = Owner(name=in_name)
        owner.save()
    #print(Owner.objects.all())

def loadDraft():
    print("Loading Draft...")
    path = 'initdb/data/draft.csv'
    lines = open(path).read().split('\n')
    owners = set()
    for line in lines:
        if line == '':
            continue
        vals = line.split(',')
        owner = Owner.get_by_name(vals[0])
        bid = int(vals[1])
        bracket = Bracket(bid=bid, owner=owner)
        bracket.save()
    #print(Bracket.objects.all())

def loadBrackets():
    print("Loading Brackts...")
    for bid in range(1, 29):
        counts = [65, 32, 16, 8, 4, 2, 1]
        path = 'initdb/data/brackets/csv/' + str(bid) + '.csv'
        lines = open(path).read().split('\n')
        for i, line in enumerate(lines):
            if line == '':
                break

            vals = line.split(',')
            for rd in range(1, 7):
                team_name = vals[4 + rd]
                if team_name == '':
                    break

                if i < 66: #reg tourney
                    gid = counts[rd]
                    counts[rd] += 1
                else:
                    # The first four happen to be spaced out 4 games apart.
                    gid = counts[0]
                    counts[0] += 8

                # create Slot Entry
                bracket = Bracket.get_by_bid(bid)
                game = Game.get_by_gid(gid)
                winner = Team.get_by_name(team_name)
                slot = Slot(bracket=bracket, game=game, winner=winner)
                slot.save()
        print(str(bid) + "/28")







deleteAll()
loadTeams()
loadGames()
loadOwners()
loadDraft()
loadBrackets()



