from django.core.management.base import BaseCommand
from pathlib import Path
from datetime import datetime
import ast
import re

class Command(BaseCommand):
    help = 'Gera relatorio final de blindagem preventiva do SAC sem alterar regras, banco ou arquivos existentes.'

    def add_arguments(self, parser):
        parser.add_argument('--limite', type=int, default=200)

    def handle(self, *args, **options):
        base = Path.cwd()
        limite = options['limite']
        diag = base / 'diagnosticos'
        diag.mkdir(exist_ok=True)
        agora = datetime.now().strftime('%Y%m%d_%H%M%S')
        out = diag / f'RELATORIO_FINAL_BLINDAGEM_SAC_{agora}.txt'

        alvos = [
            base / 'core' / 'views.py',
            base / 'core' / 'forms.py',
            base / 'core' / 'models.py',
            base / 'core' / 'admin.py',
            base / 'config' / 'urls.py',
            base / 'config' / 'settings.py',
        ]
        templates_dir = base / 'core' / 'templates'
        if templates_dir.exists():
            alvos.extend(sorted(templates_dir.rglob('*.html')))
        services_dir = base / 'core' / 'services'
        if services_dir.exists():
            alvos.extend(sorted(services_dir.rglob('*.py')))
        modular_dir = base / 'core' / 'views_modular'
        if modular_dir.exists():
            alvos.extend(sorted(modular_dir.rglob('*.py')))

        linhas = []
        linhas.append('RELATORIO FINAL DE BLINDAGEM PREVENTIVA DO SAC')
        linhas.append('=' * 70)
        linhas.append(f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}')
        linhas.append('Modo: somente leitura. Nenhuma regra, banco ou template foi alterado por este comando.')
        linhas.append('')

        indicadores = {
            'except_generico': [],
            'prints_debug': [],
            'hardcoded_fluxo': [],
            'arquivos_muito_grandes': [],
            'todos_paths': [],
            'possiveis_templates_fragil': [],
        }
        termos_fluxo = ['Concluído','Concluido','Diretoria','Logística','Logistica','Assessoria','Comercial','Aguardando','Em Análise','Emissao','Emissão']

        for path in alvos:
            if not path.exists() or path.is_dir():
                continue
            try:
                texto = path.read_text(encoding='utf-8', errors='ignore')
            except Exception as exc:
                linhas.append(f'[ERRO LEITURA] {path.relative_to(base)}: {exc}')
                continue
            rel = str(path.relative_to(base))
            qtd_linhas = texto.count('\n') + 1
            indicadores['todos_paths'].append((rel, qtd_linhas))
            if qtd_linhas > 800:
                indicadores['arquivos_muito_grandes'].append((rel, qtd_linhas))
            for n, line in enumerate(texto.splitlines(), 1):
                low = line.lower()
                if re.search(r'except\s+exception\s*:', line, re.I) or re.search(r'except\s*:', line):
                    indicadores['except_generico'].append((rel, n, line.strip()[:180]))
                if 'print(' in line and path.suffix == '.py':
                    indicadores['prints_debug'].append((rel, n, line.strip()[:180]))
                if any(t.lower() in low for t in termos_fluxo) and path.suffix in ['.py','.html']:
                    if '=' in line or 'if ' in low or 'elif ' in low or '==' in line or ' in ' in low:
                        indicadores['hardcoded_fluxo'].append((rel, n, line.strip()[:180]))
                if path.suffix == '.html' and ('include' in low or 'url ' in low or 'static' in low):
                    if "'" in line or '"' in line:
                        indicadores['possiveis_templates_fragil'].append((rel, n, line.strip()[:180]))

        linhas.append('1) TAMANHO DOS PRINCIPAIS ARQUIVOS')
        linhas.append('-' * 70)
        for rel, qtd in sorted(indicadores['todos_paths'], key=lambda x: x[1], reverse=True)[:50]:
            linhas.append(f'{qtd:5d} linhas | {rel}')
        linhas.append('')

        linhas.append('2) ARQUIVOS GRANDES QUE DEVEM SER MEXIDOS COM MUITO CUIDADO')
        linhas.append('-' * 70)
        if indicadores['arquivos_muito_grandes']:
            for rel, qtd in indicadores['arquivos_muito_grandes']:
                linhas.append(f'ATENCAO: {rel} tem {qtd} linhas. Risco alto de regressao em alteracoes grandes.')
        else:
            linhas.append('Nenhum arquivo acima do limite de risco encontrado.')
        linhas.append('')

        secoes = [
            ('3) EXCEPT GENERICO / ERRO SILENCIOSO', 'except_generico'),
            ('4) PRINTS DE DEBUG EM PYTHON', 'prints_debug'),
            ('5) POSSIVEIS REGRAS / NOMES DE FLUXO FIXOS NO CODIGO', 'hardcoded_fluxo'),
            ('6) REFERENCIAS FRAGEIS EM TEMPLATES', 'possiveis_templates_fragil'),
        ]
        for titulo, chave in secoes:
            linhas.append(titulo)
            linhas.append('-' * 70)
            itens = indicadores[chave][:limite]
            if not itens:
                linhas.append('Nada relevante encontrado nesta categoria.')
            else:
                for rel, n, trecho in itens:
                    linhas.append(f'{rel}:{n} | {trecho}')
                if len(indicadores[chave]) > limite:
                    linhas.append(f'... mais {len(indicadores[chave]) - limite} ocorrencias omitidas. Aumente --limite se precisar.')
            linhas.append('')

        linhas.append('7) RECOMENDACAO TECNICA')
        linhas.append('-' * 70)
        linhas.append('Nao recomendo alterar regras agora. Recomendo iniciar uma etapa de correcoes cirurgicas nesta ordem:')
        linhas.append('1. remover erro silencioso em pontos criticos, mantendo a mesma resposta da tela;')
        linhas.append('2. padronizar logs em diagnosticos/logs_sac, sem afetar fluxo;')
        linhas.append('3. corrigir templates com referencias quebraveis, uma tela por vez;')
        linhas.append('4. isolar views por setor somente depois de testes de fumaça;')
        linhas.append('5. criar testes para regras existentes antes de qualquer refatoracao.')
        linhas.append('')
        linhas.append('CONCLUSAO: etapa de auditoria preventiva concluida. Proximo passo seguro: corrigir apenas pontos apontados nos relatorios, com patch pequeno e rollback.')

        out.write_text('\n'.join(linhas), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Relatorio final gerado em: {out}'))
