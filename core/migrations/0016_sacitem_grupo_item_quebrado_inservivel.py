from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_remove_sacitem_uq_sacitem_item_rastreio"),
    ]

    operations = [
        migrations.AddField(
            model_name="sacitem",
            name="grupo",
            field=models.CharField(
                max_length=255,
                blank=True,
                default="",
                verbose_name="Grupo",
            ),
        ),
        migrations.AddField(
            model_name="sacitem",
            name="item_quebrado_inservivel",
            field=models.CharField(
                max_length=3,
                blank=True,
                default="",
                choices=[("SIM", "Sim"), ("NAO", "Não")],
                verbose_name="Item Quebrado Inservível",
            ),
        ),
    ]
