# Status Dashboard — Django

Django 5.2 LTS com autenticação nativa, SQLite, administração e histórico de login. Python 3.10+ (incluindo Python 3.14).

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

Cartórios, pastas e assistentes agora ficam no banco `db.sqlite3`, separados por usuário. A equipe pode cadastrar contas pelo admin, com grupos e permissões. Usuários ativos podem gerenciar seus próprios registros pelo dashboard; permissões de modelos controlam o acesso ao admin. Superusuários administram os registros de todas as contas. Para manter os vínculos consistentes, não transfira registros relacionados entre responsáveis pelo admin.

Os dados antigos do `localStorage` não podem ser lidos pelo servidor. Entre com a conta que receberá os registros e clique em **Importar dados locais**. O botão aparece quando existem dados antigos no mesmo navegador e na mesma origem (protocolo, host e porta). A importação exige uma conta sem registros, preserva os vínculos e mantém a cópia local. Se usava outro host/porta, acesse o Django na mesma origem para que o navegador disponibilize os dados antigos. Dados abertos anteriormente via `file://` precisam ser exportados daquele contexto; não ficam acessíveis automaticamente no HTTP.

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

Os testes cobrem autenticação, CSRF, isolamento por usuário, CRUD/vínculos, auditoria, bloqueio de tentativas e importação com reversão de falhas.

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
