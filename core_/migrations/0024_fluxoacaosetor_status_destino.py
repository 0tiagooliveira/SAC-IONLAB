from django.db import migrations, models
import django.db.models.deletion


def preencher_status_destino(apps, schema_editor):
    FluxoAcaoSetor = apps.get_model('core', 'FluxoAcaoSetor')
    StatusSAC = apps.get_model('core', 'StatusSAC')

    for fluxo in FluxoAcaoSetor.objects.select_related('proximo_setor').all():
        nome_setor = getattr(getattr(fluxo, 'proximo_setor', None), 'nome', None)
        if not nome_setor:
            continue
        status = StatusSAC.objects.filter(nome__iexact=nome_setor, ativo=True).first()
        if status:
            fluxo.status_destino_id = status.id
            fluxo.save(update_fields=['status_destino'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_alter_fluxoacaosetor_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='fluxoacaosetor',
            name='status_destino',
            field=models.ForeignKey(blank=True, help_text='Status obrigatório que o SAC deverá assumir ao aplicar esta regra de fluxo.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='fluxos_destino', to='core.statussac'),
        ),
        migrations.RunPython(preencher_status_destino, migrations.RunPython.noop),
    ]
