from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_sac_endereco_usuario_contato'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='sacitem',
            constraint=models.UniqueConstraint(
                fields=['sac', 'item_nota_fiscal', 'tipo_rastreio', 'numero_rastreio'],
                name='uq_sacitem_por_sac',
            ),
        ),
    ]
