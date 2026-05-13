from django.db import models
import re
import unicodedata
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


class Empresa(models.Model):
    codigo = models.CharField(max_length=50, blank=True, null=True)
    razao_social = models.CharField(max_length=255)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['razao_social']

    @property
    def nome(self):
        return self.razao_social

    @nome.setter
    def nome(self, valor):
        self.razao_social = valor

    def __str__(self):
        return self.razao_social


class Setor(models.Model):

    nome = models.CharField(max_length=100)
    codigo = models.CharField(max_length=100,unique=True)
    ativo = models.BooleanField(default=True)

    @staticmethod
    def _normalizar_codigo(valor):
        texto = unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode('ascii')
        texto = texto.replace('&', ' e ')
        texto = re.sub(r'[^a-zA-Z0-9]+', '_', texto.strip().lower())
        return re.sub(r'_+', '_', texto).strip('_').upper()

    @property
    def codigo_resolvido(self):
        return self.codigo or self._normalizar_codigo(self.nome)

    def save(self, *args, **kwargs):
        self.codigo = self._normalizar_codigo(self.codigo or self.nome)
        if not self.codigo:
            raise ValidationError({'codigo': 'Código é obrigatório para Setor.'})
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome

class AcaoEmEspera(models.Model):
    nome = models.CharField(max_length=255, unique=True)
    codigo = models.CharField(max_length=100, unique=True)
    setor_destino = models.ForeignKey(
        Setor,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='acoes_em_espera_destino',
        help_text='Setor que deverá assumir o SAC após esta ação em espera. Deixe em branco quando o sistema precisar permitir seleção manual do setor.'
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Ação em Espera'
        verbose_name_plural = 'Ações em Espera'
        ordering = ['nome']

    @staticmethod
    def _normalizar_codigo(valor):
        texto = unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode('ascii')
        texto = texto.replace('&', ' e ')
        texto = re.sub(r'[^a-zA-Z0-9]+', '_', texto.strip().lower())
        return re.sub(r'_+', '_', texto).strip('_').upper()

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self._normalizar_codigo(self.nome)
        else:
            self.codigo = self._normalizar_codigo(self.codigo)
        if not self.codigo:
            raise ValidationError({'codigo': 'Código é obrigatório para Ação em Espera.'})
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class UsuarioSistema(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='usuario_sistema'
    )
    nome_completo = models.CharField(max_length=255)
    ativo = models.BooleanField(default=True)
    setor = models.ForeignKey(Setor, on_delete=models.PROTECT, blank=True, null=True)

    class Meta:
        ordering = ['nome_completo']

    def __str__(self):
        return self.nome_completo


class StatusSAC(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=100)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nome']

    @staticmethod
    def _normalizar_codigo(valor):
        texto = unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode('ascii')
        texto = texto.replace('&', ' e ')
        texto = re.sub(r'[^a-zA-Z0-9]+', '_', texto.strip().lower())
        return re.sub(r'_+', '_', texto).strip('_').upper()

    def save(self, *args, **kwargs):
        self.codigo = self._normalizar_codigo(self.codigo or self.nome)
        if not self.codigo:
            raise ValidationError({'codigo': 'Código é obrigatório para Status do SAC.'})
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class TipoOcorrencia(models.Model):
    codigo = models.CharField(max_length=50, blank=True, null=True)
    nome = models.CharField(max_length=100)
    setor = models.ForeignKey(Setor, on_delete=models.PROTECT, blank=True, null=True)
    acao_em_espera = models.ForeignKey(
        AcaoEmEspera,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='tipos_ocorrencia'
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Tipo de Ocorrência'
        verbose_name_plural = 'Tipos de Ocorrência'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Cliente(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='clientes')
    codigo_interno = models.CharField(max_length=50)
    nome = models.CharField(max_length=255, blank=True, null=True)
    razao_social = models.CharField(max_length=255, blank=True, null=True)
    uf = models.CharField(max_length=2, blank=True, null=True)
    classificacao_financeira = models.CharField(max_length=100, blank=True, null=True)
    ultima_entrega_mpm = models.CharField(max_length=100, blank=True, null=True)

    contato_nome = models.CharField(max_length=255, blank=True, null=True)
    email_1 = models.EmailField(blank=True, null=True)
    email_2 = models.EmailField(blank=True, null=True)
    telefone = models.CharField(max_length=30, blank=True, null=True)
    whatsapp = models.CharField(max_length=30, blank=True, null=True)

    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['razao_social', 'nome']
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'codigo_interno'],
                name='uq_cliente_empresa_codigo_interno'
            )
        ]

    def save(self, *args, **kwargs):
        if not self.razao_social and self.nome:
            self.razao_social = self.nome
        if not self.nome and self.razao_social:
            self.nome = self.razao_social
        if not self.nome and not self.razao_social:
            self.nome = 'CLIENTE NÃO INFORMADO'
            self.razao_social = 'CLIENTE NÃO INFORMADO'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.codigo_interno} - {self.razao_social or self.nome or ""}'


