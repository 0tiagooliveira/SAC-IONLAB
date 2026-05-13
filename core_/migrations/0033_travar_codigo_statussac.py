from django.db import migrations, models
import re
import unicodedata


def _normalizar_codigo(valor):
    texto = unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode('ascii')
    texto = texto.replace('&', ' e ')
    texto = re.sub(r'[^a-zA-Z0-9]+', '_', texto.strip().lower())
    return re.sub(r'_+', '_', texto).strip('_').upper()


def popular_codigos_statussac(apps, schema_editor):
    StatusSAC = apps.get_model('core', 'StatusSAC')
    usados = set()
    for status in StatusSAC.objects.all().order_by('id'):
        base = _normalizar_codigo(getattr(status, 'codigo', None) or getattr(status, 'nome', None) or f'STATUS_{status.id}')
        if not base:
            base = f'STATUS_{status.id}'
        codigo = base
        contador = 2
        while codigo in usados:
            codigo = f'{base}_{contador}'
            contador += 1
        status.codigo = codigo
        status.save(update_fields=['codigo'])
        usados.add(codigo)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0032_travar_codigo_acaoemespera'),
    ]

    operations = [
        migrations.RunPython(popular_codigos_statussac, noop),
        migrations.AlterField(
            model_name='statussac',
            name='codigo',
            field=models.CharField(max_length=50, unique=True),
        ),
    ]
