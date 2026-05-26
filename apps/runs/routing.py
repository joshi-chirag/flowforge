from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/runs/(?P<run_id>[0-9a-f-]+)/$', consumers.RunConsumer.as_asgi()),
]
