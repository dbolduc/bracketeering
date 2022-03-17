from django.db import models

class Owner(models.Model):
    name = models.CharField(max_length=100,unique=True)
    sum_of_2 = models.IntegerField(default=0)
    best_bracket = models.IntegerField(default=0)
    # NOTE : streak_winner was manually assigned by the db admin. The "logic" is whack.
    streak_winner = models.BooleanField(default=False)
    max_elite_eight = models.IntegerField(default=0)
    payout = models.FloatField(default=-20)

    def __str__(self):
        return self.name

    def get_brackets(self):
        return Bracket.objects.filter(owner=self)

    def get_streak_winner_str(self):
        if self.streak_winner:
            return "$$$"
        return "-"

    @staticmethod
    def get_by_name(in_name):
        try:
            return Owner.objects.get(name=in_name)
        except Owner.DoesNotExist:
            pass

    # TODO : This method is pretty gross looking. Partly due to the actual logic 
    #        for calculating the given payouts... Still it might help readability
    #        to break this out into smaller methods. Also, if I were to test
    #        this code (I won't), I would want it broken up 
    @staticmethod
    def update_payouts():
        # assumes everything is up to date
        buy_in = 20.
        owners = Owner.objects.all()
        owners_count = Owner.objects.count()
        if owners_count == 0:
            return
        payouts = [-buy_in for i in range(owners_count)]

        # NOTE : this is a small use case. Only 28 brackets. So I am just grabbing all of them
        elite_eight = [[] for i in range(owners_count)]
        for i, owner in enumerate(owners):
            brackets = owner.get_brackets().order_by('elite_eight')
            for bracket in brackets:
                elite_eight[i].append(bracket.elite_eight)
            # Store max elite eight for this owner for display purposes
            owner.max_elite_eight = elite_eight[i][-1]
        brackets_per_owner = len(elite_eight[0])
        
        # NOTE : The Elite Eight payout is a little silly. Here's how it works:
        #        If an owner has 4 brackets (in ascending order): [A, B, C, D]
        #        The winner is the one with the highest D. In case of a tie,
        #        the first tie-breaker is the owner with the lowest A,
        #        next tie-breaker is highest C, last tie-breaker is lowest B.
        #        If there is still a tie, the payout will be split by whoever remains
        owners_set = set(list(range(owners_count)))
        ee_depth = 0
        for ee_depth in range(brackets_per_owner):
            # calculate index of [A, B, C, D] list
            # e.g. [3, 0, 2, 1] or [4, 0, 3, 1, 2] in a case with 5 brackets
            picking_max = ee_depth % 2 == 0
            bracket_i = 0
            if picking_max:
                bracket_i = brackets_per_owner - 1 - ee_depth // 2
            else:
                bracket_i = ee_depth // 2

            # calculate min/max for given bracket_i
            # store owner(s) of the bracket(s)
            next_owner_set = set()
            ee_max = -8 # 8 as in elite eight
            ee_mult = 1
            if not picking_max:
                ee_mult = -1 # trick to flip the inequality signs
            for owner_i in owners_set:
                val = elite_eight[owner_i][bracket_i]*ee_mult
                if val > ee_max:
                    next_owner_set = set([owner_i])
                    ee_max = val
                elif val == ee_max:
                    next_owner_set.add(owner_i)

            # update owners_set
            owners_set = next_owner_set

            # break, if we have narrowed it down to one owner
            if len(owners_set) == 1:
                break

        for owner_i in owners_set:
            payouts[owner_i] += 20. / len(owners_set)


        # OTHER PAYOUTS
        max_best = 0
        max_best_owner = []
        max_sum_2 = 0
        max_sum_2_owner = []
        for i, owner in enumerate(owners):
            # Best
            if owner.best_bracket > max_best:
                max_best = owner.best_bracket
                max_best_owner = [i]
            elif owner.best_bracket == max_best:
                max_best_owner.append(i)
            # Sum of 2
            if owner.sum_of_2 > max_sum_2:
                max_sum_2 = owner.sum_of_2
                max_sum_2_owner = [i]
            elif owner.sum_of_2 == max_sum_2:
                max_sum_2_owner.append(i)
            # Streak
            if owner.streak_winner:
                payouts[i] += 20.

        for owner_i in max_sum_2_owner:
            payouts[owner_i] += 80. / len(max_sum_2_owner)
        for owner_i in max_best_owner:
            payouts[owner_i] += 20. / len(max_best_owner)

        # update payouts for owner objects
        for i, owner in enumerate(owners):
            owner.payout = payouts[i]
            owner.save()

    def update(self):
        brackets = Bracket.objects.filter(owner=self)
        scores = []
        for bracket in brackets:
            scores.append(bracket.get_points())
        scores.sort()
        self.best_bracket = scores[-1]
        self.sum_of_2 = scores[-1] + scores[-2]
        self.save()

