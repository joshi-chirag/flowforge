from rest_framework import serializers
from .models import PipelineRun, TaskRun, TaskLog


class TaskLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskLog
        fields = ['id', 'message', 'level', 'timestamp']


class TaskRunSerializer(serializers.ModelSerializer):
    task_name = serializers.CharField(source='task.name', read_only=True)
    task_type = serializers.CharField(source='task.task_type', read_only=True)
    logs = TaskLogSerializer(many=True, read_only=True)
    duration_seconds = serializers.ReadOnlyField()

    class Meta:
        model = TaskRun
        fields = [
            'id', 'task', 'task_name', 'task_type', 'status',
            'attempt_number', 'started_at', 'finished_at',
            'duration_seconds', 'error_message', 'logs'
        ]


class PipelineRunSerializer(serializers.ModelSerializer):
    dag_name = serializers.CharField(source='dag.name', read_only=True)
    triggered_by_username = serializers.CharField(source='triggered_by.username', read_only=True)
    task_runs = TaskRunSerializer(many=True, read_only=True)
    duration_seconds = serializers.ReadOnlyField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = PipelineRun
        fields = [
            'id', 'dag', 'dag_name', 'status', 'triggered_by',
            'triggered_by_username', 'run_config', 'started_at',
            'finished_at', 'duration_seconds', 'progress',
            'task_runs', 'created_at'
        ]

    def get_progress(self, obj):
        total = obj.task_runs.count()
        if total == 0:
            return 0
        done = obj.task_runs.filter(
            status__in=['SUCCESS', 'FAILED', 'SKIPPED']
        ).count()
        return round((done / total) * 100)


class PipelineRunListSerializer(serializers.ModelSerializer):
    dag_name = serializers.CharField(source='dag.name', read_only=True)
    triggered_by_username = serializers.CharField(source='triggered_by.username', read_only=True)
    duration_seconds = serializers.ReadOnlyField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = PipelineRun
        fields = [
            'id', 'dag', 'dag_name', 'status', 'triggered_by_username',
            'duration_seconds', 'progress', 'created_at', 'started_at', 'finished_at'
        ]

    def get_progress(self, obj):
        total = obj.task_runs.count()
        if total == 0:
            return 0
        done = obj.task_runs.filter(status__in=['SUCCESS', 'FAILED', 'SKIPPED']).count()
        return round((done / total) * 100)
