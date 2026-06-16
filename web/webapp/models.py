from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import random
import string


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class Message(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('voice', 'Voice note'),
        ('call', 'Call event'),
    ]

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender.username} → {self.receiver.username}: {self.content[:30]}"


class ChatGroup(models.Model):
    name = models.CharField(max_length=80)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_chat_groups')
    members = models.ManyToManyField(User, related_name='chat_groups')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class GroupMessage(models.Model):
    MESSAGE_TYPES = Message.MESSAGE_TYPES

    group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_messages')
    content = models.TextField()
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.group.name} | {self.sender.username}: {self.content[:30]}"


class OTPCode(models.Model):
    OTP_EXPIRY_MINUTES = 5

    phone_number = models.CharField(max_length=15)
    code = models.CharField(max_length=6)
    username = models.CharField(max_length=150)
    password = models.CharField(max_length=150)  # Stores HASHED password
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"OTP {self.code} for {self.phone_number}"

    def is_expired(self):
        """Check if OTP has expired (default: 5 minutes)."""
        return timezone.now() > self.created_at + timedelta(minutes=self.OTP_EXPIRY_MINUTES)

    @staticmethod
    def generate_code():
        return ''.join(random.choices(string.digits, k=6))

    @classmethod
    def cleanup_stale(cls):
        """Delete all unused OTPs older than 30 minutes."""
        cutoff = timezone.now() - timedelta(minutes=30)
        cls.objects.filter(created_at__lt=cutoff, is_used=False).delete()
