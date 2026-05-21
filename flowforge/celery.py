import os
import django
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flowforge.settings')

app = Celery('flowforge')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Explicitly register tasks outside installed Django apps
import workers.tasks

