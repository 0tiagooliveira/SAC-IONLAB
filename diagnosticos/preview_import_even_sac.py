from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import django
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from core.models import AcaoEmEspera, Cliente, Empresa, ItemNotaFiscal, NotaFiscal, Setor, StatusSAC, TipoOcorrencia


PLANILHA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Users\comer\Desktop\DAY_BY_DAY\EVEN_SAC.xlsx")
EMPRESA_CODIGO = "EVENLAB"


ACAO_PADRAO_MAP = {
    "negociação com cliente - troca/cancelamento": {
        "acao": "Aguardando Contato com Cliente - SAC",
        "setor": "Licitação",
        "observacao": "Ação equivalente usada com setor de destino Licitação, conforme regra definida.",
    },
    "negociacao com cliente - troca/cancelamento": {
        "acao": "Aguardando Contato com Cliente - SAC",
        "setor": "Licitação",
        "observacao": "Ação equivalente usada com setor de destino Licitação, conforme regra definida.",
    },
    "aguardando faturamento/expedição": {
        "acao": "Aguardando Emissão da Nota fiscal (Saída)",
        "setor": "Logística",
        "observacao": "",
    },
    "aguardando faturamento/expedicao": {
        "acao": "Aguardando Emissão da Nota fiscal (Saída)",
        "setor": "Logística",
        "observacao": "",
    },
    "sac - emitir pedido cliente": {
        "acao": "Aguardando Emissão do Pedido (Saída)",
        "setor": "SAC",
        "observacao": "",
    },
}


def norm(valor):
    if pd.isna(valor):
        return ""
    texto = str(valor or "").strip()
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto


def norm_key(valor):
    texto = norm(valor).lower()
    troca = str.maketrans("áàãâäéèêëíìîïóòõôöúùûüç", "aaaaaeeeeiiiiooooouuuuc")
    return texto.translate(troca)


def vazio(valor):
    if pd.isna(valor):
        return True
    return norm(valor) == ""


def numero_texto(valor):
    if vazio(valor):
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    texto = norm(valor)
    if re.fullmatch(r"\d+\.0", texto):
        return texto[:-2]
    return texto


def limpar_tipo_ocorrencia(valor):
    texto = norm(valor)
    return re.sub(r"^\d+\s*-\s*", "", texto).strip()


def historico_formatado(texto):
    if vazio(texto):
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


def resolve_first(model, **kwargs):
    return model.objects.filter(**kwargs).first()


