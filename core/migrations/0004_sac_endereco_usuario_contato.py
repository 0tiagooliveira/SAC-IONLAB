from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_pacotes_1_e_2_base'),
    ]

    operations = [
        migrations.AddField(
            model_name='sac',
            name='endereco_usuario_contato',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
