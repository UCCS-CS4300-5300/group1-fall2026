from django import forms

class ExerciseInputForm(forms.Form):
    EXERCISE_CHOICES = [
        ("push_ups", "Push Ups"),
        ("sit_ups", "Sit Ups"),
        ("squats", "Squats"),
        ("curls", "Curls"),
        ("lunges", "Lunges"),
    ]

    exercise_type = forms.ChoiceField(
        choices=EXERCISE_CHOICES
    )

    sets = forms.IntegerField(
        min_value=1,
        required=False
    )

    reps = forms.IntegerField(
        min_value=1,
        required=False
    )