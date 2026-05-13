from django.db import migrations, models
import re
import unicodedata


def _normalizar_codigo(valor):
    texto = unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode('ascii')
    texto = texto.replace('&', ' e ')
    texto = re.sub(r'[^a-zA-Z0-9]+', '_', texto.strip().lower())
    return re.sub(r'_+', '_', texto).strip('_').upper()


def popular_codigos_acaoemespera(apps, schema_editor):
    AcaoEmEspera = apps.get_model('core', 'AcaoEmEspera')
    usados = set()
    for acao in AcaoEmEspera.objects.all().order_by('id'):
        base = _normalizar_codigo(getattr(acao, 'codigo', None) or getattr(acao, 'nome', None))
        if not base:
            base = f'ACAO_{acao.id}'
        codigo = base
        i = 2
        while codigo in usados:
            codigo = f'{base}_{i}'
            i += 1
        acao.codigo = codigo
        acao.save(update_fields=['codigo'])
        usados.add(codigo)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_remove_sacitem_uq_sacitem_item_rastreio_and_more'),
    ]

    operations = [
        migrations.RunPython(popular_codigos_acaoemespera, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='acaoemespera',
            name='codigo',
            field=models.CharField(max_length=100, unique=True),
        ),
    ]
