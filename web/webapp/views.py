from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Count, Q
from .models import UserProfile, Message, OTPCode, ChatGroup, GroupMessage
import json

# Try to import ratelimit; graceful fallback if not installed
try:
    from django_ratelimit.decorators import ratelimit
except ImportError:
    # Fallback: no-op decorator if django-ratelimit is not installed
    def ratelimit(**kwargs):
        def decorator(fn):
            return fn
        return decorator


# =============================================================================
# AUTH VIEWS
# =============================================================================

@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def signin(request):
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            return render(request, "login.html", {'error': 'All fields are required'})

        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            return render(request, "login.html", {'error': 'Invalid username or password'})

    return render(request, "login.html")


def signout(request):
    logout(request)
    return redirect('/signin')


@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def signup(request):
    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confpassword = request.POST.get('confirmpassword', '')

        if not password or not username or not phone:
            return render(request, "signup.html", {'error': 'All fields are required'})

        if len(username) < 3:
            return render(request, "signup.html", {'error': 'Username must be at least 3 characters'})

        if len(password) < 6:
            return render(request, "signup.html", {'error': 'Password must be at least 6 characters'})

        if User.objects.filter(username=username).exists():
            return render(request, "signup.html", {'error': 'Username already exists'})

        if password != confpassword:
            return render(request, "signup.html", {'error': 'Passwords do not match'})

        if len(phone) < 10 or not phone.isdigit():
            return render(request, "signup.html", {'error': 'Enter a valid 10-digit phone number'})

        # Clean up stale OTPs
        OTPCode.cleanup_stale()

        # Generate OTP and store with HASHED password
        code = OTPCode.generate_code()
        OTPCode.objects.create(
            phone_number=phone,
            code=code,
            username=username,
            password=make_password(password),  # HASHED — never store plain text
        )

        # Print OTP to terminal for testing (replace with SMS API in production)
        print(f"\n{'='*50}")
        print(f"  OTP for {phone}: {code}")
        print(f"{'='*50}\n")

        # Store in session for OTP verification page
        request.session['otp_phone'] = phone
        request.session['otp_username'] = username
        from django.conf import settings
        if getattr(settings, 'SHOW_OTP_ON_PAGE', False):
            request.session['otp_debug_code'] = code

        return redirect('/verify_otp/')

    return render(request, "signup.html")


@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def verify_otp(request):
    phone = request.session.get('otp_phone')
    username = request.session.get('otp_username')
    from django.conf import settings
    debug_otp = request.session.get('otp_debug_code') if getattr(settings, 'SHOW_OTP_ON_PAGE', False) else None

    if not phone or not username:
        return redirect('/signup/')

    def render_verify(error_msg=None):
        ctx = {'phone': phone}
        if error_msg:
            ctx['error'] = error_msg
        if debug_otp:
            ctx['debug_otp'] = debug_otp
        return render(request, 'verify_otp.html', ctx)

    if request.method == 'POST':
        entered_code = request.POST.get('otp', '').strip()

        if not entered_code or len(entered_code) != 6:
            return render_verify('Please enter a valid 6-digit OTP.')

        # Find the latest unused OTP for this phone + username
        otp_obj = OTPCode.objects.filter(
            phone_number=phone,
            username=username,
            is_used=False,
        ).order_by('-created_at').first()

        if not otp_obj:
            return render_verify('OTP expired or not found. Please sign up again.')

        # Check expiry
        if otp_obj.is_expired():
            otp_obj.delete()
            return render_verify('OTP expired (valid for 5 minutes). Please sign up again.')

        if otp_obj.code != entered_code:
            return render_verify('Invalid OTP. Please try again.')

        # OTP is correct — create the user
        otp_obj.is_used = True
        otp_obj.save()

        try:
            # Password is already hashed — set it directly
            user = User(username=otp_obj.username)
            user.password = otp_obj.password  # Already hashed via make_password()
            user.save()

            UserProfile.objects.create(user=user, phone_number=phone)
            login(request, user)

            # Clean session
            request.session.pop('otp_phone', None)
            request.session.pop('otp_username', None)
            request.session.pop('otp_debug_code', None)

            return redirect('/')
        except Exception as e:
            return render_verify(f'Error creating account: {str(e)}')

    return render_verify()


# =============================================================================
# PROFILE & UPLOAD VIEWS
# =============================================================================

ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB


@login_required
@require_POST
def upload(request):
    if 'pic' not in request.FILES:
        return redirect('/')

    pic = request.FILES['pic']

    # Validate file size
    if pic.size > MAX_UPLOAD_SIZE:
        return redirect('/')

    # Validate file type
    if pic.content_type not in ALLOWED_IMAGE_TYPES:
        return redirect('/')

    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    user_profile.profile_pic = pic
    user_profile.save()
    return redirect('/')


