from rest_framework.generics import RetrieveAPIView, ListAPIView
from rest_framework.schemas import ManualSchema
from django.http import JsonResponse
from django.views import View
from django.core.serializers import serialize
from .models import Canvas
from ..manifests.models import Manifest
from .serializers import CanvasSerializer
import json
import uuid

class IIIFV2List(View):
    def get_queryset(self):
        return Canvas.objects.filter(manifest=Manifest.objects.get(pid=self.kwargs['manifest']))

    def get(self, request, *args, **kwargs):
        return JsonResponse(json.loads(serialize('canvas', self.get_queryset(), islist=True)), safe=False)

class IIIFV2Detail(View):
    
    def get_queryset(self):
        return Canvas.objects.filter(pid=self.kwargs['pid'])
    
    def get(self, request, *args, **kwargs):
        return JsonResponse(json.loads(serialize('canvas', self.get_queryset())))