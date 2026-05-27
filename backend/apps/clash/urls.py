from django.urls import path
from . import views

urlpatterns = [
    path("clash/create/",                  views.create_clash,   name="clash_create"),
    path("clash/join/",                    views.join_clash,     name="clash_join"),
    path("clash/<str:room_code>/",         views.room_info,      name="clash_room_info"),
    path("clash/<str:room_code>/results/", views.clash_results, name="clash_results"),
]
