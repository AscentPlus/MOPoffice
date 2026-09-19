from django.urls import path

from . import views

urlpatterns = [
    path('', views.inbox, name='messaging_inbox'),
    path('start/', views.start_conversation, name='messaging_start'),
    path('attachments/<int:attachment_id>/download/', views.download_attachment, name='messaging_attachment_download'),
    # JSON API
    path('api/inbox/', views.api_inbox, name='messaging_api_inbox'),
    path('api/unread-count/', views.api_unread_count, name='messaging_api_unread'),
    path('api/presence/', views.api_presence, name='messaging_api_presence'),
    path('api/<int:conversation_id>/messages/', views.api_messages, name='messaging_api_messages'),
    path('api/<int:conversation_id>/send/', views.api_send, name='messaging_api_send'),
    path('<int:conversation_id>/send/', views.send_message_view, name='messaging_send'),
    path('<int:conversation_id>/', views.inbox, name='messaging_conversation'),
]
