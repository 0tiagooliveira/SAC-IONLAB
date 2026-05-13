from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import (
    AcaoEmEspera,
    Cliente,
    Empresa,
    ImportacaoLegadoSAC,
    ItemNotaFiscal,
    NotaFiscal,
    SAC,
    SACItem,
    SacHistorico,
    Setor,
    StatusSAC,
    TipoOcorrencia,
)


EMPRESA_CODIGO = "EVENLAB"
ANO_IMPORTACAO = 2025
SHEET_NAME = "2025"


ACAO_PADRAO_MAP = {
    "negociacao com cliente troca cancelamento": {
        "acao": "Aguardando Contato com Cliente - SAC",
        "setor": "Licitação",
    },
    "aguardando faturamento expedicao": {
        "acao": "Aguardando Emissão da Nota fiscal (Saída)",
        "setor": "Logística",
    },
    "sac emitir pedido cliente": {
        "acao": "Aguardando Emissão do Pedido (Saída)",
        "setor": "SAC",
    },
}


def norm(valor):
    if pd.isna(valor):
        return ""
    texto = str(valor or "").strip().replace("\xa0", " ")
    return re.sub(r"\s+", " ", texto)


def norm_ascii(valor):
    texto = unicodedata.normalize("NFKD", norm(valor)).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-zA-Z0-9]+", " ", texto.lower())
    return re.sub(r"\s+", " ", texto).strip()


def norm_key(valor):
    return norm_ascii(valor).replace(" ", "_")


def numero_texto(valor):
    texto = norm(valor)
    if not texto:
        return ""
    if re.fullmatch(r"\d+\.0", texto):
        return texto[:-2]
    try:
        numero = float(texto.replace(",", "."))
        if numero.is_integer():
            return str(int(numero))
    except Exception:
        pass
    return texto


def inteiro(valor, padrao=1):
    texto = numero_texto(valor)
    if not texto:
        return padrao
    try:
        return max(1, int(Decimal(texto.replace(",", "."))))
    except (InvalidOperation, ValueError):
        return padrao


def dinheiro(valor):
    texto = norm(valor)
    if not texto:
        return ""
    return texto


