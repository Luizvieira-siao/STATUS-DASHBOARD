from datetime import timedelta
from django.http import HttpResponse
from django.utils import timezone
from .models import LoginAttempt
from .signals import record

class LoginThrottleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        if request.method == 'POST' and request.path in ['/login/', '/admin/login/']:
            cutoff = timezone.now() - timedelta(minutes=5)
            LoginAttempt.objects.filter(created_at__lt=cutoff).delete()
            if LoginAttempt.objects.filter(ip=request.META.get('REMOTE_ADDR', '127.0.0.1'), created_at__gte=cutoff).count() >= 5:
                record(request, 'blocked')
                return HttpResponse('Muitas tentativas. Aguarde 5 minutos para tentar novamente.', status=429, headers={'Retry-After': '300'})
        response = self.get_response(request)
        if not request.path.startswith('/static/'):
            response['Cache-Control'] = 'no-store'
        response['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response
