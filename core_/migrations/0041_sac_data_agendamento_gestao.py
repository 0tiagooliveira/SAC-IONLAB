# Generated for Gestão do SAC scheduling workflow.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0040_permitir_multiplos_fluxos_por_setor'),
    ]

    operations = [
        migrations.AddField(
            model_name='sac',
            name='data_agendamento_gestao',
            field=models.DateField(
                blank=True,
                null=True,
                db_index=True,
                help_text='Data futura usada pela Gestão do SAC para manter o SAC em Agendamentos até o dia indicado.',
            ),
        ),
    ]
