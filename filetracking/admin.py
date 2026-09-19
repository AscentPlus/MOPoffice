from django.contrib import admin
from .models import FileMaster, FileMovement, FileAction, FileDocument


@admin.register(FileMaster)
class FileMasterAdmin(admin.ModelAdmin):
    list_display = ['file_number', 'subject', 'department', 'current_holder', 
                    'document_priority', 'is_closed', 'created_at']
    list_filter = ['is_closed', 'department', 'document_priority', 'current_status']
    search_fields = ['file_number', 'subject']
    readonly_fields = ['file_number', 'created_at', 'closed_at']
    date_hierarchy = 'created_at'


@admin.register(FileMovement)
class FileMovementAdmin(admin.ModelAdmin):
    list_display = ['file', 'from_post', 'to_post', 'action_required', 'moved_at', 'moved_by']
    list_filter = ['action_required', 'to_post']
    search_fields = ['file__file_number', 'file__subject']
    date_hierarchy = 'moved_at'


@admin.register(FileAction)
class FileActionAdmin(admin.ModelAdmin):
    list_display = ['file', 'post', 'action_type', 'action_at', 'action_by']
    list_filter = ['action_type', 'post']
    search_fields = ['file__file_number', 'file__subject', 'remarks']
    date_hierarchy = 'action_at'


@admin.register(FileDocument)
class FileDocumentAdmin(admin.ModelAdmin):
    list_display = ['file', 'description', 'uploaded_by', 'uploaded_at']
    search_fields = ['file__file_number', 'description']
    date_hierarchy = 'uploaded_at'
