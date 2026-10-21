// ===== Estado / persistência =====
// Modelo:
//   cartorios:   { uid, id, nome, estado, pastas: [uid], assistentes: [uid] }
//   pastas:      { uid, nome, assistentes: [uid] }
//   assistentes: { uid, nome, llm }
const STORAGE_KEY = 'status-dashboard:v1';
const ESTADOS = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'];

let db = { cartorios: [], pastas: [], assistentes: [] };
let loaded = false;
const statusMessage = document.getElementById('connection-status');

async function api(path, method = 'GET', data) {
  const response = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name="csrfmiddlewaretoken"]').value },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (response.redirected || response.status === 401) {
    window.location.replace('/login/');
    throw new Error('Sua sessão expirou. Entre novamente.');
  }
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(result.error || 'Não foi possível salvar. Tente novamente.');
  }
  return response.json();
}

function updateState(data) {
  db = data;
  loaded = true;
  statusMessage.hidden = true;
  renderDashboard();
}

async function carregar() {
  try {
    updateState(await api('/api/state/'));
    document.querySelectorAll('[data-open]').forEach(button => { button.disabled = false; });
  } catch (error) {
    statusMessage.textContent = 'Não foi possível carregar os dados. Recarregue a página para tentar novamente.';
    statusMessage.hidden = false;
  }
}

async function salvarForm(event, kind, getData, editId = null) {
  event.preventDefault();
  if (!loaded) return;
  const form = event.target;
  const button = form.querySelector('[type="submit"]');
  button.disabled = true;
  try {
    updateState(await api('/api/items/' + kind + '/' + (editId ? editId + '/' : ''), editId ? 'PATCH' : 'POST', getData(form)));
    form.closest('dialog').close();
    toast(editId ? 'Assistente atualizado!' : 'Registro criado!');
  } catch (error) {
    let message = form.querySelector('.erro');
    if (!message) {
      message = document.createElement('p');
      message.className = 'erro';
      message.setAttribute('role', 'alert');
      form.querySelector('.modal-actions').before(message);
    }
    message.textContent = error.message;
    message.hidden = false;
  } finally {
    button.disabled = false;
  }
}

const byUid = (lista, id) => lista.find(x => x.uid === id);
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), 2200);
}

// ===== Abas =====
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b === btn));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + btn.dataset.tab));
    if (btn.dataset.tab === 'dashboard') renderDashboard();
  });
});

// ===== Modais =====
function preencherSelects(form) {
  form.querySelectorAll('.sel-estado').forEach(sel => {
    sel.innerHTML = '<option value="">Selecione...</option>' + ESTADOS.map(e => `<option>${e}</option>`).join('');
  });
  form.querySelectorAll('.sel-cartorio').forEach(sel => {
    sel.innerHTML = '<option value="">— Nenhum —</option>' +
      db.cartorios.map(c => `<option value="${c.uid}">${esc(c.nome)} (${esc(c.id)})</option>`).join('');
  });
  form.querySelectorAll('.sel-pasta').forEach(sel => {
    sel.innerHTML = '<option value="">— Nenhuma —</option>' +
      db.pastas.map(p => `<option value="${p.uid}">${esc(p.nome)}</option>`).join('');
  });
  form.querySelectorAll('.checklist').forEach(box => {
    const itens = db[box.dataset.source];
    box.innerHTML = itens.length
      ? itens.map(i => `<label><input type="checkbox" value="${i.uid}"> ${esc(i.nome)}${i.llm ? ` <span class="muted">· ${esc(i.llm)}</span>` : ''}</label>`).join('')
      : `<span class="vazio">Nenhum(a) criado(a) ainda.</span>`;
  });
}

document.querySelectorAll('[data-open]').forEach(btn => {
  btn.addEventListener('click', () => {
    const dlg = document.getElementById(btn.dataset.open);
    const form = dlg.querySelector('form');
    form.reset();
    const erro = form.querySelector('.erro');
    if (erro) erro.hidden = true;
    preencherSelects(form);
    dlg.showModal();
  });
});
document.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', () => btn.closest('dialog').close()));

const marcados = form => box => [...form.querySelectorAll(`.checklist[data-source="${box}"] input:checked`)].map(i => i.value);