class Bracket(models.Model):
    bid = models.IntegerField(unique=True)
    owner = models.ForeignKey(Owner, on_delete=models.CASCADE)
    points_norm = models.IntegerField(default=0)
    points_bonus = models.IntegerField(default=0)
    potential_norm = models.IntegerField(default=0)
    potential_bonus = models.IntegerField(default=0)
    elite_eight = models.IntegerField(default=0)
    elite_eight_pot = models.IntegerField(default=0)

    def __str__(self):
        return "Bracket: " + str(self.bid)

    @staticmethod
    def get_by_bid(in_bid):
        try:
            return Bracket.objects.get(bid=in_bid)
        except Bracket.DoesNotExist:
            pass

    def get_points(self):
        return self.points_norm + self.points_bonus

    def get_potential(self):
        return self.potential_norm + self.potential_bonus

    def update(self):
        points = [[0,0],[0,0]] # [[norm, bonus], [pot_norm, pot_bonus]]
        h = {} # [bonus, pot_bonus]
        elite_eight = [0,0] # [count, pot_count]
        slots = Slot.objects.filter(bracket=self)
        for slot in slots:
            vals = [slot.points, slot.potential]

            # 5 point bonuses for perfect region in round of 32, sweet 16, elite 8
            rd = slot.game.get_round()
            # no bonuses for First Four or Championship rounds
            key = None
            if rd != 0 and rd != 6:
                rgn = 0
                if rd < 4:
                    rgn = slot.game.get_region()
                key = (rd, rgn)
                if key not in h:
                    h[key] = [5, 5]
            
            for i in range(2): # 0: points, 1: potential
                points[i][0] += vals[i]
                if key:
                    if vals[i] == 0:
                        h[key][i] = 0
                    elif rd == 3: # store Elite Eight count (needed for a payout)
                        elite_eight[i] += 1

        # sum the bonuses
        for bonus in h.values():
            points[0][1] += bonus[0]
            points[1][1] += bonus[1]
        # store the results
        self.points_norm = points[0][0]
        self.points_bonus = points[0][1]
        self.potential_norm = points[1][0]
        self.potential_bonus = points[1][1]
        self.elite_eight = elite_eight[0]
        self.elite_eight_pot = elite_eight[1]
        self.save()
        print("Updated bracket: " + str(self.bid))

class Team(models.Model):
    name = models.CharField(max_length=100,unique=True)
    overall_seed = models.IntegerField(unique=True)
    seed = models.IntegerField()
    alive = models.BooleanField(default=True)

    def __str__(self):
        return str(self.seed) + " " + self.name

    def get_link_name(self):
        return self.name.replace(' ', '-')

    def get_alive_str(self):
        # TODO : better than an alive flag would be a depth achieved field
        if self.alive:
            return "Alive"
        return "Out"
    
    @staticmethod
    def get_by_name(in_name):
        in_name = in_name.replace('-',' ')
        try:
            return Team.objects.get(name=in_name)
        except Team.DoesNotExist:
            pass

class Game(models.Model):
    gid = models.IntegerField(unique=True)
    winner = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, related_name='winner')
    team1 = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, related_name='team1')
    team2 = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, related_name='team2')

    def __str__(self):
        return "Game " + str(self.gid)

    @staticmethod
    def get_by_gid(in_gid):
        try:
            return Game.objects.get(gid=in_gid)
        except Game.DoesNotExist:
            return None

    def get_matchup_str(self):
        ret = ""
        if self.team1:
            ret += str(self.team1)
        else:
            ret += "TBD"
        ret += " vs. "
        if self.team2:
            ret += str(self.team2)
        else:
            ret += "TBD"
        return ret

    def get_round(self):
        return 7 - self.gid.bit_length()

    def get_round_str(self):
        rd = self.get_round()
        return ["First Four", "1st Round", "2nd Round", "Sweet Sixteen", "Elite Eight", "Final Four", "Championship"][rd]

    def get_region(self):
        rd = self.get_round()
        if rd > 4:
            return 0
        return self.gid // pow(2, 4 - rd) - 3

    def get_region_str(self):
        region = self.get_region()
        return ["No Region", "West", "East", "South", "Midwest"][region]

    def get_prev_game1(self):
        return Game.get_by_gid(2 * self.gid)

    def get_prev_game2(self):
        return Game.get_by_gid(2 * self.gid + 1)

    def get_points(self):
        rd = self.get_round()
        return [1, 1, 2, 3, 5, 8, 13][rd]

    def get_next_game(self):
        return Game.get_by_gid(self.gid // 2)

    def set_winner(self, team1_wins):
        # only set winner if both teams are there
        if not self.team1 or not self.team2:
            return

        winner = self.team1
        loser = self.team2
        if not team1_wins:
            winner = self.team2
            loser = self.team1

        # set this game's winner
        self.winner = winner
        self.save()

        # propogate winner to next game
        game = self.get_next_game()
        if game:
            if self.gid % 2 == 0:
                game.team1 = winner
            else:
                game.team2 = winner
            game.save()

        # update teams' alive status
        winner.alive = True
        winner.save()
        loser.alive = False
        loser.save()

        # update slots that deal with this game
        # update slots that deal with losing team
        slots = Slot.objects.filter(models.Q(game=self) | models.Q(winner=loser))
        for slot in slots:
            slot.update()

        # update brackets
        brackets = Bracket.objects.all()
        for bracket in brackets:
            bracket.update()

        # update owners
        owners = Owner.objects.all()
        for owner in owners:
            owner.update()
        Owner.update_payouts()


class Slot(models.Model):
    bracket = models.ForeignKey(Bracket, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    winner = models.ForeignKey(Team, on_delete=models.CASCADE)
    points = models.IntegerField(default=0)
    potential = models.IntegerField(default=0)

    def update(self):
        self.save()
        points = 0
        potential = 0
        winner = self.game.winner
        if winner and winner == self.winner:
            points = self.game.get_points()
            potential = points
        elif self.winner.alive:
            potential = self.game.get_points()
        self.points = points
        self.potential = potential
        self.save()

class TeamDepth(models.Model):
    bracket = models.ForeignKey(Bracket, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    depth = models.IntegerField(default=0)


