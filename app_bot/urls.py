from django.http import HttpResponse
from django.urls import path

from .views import (add_content_after_practice, add_content_after_test,
                    add_content_after_video, add_payment, add_start_content,
                    add_user, add_user_contact, get_admin_info,
                    get_available_lesson, get_available_topic,
                    get_lesson_practices, get_lesson_tests, get_lesson_video,
                    get_lessons, get_practice_info, get_practices, get_tariff,
                    get_tariffs, get_test, get_tests, get_topic,
                    get_topic_lessons, get_topics, get_user, get_video_info,
                    get_video_question, get_videos, index_page)

app_name = "app_bot"

def health_check(request):
    return HttpResponse("OK", status=200)

urlpatterns = [
    path('', index_page, name="index_page"),
    path('tg_user/<int:telegram_id>', get_user),
    path('user/add/', add_user),
    path('topics/', get_topics),
    path('topic/<str:topic_title>/', get_topic),
    path('contact/add/', add_user_contact),
    path('start_test/<str:test_title>/', get_test),
    path('tariffs/', get_tariffs),
    path('tariff/<str:tariff_title>/', get_tariff),
    path('payment/add/', add_payment, name='add_payment'),
    path('available_topics/<int:telegram_id>/', get_available_topic),
    path('topic_lessons/<str:topic_title>/', get_topic_lessons),
    path('lesson/<str:topic_title>/<str:lesson_title>/', get_available_lesson),
    path('lessons/', get_lessons),
    path('lesson_video/<str:topic_title>/<str:lesson_title>/', get_lesson_video),
    path('video/<str:lesson_title>/<str:video_title>/', get_video_info),
    path('videos/', get_videos),
    path('video_question/<int:video_id>/', get_video_question),
    path('start_content/add/', add_start_content),
    path('next_content/add/', add_content_after_video),
    path('lesson_tests/<str:topic_title>/<str:lesson_title>/', get_lesson_tests),
    path('tests/', get_tests),
    path('next_content_test/add/', add_content_after_test),
    path('get_tg_admin/', get_admin_info),
    path('lesson_practices/<str:topic_title>/<str:lesson_title>/', get_lesson_practices),
    path('practice/<str:lesson_title>/<str:practice_title>/', get_practice_info),
    path('practices/', get_practices),
    path('next_content_practice/add/', add_content_after_practice),
    path('health/', health_check, name='health_check'),

]
