from django.db import migrations, models
import re
import unicodedata


def _normalizar_codigo(valor):
    texto = unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode('ascii')
    texto = texto.replace('&', ' e ')
    texto = re.sub(r'[^a-zA-Z0-9]+', '_', texto.strip().lower())
    return re.sub(r'_+', '_', texto).strip('_').upper()


def popular_codigos(apps, schema_editor):
    Setor = apps.get_model('core', 'Setor')
    AcaoEmEspera = apps.get_model('core', 'AcaoEmEspera')

    for setor in Setor.objects.all():
        codigo = _normalizar_codigo(getattr(setor, 'codigo', None) or getattr(setor, 'nome', None))
        Setor.objects.filter(pk=setor.pk).update(codigo=codigo)

    for acao in AcaoEmEspera.objects.all():
        codigo = _normalizar_codigo(getattr(acao, 'codigo', None) or getattr(acao, 'nome', None))
        AcaoEmEspera.objects.filter(pk=acao.pk).update(codigo=codigo)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0030_remove_sacitem_uq_sacitem_item_rastreio_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='setor',
            name='codigo',
            field=models.CharField(blank=True, db_index=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='acaoemespera',
            name='codigo',
            field=models.CharField(blank=True, db_index=True, max_length=100, null=True),
        ),
        migrations.RunPython(popular_codigos, migrations.RunPython.noop),
    ]
