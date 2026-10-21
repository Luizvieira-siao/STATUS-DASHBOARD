import uuid
from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

class Owned(models.Model):
    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Responsável')
    nome = models.CharField('Nome', max_length=200)
    class Meta:
        abstract = True
    def __str__(self):
        return self.nome

class Assistente(Owned):
    llm = models.CharField('LLM', max_length=100)

class Pasta(Owned):
    assistentes = models.ManyToManyField(Assistente, blank=True)

class Cartorio(Owned):
    id = models.CharField('Identificador', max_length=100)
    estado = models.CharField(max_length=2, choices=[(x,x) for x in 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split()])
    pastas = models.ManyToManyField(Pasta, blank=True)
    assistentes = models.ManyToManyField(Assistente, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = 'Cartório'
        constraints = [models.UniqueConstraint(Lower('id'), 'owner', name='unique_cartorio_id_owner')]

class AccessEvent(models.Model):
    EVENTS = [('login','Entrada'), ('logout','Saída'), ('failed','Login inválido'), ('blocked','Tentativa bloqueada')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    username = models.CharField('Usuário informado', max_length=150, blank=True)
    event = models.CharField('Evento', max_length=10, choices=EVENTS)
    ip = models.GenericIPAddressField('IP', null=True, blank=True)
    user_agent = models.CharField('Navegador', max_length=300, blank=True)
    created_at = models.DateTimeField('Data', auto_now_add=True)
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Registro de acesso'
        verbose_name_plural = 'Registros de acesso'

class LoginAttempt(models.Model):
    ip = models.GenericIPAddressField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
