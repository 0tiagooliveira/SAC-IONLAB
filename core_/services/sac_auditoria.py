from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone


def _logger() -> logging.Logger:
    logger = logging.getLogger('sac.auditoria')
    if logger.handlers:
        return logger
    log_dir = Path(getattr(settings, 'BASE_DIR', '.')) / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_dir / 'sac_auditoria.log', maxBytes=2_000_000, backupCount=5, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _safe(value: Any):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, 'isoformat'):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def registrar_log_sac(evento: str, **dados: Any) -> None:
    payload = {
        'evento': evento,
        'timestamp': timezone.now().isoformat(),
        **{k: _safe(v) for k, v in dados.items()},
    }
    _logger().info(json.dumps(payload, ensure_ascii=False, sort_keys=True))
