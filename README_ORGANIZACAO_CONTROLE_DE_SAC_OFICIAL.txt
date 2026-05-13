CONTROLE DE SAC OFICIAL - ORGANIZACAO DA BASE

Esta pasta foi preparada para padronizar o projeto e evitar erros de caminho, templates e execucao.

1. O QUE E ARQUIVO ATIVO
Os arquivos ativos do projeto sao:
- config\settings.py
- config\urls.py
- core\models.py
- core\forms.py
- core\views.py
- core\admin.py
- core\templates\core\*.html
- core\templates\admin\core\pecatabelapreco\change_list.html
- core\migrations\*.py

2. O QUE E HISTORICO / BACKUP
Arquivos com nomes como abaixo nao devem ser usados para novas correcoes, salvo busca tecnica especifica:
- *_backup.py
- *_backup.html
- *bkp*.py
- *bkp*.html
- *.txt dentro de migrations que sao apenas historico

3. REGRA DE TRABALHO
Sempre considerar esta base como:
CONTROLE DE SAC OFICIAL

4. PASTAS IMPORTANTES
Projeto:
C:\Ionlab\SAC\programa\sac_intranet

Templates principais:
C:\Ionlab\SAC\programa\sac_intranet\core\templates\core

Override do admin para tabela de pecas:
C:\Ionlab\SAC\programa\sac_intranet\core\templates\admin\core\pecatabelapreco

5. FLUXO PADRAO PARA TESTAR
1) Abrir CMD
2) Ir para a pasta do projeto
3) Ativar venv
4) Rodar py_compile
5) Rodar manage.py check
6) Rodar migrate se houver migration nova
7) Rodar runserver

6. SCRIPTS DE APOIO
- 01_garantir_pastas_oficiais.bat
- 02_validar_e_subir_sem_migrate.bat
- 03_validar_migrar_e_subir.bat
- 04_backup_controle_sac_oficial.bat

7. OBSERVACAO IMPORTANTE
Sempre que houver um novo zip estavel, ele deve substituir a base oficial para evitar regressao.
