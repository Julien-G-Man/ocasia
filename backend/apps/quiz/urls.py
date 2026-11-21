from django.urls import path

from . import views

urlpatterns = [
    path("quiz/generate/",                  views.QuizGenerateView.as_view(),       name="generate_quiz_api"),
    path("quiz/extract-text/",              views.QuizExtractTextView.as_view(),    name="extract_text"),
    path("quiz/ajax-extract-text/",         views.QuizExtractTextView.as_view(),    name="ajax_extract_text"),
    path("quiz/extract-youtube/",           views.QuizYouTubeExtractView.as_view(), name="extract_youtube"),
    path("quiz/submit/",                    views.QuizSubmitView.as_view(),         name="submit_quiz_api"),
    path("quiz/download/",                  views.QuizDownloadView.as_view(),       name="download_quiz_results"),
    path("quiz/history/",                   views.QuizHistoryView.as_view(),        name="quiz_history"),
    path("quiz/sessions/<int:session_id>/", views.QuizReplayView.as_view(),         name="quiz_replay"),
    path("quiz/weak-areas/",                views.WeakAreasView.as_view(),          name="weak_areas"),
    path("quiz/due-topics/",                views.DueTopicsView.as_view(),          name="due_topics"),
]
