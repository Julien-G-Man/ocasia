"""
One-time backfill command.

Reads all existing QuizSession rows and builds TopicPerformance +
QuizTopicSchedule from them so historical data is reflected in weak
area detection and spaced scheduling.

Safe to re-run: existing rows are updated with the full aggregate, so
running this twice does not double-count anything.

Usage:
    python manage.py backfill_topic_performance
    python manage.py backfill_topic_performance --dry-run
"""
from django.core.management.base import BaseCommand
from django.db.models import Sum, Max


class Command(BaseCommand):
    help = "Backfill TopicPerformance and QuizTopicSchedule from all QuizSession history"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be written without touching the DB",
        )

    def handle(self, *args, **options):
        from apps.quiz.models import QuizSession, TopicPerformance, QuizTopicSchedule
        from apps.quiz.utils.scoring import score_to_sm2_quality
        from apps.flashcards.scheduling import update_sm2

        dry = options["dry_run"]
        if dry:
            self.stdout.write(self.style.WARNING("Dry run — no DB writes"))

        # Aggregate totals per (user, subject) across all sessions in one query
        groups = (
            QuizSession.objects
            .exclude(subject="")
            .values("user_id", "subject")
            .annotate(
                total_q=Sum("total_questions"),
                total_correct=Sum("correct_answers"),
                latest_score=Max("score_percentage"),
            )
        )

        tp_created = tp_updated = sched_created = 0

        for row in groups:
            user_id = row["user_id"]
            topic = row["subject"]
            total_q = row["total_q"] or 0
            total_correct = row["total_correct"] or 0
            latest_score = float(row["latest_score"] or 0)

            if not topic or total_q == 0:
                continue

            accuracy = round(total_correct / total_q * 100, 2)

            if dry:
                self.stdout.write(
                    f"  user={user_id} topic={topic!r:30s} "
                    f"{total_correct}/{total_q} = {accuracy}%"
                )
                continue

            # TopicPerformance: always overwrite with full aggregate so re-runs are idempotent
            _, created = TopicPerformance.objects.update_or_create(
                user_id=user_id,
                topic=topic,
                defaults={
                    "subject": topic,
                    "total_questions": total_q,
                    "correct_answers": total_correct,
                    "accuracy": accuracy,
                },
            )
            if created:
                tp_created += 1
            else:
                tp_updated += 1

            # QuizTopicSchedule: only initialise if the row doesn't exist yet.
            # Don't overwrite SM-2 state that was already tracked live.
            schedule, sched_was_created = QuizTopicSchedule.objects.get_or_create(
                user_id=user_id,
                topic=topic,
                defaults={"subject": topic},
            )
            if sched_was_created:
                update_sm2(schedule, score_to_sm2_quality(latest_score))
                sched_created += 1

        if not dry:
            self.stdout.write(
                self.style.SUCCESS(
                    f"TopicPerformance: {tp_created} created, {tp_updated} updated\n"
                    f"QuizTopicSchedule: {sched_created} initialised"
                )
            )
