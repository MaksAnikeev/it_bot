from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from tinymce.models import HTMLField


# Пользователи
class TelegramUser(models.Model):
    user_id = models.AutoField(primary_key=True)
    tg_name = models.CharField(
        max_length=255,
        verbose_name='Имя пользователя в телеграмме',
        db_index=True
    )
    tg_id = models.IntegerField(
        unique=True,
        verbose_name='ИД пользователя в телеграмме'
    )
    ROLE_CHOICES = (
        ('admin', 'Администратор'),
        ('client', 'Клиент'),
        ('user', 'Пользователь'),
    )
    role = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        default='user',
        verbose_name='роль пользователя'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='дата создания объекта')

    class Meta:
        db_table = 'telegramuser'
        verbose_name = 'пользователь'
        verbose_name_plural = '1. Пользователи'

    def __str__(self):
        return self.tg_name


# Тарифы
class Tariff(models.Model):
    tariff_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255, verbose_name='название')
    description = HTMLField(
        blank=True,
        default='',
        verbose_name='описание'
    )
    price = models.IntegerField(verbose_name='цена тарифа в рублях')
    STATUS_CHOICES = (
        ('active', 'активный'),
        ('archive', 'в архиве'),
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name='статус тарифа'
    )

    class Meta:
        db_table = 'tariff'
        verbose_name = 'тариф'
        verbose_name_plural = 'тарифы'

    def __str__(self):
        return self.title


# Платежи
class Payment(models.Model):
    payment_id = models.AutoField(primary_key=True)
    payment_date = models.DateTimeField(auto_now_add=True, verbose_name='дата осуществления платежа')
    amount = models.IntegerField(verbose_name='сумма платежа')
    user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='payments',
        db_index=True
    )
    access_date_start = models.DateField(verbose_name='дата начала доступа')
    access_date_finish = models.DateField(verbose_name='дата окончания доступа')
    tariff = models.ForeignKey(
        Tariff,
        on_delete=models.SET_NULL,
        related_name='payments',
        db_index=True,
        null=True,
    )
    status = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='статус платежа'
    )
    service_description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='назначение платежа')

    class Meta:
        db_table = 'payment'
        verbose_name = 'платеж'
        verbose_name_plural = '3. Платежи'

    def __str__(self):
        return f"Payment {self.payment_id} for {self.user.tg_name}"


# Контактная информация пользователя
class UserContact(models.Model):
    user = models.OneToOneField(
        TelegramUser,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='contact'
    )
    firstname = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='имя',
    )
    secondname = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='фамилия'
    )
    email = models.EmailField(blank=True, null=True)
    city = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='город проживания'
    )
    phonenumber = PhoneNumberField(
        verbose_name='номер телефона',
        region='RU'
    )

    class Meta:
        db_table = 'usercontact'
        verbose_name = 'контакт'
        verbose_name_plural = '2. Контакты'

    def __str__(self):
        return f"Contact for {self.user.tg_name}"


# Темы
class Topic(models.Model):
    topic_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255, verbose_name='название')
    description = HTMLField(
        blank=True,
        default='',
        verbose_name='описание'
    )
    serial_number = models.IntegerField(verbose_name='последовательность вывода')
    picture = models.ImageField(
        upload_to='topics/',  # Папка в media, куда будут сохраняться файлы
        blank=True,
        null=True,
        verbose_name='Картинка темы'
    )

    class Meta:
        db_table = 'topic'
        verbose_name = 'тема'
        verbose_name_plural = '5. Темы'
        ordering = ['serial_number']

    def __str__(self):
        return self.title


# Уроки
class Lesson(models.Model):
    lesson_id = models.AutoField(primary_key=True)
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name='lessons',
        db_index=True
    )
    title = models.CharField(max_length=255, verbose_name='название')
    description = HTMLField(
        blank=True,
        default='',
        verbose_name='описание'
    )
    serial_number = models.IntegerField(verbose_name='последовательность вывода')
    picture = models.ImageField(
        upload_to='lesons/',  # Папка в media, куда будут сохраняться файлы
        blank=True,
        null=True,
        verbose_name='Картинка урока'
    )

    class Meta:
        db_table = 'lesson'
        verbose_name = 'урок'
        verbose_name_plural = '6. Уроки'
        ordering = ['serial_number']

    def __str__(self):
        return self.title


# Видео
class Video(models.Model):
    video_id = models.AutoField(primary_key=True)
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='videos',
        db_index=True
    )
    title = models.CharField(max_length=255, verbose_name='название')
    serial_number = models.IntegerField(verbose_name='последовательность вывода')
    video_link = models.URLField(verbose_name='Ссылка на видео')
    next_topics = models.ManyToManyField(
        'Topic',
        related_name='unlocked_by_videos',
        blank=True,
        verbose_name='открыть тему после прохождения'
    )
    next_lessons = models.ManyToManyField(
        'Lesson',
        related_name='unlocked_by_videos',
        blank=True,
        verbose_name='открыть урок после прохождения'
    )
    next_videos = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='unlocked_by_videos',
        blank=True,
        verbose_name='открыть видео после прохождения'
    )
    next_tests = models.ManyToManyField(
        'Test',
        related_name='unlocked_by_videos',
        blank=True,
        verbose_name='открыть тест после прохождения'
    )
    next_practices = models.ManyToManyField(
        'Practice',
        related_name='unlocked_by_videos',
        blank=True,
        verbose_name='открыть практику после прохождения'
    )


    class Meta:
        db_table = 'video'
        verbose_name = 'видео'
        verbose_name_plural = '7. Видео'
        ordering = ['serial_number']

    def __str__(self):
        return self.title


