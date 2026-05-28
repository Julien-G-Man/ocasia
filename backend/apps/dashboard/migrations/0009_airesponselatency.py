from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0008_anonymoususageevent_tutor_response'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIResponseLatency',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('feature', models.CharField(
                    choices=[('chat', 'Chat'), ('quiz', 'Quiz'), ('flashcards', 'Flashcards')],
                    db_index=True,
                    max_length=20,
                )),
                ('duration_ms', models.PositiveIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['feature', 'created_at'], name='dashboard_a_feature_created_idx'),
                ],
            },
        ),
    ]
