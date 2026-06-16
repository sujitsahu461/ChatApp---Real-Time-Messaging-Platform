import json
import time
from collections import defaultdict
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Message, UserProfile, ChatGroup, GroupMessage

# Track online users globally
online_users = set()

# Simple in-memory rate limiter for WebSocket messages
# Format: {user_id: [timestamp1, timestamp2, ...]}
_ws_rate_tracker = defaultdict(list)
WS_RATE_LIMIT = 30      # max messages
WS_RATE_WINDOW = 60     # per 60 seconds

# Valid message types
VALID_MESSAGE_TYPES = {'text', 'voice', 'call'}

# Max message content length
MAX_TEXT_LENGTH = 5_000
MAX_VOICE_LENGTH = 500_000


def format_time(dt):
    """Convert UTC datetime to local timezone and format as HH:MM."""
    local_dt = timezone.localtime(dt)
    return local_dt.strftime('%H:%M')


def format_date(dt):
    """Convert UTC datetime to local timezone and format as date."""
    local_dt = timezone.localtime(dt)
    return local_dt.strftime('%d %b %Y')


def check_ws_rate_limit(user_id):
    """Return True if the user is within rate limits, False if exceeding."""
    now = time.time()
    timestamps = _ws_rate_tracker[user_id]

    # Remove timestamps older than the window
    _ws_rate_tracker[user_id] = [t for t in timestamps if now - t < WS_RATE_WINDOW]

    if len(_ws_rate_tracker[user_id]) >= WS_RATE_LIMIT:
        return False

    _ws_rate_tracker[user_id].append(now)
    return True


