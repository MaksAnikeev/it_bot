import html

from django.contrib import admin
from django.utils.html import format_html, mark_safe, strip_tags

from .models import (Answer, Lesson, Payment, Practice, Question,
                     StartUserAvailability, Tariff, TelegramUser, Test, Topic,
                     UserAvailability, UserContact, Video, VideoSummary, UserDone)


class UserContactInline(admin.TabularInline):
    model = UserContact
    fields = ['firstname', 'phonenumber', 'city']


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    inlines = [UserContactInline, ]
    list_display = ('user_id', 'tg_name', 'get_contact_firstname', 'role', 'tg_id')
    search_fields = ('tg_name',)
    ordering = ('user_id',)

    def get_contact_firstname(self, obj):
        # Возвращает имя из связанной модели UserContact или '-' если записи нет
        return obj.contact.firstname if obj.contact else '-'

    get_contact_firstname.short_description = 'Имя пользователя'  # Название столбца в админке


@admin.register(UserContact)
class UserContactAdmin(admin.ModelAdmin):
    list_display = ('get_user_tg_name', 'firstname', 'secondname', 'phonenumber', 'city')
    search_fields = ('user__tg_name',)

    def get_user_tg_name(self, obj):
        # Возвращает тгимя из связанной модели TelegramUser или '-' если записи нет
        return obj.user.tg_name if obj.user else '-'

    get_user_tg_name.short_description = 'ТГ Имя пользователя'  # Название столбца в админке


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('get_user_tg_name', 'tariff', 'access_date_start', 'access_date_finish')
    search_fields = ('user__tg_name',)

    def get_user_tg_name(self, obj):
        # Возвращает тгимя из связанной модели TelegramUser или '-' если записи нет
        return obj.user.tg_name if obj.user else '-'

    get_user_tg_name.short_description = 'ТГ Имя пользователя'  # Название столбца в админке


@admin.register(UserAvailability)
class UserAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_topics', 'get_lessons', 'get_videos', 'get_tests', 'get_practices')
    filter_horizontal = ('topics', 'lessons', 'videos', 'tests', 'practices')  # Удобный виджет для M2M

    def get_topics(self, obj):
        return ", ".join([topic.title for topic in obj.topics.all()])
    get_topics.short_description = 'Темы'

    def get_lessons(self, obj):
        return ", ".join([lesson.title for lesson in obj.lessons.all()])
    get_lessons.short_description = 'Уроки'

    def get_videos(self, obj):
        return ", ".join([video.title for video in obj.videos.all()])
    get_videos.short_description = 'Видео'

    def get_tests(self, obj):
        return ", ".join([test.title for test in obj.tests.all()])
    get_tests.short_description = 'Тесты'

    def get_practices(self, obj):
        return ", ".join([practice.title for practice in obj.practices.all()])
    get_practices.short_description = 'Практики'


@admin.register(UserDone)
class UserDoneAdmin(admin.ModelAdmin):
    list_display = ('user', 'last_updated', 'get_topics', 'get_lessons', 'get_videos', 'get_tests', 'get_practices')
    filter_horizontal = ('topics', 'lessons', 'videos', 'tests', 'practices')  # Удобный виджет для M2M

    def get_topics(self, obj):
        return ", ".join([topic.title for topic in obj.topics.all()])
    get_topics.short_description = 'Темы'

    def get_lessons(self, obj):
        return ", ".join([lesson.title for lesson in obj.lessons.all()])
    get_lessons.short_description = 'Уроки'

    def get_videos(self, obj):
        return ", ".join([video.title for video in obj.videos.all()])
    get_videos.short_description = 'Видео'

    def get_tests(self, obj):
        return ", ".join([test.title for test in obj.tests.all()])
    get_tests.short_description = 'Тесты'

    def get_practices(self, obj):
        return ", ".join([practice.title for practice in obj.practices.all()])
    get_practices.short_description = 'Практики'


@admin.register(StartUserAvailability)
class StartUserAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('tariff', 'get_topics', 'get_lessons', 'get_videos', 'get_tests', 'get_practices')
    filter_horizontal = ('topics', 'lessons', 'videos', 'tests', 'practices')  # Удобный виджет для M2M

    def get_topics(self, obj):
        return ", ".join([topic.title for topic in obj.topics.all()])
    get_topics.short_description = 'Темы'

    def get_lessons(self, obj):
        return ", ".join([lesson.title for lesson in obj.lessons.all()])
    get_lessons.short_description = 'Уроки'

    def get_videos(self, obj):
        return ", ".join([video.title for video in obj.videos.all()])
    get_videos.short_description = 'Видео'

    def get_tests(self, obj):
        return ", ".join([test.title for test in obj.tests.all()])
    get_tests.short_description = 'Тесты'

    def get_practices(self, obj):
        return ", ".join([practice.title for practice in obj.practices.all()])
    get_practices.short_description = 'Практики'