// Operações persistidas e validadas no servidor.
document.getElementById('form-cartorio').addEventListener('submit', event => salvarForm(event, 'cartorios', f => ({
  id: f.elements.namedItem('id').value.trim(), nome: f.elements.nome.value.trim(), estado: f.elements.estado.value,
  pastas: marcados(f)('pastas'), assistentes: marcados(f)('assistentes'),
})));
document.getElementById('form-pasta').addEventListener('submit', event => salvarForm(event, 'pastas', f => ({
  nome: f.elements.nome.value.trim(), cartorio: f.elements.cartorio.value, assistentes: marcados(f)('assistentes'),
})));
document.getElementById('form-assistente').addEventListener('submit', event => salvarForm(event, 'assistentes', f => ({
  nome: f.elements.nome.value.trim(), llm: f.elements.llm.value.trim(), cartorio: f.elements.cartorio.value, pasta: f.elements.pasta.value,
})));

document.addEventListener('click', event => {
  const button = event.target.closest('[data-edit-assistente]');
  if (!button) return;
  const assistente = byUid(db.assistentes, button.dataset.editAssistente);
  if (!assistente) return;
  const form = document.getElementById('form-editar-assistente');
  form.reset();
  form.dataset.uid = assistente.uid;
  form.elements.nome.value = assistente.nome;
  form.elements.llm.value = assistente.llm;
  form.querySelector('.erro').hidden = true;
  form.closest('dialog').showModal();
});
document.getElementById('form-editar-assistente').addEventListener('submit', event =>
  salvarForm(event, 'assistentes', form => ({
    nome: form.elements.nome.value.trim(), llm: form.elements.llm.value.trim(),
  }), event.target.dataset.uid)
);

async function excluir(tipo, id) {
  if (!confirm('Excluir este item?')) return;
  try {
    updateState(await api('/api/items/' + tipo + '/' + id + '/', 'DELETE'));
    toast('Registro excluído.');
  } catch (error) {
    toast(error.message);
  }
}
document.addEventListener('click', e => {
  const b = e.target.closest('[data-del]');
  if (b) excluir(b.dataset.del, b.dataset.id);
});

// ===== Dashboard =====
const chipAssist = a => `<span class="chip">${esc(a.nome)} · <b>${esc(a.llm)}</b></span>`;

function barras(contagem) {
  const entradas = Object.entries(contagem).sort((a, b) => b[1] - a[1]);
  if (!entradas.length) return '<div class="empty">Sem dados.</div>';
  const max = entradas[0][1];
  return entradas.map(([k, v]) => `
    <div class="bar-row">
      <div class="bar-label"><span>${esc(k)}</span><span>${v}</span></div>
      <div class="bar"><span style="width:${(v / max) * 100}%"></span></div>
    </div>`).join('');
}

