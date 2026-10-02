from django.db import models
from .models_repkin import Repkin


class StarterItem(models.Model):
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.title
