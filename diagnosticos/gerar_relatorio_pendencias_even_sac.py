from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path

import django
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from core.models import Cliente, Empresa, ItemNotaFiscal, NotaFiscal


PLANILHA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Users\comer\Desktop\DAY_BY_DAY\EVEN_SAC.xlsx")
EMPRESA_CODIGO = "EVENLAB"
SUFIXO = re.sub(r"[^a-zA-Z0-9_]+", "_", PLANILHA.stem.lower())
SAIDA_CSV = ROOT / "diagnosticos" / f"relatorio_pendencias_import_{SUFIXO}.csv"
SAIDA_MD = ROOT / "diagnosticos" / f"relatorio_pendencias_import_{SUFIXO}.md"
SAIDA_XLSX = ROOT / "diagnosticos" / f"relatorio_pendencias_import_{SUFIXO}.xlsx"


def norm(valor):
    if pd.isna(valor):
        return ""
    texto = str(valor or "").strip()
    texto = texto.replace("\xa0", " ")
    return re.sub(r"\s+", " ", texto)


def norm_key(valor):
    texto = norm(valor).lower()
    troca = str.maketrans("áàãâäéèêëíìîïóòõôöúùûüç", "aaaaaeeeeiiiiooooouuuuc")
    return texto.translate(troca)


def numero_texto(valor):
    texto = norm(valor)
    if not texto:
        return ""
    if re.fullmatch(r"\d+\.0", texto):
        return texto[:-2]
    try:
        numero = float(texto)
        if numero.is_integer():
            return str(int(numero))
    except Exception:
        pass
    return texto


def item_na_base(nf, referencia, equipamento):
    if nf is None:
        return False
    qs = ItemNotaFiscal.objects.filter(nota_fiscal=nf)
    if referencia and qs.filter(codigo_produto__iexact=referencia).exists():
        return True
    if equipamento and qs.filter(descricao_item__iexact=equipamento).exists():
        return True
    return False


def pendencia(linhas, sac, tipo, detalhe, coluna="", valor_atual="", referencia="", equipamento="", severidade="Bloqueia"):
    linhas.append(
        {
            "SAC": sac,
            "Severidade": severidade,
            "Tipo da pendencia": tipo,
            "Problema": detalhe,
            "Coluna / campo": coluna,
            "Valor atual": valor_atual,
            "Referencia": referencia,
            "Equipamento / item": equipamento,
        }
    )


