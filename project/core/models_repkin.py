from django.db import models


class Repkin(models.Model):
    mood = models.CharField(max_length=20)
    color = models.CharField(max_length=20)