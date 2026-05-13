from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
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
from core.services.texto_padrao import padronizar_caixa_texto


EMPRESA_CODIGO = "IONLAB"


ACAO_PADRAO_MAP = {
    "aguardando faturamento expedicao": "Aguardando Emissão da Nota fiscal (Saída)",
    "aguardando cliente fazer o envio do equipamento": "Aguardando Cliente emitir Nota fiscal e fazer envio",
    "aguardando envio para area tecnica revisar": "Aguardando Inspeção fisica e Funcional",
    "aguardando manutencao": "Aguardando Manutenção Interna",
    "aguardando mantencao": "Aguardando Manutenção Interna",
    "aguardando manutencao externa": "Aguardando Manutenção Externa",
    "aguardando aprovacao de orcamento": "Aguardando Aprovação do Orçamento (cliente)",
    "aguardando autorizacao diretoria": "Aguardando Aprovação de orçamento (Interno Diretoria)",
    "sac emitir pedido": "Aguardando Emissão do Pedido (Saída)",
    "em transito aguardando chegar no cliente": "Em Transito (Com destino ao Cliente)",
    "em transito aguardando chegar na ionlab": "Em Transito (Com destino a Ionlab)",
    "aguardando coleta reversa no cliente": "Aguardando Cliente emitir Nota fiscal e fazer envio",
    "aguardando nf remessa conserto cliente": "Aguardando Emissão da Nota fiscal (Entrada/Retorno))",
    "manutencao realizada enviado para pagamento": "Aprovar Cobrança do Valor do Serviço",
}


TIPO_OCORRENCIA_MAP = {
    "tecnico": "Tecnico - Equipamento não funciona",
    "avarias": "Itens/Equipamentos avariados",
    "material equipamento faltante": "Itens/Equipamentos faltantes na embalagem",
    "material equipamento errado": "Itens/Equipamentos em desacordo com pedido",
    "material equipamento sobrando": "Itens/Equipamentos sobrando na embalagem",
}


SETOR_ATUAL_OVERRIDE = {
    "148/2024": {
        "setor": "SAC",
        "acao": "Aguardando Emissão do Pedido (Entrada/Retorno)",
    },
    "273/2024": {
        "setor": "Assessoria Cientifica",
        "acao": "Aguardando Contato com Cliente - AC",
    },
    "768/2026": {
        "setor": "Assistência Técnica",
        "acao": "Aguardando Inspeção fisica e Funcional",
    },
    "784/2026": {
        "setor": "Assistência Técnica",
        "acao": "Aguardando Inspeção fisica e Funcional",
    },
    "799/2026": {
        "setor": "Assistência Técnica",
        "acao": "Aguardando Inspeção fisica e Funcional",
    },
}


CRONOLOGIA_EVENTOS = [
    ("aberto", "Aberto", "SAC importado da planilha historica Ionlab."),
    (
        "aberto aguardando tratativa tecnica por telefone",
        "Aberto - Aguardando Tratativa Tecnica Por Telefone",
        "Etapa historica: aguardando tratativa tecnica por telefone.",
    ),
    (
        "aberto aguardando chegada",
        "Aberto - Aguardando Chegada",
        "Etapa historica: aguardando chegada.",
    ),
    (
        "aberto aguardando avaliacao",
        "Aberto - Aguardando Avaliação",
        "Etapa historica: aguardando avaliacao.",
    ),
    (
        "aberto aguardando aprov orcamento",
        "Aberto - Aguardando Aprov. Orçamento",
        "Etapa historica: aguardando aprovacao de orcamento.",
    ),
    (
        "aberto aguardando peca",
        "Aberto - Aguardando Peça",
        "Etapa historica: aguardando peca.",
    ),
    (
        "aberto aguardando manutencao interna",
        "Aberto - Aguardando manutenção Interna",
        "Etapa historica: aguardando manutencao interna.",
    ),
    (
        "aberto aguardando manutencao externa",
        "Aberto - Aguardando manutenção Externa",
        "Etapa historica: aguardando manutencao externa.",
    ),
    (
        "aberto aguardando devolucao ao cliente",
        "Aberto - Aguardando devolução ao Cliente",
        "Etapa historica: aguardando devolucao ao cliente.",
    ),
    (
        "encerrado parcialmente aguardando entrega ao cliente",
        "Encerrado Parcialmente - Aguardando entrega ao cliente",
        "Etapa historica: encerrado parcialmente, aguardando entrega ao cliente.",
    ),
    ("acao interna", "Ação interna", "Etapa historica: acao interna."),
    ("encerrado", "Encerrado", "SAC concluido conforme planilha historica Ionlab."),
]


