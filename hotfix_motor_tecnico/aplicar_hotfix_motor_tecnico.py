# -*- coding: utf-8 -*-
"""
Hotfix Motor Técnico - Assistência Técnica
Aplica blindagem na regra de inspeção física/funcional:
- exige FluxoAcaoSetor ativo e completo para o destino calculado;
- impede fallback silencioso por nome parecido;
- registra histórico com destino vindo do fluxo validado;
- mantém layout e demais regras existentes.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import sys

ROOT = Path.cwd()
VIEW = ROOT / "core" / "views_assistencia_tecnica.py"

if not VIEW.exists():
    print(f"ERRO: arquivo não encontrado: {VIEW}")
    print("Execute este script dentro da raiz do projeto SAC_Intranet_oficial.")
    sys.exit(1)

text = VIEW.read_text(encoding="utf-8")
backup = VIEW.with_suffix(".py.bak_motor_tecnico_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
backup.write_text(text, encoding="utf-8")
print(f"Backup criado: {backup}")

helper_marker = "def _destinos(r):\n"
new_helper = r'''
def _resolver_fluxo_inspecao_tecnica(sac, resultado):
    """Resolve e valida o FluxoAcaoSetor exato da inspeção técnica.

    A regra técnica calcula a DECISÃO de negócio: dentro ou fora da garantia.
    O ENCAMINHAMENTO precisa existir no cadastro FluxoAcaoSetor, sem destino
    silencioso por aproximação. Se faltar status, ação ou setor, o salvamento é
    bloqueado com mensagem clara.
    """
    if not sac or not getattr(sac, 'acao_em_espera_id', None):
        return None, None, None, ['Ação atual do SAC não encontrada.']

    st_esperado, ac_esperada, se_esperado, faltam_base = _destinos(resultado)
    if faltam_base:
        return None, None, None, [
            'Cadastro base ausente para o destino calculado: ' + '; '.join(faltam_base)
        ]

    qs = FluxoAcaoSetor.objects.filter(
        ativo=True,
        acao_atual=sac.acao_em_espera,
        status_destino=st_esperado,
        proxima_acao=ac_esperada,
        proximo_setor=se_esperado,
    ).select_related('status_destino', 'proxima_acao', 'proximo_setor', 'setor_atual')

    fluxo = None
    if getattr(sac, 'setor_atual_id', None):
        fluxo = qs.filter(setor_atual=sac.setor_atual).first()
    if fluxo is None:
        fluxo = qs.filter(setor_atual__isnull=True).first()

    if fluxo is None:
        return None, None, None, [
            'Fluxo não configurado no FluxoAcaoSetor para a decisão técnica calculada.',
            f"Ação atual: {_nome(sac.acao_em_espera)}",
            f"Setor atual: {_nome(sac.setor_atual)}",
            f"Destino esperado: Status '{resultado['status']}' / Ação '{resultado['acao']}' / Setor '{resultado['setor']}'.",
        ]

    faltam = []
    if not getattr(fluxo, 'status_destino_id', None):
        faltam.append('Status destino não configurado no FluxoAcaoSetor.')
    if not getattr(fluxo, 'proxima_acao_id', None):
        faltam.append('Próxima ação não configurada no FluxoAcaoSetor.')
    if not getattr(fluxo, 'proximo_setor_id', None):
        faltam.append('Próximo setor não configurado no FluxoAcaoSetor.')
    if faltam:
        return None, None, None, faltam

    return fluxo.status_destino, fluxo.proxima_acao, fluxo.proximo_setor, []

'''

if "def _resolver_fluxo_inspecao_tecnica" not in text:
    idx = text.find(helper_marker)
    if idx == -1:
        print("ERRO: não encontrei o ponto de inserção antes de def _destinos(r).")
        sys.exit(1)
    text = text[:idx] + new_helper + text[idx:]
    print("Helper _resolver_fluxo_inspecao_tecnica inserido.")
else:
    print("Helper _resolver_fluxo_inspecao_tecnica já existia; não inseri duplicado.")

old = """            st, ac, se, faltam = _destinos(r)\n            if faltam:\n                messages.error(request, 'Fluxo não configurado: ' + '; '.join(faltam))\n                return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')\n"""
new = """            st, ac, se, faltam = _resolver_fluxo_inspecao_tecnica(sac, r)\n            if faltam:\n                messages.error(request, 'Fluxo não configurado — ' + ' | '.join(faltam))\n                return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')\n"""

count = text.count(old)
if count == 0:
    print("ERRO: bloco antigo de resolução de destino não encontrado. O arquivo pode ter mudado.")
    print("Nada foi gravado além do backup.")
    sys.exit(1)
if count > 1:
    print(f"AVISO: encontrei {count} blocos iguais. Vou substituir apenas o primeiro para evitar alteração indevida.")
text = text.replace(old, new, 1)

VIEW.write_text(text, encoding="utf-8")
print("Hotfix aplicado em core/views_assistencia_tecnica.py")
print("Resumo:")
print("- Inspeção técnica agora exige FluxoAcaoSetor ativo e exato para o destino calculado.")
print("- Dentro da garantia: Em Manutenção / Aguardando Manutenção Interna / Assistência Técnica.")
print("- Fora da garantia: Aguardando Aprovação do Orçamento - Cliente / Aguardando Aprovação do Orçamento (cliente) / SAC.")
print("- Se faltar cadastro, o sistema bloqueia o salvamento e mostra mensagem clara.")
