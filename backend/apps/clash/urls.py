from django.urls import path
from . import views

urlpatterns = [
    path("clash/create/",                    views.create_clash,       name="clash_create"),
    path("clash/join/",                      views.join_clash,         name="clash_join"),
    path("clash/my/",                        views.my_clashes,         name="clash_my"),
    path("clash/my/<str:room_code>/",        views.my_clash_detail,    name="clash_my_detail"),
    path("clash/admin/",                     views.admin_clash_list,   name="clash_admin_list"),
    path("clash/admin/<str:room_code>/",     views.admin_clash_detail, name="clash_admin_detail"),
    path("clash/<str:room_code>/",           views.room_info,          name="clash_room_info"),
    path("clash/<str:room_code>/results/",   views.clash_results,      name="clash_results"),
]
