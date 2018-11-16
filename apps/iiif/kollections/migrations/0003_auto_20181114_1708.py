# Generated by Django 2.1.2 on 2018-11-14 17:08

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kollections', '0002_collection_pid'),
    ]

    operations = [
        migrations.AddField(
            model_name='collection',
            name='metadata',
            field=django.contrib.postgres.fields.jsonb.JSONField(null=True),
        ),
        migrations.AddField(
            model_name='collection',
            name='upload',
            field=models.FileField(null=True, upload_to='uploads/'),
        ),
    ]
