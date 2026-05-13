@echo off
title SAC Intranet - Servidor Local 8000
cd /d C:\Ionlab\SAC\programa\SAC_Intranet_oficial
echo.
echo Iniciando o SAC Intranet em http://127.0.0.1:8000/
echo.
echo IMPORTANTE: mantenha esta janela aberta enquanto estiver usando o sistema.
echo.
"C:\Ionlab\SAC\programa\SAC_Intranet_oficial\venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000 --noreload
echo.
echo O servidor foi encerrado. Copie a mensagem acima se precisar analisar o erro.
pause
