from bs4 import BeautifulSoup
from rest_framework import serializers
from .models import TelegramUser, UserContact, Topic, Answer, Question, Test, Tariff, Payment, UserAvailability,\
    Lesson, Video, VideoSummary, Practice


def clean_html(html_text):
    """Удаляет HTML-теги и лишние пробелы/переносы, возвращает чистый текст."""
    if not html_text:
        return ""
    # Удаляем HTML-теги
    soup = BeautifulSoup(html_text, 'html.parser')
    text = soup.get_text()
    # Заменяем неразрывные пробелы на обычные
    text = text.replace('\xa0', ' ')
    # Убираем лишние переносы строк и сжимаем пробелы
    text = ' '.join(text.split())
    return text.strip()


class TariffSerializer(serializers.ModelSerializer):

    class Meta:
        model = Tariff
        fields = '__all__'


class PaymentSerializer(serializers.ModelSerializer):
    tariff = serializers.PrimaryKeyRelatedField(
        queryset=Tariff.objects.all(),
        write_only=True
    )
    tariff_detail = serializers.SerializerMethodField(read_only=True)  # Добавим для отображения деталей

    def get_tariff_detail(self, obj):
        return TariffSerializer(obj.tariff, read_only=True).data

    class Meta:
        model = Payment
        fields = ['amount', 'user', 'access_date_start', 'access_date_finish', 'tariff',
                  'tariff_detail', 'status', 'service_description']


class UserContactSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserContact
        fields = ['user', 'firstname', 'secondname', 'email', 'city', 'phonenumber']


class TelegramUserSerializer(serializers.ModelSerializer):
    contact = UserContactSerializer(many=False, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = TelegramUser
        fields = '__all__'


class TopicSerializer(serializers.ModelSerializer):

    def get_description(self, obj):
        return clean_html(obj.description)

    def get_picture(self, obj):
        """Возвращает полный URL для изображения."""
        if obj.picture:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.picture.url)
            # Запасной вариант для локальной разработки
            return f"http://127.0.0.1:8000{obj.picture.url}"
        return None

    class Meta:
        model = Topic
        fields = '__all__'


class AnswerSerializer(serializers.ModelSerializer):
    description = serializers.SerializerMethodField()

    def get_description(self, obj):
        return clean_html(obj.description)

    class Meta:
        model = Answer
        fields = ['answer_id', 'description', 'serial_number', 'right']


class QuestionSerializer(serializers.ModelSerializer):
    description = serializers.SerializerMethodField()
    picture = serializers.SerializerMethodField()
    answers = AnswerSerializer(many=True, read_only=True)

    def get_description(self, obj):
        return clean_html(obj.description)

    def get_picture(self, obj):
        """Возвращает полный URL для изображения."""
        if obj.picture:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.picture.url)
            # Запасной вариант для локальной разработки
            return f"http://127.0.0.1:8000{obj.picture.url}"
        return None

    class Meta:
        model = Question
        fields = ['question_id', 'description', 'serial_number', 'picture', 'answers']


class TestSerializer(serializers.ModelSerializer):
    description = serializers.SerializerMethodField()
    questions = QuestionSerializer(many=True, read_only=True)

    def get_description(self, obj):
        return clean_html(obj.description)

    class Meta:
        model = Test
        fields = ['test_id', 'title', 'description', 'show_right_answer', 'questions']


class LessonSerializer(serializers.ModelSerializer):
    description = serializers.SerializerMethodField()
    picture = serializers.SerializerMethodField()

    def get_description(self, obj):
        return clean_html(obj.description)

    def get_picture(self, obj):
        """Возвращает полный URL для изображения."""
        if obj.picture:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.picture.url)
            # Запасной вариант для локальной разработки
            return f"http://127.0.0.1:8000{obj.picture.url}"
        return None

    class Meta:
        model = Lesson
        fields = ['lesson_id', 'title', 'description', 'picture', 'serial_number']


class VideoSummarySerializer(serializers.ModelSerializer):
    description = serializers.SerializerMethodField()
    picture = serializers.SerializerMethodField()

    def get_description(self, obj):
        return clean_html(obj.description)

    def get_picture(self, obj):
        """Возвращает полный URL для изображения."""
        if obj.picture:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.picture.url)
            # Запасной вариант для локальной разработки
            return f"http://127.0.0.1:8000{obj.picture.url}"
        return None

    class Meta:
        model = VideoSummary
        fields = ['summary_id', 'title', "description", "picture"]


class VideoSerializer(serializers.ModelSerializer):
    summaries = VideoSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Video
        fields = '__all__'


class PracticeSerializer(serializers.ModelSerializer):
    description = serializers.SerializerMethodField()
    exercise = serializers.SerializerMethodField()

    def get_description(self, obj):
        return clean_html(obj.description)

    def get_exercise(self, obj):
        """Возвращает полный URL для файла с практическими заданиями."""
        if obj.exercise:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.exercise.url)
            # Запасной вариант для локальной разработки
            return f"http://127.0.0.1:8000{obj.exercise.url}"
        return None

    class Meta:
        model = Practice
        fields = '__all__'


class UserAvailabilitySerializer(serializers.ModelSerializer):
    topics = TopicSerializer(many=True, read_only=True)
    lessons = LessonSerializer(many=True, read_only=True)
    videos = VideoSerializer(many=True, read_only=True)
    tests = TestSerializer(many=True, read_only=True)
    practices = PracticeSerializer(many=True, read_only=True)

    class Meta:
        model = UserAvailability
        fields = '__all__'
