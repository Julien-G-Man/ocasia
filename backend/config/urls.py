"""
URL configuration for lamla project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.urls import path, include
from django.conf.urls.static import static
from apps.core.views import HealthCheckView, warmup

urlpatterns = [
    path('warmup/', warmup),
    path('health/', HealthCheckView.as_view(), name="health"),
    path('admin/', admin.site.urls),
    
    path('api/', include("apps.chatbot.urls")),
    path('api/', include("apps.quiz.urls")),
    path('api/', include("apps.flashcards.urls")),
    path('api/', include("apps.accounts.urls")),
    path('api/', include("apps.dashboard.urls")),
    path('api/', include("apps.materials.urls")),
    path('api/', include("apps.subscriptions.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.
                          MEDIA_URL, document_root=settings.MEDIA_ROOT)