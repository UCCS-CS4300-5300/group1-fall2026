from .models_repkin import Repkin
from django import forms

COLOR_CHOICES = [
    ("green", "Green"),
    ("blue", "Blue"),
    ("purple", "Purple"),
    ("red", "Red"),
    ("yellow", "Yellow"),
]

class RepkinSetupForm(forms.ModelForm):
    color = forms.ChoiceField(choices=COLOR_CHOICES)

    class Meta:
        model = Repkin
        fields = ("name", "color", "favorite_activity", "favorite_food")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True