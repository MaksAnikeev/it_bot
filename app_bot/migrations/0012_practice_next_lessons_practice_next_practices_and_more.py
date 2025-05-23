# Generated by Django 5.1.7 on 2025-04-15 17:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_bot', '0011_test_next_lessons_test_next_practices_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='practice',
            name='next_lessons',
            field=models.ManyToManyField(blank=True, related_name='unlocked_by_practices', to='app_bot.lesson', verbose_name='открыть урок после прохождения'),
        ),
        migrations.AddField(
            model_name='practice',
            name='next_practices',
            field=models.ManyToManyField(blank=True, related_name='unlocked_by_practices', to='app_bot.practice', verbose_name='открыть практику после прохождения'),
        ),
        migrations.AddField(
            model_name='practice',
            name='next_tests',
            field=models.ManyToManyField(blank=True, related_name='unlocked_by_practices', to='app_bot.test', verbose_name='открыть тест после прохождения'),
        ),
        migrations.AddField(
            model_name='practice',
            name='next_topics',
            field=models.ManyToManyField(blank=True, related_name='unlocked_by_practices', to='app_bot.topic', verbose_name='открыть тему после прохождения'),
        ),
        migrations.AddField(
            model_name='practice',
            name='next_videos',
            field=models.ManyToManyField(blank=True, related_name='unlocked_by_practices', to='app_bot.video', verbose_name='открыть видео после прохождения'),
        ),
    ]
