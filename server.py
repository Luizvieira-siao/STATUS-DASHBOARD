"""Compatibilidade: inicia o servidor de desenvolvimento Django."""
import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from django.core.management import execute_from_command_line
if __name__ == '__main__':
    execute_from_command_line([sys.argv[0], 'runserver', *sys.argv[1:]])
