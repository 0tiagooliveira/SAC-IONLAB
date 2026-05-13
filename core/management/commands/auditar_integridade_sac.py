from __future__ import annotations

import ast
from collections import Counter, defaultdict
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Count, Q
from django.template import engines

from core.models import (
    AcaoEmEspera,
    Cliente,
    Empresa,
    FluxoAcaoSetor,
    NotaFiscal,
    SAC,
    Setor,
    StatusSAC,
)


class Command(BaseCommand):
    help = (
        'Auditoria preventiva do SAC. Não altera dados, não cria migrations e não muda regras. '
        'Serve para localizar riscos antes de novos patches.'
    )

    TERMOS_SENSIVEIS = [
        'Concluído',
        'Concluido',
        'Diretoria',
        'Logística',
        'Logistica',
        'Assessoria',
        'Comercial',
        'Aguardando',
        'Em Análise',
        'Em Analise',
    ]

    PASTAS_IGNORAR = {
        '.git',
        '__pycache__',
        'venv',
        'env',
        '.venv',
        'media',
        'staticfiles',
        'backups',
        'backup',
        'logs',
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--detalhado',
            action='store_true',
            help='Mostra amostras de arquivos/linhas para facilitar correção cirúrgica.',
        )
        parser.add_argument(
            '--limite',
            type=int,
            default=25,
            help='Limite de itens exibidos por seção.',
        )
        parser.add_argument(
            '--somente-codigo',
            action='store_true',
            help='Roda apenas auditorias de arquivos/código, sem consultar o banco.',
        )

    def handle(self, *args, **options):
        self.base_dir = Path.cwd()
        self.detalhado = bool(options['detalhado'])
        self.limite = int(options['limite'])
        self.alertas = 0
        self.erros = 0

        self._titulo('AUDITORIA PREVENTIVA DO SAC')
        self._info('Modo seguro: nenhuma alteração será feita no sistema ou no banco.')
        self._info(f'Projeto analisado: {self.base_dir}')

        self._auditar_arquivos_duplicados_e_backups()
        self._auditar_tamanho_arquivos_python()
        self._auditar_imports_python()
        self._auditar_except_generico()
        self._auditar_textos_fixos_em_regras()
        self._auditar_templates_referenciados()
        self._auditar_urls_e_views()

        if not options['somente_codigo']:
            self._auditar_banco_e_fluxos()

        self._resumo_final()

    # ------------------------------------------------------------------
    # Saída
    # ------------------------------------------------------------------
    def _titulo(self, texto):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(f'==== {texto} ===='))

    def _ok(self, texto):
        self.stdout.write(self.style.SUCCESS(f'OK - {texto}'))

    def _info(self, texto):
        self.stdout.write(f'- {texto}')

    def _warn(self, texto):
        self.alertas += 1
        self.stdout.write(self.style.WARNING(f'ATENÇÃO - {texto}'))

    def _erro(self, texto):
        self.erros += 1
        self.stdout.write(self.style.ERROR(f'ERRO - {texto}'))

    def _iter_arquivos(self, sufixos=None):
        for caminho in self.base_dir.rglob('*'):
            if not caminho.is_file():
                continue
            partes = set(caminho.relative_to(self.base_dir).parts)
            if partes & self.PASTAS_IGNORAR:
                continue
            if sufixos and caminho.suffix.lower() not in sufixos:
                continue
            yield caminho

    # ------------------------------------------------------------------
    # Auditoria de código/estrutura
    # ------------------------------------------------------------------
    def _auditar_arquivos_duplicados_e_backups(self):
        self._titulo('1. ESTRUTURA E BACKUPS DENTRO DO PROJETO')
        suspeitos = []
        padroes = ('.bkp', '.backup', '_backup', 'backup_', 'bkp_', '.old', '.zip')
        for caminho in self._iter_arquivos():
            nome = caminho.name.lower()
            rel = str(caminho.relative_to(self.base_dir))
            if any(p in nome or p in rel.lower() for p in padroes):
                suspeitos.append(rel)

        if suspeitos:
            self._warn(f'{len(suspeitos)} arquivo(s) de backup/pacote dentro do projeto. Isso pode confundir imports, deploy e comparação de versões.')
            for rel in suspeitos[: self.limite]:
                self._info(rel)
        else:
            self._ok('não encontrei backups/pacotes soltos dentro das pastas analisadas.')

    def _auditar_tamanho_arquivos_python(self):
        self._titulo('2. ARQUIVOS PYTHON MUITO GRANDES')
        grandes = []
        for caminho in self._iter_arquivos({'.py'}):
            try:
                linhas = caminho.read_text(encoding='utf-8', errors='ignore').count('\n') + 1
            except OSError:
                continue
            if linhas >= 800:
                grandes.append((linhas, str(caminho.relative_to(self.base_dir))))
        grandes.sort(reverse=True)
        if grandes:
            self._warn('arquivos grandes aumentam risco de regressão em correções futuras.')
            for linhas, rel in grandes[: self.limite]:
                self._info(f'{rel}: {linhas} linhas')
        else:
            self._ok('nenhum arquivo Python acima do limite de risco definido.')

    def _auditar_imports_python(self):
        self._titulo('3. SINTAXE E IMPORTS PYTHON')
        problemas = []
        for caminho in self._iter_arquivos({'.py'}):
            rel = str(caminho.relative_to(self.base_dir))
            try:
                ast.parse(caminho.read_text(encoding='utf-8', errors='ignore'))
            except SyntaxError as exc:
                problemas.append((rel, f'linha {exc.lineno}: {exc.msg}'))
            except Exception as exc:  # auditoria defensiva
                problemas.append((rel, str(exc)))
        if problemas:
            self._erro(f'{len(problemas)} arquivo(s) com problema de sintaxe/leitura.')
            for rel, msg in problemas[: self.limite]:
                self._info(f'{rel} -> {msg}')
        else:
            self._ok('todos os arquivos Python analisados passaram no parse de sintaxe.')

    def _auditar_except_generico(self):
        self._titulo('4. EXCEPT GENÉRICO / ERRO SILENCIOSO')
        achados = []
        for caminho in self._iter_arquivos({'.py'}):
            rel = str(caminho.relative_to(self.base_dir))
            texto = caminho.read_text(encoding='utf-8', errors='ignore').splitlines()
            for i, linha in enumerate(texto, start=1):
                l = linha.strip()
                if l.startswith('except Exception') or l == 'except:':
                    achados.append((rel, i, l))
        if achados:
            self._warn(f'{len(achados)} ponto(s) com except genérico. Corrigir aos poucos com log/diagnóstico para não esconder falhas.')
            if self.detalhado:
                for rel, i, linha in achados[: self.limite]:
                    self._info(f'{rel}:{i} -> {linha}')
        else:
            self._ok('não encontrei except genérico nos arquivos analisados.')

    def _auditar_textos_fixos_em_regras(self):
        self._titulo('5. TEXTOS FIXOS SENSÍVEIS EM CÓDIGO/TEMPLATES')
        contagem = Counter()
        exemplos = defaultdict(list)
        for caminho in self._iter_arquivos({'.py', '.html', '.js'}):
            rel = str(caminho.relative_to(self.base_dir))
            if 'migrations' in caminho.parts:
                continue
            linhas = caminho.read_text(encoding='utf-8', errors='ignore').splitlines()
            for i, linha in enumerate(linhas, start=1):
                for termo in self.TERMOS_SENSIVEIS:
                    if termo in linha:
                        contagem[termo] += 1
                        if len(exemplos[termo]) < 3:
                            exemplos[termo].append((rel, i))
        if contagem:
            self._warn('há textos de status/setor/ação espalhados. Não é erro imediato, mas aumenta risco se nomes mudarem no banco.')
            for termo, total in contagem.most_common():
                self._info(f'{termo}: {total} ocorrência(s)')
                if self.detalhado:
                    for rel, i in exemplos[termo]:
                        self._info(f'  exemplo: {rel}:{i}')
        else:
            self._ok('não encontrei termos sensíveis fixos nos arquivos analisados.')

    def _auditar_templates_referenciados(self):
        self._titulo('6. TEMPLATES REFERENCIADOS')
        faltantes = []
        engine = engines['django']
        for caminho in self._iter_arquivos({'.py'}):
            rel = str(caminho.relative_to(self.base_dir))
            texto = caminho.read_text(encoding='utf-8', errors='ignore')
            for template in sorted(set(self._extrair_templates_de_texto(texto))):
                try:
                    engine.get_template(template)
                except Exception as exc:
                    faltantes.append((rel, template, str(exc).split('\n')[0]))
        if faltantes:
            self._erro(f'{len(faltantes)} referência(s) de template não localizada(s).')
            for rel, template, msg in faltantes[: self.limite]:
                self._info(f'{rel} -> {template} ({msg})')
        else:
            self._ok('templates referenciados em render() foram localizados.')

    @staticmethod
    def _extrair_templates_de_texto(texto):
        templates = []
        marcador = "render("
        for parte in texto.split(marcador)[1:]:
            pedaco = parte[:300]
            aspas = ["'", '"']
            encontrados = []
            for asp in aspas:
                idx = pedaco.find(asp)
                if idx >= 0:
                    fim = pedaco.find(asp, idx + 1)
                    if fim > idx:
                        encontrados.append(pedaco[idx + 1 : fim])
            for item in encontrados:
                if item.endswith('.html') and '/' in item:
                    templates.append(item)
        return templates

    def _auditar_urls_e_views(self):
        self._titulo('7. URLS E VIEWS')
        urls_path = self.base_dir / 'config' / 'urls.py'
        if not urls_path.exists():
            self._erro('config/urls.py não encontrado.')
            return
        texto = urls_path.read_text(encoding='utf-8', errors='ignore')
        usa_core_views = 'core.views' in texto
        usa_modular = 'views_modular' in texto or 'urls_modular' in texto
        if usa_core_views and usa_modular:
            self._warn('config/urls.py mistura core.views com views/urls modulares. Isso exige cuidado para não duplicar lógica entre telas.')
        else:
            self._ok('não identifiquei mistura evidente entre views monolíticas e modulares no urls.py.')

    # ------------------------------------------------------------------
    # Auditoria de banco/fluxo
    # ------------------------------------------------------------------
    def _auditar_banco_e_fluxos(self):
        self._titulo('8. BANCO, CADASTROS E FLUXOS')
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
        except Exception as exc:
            self._erro(f'não foi possível conectar ao banco atual: {exc}')
            self._info('Rode novamente com --somente-codigo se quiser auditar apenas arquivos.')
            return

        self._contar_modelos_principais()
        self._auditar_codigos_obrigatorios()
        self._auditar_fluxo_duplicado_exato()
        self._auditar_sacs_sem_fluxo()
        self._auditar_concluidos_com_pendencia()
        self._auditar_dados_sac_nf_tempo_uso()
        self._auditar_clientes_codigo_suspeito()

    def _contar_modelos_principais(self):
        modelos = [Empresa, Setor, StatusSAC, AcaoEmEspera, FluxoAcaoSetor, Cliente, NotaFiscal, SAC]
        for modelo in modelos:
            try:
                self._info(f'{modelo.__name__}: {modelo.objects.count()} registro(s)')
            except Exception as exc:
                self._warn(f'não consegui contar {modelo.__name__}: {exc}')

    def _auditar_codigos_obrigatorios(self):
        problemas = []
        for modelo in [Setor, StatusSAC, AcaoEmEspera]:
            qs = modelo.objects.filter(Q(codigo__isnull=True) | Q(codigo=''))
            total = qs.count()
            if total:
                problemas.append((modelo.__name__, total))
        if problemas:
            for nome, total in problemas:
                self._erro(f'{nome} com código vazio/nulo: {total}')
        else:
            self._ok('Setor, StatusSAC e AcaoEmEspera possuem código preenchido.')

    def _auditar_fluxo_duplicado_exato(self):
        duplicados = (
            FluxoAcaoSetor.objects.filter(ativo=True)
            .values('acao_atual_id', 'setor_atual_id', 'proxima_acao_id', 'proximo_setor_id', 'status_destino_id')
            .annotate(total=Count('id'))
            .filter(total__gt=1)
        )
        if duplicados.exists():
            self._erro('existem fluxos ativos exatamente duplicados.')
            for item in duplicados[: self.limite]:
                self._info(str(item))
        else:
            self._ok('não há fluxo ativo exatamente duplicado.')

    def _auditar_sacs_sem_fluxo(self):
        faltantes = []
        qs = SAC.objects.select_related('acao_em_espera', 'setor_atual', 'status_atual').filter(acao_em_espera__isnull=False)
        for sac in qs[:1000]:
            setor = sac.setor_atual
            acao = sac.acao_em_espera
            existe = FluxoAcaoSetor.objects.filter(ativo=True, acao_atual=acao, setor_atual=setor).exists()
            existe_generico = FluxoAcaoSetor.objects.filter(ativo=True, acao_atual=acao, setor_atual__isnull=True).exists()
            if not existe and not existe_generico:
                faltantes.append(sac)
        if faltantes:
            self._warn(f'{len(faltantes)} SAC(s) com ação/setor atual sem regra específica nem genérica de fluxo.')
            for sac in faltantes[: self.limite]:
                self._info(
                    f'SAC {sac.numero or sac.id} | status={getattr(sac.status_atual, "nome", None)} | '
                    f'ação={getattr(sac.acao_em_espera, "nome", None)} | setor={getattr(sac.setor_atual, "nome", None)}'
                )
        else:
            self._ok('SACs atuais possuem fluxo específico ou genérico para a ação/setor atual.')

    def _auditar_concluidos_com_pendencia(self):
        concluidos = SAC.objects.filter(
            Q(status_atual__codigo__icontains='CONCL') | Q(status_atual__nome__icontains='Concl')
        ).filter(Q(acao_em_espera__isnull=False) | Q(setor_atual__isnull=False))
        total = concluidos.count()
        if total:
            self._warn(f'{total} SAC(s) concluído(s) ainda possuem ação em espera e/ou setor atual. Pode ser regra válida, mas merece conferência.')
            for sac in concluidos.select_related('acao_em_espera', 'setor_atual')[: self.limite]:
                self._info(
                    f'SAC {sac.numero or sac.id} | ação={getattr(sac.acao_em_espera, "nome", None)} | setor={getattr(sac.setor_atual, "nome", None)}'
                )
        else:
            self._ok('não encontrei SAC concluído com pendência ativa evidente.')

    def _auditar_dados_sac_nf_tempo_uso(self):
        qs = SAC.objects.filter(
            Q(data_emissao_nf__isnull=False) | Q(data_emissao_nf_revenda__isnull=False)
        ).filter(tempo_uso_dias__isnull=True)
        total = qs.count()
        if total:
            self._warn(f'{total} SAC(s) possuem data de NF/revenda mas tempo_uso_dias está vazio.')
            for sac in qs[: self.limite]:
                self._info(f'SAC {sac.numero or sac.id}')
        else:
            self._ok('tempo de uso preenchido quando há data de NF/revenda registrada no SAC.')

    def _auditar_clientes_codigo_suspeito(self):
        suspeitos = Cliente.objects.filter(codigo_interno__endswith='.0').count()
        if suspeitos:
            self._warn(f'{suspeitos} cliente(s) com código interno terminando em .0. Isso costuma vir de importação Excel e pode duplicar cliente.')
        else:
            self._ok('não encontrei clientes com código interno terminando em .0.')

    def _resumo_final(self):
        self._titulo('RESUMO')
        if self.erros:
            self._erro(f'auditoria terminou com {self.erros} erro(s) crítico(s) e {self.alertas} alerta(s).')
            self._info('Prioridade: corrigir erros críticos antes de novas alterações de regra/tela.')
        elif self.alertas:
            self._warn(f'auditoria terminou com {self.alertas} alerta(s), sem erro crítico.')
            self._info('Próximo passo seguro: corrigir alertas em patches pequenos, com backup e testes.')
        else:
            self._ok('auditoria não encontrou riscos relevantes nos pontos verificados.')