class ClienteContato(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='contatos_salvos')
    nome_contato = models.CharField(max_length=255, blank=True, null=True)
    whatsapp = models.CharField(max_length=30, blank=True, null=True)
    telefone = models.CharField(max_length=30, blank=True, null=True)
    email_1 = models.EmailField(blank=True, null=True)
    email_2 = models.EmailField(blank=True, null=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome_contato', 'id']

    def __str__(self):
        return self.nome_contato or f'Contato {self.id}'


class Vendedor(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=255, unique=True)
    email = models.EmailField(blank=True, null=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Vendedor'
        verbose_name_plural = 'Vendedores'

    def __str__(self):
        return f'{self.codigo} - {self.nome}'


class NotaFiscal(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='notas_fiscais')
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='notas_fiscais')

    id_nf_sistema = models.CharField(max_length=50, blank=True, null=True)
    serie_nf = models.CharField(max_length=20, blank=True, null=True)
    numero = models.CharField(max_length=50, blank=True, null=True)
    numero_nf = models.CharField(max_length=50, blank=True, null=True)
    data_emissao = models.DateField(blank=True, null=True)

    vendedor_codigo = models.CharField(max_length=50, blank=True, null=True)
    vendedor_nome = models.CharField(max_length=255, blank=True, null=True)

    transportadora_codigo = models.CharField(max_length=50, blank=True, null=True)
    transportadora_nome = models.CharField(max_length=255, blank=True, null=True)

    cfop = models.CharField(max_length=20, blank=True, null=True)
    cfop_descricao = models.CharField(max_length=255, blank=True, null=True)

    frete_ctr = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    frete_nf = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    desconto = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    seguro = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    outras_despesas = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    difal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fcp = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    iss = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    lucro_reais = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    lucro_percentual = models.DecimalField(max_digits=15, decimal_places=4, default=0)

    class Meta:
        ordering = ['-data_emissao', '-numero_nf', '-numero']
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'numero_nf'],
                name='uq_notafiscal_empresa_numero'
            )
        ]

    def save(self, *args, **kwargs):
        if not self.numero_nf and self.numero:
            self.numero_nf = self.numero
        if not self.numero and self.numero_nf:
            self.numero = self.numero_nf
        super().save(*args, **kwargs)

    def __str__(self):
        numero = self.numero_nf or self.numero or ""
        empresa_nome = ""

        if getattr(self, "empresa_id", None) and self.empresa:
            empresa_nome = self.empresa.razao_social or ""

        if empresa_nome:
            return f"NF {numero} - {empresa_nome}"

        return f"NF {numero}"


