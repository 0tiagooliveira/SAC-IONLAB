SAC Intranet Oficial - Base Congelada

Objetivo
Esta pasta foi gerada a partir do ZIP original do projeto e deve ser usada como base oficial limpa.
A regra daqui para frente é: não substituir mais arquivos grandes inteiros sem necessidade.

Método de evolução recomendado
1. Sempre fazer backup da pasta antes de qualquer alteração.
2. Corrigir uma tela por vez.
3. Alterar preferencialmente apenas:
   - um template
   - uma função específica de views
   - uma rota específica
4. Sempre validar após cada mudança:
   python manage.py check
   /intra/
   /sac/gestao/
   /sac/analise-comercial/
   /sac/abrir/
   /admin/

Estrutura futura sugerida
core/views/
    painel.py
    comercial.py
    tecnica.py
    gestao.py
    abertura.py
    importacao.py
    api.py

core/templates/core/
    painel/
    comercial/
    tecnica/
    gestao/
    abertura/
    components/

Estratégia de permissões futura
Sugestão de grupos:
- ADMIN
- CADASTROS
- ABERTURA_SAC
- GESTAO_SAC
- COMERCIAL
- ASSESSORIA_CIENTIFICA
- VISUALIZACAO_GERAL

Observação
Esta entrega não tenta refatorar tudo agora, porque uma refatoração estrutural sem homologação pode quebrar rotas já existentes.
Ela congela a base original e cria um caminho seguro para evoluir.
