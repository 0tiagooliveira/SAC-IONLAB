@echo off
setlocal
cd /d C:\Ionlab\SAC\programa\sac_intranet

echo Criando e validando pastas oficiais...
if not exist "core\templates\core" mkdir "core\templates\core"
if not exist "core\templates\admin" mkdir "core\templates\admin"
if not exist "core\templates\admin\core" mkdir "core\templates\admin\core"
if not exist "core\templates\admin\core\pecatabelapreco" mkdir "core\templates\admin\core\pecatabelapreco"
if not exist "core\migrations" mkdir "core\migrations"

echo.
echo Estrutura oficial pronta.
pause
