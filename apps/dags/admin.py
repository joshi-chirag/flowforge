from django.contrib import admin
from .models import DAG, Task, TaskDependency


@admin.register(DAG)
class DAGAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_by', 'is_active', 'task_count', 'created_at']
    list_filter = ['is_active', 'created_by']
    search_fields = ['name', 'description']

    def task_count(self, obj):
        return obj.tasks.count()


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'dag', 'task_type', 'max_retries', 'created_at']
    list_filter = ['task_type', 'dag']
    search_fields = ['name', 'dag__name']


@admin.register(TaskDependency)
class TaskDependencyAdmin(admin.ModelAdmin):
    list_display = ['task', 'depends_on']