function renderDashboard() {
  // KPIs
  const llms = new Set(db.assistentes.map(a => a.llm));
  document.getElementById('kpis').innerHTML = [
    ['Cartórios', db.cartorios.length],
    ['Pastas', db.pastas.length],
    ['Assistentes', db.assistentes.length],
    ['LLMs em uso', llms.size],
  ].map(([l, v]) => `<div class="kpi"><div class="label">${l}</div><div class="value">${v}</div></div>`).join('');

  // Filtro de estado (mantém seleção)
  const selEstado = document.getElementById('filtro-estado');
  const atual = selEstado.value;
  const estadosUsados = [...new Set(db.cartorios.map(c => c.estado))].sort();
  selEstado.innerHTML = '<option value="">Todos os estados</option>' + estadosUsados.map(e => `<option ${e === atual ? 'selected' : ''}>${e}</option>`).join('');

  // Lista de cartórios
  const busca = document.getElementById('filtro-busca').value.trim().toLowerCase();
  const lista = db.cartorios.filter(c =>
    (!selEstado.value || c.estado === selEstado.value) &&
    (!busca || c.nome.toLowerCase().includes(busca) || c.id.toLowerCase().includes(busca)));

  document.getElementById('lista-cartorios').innerHTML = lista.length ? lista.map(c => {
    const pastas = c.pastas.map(id => byUid(db.pastas, id)).filter(Boolean);
    const assist = c.assistentes.map(id => byUid(db.assistentes, id)).filter(Boolean);
    return `
      <div class="card">
        <div class="card-head">
          <div>
            <h3>${esc(c.nome)}</h3>
            <div class="meta">
              <span class="badge">ID: ${esc(c.id)}</span>
              <span class="badge">${esc(c.estado)}</span>
              <span class="badge gray">${pastas.length} pasta(s)</span>
              <span class="badge gray">${assist.length} assistente(s)</span>
            </div>
          </div>
          <button class="icon-btn" title="Excluir cartório" data-del="cartorios" data-id="${c.uid}">✕</button>
        </div>
        ${pastas.length ? `<div class="sub"><h4>Pastas</h4>${pastas.map(p => {
          const as = p.assistentes.map(id => byUid(db.assistentes, id)).filter(Boolean);
          return `<div class="pasta"><div class="pasta-nome">📁 ${esc(p.nome)}</div>
            ${as.length ? `<div class="chips">${as.map(chipAssist).join('')}</div>` : '<div class="muted" style="font-size:12px">Sem assistentes</div>'}</div>`;
        }).join('')}</div>` : ''}
        ${assist.length ? `<div class="sub"><h4>Assistentes do cartório</h4><div class="chips">${assist.map(chipAssist).join('')}</div></div>` : ''}
      </div>`;
  }).join('') : `<div class="empty">${db.cartorios.length ? 'Nenhum cartório corresponde ao filtro.' : 'Nenhum cartório criado ainda. Vá em "Início" e clique em CRIAR CARTÓRIO.'}</div>`;

  document.getElementById('lista-assistentes').innerHTML = db.assistentes.length
    ? db.assistentes.map(a => `<div class="assistant-item">
        <div><strong>${esc(a.nome)}</strong><div class="muted">${esc(a.llm)}</div></div>
        <button type="button" class="btn-ghost" data-edit-assistente="${a.uid}" aria-label="Editar ${esc(a.nome)}">Editar</button>
      </div>`).join('')
    : '<div class="empty">Nenhum assistente criado ainda.</div>';

  // Gráficos
  const porLlm = {};
  db.assistentes.forEach(a => (porLlm[a.llm] = (porLlm[a.llm] || 0) + 1));
  document.getElementById('chart-llm').innerHTML = barras(porLlm);
  const porEstado = {};
  db.cartorios.forEach(c => (porEstado[c.estado] = (porEstado[c.estado] || 0) + 1));
  document.getElementById('chart-estado').innerHTML = barras(porEstado);

  // Pastas/assistentes sem vínculo
  const pastasVinc = new Set(db.cartorios.flatMap(c => c.pastas));
  const assistVinc = new Set([...db.cartorios.flatMap(c => c.assistentes), ...db.pastas.flatMap(p => p.assistentes)]);
  const soltos = [
    ...db.pastas.filter(p => !pastasVinc.has(p.uid)).map(p => ({ t: 'pastas', u: p.uid, txt: `📁 ${esc(p.nome)}` })),
    ...db.assistentes.filter(a => !assistVinc.has(a.uid)).map(a => ({ t: 'assistentes', u: a.uid, txt: `🤖 ${esc(a.nome)} <span class="muted">· ${esc(a.llm)}</span>` })),
  ];
  document.getElementById('soltos').innerHTML = soltos.length
    ? soltos.map(s => `<div class="solto-item"><span>${s.txt}</span><button class="icon-btn" data-del="${s.t}" data-id="${s.u}">✕</button></div>`).join('')
    : '<div class="empty">Tudo vinculado.</div>';
}

document.getElementById('filtro-busca').addEventListener('input', renderDashboard);
document.getElementById('filtro-estado').addEventListener('change', renderDashboard);

document.querySelectorAll('[data-open]').forEach(button => { button.disabled = true; });
carregar();

async function verificarSessao() {
  try {
    const response = await fetch('/api/session');
    if (!response.ok) window.location.replace('/login/');
  } catch {
    statusMessage.textContent = 'Conexão indisponível. Verifique a conexão antes de continuar.';
    statusMessage.hidden = false;
  }
}
window.addEventListener('pageshow', verificarSessao);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) verificarSessao();
});
setInterval(verificarSessao, 60000);
document.getElementById('logout').addEventListener('click', async () => {
  try {
    const response = await fetch('/logout/', {
      method: 'POST',
      headers: { 'X-CSRFToken': document.querySelector('[name="csrfmiddlewaretoken"]').value },
    });
    if (!response.ok) throw new Error('logout');
    window.location.replace('/login/');
  } catch {
    toast('Não foi possível sair. Tente novamente.');
  }
});

const importButton = document.getElementById('import-legacy');
let legacy;
try {
  legacy = JSON.parse(localStorage.getItem(STORAGE_KEY));
  importButton.hidden = !legacy || !['cartorios', 'pastas', 'assistentes'].some(kind => legacy[kind]?.length);
} catch { /* Dados locais indisponíveis. */ }
importButton.addEventListener('click', async () => {
  if (!loaded || !confirm('Importar os dados deste navegador para sua conta? O painel precisa estar vazio.')) return;
  importButton.disabled = true;
  try {
    updateState(await api('/api/import/', 'POST', legacy));
    importButton.hidden = true;
    toast('Dados importados! A cópia local foi preservada.');
  } catch (error) {
    statusMessage.textContent = error.message;
    statusMessage.hidden = false;
  } finally {
    importButton.disabled = false;
  }
});