# Конспект видео
class VideoSummary(models.Model):
    summary_id = models.AutoField(primary_key=True)
    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name='summaries',
        db_index=True
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='название'
    )
    description = HTMLField(
        blank=True,
        default='',
        verbose_name='описание'
    )
    picture = models.ImageField(
        upload_to='video_summary/',  # Папка в media, куда будут сохраняться файлы
        blank=True,
        null=True,
        verbose_name='картинка для описания'
    )

    class Meta:
        db_table = 'videosummary'
        verbose_name = 'видеоконспект'
        verbose_name_plural = '8. Видеоконспекты'

    def __str__(self):
        return f"Summary for {self.video.title}"


# Тесты
class Test(models.Model):
    test_id = models.AutoField(primary_key=True)
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='tests',
        db_index=True
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='название'
    )
    description = HTMLField(
        blank=True,
        default='',
        verbose_name='описание'
    )
    show_right_answer = models.BooleanField(default=False)
    next_topics = models.ManyToManyField(
        'Topic',
        related_name='unlocked_by_tests',
        blank=True,
        verbose_name='открыть тему после прохождения'
    )
    next_lessons = models.ManyToManyField(
        'Lesson',
        related_name='unlocked_by_tests',
        blank=True,
        verbose_name='открыть урок после прохождения'
    )
    next_videos = models.ManyToManyField(
        'Video',
        related_name='unlocked_by_tests',
        blank=True,
        verbose_name='открыть видео после прохождения'
    )
    next_tests = models.ManyToManyField(
        'self',
        symmetrical=False,  # Явно указываем несимметричное отношение
        related_name='unlocked_by_tests',
        blank=True,
        verbose_name='открыть тест после прохождения'
    )
    next_practices = models.ManyToManyField(
        'Practice',
        related_name='unlocked_by_tests',
        blank=True,
        verbose_name='открыть практику после прохождения'
    )

    class Meta:
        db_table = 'test'
        verbose_name = 'тест'
        verbose_name_plural = '9. Тесты'

    def __str__(self):
        return self.title or "Без названия"


# Вопросы
class Question(models.Model):
    question_id = models.AutoField(primary_key=True)
    test = models.ForeignKey(
        'Test',
        on_delete=models.CASCADE,
        related_name='questions',
        db_index=True,
        blank=True,
        null=True,
        verbose_name='тест'
    )
    video = models.ForeignKey(
        'Video',
        on_delete=models.CASCADE,
        related_name='questions',
        db_index=True,
        blank=True,
        null=True,
        verbose_name='вопрос для видео'
    )
    description = HTMLField(verbose_name='описание вопроса')
    serial_number = models.IntegerField(verbose_name='последовательность вывода')
    picture = models.ImageField(
        upload_to='questions/',
        blank=True,
        null=True,
        verbose_name='тест картинка'
    )

    class Meta:
        db_table = 'question'
        verbose_name = 'вопрос'
        verbose_name_plural = 'Вопросы'
        ordering = ['serial_number']

    def __str__(self):
        if self.test:
            return f"Question {self.serial_number} for Test {self.test.title}"
        elif self.video:
            return f"Question {self.serial_number} for Video {self.video.title}"
        return f"Question {self.serial_number}"

    def clean(self):
        """Проверка, что вопрос привязан либо к тесту, либо к видео, но не к обоим."""
        if not self.test and not self.video:
            raise ValidationError("Вопрос должен быть привязан к тесту или видео.")
        if self.test and self.video:
            raise ValidationError("Вопрос не может быть привязан одновременно к тесту и видео.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Проверяем валидность перед сохранением
        super().save(*args, **kwargs)


# Ответы
class Answer(models.Model):
    answer_id = models.AutoField(primary_key=True)
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers',
        db_index=True
    )
    description = HTMLField(verbose_name='описание ответа')
    serial_number = models.IntegerField(blank=True, verbose_name='последовательность вывода')
    right = models.BooleanField(verbose_name='метка правильности ответа')

    def save(self, *args, **kwargs):
        # Если serial_number не указан (например, при создании через код или форму)
        if self.serial_number is None:
            # Находим максимальный serial_number для текущего вопроса
            max_serial = Answer.objects.filter(question=self.question).aggregate(
                models.Max('serial_number')
            )['serial_number__max']
            # Если ответов ещё нет, начинаем с 1, иначе добавляем 1 к максимальному
            self.serial_number = 1 if max_serial is None else max_serial + 1
        # Сохраняем объект
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'answer'
        verbose_name = 'ответ'
        verbose_name_plural = 'ответы'
        ordering = ['serial_number']

    def __str__(self):
        return f"Answer {self.serial_number} for {self.question}"


