from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('api/bot/launch', views.launch_bot_api, name='launch_bot_api'),
    path('api/bot/status', views.status_bot_api, name='status_bot_api'),
    path('api/log_error', views.log_error, name='log_error'),
]
