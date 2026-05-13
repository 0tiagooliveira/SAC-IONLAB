@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "PROJ=C:\Ionlab\SAC\programa\SAC_Intranet_oficial"
set "ZIP=%USERPROFILE%\Downloads\hotfix_motor_tecnico.zip"
set "TMP=%USERPROFILE%\Downloads\hotfix_motor_tecnico_extraido"

echo ============================================================
echo HOTFIX MOTOR TECNICO - ASSISTENCIA TECNICA
echo ============================================================

echo.
echo [1/7] Fechando processos Python antigos, se existirem...
taskkill /F /IM python.exe >nul 2>nul
taskkill /F /IM pythonw.exe >nul 2>nul

echo.
echo [2/7] Limpando pasta temporaria...
if exist "%TMP%" rmdir /S /Q "%TMP%"
mkdir "%TMP%"

echo.
echo [3/7] Extraindo ZIP...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%TMP%' -Force"
if errorlevel 1 (
  echo ERRO: nao consegui extrair o ZIP em %ZIP%
  pause
  exit /b 1
)

echo.
echo [4/7] Entrando no projeto...
cd /d "%PROJ%"
if errorlevel 1 (
  echo ERRO: nao encontrei a pasta do projeto: %PROJ%
  pause
  exit /b 1
)

echo.
echo [5/7] Aplicando patch...
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" "%TMP%\aplicar_hotfix_motor_tecnico.py"
) else (
  python "%TMP%\aplicar_hotfix_motor_tecnico.py"
)
if errorlevel 1 (
  echo ERRO: falha ao aplicar o hotfix.
  pause
  exit /b 1
)

echo.
echo [6/7] Validando sintaxe e Django check...
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" -m py_compile core\views_assistencia_tecnica.py
  if errorlevel 1 goto erro_validacao
  "venv\Scripts\python.exe" manage.py check
  if errorlevel 1 goto erro_validacao
) else (
  python -m py_compile core\views_assistencia_tecnica.py
  if errorlevel 1 goto erro_validacao
  python manage.py check
  if errorlevel 1 goto erro_validacao
)

echo.
echo [7/7] Subindo servidor local...
echo Abra: http://127.0.0.1:8000/sac/assistencia-tecnica/
echo.
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
) else (
  python manage.py runserver 127.0.0.1:8000
)
exit /b 0

:erro_validacao
echo.
echo ERRO: validacao falhou. O backup .bak_motor_tecnico foi criado ao lado do arquivo original.
pause
exit /b 1
