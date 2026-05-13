from django.db import migrations


SAFE_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_sacitem_item_rastreio'
    ) THEN
        ALTER TABLE core_sacitem DROP CONSTRAINT uq_sacitem_item_rastreio;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_sacitem_por_sac'
    ) THEN
        ALTER TABLE core_sacitem
        ADD CONSTRAINT uq_sacitem_por_sac
        UNIQUE (sac_id, item_nota_fiscal_id, tipo_rastreio, numero_rastreio);
    END IF;
END $$;
"""

REVERSE_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_sacitem_por_sac'
    ) THEN
        ALTER TABLE core_sacitem DROP CONSTRAINT uq_sacitem_por_sac;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_sacitem_item_rastreio'
    ) THEN
        ALTER TABLE core_sacitem
        ADD CONSTRAINT uq_sacitem_item_rastreio
        UNIQUE (item_nota_fiscal_id, tipo_rastreio, numero_rastreio);
    END IF;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_sacitem_unicidade_por_sac'),
    ]

    operations = [
        migrations.RunSQL(SAFE_SQL, REVERSE_SQL),
    ]
