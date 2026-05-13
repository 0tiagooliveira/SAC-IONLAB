# Generated manually by ChatGPT for SAC tempo de uso oficial

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0039_blindar_fluxoacao_constraints'),
    ]

    operations = [
        migrations.AddField(
            model_name='sac',
            name='data_emissao_nf',
            field=models.DateField(blank=True, db_index=True, help_text='Data de emissão da nota fiscal original usada como base do tempo de uso.', null=True),
        ),
        migrations.AddField(
            model_name='sac',
            name='numero_nf_revenda',
            field=models.CharField(blank=True, help_text='Número da nota fiscal de revenda informado manualmente na abertura do SAC.', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='sac',
            name='data_emissao_nf_revenda',
            field=models.DateField(blank=True, db_index=True, help_text='Data de emissão da nota fiscal de revenda; quando preenchida, prevalece no cálculo do tempo de uso.', null=True),
        ),
        migrations.AddField(
            model_name='sac',
            name='tempo_uso_dias',
            field=models.PositiveIntegerField(blank=True, db_index=True, help_text='Tempo de uso oficial do SAC, em dias, calculado da data base da NF até a data de abertura do SAC.', null=True),
        ),
    ]
