from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import UserProfile, Message
import json

# Create your views here.

def home(request):
    if request.user.is_authenticated:
        users = User.objects.exclude(id=request.user.id)
        # Ensure profile exists
        UserProfile.objects.get_or_create(user=request.user)
        return render(request, 'home.html', {'users': users})
    else:
        return redirect('/signin')

def signin(request):
    if request.user.is_authenticated:
        return redirect('/')
    else:
        if request.method == 'POST':
            username = request.POST['username']
            password = request.POST['password']
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('/')
            else:
                return render(request, "login.html", {'error': 'Invalid username or password'})
        else:
            return render(request, "login.html")

def signout(request):
    logout(request)
    return redirect('/signin')

def signup(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        confpassword = request.POST.get('confirmpassword')

        if User.objects.filter(username=username).exists():
            return render(request, "signup.html", {'error': 'Username already exists'})

        if password != confpassword:
            return render(request, "signup.html", {'error': 'Passwords do not match'})

        if not password or not username:
            return render(request, "signup.html", {'error': 'Username and password are required'})

        try:
            user = User.objects.create_user(username=username, password=password)
            user.save()
            UserProfile.objects.create(user=user)
            login(request, user)
            return redirect('/')
        except Exception as e:
            return render(request, "signup.html", {'error': 'Error creating account: ' + str(e)})
    else:
        return render(request, "signup.html")

def upload(request):
    if request.user.is_authenticated:
        if request.method == 'POST':
            if 'pic' in request.FILES:
                pic = request.FILES['pic']
                user_profile, created = UserProfile.objects.get_or_create(user=request.user)
                user_profile.profile_pic = pic
                user_profile.save()
                return redirect('/')
            else:
                return redirect('/')
        else:
            return redirect('/')
    else:
        return redirect('/signin')

def send_message(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    if request.method == 'POST':
        data = json.loads(request.body)
        receiver_id = data.get('receiver_id')
        content = data.get('content', '').strip()
        if not content:
            return JsonResponse({'error': 'Empty message'}, status=400)
        try:
            receiver = User.objects.get(id=receiver_id)
            msg = Message.objects.create(
                sender=request.user,
                receiver=receiver,
                content=content
            )
            return JsonResponse({
                'id': msg.id,
                'content': msg.content,
                'timestamp': msg.timestamp.strftime('%H:%M'),
                'sender_id': request.user.id,
            })
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)
    return JsonResponse({'error': 'Invalid method'}, status=405)

def get_messages(request, user_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    try:
        other_user = User.objects.get(id=user_id)
        messages = Message.objects.filter(
            sender=request.user, receiver=other_user
        ) | Message.objects.filter(
            sender=other_user, receiver=request.user
        )
        messages = messages.order_by('timestamp')

        # Mark received messages as read
        Message.objects.filter(sender=other_user, receiver=request.user, is_read=False).update(is_read=True)

        data = []
        for msg in messages:
            try:
                pic_url = msg.sender.userprofile.profile_pic.url if msg.sender.userprofile.profile_pic else ''
            except Exception:
                pic_url = ''
            data.append({
                'id': msg.id,
                'content': msg.content,
                'timestamp': msg.timestamp.strftime('%H:%M'),
                'sender_id': msg.sender.id,
                'sender_username': msg.sender.username,
                'sender_pic': pic_url,
            })
        return JsonResponse({'messages': data})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

def get_unread_counts(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    users = User.objects.exclude(id=request.user.id)
    counts = {}
    for u in users:
        counts[u.id] = Message.objects.filter(sender=u, receiver=request.user, is_read=False).count()
    return JsonResponse({'counts': counts})