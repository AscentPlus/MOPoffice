from django.contrib import admin

from .models import (
    Conversation,
    ConversationParticipantState,
    Message,
    MessageAttachment,
    UserPresence,
)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'participant_a', 'participant_b', 'updated_at', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('participant_a__username', 'participant_b__username')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'created_at', 'is_deleted')
    list_filter = ('is_deleted',)
    search_fields = ('body', 'sender__username')


admin.site.register(ConversationParticipantState)
admin.site.register(MessageAttachment)
admin.site.register(UserPresence)
