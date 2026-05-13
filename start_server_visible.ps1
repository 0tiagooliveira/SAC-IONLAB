Set-Location 'C:\Ionlab\SAC\programa\SAC_Intranet_oficial'
.\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload *> server_visible.log
Read-Host 'Servidor encerrado. Pressione Enter para fechar'
