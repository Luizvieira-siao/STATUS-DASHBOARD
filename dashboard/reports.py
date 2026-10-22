"""Tabelas compartilhadas pela prévia e pelo CSV personalizado."""
from collections import Counter

SECTIONS = {'resumo', 'cartorios', 'pastas', 'modelos', 'assistentes', 'sem_vinculo'}


def build_report(data, sections, model=''):
    if not sections or set(sections) - SECTIONS:
        raise ValueError('Selecione pelo menos uma opção válida para o relatório.')
    assistants = [a for a in data['assistentes'] if not model or a['llm'].casefold() == model.casefold()
                  or (model == '__gemini__' and a['llm'].casefold().startswith('gemini'))]
    ids = {a['uid'] for a in assistants}
    folders = {p['uid']: p for p in data['pastas']}
    result = []

    def add(key, title, headers, rows):
        if key in sections:
            result.append(dict(key=key, title=title, headers=headers, rows=rows))

    add('resumo', 'Totais gerais', ['Indicador', 'Quantidade'], [
        ['Cartórios cadastrados', len(data['cartorios'])], ['Pastas cadastradas', len(folders)],
        ['Assistentes no modelo selecionado' if model else 'Assistentes cadastrados', len(assistants)],
        ['Modelos em uso no recorte', len({a['llm'] for a in assistants})]])
    registry_rows = []
    for c in data['cartorios']:
        direct = set(c['assistentes']) & ids
        indirect = {a for p in c['pastas'] if p in folders for a in folders[p]['assistentes']} & ids
        registry_rows.append([c['nome'], c['id'], c['estado'], len(c['pastas']), len(direct), len(indirect), len(direct | indirect)])
    add('cartorios', 'Pastas e assistentes por cartório',
        ['Cartório', 'Identificador', 'Estado', 'Pastas associadas', 'Assistentes diretos', 'Assistentes via pastas', 'Assistentes únicos'], registry_rows)
    add('pastas', 'Assistentes por pasta', ['Pasta', 'Cartórios associados', 'Assistentes associados'], [
        [p['nome'], sum(p['uid'] in c['pastas'] for c in data['cartorios']), len(set(p['assistentes']) & ids)] for p in folders.values()])
    counts = Counter(a['llm'] for a in assistants)
    add('modelos', 'Assistentes por modelo', ['Modelo LLM', 'Quantidade de assistentes'],
        [[name, count] for name, count in sorted(counts.items(), key=lambda item: item[0].casefold())])
    add('assistentes', 'Lista de assistentes', ['Assistente', 'UID', 'Modelo LLM', 'Cartórios diretos', 'Pastas associadas'], [
        [a['nome'], a['uid'], a['llm'], sum(a['uid'] in c['assistentes'] for c in data['cartorios']),
         sum(a['uid'] in p['assistentes'] for p in folders.values())] for a in assistants])
    linked_p = {p for c in data['cartorios'] for p in c['pastas']}
    linked_a = {a for c in data['cartorios'] for a in c['assistentes']} | {a for p in folders.values() for a in p['assistentes']}
    add('sem_vinculo', 'Cadastros sem vínculo', ['Tipo', 'Nome', 'UID'],
        [['Pasta', p['nome'], p['uid']] for p in folders.values() if p['uid'] not in linked_p] +
        [['Assistente', a['nome'], a['uid']] for a in assistants if a['uid'] not in linked_a])
    return result
