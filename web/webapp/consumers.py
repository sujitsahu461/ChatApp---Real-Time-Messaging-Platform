import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Message, UserProfile

# Track online users globally
online_users = set()


def format_time(dt):
    """Convert UTC datetime to local timezone and format as HH:MM."""
    local_dt = timezone.localtime(dt)
    return local_dt.strftime('%H:%M')


def format_date(dt):
    """Convert UTC datetime to local timezone and format as date."""
    local_dt = timezone.localtime(dt)
    return local_dt.strftime('%d %b %Y')


class ChatConsumer(AsyncWebsocketConsumer):
    """Handles direct 1-to-1 chat WebSocket connections."""

    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        self.other_user_id = int(self.scope['url_route']['kwargs']['user_id'])

        # Create a consistent room name for both users
        ids = sorted([self.user.id, self.other_user_id])
        self.room_name = f'chat_{ids[0]}_{ids[1]}'

        await self.channel_layer.group_add(self.room_name, self.channel_name)
        await self.accept()

        # Send chat history
        messages = await self.get_messages()
        await self.send(text_data=json.dumps({
            'type': 'history',
            'messages': messages,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'room_name'):
            await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        content = data.get('message', '').strip()
        if not content:
            return

        # Save message to DB
        msg_data = await self.save_message(content)

        # Broadcast to chat room
        await self.channel_layer.group_send(self.room_name, {
            'type': 'chat_message',
            'message': msg_data,
        })

        # Send notification to the receiver
        await self.channel_layer.group_send(
            f'notifications_{self.other_user_id}',
            {
                'type': 'notify',
                'message': {
                    'sender_id': self.user.id,
                    'sender_username': self.user.username,
                    'sender_pic': msg_data['sender_pic'],
                    'content': content[:100],
                    'timestamp': msg_data['timestamp'],
                },
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
        }))

    @database_sync_to_async
    def save_message(self, content):
        receiver = User.objects.get(id=self.other_user_id)
        msg = Message.objects.create(
            sender=self.user,
            receiver=receiver,
            content=content,
        )
        try:
            pic_url = self.user.userprofile.profile_pic.url if self.user.userprofile.profile_pic else ''
        except Exception:
            pic_url = ''

        return {
            'id': msg.id,
            'content': msg.content,
            'timestamp': format_time(msg.timestamp),
            'date': format_date(msg.timestamp),
            'sender_id': self.user.id,
            'sender_username': self.user.username,
            'sender_pic': pic_url,
        }

    @database_sync_to_async
    def get_messages(self):
        messages = Message.objects.filter(
            sender_id=self.user.id, receiver_id=self.other_user_id
        ) | Message.objects.filter(
            sender_id=self.other_user_id, receiver_id=self.user.id
        )
        messages = messages.order_by('timestamp')

        # Mark received messages as read
        Message.objects.filter(
            sender_id=self.other_user_id, receiver_id=self.user.id, is_read=False
        ).update(is_read=True)

        data = []
        for msg in messages:
            try:
                pic_url = msg.sender.userprofile.profile_pic.url if msg.sender.userprofile.profile_pic else ''
            except Exception:
                pic_url = ''
            data.append({
                'id': msg.id,
                'content': msg.content,
                'timestamp': format_time(msg.timestamp),
                'date': format_date(msg.timestamp),
                'sender_id': msg.sender.id,
                'sender_username': msg.sender.username,
                'sender_pic': pic_url,
            })
        return data


class NotificationConsumer(AsyncWebsocketConsumer):
    """Global per-user WebSocket for receiving notifications + online tracking."""

    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        self.notification_group = f'notifications_{self.user.id}'
        await self.channel_layer.group_add(self.notification_group, self.channel_name)

        # Join the global presence group (all users)
        await self.channel_layer.group_add('presence', self.channel_name)

        await self.accept()

        # Mark user as online
        online_users.add(self.user.id)

        # Broadcast online status to everyone
        await self.channel_layer.group_send('presence', {
            'type': 'presence_update',
            'user_id': self.user.id,
            'status': 'online',
        })

        # Send the current online users list to this user
        await self.send(text_data=json.dumps({
            'type': 'online_users',
            'users': list(online_users),
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'notification_group'):
            await self.channel_layer.group_discard(self.notification_group, self.channel_name)

        if hasattr(self, 'user') and self.user.is_authenticated:
            # Mark user as offline
            online_users.discard(self.user.id)

            await self.channel_layer.group_discard('presence', self.channel_name)

            # Broadcast offline status to everyone
            await self.channel_layer.group_send('presence', {
                'type': 'presence_update',
                'user_id': self.user.id,
                'status': 'offline',
            })

    async def notify(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': event['message'],
        }))

    async def presence_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'presence',
            'user_id': event['user_id'],
            'status': event['status'],
        }))
