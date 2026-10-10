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