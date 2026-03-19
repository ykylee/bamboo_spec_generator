from __future__ import annotations

from django.db import migrations, models


def require_definition_reingest_for_year(apps, schema_editor) -> None:
    BuildPlanDefinition = apps.get_model("buildmeta", "BuildPlanDefinition")
    if BuildPlanDefinition.objects.exists():
        raise RuntimeError(
            "Existing build plan definitions must be re-ingested because year is now stored as "
            "explicit DB metadata. Reset the development database with "
            "`python backend/manage.py init_dev_db` or "
            "`python backend/manage.py init_postgres_db --force`."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("buildmeta", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="buildplandefinition",
            name="year",
            field=models.CharField(default="", max_length=16),
            preserve_default=False,
        ),
        migrations.RunPython(require_definition_reingest_for_year, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name="buildversion",
            name="ix_build_version_commit",
        ),
        migrations.RemoveConstraint(
            model_name="buildversion",
            name="uq_build_version_commit",
        ),
        migrations.AddIndex(
            model_name="buildversion",
            index=models.Index(fields=["build_plan", "commit_hash"], name="ix_build_version_commit"),
        ),
        migrations.AddConstraint(
            model_name="buildversion",
            constraint=models.UniqueConstraint(fields=("build_plan", "commit_hash"), name="uq_build_version_commit"),
        ),
    ]
