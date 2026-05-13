from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_fix_sacitem_constraint'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uq_sacitem_item_rastreio'
                ) THEN
                    ALTER TABLE core_sacitem DROP CONSTRAINT uq_sacitem_item_rastreio;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'core_sacitem_item_nota_fiscal_id_tipo_7aa16147_uniq'
                ) THEN
                    ALTER TABLE core_sacitem DROP CONSTRAINT core_sacitem_item_nota_fiscal_id_tipo_7aa16147_uniq;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE indexname = 'uq_sacitem_item_rastreio'
                ) THEN
                    DROP INDEX IF EXISTS uq_sacitem_item_rastreio;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE indexname = 'core_sacitem_item_nota_fiscal_id_tipo_7aa16147_uniq'
                ) THEN
                    DROP INDEX IF EXISTS core_sacitem_item_nota_fiscal_id_tipo_7aa16147_uniq;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uq_sacitem_por_sac'
                ) THEN
                    ALTER TABLE core_sacitem
                    ADD CONSTRAINT uq_sacitem_por_sac
                    UNIQUE (sac_id, item_nota_fiscal_id, tipo_rastreio, numero_rastreio);
                END IF;
            END
            $$;
            """,
            reverse_sql="""
            ALTER TABLE core_sacitem DROP CONSTRAINT IF EXISTS uq_sacitem_por_sac;
            """,
        ),
    ]
