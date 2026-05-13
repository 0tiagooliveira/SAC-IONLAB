# Generated to control SAC opening rectification access.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0043_usuario_cpf_permissoes'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='usuariosistema',
            options={
                'ordering': ['nome_completo'],
                'permissions': [
                    ('acessar_painel', 'Pode acessar Painel / Intra'),
                    ('acessar_dashboard_sla', 'Pode acessar Dashboard SLA'),
                    ('acessar_pesquisa_sacs', 'Pode acessar Pesquisa de SACs'),
                    ('acessar_abertura_sac', 'Pode acessar Abertura de SAC'),
                    ('acessar_comercial', 'Pode acessar Análise Comercial'),
                    ('acessar_logistica', 'Pode acessar Gestão Logística'),
                    ('acessar_assessoria', 'Pode acessar Assessoria Científica'),
                    ('acessar_assistencia_tecnica', 'Pode acessar Assistência Técnica'),
                    ('acessar_diretoria', 'Pode acessar Diretoria'),
                    ('acessar_financeiro', 'Pode acessar Gestão Financeira'),
                    ('acessar_licitacao', 'Pode acessar Gestão Licitação'),
                    ('acessar_importacoes', 'Pode acessar Importações'),
                    ('acessar_admin_cadastros', 'Pode acessar Cadastros / Admin'),
                    ('retificar_sac', 'Pode retificar dados de abertura do SAC'),
                ],
            },
        ),
    ]
