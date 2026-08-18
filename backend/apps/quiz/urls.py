from django.urls import path
from . import async_views, download_helpers, extract_text

urlpatterns = [
    # High-performance async proxy endpoints
    path("quiz/generate/",                  async_views.generate_quiz_api_async, name="generate_quiz_api"),
    path("quiz/ajax-extract-text/",         extract_text.ajax_extract_text, name="ajax_extract_text"),
    path("quiz/extract-youtube/",           async_views.extract_youtube_transcript, name="extract_youtube"),
    path("quiz/submit/",                    async_views.submit_quiz_api_async, name="submit_quiz_api"),
    path("quiz/download/",                  download_helpers.download_quiz_results, name="download_quiz_results"),
    path('quiz/history/',                   async_views.QuizHistoryView.as_view()),
    path('quiz/sessions/<int:session_id>/', async_views.QuizReplayView.as_view()),
    path('quiz/weak-areas/',                async_views.WeakAreasView.as_view()),
    path('quiz/due-topics/',                async_views.DueTopicsView.as_view()),
]