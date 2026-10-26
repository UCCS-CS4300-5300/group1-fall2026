from django.db import models
from django.conf import settings


class Repkin(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="repkin", null=True)
    mood = models.CharField(max_length=20)
    color = models.CharField(max_length=20)
    name = models.CharField(max_length=30, blank=True)
    favorite_activity = models.CharField(max_length=40, blank=True)
    favorite_food = models.CharField(max_length=40, blank=True)
    setup_complete = models.BooleanField(default=False)

    #Physical Stats Dict
    stats = {"strength":50, "dexterity":50, "endurance":50 }

    #Progressive Stats Dict
    progress_stats = {"strength":0, "dexterity":0, "endurance":0 }
    
    # Add progressive stats to the repkin's actual stats, for use per week when final progress 
    # count is made real. Resets the progression back to zero to be built up over the next week.
    def add_prog_to_stats(self):
        for key in self.progress_stats:
            self.stats[key] += self.progress_stats[key]
            self.progress_stats[key] = 0
        return

    # Update the progression stats by adding incoming values to the dictionary.
    def update_progress(self, stats):
        for key in self.progress_stats:
            self.progress_stats[key] += stats[key]
        return

    # set real stats by setting values to the dictionary, mostly for testing purposes.
    def set_stats(self, stats):
        for key in self.stats:
            self.stats[key] = stats[key]
        return
    
    # Set progression stats by setting values in dict, mostly for testing purposes.
    def set_progress(self, stats):
        for key in self.progress_stats:
            self.progress_stats[key] = stats[key]
        return




