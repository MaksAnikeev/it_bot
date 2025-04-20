from django import forms

from .models import Topic, Video  # Явный импорт модели Topic


class TopicForm(forms.Form):
    topic = forms.ModelChoiceField(
        queryset=Topic.objects.all(),
        required=False,
        label='миссия',
    )
    video = forms.ModelChoiceField(
        queryset=Video.objects.all(),
        required=False,
        label='видео',
    )
