# Status Dashboard — Django

Django 5.2 LTS com autenticação nativa, SQLite, administração e histórico de login. Python 3.10+ (incluindo Python 3.14).

## Relatório CSV

Na aba **Dashboard**, clique em **Gerar relatório** e digite sua pergunta, por exemplo: “Quantos assistentes usam Gemini?” ou “Quantas pastas cada cartório possui?”. O Gemini interpreta a pergunta em seções e um filtro de modelo; o Django valida o plano e calcula os resultados. A prévia mostra a interpretação usada. Perguntas fora das capacidades suportadas pedem reformulação, sem executar SQL ou código gerado pela IA.

As consultas suportadas são totais gerais, pastas/assistentes por cartório, assistentes por pasta, distribuição por modelo, lista de assistentes e cadastros sem vínculo. É possível filtrar assistentes por um modelo exato ou por todas as versões do Gemini. Filtros por nome de cartório, estado, data e rankings ainda não são suportados. Os totais por cartório contam assistentes únicos nos vínculos diretos e nas pastas.

Clique em **Visualizar relatório** e depois em **Baixar CSV**. Ao editar a pergunta, gere uma nova prévia. O download usa o plano validado sem chamar a IA novamente e consulta os dados atuais. O CSV usa UTF-8 com BOM, separador `;` e proteção contra fórmulas; importe identificadores como texto no Excel para preservar zeros à esquerda. A URL `/relatorios/cadastros.csv` sem parâmetros mantém a exportação completa anterior.

### Configurar o Gemini

No Render, em **Environment**, defina `GEMINI_API_KEY` e faça deploy do código. Opcionalmente configure `GEMINI_MODEL` (padrão: `gemini-3.5-flash-lite`). A chave nunca vai ao navegador. O servidor envia somente a pergunta e as instruções de interpretação; nomes, UIDs e demais registros do banco não são enviados. O próprio texto digitado é enviado ao Google: evite incluir informações confidenciais.

O modelo padrão oferece cota gratuita conforme a conta e os limites do Google; a aplicação não ativa faturamento nem altera o plano da conta. Se houver erro de chave, limite ou conexão, a tela informa o problema. Sem chave, a consulta por pergunta fica indisponível, mas a exportação completa continua funcionando. Para desenvolvimento local, preencha `GEMINI_API_KEY` no arquivo `.env` na raiz. Ele é carregado automaticamente; variáveis já definidas no ambiente têm prioridade. O `.env` é ignorado pelo Git. Nunca grave a chave real em `.env.example`.

A integração usa a API REST com saída estruturada, timeout de 20 segundos e limite local de 10 perguntas por usuário/minuto. Esse limite usa o cache Django: com o cache de memória padrão, ele é por processo e reinicia com o serviço. Para limite compartilhado entre workers, configure um backend de cache compartilhado. Os testes simulam o provedor e não consomem cota real.

