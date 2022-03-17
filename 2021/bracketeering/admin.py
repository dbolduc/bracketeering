from django.contrib import admin

from .models import *

admin.site.register(Owner)
admin.site.register(Bracket)
admin.site.register(Slot)
admin.site.register(Game)
admin.site.register(Team)
admin.site.register(TeamDepth)
