from django.urls import path, include
from rest_framework_nested import routers
from rest_framework.routers import DefaultRouter
from .views import DAGViewSet, TaskViewSet

router = DefaultRouter()
router.register(r'dags', DAGViewSet, basename='dag')

# Nested: /api/dags/{dag_pk}/tasks/
from rest_framework_nested.routers import NestedDefaultRouter
dags_router = NestedDefaultRouter(router, r'dags', lookup='dag')
dags_router.register(r'tasks', TaskViewSet, basename='dag-tasks')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(dags_router.urls)),
]