Referências: [saída estruturada do Gemini](https://ai.google.dev/gemini-api/docs/generate-content/structured-output), [preços e cotas gratuitas](https://ai.google.dev/gemini-api/docs/pricing).

## Executar neste projeto

As dependências já estão instaladas em `.venv` e as migrações foram aplicadas.

```bash
source .venv/bin/activate
python manage.py runserver
```

Abra http://127.0.0.1:8000. Para administração: http://127.0.0.1:8000/admin/.

O administrador inicial foi criado com senha aleatória. Consulte `.initial-admin.txt` localmente, entre e altere a senha no admin. Exclua o arquivo após guardar a credencial. Esse arquivo tem permissão de leitura restrita e é ignorado pelo Git. Nenhuma senha padrão está embutida no código.

Os eventos estão em **Administração → Dashboard → Registros de acesso** (`/admin/dashboard/accessevent/`): entradas, saídas, falhas e bloqueios, com usuário, data, IP e navegador. Apenas superusuários veem esse histórico. Não são armazenadas senhas. Isso registra autenticações; não é um histórico de cada página visitada ou de alterações feitas pelo dashboard. O admin mantém seu próprio histórico de edição.

Em outra instalação:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Se a distribuição não tiver `venv`/`ensurepip`, instale o pacote de venv correspondente à versão do Python antes. `python server.py` continua disponível como atalho para o servidor de desenvolvimento, usando o Python do ambiente virtual.

## Dados e usuários

Cartórios, pastas e assistentes são compartilhados entre todos os usuários autenticados: todos podem visualizar, criar, editar assistentes e excluir registros pelo dashboard. O campo responsável registra quem criou cada item e não restringe seu acesso. Os dados existentes de todas as contas são preservados e passam a aparecer juntos. O acesso ao admin continua dependendo de staff e permissões; o histórico de acessos continua exclusivo dos superusuários.

Os dados antigos do `localStorage` não podem ser lidos pelo servidor. Entre com uma conta autorizada e clique em **Importar dados locais**. O botão aparece quando existem dados antigos no mesmo navegador e na mesma origem (protocolo, host e porta). A importação exige que o painel compartilhado esteja vazio, preserva os vínculos e mantém a cópia local. Se usava outro host/porta, acesse o Django na mesma origem para que o navegador disponibilize os dados antigos. Dados abertos anteriormente via `file://` precisam ser exportados daquele contexto; não ficam acessíveis automaticamente no HTTP.

Faça backup de `db.sqlite3` e da chave secreta. A chave de desenvolvimento é gerada em `.django-secret-key`, com permissão restrita; em produção, forneça `DJANGO_SECRET_KEY` no ambiente.

## Segurança e produção

- Login, logout por POST e operações de escrita protegidos por CSRF; sessões no banco com cookies HttpOnly e SameSite=Strict, duração de 8 horas.
- Após 5 senhas inválidas por IP em 5 minutos, os logins do dashboard e do admin ficam bloqueados até as tentativas expirarem. O IP vem de `REMOTE_ADDR`; cabeçalhos de encaminhamento não são confiados automaticamente.
- O código JavaScript e o CSS são públicos, como em aplicações web usuais. Os dados e as operações exigem autenticação no servidor.
- `DEBUG=1` é o padrão **apenas para desenvolvimento local**. O servidor `runserver` não é servidor de produção.

Para produção, exporte as variáveis de `.env.example` com os valores reais (o projeto não carrega `.env` automaticamente), use HTTPS e configure um servidor/proxy apropriado. Com `DJANGO_DEBUG=0`, a chave secreta é obrigatória, cookies exigem HTTPS, HTTP é redirecionado e HSTS é ativado. Se terminar TLS em proxy, configure o repasse de esquema de forma confiável no Django/servidor; não exponha a aplicação diretamente nem aceite cabeçalhos de proxy de clientes. Avalie o limite por IP quando houver proxy: sem o IP de origem confiável, todos os usuários podem compartilhar o limite.

```bash
python manage.py collectstatic --noinput
python manage.py check --deploy
 gunicorn config.wsgi:application --bind 127.0.0.1:8000
```

WhiteNoise serve os arquivos estáticos coletados. SQLite é usado somente no desenvolvimento sem `DATABASE_URL`; em produção, PostgreSQL é obrigatório. Mantenha as dependências atualizadas e defina retenção e acesso adequados para os registros de IP e navegador.

## Verificação

```bash
python manage.py check
python manage.py test
```

Os testes cobrem autenticação, CSRF, compartilhamento entre usuários autenticados, CRUD/vínculos, auditoria, bloqueio de tentativas e importação com reversão de falhas.

## Deploy no Render

1. Envie o código ao GitHub e crie um PostgreSQL no Render, na mesma região do Web Service.
2. Crie **New → Web Service**, selecione o repositório e o ambiente Python.
3. Use **Build Command:** `bash build.sh` e **Start Command:** `bash start.sh`.
4. Em **Environment**, cadastre:

| Variável | Valor |
| --- | --- |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_SECRET_KEY` | Chave aleatória gerada no painel, mantida entre deploys |
| `DATABASE_URL` | Internal Database URL do PostgreSQL |
| `DJANGO_ALLOWED_HOSTS` | Domínio personalizado, se houver, sem protocolo |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Origem personalizada, se houver, com `https://` |

O hostname `onrender.com` é incluído automaticamente a partir de `RENDER_EXTERNAL_HOSTNAME`. O Render define `RENDER=true`; nesse ambiente, o projeto reconhece HTTPS pelo cabeçalho do proxy e desativa DEBUG por padrão. Fora do Render, habilite `DJANGO_TRUST_PROXY=1` apenas quando o proxy confiável remover/sobrescrever o cabeçalho de protocolo e o backend não aceitar tráfego direto.

O build coleta os estáticos e verifica as configurações de segurança. A inicialização aplica migrações antes de iniciar o Gunicorn. Para várias instâncias, mova `python manage.py migrate --noinput` para uma etapa única de pre-deploy, se disponível no plano.

Após publicar, use o Shell de um serviço que ofereça esse recurso e execute `python manage.py createsuperuser`. Não use `bootstrap_admin` em filesystem temporário: ele salva a senha em arquivo local. Não há criação de usuário com senha padrão no deploy.

O banco remoto começa vazio. O SQLite local e seus usuários não são enviados automaticamente: migrar os dados existentes requer uma exportação/importação separada. Fazer deploy não apaga nem altera o banco local. Para uso contínuo, escolha um banco sem expiração e configure backups; o PostgreSQL gratuito do Render expira após 30 dias.

Referências: https://render.com/docs/deploy-django e https://render.com/docs/free.

## CI/CD: GitHub Actions e Render

O workflow `.github/workflows/ci.yml` executa em pushes para `main`, pull requests destinados a `main` e manualmente em **Actions → CI → Run workflow**.

A pipeline roda em Python 3.12 e 3.14 com um PostgreSQL 16 temporário e isolado. Verifica dependências, sintaxe JavaScript/Bash, configurações Django, migrações pendentes, aplicação das migrações, coleta de estáticos, testes de autenticação/CRUD/importação e configurações de segurança de produção. As credenciais no YAML são exclusivamente do banco descartável do CI; não há acesso ao banco do Render.

Para ativar o deploy automático após os testes:

1. Envie o workflow ao GitHub e confira se os dois jobs do **CI** ficam verdes em **Actions**.
2. No Render, abra o Web Service → **Settings → Build & Deploy → Auto-Deploy** e selecione **After CI Checks Pass**. A branch deve ser `main`, e a integração GitHub precisa estar conectada (não apenas a URL pública do repositório).
3. Mantenha **Build Command** `bash build.sh` e **Start Command** `bash start.sh`, além das variáveis de produção já cadastradas.
4. Nos próximos pushes/merges em `main`, o Render aguardará os checks e iniciará o deploy se todos passarem. Pull requests executam testes; não publicam produção por este fluxo.

Não configure um deploy hook em paralelo: a integração nativa já aciona a publicação. A opção **On Commit** publica antes do resultado do CI, portanto substitua-a por **After CI Checks Pass**. Esse ajuste é feito no painel e não é aplicado automaticamente por este arquivo.

Recomenda-se também uma regra de proteção de `main` no GitHub que exija os dois checks **Django / Python 3.12 / PostgreSQL** e **Django / Python 3.14 / PostgreSQL** antes de permitir merge. Os checks só aparecem para seleção após a primeira execução. Essa proteção é uma configuração separada do repositório.

Um CI verde confirma os testes; o resultado do deploy fica em **Render → Events/Deploys**, onde devem ser conferidos migrações, inicialização e acesso ao site. O CI não confirma sozinho que a aplicação foi publicada.

Referência: https://render.com/docs/deploys#integrating-with-ci.
