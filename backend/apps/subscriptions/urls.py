from django.urls import path
from . import views

urlpatterns = [
    path("subscriptions/donate/initiate/", views.initiate_donation,  name="donate-initiate"),
    path("subscriptions/donate/verify/",   views.verify_donation,    name="donate-verify"),
    path("subscriptions/webhook/",         views.webhook,            name="paystack-webhook"),
    path("subscriptions/webhook",          views.webhook),
]
