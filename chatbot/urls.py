from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('chat-stream/', views.chat_stream, name='chat_stream'),
]
