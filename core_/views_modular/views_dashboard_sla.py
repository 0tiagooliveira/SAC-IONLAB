
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from core.models import SAC
from core.services.dashboard_sla import montar_auditoria_visual_sac, montar_dashboard_sla


@login_required
def dashboard_sla(request):
    contexto = montar_dashboard_sla()
    return render(request, 'core/dashboard_sla.html', contexto)


@login_required
def auditoria_visual_sac(request, sac_id):
    sac = get_object_or_404(SAC.objects.select_related('cliente', 'empresa', 'status_atual', 'setor_atual'), id=sac_id)
    contexto = montar_auditoria_visual_sac(sac)
    return render(request, 'core/auditoria_visual_sac.html', contexto)
