import random
import string
from django.db import models
from django.conf import settings

MAX_PARTICIPANTS = 20
VALID_TIME_OPTIONS = [10, 15, 20, 30]
DEFAULT_TIME_PER_QUESTION = 20


def _generate_room_code():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=6))


class ClashRoom(models.Model):
    WAITING = 'waiting'
    ACTIVE = 'active'
    FINISHED = 'finished'
    STATUS_CHOICES = [
        (WAITING, 'Waiting'),
        (ACTIVE, 'Active'),
        (FINISHED, 'Finished'),
    ]

    room_code = models.CharField(max_length=6, unique=True, default=_generate_room_code)
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hosted_clashes',
    )
    subject = models.CharField(max_length=200)
    difficulty = models.CharField(max_length=20, default='medium')
    questions = models.JSONField(default=list)       # MCQ list from FastAPI
    num_questions = models.PositiveIntegerField()
    time_per_question = models.PositiveIntegerField(default=DEFAULT_TIME_PER_QUESTION)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=WAITING)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Clash {self.room_code} — {self.subject} ({self.status})"


class ClashParticipant(models.Model):
    room = models.ForeignKey(ClashRoom, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='clash_participations',
    )
    display_name = models.CharField(max_length=50)
    score = models.IntegerField(default=0)
    answers = models.JSONField(default=list)   # [{q_idx, answer, correct, points, ms_taken}]
    is_host = models.BooleanField(default=False)
    rank = models.IntegerField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('room', 'user')
        ordering = ['-score', 'joined_at']

    def __str__(self):
        return f"{self.display_name} in {self.room.room_code}"
