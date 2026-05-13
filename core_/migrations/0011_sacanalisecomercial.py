from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_orcamento_tecnico_externo'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SacAnaliseComercial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cliente_confirmou_pedido', models.BooleanField(default=False)),
                ('cliente_aceita_negociacao', models.BooleanField(default=False)),
                ('observacao_comercial', models.TextField(blank=True, null=True)),
                ('data_analise', models.DateTimeField(default=django.utils.timezone.now)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('acao_em_espera', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='analises_comerciais', to='core.acaoemespera')),
                ('proximo_status_sugerido', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='analises_comerciais_proximo_status', to='core.statussac')),
                ('sac', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='analise_comercial', to='core.sac')),
                ('usuario_responsavel', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='analises_comerciais_responsaveis', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Análise Comercial do SAC',
                'verbose_name_plural': 'Análises Comerciais do SAC',
            },
        ),
    ]
