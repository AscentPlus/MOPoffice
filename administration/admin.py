from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Department, Post, DocumentType, DocumentOrigin,
    DocumentPriority, TransitType, DocumentStatus, CustomUser, UserLoginLog, VoucherNumber
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['name', 'priority', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']
    ordering = ['priority']


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(DocumentOrigin)
class DocumentOriginAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(DocumentPriority)
class DocumentPriorityAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(TransitType)
class TransitTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(DocumentStatus)
class DocumentStatusAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'user_id', 'post', 'email', 'is_active', 'created_at']
    list_filter = ['is_active', 'post']
    search_fields = ['username', 'user_id', 'email']
    readonly_fields = ['user_id', 'created_at', 'updated_at']
    
    fieldsets = UserAdmin.fieldsets + (
        ('MOP Information', {
            'fields': ('user_id', 'post', 'mobile', 'created_by')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('MOP Information', {
            'fields': ('post', 'mobile', 'created_by')
        }),
    )
@admin.register(UserLoginLog)
class UserLoginLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'login_time', 'logout_time', 'ip_address']
    list_filter = ['login_time', 'logout_time']
    search_fields = ['user__username', 'ip_address']
    readonly_fields = ['login_time', 'logout_time', 'ip_address', 'user_agent', 'session_key']


@admin.register(VoucherNumber)
class VoucherNumberAdmin(admin.ModelAdmin):
    list_display = ['year', 'last_no']
    search_fields = ['year']
