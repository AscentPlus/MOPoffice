from django.urls import path
from . import views

urlpatterns = [
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.create_user, name='create_user'),
    path('users/created/', views.user_created_success, name='user_created_success'),
    path('users/<int:user_id>/edit/', views.edit_user, name='edit_user'),
    path('users/<int:user_id>/reset-password/', views.reset_user_password, name='reset_user_password'),
    path('users/<int:user_id>/toggle/', views.toggle_user_status, name='toggle_user_status'),
    
    # Post management
    path('posts/', views.post_list, name='post_list'),
    path('posts/create/', views.create_post, name='create_post'),
    path('posts/<int:post_id>/edit/', views.edit_post, name='edit_post'),
    path('posts/<int:post_id>/toggle/', views.toggle_post_status, name='toggle_post_status'),

    # Master Data Management
    path('master-data/', views.master_data_index, name='master_data_index'),
    path('master-data/<slug:category_slug>/', views.master_data_list, name='master_data_list'),
    path('master-data/<slug:category_slug>/create/', views.master_data_create, name='master_data_create'),
    path('master-data/<slug:category_slug>/<int:item_id>/edit/', views.master_data_edit, name='master_data_edit'),
    path('master-data/<slug:category_slug>/<int:item_id>/toggle/', views.master_data_toggle, name='master_data_toggle'),
]