class ItemNotaFiscal(models.Model):
    nota_fiscal = models.ForeignKey(NotaFiscal, on_delete=models.CASCADE, related_name='itens')

    id_prnf = models.CharField(max_length=50, blank=True, null=True)

    item = models.CharField(max_length=255, blank=True, null=True)
    codigo_produto = models.CharField(max_length=100, blank=True, null=True)
    descricao_item = models.CharField(max_length=255, blank=True, null=True)
    quantidade = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    valor_total_item = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    custo_n = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    v_icms = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    v_pis = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    v_cofins = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    v_irpj = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    v_csll = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    v_est_ircs_ou_simples = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    v_comissao = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    v_ipi = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    v_icmsst = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    v_pisst = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    v_cofinsst = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fcp_st = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    agrp = models.CharField(max_length=100, blank=True, null=True)
    faixa_desconto = models.CharField(max_length=100, blank=True, null=True)
    al_cred_simp = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    al_csll = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    al_irpj = models.DecimalField(max_digits=15, decimal_places=4, default=0)

    class Meta:
        ordering = ['descricao_item', 'item', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['nota_fiscal', 'codigo_produto', 'descricao_item'],
                name='uq_item_nf_codigo_descricao'
            )
        ]

    def save(self, *args, **kwargs):
        if not self.descricao_item and self.item:
            self.descricao_item = self.item
        if not self.item and self.descricao_item:
            self.item = self.descricao_item
        super().save(*args, **kwargs)

    def __str__(self):
        return self.descricao_item or self.item or f'Item {self.id}'


class RastreioNotaItem(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='rastreios_importados')
    numero_nf = models.CharField(max_length=50)
    codigo_produto = models.CharField(max_length=100, blank=True, null=True)
    descricao_produto = models.CharField(max_length=255, blank=True, null=True)
    quantidade = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    serial_lote = models.CharField(max_length=255, blank=True, null=True)
    saidas_raw = models.TextField(blank=True, null=True)
    tipo = models.CharField(max_length=50, blank=True, null=True)
    data_doc = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ['numero_nf', 'codigo_produto', 'serial_lote']
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'numero_nf', 'codigo_produto', 'serial_lote'],
                name='uq_rastreio_nf_item_serial'
            )
        ]

    def __str__(self):
        return f'{self.numero_nf} - {self.codigo_produto or ""} - {self.serial_lote or ""}'


