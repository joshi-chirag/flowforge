from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PipelineRunViewSet

router = DefaultRouter()
router.register(r'runs', PipelineRunViewSet, basename='run')

urlpatterns = [
    path('', include(router.urls)),
]
