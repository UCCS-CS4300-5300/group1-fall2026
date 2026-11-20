from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_repkin_limb_levels"),
    ]

    operations = [
        migrations.AddField(
            model_name="repkin",
            name="is_tired",
            field=models.BooleanField(default=False),
        ),
    ]
