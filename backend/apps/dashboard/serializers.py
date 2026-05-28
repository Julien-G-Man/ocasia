from rest_framework import serializers

_HTML_PATTERNS = ('<', '>', 'script')


def _no_html(value: str) -> str:
    """Reject inputs containing HTML tags or the word 'script'."""
    lower = value.lower()
    for pat in _HTML_PATTERNS:
        if pat in lower:
            raise serializers.ValidationError("Input contains disallowed HTML content.")
    return value


class ContactFormSerializer(serializers.Serializer):
    title = serializers.CharField(min_length=5, max_length=180)
    name = serializers.CharField(min_length=2, max_length=120)
    email = serializers.EmailField(max_length=254)
    message = serializers.CharField(min_length=10, max_length=5000)

    def validate_title(self, value):
        return _no_html(value)

    def validate_name(self, value):
        return _no_html(value)

    def validate_message(self, value):
        return _no_html(value)


class NewsletterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class QuizFeedbackSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    source = serializers.CharField(max_length=40, required=False, default="quiz_results")
