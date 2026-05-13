from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import AcaoEmEspera, Setor

try:
    from core.models import FluxoAcaoSetor
except Exception:  # pragma: no cover
    FluxoAcaoSetor = None


def normalizar(texto):
    import unicodedata, re
    texto = unicodedata.normalize('NFKD', str(texto or '')).encode('ascii', 'ignore').decode('ascii')
    texto = texto.replace('&', ' e ')
    texto = re.sub(r'[^a-zA-Z0-9]+', '_', texto.strip().lower())
    return re.sub(r'_+', '_', texto).strip('_').upper()


class Command(BaseCommand):
    help = 'Audita e corrige inconsistências de fluxo, ações em espera e setores destino.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--corrigir',
            action='store_true',
            help='Aplica correções automáticas seguras conhecidas.',
        )
        parser.add_argument(
            '--detalhado',
            action='store_true',
            help='Mostra relatório detalhado.',
        )

    def _setor_por_codigo_ou_nome(self, *valores):
        codigos = [normalizar(v) for v in valores if v]
        nomes = [str(v).strip() for v in valores if v]
        qs = Setor.objects.filter(ativo=True)
        for codigo in codigos:
            setor = qs.filter(codigo__iexact=codigo).first()
            if setor:
                return setor
        for nome in nomes:
            setor = qs.filter(nome__iexact=nome).first()
            if setor:
                return setor
        for nome in nomes:
            setor = qs.filter(nome__icontains=nome).first()
            if setor:
                return setor
        return None

    def _acao_por_codigo_ou_nome(self, *valores):
        codigos = [normalizar(v) for v in valores if v]
        nomes = [str(v).strip() for v in valores if v]
        qs = AcaoEmEspera.objects.all()
        for codigo in codigos:
            acao = qs.filter(codigo__iexact=codigo).first()
            if acao:
                return acao
        for nome in nomes:
            acao = qs.filter(nome__iexact=nome).first()
            if acao:
                return acao
        for nome in nomes:
            acao = qs.filter(nome__icontains=nome).first()
            if acao:
                return acao
        return None

    def _corrigir_acao_disponibilidade_cliente(self, aplicar=False):
        acao = self._acao_por_codigo_ou_nome(
            'AGUARDANDO_DISPONIBILIDADE_DO_CLIENTE',
            'Aguardando disponibilidade do Cliente',
            'Aguardando Disponibilidade do Cliente',
        )
        setor_sac = self._setor_por_codigo_ou_nome('SAC')
        if not acao:
            return ('acao_nao_encontrada', None, None)
        if not setor_sac:
            return ('setor_sac_nao_encontrado', acao, None)
        setor_atual = getattr(acao, 'setor_destino', None)
        if setor_atual and setor_atual.id == setor_sac.id:
            return ('ok', acao, setor_sac)
        if aplicar:
            acao.setor_destino = setor_sac
            acao.save(update_fields=['setor_destino'])
            return ('corrigido', acao, setor_sac)
        return ('divergente', acao, setor_sac)

    def _auditar_acoes_sem_setor(self):
        return AcaoEmEspera.objects.filter(ativo=True, setor_destino__isnull=True).order_by('nome')

    def _auditar_codigos_incoerentes(self):
        inconsistencias = []
        for acao in AcaoEmEspera.objects.all().order_by('nome'):
            esperado = normalizar(acao.nome)
            atual = normalizar(acao.codigo)
            if esperado and atual and esperado != atual:
                inconsistencias.append((acao, atual, esperado))
        return inconsistencias

    def _auditar_fluxos_setor_divergente(self):
        if FluxoAcaoSetor is None:
            return []
        divergencias = []
        qs = FluxoAcaoSetor.objects.filter(ativo=True).select_related(
            'acao_atual', 'setor_atual', 'proxima_acao', 'proximo_setor'
        )
        for fluxo in qs:
            proxima_acao = getattr(fluxo, 'proxima_acao', None)
            proximo_setor = getattr(fluxo, 'proximo_setor', None)
            setor_padrao = getattr(proxima_acao, 'setor_destino', None) if proxima_acao else None
            if proxima_acao and setor_padrao and proximo_setor and setor_padrao.id != proximo_setor.id:
                divergencias.append((fluxo, proxima_acao, setor_padrao, proximo_setor))
        return divergencias

    @transaction.atomic
    def handle(self, *args, **options):
        aplicar = bool(options.get('corrigir'))
        detalhado = bool(options.get('detalhado'))

        self.stdout.write('==========================================')
        self.stdout.write('BLINDAGEM / AUDITORIA DE FLUXO SAC')
        self.stdout.write('==========================================')
        self.stdout.write(f'Modo correção automática: {"SIM" if aplicar else "NÃO - somente auditoria"}')
        self.stdout.write('')

        status, acao, setor = self._corrigir_acao_disponibilidade_cliente(aplicar=aplicar)
        if status == 'ok':
            self.stdout.write(self.style.SUCCESS('OK: Ação "Aguardando disponibilidade do Cliente" já aponta para SAC.'))
        elif status == 'corrigido':
            self.stdout.write(self.style.SUCCESS('CORRIGIDO: Ação "Aguardando disponibilidade do Cliente" agora aponta para SAC.'))
        elif status == 'divergente':
            atual = getattr(getattr(acao, 'setor_destino', None), 'nome', 'SEM SETOR')
            self.stdout.write(self.style.WARNING(
                f'DIVERGÊNCIA: Ação "{acao.nome}" aponta para "{atual}", mas deveria apontar para "{setor.nome}". Rode com --corrigir para ajustar.'
            ))
        elif status == 'acao_nao_encontrada':
            self.stdout.write(self.style.ERROR('ERRO: Ação "Aguardando disponibilidade do Cliente" não encontrada.'))
        elif status == 'setor_sac_nao_encontrado':
            self.stdout.write(self.style.ERROR('ERRO: Setor SAC não encontrado.'))

        self.stdout.write('')
        sem_setor = list(self._auditar_acoes_sem_setor())
        self.stdout.write(f'Ações ativas sem setor destino: {len(sem_setor)}')
        if detalhado and sem_setor:
            for item in sem_setor[:100]:
                self.stdout.write(f' - ID {item.id}: {item.nome} | codigo={item.codigo}')
            if len(sem_setor) > 100:
                self.stdout.write(f' ... mais {len(sem_setor) - 100}')

        self.stdout.write('')
        codigos = self._auditar_codigos_incoerentes()
        self.stdout.write(f'Ações com código diferente do nome normalizado: {len(codigos)}')
        if detalhado and codigos:
            for acao, atual, esperado in codigos[:100]:
                self.stdout.write(f' - ID {acao.id}: {acao.nome} | codigo atual={atual} | esperado pelo nome={esperado}')
            if len(codigos) > 100:
                self.stdout.write(f' ... mais {len(codigos) - 100}')

        self.stdout.write('')
        divergencias = self._auditar_fluxos_setor_divergente()
        self.stdout.write(f'Fluxos ativos com próximo setor divergente do setor padrão da próxima ação: {len(divergencias)}')
        if detalhado and divergencias:
            for fluxo, proxima_acao, setor_padrao, proximo_setor in divergencias[:100]:
                atual = getattr(getattr(fluxo, 'acao_atual', None), 'nome', '-')
                setor_atual = getattr(getattr(fluxo, 'setor_atual', None), 'nome', '-')
                self.stdout.write(
                    f' - Fluxo ID {fluxo.id}: atual={atual} | setor_atual={setor_atual} | '
                    f'proxima_acao={proxima_acao.nome} | setor_padrao_acao={setor_padrao.nome} | proximo_setor_fluxo={proximo_setor.nome}'
                )
            if len(divergencias) > 100:
                self.stdout.write(f' ... mais {len(divergencias) - 100}')

        self.stdout.write('')
        if divergencias:
            self.stdout.write(self.style.WARNING(
                'ATENÇÃO: existem fluxos divergentes. Eles podem gerar erro "Setor de destino divergente do padrão da ação".'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('Nenhuma divergência crítica de fluxo encontrada.'))

        self.stdout.write('')
        self.stdout.write('Auditoria finalizada.')
