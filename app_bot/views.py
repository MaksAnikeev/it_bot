import html
import logging
import re

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404, render
from django.utils.html import strip_tags
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .forms import TopicForm
from .models import (Lesson, Practice, Question, StartUserAvailability, Tariff,
                     TelegramUser, Test, Topic, UserAvailability, UserContact,
                     Video, UserDone)
from .serializers import (LessonSerializer, PaymentSerializer,
                          PracticeSerializer, QuestionSerializer,
                          TariffSerializer, TelegramUserSerializer,
                          TestSerializer, TopicSerializer,
                          UserAvailabilitySerializer, UserContactSerializer,
                          VideoSerializer)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def index_page(request):
    form = TopicForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        topic = form.cleaned_data.get("topic")
        video = form.cleaned_data.get("video")
    else:
        topic = None
        video = None

    lessons = Lesson.objects.filter(topic=topic)

    for lesson in lessons:
        decoded_text = html.unescape(lesson.description)
        clean_text = strip_tags(decoded_text)
        clean_text = re.sub(r'[\xa0\u200d]', ' ', clean_text)
        lesson.clean_description = clean_text

    if video and 'youtu.be' in video.video_link:
        video_id = video.video_link.split('youtu.be/')[-1]  # Извлекаем ID (например, CPo86DyaYF8)
        embed_video_link = f"https://www.youtube.com/embed/{video_id}"
    elif video and 'youtube.com/watch?v=' in video.video_link:
        video_id = video.video_link.split('watch?v=')[-1]
        embed_video_link = f"https://www.youtube.com/embed/{video_id}"
    elif video:
        embed_video_link = video.video_link  # Для других типов ссылок оставляем как есть
    else:
        embed_video_link = None

    context = {
        'lessons': lessons,
        'form': form,
        'video': video,
        'embed_video_link': embed_video_link  # Добавляем готовую ссылку
    }
    return render(request, 'index.html', context)


@api_view(['GET'])
def get_user(request, telegram_id):
    """
    Получение данных о пользователе через сериализатор.
    Если пользователя нет в БД - возвращает 502 статус.
    """
    try:
        user = TelegramUser.objects.get(tg_id=telegram_id)
    except ObjectDoesNotExist:
        return Response(
            {'status': 'false', 'message': 'user not found'},
            status=status.HTTP_502_BAD_GATEWAY
        )

    serializer = TelegramUserSerializer(user)
    return Response(serializer.data, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
def add_user(request):
    """
    Добавление пользователя в БД с валидацией через сериализатор и DRF Response.
    """
    serializer = TelegramUserSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {'status': 'true', 'message': 'user created'},
            status=status.HTTP_200_OK
        )
    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST
    )


@api_view(['GET'])
def get_topics(request):
    """Возвращает название всех тем."""
    topics = Topic.objects.all()
    serializer = TopicSerializer(topics, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_topic(request, topic_title):
    """
    Возвращает всю информацию по теме с преобразованием в сериалайзере относительного URL в полный URL для изображения.
    """
    logger.info(f"Received topic_title: {topic_title}")
    try:
        topic = get_object_or_404(Topic, title=topic_title)
        serializer = TopicSerializer(topic, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error fetching topic: {str(e)}")
        return Response(
            {"status": "false", "message": f"Topic '{topic_title}' not found"},
            status=status.HTTP_404_NOT_FOUND
        )


@csrf_exempt
@api_view(['POST'])
def add_user_contact(request):
    """
    Добавление контактов пользователя в БД с валидацией через сериализатор и DRF Response.
    """
    logger.info(f"Данные для создания контактов: {request.data}")
    serializer = UserContactSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {'status': 'true', 'message': 'user created'},
            status=status.HTTP_200_OK
        )
    logger.error(f"Validation errors: {serializer.errors}")
    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST
    )


