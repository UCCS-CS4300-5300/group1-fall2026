from django.conf import settings
from django.db import models

from .exercises import STAT_NAMES


class Repkin(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="repkin", null=True)
    mood = models.CharField(max_length=20)
    color = models.CharField(max_length=20)
    name = models.CharField(max_length=30, blank=True)
    favorite_activity = models.CharField(max_length=40, blank=True)
    favorite_food = models.CharField(max_length=40, blank=True)
    setup_complete = models.BooleanField(default=False)

    # Physical stats, saved separately for each Repkin.
    strength = models.IntegerField(default=50)
    dexterity = models.IntegerField(default=50)
    endurance = models.IntegerField(default=50)

    # Progress stats built up during the week, added to the real stats later.
    progress_strength = models.IntegerField(default=0)
    progress_dexterity = models.IntegerField(default=0)
    progress_endurance = models.IntegerField(default=0)

    # Read the stats as dicts, same shape as before:
    # {"strength": 50, "dexterity": 50, "endurance": 50}
    @property
    def stats(self):
        return {name: getattr(self, name) for name in STAT_NAMES}

    @property
    def progress_stats(self):
        return {name: getattr(self, f"progress_{name}") for name in STAT_NAMES}

    # The methods below change the values but do not save.
    # Call repkin.save() afterward to store them in the database.

    # Add progressive stats to the repkin's actual stats, for use per week when final progress
    # count is made real. Resets the progression back to zero to be built up over the next week.
    def add_prog_to_stats(self):
        for name in STAT_NAMES:
            setattr(self, name, getattr(self, name) + getattr(self, f"progress_{name}"))
            setattr(self, f"progress_{name}", 0)

    # Update the progression stats by adding incoming values.
    def update_progress(self, stats):
        for name in STAT_NAMES:
            setattr(self, f"progress_{name}", getattr(self, f"progress_{name}") + stats[name])

    # Update real stats by adding incoming values.
    def update_stats(self, stats):
        for name in STAT_NAMES:
            setattr(self, name, getattr(self, name) + stats[name])

    # Set real stats directly, mostly for testing purposes.
    def set_stats(self, stats):
        for name in STAT_NAMES:
            setattr(self, name, stats[name])

    # Set progression stats directly, mostly for testing purposes.
    def set_progress(self, stats):
        for name in STAT_NAMES:
            setattr(self, f"progress_{name}", stats[name])
