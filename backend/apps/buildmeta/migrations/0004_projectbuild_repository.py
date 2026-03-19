from __future__ import annotations

from django.db import migrations, models


def populate_project_build_repository(apps, schema_editor) -> None:
    ProjectBuild = apps.get_model("buildmeta", "ProjectBuild")
    ProjectRepository = apps.get_model("buildmeta", "ProjectRepository")

    for project_build in ProjectBuild.objects.select_related("project").all():
        project = project_build.project
        repository = None
        if project.representative_repo_slug:
            repository = ProjectRepository.objects.filter(
                project_id=project.id,
                repo_slug=project.representative_repo_slug,
            ).first()
        if repository is None:
            repository = ProjectRepository.objects.filter(project_id=project.id).order_by("repo_slug").first()
        if repository is not None:
            project_build.repository_id = repository.id
            project_build.save(update_fields=["repository"])


class Migration(migrations.Migration):

    dependencies = [
        ("buildmeta", "0003_remove_buildplan_active_definition"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectbuild",
            name="repository",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name="builds",
                to="buildmeta.projectrepository",
            ),
        ),
        migrations.RunPython(populate_project_build_repository, migrations.RunPython.noop),
    ]