@api_view(['GET'])
def get_test(request, test_title):
    """Отправляем тест с вопросами и ответами."""
    logger.info(f"Запрос теста: {test_title}")
    try:
        test = Test.objects.get(title=test_title)
        serializer = TestSerializer(test)
        logger.info(f"Тест '{test_title}' успешно найден")
        return Response(serializer.data)
    except Test.DoesNotExist:
        logger.error(f"Тест '{test_title}' не найден")
        return Response({"error": f"Тест '{test_title}' не найден"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Ошибка при получении теста '{test_title}': {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_tariffs(request):
    """
    Отправляем информацию о тарифах.
    """
    tariffs = Tariff.objects.all()
    if tariffs:
        serializer = TariffSerializer(tariffs,  many=True)
        return Response(serializer.data)
    return Response({"error": "No tariff available"}, status=404)


@api_view(['GET'])
def get_tariff(request, tariff_title):
    """
    Возвращает всю информацию по тарифу.
    """
    logger.info(f"Received tariff_title: {tariff_title}")
    try:
        tariff = get_object_or_404(Tariff, title=tariff_title)
        serializer = TariffSerializer(tariff)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error fetching tariff: {str(e)}")
        return Response(
            {"status": "false", "message": f"Tariff '{tariff_title}' not found"},
            status=status.HTTP_404_NOT_FOUND
        )


@csrf_exempt
@api_view(['POST'])
def add_payment(request):
    """Добавление платежа и обновление роли пользователя."""
    data = request.data
    try:
        # Извлекаем объекты
        tariff = Tariff.objects.get(title=data['tariff'])
        user = TelegramUser.objects.get(user_id=data['user'])
        # Формируем данные для сериализатора
        payment_info = {
            'amount': data['amount'],
            'user': user.user_id,
            'access_date_start': data['access_date_start'],
            'access_date_finish': data['access_date_finish'],
            'tariff': tariff.tariff_id,
            'status': data['status'],
            'service_description': data['service_description']
        }
        serializer = PaymentSerializer(data=payment_info)
        if serializer.is_valid():
            serializer.save()
            # Обновляем роль пользователя
            user.role = 'client'
            user.save()
            return Response(
                {'status': 'true', 'message': 'Payment created and user role updated'},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except (Tariff.DoesNotExist, TelegramUser.DoesNotExist) as e:
        return Response({'error': f"Объект не найден: {str(e)}"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_available_topic(request, telegram_id):
    """
    Возвращает информацию по доступным пользователю темам.
    """
    logger.info(f"Received telegram_id: {telegram_id}")
    try:
        user = get_object_or_404(TelegramUser, tg_id=telegram_id)
        user_availability = UserAvailability.objects.get(user=user.user_id)
        serializer = UserAvailabilitySerializer(user_availability)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error fetching topic: {str(e)}")
        return Response(
            {"status": "false", "message": f"User with '{telegram_id}' not found"},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
def get_topic_lessons(request, topic_title):
    """
    Возвращает информацию по урокам в выбранной теме.
    """
    logger.info(f"Received topic_title: {topic_title}")
    try:
        lessons = Lesson.objects.filter(topic__title=topic_title)
        serializer = LessonSerializer(lessons,  many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error fetching lessons: {str(e)}")
        return Response(
            {"status": "false", "message": f"Topic '{topic_title}' not found"},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
def get_available_lesson(request, topic_title, lesson_title):
    """
    Возвращает информацию по выбранному пользователем уроку.
    """
    logger.info(f"Received topic_title: {topic_title}")
    logger.info(f"Received lesson_title: {lesson_title}")
    try:
        topic = Topic.objects.get(title=topic_title)
        lesson = Lesson.objects.get(title=lesson_title, topic=topic)
        serializer = LessonSerializer(lesson)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Topic.DoesNotExist:
        return Response({'error': f"Тема '{topic_title}' не найдена"}, status=status.HTTP_404_NOT_FOUND)
    except Lesson.DoesNotExist:
        return Response({'error': f"Урок '{lesson_title}' не найден в теме '{topic_title}'"},
                        status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_lessons(request):
    """Возвращает название всех уроков."""
    lessons = Lesson.objects.all()
    serializer = LessonSerializer(lessons, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_lesson_video(request, topic_title, lesson_title):
    """
    Возвращает информацию по видео в выбранном уроке.
    """
    logger.info(f"Received topic_title: {topic_title}")
    logger.info(f"Received lesson_title: {lesson_title}")
    try:
        topic = Topic.objects.get(title=topic_title)
        lesson = Lesson.objects.get(title=lesson_title, topic=topic)
        video = Video.objects.filter(lesson=lesson.lesson_id)
        serializer = VideoSerializer(video, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Topic.DoesNotExist:
        return Response({'error': f"Тема '{topic_title}' не найдена"}, status=status.HTTP_404_NOT_FOUND)
    except Lesson.DoesNotExist:
        return Response({'error': f"Урок '{lesson_title}' не найден в теме '{topic_title}'"},
                        status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_video_info(request, lesson_title, video_title):
    """
    Возвращает видео и его конспект.
    """
    logger.info(f"Received video_title: {video_title}")
    logger.info(f"Received lesson_title: {lesson_title}")
    try:
        lesson = Lesson.objects.get(title=lesson_title)
        video = Video.objects.get(title=video_title, lesson=lesson.lesson_id)
        serializer = VideoSerializer(video)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Lesson.DoesNotExist:
        return Response({'error': f"Урок '{lesson_title}' не найдена"}, status=status.HTTP_404_NOT_FOUND)
    except Video.DoesNotExist:
        return Response({'error': f"Видео '{video_title}' не найден в уроке '{lesson_title}'"},
                        status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_videos(request):
    """Возвращает название всех видео."""
    videos = Video.objects.all()
    serializer = VideoSerializer(videos, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_video_question(request, video_id):
    """Возвращает контрольный вопрос для видео."""
    try:
        question_for_video = Question.objects.get(video__video_id=video_id)
        serializer = QuestionSerializer(question_for_video)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Question.DoesNotExist:
        return Response({'error': f"Вопрос к видео '{video_id}' не найден"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_lesson_tests(request, topic_title, lesson_title):
    """
    Возвращает информацию по тестам в выбранном уроке.
    """
    logger.info(f"Запрос тестов для темы '{topic_title}', урока '{lesson_title}'")
    try:
        topic = Topic.objects.get(title=topic_title)
        lesson = Lesson.objects.get(title=lesson_title, topic=topic)
        tests = Test.objects.filter(lesson=lesson.lesson_id)
        logger.info(f"Найдено тестов: {tests.count()}")

        if not tests.exists():
            logger.info(f"Тесты для урока '{lesson_title}' не найдены")
            return Response(
                {'status': 'success', 'data': [], 'message': 'Тесты отсутствуют'},
                status=status.HTTP_200_OK
            )

        serializer = TestSerializer(tests, many=True)
        logger.debug(f"Сериализованные данные: {serializer.data}")
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Topic.DoesNotExist:
        logger.error(f"Тема '{topic_title}' не найдена")
        return Response({'error': f"Тема '{topic_title}' не найдена"}, status=status.HTTP_404_NOT_FOUND)
    except Lesson.DoesNotExist:
        logger.error(f"Урок '{lesson_title}' не найден в теме '{topic_title}'")
        return Response(
            {'error': f"Урок '{lesson_title}' не найден в теме '{topic_title}'"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Ошибка в get_lesson_tests: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_tests(request):
    """Возвращает название всех тестов."""
    tests = Test.objects.all()
    serializer = TestSerializer(tests, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


def add_new_content(user_availability: 'UserAvailability',
                    topics: set = None,
                    lessons: set = None,
                    videos: set = None,
                    tests: set = None,
                    practices: set = None) -> None:
    """
    Добавляет новый контент в UserAvailability, избегая дубликатов.

    Args:
        user_availability: Объект UserAvailability, куда добавляется контент.
        topics, lessons, videos, tests, practices: Наборы объектов для добавления (опционально).
    """
    # Получаем текущие доступные объекты пользователя
    current_topics = set(user_availability.topics.all())
    current_lessons = set(user_availability.lessons.all())
    current_videos = set(user_availability.videos.all())
    current_tests = set(user_availability.tests.all())
    current_practices = set(user_availability.practices.all())

    # Проверяем и добавляем только новые объекты
    if topics:
        new_topics = topics - current_topics
        if new_topics:
            user_availability.topics.add(*new_topics)
    if lessons:
        new_lessons = lessons - current_lessons
        if new_lessons:
            user_availability.lessons.add(*new_lessons)
    if videos:
        new_videos = videos - current_videos
        if new_videos:
            user_availability.videos.add(*new_videos)
    if tests:
        new_tests = tests - current_tests
        if new_tests:
            user_availability.tests.add(*new_tests)
    if practices:
        new_practices = practices - current_practices
        if new_practices:
            user_availability.practices.add(*new_practices)
    # Сохраняем изменения
    user_availability.save()


def add_done_content(user_done: 'UserDone',
                    topics: set = None,
                    lessons: set = None,
                    videos: set = None,
                    tests: set = None,
                    practices: set = None) -> None:
    """
    Добавляет выполненный контент в UserDone, избегая дубликатов.

    Args:
        user_done: Объект UserDone, куда добавляется контент.
        topics, lessons, videos, tests, practices: Наборы объектов для добавления (опционально).
    """
    # Получаем текущие выполненные объекты пользователя
    current_topics = set(user_done.topics.all())
    current_lessons = set(user_done.lessons.all())
    current_videos = set(user_done.videos.all())
    current_tests = set(user_done.tests.all())
    current_practices = set(user_done.practices.all())
    # Проверяем и добавляем только новые объекты
    # Логика для тем и уроков - добавляем предыдущий по serial_number
    if topics:
        for topic in topics:
            done_topic_serial_number = int(topic.serial_number) - 1
            if done_topic_serial_number > 0:
                done_topic = Topic.objects.filter(serial_number=done_topic_serial_number).first()
                if done_topic and done_topic not in current_topics:
                    user_done.topics.add(done_topic)
                    lesson_done = Lesson.objects.filter(topic=done_topic).last()
                    user_done.lessons.add(lesson_done)

    if lessons:
        for lesson in lessons:
            done_lesson_serial_number = int(lesson.serial_number) - 1
            if done_lesson_serial_number > 0:
                done_lesson = Lesson.objects.filter(serial_number=done_lesson_serial_number).first()
                if done_lesson and done_lesson not in current_lessons:
                    user_done.lessons.add(done_lesson)

    # Логика для видео, тестов и практик - добавляем переданные объекты
    if videos:
        new_done_videos = videos - current_videos
        if new_done_videos:
            user_done.videos.add(*new_done_videos)
    if tests:
        new_done_tests = tests - current_tests
        if new_done_tests:
            user_done.tests.add(*new_done_tests)
    if practices:
        new_done_practices = practices - current_practices
        if new_done_practices:
            user_done.practices.add(*new_done_practices)


def get_serial_numbers(content):
    """Возвращает последовательность получаемых объектов."""
    hasattr(content, 'serial_number') and content.serial_number is not None
    return content.serial_number


def get_next_step(topics: set = None,
                  lessons: set = None,
                  videos: set = None,
                  tests: set = None,
                  practices: set = None) -> tuple[str, dict]:
    """
    Определяем следующий шаг после просмотра видео

    Args:
        topics, lessons, videos, tests, practices: Наборы объектов доступных после просмотра видео (опционально).
    """
    logger.info(f"get_next_step called with: topics={len(topics or [])}, lessons={len(lessons or [])}, "
                f"videos={len(videos or [])}, tests={len(tests or [])}, practices={len(practices or [])}")

    # Проверяем, что доступно после видео
    if topics:
        next_topic = min(topics, key=get_serial_numbers)
        next_step = 'topic'
        next_step_params = {'topic_title': next_topic.title}
    elif lessons:
        next_lesson = min(lessons, key=get_serial_numbers)
        next_step = 'lesson'
        try:
            topic = Topic.objects.get(lessons__title=next_lesson.title)
        except Lesson.DoesNotExist:
            logger.error(f"Lesson '{next_lesson.title}' not found in Topic")
            return '', {}
        next_step_params = {'lesson_title': next_lesson.title,
                            'topic_title': topic.title}
    elif videos:
        next_video = min(videos, key=get_serial_numbers)
        next_step = 'video'
        try:
            lesson = Lesson.objects.get(videos__title=next_video.title)
        except Lesson.DoesNotExist:
            logger.error(f"Lesson for video '{next_video.title}' not found")
            return '', {}
        next_step_params = {'video_title': next_video.title,
                            'lesson_title': lesson.title}
    elif tests:
        next_test = list(tests)[0]
        next_step = 'test'
        next_step_params = {'test_title': next_test.title}

    elif practices:
        next_practice = list(practices)[0]
        next_step = 'practice'
        try:
            lesson = Lesson.objects.get(practices__title=next_practice.title)
        except Lesson.DoesNotExist:
            logger.error(f"Lesson for practice '{next_practice.title}' not found")
            return '', {}
        next_step_params = {'practice_title': next_practice.title,
                            'lesson_title': lesson.title}
    else:
        logger.warning("No next step or content found")
        next_step = None
        next_step_params = {}

    return next_step, next_step_params


@api_view(['GET'])
def get_lesson_video(request, topic_title, lesson_title):
    """
    Возвращает информацию по видео в выбранном уроке.
    """
    logger.info(f"Received topic_title: {topic_title}")
    logger.info(f"Received lesson_title: {lesson_title}")
    try:
        topic = Topic.objects.get(title=topic_title)
        lesson = Lesson.objects.get(title=lesson_title, topic=topic)
        video = Video.objects.filter(lesson=lesson.lesson_id)
        serializer = VideoSerializer(video, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Topic.DoesNotExist:
        return Response({'error': f"Тема '{topic_title}' не найдена"}, status=status.HTTP_404_NOT_FOUND)
    except Lesson.DoesNotExist:
        return Response({'error': f"Урок '{lesson_title}' не найден в теме '{topic_title}'"},
                        status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['POST'])
def add_start_content(request):
    """Добавление стартового контента пользователю, избегая дубликатов."""
    data = request.data
    try:
        # Извлекаем объекты
        start_availability = StartUserAvailability.objects.get(tariff__title=data['tariff'])
        user = TelegramUser.objects.get(user_id=data['user'])
        user_availability, created = UserAvailability.objects.get_or_create(user=user)

        # Получаем стартовые объекты
        start_topics = set(start_availability.topics.all())
        start_lessons = set(start_availability.lessons.all())
        start_videos = set(start_availability.videos.all())
        start_tests = set(start_availability.tests.all())
        start_practices = set(start_availability.practices.all())

        # Добавляем новый контент через универсальную функцию
        add_new_content(
            user_availability=user_availability,
            topics=start_topics,
            lessons=start_lessons,
            videos=start_videos,
            tests=start_tests,
            practices=start_practices
        )

        return Response(
            {'status': 'true', 'message': 'Start content added successfully'},
            status=status.HTTP_201_CREATED
        )
    except StartUserAvailability.DoesNotExist:
        return Response({'error': f"Стартовый контент для тарифа '{data['tariff']}' не найден"},
                        status=status.HTTP_404_NOT_FOUND)
    except TelegramUser.DoesNotExist:
        return Response({'error': f"Пользователь с user_id '{data['user']}' не найден"},
                        status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['POST'])
def add_content_after_video(request):
    """Добавление контента пользователю после просмотра видео."""
    data = request.data
    try:
        video = Video.objects.get(video_id=data['video_id'])
        user = TelegramUser.objects.get(user_id=data['user_id'])
        user_availability, created = UserAvailability.objects.get_or_create(user=user)
        # Получаем объекты, которые открываются после просмотра видео
        next_topics = set(video.next_topics.all())
        next_lessons = set(video.next_lessons.all())
        next_videos = set(video.next_videos.all())
        next_tests = set(video.next_tests.all())
        next_practices = set(video.next_practices.all())

        # Добавляем новый контент
        add_new_content(
            user_availability=user_availability,
            topics=next_topics,
            lessons=next_lessons,
            videos=next_videos,
            tests=next_tests,
            practices=next_practices
        )

        # Добавляем выполненный пользователем контент
        user_done, created = UserDone.objects.get_or_create(user=user)
        add_done_content(
            user_done=user_done,
            topics=next_topics,
            lessons=next_lessons,
            videos={video},
        )

        # Формируем имена для ответа
        next_topics_name = [next_topic.title for next_topic in next_topics] or ["Нет новых тем"]
        next_lessons_name = [next_lesson.title for next_lesson in next_lessons] or ["Нет новых уроков"]
        next_videos_name = [next_video.title for next_video in next_videos] or ["Нет новых видео"]
        next_tests_name = [next_test.title for next_test in next_tests] or ["Нет новых тестов"]
        next_practices_name = [next_practice.title for next_practice in next_practices] or ["Нет новых практик"]
        next_content = {
            "next_topics_name": next_topics_name,
            "next_lessons_name": next_lessons_name,
            "next_videos_name": next_videos_name,
            "next_tests_name": next_tests_name,
            "next_practices_name": next_practices_name,
        }
        next_step, next_step_params = get_next_step(topics=next_topics,
                                                    lessons=next_lessons,
                                                    videos=next_videos,
                                                    tests=next_tests,
                                                    practices=next_practices)
        if not next_step and not any([next_topics, next_lessons, next_videos, next_tests, next_practices]):
            logger.warning(f"No next step or content found for video_id={data['video_id']}")
            return Response(
                {'status': 'false', 'message': 'Нет доступного следующего контента', "next_content": next_content},
                status=status.HTTP_200_OK
            )

        return Response(
            {'status': 'true',
             'message': 'Content added after video',
             "next_content": next_content,
             "next_step": next_step,
             "next_step_params": next_step_params
             },
            status=status.HTTP_201_CREATED
        )
    except Video.DoesNotExist:
        return Response({'error': f"Видео с ID '{data['video_id']}' не найдено"},
                        status=status.HTTP_404_NOT_FOUND)
    except TelegramUser.DoesNotExist:
        return Response({'error': f"Пользователь с user_id '{data['user_id']}' не найден"},
                        status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['POST'])
def add_content_after_test(request):
    """Добавление контента пользователю после успешного прохождения теста."""
    data = request.data
    try:
        test = Test.objects.get(test_id=data['test_id'])
        user = TelegramUser.objects.get(user_id=data['user_id'])
        user_availability, created = UserAvailability.objects.get_or_create(user=user)

        # Получаем объекты, которые открываются после прохождения теста
        next_topics = set(test.next_topics.all())
        next_lessons = set(test.next_lessons.all())
        next_videos = set(test.next_videos.all())
        next_tests = set(test.next_tests.all())
        next_practices = set(test.next_practices.all())

        # Добавляем новый контент
        add_new_content(
            user_availability=user_availability,
            topics=next_topics,
            lessons=next_lessons,
            videos=next_videos,
            tests=next_tests,
            practices=next_practices
        )
        # Добавляем выполненный пользователем контент
        user_done, created = UserDone.objects.get_or_create(user=user)
        add_done_content(
            user_done=user_done,
            topics=next_topics,
            lessons=next_lessons,
            tests={test},
        )

        # Формируем имена для ответа
        next_topics_name = [next_topic.title for next_topic in next_topics] or ["Нет новых тем"]
        next_lessons_name = [next_lesson.title for next_lesson in next_lessons] or ["Нет новых уроков"]
        next_videos_name = [next_video.title for next_video in next_videos] or ["Нет новых видео"]
        next_tests_name = [next_test.title for next_test in next_tests] or ["Нет новых тестов"]
        next_practices_name = [next_practice.title for next_practice in next_practices] or ["Нет новых практик"]

        next_content = {
            "next_topics_name": next_topics_name,
            "next_lessons_name": next_lessons_name,
            "next_videos_name": next_videos_name,
            "next_tests_name": next_tests_name,
            "next_practices_name": next_practices_name,
        }
        next_step, next_step_params = get_next_step(topics=next_topics,
                                                    lessons=next_lessons,
                                                    videos=next_videos,
                                                    tests=next_tests,
                                                    practices=next_practices)
        if not next_step and not any([next_topics, next_lessons, next_videos, next_tests, next_practices]):
            logger.warning(f"No next step or content found for video_id={data['video_id']}")
            return Response(
                {'status': 'false', 'message': 'Нет доступного следующего контента', "next_content": next_content},
                status=status.HTTP_200_OK
            )

        return Response(
            {
                'status': 'true',
                'message': 'Content added after test',
                "next_content": next_content,
                "next_step": next_step,
                "next_step_params": next_step_params
            },
            status=status.HTTP_201_CREATED
        )
    except Test.DoesNotExist:
        return Response({'error': f"Тест с ID '{data['test_id']}' не найден"},
                        status=status.HTTP_404_NOT_FOUND)
    except TelegramUser.DoesNotExist:
        return Response({'error': f"Пользователь с user_id '{data['user_id']}' не найден"},
                        status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_admin_info(request):
    """
    Получение данных о админе через сериализатор.
    Если пользователя нет в БД - возвращает 502 статус.
    """
    try:
        user = TelegramUser.objects.filter(role='admin').first()
        serializer = TelegramUserSerializer(user)
        logger.info(f"Администратор найден {user.tg_name}")
        return Response(
            serializer.data, status=status.HTTP_200_OK
        )

    except TelegramUser.DoesNotExist:
        logger.error(f"Администратор не найден в теме")
        return Response(
            {'status': 'false', 'message': 'user not found'},
            status=status.HTTP_502_BAD_GATEWAY
        )


@api_view(['GET'])
def get_lesson_practices(request, topic_title, lesson_title):
    """
    Возвращает информацию по практическим заданиям в выбранном уроке.
    """
    logger.info(f"Запрос практик для темы '{topic_title}', урока '{lesson_title}'")
    try:
        topic = Topic.objects.get(title=topic_title)
        lesson = Lesson.objects.get(title=lesson_title, topic=topic)
        practices = Practice.objects.filter(lesson=lesson.lesson_id)
        logger.info(f"Найдено тестов: {practices.count()}")

        if not practices.exists():
            logger.info(f"Практические задания для урока '{lesson_title}' не найдены")
            return Response(
                {'status': 'success', 'data': [], 'message': 'Тесты отсутствуют'},
                status=status.HTTP_200_OK
            )

        serializer = PracticeSerializer(practices, many=True)
        logger.debug(f"Сериализованные данные: {serializer.data}")
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Topic.DoesNotExist:
        logger.error(f"Тема '{topic_title}' не найдена")
        return Response({'error': f"Тема '{topic_title}' не найдена"}, status=status.HTTP_404_NOT_FOUND)
    except Lesson.DoesNotExist:
        logger.error(f"Урок '{lesson_title}' не найден в теме '{topic_title}'")
        return Response(
            {'error': f"Урок '{lesson_title}' не найден в теме '{topic_title}'"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Ошибка в get_lesson_practices: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_practice_info(request, lesson_title, practice_title):
    """
    Возвращает файл практики.
    """
    logger.info(f"Received video_title: {practice_title}")
    logger.info(f"Received lesson_title: {lesson_title}")
    try:
        lesson = Lesson.objects.get(title=lesson_title)
        practice = Practice.objects.get(title=practice_title, lesson=lesson.lesson_id)
        serializer = PracticeSerializer(practice)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Lesson.DoesNotExist:
        return Response({'error': f"Урок '{lesson_title}' не найдена"}, status=status.HTTP_404_NOT_FOUND)
    except Practice.DoesNotExist:
        return Response({'error': f"Практическое задание '{practice_title}' не найден в уроке '{lesson_title}'"},
                        status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_practices(request):
    """Возвращает название всех практических заданий."""
    practices = Practice.objects.all()
    serializer = PracticeSerializer(practices, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
def add_content_after_practice(request):
    """Добавление контента пользователю после успешного прохождения практики."""
    data = request.data
    try:
        practice = Practice.objects.get(practice_id=data['practice_id'])
        user = TelegramUser.objects.get(tg_id=data['telegram_id'])
        user_availability, created = UserAvailability.objects.get_or_create(user=user)

        # Получаем объекты, которые открываются после прохождения теста
        next_topics = set(practice.next_topics.all())
        next_lessons = set(practice.next_lessons.all())
        next_videos = set(practice.next_videos.all())
        next_tests = set(practice.next_tests.all())
        next_practices = set(practice.next_practices.all())

        # Добавляем новый контент
        add_new_content(
            user_availability=user_availability,
            topics=next_topics,
            lessons=next_lessons,
            videos=next_videos,
            tests=next_tests,
            practices=next_practices
        )

        # Добавляем выполненный пользователем контент
        user_done, created = UserDone.objects.get_or_create(user=user)
        add_done_content(
            user_done=user_done,
            topics=next_topics,
            lessons=next_lessons,
            practices={practice},
        )
        # Формируем имена для ответа
        next_topics_name = [next_topic.title for next_topic in next_topics] or ["Нет новых тем"]
        next_lessons_name = [next_lesson.title for next_lesson in next_lessons] or ["Нет новых уроков"]
        next_videos_name = [next_video.title for next_video in next_videos] or ["Нет новых видео"]
        next_tests_name = [next_test.title for next_test in next_tests] or ["Нет новых тестов"]
        next_practices_name = [next_practice.title for next_practice in next_practices] or ["Нет новых практик"]

        next_content = {
            "next_topics_name": next_topics_name,
            "next_lessons_name": next_lessons_name,
            "next_videos_name": next_videos_name,
            "next_tests_name": next_tests_name,
            "next_practices_name": next_practices_name,
        }

        next_step, next_step_params = get_next_step(topics=next_topics,
                                                    lessons=next_lessons,
                                                    videos=next_videos,
                                                    tests=next_tests,
                                                    practices=next_practices)
        if not next_step and not any([next_topics, next_lessons, next_videos, next_tests, next_practices]):
            logger.warning(f"No next step or content found for video_id={data['video_id']}")
            return Response(
                {'status': 'false', 'message': 'Нет доступного следующего контента', "next_content": next_content},
                status=status.HTTP_200_OK
            )
        return Response(
            {'status': 'true',
             'message': 'Content added after video',
             "next_content": next_content,
             "next_step": next_step,
             "next_step_params": next_step_params
             },
            status=status.HTTP_201_CREATED
        )
    except Practice.DoesNotExist:
        return Response({'error': f"Practice с ID '{data['practice_id']}' не найден"},
                        status=status.HTTP_404_NOT_FOUND)
    except TelegramUser.DoesNotExist:
        return Response({'error': f"Пользователь с user_id '{data['telegram_id']}' не найден"},
                        status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_user_progress(request, telegram_id):
    """
    Возвращает информацию по прогрессу пользователя.
    """
    logger.info(f"Received telegram_id: {telegram_id}")
    try:
        user = TelegramUser.objects.get(tg_id=telegram_id)
        content_done, created = UserDone.objects.get_or_create(user=user)

        # Получаем пройденные объекты пользователя
        done_topics = content_done.topics.all()
        done_lessons = content_done.lessons.all()
        done_videos = content_done.videos.all()
        done_tests = content_done.tests.all()
        done_practices = content_done.practices.all()
        names_done_topics = [done_topic.title for done_topic in done_topics]
        names_done_lessons = [done_lesson.title for done_lesson in done_lessons]
        names_done_videos = [done_video.title for done_video in done_videos]
        names_done_tests = [done_test.title for done_test in done_tests]
        names_done_practices = [done_practice.title for done_practice in done_practices]
        payload = {
            'names_done': {
                'names_done_topics': names_done_topics,
                'names_done_lessons': names_done_lessons,
                'names_done_videos': names_done_videos,
                'names_done_tests': names_done_tests,
                'names_done_practices': names_done_practices},
            'quantity_done': {
                'quantity_done_topics': done_topics.count(),
                'quantity_done_lessons': done_lessons.count(),
                'quantity_done_videos': done_videos.count(),
                'quantity_done_tests': done_tests.count(),
                'quantity_done_practices': done_practices.count()},
            'quantity_all': {
                'topics': Topic.objects.all().count(),
                'lessons': Lesson.objects.all().count(),
                'videos': Video.objects.all().count(),
                'tests': Test.objects.all().count(),
                'practices': Practice.objects.all().count()
            }
        }
        return Response(payload, status=status.HTTP_200_OK)

    except TelegramUser.DoesNotExist:
        return Response({'error': f"Пользователь '{telegram_id}' не найден"},
                        status=status.HTTP_404_NOT_FOUND)
    except UserDone.DoesNotExist:
        return Response({'error': f"Выполненные задания для пользователя '{telegram_id}' не найдены"},
                        status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
