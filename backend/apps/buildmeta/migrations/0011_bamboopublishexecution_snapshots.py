from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("buildmeta", "0010_buildplan_repository_linkage_mode_override"),
    ]

    operations = [
        migrations.AddField(
            model_name="bamboopublishexecution",
            name="snapshot_export_draft_json",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bamboopublishexecution",
            name="snapshot_preview_json",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
