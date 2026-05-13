from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0025_sacitem_item_pequeno_valor"),
    ]

    operations = [
        migrations.CreateModel(
            name="Vendedor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=50, unique=True)),
                ("nome", models.CharField(max_length=255, unique=True)),
                ("email", models.EmailField(blank=True, max_length=254, null=True)),
                ("ativo", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Vendedor",
                "verbose_name_plural": "Vendedores",
                "ordering": ["nome"],
            },
        ),
    ]
