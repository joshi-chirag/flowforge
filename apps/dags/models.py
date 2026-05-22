import uuid
from django.db import models
from django.contrib.auth.models import User


class DAG(models.Model):
    """Represents a pipeline — a collection of dependent tasks."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dags')
    is_active = models.BooleanField(default=True)
    schedule = models.CharField(
        max_length=100, blank=True, null=True,
        help_text='Cron expression e.g. "0 9 * * *" for daily at 9am'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Task(models.Model):
    """A single node in the DAG — one unit of work."""

    class TaskType(models.TextChoices):
        DUMMY = 'DUMMY', 'Dummy (simulated)'
        PYTHON = 'PYTHON', 'Python Function'
        HTTP = 'HTTP', 'HTTP Request'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dag = models.ForeignKey(DAG, on_delete=models.CASCADE, related_name='tasks')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=20, choices=TaskType.choices, default=TaskType.DUMMY)
    task_config = models.JSONField(
        default=dict, blank=True,
        help_text='Config depends on task_type. DUMMY: {"duration": 3}, PYTHON: {"code": "..."}, HTTP: {"url": "...", "method": "GET"}'
    )
    max_retries = models.PositiveIntegerField(default=1)
    retry_delay_seconds = models.PositiveIntegerField(default=5)
    timeout_seconds = models.PositiveIntegerField(default=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('dag', 'name')
        ordering = ['created_at']

    def __str__(self):
        return f"{self.dag.name} → {self.name}"


class TaskDependency(models.Model):
    """An edge in the DAG — task depends_on must complete before task can start."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='dependencies')
    depends_on = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='dependents')

    class Meta:
        unique_together = ('task', 'depends_on')

    def __str__(self):
        return f"{self.depends_on.name} → {self.task.name}"
