import os 
from datetime import datetime 
 
LOG = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs_sac', 'motor_divergencias.log') 
 
def registrar_divergencia(sac_id, atual, motor): 
    try: 
        os.makedirs(os.path.dirname(LOG), exist_ok=True) 
        with open(LOG, 'a', encoding='utf-8') as f: 
            f.write(f"[{datetime.now()}] SAC {sac_id} | ATUAL={atual} | MOTOR={motor}\n") 
    except Exception: 
        pass 
        pass 
