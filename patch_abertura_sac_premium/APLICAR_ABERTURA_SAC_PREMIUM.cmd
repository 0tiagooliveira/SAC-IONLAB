@echo off
setlocal EnableExtensions EnableDelayedExpansion
title HOTFIX VISUAL - ABERTURA SAC PREMIUM

echo =======================================================
echo HOTFIX VISUAL - ABERTURA DO SAC PREMIUM
echo Sem alterar regras, models, services ou fluxo.
echo =======================================================

set "ZIP=C:\Users\comer\Downloads\patch_abertura_sac_premium.zip"
set "DESTINO=C:\Ionlab\SAC\programa\SAC_Intranet_oficial"
set "TEMP=%DESTINO%\_patch_abertura_sac_premium"
set "BACKUP=%DESTINO%\backup_pre_hotfix_abertura_%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "BACKUP=%BACKUP: =0%"

echo.
echo [1/9] Fechando servidores Python abertos...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1

echo.
echo [2/9] Validando caminhos...
if not exist "%ZIP%" (
  echo ERRO: ZIP nao encontrado em %ZIP%
  pause
  exit /b 1
)
if not exist "%DESTINO%\manage.py" (
  echo ERRO: manage.py nao encontrado em %DESTINO%
  pause
  exit /b 1
)
if not exist "%DESTINO%\core\templates\core\abrir_sac.html" (
  echo ERRO: abrir_sac.html nao encontrado no destino.
  pause
  exit /b 1
)

echo.
echo [3/9] Criando backup completo dos arquivos afetados...
mkdir "%BACKUP%" >nul 2>&1
mkdir "%BACKUP%\core\templates\core" >nul 2>&1
mkdir "%BACKUP%\core\static\core\css" >nul 2>&1
mkdir "%BACKUP%\core\static\core\js" >nul 2>&1
copy "%DESTINO%\core\templates\core\abrir_sac.html" "%BACKUP%\core\templates\core\abrir_sac.html" /Y >nul
if exist "%DESTINO%\core\static\core\css\abrir_sac_premium.css" copy "%DESTINO%\core\static\core\css\abrir_sac_premium.css" "%BACKUP%\core\static\core\css\abrir_sac_premium.css" /Y >nul
if exist "%DESTINO%\core\static\core\js\abrir_sac_premium.js" copy "%DESTINO%\core\static\core\js\abrir_sac_premium.js" "%BACKUP%\core\static\core\js\abrir_sac_premium.js" /Y >nul
echo Backup criado em: %BACKUP%

echo.
echo [4/9] Extraindo ZIP dentro do projeto...
rmdir /S /Q "%TEMP%" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%ZIP%' -DestinationPath '%TEMP%' -Force"
if errorlevel 1 (
  echo ERRO ao extrair ZIP.
  pause
  exit /b 1
)

echo.
echo [5/9] Aplicando patch visual no template atual...
cd /d "%DESTINO%"
call venv\Scripts\activate.bat
python "%TEMP%\tools\aplicar_abertura_premium.py"
if errorlevel 1 (
  echo ERRO ao aplicar patch. O backup esta em: %BACKUP%
  pause
  exit /b 1
)

echo.
echo [6/9] Validando template e arquivos estaticos aplicados...
findstr /C:"abrir_sac_premium.css" "%DESTINO%\core\templates\core\abrir_sac.html" >nul || (echo ERRO: CSS nao foi injetado.& pause & exit /b 1)
findstr /C:"abrir_sac_premium.js" "%DESTINO%\core\templates\core\abrir_sac.html" >nul || (echo ERRO: JS nao foi injetado.& pause & exit /b 1)
if not exist "%DESTINO%\core\static\core\css\abrir_sac_premium.css" (echo ERRO: CSS nao copiado.& pause & exit /b 1)
if not exist "%DESTINO%\core\static\core\js\abrir_sac_premium.js" (echo ERRO: JS nao copiado.& pause & exit /b 1)

echo.
echo [7/9] Rodando validacao Django...
python manage.py check
if errorlevel 1 (
  echo ERRO no manage.py check. Verifique a mensagem acima.
  pause
  exit /b 1
)

echo.
echo [8/9] Teste rapido da rota /sac/abrir/ ...
python - <<PY
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
try:
    import django
    django.setup()
    from django.test import Client
    c=Client()
    r=c.get('/sac/abrir/')
    print('Status /sac/abrir/:', r.status_code)
except Exception as e:
    print('Aviso: teste HTTP local nao executado:', e)
PY

echo.
echo [9/9] Subindo o sistema novamente...
start "SAC Intranet" cmd /k "cd /d %DESTINO% && call venv\Scripts\activate.bat && python manage.py runserver 127.0.0.1:8000"

echo.
echo =======================================================
echo HOTFIX VISUAL APLICADO.
echo Abra no navegador:
echo http://127.0.0.1:8000/sac/abrir/
echo Backup: %BACKUP%
echo =======================================================
pause
