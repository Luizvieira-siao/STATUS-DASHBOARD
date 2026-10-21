import os
import secrets
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Cria o administrador inicial e salva a senha em arquivo local privado.'
    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write('Já existe um administrador; nenhuma credencial foi alterada.')
            return
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        if User.objects.filter(username=username).exists():
            raise CommandError('Esse usuário já existe. Use createsuperuser com outro nome.')
        path = Path(settings.BASE_DIR) / '.initial-admin.txt'
        password = secrets.token_urlsafe(24)
        with open(path, 'x', opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
            stream.write(f'Usuário: {username}\nSenha: {password}\n\nAltere a senha no admin após entrar e exclua este arquivo.\n')
        try:
            User.objects.create_superuser(username=username, email='', password=password)
        except Exception:
            path.unlink()
            raise
        self.stdout.write(self.style.SUCCESS('Administrador criado. Credenciais em .initial-admin.txt (acesso privado).'))