# Практические задания
class Practice(models.Model):
    practice_id = models.AutoField(primary_key=True)
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='practices',
        db_index=True
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='название'
    )
    description = HTMLField(
        blank=True,
        default='',
        verbose_name='описание'
    )
    exercise = models.FileField(
        upload_to='exercises/',
        verbose_name='файл с заданием',
        blank=True,
        null=True
    )
    next_topics = models.ManyToManyField(
        'Topic',
        related_name='unlocked_by_practices',
        blank=True,
        verbose_name='открыть тему после прохождения'
    )
    next_lessons = models.ManyToManyField(
        'Lesson',
        related_name='unlocked_by_practices',
        blank=True,
        verbose_name='открыть урок после прохождения'
    )
    next_videos = models.ManyToManyField(
        'Video',
        related_name='unlocked_by_practices',
        blank=True,
        verbose_name='открыть видео после прохождения'
    )
    next_tests = models.ManyToManyField(
        'Test',
        related_name='unlocked_by_practices',
        blank=True,
        verbose_name='открыть тест после прохождения'
    )
    next_practices = models.ManyToManyField(
        'self',
        symmetrical=False,  # Явно указываем несимметричное отношение
        related_name='unlocked_by_practices',
        blank=True,
        verbose_name='открыть практику после прохождения'
    )

    class Meta:
        db_table = 'practice'
        verbose_name = 'практическое задание'
        verbose_name_plural = 'практические задания'

    def __str__(self):
        return self.title


# Доступный контент пользователю
class UserAvailability(models.Model):
    user = models.OneToOneField(
        TelegramUser,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='availability'
    )
    topics = models.ManyToManyField(
        Topic,
        blank=True,
        verbose_name='доступные темы',
        related_name='available_to_users'
    )
    lessons = models.ManyToManyField(
        Lesson,
        blank=True,
        verbose_name='доступные уроки',
        related_name='available_to_users'
    )
    videos = models.ManyToManyField(
        Video,
        blank=True,
        verbose_name='доступные видео',
        related_name='available_to_users'
    )
    tests = models.ManyToManyField(
        Test,
        blank=True,
        verbose_name='доступные тесты',
        related_name='available_to_users'
    )
    practices = models.ManyToManyField(
        Practice,
        blank=True,
        verbose_name='доступные практические задания',
        related_name='available_to_users'
    )

    class Meta:
        db_table = 'useravailability'
        verbose_name = 'доступный пользователю контент'
        verbose_name_plural = '4. Доступный пользователю контент'

    def __str__(self):
        return f"Availability for {self.user.tg_name}"


# Доступный стартовый контент пользователю
class StartUserAvailability(models.Model):
    tariff = models.OneToOneField(
        Tariff,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='start_availability'
    )
    topics = models.ManyToManyField(
        Topic,
        blank=True,
        verbose_name='доступные темы',
        related_name='start_available_to_users'
    )
    lessons = models.ManyToManyField(
        Lesson,
        blank=True,
        verbose_name='доступные уроки',
        related_name='start_available_to_users'
    )
    videos = models.ManyToManyField(
        Video,
        blank=True,
        verbose_name='доступные видео',
        related_name='start_available_to_users'
    )
    tests = models.ManyToManyField(
        Test,
        blank=True,
        verbose_name='доступные тесты',
        related_name='start_available_to_users'
    )
    practices = models.ManyToManyField(
        Practice,
        blank=True,
        verbose_name='доступные практические задания',
        related_name='start_available_to_users'
    )

    class Meta:
        db_table = 'startuseravailability'
        verbose_name = 'доступный сначала пользователю контент'
        verbose_name_plural = '4.1 Доступный сначала пользователю контент'

    def __str__(self):
        return f"Start availability for {self.tariff.title}"


# Пройденный пользователем контент
class UserDone(models.Model):
    user = models.OneToOneField(
        TelegramUser,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='done'
    )
    topics = models.ManyToManyField(
        Topic,
        blank=True,
        verbose_name='пройденные темы',
        related_name='users_done'
    )
    lessons = models.ManyToManyField(
        Lesson,
        blank=True,
        verbose_name='пройденные уроки',
        related_name='users_done'
    )
    videos = models.ManyToManyField(
        Video,
        blank=True,
        verbose_name='пройденные видео',
        related_name='users_done'
    )
    tests = models.ManyToManyField(
        Test,
        blank=True,
        verbose_name='пройденные тесты',
        related_name='users_done'
    )
    practices = models.ManyToManyField(
        Practice,
        blank=True,
        verbose_name='пройденные практические задания',
        related_name='users_done'
    )
    last_updated = models.DateTimeField(
        auto_now=True,
        verbose_name='Последнее обновление'
    )

    class Meta:
        db_table = 'users_done'
        verbose_name = 'Пройденный пользователем контент'
        verbose_name_plural = '4.2 Пройденный пользователем контент'

    def __str__(self):
        return f"Done for {self.user.tg_name}"
