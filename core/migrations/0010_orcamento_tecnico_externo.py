from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_add_endereco_usuario_contato'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrcamentoTecnicoExterno',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telefone', models.CharField(blank=True, max_length=30, null=True)),
                ('whatsapp', models.CharField(blank=True, max_length=30, null=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('cidade', models.CharField(blank=True, max_length=255, null=True)),
                ('estado', models.CharField(blank=True, max_length=2, null=True)),
                ('precisa_peca_reposicao', models.BooleanField(default=False)),
                ('quantidade_horas', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('valor_unitario_hora', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('valor_total_horas', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('valor_total_pecas', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('valor_total_geral', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('sac', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='orcamento_tecnico_externo', to='core.sac')),
                ('tecnico_externo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='orcamentos_tecnicos', to='core.tecnicoexterno')),
            ],
            options={
                'verbose_name': 'Orçamento Técnico Externo',
                'verbose_name_plural': 'Orçamentos Técnicos Externos',
            },
        ),
        migrations.CreateModel(
            name='OrcamentoTecnicoExternoPeca',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('referencia', models.CharField(max_length=100)),
                ('descricao', models.CharField(max_length=255)),
                ('quantidade', models.DecimalField(decimal_places=2, default=1, max_digits=10)),
                ('valor_unitario', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('valor_total', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('orcamento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pecas', to='core.orcamentotecnicoexterno')),
                ('peca', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='itens_orcamento', to='core.pecatabelapreco')),
            ],
            options={
                'verbose_name': 'Peça do Orçamento Técnico Externo',
                'verbose_name_plural': 'Peças do Orçamento Técnico Externo',
            },
        ),
    ]
