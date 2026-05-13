from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0045_importacao_legado_sac"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sac",
            name="numero",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddConstraint(
            model_name="sac",
            constraint=models.UniqueConstraint(
                fields=("empresa", "numero"),
                name="uq_sac_empresa_numero",
            ),
        ),
    ]
