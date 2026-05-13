# -*- coding: utf-8 -*-
"""
Auditoria preventiva de templates, URLs e referencias do SAC.
Somente leitura: nao altera banco, regras, status, setores ou fluxos.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import get_resolver


class Command(BaseCommand):
    help = "Audita templates, URLs, includes e referencias frageis do SAC sem alterar regras."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=200, help="Limite de itens por secao no relatorio.")
        parser.add_argument("--json", action="store_true", help="Tambem salva um JSON com os achados.")

    def handle(self, *args, **options):
        base = Path(settings.BASE_DIR)
        limite = int(options.get("limite") or 200)
        diag_dir = base / "diagnosticos"
        diag_dir.mkdir(exist_ok=True)
        agora = datetime.now().strftime("%Y%m%d_%H%M%S")
        relatorio = diag_dir / f"auditoria_templates_urls_sac_{agora}.txt"
        relatorio_json = diag_dir / f"auditoria_templates_urls_sac_{agora}.json"

        achados = self._auditar(base, limite)
        linhas = self._formatar(achados, base)
        relatorio.write_text("\n".join(linhas), encoding="utf-8")

        if options.get("json"):
            relatorio_json.write_text(json.dumps(achados, ensure_ascii=False, indent=2), encoding="utf-8")

        for linha in linhas[:120]:
            self.stdout.write(linha)
        if len(linhas) > 120:
            self.stdout.write(f"\n... relatorio completo salvo em: {relatorio}")
        else:
            self.stdout.write(f"\nRelatorio salvo em: {relatorio}")
        if options.get("json"):
            self.stdout.write(f"JSON salvo em: {relatorio_json}")

    def _auditar(self, base: Path, limite: int):
        core = base / "core"
        templates_dir = core / "templates"
        py_files = [p for p in core.rglob("*.py") if "__pycache__" not in str(p)]
        html_files = [p for p in templates_dir.rglob("*.html")] if templates_dir.exists() else []

        url_names = self._coletar_url_names()
        template_paths = {self._template_name(p, templates_dir): p for p in html_files}

        includes = []
        extends = []
        url_tags = []
        possiveis_templates_em_views = []
        hardcoded_urls = []
        duplicate_blocks = defaultdict(list)
        fragile_patterns = []

        include_re = re.compile(r"{%\s*include\s+['\"]([^'\"]+)['\"]")
        extends_re = re.compile(r"{%\s*extends\s+['\"]([^'\"]+)['\"]")
        url_tag_re = re.compile(r"{%\s*url\s+['\"]([^'\"]+)['\"]")
        block_re = re.compile(r"{%\s*block\s+([A-Za-z0-9_\-]+)")
        render_re = re.compile(r"render\s*\([^\n]*?['\"]([^'\"]+\.html)['\"]")
        template_name_re = re.compile(r"template_name\s*=\s*['\"]([^'\"]+\.html)['\"]")
        hard_url_re = re.compile(r"['\"](/sac/[^'\"]*)['\"]")
        fragile_regras = [
            ("except_exception", re.compile(r"except\s+Exception\b")),
            ("print_debug", re.compile(r"\bprint\s*\(")),
            ("todo_fixme", re.compile(r"\b(TODO|FIXME|gambiarra|provisorio|provisório)\b", re.I)),
            ("status_texto_fixo", re.compile(r"['\"](Conclu[ií]do|Em An[aá]lise|Log[ií]stica|Diretoria|SAC|Assessoria Cient[ií]fica)['\"]", re.I)),
        ]

        for p in html_files:
            txt = self._read(p)
            rel = str(p.relative_to(base))
            for m in include_re.finditer(txt):
                name = m.group(1)
                includes.append({"arquivo": rel, "template": name, "existe": name in template_paths})
            for m in extends_re.finditer(txt):
                name = m.group(1)
                extends.append({"arquivo": rel, "template": name, "existe": name in template_paths})
            for m in url_tag_re.finditer(txt):
                name = m.group(1)
                url_tags.append({"arquivo": rel, "url_name": name, "existe": name in url_names})
            blocks = [m.group(1) for m in block_re.finditer(txt)]
            for nome, qtd in Counter(blocks).items():
                if qtd > 1:
                    duplicate_blocks[rel].append({"block": nome, "qtd": qtd})
            for m in hard_url_re.finditer(txt):
                hardcoded_urls.append({"arquivo": rel, "url": m.group(1)})

        for p in py_files:
            txt = self._read(p)
            rel = str(p.relative_to(base))
            for regex in (render_re, template_name_re):
                for m in regex.finditer(txt):
                    name = m.group(1)
                    possiveis_templates_em_views.append({"arquivo": rel, "template": name, "existe": name in template_paths})
            for m in hard_url_re.finditer(txt):
                hardcoded_urls.append({"arquivo": rel, "url": m.group(1)})
            for nome, regex in fragile_regras:
                ocorrencias = len(regex.findall(txt))
                if ocorrencias:
                    fragile_patterns.append({"arquivo": rel, "tipo": nome, "ocorrencias": ocorrencias})

        faltantes = {
            "includes_faltantes": [x for x in includes if not x["existe"]][:limite],
            "extends_faltantes": [x for x in extends if not x["existe"]][:limite],
            "url_tags_faltantes": [x for x in url_tags if not x["existe"]][:limite],
            "templates_chamados_faltantes": [x for x in possiveis_templates_em_views if not x["existe"]][:limite],
        }

        return {
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "resumo": {
                "templates_html": len(html_files),
                "arquivos_python_core": len(py_files),
                "url_names_identificados": len(url_names),
                "includes_total": len(includes),
                "extends_total": len(extends),
                "url_tags_total": len(url_tags),
                "hardcoded_urls_total": len(hardcoded_urls),
                "padroes_frageis_total": sum(x["ocorrencias"] for x in fragile_patterns),
            },
            "faltantes": faltantes,
            "blocks_duplicados": dict(list(duplicate_blocks.items())[:limite]),
            "hardcoded_urls": hardcoded_urls[:limite],
            "padroes_frageis": sorted(fragile_patterns, key=lambda x: (-x["ocorrencias"], x["arquivo"]))[:limite],
        }

    def _coletar_url_names(self):
        nomes = set()

        def walk(patterns):
            for p in patterns:
                if getattr(p, "name", None):
                    nomes.add(p.name)
                if hasattr(p, "url_patterns"):
                    walk(p.url_patterns)

        try:
            walk(get_resolver().url_patterns)
        except Exception:
            pass
        return nomes

    def _template_name(self, p: Path, templates_dir: Path) -> str:
        try:
            return str(p.relative_to(templates_dir)).replace("\\", "/")
        except Exception:
            return p.name

    def _read(self, p: Path) -> str:
        try:
            return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    def _formatar(self, achados, base: Path):
        linhas = []
        linhas.append("AUDITORIA PREVENTIVA - TEMPLATES / URLS / REFERENCIAS SAC")
        linhas.append("Somente leitura: nao altera regra, banco, migrations ou fluxo.")
        linhas.append(f"Projeto: {base}")
        linhas.append(f"Gerado em: {achados['gerado_em']}")
        linhas.append("")
        linhas.append("RESUMO")
        for k, v in achados["resumo"].items():
            linhas.append(f"- {k}: {v}")

        def secao(titulo, itens, campos):
            linhas.append("")
            linhas.append(titulo)
            if not itens:
                linhas.append("- Nenhum achado nesta secao.")
                return
            for item in itens:
                linhas.append("- " + " | ".join(f"{c}: {item.get(c)}" for c in campos))

        falt = achados["faltantes"]
        secao("INCLUDES FALTANTES", falt["includes_faltantes"], ["arquivo", "template"])
        secao("EXTENDS FALTANTES", falt["extends_faltantes"], ["arquivo", "template"])
        secao("URL TAGS FALTANTES", falt["url_tags_faltantes"], ["arquivo", "url_name"])
        secao("TEMPLATES CHAMADOS EM PYTHON MAS NAO ENCONTRADOS", falt["templates_chamados_faltantes"], ["arquivo", "template"])

        linhas.append("")
        linhas.append("BLOCKS DUPLICADOS EM TEMPLATES")
        if not achados["blocks_duplicados"]:
            linhas.append("- Nenhum block duplicado encontrado.")
        else:
            for arq, itens in achados["blocks_duplicados"].items():
                for item in itens:
                    linhas.append(f"- arquivo: {arq} | block: {item['block']} | qtd: {item['qtd']}")

        secao("URLS /sac/ FIXAS NO CODIGO (RISCO FUTURO)", achados["hardcoded_urls"], ["arquivo", "url"])
        secao("PADROES FRAGEIS PARA REVISAO FUTURA", achados["padroes_frageis"], ["arquivo", "tipo", "ocorrencias"])
        linhas.append("")
        linhas.append("OBS: Este relatorio apenas aponta riscos. Corrigir somente por patch cirurgico, um grupo por vez.")
        return linhas
