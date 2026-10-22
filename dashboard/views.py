import csv
import json
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from .models import Cartorio, Pasta, Assistente
from .reports import build_report
from .report_ai import interpret_question, ReportAIError

MODELS = {'cartorios': Cartorio, 'pastas': Pasta, 'assistentes': Assistente}

@login_required
@ensure_csrf_cookie
def index(request):
    return render(request, 'index.html')

@require_GET
def session(request):
    return JsonResponse({}, status=200 if request.user.is_authenticated else 401)

def snapshot():
    return {
        'cartorios': [dict(uid=str(c.pk), id=c.id, nome=c.nome, estado=c.estado, pastas=[str(x.pk) for x in c.pastas.all()], assistentes=[str(x.pk) for x in c.assistentes.all()]) for c in Cartorio.objects.all().prefetch_related('pastas', 'assistentes')],
        'pastas': [dict(uid=str(p.pk), nome=p.nome, assistentes=[str(x.pk) for x in p.assistentes.all()]) for p in Pasta.objects.all().prefetch_related('assistentes')],
        'assistentes': [dict(uid=str(a.pk), nome=a.nome, llm=a.llm) for a in Assistente.objects.all()],
    }


@login_required
@require_http_methods(['GET', 'POST'])
def report_preview(request):
    try:
        if request.method == 'POST':
            payload = read_json(request)
            question = payload.get('question')
            if not isinstance(question, str) or not 3 <= len(question.strip()) <= 1000:
                raise ValueError('Digite uma pergunta entre 3 e 1.000 caracteres.')
            bucket = f'report-ai:{request.user.pk}:{int(timezone.now().timestamp()) // 60}'
            if cache.add(bucket, 1, timeout=120):
                count = 1
            else:
                count = cache.incr(bucket)
            if count > 10:
                return JsonResponse({'error': 'Aguarde um minuto antes de gerar mais relatórios.'}, status=429)
            plan = interpret_question(question.strip())
        else:
            plan = {'sections': request.GET.get('sections', '').split(','), 'model': request.GET.get('model', '')}
        tables = build_report(snapshot(), plan['sections'], plan['model'])
    except ReportAIError as error:
        return JsonResponse({'error': str(error)}, status=error.status)
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    response = JsonResponse({'tables': tables, 'plan': plan})
    response['Cache-Control'] = 'no-store'
    return response


@login_required
@require_GET
def export_csv(request):
    data = snapshot()
    tables = None
    if 'sections' in request.GET:
        try:
            tables = build_report(data, request.GET['sections'].split(','), request.GET.get('model', ''))
        except ValueError as error:
            return JsonResponse({'error': str(error)}, status=400)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="status-relatorio-{timezone.localdate():%Y-%m-%d}.csv"'
    )
    response['Cache-Control'] = 'no-store'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';', lineterminator='\r\n')

    def safe(value):
        value = str(value)
        # Impede que nomes cadastrados sejam executados como fórmulas na planilha.
        if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')):
            return "'" + value
        return value

    def links(items):
        return ' | '.join(f"{item['nome']} [{item['uid']}]" for item in items)

    def write(values):
        writer.writerow([safe(value) for value in values])

    if tables is not None:
        model = request.GET.get('model', '')
        write(['Filtro de assistentes', 'Gemini — todas as versões' if model == '__gemini__' else model or 'Todos os modelos'])
        for table in tables:
            write([])
            write([table['title']])
            write(table['headers'])
            for row in table['rows']:
                write(row)
        return response

    write(['Tipo', 'UID', 'Nome', 'Identificador', 'Estado', 'LLM', 'Cartórios vinculados', 'Pastas vinculadas', 'Assistentes vinculados'])
    for registry in data['cartorios']:
        write(['Cartório', registry['uid'], registry['nome'], registry['id'], registry['estado'], '', '',
               links(p for p in data['pastas'] if p['uid'] in registry['pastas']),
               links(a for a in data['assistentes'] if a['uid'] in registry['assistentes'])])
    for folder in data['pastas']:
        write(['Pasta', folder['uid'], folder['nome'], '', '', '',
               links(c for c in data['cartorios'] if folder['uid'] in c['pastas']), '',
               links(a for a in data['assistentes'] if a['uid'] in folder['assistentes'])])
    for assistant in data['assistentes']:
        write(['Assistente', assistant['uid'], assistant['nome'], '', '', assistant['llm'],
               links(c for c in data['cartorios'] if assistant['uid'] in c['assistentes']),
               links(p for p in data['pastas'] if assistant['uid'] in p['assistentes']), ''])
    return response

def read_json(request):
    data = json.loads(request.body)
    if not isinstance(data, dict): raise ValueError('Dados inválidos.')
    return data

def text(data, key):
    value = data.get(key, '')
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'Preencha {key}.')
    return value.strip()

def related(model, ids):
    if not isinstance(ids, list) or len(ids) > 5000:
        raise ValueError('Vínculos inválidos.')
    objects = list(model.objects.filter(pk__in=ids))
    if len(objects) != len(set(ids)):
        raise ValueError('Um dos vínculos não existe.')
    return objects

