# Checklist de publicacao web do SAC

## 1. Antes de publicar

- Fazer backup do banco PostgreSQL.
- Fazer backup da pasta `media`.
- Definir dominio final, por exemplo `sac.empresa.com.br`.
- Gerar uma `DJANGO_SECRET_KEY` nova e grande no servidor.
- Preencher as variaveis de ambiente usando `.env.example` como modelo.

## 2. Variaveis obrigatorias

- `DJANGO_DEBUG=False`
- `DJANGO_SECRET_KEY=<chave segura>`
- `DJANGO_ALLOWED_HOSTS=<dominio>`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://<dominio>`
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`

## 3. HTTPS

Com HTTPS ativo no servidor, usar:

- `SECURE_SSL_REDIRECT=True`
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `SECURE_HSTS_SECONDS=31536000`

Se ainda estiver testando sem HTTPS, nao ativar essas flags, porque o login pode parar de funcionar em HTTP.

## 4. Comandos no servidor

```powershell
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\python manage.py migrate
.\venv\Scripts\python manage.py collectstatic --noinput
.\venv\Scripts\python manage.py check --deploy
```

## 5. Servidor web

Nao usar `runserver` para internet. Usar um servidor de aplicacao WSGI/ASGI e um proxy web na frente.

O proxy web deve servir:

- `/static/` a partir da pasta `staticfiles`
- `/media/` a partir da pasta `media`

## 6. Alertas de SLA

Agendar o comando:

```powershell
.\venv\Scripts\python manage.py processar_alertas_sla
```

Conforme regra definida:

- SLA proximo do vencimento: dias uteis as 10:00
- SLA vencido: dias uteis as 10:00 e 15:00
- SLA reincidente: suspenso
