import json
from django.core.management.base import BaseCommand
from django.core import management
from django.apps import apps
from django.db import connection


# Фикстура, которая перезаписывает содержимое БД на стандартную при каждом перезапуске докер компоуз
# class Command(BaseCommand):
#     help = 'Load fixture with content type synchronization'
#
#     def add_arguments(self, parser):
#         parser.add_argument('fixture_file', type=str, help='Path to the fixture file')
#
#     def handle(self, *args, **options):
#         fixture_file = options['fixture_file']
#
#         # Очищаем таблицу django_content_type
#         with connection.cursor() as cursor:
#             cursor.execute('TRUNCATE TABLE django_content_type RESTART IDENTITY CASCADE')
#
#         # Загружаем фикстуру
#         management.call_command('loaddata', fixture_file, verbosity=1)
#
#         # Проверяем и исправляем content_type_id в django_admin_log
#         ContentType = apps.get_model('contenttypes', 'ContentType')
#         LogEntry = apps.get_model('admin', 'LogEntry')
#
#         for log_entry in LogEntry.objects.all():
#             try:
#                 content_type = ContentType.objects.get(pk=log_entry.content_type_id)
#             except ContentType.DoesNotExist:
#                 self.stdout.write(self.style.WARNING(
#                     f"ContentType with id {log_entry.content_type_id} not found for LogEntry {log_entry.pk}"
#                 ))
#                 # Найти подходящий ContentType по app_label и model
#                 try:
#                     content_type = ContentType.objects.get(
#                         app_label=log_entry.content_type.app_label,
#                         model=log_entry.content_type.model
#                     )
#                     log_entry.content_type_id = content_type.pk
#                     log_entry.save()
#                     self.stdout.write(self.style.SUCCESS(
#                         f"Updated LogEntry {log_entry.pk} with content_type_id {content_type.pk}"
#                     ))
#                 except ContentType.DoesNotExist:
#                     self.stdout.write(self.style.ERROR(
#                         f"Could not find matching ContentType for LogEntry {log_entry.pk}"
#                     ))
#
#         self.stdout.write(self.style.SUCCESS('Fixture loaded and content types synchronized'))


# Фикстура, которая перезаписывает содержимое БД на стандартную только при первом запуске докер компоуз, когда БД пуста.
# Потом при перезапусках изменения сохраняются уже в контейнере и остаются при перезапусках

class Command(BaseCommand):
    help = 'Load fixture with content type synchronization'

    def add_arguments(self, parser):
        parser.add_argument('fixture_file', type=str, help='Path to the fixture file')

    def handle(self, *args, **options):
        fixture_file = options['fixture_file']

        # Проверяем, пуста ли база (например, таблица django_content_type)
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM django_content_type")
            count = cursor.fetchone()[0]

        if count == 0:  # Если база пуста, загружаем фикстуру
            # Очищаем таблицу django_content_type
            with connection.cursor() as cursor:
                cursor.execute('TRUNCATE TABLE django_content_type RESTART IDENTITY CASCADE')

            # Загружаем фикстуру
            management.call_command('loaddata', fixture_file, verbosity=1)

            # Проверяем и исправляем content_type_id в django_admin_log
            ContentType = apps.get_model('contenttypes', 'ContentType')
            LogEntry = apps.get_model('admin', 'LogEntry')

            for log_entry in LogEntry.objects.all():
                try:
                    content_type = ContentType.objects.get(pk=log_entry.content_type_id)
                except ContentType.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f"ContentType with id {log_entry.content_type_id} not found for LogEntry {log_entry.pk}"
                    ))
                    try:
                        content_type = ContentType.objects.get(
                            app_label=log_entry.content_type.app_label,
                            model=log_entry.content_type.model
                        )
                        log_entry.content_type_id = content_type.pk
                        log_entry.save()
                        self.stdout.write(self.style.SUCCESS(
                            f"Updated LogEntry {log_entry.pk} with content_type_id {content_type.pk}"
                        ))
                    except ContentType.DoesNotExist:
                        self.stdout.write(self.style.ERROR(
                            f"Could not find matching ContentType for LogEntry {log_entry.pk}"
                        ))

            self.stdout.write(self.style.SUCCESS('Fixture loaded and content types synchronized'))
        else:
            self.stdout.write(self.style.SUCCESS('Database is not empty, skipping fixture load'))