def main():
    empresa = Empresa.objects.filter(codigo__iexact=EMPRESA_CODIGO).first()
    if empresa is None:
        raise SystemExit(f"Empresa {EMPRESA_CODIGO} nao encontrada.")

    df = pd.read_excel(PLANILHA, sheet_name="2025", dtype=object)
    linhas = []

    for sac_num, grupo in df.groupby("SAC Nº", dropna=False):
        sac = numero_texto(sac_num) or "SEM_NUMERO"
        primeira = grupo.iloc[0]

        codigo_cliente = numero_texto(primeira.get("Cód. Cli"))
        cliente_nome = norm(primeira.get("Cliente"))
        cliente = None
        if codigo_cliente:
            cliente = Cliente.objects.filter(empresa=empresa, codigo_interno=codigo_cliente).first()
        if not codigo_cliente:
            pendencia(
                linhas,
                sac,
                "Cliente nao identificado",
                "Sem Cód. Cli na planilha. Precisa informar o código do cliente para vincular ao cadastro.",
                "Cód. Cli",
                codigo_cliente,
                equipamento=cliente_nome,
            )
        elif cliente is None:
            pendencia(
                linhas,
                sac,
                "Cliente nao encontrado na base",
                "O Cód. Cli da planilha não foi encontrado para a empresa EVENLAB.",
                "Cód. Cli",
                codigo_cliente,
                equipamento=cliente_nome,
            )

        nf_numero = numero_texto(primeira.get("Nota Fiscal Venda"))
        nf = None
        if nf_numero:
            nf = NotaFiscal.objects.filter(empresa=empresa, numero_nf=nf_numero).first() or NotaFiscal.objects.filter(empresa=empresa, numero=nf_numero).first()
        if not nf_numero:
            pendencia(
                linhas,
                sac,
                "Nota fiscal nao informada",
                "Sem Nota Fiscal Venda na planilha. Precisa informar a NF para vincular itens e dados oficiais.",
                "Nota Fiscal Venda",
                nf_numero,
            )
        elif nf is None:
            pendencia(
                linhas,
                sac,
                "Nota fiscal nao encontrada na base",
                "A Nota Fiscal Venda da planilha não foi encontrada para a empresa EVENLAB.",
                "Nota Fiscal Venda",
                nf_numero,
            )

        for idx, row in grupo.iterrows():
            referencia = numero_texto(row.get("Referencia"))
            equipamento = norm(row.get("Equipamento "))
            categoria = norm(row.get("Categoria"))
            rastreio = numero_texto(row.get("Nº Série"))
            item_label = f"linha Excel {idx + 2}"

            if nf is not None and (referencia or equipamento) and not item_na_base(nf, referencia, equipamento):
                pendencia(
                    linhas,
                    sac,
                    "Item nao encontrado na nota fiscal",
                    f"O item informado na {item_label} não foi localizado na base de itens da NF {nf_numero}.",
                    "Referencia / Equipamento",
                    f"{referencia} / {equipamento}",
                    referencia=referencia,
                    equipamento=equipamento,
                )

            if norm_key(categoria) == "equipamento":
                if not rastreio or rastreio.upper() in {"S/N", "SN", "SEM SERIE", "SEM SÉRIE"}:
                    pendencia(
                        linhas,
                        sac,
                        "Equipamento sem numero de serie",
                        f"Categoria é Equipamento na {item_label}, mas Nº Série está vazio ou inválido. Equipamento precisa de serial.",
                        "Nº Série",
                        rastreio,
                        referencia=referencia,
                        equipamento=equipamento,
                    )
            elif False and (not rastreio or rastreio.upper() in {"S/N", "SN"}):
                pendencia(
                    linhas,
                    sac,
                    "Lote sem identificador",
                    f"Item não é Equipamento na {item_label}; será importado como LOTE, mas Nº Série/lote não foi informado.",
                    "Nº Série",
                    rastreio,
                    referencia=referencia,
                    equipamento=equipamento,
                    severidade="Conferir",
                )

    linhas.sort(key=lambda item: (int(item["SAC"]) if str(item["SAC"]).isdigit() else 999999, item["Severidade"], item["Tipo da pendencia"]))

    SAIDA_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["SAC", "Severidade", "Tipo da pendencia", "Problema", "Coluna / campo", "Valor atual", "Referencia", "Equipamento / item"], delimiter=";")
        writer.writeheader()
        writer.writerows(linhas)

    bloqueios = [l for l in linhas if l["Severidade"] == "Bloqueia"]
    conferir = [l for l in linhas if l["Severidade"] != "Bloqueia"]
    resumo_geral = pd.DataFrame(
        [
            ["Arquivo analisado", str(PLANILHA)],
            ["Total de pendencias", len(linhas)],
            ["SACs com pendencias bloqueantes", len(set(l["SAC"] for l in bloqueios))],
            ["Linhas bloqueantes", len(bloqueios)],
            ["Linhas para conferir", len(conferir)],
            ["Itens nao equipamento sem lote", "Removidos do relatorio; nao bloqueiam importacao"],
        ],
        columns=["Indicador", "Valor"],
    )
    if linhas:
        pendencias_df = pd.DataFrame(linhas)
        resumo_tipos = (
            pendencias_df.groupby(["Severidade", "Tipo da pendencia"], dropna=False)
            .size()
            .reset_index(name="Quantidade")
        )
    else:
        pendencias_df = pd.DataFrame(columns=["SAC", "Severidade", "Tipo da pendencia", "Problema", "Coluna / campo", "Valor atual", "Referencia", "Equipamento / item"])
        resumo_tipos = pd.DataFrame(columns=["Severidade", "Tipo da pendencia", "Quantidade"])

    with pd.ExcelWriter(SAIDA_XLSX, engine="openpyxl") as writer:
        resumo_geral.to_excel(writer, sheet_name="Resumo", index=False, startrow=0)
        resumo_tipos.to_excel(writer, sheet_name="Resumo", index=False, startrow=len(resumo_geral) + 3)
        pendencias_df.to_excel(writer, sheet_name="Pendencias", index=False)

        wb = writer.book
        for ws in wb.worksheets:
            ws.freeze_panes = "A2"
            for row in ws.iter_rows(min_row=1, max_row=1):
                for cell in row:
                    cell.font = cell.font.copy(bold=True)
            for col in ws.columns:
                col_letter = col[0].column_letter
                max_len = max(len(str(cell.value or "")) for cell in col)
                ws.column_dimensions[col_letter].width = min(max(max_len + 2, 12), 65)

    with SAIDA_MD.open("w", encoding="utf-8") as f:
        f.write("# Relatorio de pendencias para importacao - EVEN SAC\n\n")
        f.write(f"Arquivo analisado: `{PLANILHA}`\n\n")
        f.write(f"- SACs com pendencias bloqueantes: {len(set(l['SAC'] for l in bloqueios))}\n")
        f.write(f"- Linhas bloqueantes: {len(bloqueios)}\n")
        f.write(f"- Linhas para conferir: {len(conferir)}\n\n")
        f.write("## Pendencias\n\n")
        f.write("| SAC | Severidade | Tipo | Problema | Campo | Valor atual | Referencia | Item |\n")
        f.write("|---:|---|---|---|---|---|---|---|\n")
        for item in linhas:
            valores = [
                item["SAC"],
                item["Severidade"],
                item["Tipo da pendencia"],
                item["Problema"],
                item["Coluna / campo"],
                item["Valor atual"],
                item["Referencia"],
                item["Equipamento / item"],
            ]
            f.write("| " + " | ".join(str(v).replace("|", "/") for v in valores) + " |\n")

    print(f"CSV={SAIDA_CSV}")
    print(f"MD={SAIDA_MD}")
    print(f"XLSX={SAIDA_XLSX}")
    print(f"TOTAL={len(linhas)} BLOQUEIA={len(bloqueios)} CONFERIR={len(conferir)}")


if __name__ == "__main__":
    main()
