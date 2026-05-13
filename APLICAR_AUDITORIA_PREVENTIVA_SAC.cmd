@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "PROJ=C:\Ionlab\SAC\programa\SAC_Intranet_oficial"
set "PATCH_DIR=%~dp0"
set "STAMP=%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "STAMP=%STAMP: =0%"
set "BACKUP=%PROJ%\backup_auditoria_preventiva_%STAMP%"

if not exist "%PROJ%\manage.py" (
    echo ERRO: Nao encontrei manage.py em %PROJ%
    echo Ajuste a variavel PROJ dentro deste .cmd se o caminho estiver diferente.
    pause
    exit /b 1
)

cd /d "%PROJ%"

if not exist "%BACKUP%" mkdir "%BACKUP%"
if exist "core\management\commands\auditar_integridade_sac.py" copy "core\management\commands\auditar_integridade_sac.py" "%BACKUP%\auditar_integridade_sac.py.bkp" >nul

if not exist "core\management\commands" mkdir "core\management\commands"
copy /Y "%PATCH_DIR%core\management\commands\auditar_integridade_sac.py" "core\management\commands\auditar_integridade_sac.py" >nul
if errorlevel 1 (
    echo ERRO ao copiar auditar_integridade_sac.py
    pause
    exit /b 1
)

echo.
echo ===== ATIVANDO VENV, SE EXISTIR =====
if exist "venv\Scripts\activate.bat" call "venv\Scripts\activate.bat"

echo.
echo ===== VALIDANDO SINTAXE DO NOVO COMANDO =====
python -m py_compile "core\management\commands\auditar_integridade_sac.py"
if errorlevel 1 (
    echo ERRO: falha de sintaxe no comando de auditoria.
    pause
    exit /b 1
)

echo.
echo ===== DJANGO CHECK =====
python manage.py check
if errorlevel 1 (
    echo ERRO: manage.py check encontrou problema.
    pause
    exit /b 1
)

echo.
echo ===== RODANDO AUDITORIA SOMENTE CODIGO =====
python manage.py auditar_integridade_sac --somente-codigo --detalhado --limite 40
if errorlevel 1 (
    echo ERRO: auditoria somente codigo falhou.
    pause
    exit /b 1
)

echo.
echo ===== RODANDO AUDITORIA COMPLETA COM BANCO =====
python manage.py auditar_integridade_sac --detalhado --limite 40
if errorlevel 1 (
    echo ATENCAO: auditoria completa falhou, possivelmente por banco/postgres indisponivel.
    echo O comando somente-codigo ja foi instalado e validado.
)

echo.
echo OK - Auditoria preventiva instalada.
echo Backup anterior, se existia: %BACKUP%
echo Para rodar depois:
echo python manage.py auditar_integridade_sac --detalhado --limite 50
pause
