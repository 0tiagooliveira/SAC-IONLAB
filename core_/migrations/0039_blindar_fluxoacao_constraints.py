from django.db import migrations, models
from django.db.models import Count


def deduplicar_fluxoacao_antes_constraint(apps, schema_editor):
    FluxoAcaoSetor = apps.get_model('core', 'FluxoAcaoSetor')
    db_alias = schema_editor.connection.alias

    # Remove duplicidades ativas por combinação de ação atual + setor atual.
    duplicados = (
        FluxoAcaoSetor.objects.using(db_alias)
        .filter(ativo=True)
        .values('acao_atual_id', 'setor_atual_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
    )
    for grupo in duplicados:
        qs = (
            FluxoAcaoSetor.objects.using(db_alias)
            .filter(
                ativo=True,
                acao_atual_id=grupo['acao_atual_id'],
                setor_atual_id=grupo['setor_atual_id'],
            )
            .order_by('id')
        )
        manter = qs.first()
        if manter:
            qs.exclude(id=manter.id).delete()

    # Remove duplicidades ativas genéricas (ação sem setor específico).
    duplicados_genericos = (
        FluxoAcaoSetor.objects.using(db_alias)
        .filter(ativo=True, setor_atual_id__isnull=True)
        .values('acao_atual_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
    )
    for grupo in duplicados_genericos:
        qs = (
            FluxoAcaoSetor.objects.using(db_alias)
            .filter(
                ativo=True,
                acao_atual_id=grupo['acao_atual_id'],
                setor_atual_id__isnull=True,
            )
            .order_by('id')
        )
        manter = qs.first()
        if manter:
            qs.exclude(id=manter.id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0038_merge_20260419_1322'),
    ]

    operations = [
        migrations.RunPython(
            deduplicar_fluxoacao_antes_constraint,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name='fluxoacaosetor',
            constraint=models.UniqueConstraint(
                fields=('acao_atual', 'setor_atual'),
                condition=models.Q(ativo=True),
                name='uq_fluxoacao_acao_setor_atual_ativo',
            ),
        ),
        migrations.AddConstraint(
            model_name='fluxoacaosetor',
            constraint=models.UniqueConstraint(
                fields=('acao_atual',),
                condition=models.Q(ativo=True, setor_atual__isnull=True),
                name='uq_fluxoacao_acao_generica_ativa',
            ),
        ),
    ]
