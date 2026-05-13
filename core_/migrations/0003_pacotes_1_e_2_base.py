import django.utils.timezone
# Generated manually for Pacote 1 e 2

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_acaoemespera_alter_tipoocorrencia_options_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PecaTabelaPreco',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('referencia', models.CharField(max_length=100, unique=True)),
                ('descricao', models.CharField(max_length=255)),
                ('valor_unitario', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Peça - Tabela de Preço',
                'verbose_name_plural': 'Tabela de Preços de Peças',
                'ordering': ['descricao', 'referencia'],
            },
        ),
        migrations.CreateModel(
            name='TecnicoExterno',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=255)),
                ('telefone', models.CharField(blank=True, max_length=30, null=True)),
                ('whatsapp', models.CharField(blank=True, max_length=30, null=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('cidade', models.CharField(blank=True, max_length=255, null=True)),
                ('estado', models.CharField(blank=True, max_length=2, null=True)),
                ('observacao', models.TextField(blank=True, null=True)),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Técnico Externo',
                'verbose_name_plural': 'Técnicos Externos',
                'ordering': ['nome'],
            },
        ),
        migrations.CreateModel(
            name='TipoProblema',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=255, unique=True)),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Tipo de Problema',
                'verbose_name_plural': 'Tipos de Problema',
                'ordering': ['nome'],
            },
        ),
        migrations.CreateModel(
            name='TratativaProblema',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=255, unique=True)),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Tratativa do Problema',
                'verbose_name_plural': 'Tratativas do Problema',
                'ordering': ['nome'],
            },
        ),
        migrations.AddField(
            model_name='sac',
            name='cancelado_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sac',
            name='concluido_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sac',
            name='email_automatico_habilitado',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='sac',
            name='motivo_cancelamento',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sac',
            name='setor_atual',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='sacs_setor_atual', to='core.setor'),
        ),
        migrations.AddField(
            model_name='sac',
            name='status_atual',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='sacs_status_atual', to='core.statussac'),
        ),
        migrations.AlterField(
            model_name='sac',
            name='setor_responsavel',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='sacs_setor_abertura', to='core.setor'),
        ),
        migrations.CreateModel(
            name='SacHistorico',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_evento', models.DateTimeField(default=django.utils.timezone.now)),
                ('acao_executada', models.CharField(max_length=255)),
                ('observacao', models.TextField(blank=True, null=True)),
                ('sac', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='historicos', to='core.sac')),
                ('setor_destino', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='historicos_como_setor_destino', to='core.setor')),
                ('setor_origem', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='historicos_como_setor_origem', to='core.setor')),
                ('status_anterior', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='historicos_como_status_anterior', to='core.statussac')),
                ('status_novo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='historicos_como_status_novo', to='core.statussac')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Histórico do SAC',
                'verbose_name_plural': 'Histórico dos SACs',
                'ordering': ['-data_evento', '-id'],
            },
        ),
        migrations.CreateModel(
            name='SacAnaliseTecnica',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('observacao_tecnica', models.TextField(blank=True, null=True)),
                ('data_analise', models.DateTimeField(default=django.utils.timezone.now)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('proximo_status_sugerido', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='analises_tecnicas_proximo_status', to='core.statussac')),
                ('sac', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='analise_tecnica', to='core.sac')),
                ('tipo_problema', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='analises_tecnicas', to='core.tipoproblema')),
                ('tratativa_problema', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='analises_tecnicas', to='core.tratativaproblema')),
                ('usuario_responsavel', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='analises_tecnicas_responsaveis', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Análise Técnica do SAC',
                'verbose_name_plural': 'Análises Técnicas do SAC',
            },
        ),
    ]