def create(user, kind, data):
    model = MODELS[kind]
    obj = model(owner=user, nome=text(data, 'nome'))
    if kind == 'cartorios':
        obj.id, obj.estado = text(data, 'id'), text(data, 'estado')
    if kind == 'assistentes': obj.llm = text(data, 'llm')
    obj.full_clean()
    obj.save()
    if kind in ['cartorios', 'pastas']:
        obj.assistentes.set(related(Assistente, data.get('assistentes', [])))
    if kind == 'cartorios':
        obj.pastas.set(related(Pasta, data.get('pastas', [])))
    if kind in ['pastas', 'assistentes'] and data.get('cartorio'):
        cart = related(Cartorio, [data['cartorio']])[0]
        getattr(cart, kind).add(obj)
    if kind == 'assistentes' and data.get('pasta'):
        related(Pasta, [data['pasta']])[0].assistentes.add(obj)
    return obj

@login_required
@require_GET
def state(request):
    return JsonResponse(snapshot())

@login_required
@require_http_methods(['POST', 'DELETE', 'PATCH'])
def items(request, kind, uid=None):
    if kind not in MODELS: return JsonResponse({'error': 'Tipo inválido.'}, status=404)
    try:
        with transaction.atomic():
            if request.method == 'PATCH':
                if uid is None:
                    return JsonResponse({'error': 'Rota inválida.'}, status=405)
                obj = MODELS[kind].objects.select_for_update().filter(pk=uid).first()
                if obj is None:
                    return JsonResponse({'error': 'Registro não encontrado.'}, status=404)
                data = read_json(request)
                obj.nome = text(data, 'nome')
                if kind == 'assistentes':
                    obj.llm = text(data, 'llm')
                if kind == 'cartorios':
                    obj.id, obj.estado = text(data, 'id'), text(data, 'estado')
                obj.full_clean()
                fields = {'assistentes': ['nome', 'llm'], 'pastas': ['nome'], 'cartorios': ['nome', 'id', 'estado']}
                obj.save(update_fields=fields[kind])
                if kind == 'cartorios' and 'pastas' in data:
                    obj.pastas.set(related(Pasta, data['pastas']))
                if kind in ['pastas', 'cartorios'] and 'assistentes' in data:
                    obj.assistentes.set(related(Assistente, data['assistentes']))
            elif request.method == 'DELETE':
                obj = MODELS[kind].objects.filter(pk=uid).first()
                if not obj: return JsonResponse({'error': 'Registro não encontrado.'}, status=404)
                obj.delete()
            else:
                if uid: return JsonResponse({'error': 'Rota inválida.'}, status=405)
                create(request.user, kind, read_json(request))
        return JsonResponse(snapshot())
    except (ValueError, TypeError, ValidationError, IntegrityError) as error:
        message = ' '.join(error.messages) if isinstance(error, ValidationError) else 'Dados inválidos ou identificador já existente.'
        return JsonResponse({'error': message}, status=400)

@login_required
@require_POST
def import_legacy(request):
    try:
        data = read_json(request)
        if any(not isinstance(data.get(k), list) or len(data[k]) > 5000 for k in MODELS):
            raise ValueError('Dados inválidos.')
        with transaction.atomic():
            # Use the same lock for every user importing into the shared dashboard.
            from django.contrib.auth import get_user_model
            get_user_model().objects.order_by('pk').select_for_update().first()
            if any(model.objects.exists() for model in MODELS.values()):
                return JsonResponse({'error': 'A importação exige um painel vazio para evitar duplicações.'}, status=409)
            maps = {k: {} for k in MODELS}
            for kind in ['assistentes', 'pastas', 'cartorios']:
                for entry in data[kind]:
                    if not isinstance(entry, dict) or not isinstance(entry.get('uid'), str) or entry['uid'] in maps[kind]:
                        raise ValueError('Registro inválido ou duplicado.')
                    item = dict(entry)
                    for relation in ['assistentes', 'pastas']:
                        if relation in item:
                            item[relation] = [str(maps[relation][old].pk) for old in item[relation]]
                    maps[kind][entry['uid']] = create(request.user, kind, item)
        return JsonResponse(snapshot())
    except (ValueError, TypeError, KeyError, ValidationError, IntegrityError):
        return JsonResponse({'error': 'Não foi possível importar. Verifique os registros e vínculos locais.'}, status=400)


@login_required
@require_http_methods(['DELETE'])
def unlink_folder(request, registry_uid, folder_uid):
    with transaction.atomic():
        registry = Cartorio.objects.select_for_update().filter(pk=registry_uid).first()
        if registry is None or not Pasta.objects.filter(pk=folder_uid).exists():
            return JsonResponse({'error': 'Cartório ou pasta não encontrado.'}, status=404)
        registry.pastas.remove(folder_uid)
    return JsonResponse(snapshot())
