from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import SAC


def _fmt_data(valor):
    if not valor:
        return "-"
    try:
        return valor.strftime("%d/%m/%Y")
    except Exception:
        return str(valor)


def _numero_sac(sac):
    numero = str(getattr(sac, "numero", "") or "").strip()
    ano = str(getattr(sac, "ano", "") or "").strip()
    if not numero:
        return f"SAC ID {sac.id}"
    if "/" in numero:
        return numero
    try:
        numero = str(int(numero)).zfill(3)
    except Exception:
        pass
    return f"{numero}/{ano}" if ano else numero


def _tempo_uso_formatado(dias):
    if dias is None:
        return "-"
    try:
        dias = max(int(dias), 0)
    except Exception:
        return "-"
    meses = dias // 30
    resto = dias % 30
    if meses and resto:
        return f"{meses} meses e {resto} dias"
    if meses:
        return f"{meses} meses"
    return f"{resto} dias"


class Command(BaseCommand):
    help = "Audita dados oficiais do SAC: NF, data da NF, NF revenda e tempo de uso."

    def add_arguments(self, parser):
        parser.add_argument(
            "--detalhar-ok",
            action="store_true",
            help="Também lista SACs sem inconsistência.",
        )
        parser.add_argument(
            "--limite",
            type=int,
            default=100,
            help="Limite de SACs exibidos por grupo. Padrão: 100.",
        )

    def handle(self, *args, **options):
        limite = options["limite"]
        detalhar_ok = options["detalhar_ok"]

        qs = (
            SAC.objects
            .select_related("empresa", "cliente", "nota_fiscal", "status_atual", "acao_em_espera", "setor_atual")
            .order_by("id")
        )

        total = qs.count()
        problemas = []
        ok = []

        for sac in qs:
            nf = getattr(sac, "nota_fiscal", None)
            data_nf_sac = getattr(sac, "data_emissao_nf", None)
            data_nf_real = getattr(nf, "data_emissao", None) if nf else None
            data_revenda = getattr(sac, "data_emissao_nf_revenda", None)
            numero_revenda = getattr(sac, "numero_nf_revenda", None)
            tempo_uso = getattr(sac, "tempo_uso_dias", None)

            erros = []

            if not getattr(sac, "data_abertura", None):
                erros.append("sem data de abertura")

            if not getattr(sac, "nota_fiscal_id", None):
                erros.append("sem nota fiscal vinculada")

            if nf and not data_nf_real and not data_nf_sac:
                erros.append("NF sem data de emissão")

            if nf and data_nf_real and data_nf_sac and data_nf_real != data_nf_sac:
                erros.append(
                    f"data_emissao_nf do SAC diferente da NF: SAC={_fmt_data(data_nf_sac)} / NF={_fmt_data(data_nf_real)}"
                )

            if numero_revenda and not data_revenda:
                erros.append("número NF revenda preenchido sem data NF revenda")

            if data_revenda and not numero_revenda:
                erros.append("data NF revenda preenchida sem número NF revenda")

            if tempo_uso is None:
                erros.append("sem tempo_uso_dias")

            if tempo_uso is not None and getattr(sac, "data_abertura", None):
                data_abertura = sac.data_abertura.date() if hasattr(sac.data_abertura, "date") else sac.data_abertura
                data_base = data_revenda or data_nf_sac or data_nf_real
                if data_base:
                    esperado = max((data_abertura - data_base).days, 0)
                    try:
                        tempo_int = int(tempo_uso)
                    except Exception:
                        tempo_int = None
                    if tempo_int != esperado:
                        erros.append(
                            f"tempo_uso_dias divergente: atual={tempo_uso} / esperado={esperado}"
                        )

            registro = {
                "id": sac.id,
                "numero": _numero_sac(sac),
                "cliente": getattr(getattr(sac, "cliente", None), "razao_social", None)
                           or getattr(getattr(sac, "cliente", None), "nome", None)
                           or "-",
                "nf": getattr(nf, "numero_nf", None) or getattr(nf, "numero", None) or "-",
                "data_nf": _fmt_data(data_nf_sac or data_nf_real),
                "nf_revenda": numero_revenda or "-",
                "data_revenda": _fmt_data(data_revenda),
                "tempo_uso": _tempo_uso_formatado(tempo_uso),
                "erros": erros,
            }

            if erros:
                problemas.append(registro)
            else:
                ok.append(registro)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("AUDITORIA DE DADOS OFICIAIS DO SAC"))
        self.stdout.write(f"Total de SACs analisados: {total}")
        self.stdout.write(self.style.SUCCESS(f"SACs OK: {len(ok)}"))
        if problemas:
            self.stdout.write(self.style.ERROR(f"SACs com inconsistência: {len(problemas)}"))
        else:
            self.stdout.write(self.style.SUCCESS("SACs com inconsistência: 0"))

        if problemas:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("INCONSISTÊNCIAS ENCONTRADAS"))
            for item in problemas[:limite]:
                self.stdout.write("-" * 72)
                self.stdout.write(f"SAC: {item['numero']} | ID: {item['id']} | Cliente: {item['cliente']}")
                self.stdout.write(f"NF: {item['nf']} | Data NF: {item['data_nf']}")
                self.stdout.write(f"NF Revenda: {item['nf_revenda']} | Data Revenda: {item['data_revenda']}")
                self.stdout.write(f"Tempo de uso: {item['tempo_uso']}")
                for erro in item["erros"]:
                    self.stdout.write(self.style.ERROR(f"  - {erro}"))

            if len(problemas) > limite:
                self.stdout.write("")
                self.stdout.write(f"... mais {len(problemas) - limite} inconsistência(s) não exibida(s). Use --limite para aumentar.")

        if detalhar_ok and ok:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("SACS OK"))
            for item in ok[:limite]:
                self.stdout.write("-" * 72)
                self.stdout.write(f"SAC: {item['numero']} | ID: {item['id']} | Cliente: {item['cliente']}")
                self.stdout.write(f"NF: {item['nf']} | Data NF: {item['data_nf']}")
                self.stdout.write(f"NF Revenda: {item['nf_revenda']} | Data Revenda: {item['data_revenda']}")
                self.stdout.write(f"Tempo de uso: {item['tempo_uso']}")

        self.stdout.write("")
        if problemas:
            self.stdout.write(self.style.WARNING("Auditoria concluída com alertas."))
        else:
            self.stdout.write(self.style.SUCCESS("Auditoria concluída sem inconsistências."))
