# Generated safely for user/access control hardening.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0042_merge_tempo_uso_agendamento'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuariosistema',
            name='cpf',
            field=models.CharField(blank=True, help_text='Informe somente números. O sistema bloqueia CPF duplicado.', max_length=11, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='usuariosistema',
            name='setor',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='core.setor'),
        ),
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
                ],
            },
        ),
    ]
