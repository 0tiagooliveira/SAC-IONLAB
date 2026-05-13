from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0046_sac_numero_unico_por_empresa"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_sacitem_item_rastreio'
                ) THEN
                    ALTER TABLE core_sacitem
                    DROP CONSTRAINT uq_sacitem_item_rastreio;
                END IF;
            END
            $$;

            DROP INDEX IF EXISTS uq_sacitem_item_rastreio;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
