from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Corrige automaticamente a estrutura do banco para clientes, notas, itens e SAC.'

    def handle(self, *args, **options):
        comandos = [
            """
            CREATE TABLE IF NOT EXISTS core_acaoemespera (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(255) UNIQUE,
                ativo BOOLEAN DEFAULT TRUE
            );
            """,
            """
            ALTER TABLE core_tipoocorrencia
            ADD COLUMN IF NOT EXISTS setor_id INTEGER;
            """,
            """
            ALTER TABLE core_tipoocorrencia
            ADD COLUMN IF NOT EXISTS acao_em_espera_id INTEGER;
            """,
            """
            ALTER TABLE core_sac
            ADD COLUMN IF NOT EXISTS acao_em_espera_id INTEGER;
            """,
            """
            INSERT INTO core_acaoemespera (nome, ativo)
            VALUES ('Analise do Ocorrido', TRUE)
            ON CONFLICT (nome) DO NOTHING;
            """,
            """
            INSERT INTO core_acaoemespera (nome, ativo)
            VALUES ('Atendimento Remoto', TRUE)
            ON CONFLICT (nome) DO NOTHING;
            """,
            """
            UPDATE core_tipoocorrencia
            SET acao_em_espera_id = (SELECT id FROM core_acaoemespera WHERE nome = 'Analise do Ocorrido')
            WHERE id IN (1,2,3,5,6,7,8,9,10) AND acao_em_espera_id IS NULL;
            """,
            """
            UPDATE core_tipoocorrencia
            SET acao_em_espera_id = (SELECT id FROM core_acaoemespera WHERE nome = 'Atendimento Remoto')
            WHERE id = 4 AND acao_em_espera_id IS NULL;
            """,
            """
            UPDATE core_tipoocorrencia
            SET setor_id = (SELECT id FROM core_setor WHERE nome ILIKE 'Comercial' LIMIT 1)
            WHERE id IN (3,6,9) AND setor_id IS NULL;
            """,
            """
            UPDATE core_tipoocorrencia
            SET setor_id = (SELECT id FROM core_setor WHERE nome ILIKE 'Logistica' LIMIT 1)
            WHERE id IN (1,2,5,10) AND setor_id IS NULL;
            """,
            """
            UPDATE core_tipoocorrencia
            SET setor_id = (SELECT id FROM core_setor WHERE nome ILIKE 'Licitação' LIMIT 1)
            WHERE id IN (7,8) AND setor_id IS NULL;
            """,
            """
            UPDATE core_tipoocorrencia
            SET setor_id = (SELECT id FROM core_setor WHERE nome ILIKE 'Assessoria Cientifica' LIMIT 1)
            WHERE id = 4 AND setor_id IS NULL;
            """
        ]

        self.stdout.write(self.style.WARNING('Iniciando correção automática do banco...'))

        with connection.cursor() as cursor:
            for i, sql in enumerate(comandos, start=1):
                try:
                    cursor.execute(sql)
                    self.stdout.write(self.style.SUCCESS(f'[{i}] OK'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'[{i}] ERRO: {e}'))

        self.stdout.write(self.style.SUCCESS('Correção automática concluída.'))