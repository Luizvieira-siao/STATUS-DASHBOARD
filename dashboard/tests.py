import json
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from .models import AccessEvent, Assistente, Cartorio, Pasta, LoginAttempt

@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class DashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('ana', password='A-long-test-password!')
        self.other = get_user_model().objects.create_user('bia', password='Another-long-password!')
        self.client.force_login(self.user)
    def post(self, path, data):
        return self.client.post(path, data=json.dumps(data), content_type='application/json')
    def test_protected_pages_and_admin(self):
        anonymous = Client()
        self.assertRedirects(anonymous.get('/'), '/login/?next=/', fetch_redirect_response=False)
        self.assertEqual(anonymous.get('/api/session').status_code, 401)
        self.assertEqual(anonymous.get('/api/state/').status_code, 302)
        self.assertEqual(anonymous.get('/login/').status_code, 200)
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/admin/').status_code, 302)
    def test_crud_relations_and_tenant_isolation(self):
        response = self.post('/api/items/assistentes/', {'nome': 'Assistente', 'llm': 'GPT'})
        self.assertEqual(response.status_code, 200)
        aid = response.json()['assistentes'][0]['uid']
        response = self.post('/api/items/pastas/', {'nome': 'Pasta', 'assistentes': [aid]})
        pid = response.json()['pastas'][0]['uid']
        response = self.post('/api/items/cartorios/', {'nome': 'Cartório', 'id': 'C1', 'estado': 'PE', 'pastas': [pid], 'assistentes': [aid]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['cartorios'][0]['pastas'], [pid])
        self.assertEqual(self.post('/api/items/cartorios/', {'nome': 'Outro', 'id': 'c1', 'estado': 'PE'}).status_code, 400)
        self.assertEqual(self.post('/api/items/cartorios/', {'nome': 'Outro', 'id': 'C2', 'estado': 'XX'}).status_code, 400)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get('/api/state/').json()['cartorios'], [])
        self.assertEqual(self.client.delete('/api/items/assistentes/'+aid+'/').status_code, 404)
        self.assertEqual(self.post('/api/items/pastas/', {'nome': 'Intrusa', 'assistentes': [aid]}).status_code, 400)
        self.assertFalse(Pasta.objects.filter(owner=self.other).exists())
        self.client.force_login(self.user)
        self.assertEqual(self.client.delete('/api/items/assistentes/'+aid+'/').status_code, 200)
        self.assertEqual(Pasta.objects.get(pk=pid).assistentes.count(), 0)
    def test_csrf_enforced_login_and_writes(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/login/', {'username': 'ana', 'password': 'A-long-test-password!'}).status_code, 403)
        client.get('/login/')
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post('/login/', {'username': 'ana', 'password': 'A-long-test-password!', 'csrfmiddlewaretoken': token}).status_code, 302)
        self.assertEqual(client.post('/api/items/pastas/', data='{"nome":"Teste"}', content_type='application/json').status_code, 403)
        self.assertEqual(client.get('/logout/').status_code, 405)
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post('/logout/', HTTP_X_CSRFTOKEN=token).status_code, 302)
        self.assertEqual(client.get('/api/session').status_code, 401)
        self.assertTrue(AccessEvent.objects.filter(event='login', user=self.user).exists())
        self.assertTrue(AccessEvent.objects.filter(event='logout', user=self.user).exists())
    def test_rate_limit_applies_to_admin_and_login(self):
        client = Client()
        for _ in range(5):
            self.assertEqual(client.post('/login/', {'username': 'ana', 'password': 'wrong'}).status_code, 200)
        self.assertEqual(client.post('/login/', {'username': 'ana', 'password': 'A-long-test-password!'}).status_code, 429)
        self.assertEqual(client.post('/admin/login/', {'username': 'ana', 'password': 'wrong'}).status_code, 429)
        self.assertEqual(AccessEvent.objects.filter(event='failed').count(), 5)
        self.assertFalse(AccessEvent.objects.filter(username__contains='wrong').exists())
    def test_legacy_import_preserves_relations_and_prevents_duplicates(self):
        payload = {'assistentes': [{'uid': 'a1', 'nome': 'Legado', 'llm': 'GPT'}], 'pastas': [{'uid': 'p1', 'nome': 'Pasta', 'assistentes': ['a1']}], 'cartorios': [{'uid': 'c1', 'nome': 'Cartório', 'id': '001', 'estado': 'PE', 'pastas': ['p1'], 'assistentes': ['a1']}]}
        self.assertEqual(self.post('/api/import/', payload).status_code, 200)
        self.assertEqual(Cartorio.objects.get().pastas.get().assistentes.get().nome, 'Legado')
        self.assertEqual(self.post('/api/import/', payload).status_code, 409)
    def test_invalid_import_rolls_back(self):
        payload = {'assistentes': [{'uid': 'a1', 'nome': 'Teste', 'llm': 'GPT'}], 'pastas': [{'uid': 'p1', 'nome': 'Pasta', 'assistentes': ['missing']}], 'cartorios': []}
        self.assertEqual(self.post('/api/import/', payload).status_code, 400)
        self.assertFalse(Assistente.objects.exists())
    def test_admin_access_log_and_models(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        for url in ['/admin/', '/admin/dashboard/accessevent/', '/admin/dashboard/cartorio/', '/admin/dashboard/cartorio/add/']:
            self.assertEqual(self.client.get(url).status_code, 200)