class LessonInline(admin.TabularInline):
    model = Lesson
    fields = ['lesson_id', 'title', 'serial_number', 'preview']

    readonly_fields = ['preview']

    def preview(self, obj):
        if not obj.picture:
            return 'нет картинки'
        return format_html('<img src="{url}" style="max-height: 100px;"/>',
                           url=obj.picture.url)

    preview.short_description = 'Аватарка'


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('topic_id', 'title', 'serial_number', 'preview')
    search_fields = ('title',)
    readonly_fields = ['preview']
    inlines = [LessonInline, ]

    def preview(self, obj):
        if not obj.picture:
            return 'нет картинки'
        return format_html('<img src="{url}" style="max-height: 50px;"/>',
                           url=obj.picture.url)

    preview.short_description = 'Аватарка'


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('lesson_id', 'title', 'get_topic', 'serial_number', 'preview')
    search_fields = ('topic__title',)
    readonly_fields = ['preview']
    ordering = ('topic__serial_number', 'serial_number')

    def get_topic(self, obj):
        return obj.topic.title

    def preview(self, obj):
        if not obj.picture:
            return 'нет картинки'
        return format_html('<img src="{url}" style="max-height: 50px;"/>',
                           url=obj.picture.url)

    preview.short_description = 'Аватарка'
    get_topic.short_description = 'Тема'


class VideoSummaryInline(admin.TabularInline):
    model = VideoSummary
    fields = ['summary_id', 'title', ]
    readonly_fields = ['summary_id']


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('video_id', 'title', 'get_lesson', 'serial_number')
    search_fields = ('lesson__title',)
    ordering = ('lesson__serial_number', 'serial_number')
    inlines = [VideoSummaryInline, ]
    filter_horizontal = ('next_topics', 'next_lessons', 'next_videos', 'next_tests', 'next_practices')

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Делаем поля необязательными в форме
        for field in ['next_topics', 'next_lessons', 'next_videos', 'next_tests', 'next_practices']:
            form.base_fields[field].required = False
        return form

    def get_lesson(self, obj):
        return obj.lesson.title

    get_lesson.short_description = 'Урок'


@admin.register(VideoSummary)
class VideoSummaryAdmin(admin.ModelAdmin):
    list_display = ('summary_id', 'title', 'get_video', 'get_lesson')
    search_fields = ('video__lesson__title',)
    ordering = ('video__lesson__serial_number', 'video__serial_number')

    def get_video(self, obj):
        return obj.video.title

    def get_lesson(self, obj):
        return obj.video.lesson.title

    get_lesson.short_description = 'Урок'
    get_video.short_description = 'Видео'


class QuestionInline(admin.TabularInline):
    model = Question
    fields = ['question_id', 'description_clean', 'serial_number']
    readonly_fields = ['description_clean']  # Делаем его только для чтения

    def description_clean(self, obj):
        # Сначала убираем теги, затем декодируем HTML-сущности
        clean_text = html.unescape(strip_tags(obj.description))
        return clean_text

    description_clean.short_description = 'Текст вопроса'  # Заголовок столбца


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('test_id', 'title', 'get_lesson')
    search_fields = ('lesson__title',)
    ordering = ('lesson__serial_number', )
    inlines = [QuestionInline, ]
    filter_horizontal = ('next_topics', 'next_lessons', 'next_videos', 'next_tests', 'next_practices')

    def get_lesson(self, obj):
        return obj.lesson.title

    get_lesson.short_description = 'Урок'


class AnswerInline(admin.TabularInline):
    model = Answer
    fields = ['answer_id', 'description_clean', 'serial_number', 'right']
    readonly_fields = ['description_clean', ]  # Делаем его только для чтения

    def description_clean(self, obj):
        # Сначала убираем теги, затем декодируем HTML-сущности
        clean_text = html.unescape(strip_tags(obj.description))
        # Обрезаем до 20 символов и добавляем многоточие, если текст длиннее
        return clean_text[:50] + '...' if len(clean_text) > 50 else clean_text

    description_clean.short_description = 'Текст ответа'  # Заголовок столбца


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_id', 'description_clean', 'get_test', 'get_video', 'serial_number')
    search_fields = ('test__title',)
    ordering = ('test__test_id', 'serial_number')
    inlines = [AnswerInline, ]

    def get_test(self, obj):
        return obj.test.title if obj.test else "—"
    get_test.short_description = 'Тест'

    def get_video(self, obj):
        return obj.video.title if obj.video else "—"
    get_video.short_description = 'Видео'

    def description_clean(self, obj):
        # Сначала убираем теги, затем декодируем HTML-сущности
        clean_text = html.unescape(strip_tags(obj.description))
        # Обрезаем до 20 символов и добавляем многоточие, если текст длиннее
        return clean_text[:50] + '...' if len(clean_text) > 50 else clean_text

    get_test.short_description = 'Тест'
    description_clean.short_description = 'Текст вопроса'


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('answer_id', 'description_clean', 'get_question', 'serial_number', 'right')
    search_fields = ('question__question_id',)
    ordering = ('question__question_id', 'serial_number')

    def get_question(self, obj):
        return obj.question.question_id

    def description_clean(self, obj):
        # Сначала убираем теги, затем декодируем HTML-сущности
        clean_text = html.unescape(strip_tags(obj.description))
        # Обрезаем до 20 символов и добавляем многоточие, если текст длиннее
        return clean_text[:50] + '...' if len(clean_text) > 50 else clean_text

    description_clean.short_description = 'Текст ответа'
    get_question.short_description = 'Вопрос'


@admin.register(Practice)
class PracticeAdmin(admin.ModelAdmin):
    list_display = ('practice_id', 'title', 'get_lesson')
    search_fields = ('lesson__title',)
    ordering = ('lesson__lesson_id', )
    filter_horizontal = ('next_topics', 'next_lessons', 'next_videos', 'next_tests', 'next_practices')

    def get_lesson(self, obj):
        return obj.lesson.title

    get_lesson.short_description = 'Урок'


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = ('tariff_id', 'title', 'price', 'status')
    search_fields = ('title',)
    ordering = ('tariff_id', )
