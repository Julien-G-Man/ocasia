from django.urls import path
from . import async_views
from .dashboard_views import ChatHistoryView

urlpatterns = [
    path("chat/",                async_views.chatbot_api_async,           name="chatbot_api"),
    path("chat/file/",           async_views.chatbot_file_api_async,      name="chatbot_file_api"),
    path("chat/history/",        async_views.get_conversation_history,    name="get_history"),
    path("chat/history/clear/",  async_views.clear_conversation_history,  name="clear_history"),
    path("chat/history/rename/", async_views.rename_conversation_session, name="rename_history"),
    path("chatbot/history/",     ChatHistoryView.as_view(),               name="chat_history_dashboard"),
]
