from django.db import migrations, models
import django.db.models.deletion


def preencher_setor_destino(apps, schema_editor):
    AcaoEmEspera = apps.get_model('core', 'AcaoEmEspera')
    Setor = apps.get_model('core', 'Setor')

    mapa = {
        'Aguardando alocação em Prateleira': 'Logistica',
        'Aguardando Aprovação do Orçamento': 'SAC',
        'Aguardando Coleta no Cliente': 'Logistica',
        'Aguardando Conclusão do SAC': 'SAC',
        'Aguardando Devolução ao Cliente': 'Logistica',
        'Aguardando Disponibilidade do Cliente': 'Assessoria Cientifica',
        'Aguardando Emissão do Pedido de Saída': 'SAC',
        'Aguardando Inspeção fisica e Funcional': 'Assistencia Tecnica',
        'Aguardando Manutenção Externa': 'Assessoria Cientifica',
        'Aguardando Manutenção Interna': 'Assistencia Tecnica',
        'Analise do Ocorrido': None,
        'Em Transito (Com destino a Ionlab)': 'Logistica',
        'Em Transito (Com destino ao Cliente)': 'Logistica',
        'Emissão do Pedido de Entrada/Retorno': 'SAC',
        'Ligar para o Cliente': 'Assessoria Cientifica',
    }

    for nome_acao, nome_setor in mapa.items():
        try:
            acao = AcaoEmEspera.objects.get(nome=nome_acao)
        except AcaoEmEspera.DoesNotExist:
            continue

        if nome_setor is None:
            acao.setor_destino = None
            acao.save(update_fields=['setor_destino'])
            continue

        try:
            setor = Setor.objects.get(nome=nome_setor)
        except Setor.DoesNotExist:
            continue

        acao.setor_destino = setor
        acao.save(update_fields=['setor_destino'])


def desfazer_setor_destino(apps, schema_editor):
    AcaoEmEspera = apps.get_model('core', 'AcaoEmEspera')
    AcaoEmEspera.objects.update(setor_destino=None)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_sacanalisecomercial'),
    ]

    operations = [
        migrations.AddField(
            model_name='acaoemespera',
            name='setor_destino',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='acoes_em_espera_destino',
                to='core.setor',
                help_text='Setor que deverá assumir o SAC após esta ação em espera. Deixe em branco quando o sistema precisar permitir seleção manual do setor.',
            ),
        ),
        migrations.RunPython(preencher_setor_destino, desfazer_setor_destino),
    ]
