from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.home, name='home'),
    path('logout/', views.logout_view, name='logout'),
    path('api/auth/login', views.auth_login_api, name='auth_login_api'),
    path('api/auth/signup', views.auth_signup_api, name='auth_signup_api'),
    path('api/auth/user', views.auth_user_api, name='auth_user_api'),
    path('auth/github/', views.github_oauth_start, name='github_oauth_start'),
    path('auth/github/callback/', views.github_oauth_callback, name='github_oauth_callback'),
    path('auth/google/', views.google_oauth_start, name='google_oauth_start'),
    path('auth/google/callback/', views.google_oauth_callback, name='google_oauth_callback'),
    path('api/bot/launch', views.launch_bot_api, name='launch_bot_api'),
    path('api/bot/status', views.status_bot_api, name='status_bot_api'),
    path('api/log_error', views.log_error, name='log_error'),
]
