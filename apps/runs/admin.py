from django.contrib import admin
from .models import PipelineRun, TaskRun, TaskLog


@admin.register(PipelineRun)
class PipelineRunAdmin(admin.ModelAdmin):
    list_display = ['dag', 'status', 'triggered_by', 'started_at', 'finished_at']
    list_filter = ['status']
    readonly_fields = ['id', 'created_at']


@admin.register(TaskRun)
class TaskRunAdmin(admin.ModelAdmin):
    list_display = ['task', 'pipeline_run', 'status', 'attempt_number', 'started_at']
    list_filter = ['status']


@admin.register(TaskLog)
class TaskLogAdmin(admin.ModelAdmin):
    list_display = ['task_run', 'level', 'message', 'timestamp']
    list_filter = ['level']
