from django.views.generic import TemplateView
from bracketeering.models import *

class AboutView(TemplateView):
    template_name = 'about.html'

class DraftView(TemplateView):
    template_name = 'draft.html'

    def get_context_data(self, **kwargs):
        context = super(DraftView, self).get_context_data(**kwargs)
        context['brackets'] = Bracket.objects.all()
        return context

class MainView(TemplateView):
    template_name = 'main.html'

    def get_context_data(self, **kwargs):
        context = super(MainView, self).get_context_data(**kwargs)
        context['brackets'] = Bracket.objects.all()
        context['owners'] = Owner.objects.all()
        return context

class BracketView(TemplateView):
    template_name = 'bracket.html'
    bracket = None
    slots = []

    def dispatch(self, request, *args, **kwargs):
        # get the bracket by bid
        self.bracket = Bracket.get_by_bid(kwargs['bid'])
        self.slots = Slot.objects.filter(bracket=self.bracket)
        return super(BracketView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(BracketView, self).get_context_data(**kwargs)
        context['bracket'] = self.bracket
        context['slots'] = self.slots
        return context

class OwnerView(TemplateView):
    template_name = 'owner.html'
    owner = None
    brackets = []

    def dispatch(self, request, *args, **kwargs):
        # get the bracket by bid
        self.owner = Owner.get_by_name(kwargs['name'])
        self.brackets = Bracket.objects.filter(owner=self.owner)
        return super(OwnerView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(OwnerView, self).get_context_data(**kwargs)
        context['owner'] = self.owner
        context['brackets'] = self.brackets
        return context

class GameView(TemplateView):
    template_name = 'game.html'
    game = None
    slots = []

    def dispatch(self, request, *args, **kwargs):
        self.game = Game.get_by_gid(kwargs['gid'])
        self.slots = Slot.objects.filter(game=self.game)
        return super(GameView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(GameView, self).get_context_data(**kwargs)
        context['game'] = self.game
        context['slots'] = self.slots
        return context

class TeamView(TemplateView):
    template_name = 'team.html'
    team = None
    depths = []

    def dispatch(self, request, *args, **kwargs):
        self.team = Team.get_by_name(kwargs['name'])
        self.depths = TeamDepth.objects.filter(team=self.team)
        return super(TeamView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(TeamView, self).get_context_data(**kwargs)
        context['team'] = self.team
        context['depths'] = self.depths
        return context