def data_valor(valor):
    if pd.isna(valor) or valor in ("", None):
        return None
    if isinstance(valor, pd.Timestamp):
        return valor.to_pydatetime()
    if isinstance(valor, datetime):
        return valor
    try:
        parsed = pd.to_datetime(valor, dayfirst=True, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()
    except Exception:
        return None


def data_hora_aware(valor, fim_do_dia=False):
    dt = data_valor(valor)
    if not dt:
        return None
    if not isinstance(dt, datetime):
        dt = datetime.combine(dt, time.max if fim_do_dia else time.min)
    if dt.time() == time.min and fim_do_dia:
        dt = datetime.combine(dt.date(), time.max.replace(microsecond=0))
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def limpar_tipo_ocorrencia(valor):
    return re.sub(r"^\d+\s*-\s*", "", norm(valor)).strip()


def limitar(valor, tamanho):
    texto = norm(valor)
    return texto[:tamanho] if texto else ""


def historico_formatado(texto):
    if not norm(texto):
        return ""
    bruto = norm(texto)
    bruto = re.sub(r"\*{2,}", "\n", bruto)
    bruto = re.sub(r"(?<!^)(?<!\n)(?<!\d)(\d{1,2}/\d{1,2}/\d{4})\s*[-–:]", r"\n\1 -", bruto)
    linhas = []
    atual = ""
    for parte in re.split(r"\n+", bruto):
        parte = parte.strip(" -*")
        if not parte:
            continue
        parte = re.sub(r"^(\d{1,2}/\d{1,2}/\d{4})\s*[-–:]?\s*", r"\1 - ", parte)
        parte = re.sub(r"\s+-\s+", " - ", parte)
        if re.match(r"^\d{1,2}/\d{1,2}/\d{4}\s+-\s+", parte):
            if atual:
                linhas.append(atual.strip())
            atual = parte
        elif atual:
            atual += " " + parte
        else:
            linhas.append(parte)
    if atual:
        linhas.append(atual.strip())
    return "\n".join(linhas)


def coluna(df, nome):
    alvo = norm_ascii(nome)
    for col in df.columns:
        if norm_ascii(col) == alvo:
            return col
    raise CommandError(f"Coluna obrigatoria nao encontrada: {nome}")


def sac_numero_sistema(sac_planilha):
    numero = int(numero_texto(sac_planilha))
    return f"{numero:03d}/{ANO_IMPORTACAO}", numero


class ImportadorEvenSAC:
    def __init__(self, *, arquivo, commit=False, incluir_bloqueados=False, usuario=None):
        self.arquivo = Path(arquivo)
        self.commit = commit
        self.incluir_bloqueados = incluir_bloqueados
        self.usuario = usuario
        self.empresa = Empresa.objects.filter(codigo__iexact=EMPRESA_CODIGO).first()
        if not self.empresa:
            raise CommandError(f"Empresa {EMPRESA_CODIGO} nao encontrada.")

        self.status_aberto = self._status("Aberto")
        self.status_analise = self._status("Em Análise") or self.status_aberto
        self.status_concluido = self._status("Concluído")
        if not self.status_aberto or not self.status_concluido:
            raise CommandError("Status obrigatorios nao encontrados: Aberto/Concluido.")

        self.setores = {norm_ascii(s.nome): s for s in Setor.objects.filter(ativo=True)}
        self.acoes = {norm_ascii(a.nome): a for a in AcaoEmEspera.objects.filter(ativo=True)}
        self.tipos = {norm_ascii(t.nome): t for t in TipoOcorrencia.objects.filter(ativo=True).select_related("setor", "acao_em_espera")}
        self.stats = defaultdict(int)
        self.skipped = []
        self.imported = []
        self.errors = []

    def _status(self, nome):
        chave = norm_ascii(nome)
        for status in StatusSAC.objects.filter(ativo=True):
            if norm_ascii(status.nome) == chave:
                return status
        return None

    def _acao_setor_por_padrao(self, valor):
        regra = ACAO_PADRAO_MAP.get(norm_ascii(valor))
        if not regra:
            return None, None
        return self.acoes.get(norm_ascii(regra["acao"])), self.setores.get(norm_ascii(regra["setor"]))

    def _item_nf(self, nf, referencia, equipamento):
        qs = ItemNotaFiscal.objects.filter(nota_fiscal=nf)
        if referencia:
            item = qs.filter(codigo_produto__iexact=referencia).first()
            if item:
                return item
        if equipamento:
            return qs.filter(descricao_item__iexact=equipamento).first()
        return None

    def _tipo_ocorrencia(self, valor):
        nome = limpar_tipo_ocorrencia(valor)
        return self.tipos.get(norm_ascii(nome)) if nome else None

    def carregar(self):
        if not self.arquivo.exists():
            raise CommandError(f"Arquivo nao encontrado: {self.arquivo}")
        df = pd.read_excel(self.arquivo, sheet_name=SHEET_NAME, dtype=object)
        return df

    def validar_grupo(self, sac_planilha, grupo, cols):
        pendencias = []
        primeira = grupo.iloc[0]
        sac_numero, _ = sac_numero_sistema(sac_planilha)

        codigo_cliente = numero_texto(primeira.get(cols["cliente_codigo"]))
        cliente = Cliente.objects.filter(empresa=self.empresa, codigo_interno=codigo_cliente).first() if codigo_cliente else None
        if not codigo_cliente:
            pendencias.append("Cliente sem codigo.")
        elif not cliente:
            pendencias.append(f"Cliente nao encontrado na base: {codigo_cliente}.")

        nf_numero = numero_texto(primeira.get(cols["nota"]))
        nf = None
        if nf_numero:
            nf = (
                NotaFiscal.objects.filter(empresa=self.empresa, numero_nf=nf_numero).first()
                or NotaFiscal.objects.filter(empresa=self.empresa, numero=nf_numero).first()
            )
        if not nf_numero:
            pendencias.append("Nota fiscal nao informada.")
        elif not nf:
            pendencias.append(f"Nota fiscal nao encontrada: {nf_numero}.")

        itens_informados = 0
        itens_validos = 0
        for idx, row in grupo.iterrows():
            referencia = numero_texto(row.get(cols["referencia"]))
            equipamento = norm(row.get(cols["equipamento"]))
            categoria = norm_ascii(row.get(cols["categoria"]))
            rastreio = numero_texto(row.get(cols["serie"]))
            linha = idx + 2

            if categoria == "equipamento" and (not rastreio or rastreio.upper() in {"S/N", "SN", "SEM SERIE", "SEM SÉRIE"}):
                pendencias.append(f"Linha {linha}: equipamento sem numero de serie ({referencia} / {equipamento}).")

            if not referencia and not equipamento:
                continue
            itens_informados += 1
            if nf:
                item_nf = self._item_nf(nf, referencia, equipamento)
                if not item_nf:
                    pendencias.append(f"Linha {linha}: item nao encontrado na NF {nf_numero} ({referencia} / {equipamento}).")
                else:
                    itens_validos += 1

        if itens_informados and not itens_validos:
            pendencias.append("Nenhum item valido localizado para o SAC.")

        return {
            "numero": sac_numero,
            "cliente": cliente,
            "nota": nf,
            "pendencias": pendencias,
        }

    def observacao_sac(self, primeira, cols):
        partes = []
        relato = norm(primeira.get(cols["relato"]))
        parecer = norm(primeira.get(cols["parecer"]))
        solucao = norm(primeira.get(cols["solucao"]))
        if relato:
            partes.append(f"Relato do cliente/usuario:\n{relato}")
        if parecer:
            partes.append(f"Parecer tecnico interno/terceiro:\n{parecer}")
        if solucao:
            partes.append(f"Solucao padrao:\n{solucao}")
        return "\n\n".join(partes)

    def observacao_item(self, row, cols):
        campos = [
            ("Tipo de problema", cols["tipo_problema"]),
            ("Parte do equipamento", cols["parte_problema"]),
            ("Ato que gerou o problema", cols["ato"]),
            ("Garantia", cols["garantia"]),
            ("Mau uso", cols["mau_uso"]),
            ("Conserto em garantia", cols["conserto_garantia"]),
            ("Custo pecas", cols["custo_pecas"]),
            ("Frete envio Ion", cols["frete_ion"]),
            ("Frete envio cliente", cols["frete_cliente"]),
            ("Custo tecnico terceiro", cols["custo_tecnico"]),
            ("Valor manutencao cliente", cols["valor_manutencao"]),
        ]
        linhas = []
        for rotulo, col in campos:
            valor = dinheiro(row.get(col))
            if valor:
                linhas.append(f"{rotulo}: {valor}")
        return "\n".join(linhas)

    def importar_grupo(self, sac_planilha, grupo, cols, validacao):
        primeira = grupo.iloc[0]
        numero_sac, sequencia = sac_numero_sistema(sac_planilha)
        cliente = validacao["cliente"]
        nf = validacao["nota"]
        status_planilha = norm_ascii(primeira.get(cols["status"]))
        concluido = status_planilha == "concluido"
        acao, setor = (None, None) if concluido else self._acao_setor_por_padrao(primeira.get(cols["acao_padrao"]))

        if not concluido and not setor:
            setor_nome = norm(primeira.get(cols["aguarda_acao"]))
            setor = self.setores.get(norm_ascii(setor_nome)) or self.setores.get("sac")
        if not concluido and not acao:
            acao = None

        data_abertura = data_hora_aware(primeira.get(cols["aberto"])) or timezone.now()
        concluido_em = data_hora_aware(primeira.get(cols["dt_concluido"]), fim_do_dia=True) if concluido else None
        titulo = f"SAC_{numero_sac} / {cliente.razao_social or cliente.nome} / NF {nf.numero_nf or nf.numero}"
        descricao = self.observacao_sac(primeira, cols)

        sac = SAC.objects.filter(empresa=self.empresa, numero=numero_sac).first()
        sac_created = sac is None

        if self.commit:
            if sac_created:
                sac = SAC.objects.create(
                    numero=numero_sac,
                    ano=ANO_IMPORTACAO,
                    sequencia_ano=sequencia,
                    empresa=self.empresa,
                    cliente=cliente,
                    nota_fiscal=nf,
                    data_emissao_nf=nf.data_emissao,
                    status_inicial="Aberto",
                    status_atual=self.status_concluido if concluido else self.status_analise,
                    acao_em_espera=None if concluido else acao,
                    setor_responsavel=self.setores.get("sac"),
                    setor_atual=None if concluido else setor,
                    usuario_abertura=self.usuario,
                    contato_nome=limitar(primeira.get(cols["contato"]), 255),
                    telefone_1=limitar(primeira.get(cols["telefone"]), 30),
                    email_1=limitar(primeira.get(cols["email"]), 254),
                    titulo=titulo,
                    descricao=descricao,
                    concluido_em=concluido_em,
                    email_automatico_habilitado=False,
                )
                SAC.objects.filter(pk=sac.pk).update(data_abertura=data_abertura)
                sac.data_abertura = data_abertura
            else:
                sac.empresa = self.empresa
                sac.cliente = cliente
                sac.nota_fiscal = nf
                sac.data_emissao_nf = nf.data_emissao
                sac.status_atual = self.status_concluido if concluido else self.status_analise
                sac.acao_em_espera = None if concluido else acao
                sac.setor_atual = None if concluido else setor
                sac.contato_nome = limitar(primeira.get(cols["contato"]), 255)
                sac.telefone_1 = limitar(primeira.get(cols["telefone"]), 30)
                sac.email_1 = limitar(primeira.get(cols["email"]), 254)
                sac.titulo = titulo
                sac.descricao = descricao
                sac.concluido_em = concluido_em
                sac.email_automatico_habilitado = False
                sac.save()
                SAC.objects.filter(pk=sac.pk).update(data_abertura=data_abertura)
                sac.data_abertura = data_abertura

        if sac_created:
            self.stats["sacs_criados"] += 1
        else:
            self.stats["sacs_atualizados"] += 1

        itens_resultado = self.importar_itens(sac, grupo, cols) if self.commit else self.simular_itens(numero_sac, grupo, cols, nf)

        if self.commit:
            self.registrar_historicos(sac, primeira, cols, concluido, data_abertura, concluido_em)

        self.imported.append({
            "sac": numero_sac,
            "origem": numero_texto(sac_planilha),
            "criado": sac_created,
            "itens": itens_resultado,
        })

    def simular_itens(self, numero_sac, grupo, cols, nf):
        resultado = {"criados": 0, "atualizados": 0, "ignorados": 0}
        sac = SAC.objects.filter(empresa=self.empresa, numero=numero_sac).first()
        for _, row in grupo.iterrows():
            referencia = numero_texto(row.get(cols["referencia"]))
            equipamento = norm(row.get(cols["equipamento"]))
            item_nf = self._item_nf(nf, referencia, equipamento) if (referencia or equipamento) else None
            if not item_nf:
                resultado["ignorados"] += 1
                self.stats["itens_ignorados"] += 1
                continue
            tipo_rastreio = "SERIAL" if norm_ascii(row.get(cols["categoria"])) == "equipamento" else "LOTE"
            numero_rastreio = numero_texto(row.get(cols["serie"]))
            if SACItem.objects.filter(item_nota_fiscal=item_nf, tipo_rastreio=tipo_rastreio, numero_rastreio=numero_rastreio or "").exclude(sac=sac).exists():
                resultado["ignorados"] += 1
                self.stats["itens_ignorados"] += 1
                continue
            exists = bool(sac and SACItem.objects.filter(sac=sac, item_nota_fiscal=item_nf, tipo_rastreio=tipo_rastreio, numero_rastreio=numero_rastreio or "").exists())
            if exists:
                resultado["atualizados"] += 1
                self.stats["itens_atualizados"] += 1
            else:
                resultado["criados"] += 1
                self.stats["itens_criados"] += 1
        return resultado

    def importar_itens(self, sac, grupo, cols):
        resultado = {"criados": 0, "atualizados": 0, "ignorados": 0}
        for _, row in grupo.iterrows():
            referencia = numero_texto(row.get(cols["referencia"]))
            equipamento = norm(row.get(cols["equipamento"]))
            item_nf = self._item_nf(sac.nota_fiscal, referencia, equipamento) if (referencia or equipamento) else None
            if not item_nf:
                resultado["ignorados"] += 1
                self.stats["itens_ignorados"] += 1
                continue
            tipo_rastreio = "SERIAL" if norm_ascii(row.get(cols["categoria"])) == "equipamento" else "LOTE"
            numero_rastreio = numero_texto(row.get(cols["serie"]))
            if SACItem.objects.filter(item_nota_fiscal=item_nf, tipo_rastreio=tipo_rastreio, numero_rastreio=numero_rastreio or "").exclude(sac=sac).exists():
                resultado["ignorados"] += 1
                self.stats["itens_ignorados"] += 1
                self.errors.append({
                    "sac": sac.numero,
                    "tipo": "item_serial_ja_existente",
                    "item_nota_fiscal_id": item_nf.id,
                    "tipo_rastreio": tipo_rastreio,
                    "numero_rastreio": numero_rastreio,
                })
                continue
            tipo_ocorrencia = self._tipo_ocorrencia(row.get(cols["tipo_ocorrencia"]))
            grupo = norm(row.get(cols["categoria"]))
            defaults = {
                "tipo_ocorrencia": tipo_ocorrencia,
                "quantidade_com_problema": inteiro(row.get(cols["quantidade"]), 1),
                "grupo": grupo,
                "item_quebrado_inservivel": None,
                "item_pequeno_valor": None,
                "observacao_item": self.observacao_item(row, cols),
            }
            sac_item, created = SACItem.objects.update_or_create(
                sac=sac,
                item_nota_fiscal=item_nf,
                tipo_rastreio=tipo_rastreio,
                numero_rastreio=numero_rastreio or "",
                defaults=defaults,
            )
            if created:
                resultado["criados"] += 1
                self.stats["itens_criados"] += 1
            else:
                resultado["atualizados"] += 1
                self.stats["itens_atualizados"] += 1
        return resultado

    def registrar_historicos(self, sac, primeira, cols, concluido, data_abertura, concluido_em):
        marcador = f"Importacao historica EVEN 2025 - arquivo {self.arquivo.name}"
        if not SacHistorico.objects.filter(sac=sac, acao_executada=marcador).exists():
            SacHistorico.objects.create(
                sac=sac,
                usuario=self.usuario,
                data_evento=data_abertura,
                status_anterior=None,
                status_novo=sac.status_atual,
                setor_origem=None,
                setor_destino=sac.setor_atual,
                acao_executada=marcador,
                observacao=self.observacao_sac(primeira, cols) or "SAC importado da planilha historica EVEN 2025.",
            )
        historico = historico_formatado(primeira.get(cols["historico"]))
        if historico and not SacHistorico.objects.filter(sac=sac, acao_executada="Historico legado EVEN 2025").exists():
            SacHistorico.objects.create(
                sac=sac,
                usuario=self.usuario,
                data_evento=data_abertura,
                status_anterior=None,
                status_novo=sac.status_atual,
                setor_origem=None,
                setor_destino=sac.setor_atual,
                acao_executada="Historico legado EVEN 2025",
                observacao=historico,
            )
        if concluido and concluido_em and not SacHistorico.objects.filter(sac=sac, acao_executada="Conclusao historica EVEN 2025").exists():
            SacHistorico.objects.create(
                sac=sac,
                usuario=self.usuario,
                data_evento=concluido_em,
                status_anterior=self.status_aberto,
                status_novo=self.status_concluido,
                setor_origem=sac.setor_atual,
                setor_destino=sac.setor_atual,
                acao_executada="Conclusao historica EVEN 2025",
                observacao="SAC marcado como concluido conforme planilha historica.",
            )

    def executar(self):
        df = self.carregar()
        cols = {
            "sac": coluna(df, "SAC Nº"),
            "status": coluna(df, "STATUS"),
            "aberto": coluna(df, "Aberto"),
            "dt_concluido": coluna(df, "DT CONCLUÍDO"),
            "acao_padrao": coluna(df, "Ação Padrão"),
            "aguarda_acao": coluna(df, "Aguarda ação de"),
            "historico": coluna(df, "Historico Recente"),
            "nota": coluna(df, "Nota Fiscal Venda"),
            "cliente_codigo": coluna(df, "Cód. Cli"),
            "contato": coluna(df, "Contato"),
            "telefone": coluna(df, "DDD/Telefone"),
            "email": coluna(df, "e-mail"),
            "referencia": coluna(df, "Referencia"),
            "equipamento": coluna(df, "Equipamento"),
            "quantidade": coluna(df, "Quantidade"),
            "serie": coluna(df, "Nº Série"),
            "relato": coluna(df, "Relato do Cliente/usuário sobre o Problema"),
            "parecer": coluna(df, "Resumo Parecer Área Tecnica Interna/Terceira"),
            "solucao": coluna(df, "Solução Padrão"),
            "tipo_ocorrencia": coluna(df, "Tipo ocorrência"),
            "tipo_problema": coluna(df, "Tipo de problema no Equipamento"),
            "parte_problema": coluna(df, "Indique a parte do equipamento com problema"),
            "categoria": coluna(df, "Categoria"),
            "ato": coluna(df, "Ato que gerou o problema"),
            "garantia": coluna(df, "Dentro do periodo de garantia"),
            "mau_uso": coluna(df, "Detectado mau uso"),
            "conserto_garantia": coluna(df, "Conserto em Garantia"),
            "custo_pecas": coluna(df, "Custo Total das Peças de Reposição"),
            "frete_ion": coluna(df, "Valor Frete R$ de envio para Ion"),
            "frete_cliente": coluna(df, "Valor do Frete De envio ao Cliente"),
            "custo_tecnico": coluna(df, "Custo com Tecnico Terceiro"),
            "valor_manutencao": coluna(df, "Valor da manutenção cobrada do Cliente"),
        }

        importacao = ImportacaoLegadoSAC.objects.create(
            nome=f"EVEN SAC {ANO_IMPORTACAO} - {self.arquivo.name}",
            arquivo_origem=str(self.arquivo),
            empresa=self.empresa,
            usuario=self.usuario,
            dry_run=not self.commit,
            status="COMMIT" if self.commit else "DRY_RUN",
            total_linhas=len(df),
            total_sacs_planilha=int(df[cols["sac"]].nunique()),
        )

        try:
            with transaction.atomic():
                for sac_planilha, grupo in df.groupby(cols["sac"], dropna=False):
                    if not numero_texto(sac_planilha):
                        self.skipped.append({"sac": "SEM_NUMERO", "pendencias": ["SAC sem numero."]})
                        self.stats["sacs_pulados"] += 1
                        continue
                    validacao = self.validar_grupo(sac_planilha, grupo, cols)
                    if validacao["pendencias"] and not self.incluir_bloqueados:
                        self.skipped.append({
                            "sac": validacao["numero"],
                            "origem": numero_texto(sac_planilha),
                            "pendencias": validacao["pendencias"],
                        })
                        self.stats["sacs_pulados"] += 1
                        continue
                    self.importar_grupo(sac_planilha, grupo, cols, validacao)
                if not self.commit:
                    transaction.set_rollback(False)
        except Exception as exc:
            importacao.status = "ERRO"
            importacao.detalhes = {"erro": str(exc), "importados": self.imported, "pulados": self.skipped}
            importacao.save()
            raise

        importacao.sacs_criados = self.stats["sacs_criados"]
        importacao.sacs_atualizados = self.stats["sacs_atualizados"]
        importacao.itens_criados = self.stats["itens_criados"]
        importacao.itens_atualizados = self.stats["itens_atualizados"]
        importacao.itens_ignorados = self.stats["itens_ignorados"]
        importacao.sacs_pulados = self.stats["sacs_pulados"]
        importacao.detalhes = {
            "arquivo": str(self.arquivo),
            "commit": self.commit,
            "incluir_bloqueados": self.incluir_bloqueados,
            "sacs_importados": self.imported,
            "sacs_pulados": self.skipped,
            "erros": self.errors,
        }
        importacao.save()
        return importacao


class Command(BaseCommand):
    help = "Importa SACs historicos da planilha EVEN, com dry-run seguro e reprocessamento idempotente."

    def add_arguments(self, parser):
        parser.add_argument("arquivo", help="Caminho da planilha EVEN_SAC_rev*.xlsx")
        parser.add_argument("--commit", action="store_true", help="Grava no banco. Sem esta flag, roda apenas simulacao.")
        parser.add_argument("--incluir-bloqueados", action="store_true", help="Tenta importar tambem SACs com pendencias.")
        parser.add_argument("--usuario", default="", help="Username responsavel pelo historico da importacao.")

    def handle(self, *args, **options):
        User = get_user_model()
        usuario = None
        username = (options.get("usuario") or "").strip()
        if username:
            usuario = User.objects.filter(username=username).first()
            if not usuario:
                raise CommandError(f"Usuario nao encontrado: {username}")
        if not usuario:
            usuario = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not usuario:
            raise CommandError("Nenhum usuario encontrado para registrar historico.")

        importador = ImportadorEvenSAC(
            arquivo=options["arquivo"],
            commit=options["commit"],
            incluir_bloqueados=options["incluir_bloqueados"],
            usuario=usuario,
        )
        importacao = importador.executar()

        resumo = {
            "importacao_id": importacao.id,
            "status": importacao.status,
            "dry_run": importacao.dry_run,
            "total_linhas": importacao.total_linhas,
            "total_sacs_planilha": importacao.total_sacs_planilha,
            "sacs_criados": importacao.sacs_criados,
            "sacs_atualizados": importacao.sacs_atualizados,
            "itens_criados": importacao.itens_criados,
            "itens_atualizados": importacao.itens_atualizados,
            "itens_ignorados": importacao.itens_ignorados,
            "sacs_pulados": importacao.sacs_pulados,
        }
        self.stdout.write(json.dumps(resumo, ensure_ascii=False, indent=2))
