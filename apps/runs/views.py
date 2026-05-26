from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.dags.models import DAG, TaskDependency
from apps.dags.services.graph import topological_sort, detect_cycle
from .models import PipelineRun, TaskRun, TaskLog
from .serializers import PipelineRunSerializer, PipelineRunListSerializer, TaskRunSerializer


class PipelineRunViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PipelineRun.objects.filter(
            dag__created_by=self.request.user
        ).prefetch_related('task_runs', 'task_runs__logs', 'task_runs__task')

    def get_serializer_class(self):
        if self.action == 'list':
            return PipelineRunListSerializer
        return PipelineRunSerializer

    @action(detail=False, methods=['post'], url_path='trigger/(?P<dag_id>[0-9a-f-]+)')
    def trigger(self, request, dag_id=None):
        """Trigger a new pipeline run for the given DAG."""
        dag = DAG.objects.filter(id=dag_id, created_by=request.user).first()
        if not dag:
            return Response({'error': 'DAG not found.'}, status=404)

        tasks = list(dag.tasks.all())
        if not tasks:
            return Response({'error': 'DAG has no tasks to run.'}, status=400)

        dependencies = list(TaskDependency.objects.filter(task__dag=dag))
        if detect_cycle(tasks, dependencies):
            return Response({'error': 'DAG has a cycle. Fix it before triggering.'}, status=400)

        # Create the pipeline run
        run = PipelineRun.objects.create(
            dag=dag,
            triggered_by=request.user,
            status=PipelineRun.Status.RUNNING,
            started_at=timezone.now(),
            run_config=request.data.get('run_config', {})
        )

        # Create TaskRun records for all tasks (all start as PENDING)
        for task in tasks:
            TaskRun.objects.create(pipeline_run=run, task=task, status=TaskRun.Status.PENDING)

        # Get tasks with no dependencies — they run immediately
        ordered = topological_sort(tasks, dependencies)
        dep_task_ids = {dep.task_id for dep in dependencies}
        root_tasks = [t for t in ordered if t.id not in dep_task_ids]

        # Dispatch root tasks to Celery
        from workers.tasks import execute_task_run
        for task in root_tasks:
            task_run = TaskRun.objects.get(pipeline_run=run, task=task)
            execute_task_run.delay(str(task_run.id))

        serializer = PipelineRunSerializer(run, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a running pipeline."""
        run = self.get_object()
        if run.status not in [PipelineRun.Status.PENDING, PipelineRun.Status.RUNNING]:
            return Response({'error': 'Can only cancel PENDING or RUNNING pipelines.'}, status=400)

        run.status = PipelineRun.Status.CANCELLED
        run.finished_at = timezone.now()
        run.save()

        # Mark all pending task runs as cancelled (use SKIPPED status)
        TaskRun.objects.filter(
            pipeline_run=run, status__in=['PENDING', 'RUNNING']
        ).update(status=TaskRun.Status.SKIPPED, finished_at=timezone.now())

        return Response({'message': 'Pipeline cancelled.'})
