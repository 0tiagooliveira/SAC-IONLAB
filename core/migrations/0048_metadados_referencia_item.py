from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0047_remover_indice_antigo_sacitem_rastreio'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemnotafiscal',
            name='modelo',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name='itemnotafiscal',
            name='origem',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='itemnotafiscal',
            name='voltagem',
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
        migrations.AddField(
            model_name='pecatabelapreco',
            name='modelo',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name='pecatabelapreco',
            name='origem',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='pecatabelapreco',
            name='voltagem',
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
    ]
