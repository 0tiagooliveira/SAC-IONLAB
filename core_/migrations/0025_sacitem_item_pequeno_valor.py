from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_fluxoacaosetor_status_destino'),
    ]

    operations = [
        migrations.AddField(
            model_name='sacitem',
            name='item_pequeno_valor',
            field=models.CharField(blank=True, choices=[('SIM', 'Sim'), ('NAO', 'Não')], max_length=3, null=True),
        ),
    ]
