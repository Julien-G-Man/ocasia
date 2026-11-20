from rest_framework import serializers


class TutorHistoryItemSerializer(serializers.Serializer):
    role = serializers.CharField(required=False, allow_blank=True, max_length=32)
    message_type = serializers.CharField(required=False, allow_blank=True, max_length=32)
    content = serializers.CharField(required=False, allow_blank=True, max_length=20_000)
    message = serializers.CharField(required=False, allow_blank=True, max_length=20_000)

    def validate(self, attrs):
        role = attrs.get("message_type", attrs.get("role", ""))
        content = attrs.get("content", attrs.get("message", ""))
        return {**attrs, "role": role, "content": content}


class TutorChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=20_000, allow_blank=False, trim_whitespace=True)
    history = TutorHistoryItemSerializer(many=True, required=False, default=list, max_length=100)
    tutor_mode = serializers.ChoiceField(choices=("direct", "socratic"), default="direct")
    user_stats = serializers.DictField(required=False, allow_null=True)
    file_text = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=50_000)
    session_id = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=100)
    has_document = serializers.BooleanField(required=False)

    def validate(self, attrs):
        attrs.setdefault("has_document", bool(attrs.get("file_text")))
        return attrs


class TutorSessionRenameSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120, allow_blank=False, trim_whitespace=True)


class TutorDocumentUploadSerializer(serializers.Serializer):
    file_upload = serializers.FileField()
    message = serializers.CharField(required=False, allow_blank=True, max_length=20_000)
    session_id = serializers.CharField(required=False, allow_blank=True, max_length=100)
    tutor_mode = serializers.ChoiceField(choices=("direct", "socratic"), default="direct")

    def validate_file_upload(self, uploaded_file):
        from pathlib import Path

        from apps.tutor.rag_indexing import SUPPORTED_EXTENSIONS

        if uploaded_file.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File is too large (maximum 10 MB).")
        extension = Path(uploaded_file.name).suffix.casefold()
        if extension not in SUPPORTED_EXTENSIONS:
            raise serializers.ValidationError(
                "Unsupported file type. Upload PDF, PPTX, Markdown, or TXT."
            )
        return uploaded_file