class TratativaProblema(models.Model):
    nome = models.CharField(max_length=255, unique=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Tratativa do Problema'
        verbose_name_plural = 'Tratativas do Problema'

    def __str__(self):
        return self.nome


class TipoProblema(models.Model):
    nome = models.CharField(max_length=255, unique=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Tipo de Problema'
        verbose_name_plural = 'Tipos de Problema'

    def __str__(self):
        return self.nome


class TecnicoExterno(models.Model):
    nome = models.CharField(max_length=255)
    telefone = models.CharField(max_length=30, blank=True, null=True)
    whatsapp = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    cidade = models.CharField(max_length=255, blank=True, null=True)
    estado = models.CharField(max_length=2, blank=True, null=True)
    observacao = models.TextField(blank=True, null=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Técnico Externo'
        verbose_name_plural = 'Técnicos Externos'

    def __str__(self):
        return self.nome


class PecaTabelaPreco(models.Model):
    referencia = models.CharField(max_length=100, unique=True)
    descricao = models.CharField(max_length=255)
    valor_unitario = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    grupo = models.CharField(max_length=255, blank=True, null=True)
    custo = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['descricao', 'referencia']
        verbose_name = 'Peça - Tabela de Preço'
        verbose_name_plural = 'Tabela de Preços de Peças'

    def __str__(self):
        return f'{self.referencia} - {self.descricao}'


class SAC(models.Model):
    numero = models.CharField(max_length=20, unique=True, blank=True)
    ano = models.PositiveIntegerField(default=0)
    sequencia_ano = models.PositiveIntegerField(default=0)

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, blank=True, null=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, blank=True, null=True)
    nota_fiscal = models.ForeignKey(NotaFiscal, on_delete=models.PROTECT, blank=True, null=True)

    contato_nome = models.CharField(max_length=255, blank=True, null=True)
    telefone_1 = models.CharField(max_length=30, blank=True, null=True)
    telefone_2 = models.CharField(max_length=30, blank=True, null=True)

    email_1 = models.EmailField(blank=True, null=True)
    email_2 = models.EmailField(blank=True, null=True)

    nome_usuario_contato = models.CharField(max_length=255, blank=True, null=True)
    empresa_usuario_contato = models.CharField(max_length=255, blank=True, null=True)
    telefone_usuario_contato = models.CharField(max_length=30, blank=True, null=True)
    whatsapp_usuario_contato = models.CharField(max_length=30, blank=True, null=True)
    email_usuario_contato = models.EmailField(blank=True, null=True)
    endereco_usuario_contato = models.CharField(max_length=255, blank=True, null=True)
    cidade_usuario_contato = models.CharField(max_length=255, blank=True, null=True)
    estado_usuario_contato = models.CharField(max_length=2, blank=True, null=True)

    titulo = models.CharField(max_length=255, blank=True, null=True)
    descricao = models.TextField(blank=True, null=True)

    status_inicial = models.CharField(max_length=30, default='Aberto')
    status_atual = models.ForeignKey(
        StatusSAC,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='sacs_status_atual'
    )
    acao_em_espera = models.ForeignKey(
        AcaoEmEspera,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='sacs'
    )

    setor_responsavel = models.ForeignKey(
        Setor,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='sacs_setor_abertura'
    )
    setor_atual = models.ForeignKey(
        Setor,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='sacs_setor_atual'
    )
    usuario_abertura = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True)

    concluido_em = models.DateTimeField(blank=True, null=True)
    cancelado_em = models.DateTimeField(blank=True, null=True)
    motivo_cancelamento = models.TextField(blank=True, null=True)
    email_automatico_habilitado = models.BooleanField(default=True)
    data_agendamento_gestao = models.DateField(
        blank=True,
        null=True,
        db_index=True,
        help_text='Data futura usada pela Gestão do SAC para manter o SAC em Agendamentos até o dia indicado.',
    )

    data_emissao_nf = models.DateField(
        blank=True,
        null=True,
        db_index=True,
        help_text='Data de emissão da nota fiscal original usada como base do tempo de uso.',
    )
    numero_nf_revenda = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Número da nota fiscal de revenda informado manualmente na abertura do SAC.',
    )
    data_emissao_nf_revenda = models.DateField(
        blank=True,
        null=True,
        db_index=True,
        help_text='Data de emissão da nota fiscal de revenda; quando preenchida, prevalece no cálculo do tempo de uso.',
    )
    tempo_uso_dias = models.PositiveIntegerField(
        blank=True,
        null=True,
        db_index=True,
        help_text='Tempo de uso oficial do SAC, em dias, calculado da data base da NF até a data de abertura do SAC.',
    )

    data_abertura = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_abertura', '-id']

    def __str__(self):
        return self.numero or f'SAC {self.id}'

    @property
    def status_atual_nome(self):
        if self.status_atual:
            return self.status_atual.nome
        return self.status_inicial

    @property
    def tempo_uso_formatado(self):
        dias = self.tempo_uso_dias
        if dias is None:
            return 'Não calculado'
        try:
            dias = int(dias)
        except (TypeError, ValueError):
            return 'Não calculado'
        meses = dias // 30
        resto = dias % 30
        if meses <= 0:
            return f'{resto} dia' if resto == 1 else f'{resto} dias'
        texto_meses = f'{meses} mês' if meses == 1 else f'{meses} meses'
        texto_dias = f'{resto} dia' if resto == 1 else f'{resto} dias'
        return f'{texto_meses} e {texto_dias}'


class SACItem(models.Model):
    sac = models.ForeignKey(SAC, on_delete=models.CASCADE, related_name='itens_sac')
    item_nota_fiscal = models.ForeignKey(ItemNotaFiscal, on_delete=models.PROTECT)
    tipo_ocorrencia = models.ForeignKey(TipoOcorrencia, on_delete=models.PROTECT, blank=True, null=True)
    natureza_operacao = models.ForeignKey('NaturezaOperacao', on_delete=models.SET_NULL, blank=True, null=True, related_name='itens_sac')

    tipo_rastreio = models.CharField(
        max_length=10,
        choices=[('LOTE', 'Lote'), ('SERIAL', 'Serial')]
    )
    numero_rastreio = models.CharField(max_length=150, blank=True, null=True)
    quantidade_com_problema = models.PositiveIntegerField(default=1)
    grupo = models.CharField(max_length=255, blank=True, null=True)
    item_quebrado_inservivel = models.CharField(
        max_length=3,
        choices=[('SIM', 'Sim'), ('NAO', 'Não')],
        blank=True,
        null=True
    )
    item_pequeno_valor = models.CharField(
        max_length=3,
        choices=[('SIM', 'Sim'), ('NAO', 'Não')],
        blank=True,
        null=True
    )
    observacao_item = models.TextField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['sac', 'item_nota_fiscal', 'tipo_rastreio', 'numero_rastreio'],
                name='uq_sacitem_por_sac'
            )
        ]


