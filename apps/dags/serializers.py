from rest_framework import serializers
from .models import DAG, Task, TaskDependency


class TaskDependencySerializer(serializers.ModelSerializer):
    depends_on_name = serializers.CharField(source='depends_on.name', read_only=True)

    class Meta:
        model = TaskDependency
        fields = ['id', 'depends_on', 'depends_on_name']


class TaskSerializer(serializers.ModelSerializer):
    dependencies = TaskDependencySerializer(many=True, read_only=True)
    dependents_count = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'dag', 'name', 'description', 'task_type',
            'task_config', 'max_retries', 'retry_delay_seconds',
            'timeout_seconds', 'dependencies', 'dependents_count', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_dependents_count(self, obj):
        return obj.dependents.count()


class TaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            'name', 'description', 'task_type', 'task_config',
            'max_retries', 'retry_delay_seconds', 'timeout_seconds'
        ]

    def validate(self, attrs):
        # Retrieve the dag_pk from the view context to check for uniqueness
        view = self.context.get('view')
        if view and 'dag_pk' in view.kwargs:
            dag_pk = view.kwargs['dag_pk']
            name = attrs.get('name')
            if name and Task.objects.filter(dag_id=dag_pk, name=name).exists():
                raise serializers.ValidationError({"name": "A task with this name already exists in this pipeline."})
        return attrs



class DAGSerializer(serializers.ModelSerializer):
    tasks = TaskSerializer(many=True, read_only=True)
    task_count = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = DAG
        fields = [
            'id', 'name', 'description', 'is_active', 'schedule',
            'created_by', 'created_by_username', 'task_count',
            'tasks', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_task_count(self, obj):
        return obj.tasks.count()

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class DAGListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing DAGs (no nested tasks)."""
    task_count = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = DAG
        fields = [
            'id', 'name', 'description', 'is_active',
            'schedule', 'created_by_username', 'task_count',
            'created_at', 'updated_at'
        ]

    def get_task_count(self, obj):
        return obj.tasks.count()


class AddDependencySerializer(serializers.Serializer):
    depends_on_id = serializers.UUIDField()


class AIGenerateDAGSerializer(serializers.Serializer):
    prompt = serializers.CharField(
        max_length=1000,
        help_text='Describe your pipeline in plain English. E.g. "Fetch weather data, clean it, analyze trends, then email a report"'
    )
    dag_name = serializers.CharField(max_length=255)
