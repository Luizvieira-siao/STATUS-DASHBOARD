import json
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from .models import Cartorio, Pasta, Assistente

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
                if kind != 'assistentes' or uid is None:
                    return JsonResponse({'error': 'Rota inválida.'}, status=405)
                obj = Assistente.objects.select_for_update().filter(pk=uid).first()
                if obj is None:
                    return JsonResponse({'error': 'Assistente não encontrado.'}, status=404)
                data = read_json(request)
                obj.nome = text(data, 'nome')
                obj.llm = text(data, 'llm')
                obj.full_clean()
                obj.save(update_fields=['nome', 'llm'])
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
