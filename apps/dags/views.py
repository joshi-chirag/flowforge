from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import DAG, Task, TaskDependency
from .serializers import (
    DAGSerializer, DAGListSerializer, TaskSerializer,
    TaskCreateSerializer, AddDependencySerializer, AIGenerateDAGSerializer
)
from .services.graph import detect_cycle, topological_sort
from .services.ai_generator import generate_dag_from_prompt


class DAGViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DAG.objects.filter(created_by=self.request.user).prefetch_related(
            'tasks', 'tasks__dependencies', 'tasks__dependencies__depends_on'
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return DAGListSerializer
        return DAGSerializer

    @action(detail=True, methods=['get'])
    def validate(self, request, pk=None):
        """Check if DAG has cycles and return execution order."""
        dag = self.get_object()
        tasks = list(dag.tasks.all())
        dependencies = list(TaskDependency.objects.filter(task__dag=dag))

        if detect_cycle(tasks, dependencies):
            return Response(
                {'valid': False, 'error': 'Cycle detected in DAG!'},
                status=status.HTTP_400_BAD_REQUEST
            )

        ordered = topological_sort(tasks, dependencies)
        return Response({
            'valid': True,
            'execution_order': [{'id': str(t.id), 'name': t.name} for t in ordered]
        })

    @action(detail=False, methods=['post'])
    def ai_generate(self, request):
        """Generate a DAG from a plain English description using AI."""
        serializer = AIGenerateDAGSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        prompt = serializer.validated_data['prompt']
        dag_name = serializer.validated_data['dag_name']

        try:
            ai_result = generate_dag_from_prompt(prompt)
        except Exception as e:
            return Response(
                {'error': f'AI generation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Create the DAG
        dag = DAG.objects.create(
            name=dag_name,
            description=f'AI Generated: {prompt}',
            created_by=request.user
        )

        # Create tasks
        task_name_map = {}
        for task_data in ai_result.get('tasks', []):
            task = Task.objects.create(
                dag=dag,
                name=task_data['name'],
                description=task_data.get('description', ''),
                task_type=task_data.get('task_type', 'DUMMY'),
                task_config=task_data.get('task_config', {'duration': 3}),
            )
            task_name_map[task_data['name']] = task

        # Create dependencies
        for dep_data in ai_result.get('dependencies', []):
            task = task_name_map.get(dep_data['task'])
            depends_on = task_name_map.get(dep_data['depends_on'])
            if task and depends_on:
                TaskDependency.objects.create(task=task, depends_on=depends_on)

        serializer = DAGSerializer(dag, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TaskViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        dag_id = self.kwargs.get('dag_pk')
        if dag_id:
            return Task.objects.filter(dag_id=dag_id, dag__created_by=self.request.user)
        return Task.objects.filter(dag__created_by=self.request.user)

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TaskCreateSerializer
        return TaskSerializer

    def perform_create(self, serializer):
        dag = get_object_or_404(DAG, pk=self.kwargs['dag_pk'], created_by=self.request.user)
        serializer.save(dag=dag)

    @action(detail=True, methods=['post'])
    def add_dependency(self, request, dag_pk=None, pk=None):
        """Add a dependency: this task depends on another task."""
        task = self.get_object()
        serializer = AddDependencySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        depends_on_id = serializer.validated_data['depends_on_id']
        depends_on = get_object_or_404(Task, id=depends_on_id, dag=task.dag)

        if task.id == depends_on.id:
            return Response({'error': 'A task cannot depend on itself.'}, status=400)

        dep, created = TaskDependency.objects.get_or_create(task=task, depends_on=depends_on)

        # Check for cycles after adding
        tasks = list(task.dag.tasks.all())
        dependencies = list(TaskDependency.objects.filter(task__dag=task.dag))
        if detect_cycle(tasks, dependencies):
            dep.delete()
            return Response({'error': 'Adding this dependency would create a cycle!'}, status=400)

        return Response({'message': f'{task.name} now depends on {depends_on.name}'})

    @action(detail=True, methods=['delete'])
    def remove_dependency(self, request, dag_pk=None, pk=None):
        """Remove a dependency from this task."""
        task = self.get_object()
        depends_on_id = request.data.get('depends_on_id')
        TaskDependency.objects.filter(task=task, depends_on_id=depends_on_id).delete()
        return Response({'message': 'Dependency removed.'})
