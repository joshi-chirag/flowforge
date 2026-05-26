import json
from channels.generic.websocket import AsyncWebsocketConsumer


class RunConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time pipeline run updates.
    Clients connect to: ws://host/ws/runs/{run_id}/
    """

    async def connect(self):
        self.run_id = self.scope['url_route']['kwargs']['run_id']
        self.group_name = f'run_{self.run_id}'

        # Join the run's channel group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            'event': 'connected',
            'data': {'run_id': self.run_id, 'message': 'Connected to FlowForge live updates'}
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # Clients can send ping to keep connection alive
        data = json.loads(text_data)
        if data.get('type') == 'ping':
            await self.send(text_data=json.dumps({'event': 'pong'}))

    async def run_update(self, event):
        """Receive message from channel layer and forward to WebSocket client."""
        await self.send(text_data=json.dumps({
            'event': event['event'],
            'data': event['data'],
        }))
