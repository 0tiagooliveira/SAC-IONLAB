from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0037_sachistorico_arquivo_fix'),
    ]

    operations = [
        migrations.AddField(
            model_name='tecnicoexterno',
            name='arquivo',
            field=models.FileField(blank=True, null=True, upload_to='sac_historico/'),
        ),
    ]
