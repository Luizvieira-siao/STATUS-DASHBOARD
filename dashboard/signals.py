from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import AccessEvent, LoginAttempt

def record(request, event, user=None, username=''):
    AccessEvent.objects.create(user=user, username=(user.get_username() if user else username)[:150], event=event,
        ip=request.META.get('REMOTE_ADDR') or None, user_agent=request.META.get('HTTP_USER_AGENT', '')[:300])

@receiver(user_logged_in)
def logged_in(sender, request, user, **kwargs):
    record(request, 'login', user)

@receiver(user_logged_out)
def logged_out(sender, request, user, **kwargs):
    record(request, 'logout', user)

@receiver(user_login_failed)
def failed(sender, credentials, request, **kwargs):
    if request:
        record(request, 'failed', username=str(credentials.get('username', '')))
        LoginAttempt.objects.create(ip=request.META.get('REMOTE_ADDR', '127.0.0.1'))
