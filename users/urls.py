from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'users'  # URL namespace'i ekledik

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='users:login', http_method_names=['get', 'post']), name='logout'),
    path('profile/', views.profile, name='profile'),
] 