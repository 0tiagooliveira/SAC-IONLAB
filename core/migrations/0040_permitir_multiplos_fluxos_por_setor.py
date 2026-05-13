from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0039_blindar_fluxoacao_constraints'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='fluxoacaosetor',
            name='uq_fluxoacao_acao_setor_atual_ativo',
        ),
        migrations.RemoveConstraint(
            model_name='fluxoacaosetor',
            name='uq_fluxoacao_acao_generica_ativa',
        ),
    ]
