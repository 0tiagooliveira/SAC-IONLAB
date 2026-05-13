@echo off
setlocal
cd /d C:\Ionlab\SAC\programa\sac_intranet
call venv\Scripts\activate.bat

echo.
echo ========================================
echo CONTROLE DE SAC OFICIAL - VALIDACAO
echo ========================================
echo.
python -m py_compile core\views.py core\forms.py core\models.py core\admin.py config\urls.py
if errorlevel 1 goto erro

python manage.py check
if errorlevel 1 goto erro

echo.
echo Tudo validado. Subindo servidor...
python manage.py runserver
goto fim

:erro
echo.
echo Houve erro na validacao. Corrija antes de subir o sistema.
pause
exit /b 1

:fim
endlocal
