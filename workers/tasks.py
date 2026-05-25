import json
import time
import requests
from celery import shared_task
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def push_ws_update(run_id, event_type, data):
    """Push a real-time update to the WebSocket group for this run."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'run_{run_id}',
        {
            'type': 'run_update',
            'event': event_type,
            'data': data,
        }
    )


@shared_task(bind=True, max_retries=0)
def execute_task_run(self, task_run_id):
    """
    Main Celery task that executes a single TaskRun.
    Handles DUMMY, PYTHON, and HTTP task types.
    Sends real-time WebSocket updates.
    """
    from apps.runs.models import TaskRun, TaskLog, PipelineRun

    task_run = TaskRun.objects.select_related('task', 'pipeline_run').get(id=task_run_id)
    task = task_run.task
    pipeline_run = task_run.pipeline_run
    run_id = str(pipeline_run.id)

    def log(message, level='INFO'):
        TaskLog.objects.create(task_run=task_run, message=message, level=level)
        push_ws_update(run_id, 'task_log', {
            'task_run_id': str(task_run.id),
            'task_id': str(task.id),
            'task_name': task.name,
            'message': message,
            'level': level,
        })

    # Mark as RUNNING
    task_run.status = TaskRun.Status.RUNNING
    task_run.started_at = timezone.now()
    task_run.celery_task_id = self.request.id
    task_run.save()

    push_ws_update(run_id, 'task_status', {
        'task_id': str(task.id),
        'task_run_id': str(task_run.id),
        'task_name': task.name,
        'status': 'RUNNING',
        'attempt_number': task_run.attempt_number,
    })

    log(f'Starting task: {task.name} (type: {task.task_type}, attempt: {task_run.attempt_number})')

    try:
        config = task.task_config or {}

        if task.task_type == 'DUMMY':
            # Simulate work with a sleep
            duration = config.get('duration', 3)
            log(f'Simulating work for {duration} seconds...')
            time.sleep(duration)
            log('Task completed successfully.', 'SUCCESS')

        elif task.task_type == 'PYTHON':
            # Execute Python code safely
            code = config.get('code', 'print("Hello from FlowForge!")')
            log(f'Executing Python code...')
            exec_globals = {}
            exec(code, exec_globals)
            output = exec_globals.get('output', 'Code executed successfully.')
            log(str(output), 'SUCCESS')

        elif task.task_type == 'HTTP':
            url = config.get('url')
            method = config.get('method', 'GET').upper()
            headers = config.get('headers', {})
            body = config.get('body', {})

            if not url:
                raise ValueError('HTTP task requires a "url" in task_config')

            log(f'Making {method} request to {url}...')
            response = requests.request(method, url, headers=headers, json=body, timeout=30)
            log(f'Response: {response.status_code} {response.reason}', 'SUCCESS')

        # SUCCESS
        task_run.status = TaskRun.Status.SUCCESS
        task_run.finished_at = timezone.now()
        task_run.save()

        push_ws_update(run_id, 'task_status', {
            'task_id': str(task.id),
            'task_run_id': str(task_run.id),
            'task_name': task.name,
            'status': 'SUCCESS',
            'duration': task_run.duration_seconds,
            'attempt_number': task_run.attempt_number,
        })

        # Trigger next tasks
        _trigger_next_tasks(pipeline_run, task)

    except Exception as e:
        error_msg = str(e)
        log(f'Error: {error_msg}', 'ERROR')

        # Check if we should retry
        if task_run.attempt_number < task.max_retries:
            task_run.status = TaskRun.Status.PENDING
            task_run.finished_at = timezone.now()
            task_run.save()

            log(f'Retrying in {task.retry_delay_seconds}s (attempt {task_run.attempt_number + 1}/{task.max_retries})', 'WARNING')

            push_ws_update(run_id, 'task_status', {
                'task_id': str(task.id),
                'task_run_id': str(task_run.id),
                'task_name': task.name,
                'status': 'RETRYING',
                'attempt_number': task_run.attempt_number + 1,
            })

            # Schedule retry
            new_task_run = TaskRun.objects.create(
                pipeline_run=pipeline_run,
                task=task,
                status=TaskRun.Status.PENDING,
                attempt_number=task_run.attempt_number + 1,
            )
            execute_task_run.apply_async(
                args=[str(new_task_run.id)],
                countdown=task.retry_delay_seconds
            )
        else:
            task_run.status = TaskRun.Status.FAILED
            task_run.error_message = error_msg
            task_run.finished_at = timezone.now()
            task_run.save()

            push_ws_update(run_id, 'task_status', {
                'task_id': str(task.id),
                'task_run_id': str(task_run.id),
                'task_name': task.name,
                'status': 'FAILED',
                'error': error_msg,
                'attempt_number': task_run.attempt_number,
            })

            # Mark downstream tasks as SKIPPED
            _skip_downstream_tasks(pipeline_run, task)

            # Check if whole pipeline failed
            _check_pipeline_completion(pipeline_run)


def _trigger_next_tasks(pipeline_run, completed_task):
    """
    After a task succeeds, check if any downstream tasks are now unblocked.
    A task is unblocked when ALL its dependencies have succeeded.
    """
    from apps.runs.models import TaskRun
    from apps.dags.models import TaskDependency

    run_id = str(pipeline_run.id)

    # Find tasks that depend on the completed task
    downstream_deps = TaskDependency.objects.filter(
        depends_on=completed_task,
        task__dag=pipeline_run.dag
    ).select_related('task')

    for dep in downstream_deps:
        downstream_task = dep.task

        # Check if ALL dependencies of this downstream task have succeeded
        all_deps = TaskDependency.objects.filter(task=downstream_task)
        all_succeeded = all(
            TaskRun.objects.filter(
                pipeline_run=pipeline_run,
                task=d.depends_on,
                status=TaskRun.Status.SUCCESS
            ).exists()
            for d in all_deps
        )

        if all_succeeded:
            # Get the pending task run and dispatch it
            pending_run = TaskRun.objects.filter(
                pipeline_run=pipeline_run,
                task=downstream_task,
                status=TaskRun.Status.PENDING
            ).first()

            if pending_run:
                execute_task_run.delay(str(pending_run.id))

    _check_pipeline_completion(pipeline_run)


def _skip_downstream_tasks(pipeline_run, failed_task):
    """Mark all tasks downstream of a failed task as SKIPPED."""
    from apps.runs.models import TaskRun
    from apps.dags.models import TaskDependency

    run_id = str(pipeline_run.id)
    to_skip = []
    queue = [failed_task]

    while queue:
        task = queue.pop(0)
        deps = TaskDependency.objects.filter(depends_on=task, task__dag=pipeline_run.dag)
        for dep in deps:
            to_skip.append(dep.task)
            queue.append(dep.task)

    for task in to_skip:
        TaskRun.objects.filter(
            pipeline_run=pipeline_run,
            task=task,
            status=TaskRun.Status.PENDING
        ).update(status=TaskRun.Status.SKIPPED, finished_at=timezone.now())

        push_ws_update(run_id, 'task_status', {
            'task_id': str(task.id),
            'task_name': task.name,
            'status': 'SKIPPED',
            'attempt_number': 1,
        })


def _check_pipeline_completion(pipeline_run):
    """Check if the entire pipeline is done (all tasks finished)."""
    from apps.runs.models import TaskRun

    run_id = str(pipeline_run.id)
    all_runs = TaskRun.objects.filter(pipeline_run=pipeline_run)
    terminal_statuses = {TaskRun.Status.SUCCESS, TaskRun.Status.FAILED, TaskRun.Status.SKIPPED}

    all_done = all(r.status in terminal_statuses for r in all_runs)
    if not all_done:
        return

    has_failure = any(r.status == TaskRun.Status.FAILED for r in all_runs)
    final_status = 'FAILED' if has_failure else 'SUCCESS'

    pipeline_run.status = final_status
    pipeline_run.finished_at = timezone.now()
    pipeline_run.save()

    push_ws_update(run_id, 'pipeline_status', {
        'run_id': run_id,
        'status': final_status,
        'duration': pipeline_run.duration_seconds,
    })
