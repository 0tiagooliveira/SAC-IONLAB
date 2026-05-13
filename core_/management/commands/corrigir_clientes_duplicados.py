from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Cliente, ClienteContato, NotaFiscal, SAC


def normalizar_codigo_excel(valor):
    if valor in (None, ''):
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        numero = float(texto.replace(',', '.'))
        if numero.is_integer():
            return str(int(numero))
    except (TypeError, ValueError):
        pass
    if texto.endswith('.0'):
        return texto[:-2]
    return texto


CAMPOS_CLIENTE = [
    'nome',
    'razao_social',
    'uf',
    'classificacao_financeira',
    'ultima_entrega_mpm',
    'contato_nome',
    'email_1',
    'email_2',
    'telefone',
    'whatsapp',
]


class Command(BaseCommand):
    help = 'Consolida clientes duplicados por empresa + código normalizado, removendo códigos com .0 e preservando vínculos.'

    def handle(self, *args, **options):
        total_grupos = 0
        total_mesclados = 0
        total_excluidos = 0
        total_notas = 0
        total_sacs = 0
        total_contatos = 0
        total_codigos_ajustados = 0

        clientes = list(Cliente.objects.select_related('empresa').order_by('empresa_id', 'id'))
        grupos = {}
        for cliente in clientes:
            codigo_norm = normalizar_codigo_excel(cliente.codigo_interno)
            if not codigo_norm:
                continue
            grupos.setdefault((cliente.empresa_id, codigo_norm), []).append(cliente)

        for (empresa_id, codigo_norm), grupo in grupos.items():
            if not grupo:
                continue

            precisa_ajustar = len(grupo) > 1 or any((c.codigo_interno or '').strip() != codigo_norm for c in grupo)
            if not precisa_ajustar:
                continue

            total_grupos += 1

            def peso(cliente):
                codigo_atual = (cliente.codigo_interno or '').strip()
                referencias = (
                    NotaFiscal.objects.filter(cliente=cliente).count()
                    + SAC.objects.filter(cliente=cliente).count()
                    + ClienteContato.objects.filter(cliente=cliente).count()
                )
                preferencia_codigo = 0 if codigo_atual == codigo_norm else 1
                nome_preenchido = 0 if (cliente.razao_social or cliente.nome) else 1
                return (preferencia_codigo, nome_preenchido, -referencias, cliente.id)

            grupo.sort(key=peso)
            principal = grupo[0]
            secundarios = grupo[1:]

            with transaction.atomic():
                if (principal.codigo_interno or '').strip() != codigo_norm:
                    principal.codigo_interno = codigo_norm
                    total_codigos_ajustados += 1

                for secundario in secundarios:
                    for campo in CAMPOS_CLIENTE:
                        valor_principal = getattr(principal, campo)
                        valor_secundario = getattr(secundario, campo)
                        if (valor_principal in (None, '')) and (valor_secundario not in (None, '')):
                            setattr(principal, campo, valor_secundario)

                    notas_qs = NotaFiscal.objects.filter(cliente=secundario)
                    notas_movidas = notas_qs.count()
                    if notas_movidas:
                        notas_qs.update(cliente=principal)
                        total_notas += notas_movidas

                    sacs_qs = SAC.objects.filter(cliente=secundario)
                    sacs_movidos = sacs_qs.count()
                    if sacs_movidos:
                        sacs_qs.update(cliente=principal)
                        total_sacs += sacs_movidos

                    contatos_qs = ClienteContato.objects.filter(cliente=secundario)
                    contatos_movidos = contatos_qs.count()
                    if contatos_movidos:
                        contatos_qs.update(cliente=principal)
                        total_contatos += contatos_movidos

                principal.save()

                for secundario in secundarios:
                    secundario.delete()
                    total_excluidos += 1
                    total_mesclados += 1

        self.stdout.write(self.style.SUCCESS('Correção de clientes duplicados concluída.'))
        self.stdout.write(f'Grupos consolidados: {total_grupos}')
        self.stdout.write(f'Clientes mesclados: {total_mesclados}')
        self.stdout.write(f'Clientes excluídos: {total_excluidos}')
        self.stdout.write(f'Notas fiscais reapontadas: {total_notas}')
        self.stdout.write(f'SACs reapontados: {total_sacs}')
        self.stdout.write(f'Contatos reapontados: {total_contatos}')
        self.stdout.write(f'Códigos ajustados para formato sem .0: {total_codigos_ajustados}')
