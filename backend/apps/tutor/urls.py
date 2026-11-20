from django.urls import path

from apps.tutor.views import (
    TutorChatStreamView,
    TutorChatView,
    TutorDocumentUploadView,
    TutorSessionDetailView,
    TutorSessionListView,
)

app_name = "tutor"

urlpatterns = [
    path("tutor/chat/", TutorChatView.as_view(), name="chat"),
    path("tutor/chat/stream/", TutorChatStreamView.as_view(), name="chat_stream"),
    path("tutor/upload/", TutorDocumentUploadView.as_view(), name="upload"),
    path("tutor/sessions/", TutorSessionListView.as_view(), name="session_list"),
    path("tutor/sessions/<str:session_id>/", TutorSessionDetailView.as_view(), name="session_detail"),
]