class SACAnexo(models.Model):
    sac = models.ForeignKey(SAC, on_delete=models.CASCADE)
    arquivo = models.FileField(upload_to='sac_anexos/')


class SacHistorico(models.Model):
    sac = models.ForeignKey(SAC, on_delete=models.CASCADE, related_name='historicos')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    data_evento = models.DateTimeField(default=timezone.now)
    status_anterior = models.ForeignKey(
        StatusSAC,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='historicos_como_status_anterior'
    )
    status_novo = models.ForeignKey(
        StatusSAC,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='historicos_como_status_novo'
    )
    setor_origem = models.ForeignKey(
        Setor,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='historicos_como_setor_origem'
    )
    setor_destino = models.ForeignKey(
        Setor,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='historicos_como_setor_destino'
    )
    acao_executada = models.CharField(max_length=255)
    observacao = models.TextField(blank=True, null=True)
    arquivo = models.FileField(upload_to='sac_historico/', blank=True, null=True)

    class Meta:
        ordering = ['-data_evento', '-id']
        verbose_name = 'Histórico do SAC'
        verbose_name_plural = 'Histórico dos SACs'

    def __str__(self):
        return f'{self.sac.numero} - {self.acao_executada}'




class OrcamentoTecnicoExterno(models.Model):
    sac = models.OneToOneField(SAC, on_delete=models.CASCADE, related_name='orcamento_tecnico_externo')
    tecnico_externo = models.ForeignKey(
        TecnicoExterno,
        on_delete=models.PROTECT,
        related_name='orcamentos_tecnicos'
    )
    telefone = models.CharField(max_length=30, blank=True, null=True)
    whatsapp = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    cidade = models.CharField(max_length=255, blank=True, null=True)
    estado = models.CharField(max_length=2, blank=True, null=True)
    precisa_peca_reposicao = models.BooleanField(default=False)
    quantidade_horas = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_unitario_hora = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    valor_total_horas = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    valor_total_pecas = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    valor_total_geral = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Orçamento Técnico Externo'
        verbose_name_plural = 'Orçamentos Técnicos Externos'

    def __str__(self):
        return f'Orçamento Técnico Externo - {self.sac.numero}'


class OrcamentoTecnicoExternoPeca(models.Model):
    orcamento = models.ForeignKey(
        OrcamentoTecnicoExterno,
        on_delete=models.CASCADE,
        related_name='pecas'
    )
    peca = models.ForeignKey(PecaTabelaPreco, on_delete=models.PROTECT, related_name='itens_orcamento')
    referencia = models.CharField(max_length=100)
    descricao = models.CharField(max_length=255)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    valor_unitario = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    valor_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Peça do Orçamento Técnico Externo'
        verbose_name_plural = 'Peças do Orçamento Técnico Externo'

    def __str__(self):
        return f'{self.referencia} - {self.descricao}'


class SacAnaliseTecnica(models.Model):
    sac = models.OneToOneField(SAC, on_delete=models.CASCADE, related_name='analise_tecnica')
    tratativa_problema = models.ForeignKey(
        TratativaProblema,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='analises_tecnicas'
    )
    tipo_problema = models.ForeignKey(
        TipoProblema,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='analises_tecnicas'
    )
    observacao_tecnica = models.TextField(blank=True, null=True)
    proximo_status_sugerido = models.ForeignKey(
        StatusSAC,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='analises_tecnicas_proximo_status'
    )
    usuario_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='analises_tecnicas_responsaveis'
    )
    data_analise = models.DateTimeField(default=timezone.now)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Análise Técnica do SAC'
        verbose_name_plural = 'Análises Técnicas do SAC'

    def __str__(self):
        return f'Análise Técnica - {self.sac.numero}'


