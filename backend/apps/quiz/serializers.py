"""Request serializers for the quiz API."""

from rest_framework import serializers


class QuizGenerateRequestSerializer(serializers.Serializer):
    subject = serializers.CharField(required=False, allow_blank=True, default="General")
    extractedText = serializers.CharField(required=False, allow_blank=True, default="")
    num_mcq = serializers.IntegerField(required=False, default=7, min_value=0, max_value=30)
    num_short = serializers.IntegerField(required=False, default=0, min_value=0, max_value=10)
    difficulty = serializers.CharField(required=False, allow_blank=True, default="medium")
    source_type = serializers.CharField(required=False, allow_blank=True, default="text")
    source_filename = serializers.CharField(required=False, allow_blank=True, default="")
    quiz_time = serializers.IntegerField(required=False, default=10, min_value=1, max_value=180)


class QuizSubmitRequestSerializer(serializers.Serializer):
    quiz_data = serializers.DictField()
    user_answers = serializers.DictField(required=False, default=dict)
    quiz_id = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    duration_minutes = serializers.IntegerField(required=False, default=0, min_value=0)
    time_limit = serializers.IntegerField(required=False, default=0, min_value=0)
    exam_mode = serializers.BooleanField(required=False, default=False)


class QuizYouTubeRequestSerializer(serializers.Serializer):
    url = serializers.URLField()
