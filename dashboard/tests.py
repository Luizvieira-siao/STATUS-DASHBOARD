import json
from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
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
    def test_crud_relations_are_shared_between_users(self):
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
        self.assertEqual(len(self.client.get('/api/state/').json()['cartorios']), 1)
        self.assertEqual(self.post('/api/items/assistentes/', {'nome': 'Compartilhado', 'llm': 'GPT'}).status_code, 200)
        self.assertEqual(self.post('/api/items/pastas/', {'nome': 'Compartilhada', 'assistentes': [aid]}).status_code, 200)
        self.assertTrue(Pasta.objects.filter(owner=self.other).exists())
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
        self.client.force_login(self.other)
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

    def test_edit_assistant_preserves_relations_and_refreshes_state(self):
        assistant = Assistente.objects.create(owner=self.user, nome='Original', llm='GPT')
        folder = Pasta.objects.create(owner=self.user, nome='Pasta')
        registry = Cartorio.objects.create(owner=self.user, nome='Cartório', id='EDIT', estado='PE')
        folder.assistentes.add(assistant)
        registry.assistentes.add(assistant)
        response = self.client.patch(f'/api/items/assistentes/{assistant.pk}/',
            data=json.dumps({'nome': 'Atualizado', 'llm': 'Claude Opus 4.6'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        assistant.refresh_from_db()
        self.assertEqual((assistant.nome, assistant.llm), ('Atualizado', 'Claude Opus 4.6'))
        self.assertTrue(folder.assistentes.filter(pk=assistant.pk).exists())
        self.assertTrue(registry.assistentes.filter(pk=assistant.pk).exists())
        self.assertEqual(response.json()['assistentes'][0]['llm'], 'Claude Opus 4.6')
        page = self.client.get('/')
        self.assertContains(page, 'Claude Opus 4.6')
        self.assertContains(page, 'lista-assistentes')

    def test_edit_assistant_is_shared_and_enforces_validation_and_csrf(self):
        assistant = Assistente.objects.create(owner=self.user, nome='Original', llm='GPT')
        path = f'/api/items/assistentes/{assistant.pk}/'
        for payload in [{'nome': ' ', 'llm': 'GPT'}, {'nome': 'Alterado', 'llm': 'x' * 101}]:
            response = self.client.patch(path, data=json.dumps(payload), content_type='application/json')
            self.assertEqual(response.status_code, 400)
            assistant.refresh_from_db()
            self.assertEqual(assistant.nome, 'Original')
        self.client.force_login(self.other)
        self.assertEqual(self.client.patch(path, data='{"nome":"Intruso","llm":"GPT"}', content_type='application/json').status_code, 200)
        secure_client = Client(enforce_csrf_checks=True)
        secure_client.force_login(self.user)
        self.assertEqual(secure_client.patch(path, data='{"nome":"Alterado","llm":"GPT"}', content_type='application/json').status_code, 403)
        self.assertEqual(Client().patch(path, data='{}', content_type='application/json').status_code, 302)

    def test_unlink_folder_preserves_records_and_other_registries(self):
        folder = Pasta.objects.create(owner=self.user, nome='Compartilhada')
        assistant = Assistente.objects.create(owner=self.user, nome='Assistente', llm='GPT')
        folder.assistentes.add(assistant)
        first = Cartorio.objects.create(owner=self.user, nome='Primeiro', id='P1', estado='PE')
        second = Cartorio.objects.create(owner=self.other, nome='Segundo', id='P2', estado='PE')
        first.pastas.add(folder)
        second.pastas.add(folder)
        self.client.force_login(self.other)
        path = f'/api/cartorios/{first.pk}/pastas/{folder.pk}/'
        response = self.client.delete(path)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(first.pastas.exists())
        self.assertTrue(second.pastas.filter(pk=folder.pk).exists())
        self.assertTrue(folder.assistentes.filter(pk=assistant.pk).exists())
        self.assertTrue(Pasta.objects.filter(pk=folder.pk).exists())
        self.assertEqual(self.client.delete(path).status_code, 200)
        self.assertEqual(Client().delete(path).status_code, 302)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.user)
        self.assertEqual(secure.delete(path).status_code, 403)
        self.assertEqual(self.client.get(path).status_code, 405)
        import uuid
        self.assertEqual(self.client.delete(f'/api/cartorios/{first.pk}/pastas/{uuid.uuid4()}/').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/cartorios/{uuid.uuid4()}/pastas/{folder.pk}/').status_code, 404)

    def test_edit_folder_updates_assistants_and_preserves_registry_links(self):
        folder = Pasta.objects.create(owner=self.user, nome='Antiga')
        old = Assistente.objects.create(owner=self.user, nome='Antigo', llm='GPT')
        new = Assistente.objects.create(owner=self.other, nome='Novo', llm='GPT')
        folder.assistentes.add(old)
        registry = Cartorio.objects.create(owner=self.user, nome='Cartório', id='FOLDER', estado='PE')
        registry.pastas.add(folder)
        self.client.force_login(self.other)
        path = f'/api/items/pastas/{folder.pk}/'
        response = self.client.patch(path, data=json.dumps({'nome': 'Atualizada', 'assistentes': [str(new.pk)]}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        folder.refresh_from_db()
        self.assertEqual(folder.nome, 'Atualizada')
        self.assertEqual(list(folder.assistentes.all()), [new])
        self.assertTrue(registry.pastas.filter(pk=folder.pk).exists())
        self.assertTrue(Assistente.objects.filter(pk=old.pk).exists())
        import uuid
        response = self.client.patch(path, data=json.dumps({'nome': 'Inválida', 'assistentes': [str(uuid.uuid4())]}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        folder.refresh_from_db()
        self.assertEqual(folder.nome, 'Atualizada')
        self.assertEqual(list(folder.assistentes.all()), [new])
        self.assertEqual(self.client.patch(path, data='{"nome":" "}', content_type='application/json').status_code, 400)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.user)
        self.assertEqual(secure.patch(path, data='{}', content_type='application/json').status_code, 403)
        self.assertEqual(Client().patch(path, data='{}', content_type='application/json').status_code, 302)
        self.assertEqual(self.client.patch(path, data='{"nome":"Atualizada","assistentes":[]}', content_type='application/json').status_code, 200)
        self.assertFalse(folder.assistentes.exists())

    def test_edit_registry_updates_details_and_links_without_deleting_records(self):
        registry = Cartorio.objects.create(owner=self.user, nome='Antigo', id='REG1', estado='PE')
        duplicate = Cartorio.objects.create(owner=self.user, nome='Outro', id='REG2', estado='PE')
        folder = Pasta.objects.create(owner=self.other, nome='Pasta')
        assistant = Assistente.objects.create(owner=self.other, nome='Assistente', llm='GPT')
        path = f'/api/items/cartorios/{registry.pk}/'
        self.client.force_login(self.other)
        payload = {'nome': 'Atualizado', 'id': 'REG3', 'estado': 'SP', 'pastas': [str(folder.pk)], 'assistentes': [str(assistant.pk)]}
        self.assertEqual(self.client.patch(path, data=json.dumps(payload), content_type='application/json').status_code, 200)
        registry.refresh_from_db()
        self.assertEqual((registry.nome, registry.id, registry.estado), ('Atualizado', 'REG3', 'SP'))
        self.assertEqual(registry.owner, self.user)
        self.assertTrue(registry.pastas.filter(pk=folder.pk).exists())
        self.assertTrue(registry.assistentes.filter(pk=assistant.pk).exists())
        import uuid
        for change in [{'estado': 'XX'}, {'id': 'reg2'}, {'nome': ' '}, {'assistentes': [str(uuid.uuid4())]}]:
            self.assertEqual(self.client.patch(path, data=json.dumps({**payload, **change}), content_type='application/json').status_code, 400)
            registry.refresh_from_db()
            self.assertEqual(registry.nome, 'Atualizado')
            self.assertTrue(registry.pastas.filter(pk=folder.pk).exists())
        self.assertEqual(self.client.patch(path, data=json.dumps({**payload, 'pastas': [], 'assistentes': []}), content_type='application/json').status_code, 200)
        self.assertFalse(registry.pastas.exists())
        self.assertTrue(Pasta.objects.filter(pk=folder.pk).exists())
        self.assertTrue(Assistente.objects.filter(pk=assistant.pk).exists())
        self.assertEqual(Client().patch(path, data='{}', content_type='application/json').status_code, 302)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.user)
        self.assertEqual(secure.patch(path, data='{}', content_type='application/json').status_code, 403)

class DeploymentSettingsTests(SimpleTestCase):
    def settings_for(self, **environment):
        import os
        import runpy
        from pathlib import Path
        from unittest.mock import patch
        from django.conf import settings
        with patch.dict(os.environ, environment, clear=True), patch('dotenv.load_dotenv'):
            return runpy.run_path(str(Path(settings.BASE_DIR) / 'config/settings.py'))

    def test_local_keeps_sqlite_without_trusting_proxy(self):
        config = self.settings_for(DJANGO_SECRET_KEY='test-key')
        self.assertTrue(config['DEBUG'])
        self.assertEqual(config['DATABASES']['default']['ENGINE'], 'django.db.backends.sqlite3')
        self.assertNotIn('SECURE_PROXY_SSL_HEADER', config)

    def test_render_enforces_postgres_https_and_exact_hostname(self):
        config = self.settings_for(RENDER='true', RENDER_EXTERNAL_HOSTNAME='example.onrender.com',
            DJANGO_SECRET_KEY='test-key', DATABASE_URL='postgresql://user:password@db.example:5432/dashboard')
        self.assertFalse(config['DEBUG'])
        database = config['DATABASES']['default']
        self.assertEqual(database['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(database['NAME'], 'dashboard')
        self.assertEqual(database['OPTIONS']['sslmode'], 'require')
        self.assertTrue(database['CONN_HEALTH_CHECKS'])
        self.assertIn('example.onrender.com', config['ALLOWED_HOSTS'])
        self.assertIn('https://example.onrender.com', config['CSRF_TRUSTED_ORIGINS'])
        self.assertEqual(config['SECURE_PROXY_SSL_HEADER'], ('HTTP_X_FORWARDED_PROTO', 'https'))
        from django.test import RequestFactory, override_settings
        with override_settings(SECURE_PROXY_SSL_HEADER=config['SECURE_PROXY_SSL_HEADER']):
            request = RequestFactory().get('/', HTTP_X_FORWARDED_PROTO='https')
            self.assertTrue(request.is_secure())

    def test_production_requires_database_and_secret(self):
        from django.core.exceptions import ImproperlyConfigured
        with self.assertRaisesMessage(ImproperlyConfigured, 'DJANGO_SECRET_KEY'):
            self.settings_for(RENDER='true')
        with self.assertRaisesMessage(ImproperlyConfigured, 'DATABASE_URL'):
            self.settings_for(DJANGO_DEBUG='0', DJANGO_SECRET_KEY='test-key')

    def test_rejects_non_postgresql_url(self):
        from django.core.exceptions import ImproperlyConfigured
        with self.assertRaisesMessage(ImproperlyConfigured, 'PostgreSQL'):
            self.settings_for(DJANGO_SECRET_KEY='test-key', DATABASE_URL='sqlite:///db.sqlite3')


class CsvExportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('export-user')
        self.client.force_login(self.user)

    def rows(self, response):
        import csv
        import io
        return list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig')), delimiter=';'))

    def test_export_requires_login_and_get(self):
        self.assertEqual(Client().get('/relatorios/cadastros.csv').status_code, 302)
        self.assertEqual(self.client.post('/relatorios/cadastros.csv').status_code, 405)

    def test_export_empty_has_headers(self):
        response = self.client.get('/relatorios/cadastros.csv')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'\xef\xbb\xbf'))
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(self.rows(response), [])
        self.assertIn('Assistentes vinculados', response.content.decode('utf-8-sig'))

    def test_export_entities_relations_and_csv_escaping(self):
        assistant = Assistente.objects.create(owner=self.user, nome='Assistente; "João"\nAtendimento', llm='Gemini 3.8')
        folder = Pasta.objects.create(owner=self.user, nome='Certidões')
        folder.assistentes.add(assistant)
        registry = Cartorio.objects.create(owner=self.user, nome='Cartório São José', id='001', estado='PE')
        registry.pastas.add(folder)
        registry.assistentes.add(assistant)
        standalone = Pasta.objects.create(owner=self.user, nome='Sem vínculo')
        rows = self.rows(self.client.get('/relatorios/cadastros.csv?estado=SP'))
        self.assertEqual(len(rows), 4)
        by_uid = {row['UID']: row for row in rows}
        self.assertEqual(by_uid[str(assistant.pk)]['Nome'], assistant.nome)
        self.assertEqual(by_uid[str(assistant.pk)]['LLM'], 'Gemini 3.8')
        self.assertIn(str(registry.pk), by_uid[str(assistant.pk)]['Cartórios vinculados'])
        self.assertIn(str(folder.pk), by_uid[str(assistant.pk)]['Pastas vinculadas'])
        self.assertIn(str(assistant.pk), by_uid[str(folder.pk)]['Assistentes vinculados'])
        self.assertIn(str(folder.pk), by_uid[str(registry.pk)]['Pastas vinculadas'])
        self.assertEqual(by_uid[str(registry.pk)]['Identificador'], '001')
        self.assertEqual(by_uid[str(standalone.pk)]['Cartórios vinculados'], '')

    def test_export_neutralizes_spreadsheet_formulas(self):
        assistant = Assistente.objects.create(owner=self.user, nome='  =1+1', llm='@SUM(1)')
        row = self.rows(self.client.get('/relatorios/cadastros.csv'))[0]
        self.assertEqual(row['UID'], str(assistant.pk))
        self.assertEqual(row['Nome'], "'  =1+1")
        self.assertEqual(row['LLM'], "'@SUM(1)")


class CustomReportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('report-user')
        self.client.force_login(self.user)
        self.gemini = Assistente.objects.create(owner=self.user, nome='Gemini A', llm='Gemini 3.8')
        self.older = Assistente.objects.create(owner=self.user, nome='Gemini B', llm='Gemini 3.6')
        self.other = Assistente.objects.create(owner=self.user, nome='Outro', llm='GPT')
        self.folder = Pasta.objects.create(owner=self.user, nome='Pasta A')
        self.folder.assistentes.add(self.gemini, self.other)
        self.registry = Cartorio.objects.create(owner=self.user, nome='Cartório A', id='001', estado='PE')
        self.registry.pastas.add(self.folder)
        self.registry.assistentes.add(self.gemini)

    def preview(self, sections, model=''):
        return self.client.get('/api/reports/preview/', {'sections': sections, 'model': model})

    def test_authentication_and_invalid_selections(self):
        self.assertEqual(Client().get('/api/reports/preview/').status_code, 302)
        for sections in ['', 'invalido', 'resumo,invalido']:
            self.assertEqual(self.preview(sections).status_code, 400)
            self.assertEqual(self.client.get('/relatorios/cadastros.csv', {'sections': sections}).status_code, 400)

    def test_unique_registry_counts_and_gemini_family(self):
        response = self.preview('resumo,cartorios,modelos', '__gemini__')
        self.assertEqual(response.status_code, 200)
        tables = {table['key']: table for table in response.json()['tables']}
        self.assertEqual(tables['resumo']['rows'][2][1], 2)
        self.assertEqual(tables['cartorios']['rows'][0][3:], [1, 1, 1, 1])
        self.assertEqual(tables['modelos']['rows'], [['Gemini 3.6', 1], ['Gemini 3.8', 1]])
        unfiltered = self.preview('cartorios').json()['tables'][0]
        self.assertEqual(unfiltered['rows'][0][3:], [1, 1, 2, 2])

    def test_exact_model_and_unlinked_records(self):
        tables = self.preview('assistentes,sem_vinculo', 'Gemini 3.6').json()['tables']
        self.assertEqual(len(tables[0]['rows']), 1)
        self.assertEqual(tables[0]['rows'][0][0], 'Gemini B')
        self.assertEqual(tables[1]['rows'], [['Assistente', 'Gemini B', str(self.older.pk)]])
        self.assertEqual(self.preview('assistentes', 'inexistente').json()['tables'][0]['rows'], [])

    def test_custom_csv_matches_preview_and_selected_sections(self):
        import csv
        import io
        params = {'sections': 'cartorios,modelos', 'model': '__gemini__'}
        response = self.client.get('/relatorios/cadastros.csv', params)
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig')), delimiter=';'))
        for table in self.preview(**params).json()['tables']:
            self.assertIn([table['title']], rows)
            self.assertIn(table['headers'], rows)
            for row in table['rows']:
                self.assertIn([str(value) for value in row], rows)
        self.assertNotIn(['Lista de assistentes'], rows)


@override_settings(GEMINI_API_KEY='test-secret', GEMINI_MODEL='gemini-3.5-flash-lite')
class ReportAITests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = get_user_model().objects.create_user('ai-report-user')
        self.client.force_login(self.user)

    def ask(self, question):
        return self.client.post('/api/reports/preview/', data=json.dumps({'question': question}), content_type='application/json')

    def provider(self, plan):
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(plan)}]}}]
        }).encode()
        return response

    def test_interpretation_and_preview_export_without_second_ai_call(self):
        from unittest.mock import patch
        assistant = Assistente.objects.create(owner=self.user, nome='Nome privado', llm='Gemini 3.8')
        plan = {'sections': ['modelos'], 'model': '__gemini__', 'clarification': ''}
        with patch('dashboard.report_ai.urlopen', return_value=self.provider(plan)) as upstream:
            response = self.ask('Quantos assistentes usam Gemini?')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['tables'][0]['rows'], [['Gemini 3.8', 1]])
            params = response.json()['plan']
            export = self.client.get('/relatorios/cadastros.csv', {'sections': ','.join(params['sections']), 'model': params['model']})
            self.assertEqual(export.status_code, 200)
            self.assertIn('Gemini 3.8;1', export.content.decode('utf-8-sig'))
            self.assertEqual(upstream.call_count, 1)
            request = upstream.call_args.args[0]
            payload = json.loads(request.data)
            self.assertEqual(payload['contents'][0]['parts'][0]['text'], 'Quantos assistentes usam Gemini?')
            self.assertNotIn(assistant.nome, request.data.decode())
            self.assertNotIn(str(assistant.pk), request.data.decode())
            self.assertNotIn('test-secret', request.full_url)
            self.assertNotIn('test-secret', response.content.decode())
            self.assertEqual(upstream.call_args.kwargs['timeout'], 20)

    def test_invalid_questions_do_not_call_ai(self):
        from unittest.mock import patch
        with patch('dashboard.report_ai.urlopen') as upstream:
            for question in ['', 'ab', 'x' * 1001, None, ['consulta']]:
                self.assertEqual(self.ask(question).status_code, 400)
            self.assertEqual(self.client.post('/api/reports/preview/', data='{', content_type='application/json').status_code, 400)
            upstream.assert_not_called()

    def test_authentication_and_csrf(self):
        self.assertEqual(Client().post('/api/reports/preview/').status_code, 302)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.user)
        self.assertEqual(secure.post('/api/reports/preview/', data='{}', content_type='application/json').status_code, 403)

    @override_settings(GEMINI_API_KEY='')
    def test_missing_key(self):
        from unittest.mock import patch
        with patch('dashboard.report_ai.urlopen') as upstream:
            response = self.ask('Mostre os totais gerais')
            self.assertEqual(response.status_code, 503)
            self.assertIn('GEMINI_API_KEY', response.json()['error'])
            upstream.assert_not_called()

    def test_clarification_and_invalid_provider_plan(self):
        from unittest.mock import patch
        for plan, status in [
            ({'sections': [], 'model': '', 'clarification': 'Qual informação você quer consultar?'}, 422),
            ({'sections': ['DROP TABLE'], 'model': '', 'clarification': ''}, 502),
            ({'sections': ['resumo'], 'model': '', 'clarification': '', 'sql': 'SELECT 1'}, 502),
            ({'sections': [], 'model': '', 'clarification': ''}, 502),
        ]:
            with patch('dashboard.report_ai.urlopen', return_value=self.provider(plan)):
                self.assertEqual(self.ask('Consulta personalizada').status_code, status)

    def test_provider_errors_do_not_expose_secrets(self):
        from unittest.mock import patch
        from urllib.error import HTTPError, URLError
        for error, status in [(HTTPError('secret-url', 429, 'test-secret', {}, None), 429),
                              (HTTPError('secret-url', 403, 'test-secret', {}, None), 503),
                              (HTTPError('secret-url', 404, 'test-secret', {}, None), 503),
                              (URLError('test-secret'), 503), (TimeoutError('test-secret'), 503)]:
            with patch('dashboard.report_ai.urlopen', side_effect=error):
                response = self.ask('Mostre os totais gerais')
                self.assertEqual(response.status_code, status)
                self.assertNotIn('test-secret', response.content.decode())

    def test_local_request_limit(self):
        from unittest.mock import patch
        plan = {'sections': ['resumo'], 'model': '', 'clarification': ''}
        with patch('dashboard.report_ai.urlopen', return_value=self.provider(plan)) as upstream:
            for _ in range(10):
                self.assertEqual(self.ask('Mostre os totais gerais').status_code, 200)
            self.assertEqual(self.ask('Mostre os totais gerais').status_code, 429)
            self.assertEqual(upstream.call_count, 10)
