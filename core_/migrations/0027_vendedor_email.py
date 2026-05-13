from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0026_vendedor"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vendedor",
            name="email",
            field=models.EmailField(
                blank=True,
                null=True,
                max_length=254,
                verbose_name="E-mail",
            ),
        ),
    ]
