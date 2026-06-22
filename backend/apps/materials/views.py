import logging
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .models import Material
from .serializers import MaterialSerializer, MaterialUploadSerializer
from .helpers import _upload_file, _extract_pdf_text, SUBJECT_CHOICES, _cloudinary_candidate_urls

logger = logging.getLogger(__name__)

PAGE_SIZE = 12
MATERIALS_CACHE_TTL = 300  # 5 minutes

SUBJECT_LABEL_MAP = {s['value']: s['label'] for s in SUBJECT_CHOICES}


def _mat_cache_version():
    return cache.get('mat:v') or 0


def _bust_mat_cache():
    cache.set('mat:v', _mat_cache_version() + 1, timeout=None)


class MaterialListView(APIView):
    """GET /api/materials/ — public browse with search, subject filter, pagination."""
    permission_classes     = [AllowAny]
    authentication_classes = []

    def get(self, request):
        q       = request.query_params.get('q', '').strip()
        subject = request.query_params.get('subject', '').strip()
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (TypeError, ValueError):
            page = 1

        cache_key = f'mat:{_mat_cache_version()}:{q}:{subject}:{page}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        qs = Material.objects.filter(is_active=True).select_related('uploaded_by')
        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(uploaded_by__username__icontains=q)
            )
        if subject:
            qs = qs.filter(subject__iexact=subject)

        total     = qs.count()
        materials = qs[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]

        used_subjects = (
            Material.objects
            .exclude(subject='')
            .values_list('subject', flat=True)
            .distinct()
        )
        subjects = [s for s in SUBJECT_CHOICES if s['value'] in used_subjects]

        result = {
            'materials':   MaterialSerializer(materials, many=True).data,
            'count':       total,
            'total_pages': max(1, -(-total // PAGE_SIZE)),
            'subjects':    subjects,
        }
        cache.set(cache_key, result, timeout=MATERIALS_CACHE_TTL)
        return Response(result)


class MaterialUploadView(APIView):
    """POST /api/materials/upload/ — authenticated multipart upload."""
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = MaterialUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data
        file = data['file']

        try:
            file_url = _upload_file(file, request.user.id)
        except Exception:
            logger.exception('File upload failed for user %s', request.user.id)
            return Response({'detail': 'File upload failed. Please try again.'}, status=500)

        material = Material.objects.create(
            uploaded_by    = request.user,
            title       = data['title'],
            description = data.get('description', ''),
            subject     = data.get('subject', 'other'),
            file_url    = file_url,
            original_filename  = file.name,
            file_size   = file.size,
        )

        _bust_mat_cache()
        logger.info('Material "%s" uploaded by %s', material.title, request.user.email)
        return Response(MaterialSerializer(material).data, status=201)


class MaterialDeleteView(APIView):
    """DELETE /api/materials/<id>/delete/ — owner or admin."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, material_id):
        material = get_object_or_404(Material, id=material_id)

        is_owner = material.uploaded_by_id == request.user.id
        is_admin = getattr(request.user, 'is_admin', False)
        if not (is_owner or is_admin):
            return Response({'detail': 'Permission denied.'}, status=403)

        material.delete()
        _bust_mat_cache()
        logger.info('Material %s deleted by %s', material_id, request.user.email)
        return Response(status=204)


class MaterialDownloadView(APIView):
    """POST /api/materials/<id>/download/ — public, bumps counter, returns URL."""
    permission_classes     = [AllowAny]
    authentication_classes = []

    def post(self, request, material_id):
        material = get_object_or_404(Material, id=material_id)
        Material.objects.filter(id=material_id).update(
            download_count=material.download_count + 1
        )
        candidate_urls = _cloudinary_candidate_urls(material.file_url, material.original_filename)

        file_url = material.file_url
        try:
            import httpx
            with httpx.Client(timeout=10, follow_redirects=True) as client:
                for url in candidate_urls:
                    try:
                        probe = client.get(url, headers={'Range': 'bytes=0-1023'})
                        content_type = (probe.headers.get('content-type') or '').lower()
                        body_preview = (probe.text or '')[:200].lower()

                        # Cloudinary may return HTTP 200 with JSON error payload for missing resource.
                        if ('application/json' in content_type) or ('"error"' in body_preview and 'resource not found' in body_preview):
                            continue

                        if probe.status_code in (200, 206):
                            file_url = url
                            break
                    except Exception:
                        continue
        except Exception:
            logger.exception('Failed probing candidate download URLs for material %s', material_id)

        return Response({'file_url': file_url})


class MaterialExtractView(APIView):
    """POST /api/materials/<id>/extract/ — public, fetches PDF and returns text for quiz."""
    permission_classes     = [AllowAny]
    authentication_classes = []

    def post(self, request, material_id):
        material = get_object_or_404(Material, id=material_id)

        if not material.original_filename.lower().endswith('.pdf'):
            return Response(
                {'detail': 'Only PDF files can be extracted for quiz use.'},
                status=400,
            )

        file_bytes = None
        candidate_urls = _cloudinary_candidate_urls(material.file_url, material.original_filename)

        try:
            import httpx
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                for url in candidate_urls:
                    try:
                        resp = client.get(url)
                        content_type = (resp.headers.get('content-type') or '').lower()
                        body_preview = (resp.text or '')[:200].lower()
                        is_cloudinary_json_error = (
                            ('application/json' in content_type)
                            or ('"error"' in body_preview and 'resource not found' in body_preview)
                        )
                        looks_like_pdf = resp.content[:4] == b'%PDF'

                        if resp.status_code == 200 and resp.content and not is_cloudinary_json_error and looks_like_pdf:
                            file_bytes = resp.content
                            break
                    except Exception:
                        continue
        except Exception as e:
            logger.error('Failed to initialize HTTP client for material %s extraction: %s', material_id, e)

        if not file_bytes:
            logger.error('Failed to fetch material %s for extraction from all candidate URLs', material_id)
            return Response(
                {'detail': 'Could not retrieve the file. Please try again.'},
                status=502,
            )

        text = _extract_pdf_text(file_bytes)
        if not text:
            return Response(
                {'detail': 'Could not extract text. The PDF may be image-based or scanned.'},
                status=422,
            )

        return Response({
            'text':    text[:50000],
            'subject': SUBJECT_LABEL_MAP.get(material.subject, material.subject),
            'title':   material.title,
        })

class MaterialDetailView(APIView):
    """GET /api/materials/<id>/ — public"""
    permission_classes     = [AllowAny]
    authentication_classes = []

    def get(self, request, material_id):
        material = get_object_or_404(Material, id=material_id)
        return Response(MaterialSerializer(material).data)
    
class MyMaterialsView(APIView):
    """GET /api/materials/mine/ — authenticated user's own uploads."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        materials = Material.objects.filter(uploaded_by=request.user).order_by('-created_at')
        return Response({'results': MaterialSerializer(materials, many=True).data})