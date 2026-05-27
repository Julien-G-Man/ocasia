from django.contrib import admin
from .models import ClashRoom, ClashParticipant


class ClashParticipantInline(admin.TabularInline):
    model = ClashParticipant
    extra = 0
    readonly_fields = ('user', 'display_name', 'score', 'rank', 'is_host', 'joined_at')


@admin.register(ClashRoom)
class ClashRoomAdmin(admin.ModelAdmin):
    list_display = ('room_code', 'subject', 'difficulty', 'num_questions',
                    'time_per_question', 'status', 'host', 'created_at')
    list_filter = ('status', 'difficulty')
    search_fields = ('room_code', 'subject', 'host__username')
    readonly_fields = ('room_code', 'created_at', 'started_at', 'finished_at')
    inlines = [ClashParticipantInline]


@admin.register(ClashParticipant)
class ClashParticipantAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'room', 'score', 'rank', 'is_host', 'joined_at')
    list_filter = ('is_host',)
    search_fields = ('display_name', 'user__username', 'room__room_code')
