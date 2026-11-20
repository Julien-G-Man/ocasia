from django.urls import path

from apps.tutor.views import TutorChatStreamView, TutorChatView

app_name = "tutor"

urlpatterns = [
    path("tutor/chat/", TutorChatView.as_view(), name="chat"),
    path("tutor/chat/stream/", TutorChatStreamView.as_view(), name="chat_stream"),
]
