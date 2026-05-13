import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs_sac")
os.makedirs(LOG_DIR, exist_ok=True)

def registrar_erro(contexto, erro):
    try:
        caminho = os.path.join(LOG_DIR, "erros.log")
        with open(caminho, "a", encoding="utf-8") as f:
            f.write("[{}] {} - {}\n".format(datetime.now(), contexto, str(erro)))
    except Exception:
        pass
