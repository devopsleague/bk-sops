# Generated by Django 3.2.15 on 2022-10-25 11:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analysis_statistics", "0006_auto_20220315_1712"),
    ]

    operations = [
        migrations.AddField(
            model_name="taskflowexecutednodestatistics",
            name="template_node_id",
            field=models.CharField(blank=True, db_index=True, max_length=32, null=True, verbose_name="流程节点ID"),
        ),
    ]