from __future__ import annotations

import ast
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Gera mapa de dependencias do SAC: URLs, views, templates, forms, models e pontos frageis. Somente leitura."

    IGNORAR_PARTES = {"venv", ".venv", "__pycache__", ".git", "node_modules", "staticfiles", "media", "diagnosticos"}

    def add_arguments(self, parser):
        parser.add_argument("--detalhado", action="store_true")
        parser.add_argument("--limite", type=int, default=120)

    def handle(self, *args, **options):
        base = Path(settings.BASE_DIR)
        limite = int(options["limite"])
        detalhado = bool(options["detalhado"])

        py_files = list(self._files(base, "*.py"))
        html_files = list(self._files(base, "*.html"))

        achados = []
        mapa = {
            "urls": self._mapear_urls(base, achados),
            "templates_renderizados": self._mapear_templates_renderizados(py_files),
            "forms_por_arquivo": self._mapear_classes(py_files, sufixos=("Form", "FormSet")),
            "models_por_arquivo": self._mapear_models(py_files),
            "imports_core": self._mapear_imports_core(py_files),
        }

        achados.extend(self._auditar_urls(mapa["urls"]))
        achados.extend(self._auditar_templates(base, html_files, mapa["templates_renderizados"]))
        achados.extend(self._auditar_render_sem_template(py_files))
        achados.extend(self._auditar_redirecionamentos_hardcoded(py_files))
        achados.extend(self._auditar_funcoes_longas(py_files))
        achados.extend(self._auditar_modularizacao(base))

        resumo = Counter(a["nivel"] for a in achados)
        relatorio = {
            "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "base_dir": str(base),
            "observacao": "Somente leitura. Nao altera arquivos, regras, banco, status, setores ou fluxos.",
            "resumo": dict(resumo),
            "metricas": {
                "arquivos_python": len(py_files),
                "templates_html": len(html_files),
                "urls_mapeadas": len(mapa["urls"]),
                "templates_renderizados": len(mapa["templates_renderizados"]),
            },
            "mapa": mapa,
            "achados": achados,
        }

        diag = base / "diagnosticos"
        diag.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = diag / f"mapa_dependencias_sac_{stamp}.json"
        txt_path = diag / f"mapa_dependencias_sac_{stamp}.txt"
        json_path.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
        txt_path.write_text(self._txt(relatorio), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS("Mapa de dependencias concluido."))
        self.stdout.write(f"TXT:  {txt_path}")
        self.stdout.write(f"JSON: {json_path}")
        self.stdout.write("")
        self.stdout.write("Resumo:")
        for nivel in ["CRITICO", "ALTO", "MEDIO", "BAIXO"]:
            self.stdout.write(f"- {nivel}: {resumo.get(nivel, 0)}")
        self.stdout.write("")
        self.stdout.write("Achados principais:")
        for a in achados[:limite if detalhado else min(limite, 40)]:
            self.stdout.write(f"[{a['nivel']}] {a['origem']} - {a['mensagem']}")
            if detalhado and a.get("detalhe"):
                self.stdout.write(f"    {a['detalhe']}")

    def _files(self, base: Path, pattern: str):
        for p in base.rglob(pattern):
            if set(p.parts).intersection(self.IGNORAR_PARTES):
                continue
            if any(part.lower().startswith(("backup", "bkp")) for part in p.parts):
                continue
            yield p

    def _rel(self, p: Path) -> str:
        try:
            return str(p.relative_to(settings.BASE_DIR)).replace("\\", "/")
        except Exception:
            return str(p)

    def _read(self, p: Path) -> str:
        try:
            return p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return p.read_text(encoding="latin-1", errors="ignore")
        except Exception as exc:
            return f"__ERRO_LEITURA__ {exc}"

    def _achado(self, nivel: str, origem: str, mensagem: str, detalhe: str = ""):
        return {"nivel": nivel, "origem": origem, "mensagem": mensagem, "detalhe": detalhe}

    def _mapear_urls(self, base: Path, achados):
        urls = []
        for p in [base / "config" / "urls.py", base / "core" / "urls.py"]:
            if not p.exists():
                continue
            txt = self._read(p)
            rel = self._rel(p)
            pattern = re.compile(r"path\(\s*['\"]([^'\"]*)['\"]\s*,\s*([^,\)]+)(?:,\s*name\s*=\s*['\"]([^'\"]+)['\"])?", re.M)
            for m in pattern.finditer(txt):
                urls.append({"arquivo": rel, "rota": m.group(1), "view": m.group(2).strip(), "name": m.group(3) or ""})
        return urls

    def _mapear_templates_renderizados(self, py_files):
        encontrados = []
        rgx = re.compile(r"render\([^\n]*?,\s*['\"]([^'\"]+\.html)['\"]")
        for p in py_files:
            txt = self._read(p)
            for m in rgx.finditer(txt):
                encontrados.append({"arquivo": self._rel(p), "template": m.group(1)})
        return encontrados

    def _mapear_classes(self, py_files, sufixos):
        dados = defaultdict(list)
        for p in py_files:
            txt = self._read(p)
            try:
                tree = ast.parse(txt)
            except SyntaxError:
                continue
            classes = []
            for n in ast.walk(tree):
                if isinstance(n, ast.ClassDef) and n.name.endswith(sufixos):
                    classes.append({"classe": n.name, "linha": n.lineno})
            if classes:
                dados[self._rel(p)] = classes
        return dict(dados)

    def _mapear_models(self, py_files):
        dados = defaultdict(list)
        for p in py_files:
            if not self._rel(p).endswith("models.py"):
                continue
            txt = self._read(p)
            try:
                tree = ast.parse(txt)
            except SyntaxError:
                continue
            for n in ast.walk(tree):
                if isinstance(n, ast.ClassDef):
                    bases = [getattr(b, "attr", getattr(b, "id", "")) for b in n.bases]
                    if "Model" in bases:
                        dados[self._rel(p)].append({"model": n.name, "linha": n.lineno})
        return dict(dados)

    def _mapear_imports_core(self, py_files):
        dados = defaultdict(list)
        for p in py_files:
            txt = self._read(p)
            for i, line in enumerate(txt.splitlines(), 1):
                l = line.strip()
                if l.startswith("from core") or l.startswith("import core"):
                    dados[self._rel(p)].append({"linha": i, "import": l[:220]})
        return dict(dados)

    def _auditar_urls(self, urls):
        achados = []
        nomes = Counter(u["name"] for u in urls if u["name"])
        rotas = Counter(u["rota"] for u in urls)
        for nome, qtd in nomes.items():
            if qtd > 1:
                detalhe = "; ".join(f"{u['arquivo']} -> {u['rota']}" for u in urls if u["name"] == nome)
                achados.append(self._achado("ALTO", "urls", f"Nome de URL duplicado: {nome} ({qtd} vezes).", detalhe))
        for rota, qtd in rotas.items():
            if qtd > 1:
                detalhe = "; ".join(f"{u['arquivo']} -> {u['view']}" for u in urls if u["rota"] == rota)
                achados.append(self._achado("ALTO", "urls", f"Rota duplicada: {rota} ({qtd} vezes).", detalhe))
        for u in urls:
            if "views." in u["view"] and "views_modular" in u["arquivo"]:
                achados.append(self._achado("MEDIO", u["arquivo"], "Mistura de views antigas e modularizadas em URL.", json.dumps(u, ensure_ascii=False)))
        return achados

    def _auditar_templates(self, base, html_files, renderizados):
        achados = []
        templates_dir = base / "core" / "templates"
        existentes = {self._rel(p).replace("core/templates/", "") for p in html_files}
        for item in renderizados:
            template = item["template"]
            if template not in existentes and not (templates_dir / template).exists():
                achados.append(self._achado("ALTO", item["arquivo"], f"View renderiza template nao encontrado: {template}", "Pode quebrar a tela ao abrir."))
        return achados

    def _auditar_render_sem_template(self, py_files):
        achados = []
        for p in py_files:
            txt = self._read(p)
            rel = self._rel(p)
            for i, line in enumerate(txt.splitlines(), 1):
                if "render(" in line and ".html" not in line and "template" in line.lower():
                    achados.append(self._achado("BAIXO", f"{rel}:{i}", "Render com template dinamico encontrado.", "Conferir se ha fallback seguro."))
        return achados

    def _auditar_redirecionamentos_hardcoded(self, py_files):
        achados = []
        for p in py_files:
            txt = self._read(p)
            rel = self._rel(p)
            for i, line in enumerate(txt.splitlines(), 1):
                l = line.strip()
                if "redirect(" in l and ('"/sac/' in l or "'/sac/" in l):
                    achados.append(self._achado("MEDIO", f"{rel}:{i}", "Redirect com URL hardcoded.", "Futuro ideal: usar name/reverse para evitar quebra se rota mudar."))
        return achados

    def _auditar_funcoes_longas(self, py_files):
        achados = []
        for p in py_files:
            txt = self._read(p)
            try:
                tree = ast.parse(txt)
            except SyntaxError:
                continue
            linhas = txt.splitlines()
            for n in ast.walk(tree):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = getattr(n, "end_lineno", n.lineno)
                    tam = end - n.lineno + 1
                    if tam >= 250:
                        achados.append(self._achado("MEDIO", f"{self._rel(p)}:{n.lineno}", f"Funcao muito longa: {n.name} ({tam} linhas).", "Risco de regressao; revisar antes de alterar."))
        return achados

    def _auditar_modularizacao(self, base):
        achados = []
        views = base / "core" / "views.py"
        modular = base / "core" / "views_modular"
        if views.exists() and modular.exists():
            qtd_mod = len(list(modular.glob("*.py")))
            linhas_views = self._read(views).count("\n") + 1
            if qtd_mod and linhas_views > 2500:
                achados.append(self._achado("MEDIO", "core/views.py", f"Modularizacao parcial detectada: views.py ainda tem {linhas_views} linhas e views_modular tem {qtd_mod} arquivos.", "Evitar duplicar regra entre os dois locais."))
        return achados

    def _txt(self, relatorio):
        linhas = []
        linhas.append("MAPA DE DEPENDENCIAS SAC")
        linhas.append("=" * 70)
        linhas.append(f"Gerado em: {relatorio['gerado_em']}")
        linhas.append(relatorio["observacao"])
        linhas.append("")
        linhas.append("RESUMO")
        for k, v in relatorio["resumo"].items():
            linhas.append(f"- {k}: {v}")
        linhas.append("")
        linhas.append("METRICAS")
        for k, v in relatorio["metricas"].items():
            linhas.append(f"- {k}: {v}")
        linhas.append("")
        linhas.append("ACHADOS")
        for a in relatorio["achados"]:
            linhas.append(f"[{a['nivel']}] {a['origem']} - {a['mensagem']}")
            if a.get("detalhe"):
                linhas.append(f"    {a['detalhe']}")
        linhas.append("")
        linhas.append("ROTAS MAPEADAS")
        for u in relatorio["mapa"]["urls"]:
            linhas.append(f"- {u['arquivo']} | {u['rota']} | {u['view']} | name={u['name']}")
        return "\n".join(linhas)
