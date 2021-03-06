# Generated by Django 3.1.7 on 2021-03-19 15:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bracketeering', '0002_auto_20210319_1412'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='bracket',
            name='points',
        ),
        migrations.AddField(
            model_name='bracket',
            name='points_bonus',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='bracket',
            name='points_norm',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='bracket',
            name='potential_bonus',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='bracket',
            name='potential_norm',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='slot',
            name='potential',
            field=models.IntegerField(default=0),
        ),
    ]
