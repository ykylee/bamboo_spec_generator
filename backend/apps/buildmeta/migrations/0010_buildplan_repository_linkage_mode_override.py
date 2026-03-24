from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("buildmeta", "0009_bamboopublishexecution"),
    ]

    operations = [
        migrations.AddField(
            model_name="buildplan",
            name="repository_linkage_mode_override",
            field=models.CharField(
                blank=True,
                choices=[("linked", "linked"), ("create_if_missing", "create_if_missing")],
                max_length=32,
            ),
        ),
    ]