STATUS_CRONOLOGIA_CHAVE = {
    "aberto": "aberto",
    "aberto aguardando tratativa tecnica por telefone": "aberto aguardando tratativa tecnica por telefone",
    "aberto aguardando chegada": "aberto aguardando chegada",
    "aberto aguardando avaliacao": "aberto aguardando avaliacao",
    "aberto aguardando aprov orcamento": "aberto aguardando aprov orcamento",
    "aberto aguardando peca": "aberto aguardando peca",
    "aberto aguardando manutencao interna": "aberto aguardando manutencao interna",
    "aberto aguardando manutencao externa": "aberto aguardando manutencao externa",
    "aberto aguardando devolucao ao cliente": "aberto aguardando devolucao ao cliente",
    "encerrado parcialmente aguardando entrega ao cliente": "encerrado parcialmente aguardando entrega ao cliente",
    "acao interna": "acao interna",
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


def numero_texto(valor):
    texto = norm(valor)
    if not texto:
        return ""
    try:
        numero = float(texto.replace(",", "."))
        if numero.is_integer():
            return str(int(numero))
    except Exception:
        pass
    if re.fullmatch(r"\d+\.0", texto):
        return texto[:-2]
    return texto


def inteiro(valor, padrao=1):
    texto = numero_texto(valor)
    if not texto:
        return padrao
    try:
        return max(1, int(Decimal(texto.replace(",", "."))))
    except (InvalidOperation, ValueError):
        return padrao


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


def limitar(valor, tamanho):
    texto = norm(valor)
    return texto[:tamanho] if texto else ""


def coluna_por_chave(df, chave):
    for col in df.columns:
        if norm_ascii(col) == chave:
            return col
    return None


def valor_linha(row, col):
    if col is None or col not in row.index:
        return None
    return row.get(col)


def historico_formatado(texto):
    bruto = norm(texto)
    if not bruto:
        return ""
    bruto = re.sub(r"(?<![\n\d/])(\d{1,2}/\d{1,2}/\d{2,4})(?=\s*)", r"\n\1", bruto)
    linhas = []
    atual = ""
    for parte in re.split(r"\n+", bruto):
        parte = parte.strip(" -*")
        if not parte:
            continue
        parte = re.sub(r"^(\d{1,2}/\d{1,2}/\d{2,4})\s*[-:]?\s*", r"\1 - ", parte)
        if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}\s+-\s+", parte):
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


def data_linha_historico(data):
    if not data:
        return ""
    return timezone.localtime(data).strftime("%d/%m/%Y") if timezone.is_aware(data) else data.strftime("%d/%m/%Y")


def linha_historico(data, texto):
    texto = norm(texto)
    if not texto:
        return ""
    texto = padronizar_caixa_texto(texto)
    data_txt = data_linha_historico(data)
    return f"{data_txt} - {texto}" if data_txt else texto


def linhas_historico_legado(texto, data_padrao=None):
    formatado = historico_formatado(texto)
    if not formatado:
        return []
    linhas = []
    for linha in formatado.splitlines():
        linha = norm(linha)
        if not linha:
            continue
        if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}\s+-\s+", linha):
            data_txt, texto_linha = linha.split(" - ", 1)
            linhas.append(f"{data_txt} - {padronizar_caixa_texto(texto_linha)}")
        else:
            linhas.append(linha_historico(data_padrao, linha))
    return linhas


def prefixar_descritivo_historico(linha, prefixo):
    linha = norm(linha)
    if not linha:
        return ""
    match = re.match(r"^(\d{1,2}/\d{1,2}/\d{2,4}\s+-\s+)(.*)$", linha)
    if match:
        return f"{match.group(1)}{prefixo}: {padronizar_caixa_texto(match.group(2).strip())}"
    return f"{prefixo}: {padronizar_caixa_texto(linha)}"


