from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("buildmeta", "0002_definition_year_and_branch_version_scope"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="buildplan",
            name="active_definition",
        ),
    ]
