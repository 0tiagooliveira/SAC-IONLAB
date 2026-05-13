# Generated manually to merge the official SAC usage-time migration with the existing scheduling migration.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0040_tempo_uso_oficial_sac'),
        ('core', '0041_sac_data_agendamento_gestao'),
    ]

    operations = []
