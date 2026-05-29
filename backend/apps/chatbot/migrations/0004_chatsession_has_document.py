from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot", "0003_chat_session_title"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatsession",
            name="has_document",
            field=models.BooleanField(default=False),
        ),
    ]
