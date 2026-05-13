from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_endurecer_codigo_acaoemespera'),
    ]

    operations = [
        migrations.AddField(
            model_name='sachistorico',
            name='arquivo',
            field=models.FileField(blank=True, null=True, upload_to='sac_historico/'),
        ),
    ]
