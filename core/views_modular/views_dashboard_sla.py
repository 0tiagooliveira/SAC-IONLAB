
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import Empresa, SAC, SacHistorico, StatusSAC
from core.services.dashboard_sla import montar_auditoria_visual_sac, montar_dashboard_sla
from core.services.permissoes_simples import usuario_pode_tela


@login_required
def dashboard_sla(request):
    empresas = list(Empresa.objects.filter(ativo=True).order_by('razao_social'))
    empresa_codigo = (request.GET.get('empresa') or '').strip()
    empresa = None
    if empresa_codigo and empresa_codigo.lower() != 'agrupado':
        empresa = Empresa.objects.filter(codigo__iexact=empresa_codigo, ativo=True).first()
    cache_key = f"dashboard_sla_completo:v4:{getattr(empresa, 'id', 'agrupado')}"
    contexto_cache = cache.get(cache_key)
    if contexto_cache is None:
        contexto_cache = montar_dashboard_sla(empresa=empresa)
        cache.set(cache_key, contexto_cache, 45)
    contexto = dict(contexto_cache)
    contexto.update({
        'empresas_dashboard': empresas,
        'empresa_codigo_selecionado': getattr(empresa, 'codigo', '') or 'agrupado',
        'dashboard_agrupado': empresa is None,
    })
    return render(request, 'core/dashboard_sla.html', contexto)


@login_required
def auditoria_visual_sac(request, sac_id):
    sac = get_object_or_404(SAC.objects.select_related('cliente', 'empresa', 'status_atual', 'setor_atual'), id=sac_id)
    contexto = montar_auditoria_visual_sac(sac)
    contexto.update({
        'pode_alterar_sac': usuario_pode_tela(request.user, 'retificar_sac', 'alterar'),
        'pode_cancelar_sac': usuario_pode_tela(request.user, 'cancelar_sac', 'alterar'),
        'sac_cancelado': bool(sac.cancelado_em) or (sac.status_atual and (sac.status_atual.nome or '').lower() == 'cancelado'),
    })
    return render(request, 'core/auditoria_visual_sac.html', contexto)


@login_required
@transaction.atomic
def cancelar_sac(request, sac_id):
    sac = get_object_or_404(SAC.objects.select_related('status_atual', 'setor_atual'), id=sac_id)
    if not usuario_pode_tela(request.user, 'cancelar_sac', 'alterar'):
        messages.error(request, 'Usuário sem acesso a essa pagina')
        return redirect('auditoria_visual_sac', sac_id=sac.id)
    if request.method != 'POST':
        return redirect('auditoria_visual_sac', sac_id=sac.id)

    status_anterior = sac.status_atual
    status_cancelado, _ = StatusSAC.objects.get_or_create(
        codigo='CANCELADO',
        defaults={'nome': 'Cancelado', 'ativo': True},
    )
    if status_cancelado.nome != 'Cancelado' or not status_cancelado.ativo:
        status_cancelado.nome = 'Cancelado'
        status_cancelado.ativo = True
        status_cancelado.save(update_fields=['nome', 'ativo'])

    if not sac.cancelado_em:
        sac.cancelado_em = timezone.now()
    sac.status_atual = status_cancelado
    sac.acao_em_espera = None
    sac.motivo_cancelamento = sac.motivo_cancelamento or 'Cancelado manualmente pela auditoria visual do SAC.'
    sac.save(update_fields=['status_atual', 'acao_em_espera', 'cancelado_em', 'motivo_cancelamento'])

    SacHistorico.objects.create(
        sac=sac,
        usuario=request.user,
        status_anterior=status_anterior,
        status_novo=status_cancelado,
        setor_origem=sac.setor_atual,
        setor_destino=sac.setor_atual,
        acao_executada='Cancelamento do SAC',
        observacao='SAC cancelado manualmente pela auditoria visual.',
    )
    cache.clear()
    messages.success(request, 'SAC cancelado com sucesso.')
    return redirect('auditoria_visual_sac', sac_id=sac.id)