class ChatConsumer(AsyncWebsocketConsumer):
    """Handles direct 1-to-1 chat WebSocket connections."""

    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        self.other_user_id = int(self.scope['url_route']['kwargs']['user_id'])

        # Prevent connecting to yourself
        if self.user.id == self.other_user_id:
            await self.close()
            return

        # Create a consistent room name for both users
        ids = sorted([self.user.id, self.other_user_id])
        self.room_name = f'chat_{ids[0]}_{ids[1]}'

        await self.channel_layer.group_add(self.room_name, self.channel_name)
        await self.accept()

        # Send chat history (last 50 messages)
        messages = await self.get_messages()
        await self.send(text_data=json.dumps({
            'type': 'history',
            'messages': messages,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'room_name'):
            await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive(self, text_data):
        # Parse JSON safely
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            return  # Silently ignore malformed JSON

        if not isinstance(data, dict):
            return

        # Handle call signaling
        if data.get('type') == 'call_signal':
            await self.channel_layer.group_send(self.room_name, {
                'type': 'call_signal',
                'sender_id': self.user.id,
                'signal': data.get('signal', {}),
            })
            return

        content = data.get('message', '')
        if not isinstance(content, str):
            return
        content = content.strip()

        message_type = data.get('message_type', 'text')

        # Validate message type
        if message_type not in VALID_MESSAGE_TYPES:
            return

        # Validate message content
        if not content:
            return

        # Validate message length
        max_len = MAX_VOICE_LENGTH if message_type == 'voice' else MAX_TEXT_LENGTH
        if len(content) > max_len:
            return

        # Rate limiting
        if not check_ws_rate_limit(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Too many messages. Please slow down.',
            }))
            return

        # Save message to DB
        msg_data = await self.save_message(content, message_type)

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
                    'message_type': message_type,
                    'timestamp': msg_data['timestamp'],
                },
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
        }))

    async def call_signal(self, event):
        if event['sender_id'] == self.user.id:
            return
        await self.send(text_data=json.dumps({
            'type': 'call_signal',
            'sender_id': event['sender_id'],
            'signal': event['signal'],
        }))

    @database_sync_to_async
    def save_message(self, content, message_type='text'):
        receiver = User.objects.get(id=self.other_user_id)
        msg = Message.objects.create(
            sender=self.user,
            receiver=receiver,
            content=content,
            message_type=message_type,
        )
        try:
            pic_url = self.user.userprofile.profile_pic.url if self.user.userprofile.profile_pic else ''
        except Exception:
            pic_url = ''

        return {
            'id': msg.id,
            'content': msg.content,
            'message_type': msg.message_type,
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
        # Paginate: last 50 messages only
        messages = messages.select_related(
            'sender__userprofile'
        ).order_by('-timestamp')[:50]

        # Mark received messages as read
        Message.objects.filter(
            sender_id=self.other_user_id, receiver_id=self.user.id, is_read=False
        ).update(is_read=True)

        data = []
        for msg in reversed(messages):  # Reverse for chronological order
            try:
                pic_url = msg.sender.userprofile.profile_pic.url if msg.sender.userprofile.profile_pic else ''
            except Exception:
                pic_url = ''
            data.append({
                'id': msg.id,
                'content': msg.content,
                'message_type': msg.message_type,
                'timestamp': format_time(msg.timestamp),
                'date': format_date(msg.timestamp),
                'sender_id': msg.sender.id,
                'sender_username': msg.sender.username,
                'sender_pic': pic_url,
            })
        return data


class GroupChatConsumer(AsyncWebsocketConsumer):
    """Handles group chat WebSocket connections."""

    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        self.group_id = int(self.scope['url_route']['kwargs']['group_id'])
        is_member = await self.is_group_member()
        if not is_member:
            await self.close()
            return

        self.room_name = f'group_{self.group_id}'
        await self.channel_layer.group_add(self.room_name, self.channel_name)
        await self.accept()

        # Send last 50 messages
        messages = await self.get_messages()
        await self.send(text_data=json.dumps({
            'type': 'history',
            'messages': messages,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'room_name'):
            await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive(self, text_data):
        # Parse JSON safely
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            return

        if not isinstance(data, dict):
            return

        content = data.get('message', '')
        if not isinstance(content, str):
            return
        content = content.strip()

        message_type = data.get('message_type', 'text')

        # Validate message type
        if message_type not in VALID_MESSAGE_TYPES:
            return

        if not content:
            return

        # Validate message length
        max_len = MAX_VOICE_LENGTH if message_type == 'voice' else MAX_TEXT_LENGTH
        if len(content) > max_len:
            return

        # Rate limiting
        if not check_ws_rate_limit(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Too many messages. Please slow down.',
            }))
            return

        msg_data = await self.save_message(content, message_type)
        await self.channel_layer.group_send(self.room_name, {
            'type': 'chat_message',
            'message': msg_data,
        })

        member_ids = await self.get_member_ids()
        for member_id in member_ids:
            if member_id == self.user.id:
                continue
            await self.channel_layer.group_send(
                f'notifications_{member_id}',
                {
                    'type': 'notify',
                    'message': {
                        'sender_id': self.user.id,
                        'sender_username': self.user.username,
                        'sender_pic': msg_data['sender_pic'],
                        'group_id': self.group_id,
                        'group_name': msg_data['group_name'],
                        'content': content[:100],
                        'message_type': message_type,
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
    def is_group_member(self):
        return ChatGroup.objects.filter(id=self.group_id, members=self.user).exists()

    @database_sync_to_async
    def get_member_ids(self):
        return list(ChatGroup.objects.get(id=self.group_id).members.values_list('id', flat=True))

    @database_sync_to_async
    def save_message(self, content, message_type='text'):
        group = ChatGroup.objects.get(id=self.group_id, members=self.user)
        msg = GroupMessage.objects.create(
            group=group,
            sender=self.user,
            content=content,
            message_type=message_type,
        )
        try:
            pic_url = self.user.userprofile.profile_pic.url if self.user.userprofile.profile_pic else ''
        except Exception:
            pic_url = ''

        return {
            'id': msg.id,
            'group_id': group.id,
            'group_name': group.name,
            'content': msg.content,
            'message_type': msg.message_type,
            'timestamp': format_time(msg.timestamp),
            'date': format_date(msg.timestamp),
            'sender_id': self.user.id,
            'sender_username': self.user.username,
            'sender_pic': pic_url,
        }

    @database_sync_to_async
    def get_messages(self):
        group = ChatGroup.objects.get(id=self.group_id, members=self.user)
        # Paginate: last 50 messages
        msgs = group.messages.select_related(
            'sender', 'sender__userprofile'
        ).order_by('-timestamp')[:50]

        data = []
        for msg in reversed(msgs):  # Reverse for chronological order
            try:
                pic_url = msg.sender.userprofile.profile_pic.url if msg.sender.userprofile.profile_pic else ''
            except Exception:
                pic_url = ''
            data.append({
                'id': msg.id,
                'group_id': group.id,
                'group_name': group.name,
                'content': msg.content,
                'message_type': msg.message_type,
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
