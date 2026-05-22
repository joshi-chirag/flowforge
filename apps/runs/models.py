import uuid
from django.db import models
from django.contrib.auth.models import User
from apps.dags.models import DAG, Task


class PipelineRun(models.Model):
    """One execution instance of a DAG."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        RUNNING = 'RUNNING', 'Running'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dag = models.ForeignKey(DAG, on_delete=models.CASCADE, related_name='runs')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    run_config = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.dag.name} | Run {str(self.id)[:8]} | {self.status}"

    @property
    def duration_seconds(self):
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


class TaskRun(models.Model):
    """Execution of a single Task within a PipelineRun."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        RUNNING = 'RUNNING', 'Running'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'
        SKIPPED = 'SKIPPED', 'Skipped'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipeline_run = models.ForeignKey(PipelineRun, on_delete=models.CASCADE, related_name='task_runs')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='task_runs')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    attempt_number = models.PositiveIntegerField(default=1)
    celery_task_id = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['started_at']

    def __str__(self):
        return f"{self.task.name} | {self.status} | attempt {self.attempt_number}"

    @property
    def duration_seconds(self):
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


class TaskLog(models.Model):
    """Individual log lines from a task's execution."""

    class Level(models.TextChoices):
        INFO = 'INFO', 'Info'
        WARNING = 'WARNING', 'Warning'
        ERROR = 'ERROR', 'Error'
        SUCCESS = 'SUCCESS', 'Success'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_run = models.ForeignKey(TaskRun, on_delete=models.CASCADE, related_name='logs')
    message = models.TextField()
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"[{self.level}] {self.message[:50]}"
