from pathlib import Path
import shutil
import datetime
import sys

ROOT = Path.cwd()
TEMPLATE = ROOT / 'core' / 'templates' / 'core' / 'abrir_sac.html'
CSS_SRC = ROOT / '_patch_abertura_sac_premium' / 'core' / 'static' / 'core' / 'css' / 'abrir_sac_premium.css'
JS_SRC = ROOT / '_patch_abertura_sac_premium' / 'core' / 'static' / 'core' / 'js' / 'abrir_sac_premium.js'
CSS_DST = ROOT / 'core' / 'static' / 'core' / 'css' / 'abrir_sac_premium.css'
JS_DST = ROOT / 'core' / 'static' / 'core' / 'js' / 'abrir_sac_premium.js'
MARK_CSS = "abrir_sac_premium.css"
MARK_JS = "abrir_sac_premium.js"

def fail(msg):
    print(f"ERRO: {msg}")
    sys.exit(1)

def main():
    if not TEMPLATE.exists():
        fail(f"Template nao encontrado: {TEMPLATE}")
    if not CSS_SRC.exists() or not JS_SRC.exists():
        fail("Arquivos do patch nao encontrados dentro de _patch_abertura_sac_premium")

    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = ROOT / f'backup_abertura_sac_premium_{stamp}'
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATE, backup_dir / 'abrir_sac.html')
    if CSS_DST.exists(): shutil.copy2(CSS_DST, backup_dir / 'abrir_sac_premium.css')
    if JS_DST.exists(): shutil.copy2(JS_DST, backup_dir / 'abrir_sac_premium.js')

    CSS_DST.parent.mkdir(parents=True, exist_ok=True)
    JS_DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CSS_SRC, CSS_DST)
    shutil.copy2(JS_SRC, JS_DST)

    html = TEMPLATE.read_text(encoding='utf-8')
    changed = False
    css_tag = "    <link rel=\"stylesheet\" href=\"{% static 'core/css/abrir_sac_premium.css' %}\">\n"
    js_tag = "<script src=\"{% static 'core/js/abrir_sac_premium.js' %}\"></script>\n"

    if MARK_CSS not in html:
        if '</head>' not in html:
            fail("Nao encontrei </head> no template para inserir CSS")
        html = html.replace('</head>', css_tag + '</head>', 1)
        changed = True

    if MARK_JS not in html:
        if '</body>' not in html:
            fail("Nao encontrei </body> no template para inserir JS")
        html = html.replace('</body>', js_tag + '</body>', 1)
        changed = True

    if changed:
        TEMPLATE.write_text(html, encoding='utf-8')

    print('OK: patch visual aplicado com seguranca.')
    print(f'Backup criado em: {backup_dir}')
    print('Arquivos atualizados:')
    print(f'- {TEMPLATE}')
    print(f'- {CSS_DST}')
    print(f'- {JS_DST}')

if __name__ == '__main__':
    main()
