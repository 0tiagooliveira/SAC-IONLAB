from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_remove_sacitem_uq_sacitem_item_rastreio'),
    ]

    operations = [
        migrations.AddField(
            model_name='pecatabelapreco',
            name='grupo',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='pecatabelapreco',
            name='custo',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15),
        ),
    ]