class ImportadorIonlabSAC:
    def __init__(self, *, arquivos, commit=False, log_output=None, usuario=None):
        self.arquivos = [Path(a) for a in arquivos]
        self.commit = commit
        self.log_output = Path(log_output) if log_output else None
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
        self.acoes = {norm_ascii(a.nome): a for a in AcaoEmEspera.objects.filter(ativo=True).select_related("setor_destino")}
        self.tipos = {norm_ascii(t.nome): t for t in TipoOcorrencia.objects.filter(ativo=True)}
        self.stats = defaultdict(int)
        self.logs = []
        self.importados = []

    def _status(self, nome):
        chave = norm_ascii(nome)
        for status in StatusSAC.objects.filter(ativo=True):
            if norm_ascii(status.nome) == chave:
                return status
        return None

    def _log(self, severidade, sac, linha, campo, valor, motivo, arquivo=""):
        self.logs.append({
            "severidade": severidade,
            "sac": sac or "",
            "linha": linha or "",
            "campo": campo,
            "valor": valor or "",
            "motivo": motivo,
            "arquivo": arquivo,
        })

    def _acao_por_texto(self, texto):
        destino = ACAO_PADRAO_MAP.get(norm_ascii(texto))
        if not destino:
            return None
        return self.acoes.get(norm_ascii(destino))

    def _setor_por_texto(self, texto):
        return self.setores.get(norm_ascii(texto))

    def _tipo_ocorrencia(self, texto):
        chave = norm_ascii(texto)
        if chave in {"", "administrativo", "nan"}:
            return None
        destino = TIPO_OCORRENCIA_MAP.get(chave)
        tipo = self.tipos.get(norm_ascii(destino)) if destino else None
        return tipo

    def _cols(self, df):
        cols = {
            "numero": coluna_por_chave(df, "no sac"),
            "status": coluna_por_chave(df, "status"),
            "aberto": coluna_por_chave(df, "aberto"),
            "acao": coluna_por_chave(df, "acao padrao") or coluna_por_chave(df, "qual acao pendente"),
            "aguarda": coluna_por_chave(df, "aguarda acao de"),
            "historico": coluna_por_chave(df, "historico"),
            "nota": coluna_por_chave(df, "nota fiscal venda"),
            "cliente_codigo": coluna_por_chave(df, "cod cli"),
            "cliente": coluna_por_chave(df, "cliente"),
            "contato": coluna_por_chave(df, "contato"),
            "telefone": coluna_por_chave(df, "ddd telefone"),
            "email": coluna_por_chave(df, "e mail"),
            "referencia": coluna_por_chave(df, "referencia"),
            "equipamento": coluna_por_chave(df, "equipamento"),
            "quantidade": coluna_por_chave(df, "quantidade"),
            "serie": coluna_por_chave(df, "no serie"),
            "relato": coluna_por_chave(df, "o que o cliente alegou de problema"),
            "parecer": coluna_por_chave(df, "resumo parecer area tecnica interna terceira"),
            "solucao": coluna_por_chave(df, "solucao padrao"),
            "tipo": coluna_por_chave(df, "tipo de problema"),
            "parte": coluna_por_chave(df, "indique a parte do equipamento com problema"),
            "categoria": coluna_por_chave(df, "categoria"),
            "origem": coluna_por_chave(df, "setor da origem do problema"),
            "ato": coluna_por_chave(df, "ato que gerou o problema"),
            "garantia": coluna_por_chave(df, "dentro do periodo de garantia"),
            "mau_uso": coluna_por_chave(df, "detectado mau uso"),
            "conserto_garantia": coluna_por_chave(df, "conserto em garantia"),
            "custo_pecas": coluna_por_chave(df, "custo total das pecas de reposicao"),
            "frete_ion": coluna_por_chave(df, "valor frete r de envio para ion"),
            "frete_cliente": coluna_por_chave(df, "valor do frete de envio ao cliente"),
            "custo_tecnico": coluna_por_chave(df, "custo com tecnico terceiro"),
            "valor_manutencao": coluna_por_chave(df, "valor da manutencao cobrada do cliente"),
        }
        cols["cronologia"] = {chave: coluna_por_chave(df, chave) for chave, _, _ in CRONOLOGIA_EVENTOS}
        obrigatorias = ["numero", "status", "aberto", "nota", "cliente", "referencia", "equipamento", "quantidade", "tipo"]
        faltantes = [nome for nome in obrigatorias if not cols.get(nome)]
        if faltantes:
            raise CommandError(f"Colunas obrigatorias nao encontradas: {', '.join(faltantes)}")
        return cols

    def carregar(self):
        linhas = []
        for arquivo in self.arquivos:
            if not arquivo.exists():
                raise CommandError(f"Arquivo nao encontrado: {arquivo}")
            sheet = pd.ExcelFile(arquivo).sheet_names[0]
            df = pd.read_excel(arquivo, sheet_name=sheet, dtype=object)
            cols = self._cols(df)
            for idx, row in df.iterrows():
                numero = numero_texto(valor_linha(row, cols["numero"]))
                if not numero:
                    continue
                abertura = data_hora_aware(valor_linha(row, cols["aberto"]))
                ano = abertura.year if abertura else None
                linhas.append({
                    "arquivo": arquivo.name,
                    "linha": idx + 2,
                    "row": row,
                    "cols": cols,
                    "numero_origem": numero,
                    "ano": ano,
                    "abertura": abertura,
                    "chave": (numero, ano),
                })
        return linhas

    def _eventos_grupo(self, grupo):
        eventos = {}
        for item in grupo:
            row = item["row"]
            cols = item["cols"]
            for chave, label, obs in CRONOLOGIA_EVENTOS:
                col = cols["cronologia"].get(chave)
                data = data_hora_aware(valor_linha(row, col), fim_do_dia=(chave == "encerrado"))
                if not data:
                    continue
                eventos[(data, label)] = {
                    "data": data,
                    "label": label,
                    "observacao": obs,
                }
        return sorted(eventos.values(), key=lambda e: (e["data"], e["label"]))

    def _melhor_valor(self, grupo, campo):
        for item in grupo:
            valor = norm(valor_linha(item["row"], item["cols"].get(campo)))
            if valor:
                return valor
        return ""

    def _data_referencia_linha_pendente(self, item):
        row = item["row"]
        cols = item["cols"]
        status_chave = norm_ascii(valor_linha(row, cols["status"]))
        cronologia_chave = STATUS_CRONOLOGIA_CHAVE.get(status_chave)
        if cronologia_chave:
            col = cols["cronologia"].get(cronologia_chave)
            data = data_hora_aware(valor_linha(row, col))
            if data:
                return data

        datas = []
        for col in cols.get("cronologia", {}).values():
            data = data_hora_aware(valor_linha(row, col))
            if data:
                datas.append(data)
        if datas:
            return max(datas)
        return item.get("abertura")

    def _item_status_mais_recente(self, grupo, *, ignorar_concluidos=False):
        candidatos = []
        for item in grupo:
            status = norm_ascii(valor_linha(item["row"], item["cols"]["status"]))
            if ignorar_concluidos and status in {"concluido", "encerrado"}:
                continue
            data = self._data_referencia_linha_pendente(item)
            candidatos.append((data or item.get("abertura") or timezone.now(), item["linha"], item))
        if not candidatos:
            return grupo[0]
        return max(candidatos, key=lambda x: (x[0], x[1]))[2]

    def _item_pendente_mais_recente(self, grupo):
        return self._item_status_mais_recente(grupo, ignorar_concluidos=True)

    def _itens_status(self, grupo, status_chave):
        return [
            item for item in grupo
            if norm_ascii(valor_linha(item["row"], item["cols"]["status"])) == status_chave
        ]

    def _item_acao_interna_mais_recente(self, grupo):
        candidatos = []
        for item in self._itens_status(grupo, "acao interna"):
            data = self._data_referencia_linha_pendente(item)
            candidatos.append((data or item.get("abertura") or timezone.now(), item["linha"], item))
        if not candidatos:
            return None
        return max(candidatos, key=lambda x: (x[0], x[1]))[2]

    def _primeiro_item_com_valor(self, grupo, campo):
        for item in grupo:
            valor = norm(valor_linha(item["row"], item["cols"].get(campo)))
            if valor:
                return item
        return grupo[0]

    def _nota(self, numero):
        if not numero:
            return None
        return (
            NotaFiscal.objects.filter(empresa=self.empresa, numero_nf=numero).first()
            or NotaFiscal.objects.filter(empresa=self.empresa, numero=numero).first()
        )

    def _item_nf(self, nf, referencia, equipamento):
        if not nf:
            return None
        qs = ItemNotaFiscal.objects.filter(nota_fiscal=nf)
        if referencia:
            item = qs.filter(codigo_produto__iexact=referencia).first()
            if item:
                return item
        if equipamento:
            item = qs.filter(descricao_item__iexact=equipamento).first()
            if item:
                return item
        return None

    def _cliente_por_nome(self, nome):
        texto = norm(nome)
        if not texto:
            return None
        cliente = (
            Cliente.objects.filter(empresa=self.empresa, razao_social__iexact=texto).first()
            or Cliente.objects.filter(empresa=self.empresa, nome__iexact=texto).first()
        )
        if cliente:
            return cliente
        chave = norm_ascii(texto)
        candidatos = Cliente.objects.filter(empresa=self.empresa)
        for candidato in candidatos:
            if norm_ascii(candidato.razao_social) == chave or norm_ascii(candidato.nome) == chave:
                return candidato
        return None

    def _validar_grupo(self, chave, grupo):
        numero, ano = chave
        sac_numero = f"{int(numero):03d}/{ano}" if str(numero).isdigit() and ano else f"{numero}/{ano or 'SEM_ANO'}"
        bloqueios = []
        avisos = []

        if not ano:
            bloqueios.append("SAC sem data de abertura; nao foi possivel definir o ano do numero.")

        abertura = min([g["abertura"] for g in grupo if g["abertura"]], default=None)
        eventos = self._eventos_grupo(grupo)
        if abertura:
            for evento in eventos:
                if evento["data"] < abertura:
                    bloqueios.append(
                        f"Cronologia invalida: {evento['label']} em {evento['data'].date()} antes da abertura {abertura.date()}."
                    )
        else:
            bloqueios.append("Data de abertura nao informada.")

        nf_numero = ""
        nf = None
        for item in grupo:
            numero_nf = numero_texto(valor_linha(item["row"], item["cols"]["nota"]))
            if numero_nf:
                nf_numero = numero_nf
                nf = self._nota(numero_nf)
                if nf:
                    break
        if not nf_numero:
            bloqueios.append("Nota fiscal nao informada.")
        elif not nf:
            bloqueios.append(f"Nota fiscal nao encontrada: {nf_numero}.")

        cliente = nf.cliente if nf else None
        codigo_cliente = self._melhor_valor(grupo, "cliente_codigo")
        if not cliente and codigo_cliente:
            cliente = Cliente.objects.filter(empresa=self.empresa, codigo_interno=numero_texto(codigo_cliente)).first()
        if not cliente:
            cliente = self._cliente_por_nome(self._melhor_valor(grupo, "cliente"))
        if not cliente:
            bloqueios.append(f"Cliente nao encontrado para o SAC. Codigo informado: {codigo_cliente or '-'}")

        item_acao_interna = self._item_acao_interna_mais_recente(grupo)
        possui_acao_interna = item_acao_interna is not None
        if possui_acao_interna:
            eventos = [evento for evento in eventos if evento["label"] != "Encerrado"]

        status_grupo = [
            norm_ascii(valor_linha(item["row"], item["cols"]["status"]))
            for item in grupo
            if norm_ascii(valor_linha(item["row"], item["cols"]["status"]))
        ]
        concluido = (
            bool(status_grupo)
            and not possui_acao_interna
            and all(status in {"concluido", "encerrado"} for status in status_grupo)
        )
        acao = None
        setor = None
        item_pendente = item_acao_interna or self._item_pendente_mais_recente(grupo)
        status_pendente = norm_ascii(valor_linha(item_pendente["row"], item_pendente["cols"]["status"]))
        if not concluido:
            acao_texto = norm(valor_linha(item_pendente["row"], item_pendente["cols"].get("acao")))
            aguarda_texto = norm(valor_linha(item_pendente["row"], item_pendente["cols"].get("aguarda")))
            acao = self._acao_por_texto(acao_texto)
            if not acao and status_pendente != "acao interna":
                bloqueios.append(f"Acao pendente sem regra cadastrada: {acao_texto or '-'}")
            if status_pendente == "acao interna":
                setor = self._setor_por_texto(aguarda_texto)
                if not setor:
                    setor = getattr(acao, "setor_destino", None) if acao else None
            else:
                setor = getattr(acao, "setor_destino", None) if acao else None
                if not setor:
                    setor = self._setor_por_texto(aguarda_texto)
            if not setor:
                bloqueios.append("Setor atual nao identificado para SAC aberto.")

        override = SETOR_ATUAL_OVERRIDE.get(sac_numero) or {}
        if override and not concluido:
            setor_override = self._setor_por_texto(override.get("setor"))
            if setor_override:
                setor = setor_override
            acao_override = self._acao_por_texto(override.get("acao")) or self.acoes.get(norm_ascii(override.get("acao")))
            if acao_override:
                acao = acao_override

        for item in grupo:
            row = item["row"]
            cols = item["cols"]
            referencia = numero_texto(valor_linha(row, cols["referencia"]))
            equipamento = norm(valor_linha(row, cols["equipamento"]))
            if not referencia and not equipamento:
                continue
            nf_linha = self._nota(numero_texto(valor_linha(row, cols["nota"]))) or nf
            if not self._item_nf(nf_linha, referencia, equipamento):
                avisos.append(f"Linha {item['linha']}: item nao encontrado na NF ({referencia or '-'} / {equipamento or '-'}).")
            tipo = norm(valor_linha(row, cols["tipo"]))
            if norm_ascii(tipo) not in {"", "administrativo"} and not self._tipo_ocorrencia(tipo):
                avisos.append(f"Linha {item['linha']}: tipo de ocorrencia sem regra; sera importado nulo ({tipo}).")

        return {
            "sac_numero": sac_numero,
            "sequencia": int(numero) if str(numero).isdigit() else 0,
            "ano": ano,
            "abertura": abertura,
            "eventos": eventos,
            "concluido": concluido,
            "cliente": cliente,
            "nota": nf,
            "acao": acao,
            "setor": setor,
            "linha_pendente": item_pendente["linha"],
            "status_pendente": norm(valor_linha(item_pendente["row"], item_pendente["cols"]["status"])),
            "aguarda_pendente": norm(valor_linha(item_pendente["row"], item_pendente["cols"].get("aguarda"))),
            "bloqueios": list(dict.fromkeys(bloqueios)),
            "avisos": list(dict.fromkeys(avisos)),
        }

    def _descricao_sac(self, grupo):
        partes = []
        secoes = self._secoes_historico_legado(grupo)
        for rotulo, linhas in secoes:
            texto = "\n".join(linhas)
            if texto:
                partes.append(f"{rotulo}:\n{texto}")
        return "\n\n".join(partes)

    def _secoes_historico_legado(self, grupo):
        relatos = []
        historico_recente = []
        pareceres = []
        solucoes = []
        vistos = set()

        def adicionar_unico(destino, texto):
            texto = norm(texto)
            if not texto:
                return
            chave = norm_ascii(texto)
            if chave in vistos:
                return
            vistos.add(chave)
            destino.append(texto)

        for item in sorted(grupo, key=lambda g: (g.get("abertura") or timezone.now(), g["linha"])):
            row_item = item["row"]
            cols_item = item["cols"]
            abertura = item.get("abertura")
            data_ref = self._data_referencia_linha_pendente(item) or abertura

            relato = norm(valor_linha(row_item, cols_item.get("relato")))
            if relato:
                relato_linhas = linhas_historico_legado(relato, abertura)
                for idx, relato_linha in enumerate(relato_linhas):
                    texto_relato = (
                        prefixar_descritivo_historico(relato_linha, "Relato do Cliente/usuário sobre o Problema")
                        if idx == 0
                        else relato_linha
                    )
                    adicionar_unico(relatos, texto_relato)

            acao_pendente = norm(valor_linha(row_item, cols_item.get("acao")))
            if acao_pendente:
                if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", acao_pendente):
                    for linha in linhas_historico_legado(acao_pendente, data_ref):
                        adicionar_unico(historico_recente, linha)
                else:
                    adicionar_unico(
                        historico_recente,
                        linha_historico(data_ref, f"Qual Ação Pendente: {padronizar_caixa_texto(acao_pendente)}"),
                    )

            for linha in linhas_historico_legado(valor_linha(row_item, cols_item.get("historico")), data_ref):
                adicionar_unico(historico_recente, linha)

            parecer = norm(valor_linha(row_item, cols_item.get("parecer")))
            if parecer:
                adicionar_unico(pareceres, linha_historico(data_ref, parecer))

            solucao = norm(valor_linha(row_item, cols_item.get("solucao")))
            if solucao:
                adicionar_unico(solucoes, linha_historico(data_ref, solucao))

        return [
            ("Relato do cliente/usuário", relatos),
            ("Histórico recente", historico_recente),
            ("Parecer tecnico interno/terceiro", pareceres),
            ("Solucao padrao", solucoes),
        ]

    def _observacao_historico_legado(self, grupo):
        blocos = []
        for rotulo, linhas in self._secoes_historico_legado(grupo):
            if rotulo not in {"Relato do cliente/usuário", "Histórico recente"}:
                continue
            texto = "\n".join(linhas)
            if texto:
                blocos.append(f"{rotulo}:\n{texto}")
        return "\n\n".join(blocos)

    def _observacao_item(self, item):
        row = item["row"]
        cols = item["cols"]
        linhas = []
        for rotulo, campo in [
            ("Parte do equipamento", "parte"),
            ("Categoria", "categoria"),
            ("Setor da origem", "origem"),
            ("Ato que gerou o problema", "ato"),
            ("Garantia", "garantia"),
            ("Mau uso", "mau_uso"),
            ("Conserto em garantia", "conserto_garantia"),
            ("Custo pecas", "custo_pecas"),
            ("Frete envio Ion", "frete_ion"),
            ("Frete envio cliente", "frete_cliente"),
            ("Custo tecnico terceiro", "custo_tecnico"),
            ("Valor manutencao cliente", "valor_manutencao"),
        ]:
            texto = norm(valor_linha(row, cols.get(campo)))
            if texto:
                linhas.append(f"{rotulo}: {texto}")
        return "\n".join(linhas)

    def _criar_ou_atualizar_sac(self, grupo, validacao):
        sac = SAC.objects.filter(empresa=self.empresa, numero=validacao["sac_numero"]).first()
        created = sac is None
        base = self._primeiro_item_com_valor(group := grupo, "contato")
        row = base["row"]
        cols = base["cols"]
        cliente = validacao["cliente"]
        nf = validacao["nota"]
        titulo = f"SAC_{validacao['sac_numero']} / {cliente.razao_social or cliente.nome} / NF {nf.numero_nf or nf.numero}"
        defaults = {
            "ano": validacao["ano"] or 0,
            "sequencia_ano": validacao["sequencia"],
            "empresa": self.empresa,
            "cliente": cliente,
            "nota_fiscal": nf,
            "data_emissao_nf": nf.data_emissao,
            "status_inicial": "Aberto",
            "status_atual": self.status_concluido if validacao["concluido"] else self.status_analise,
            "acao_em_espera": None if validacao["concluido"] else validacao["acao"],
            "setor_responsavel": self.setores.get("sac"),
            "setor_atual": None if validacao["concluido"] else validacao["setor"],
            "usuario_abertura": self.usuario,
            "contato_nome": limitar(valor_linha(row, cols["contato"]), 255),
            "telefone_1": limitar(valor_linha(row, cols["telefone"]), 30),
            "email_1": limitar(valor_linha(row, cols["email"]), 254),
            "titulo": titulo,
            "descricao": self._descricao_sac(group),
            "concluido_em": self._data_conclusao(validacao),
            "email_automatico_habilitado": False,
        }
        if created:
            sac = SAC.objects.create(numero=validacao["sac_numero"], **defaults)
        else:
            for campo, valor in defaults.items():
                setattr(sac, campo, valor)
            sac.save()
        SAC.objects.filter(pk=sac.pk).update(data_abertura=validacao["abertura"])
        sac.data_abertura = validacao["abertura"]
        self.stats["sacs_criados" if created else "sacs_atualizados"] += 1
        return sac, created

    def _data_conclusao(self, validacao):
        if not validacao["concluido"]:
            return None
        encerramentos = [e["data"] for e in validacao["eventos"] if e["label"] == "Encerrado"]
        if encerramentos:
            return max(encerramentos)
        if validacao["eventos"]:
            return max(e["data"] for e in validacao["eventos"])
        return None

    def _importar_itens(self, sac, grupo, validacao):
        resultado = {"criados": 0, "atualizados": 0, "ignorados": 0}
        for item in grupo:
            row = item["row"]
            cols = item["cols"]
            referencia = numero_texto(valor_linha(row, cols["referencia"]))
            equipamento = norm(valor_linha(row, cols["equipamento"]))
            if not referencia and not equipamento:
                continue
            nf = self._nota(numero_texto(valor_linha(row, cols["nota"]))) or validacao["nota"]
            item_nf = self._item_nf(nf, referencia, equipamento)
            if not item_nf:
                resultado["ignorados"] += 1
                self.stats["itens_ignorados"] += 1
                continue
            serie = numero_texto(valor_linha(row, cols["serie"]))
            tipo_rastreio = "SERIAL" if serie else "LOTE"
            numero_rastreio = serie or ""
            if SACItem.objects.filter(
                item_nota_fiscal=item_nf,
                tipo_rastreio=tipo_rastreio,
                numero_rastreio=numero_rastreio,
            ).exclude(sac=sac).exists():
                self._log(
                    "AVISO",
                    sac.numero,
                    item["linha"],
                    "numero_rastreio",
                    numero_rastreio,
                    "Item/rastreio ja vinculado a outro SAC; item ignorado nesta importacao.",
                    item["arquivo"],
                )
                resultado["ignorados"] += 1
                self.stats["itens_ignorados"] += 1
                continue
            tipo_ocorrencia = self._tipo_ocorrencia(valor_linha(row, cols["tipo"]))
            defaults = {
                "tipo_ocorrencia": tipo_ocorrencia,
                "quantidade_com_problema": inteiro(valor_linha(row, cols["quantidade"]), 1),
                "grupo": limitar(valor_linha(row, cols["categoria"]), 255),
                "observacao_item": self._observacao_item(item),
            }
            _, created = SACItem.objects.update_or_create(
                sac=sac,
                item_nota_fiscal=item_nf,
                tipo_rastreio=tipo_rastreio,
                numero_rastreio=numero_rastreio,
                defaults=defaults,
            )
            resultado["criados" if created else "atualizados"] += 1
            self.stats["itens_criados" if created else "itens_atualizados"] += 1
        return resultado

    def _simular_itens(self, grupo, validacao):
        resultado = {"criados": 0, "atualizados": 0, "ignorados": 0}
        sac = SAC.objects.filter(empresa=self.empresa, numero=validacao["sac_numero"]).first()
        for item in grupo:
            row = item["row"]
            cols = item["cols"]
            referencia = numero_texto(valor_linha(row, cols["referencia"]))
            equipamento = norm(valor_linha(row, cols["equipamento"]))
            if not referencia and not equipamento:
                continue
            nf = self._nota(numero_texto(valor_linha(row, cols["nota"]))) or validacao["nota"]
            item_nf = self._item_nf(nf, referencia, equipamento)
            if not item_nf:
                resultado["ignorados"] += 1
                self.stats["itens_ignorados"] += 1
                continue
            serie = numero_texto(valor_linha(row, cols["serie"]))
            tipo_rastreio = "SERIAL" if serie else "LOTE"
            numero_rastreio = serie or ""
            if SACItem.objects.filter(
                item_nota_fiscal=item_nf,
                tipo_rastreio=tipo_rastreio,
                numero_rastreio=numero_rastreio,
            ).exclude(sac=sac).exists():
                resultado["ignorados"] += 1
                self.stats["itens_ignorados"] += 1
                continue
            existe = bool(
                sac
                and SACItem.objects.filter(
                    sac=sac,
                    item_nota_fiscal=item_nf,
                    tipo_rastreio=tipo_rastreio,
                    numero_rastreio=numero_rastreio,
                ).exists()
            )
            resultado["atualizados" if existe else "criados"] += 1
            self.stats["itens_atualizados" if existe else "itens_criados"] += 1
        return resultado

    def _registrar_historicos(self, sac, validacao):
        marcador = "Importacao historica IONLAB"
        SacHistorico.objects.filter(sac=sac, acao_executada__startswith=marcador).delete()
        status_anterior = None
        setor_anterior = None
        for evento in validacao["eventos"]:
            status_novo = self.status_concluido if evento["label"] == "Encerrado" else self.status_analise
            setor_destino = None if evento["label"] == "Encerrado" else (validacao["setor"] or getattr(validacao["acao"], "setor_destino", None))
            SacHistorico.objects.create(
                sac=sac,
                usuario=self.usuario,
                data_evento=evento["data"],
                status_anterior=status_anterior,
                status_novo=status_novo,
                setor_origem=setor_anterior,
                setor_destino=setor_destino,
                acao_executada=f"{marcador} - {evento['label']}",
                observacao=evento["observacao"],
            )
            status_anterior = status_novo
            setor_anterior = setor_destino

    def _registrar_historico_legado_texto(self, sac, grupo, validacao):
        observacao = self._observacao_historico_legado(grupo)
        if not observacao:
            return
        data_evento = validacao.get("abertura") or timezone.now()
        SacHistorico.objects.create(
            sac=sac,
            usuario=self.usuario,
            data_evento=data_evento,
            status_anterior=None,
            status_novo=self.status_analise,
            setor_origem=None,
            setor_destino=self.setores.get("sac"),
            acao_executada="Importacao historica IONLAB - Histórico recente legado",
            observacao=observacao,
        )

    def _salvar_log_excel(self, resumo_linhas):
        if not self.log_output:
            return
        self.log_output.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(self.log_output) as writer:
            pd.DataFrame(resumo_linhas).to_excel(writer, sheet_name="Resumo", index=False)
            pd.DataFrame(self.logs).to_excel(writer, sheet_name="Log", index=False)

    def executar(self):
        linhas = self.carregar()
        grupos = defaultdict(list)
        for item in linhas:
            grupos[item["chave"]].append(item)

        importacao = ImportacaoLegadoSAC.objects.create(
            nome=f"IONLAB SAC legado - {'commit' if self.commit else 'simulacao'}",
            arquivo_origem="; ".join(str(a) for a in self.arquivos),
            empresa=self.empresa,
            usuario=self.usuario,
            dry_run=not self.commit,
            status="COMMIT" if self.commit else "DRY_RUN",
            total_linhas=len(linhas),
            total_sacs_planilha=len(grupos),
        )

        resumo_linhas = []
        try:
            with transaction.atomic():
                for chave, grupo in sorted(grupos.items(), key=lambda x: (x[0][1] or 0, int(x[0][0]) if str(x[0][0]).isdigit() else 0)):
                    validacao = self._validar_grupo(chave, grupo)
                    for aviso in validacao["avisos"]:
                        self._log("AVISO", validacao["sac_numero"], "", "validacao", "", aviso, grupo[0]["arquivo"])
                    if validacao["bloqueios"]:
                        for bloqueio in validacao["bloqueios"]:
                            self._log("BLOQUEIO", validacao["sac_numero"], "", "validacao", "", bloqueio, grupo[0]["arquivo"])
                        self.stats["sacs_pulados"] += 1
                        resumo_linhas.append({"sac": validacao["sac_numero"], "resultado": "BLOQUEADO", "detalhe": "; ".join(validacao["bloqueios"])})
                        continue
                    if self.commit:
                        sac, created = self._criar_ou_atualizar_sac(grupo, validacao)
                        itens = self._importar_itens(sac, grupo, validacao)
                        self._registrar_historicos(sac, validacao)
                        self._registrar_historico_legado_texto(sac, grupo, validacao)
                    else:
                        created = not SAC.objects.filter(empresa=self.empresa, numero=validacao["sac_numero"]).exists()
                        itens = self._simular_itens(grupo, validacao)
                        self.stats["sacs_criados" if created else "sacs_atualizados"] += 1
                    self.importados.append(validacao["sac_numero"])
                    resumo_linhas.append({
                        "sac": validacao["sac_numero"],
                        "resultado": "CRIAR" if created else "ATUALIZAR",
                        "concluido": validacao["concluido"],
                        "status_pendente": validacao.get("status_pendente", ""),
                        "linha_pendente": validacao.get("linha_pendente", ""),
                        "aguarda_pendente": validacao.get("aguarda_pendente", ""),
                        "setor_atual": getattr(validacao.get("setor"), "nome", "") if validacao.get("setor") else "",
                        "acao_em_espera": getattr(validacao.get("acao"), "nome", "") if validacao.get("acao") else "",
                        "eventos_cronologia": len(validacao["eventos"]),
                        "itens": json.dumps(itens, ensure_ascii=False),
                    })
                if not self.commit:
                    transaction.set_rollback(False)
        except Exception as exc:
            importacao.status = "ERRO"
            importacao.detalhes = {"erro": str(exc), "logs": self.logs}
            importacao.save()
            raise

        importacao.sacs_criados = self.stats["sacs_criados"]
        importacao.sacs_atualizados = self.stats["sacs_atualizados"]
        importacao.itens_criados = self.stats["itens_criados"]
        importacao.itens_atualizados = self.stats["itens_atualizados"]
        importacao.itens_ignorados = self.stats["itens_ignorados"]
        importacao.sacs_pulados = self.stats["sacs_pulados"]
        importacao.detalhes = {
            "commit": self.commit,
            "arquivos": [str(a) for a in self.arquivos],
            "logs": self.logs[:500],
            "log_output": str(self.log_output or ""),
        }
        importacao.save()
        self._salvar_log_excel(resumo_linhas)
        return importacao


class Command(BaseCommand):
    help = "Importa SACs historicos Ionlab 2024-2026, com consolidacao entre planilhas e log de bloqueios."

    def add_arguments(self, parser):
        parser.add_argument("arquivos", nargs="+", help="Planilhas ionlab_2024.xlsx e ionlab_2025_2026.xlsx")
        parser.add_argument("--commit", action="store_true", help="Grava no banco. Sem esta flag, roda apenas simulacao.")
        parser.add_argument("--log-output", default="", help="Caminho para gerar log Excel da simulacao/importacao.")
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

        importador = ImportadorIonlabSAC(
            arquivos=options["arquivos"],
            commit=options["commit"],
            log_output=options.get("log_output") or "",
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
            "log_output": str(importador.log_output or ""),
        }
        self.stdout.write(json.dumps(resumo, ensure_ascii=False, indent=2))