@login_required
@require_POST
def update_phone(request):
    phone = request.POST.get('phone', '').strip()
    if phone and len(phone) >= 10 and phone.isdigit():
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.phone_number = phone
        profile.save()
    return redirect('/')


@login_required
@require_GET
def get_profile(request):
    try:
        profile = request.user.userprofile
        pic_url = profile.profile_pic.url if profile.profile_pic else ''
        return JsonResponse({
            'username': request.user.username,
            'phone': profile.phone_number or '',
            'pic': pic_url,
        })
    except UserProfile.DoesNotExist:
        return JsonResponse({
            'username': request.user.username,
            'phone': '',
            'pic': '',
        })


# =============================================================================
# HOME VIEW
# =============================================================================

@login_required
def home(request):
    # select_related prevents N+1 queries on user profiles
    users = User.objects.exclude(id=request.user.id).select_related('userprofile')
    groups = request.user.chat_groups.prefetch_related('members').all()
    UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'home.html', {'users': users, 'groups': groups})


# =============================================================================
# GROUP VIEWS
# =============================================================================

@login_required
@require_POST
def create_group(request):
    name = request.POST.get('name', '').strip()
    member_ids = request.POST.getlist('members')

    if not name:
        return redirect('/')

    # Sanitize name length
    name = name[:80]

    group = ChatGroup.objects.create(name=name, created_by=request.user)
    group.members.add(request.user)
    users = User.objects.filter(id__in=member_ids).exclude(id=request.user.id)
    group.members.add(*users)
    return redirect('/')


# =============================================================================
# MESSAGE API VIEWS
# =============================================================================

@login_required
@require_POST
def send_message(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    receiver_id = data.get('receiver_id')
    content = data.get('content', '').strip()
    message_type = data.get('message_type', 'text')

    if not content:
        return JsonResponse({'error': 'Empty message'}, status=400)

    # Validate message type
    if message_type not in ('text', 'voice', 'call'):
        return JsonResponse({'error': 'Invalid message type'}, status=400)

    # Validate message length
    max_len = 500_000 if message_type == 'voice' else 5_000
    if len(content) > max_len:
        return JsonResponse({'error': 'Message too long'}, status=400)

    try:
        receiver = User.objects.get(id=receiver_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

    msg = Message.objects.create(
        sender=request.user,
        receiver=receiver,
        content=content,
        message_type=message_type,
    )
    return JsonResponse({
        'id': msg.id,
        'content': msg.content,
        'message_type': msg.message_type,
        'timestamp': msg.timestamp.strftime('%H:%M'),
        'sender_id': request.user.id,
    })


@login_required
@require_GET
def get_messages(request, user_id):
    try:
        other_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

    # Use select_related to prevent N+1 queries
    messages = Message.objects.filter(
        Q(sender=request.user, receiver=other_user) |
        Q(sender=other_user, receiver=request.user)
    ).select_related(
        'sender__userprofile'
    ).order_by('-timestamp')[:50]  # Last 50 messages

    # Mark received messages as read
    Message.objects.filter(
        sender=other_user, receiver=request.user, is_read=False
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
            'timestamp': msg.timestamp.strftime('%H:%M'),
            'sender_id': msg.sender.id,
            'sender_username': msg.sender.username,
            'sender_pic': pic_url,
        })
    return JsonResponse({'messages': data})


@login_required
@require_GET
def get_unread_counts(request):
    # Single query with annotation instead of N separate COUNT queries
    users = User.objects.exclude(id=request.user.id).annotate(
        unread=Count(
            'sent_messages',
            filter=Q(sent_messages__receiver=request.user, sent_messages__is_read=False)
        )
    )
    counts = {u.id: u.unread for u in users}
    return JsonResponse({'counts': counts})


@login_required
@require_GET
def get_group_messages(request, group_id):
    try:
        group = ChatGroup.objects.get(id=group_id, members=request.user)
    except ChatGroup.DoesNotExist:
        return JsonResponse({'error': 'Group not found'}, status=404)

    # Use select_related + limit to last 50 messages
    msgs = GroupMessage.objects.filter(
        group=group
    ).select_related(
        'sender__userprofile'
    ).order_by('-timestamp')[:50]

    data = []
    for msg in reversed(msgs):  # Reverse for chronological order
        try:
            pic_url = msg.sender.userprofile.profile_pic.url if msg.sender.userprofile.profile_pic else ''
        except Exception:
            pic_url = ''
        data.append({
            'id': msg.id,
            'content': msg.content,
            'message_type': msg.message_type,
            'timestamp': msg.timestamp.strftime('%H:%M'),
            'sender_id': msg.sender.id,
            'sender_username': msg.sender.username,
            'sender_pic': pic_url,
        })
    return JsonResponse({'messages': data})