class SacAnaliseComercial(models.Model):
    sac = models.OneToOneField(SAC, on_delete=models.CASCADE, related_name='analise_comercial')
    cliente_confirmou_pedido = models.BooleanField(default=False)
    cliente_aceita_negociacao = models.BooleanField(default=False)
    proximo_status_sugerido = models.ForeignKey(
        StatusSAC,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='analises_comerciais_proximo_status'
    )
    acao_em_espera = models.ForeignKey(
        AcaoEmEspera,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='analises_comerciais'
    )
    valor_desconto_pleiteado = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    observacao_comercial = models.TextField(blank=True, null=True)
    usuario_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='analises_comerciais_responsaveis'
    )
    data_analise = models.DateTimeField(default=timezone.now)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Análise Comercial do SAC'
        verbose_name_plural = 'Análises Comerciais do SAC'

    def __str__(self):
        return f'Análise Comercial - {self.sac.numero}'


class NaturezaOperacao(models.Model):
    nome = models.CharField(max_length=255, unique=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Natureza da Operação'
        verbose_name_plural = 'Naturezas da Operação'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class FluxoAcaoSetor(models.Model):
    acao_atual = models.ForeignKey('AcaoEmEspera', on_delete=models.CASCADE, related_name='fluxo_origem')
    setor_atual = models.ForeignKey('Setor', on_delete=models.CASCADE, null=True, blank=True)
    proxima_acao = models.ForeignKey('AcaoEmEspera', on_delete=models.CASCADE, related_name='fluxo_destino')
    proximo_setor = models.ForeignKey('Setor', on_delete=models.CASCADE, related_name='fluxo_setor_destino')
    status_destino = models.ForeignKey('StatusSAC', on_delete=models.PROTECT, related_name='fluxos_como_status_destino', null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Fluxo Ação/Setor'
        verbose_name_plural = 'Fluxos Ação/Setor'
        ordering = ['acao_atual__nome', 'setor_atual__nome', 'proxima_acao__nome']
        # Permite múltiplos fluxos ativos para a mesma ação/setor.
        # A duplicidade exata continua bloqueada no clean(), considerando:
        # ação atual + setor atual + próxima ação + próximo setor + status destino.

    def clean(self):
        erros = {}

        if self.acao_atual_id == self.proxima_acao_id and self.setor_atual_id == self.proximo_setor_id:
            erros['proxima_acao'] = 'A próxima ação não pode repetir exatamente a mesma combinação de ação e setor atuais.'

        if self.proxima_acao_id and not self.proxima_acao.ativo:
            erros['proxima_acao'] = 'A próxima ação precisa estar ativa.'

        if self.acao_atual_id and not self.acao_atual.ativo:
            erros['acao_atual'] = 'A ação atual precisa estar ativa para compor uma regra de fluxo.'

        conflito = FluxoAcaoSetor.objects.filter(
            acao_atual=self.acao_atual,
            setor_atual=self.setor_atual,
            proxima_acao=self.proxima_acao,
            proximo_setor=self.proximo_setor,
            status_destino=self.status_destino,
            ativo=True,
        )
        if self.pk:
            conflito = conflito.exclude(pk=self.pk)
        if self.ativo and conflito.exists():
            erros['proximo_setor'] = 'Já existe uma regra ativa idêntica para esta combinação de ação atual, setor atual, próxima ação, próximo setor e status destino.'

        conflito_generico = FluxoAcaoSetor.objects.filter(
            acao_atual=self.acao_atual,
            setor_atual__isnull=True,
            proxima_acao=self.proxima_acao,
            proximo_setor=self.proximo_setor,
            status_destino=self.status_destino,
            ativo=True,
        )
        if self.pk:
            conflito_generico = conflito_generico.exclude(pk=self.pk)
        if self.ativo and self.setor_atual_id is None and conflito_generico.exists():
            erros['acao_atual'] = 'Já existe uma regra genérica ativa idêntica para esta ação atual.'

        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        setor = self.setor_atual.nome if self.setor_atual_id else 'SEM SETOR ESPECÍFICO'
        return f"{self.acao_atual} | {setor} -> {self.proxima_acao} / {self.proximo_setor}"
