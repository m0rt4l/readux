from rest_framework import generics
from .models import Annotation
from .serializers import AnnotationSerializer


class AnnotationListCreate(generics.ListCreateAPIView):
    """
    Endpoint that allows annotations to be listed or created.
    """
    queryset = Annotation.objects.all()
    serializer_class = AnnotationSerializer


class AnnotationForPage(generics.ListAPIView):
    """
    Endpoint to to display annotations for a page.
    """
    serializer_class = AnnotationSerializer

    def get_queryset(self):
        return Annotation.objects.filter(volume_identifier=self.kwargs['vol']).filter(page=self.kwargs['page'])


class AnnotationDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Endpoint to update and delete annotation.
    """
    serializer_class = AnnotationSerializer

    def get_queryset(self):
        return Annotation.objects.all()