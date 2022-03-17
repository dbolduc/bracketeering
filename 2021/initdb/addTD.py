from bracketeering.models import *

# Drop TeamDepth table initially
TeamDepth.objects.all().delete()

first_fours = set(["Norfolk St", "App St", "Wichita St", "Drake", "Mt St Marys", "Texas Southern", "Michigan St", "UCLA"])

teams = Team.objects.all()
brackets = Bracket.objects.all()
for team in teams:
    print(team.name)
    # calculate initial depth
    init_depth = 1
    if team.name in first_fours:
        init_depth = 0

    for bracket in brackets:
        depth = init_depth
        slots = Slot.objects.filter(bracket=bracket,winner=team)
        for slot in slots:
            game_rd = slot.game.get_round()
            if depth < game_rd + 1:
                depth = game_rd + 1

        # create object, set depth
        td = TeamDepth(team=team, bracket=bracket, depth=depth)
        td.save()
