from django.db import migrations, models


# Add saved arm and leg sprite levels to Repkin records.
class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_workouts_and_weight"),
    ]

    operations = [
        migrations.AddField(
            model_name="repkin",
            name="arms_level",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="repkin",
            name="legs_level",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]