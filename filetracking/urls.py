from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password, name='change_password'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/summary/', views.summary_dashboard, name='summary_dashboard'),
    path('dashboard/summary/user/<int:user_id>/', views.user_pending_files_api, name='user_pending_files_api'),
    path('files/<int:file_id>/viewer/<int:doc_id>/', views.document_viewer_view, name='document_viewer'),
    path('files/create/', views.create_file, name='create_file'),
    path('inbox/', views.inbox_view, name='inbox'),
    path('files/shared/<int:file_id>/mark-read/', views.mark_as_read, name='mark_as_read'),
    path('files/sent/', views.sent_files_view, name='sent_files'),
    path('files/<int:file_id>/', views.file_detail, name='file_detail'),
    path('files/<int:file_id>/edit/', views.edit_file, name='edit_file'),
    path('documents/<int:doc_id>/delete/', views.delete_document, name='delete_document'),
    path('track/', views.track_file, name='track_file'),
    path('files/movement/<int:movement_id>/recall/', views.recall_file, name='recall_file'),
    path('files/approved/', views.approved_files_view, name='approved_files'),
    path('files/created/', views.created_files_view, name='created_files'),
    path('files/keep-in-files/', views.keep_in_files_view, name='keep_in_files'),
    path('documents/<int:doc_id>/download/', views.download_document, name='download_document'),
]