def main():
    df = pd.read_excel(PLANILHA, sheet_name="2025", dtype=object)
    empresa = Empresa.objects.filter(codigo__iexact=EMPRESA_CODIGO).first()
    if not empresa:
        raise SystemExit(f"Empresa {EMPRESA_CODIGO} nao encontrada.")

    acoes = {norm_key(a.nome): a for a in AcaoEmEspera.objects.filter(ativo=True).select_related("setor_destino")}
    setores = {norm_key(s.nome): s for s in Setor.objects.filter(ativo=True)}
    tipos = {norm_key(t.nome): t for t in TipoOcorrencia.objects.filter(ativo=True).select_related("setor", "acao_em_espera")}
    status_concluido = StatusSAC.objects.filter(nome__iexact="Concluído", ativo=True).first() or StatusSAC.objects.filter(nome__iexact="Concluido", ativo=True).first()

    sac_groups = df.groupby("SAC Nº", dropna=False)
    pendencias = defaultdict(list)
    action_preview = {}
    tipo_preview = {}
    item_counts = {}
    historico_samples = {}
    cliente_encontrado = 0
    nota_encontrada = 0
    item_nf_encontrado = 0
    equipamento_sem_serial = []
    lote_sem_identificador = []

    for sac_num, grupo in sac_groups:
        sac_numero = numero_texto(sac_num)
        item_counts[sac_numero] = len(grupo)
        primeira = grupo.iloc[0]

        codigo_cliente = numero_texto(primeira.get("Cód. Cli"))
        if codigo_cliente and Cliente.objects.filter(empresa=empresa, codigo_interno=codigo_cliente).exists():
            cliente_encontrado += 1
        elif codigo_cliente:
            pendencias["clientes_nao_encontrados"].append({"sac": sac_numero, "codigo": codigo_cliente, "cliente": norm(primeira.get("Cliente"))})

        nf_numero = numero_texto(primeira.get("Nota Fiscal Venda"))
        nf = None
        if nf_numero:
            nf = NotaFiscal.objects.filter(empresa=empresa, numero_nf=nf_numero).first() or NotaFiscal.objects.filter(empresa=empresa, numero=nf_numero).first()
        if nf:
            nota_encontrada += 1
        elif nf_numero:
            pendencias["notas_nao_encontradas"].append({"sac": sac_numero, "nota": nf_numero})

        status = norm(primeira.get("STATUS"))
        acao_padrao = norm(primeira.get("Ação Padrão"))
        if norm_key(status) == "concluido":
            action_preview[sac_numero] = {"status": "Concluído", "acao": "", "setor": "", "regra": "concluido_sem_acao_futura"}
        elif acao_padrao:
            regra = ACAO_PADRAO_MAP.get(norm_key(acao_padrao))
            if not regra:
                pendencias["acoes_padrao_sem_mapa"].append({"sac": sac_numero, "acao_padrao": acao_padrao})
            else:
                acao_obj = acoes.get(norm_key(regra["acao"]))
                setor_obj = setores.get(norm_key(regra["setor"]))
                if not acao_obj:
                    pendencias["acoes_sistema_nao_encontradas"].append({"sac": sac_numero, "acao": regra["acao"]})
                if not setor_obj:
                    pendencias["setores_sistema_nao_encontrados"].append({"sac": sac_numero, "setor": regra["setor"]})
                action_preview[sac_numero] = {
                    "status": "Em Análise",
                    "acao": regra["acao"],
                    "setor": regra["setor"],
                    "regra": acao_padrao,
                    "observacao": regra["observacao"],
                }
        else:
            action_preview[sac_numero] = {"status": "Em Análise", "acao": "", "setor": norm(primeira.get("Aguarda ação de")), "regra": "sem_acao_padrao"}

        hist = historico_formatado(primeira.get("Historico Recente"))
        if hist and len(historico_samples) < 5:
            historico_samples[sac_numero] = hist.splitlines()[:5]

        for _, row in grupo.iterrows():
            tipo_nome = limpar_tipo_ocorrencia(row.get("Tipo ocorrência"))
            if tipo_nome:
                tipo = tipos.get(norm_key(tipo_nome))
                if tipo:
                    tipo_preview[tipo_nome] = {
                        "tipo_sistema": tipo.nome,
                        "setor_origem": getattr(getattr(tipo, "setor", None), "nome", ""),
                        "acao": getattr(getattr(tipo, "acao_em_espera", None), "nome", ""),
                    }
                else:
                    pendencias["tipos_ocorrencia_nao_encontrados"].append({"sac": sac_numero, "tipo": tipo_nome})

            categoria = norm_key(row.get("Categoria"))
            rastreio = numero_texto(row.get("Nº Série"))
            referencia = numero_texto(row.get("Referencia"))
            equipamento = norm(row.get("Equipamento "))
            if categoria == "equipamento":
                if not rastreio or rastreio.upper() in {"S/N", "SN", "SEM SERIE", "SEM SÉRIE"}:
                    equipamento_sem_serial.append({"sac": sac_numero, "referencia": referencia, "equipamento": equipamento})
            else:
                if not rastreio or rastreio.upper() in {"S/N", "SN"}:
                    lote_sem_identificador.append({"sac": sac_numero, "categoria": norm(row.get("Categoria")), "referencia": referencia, "equipamento": equipamento})

            if nf and (referencia or equipamento):
                qs = ItemNotaFiscal.objects.filter(nota_fiscal=nf)
                if referencia:
                    qs_ref = qs.filter(codigo_produto__iexact=referencia)
                    if qs_ref.exists():
                        item_nf_encontrado += 1
                        continue
                if equipamento and qs.filter(descricao_item__iexact=equipamento).exists():
                    item_nf_encontrado += 1
                else:
                    pendencias["itens_nf_nao_encontrados"].append({"sac": sac_numero, "nota": nf_numero, "referencia": referencia, "equipamento": equipamento[:90]})

    multi_itens = dict(sorted(item_counts.items(), key=lambda item: item[1], reverse=True)[:15])

    resultado = {
        "arquivo": str(PLANILHA),
        "empresa": getattr(empresa, "razao_social", EMPRESA_CODIGO),
        "linhas_planilha_itens": int(len(df)),
        "sacs_unicos": int(df["SAC Nº"].nunique()),
        "maior_qtd_itens_mesmo_sac": max(item_counts.values()) if item_counts else 0,
        "sacs_com_multiplos_itens_top15": multi_itens,
        "clientes_encontrados_por_sac": cliente_encontrado,
        "notas_encontradas_por_sac": nota_encontrada,
        "itens_nf_encontrados_por_linha": item_nf_encontrado,
        "status_planilha": dict(Counter(norm(v) for v in df["STATUS"].dropna())),
        "acao_padrao_planilha": dict(Counter(norm(v) for v in df["Ação Padrão"].dropna())),
        "acao_preview_amostra": dict(list(action_preview.items())[:20]),
        "tipo_ocorrencia_preview": tipo_preview,
        "equipamento_sem_serial_qtd": len(equipamento_sem_serial),
        "equipamento_sem_serial_amostra": equipamento_sem_serial[:30],
        "lote_sem_identificador_qtd": len(lote_sem_identificador),
        "lote_sem_identificador_amostra": lote_sem_identificador[:20],
        "historico_formatado_amostra": historico_samples,
        "pendencias_resumo": {k: len(v) for k, v in pendencias.items()},
        "pendencias_amostra": {k: v[:20] for k, v in pendencias.items()},
        "status_concluido_encontrado": bool(status_concluido),
    }
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
