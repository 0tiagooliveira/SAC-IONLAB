from __future__ import annotations

import ast
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Audita riscos de manutencao do SAC sem alterar banco, regras ou arquivos. "
        "Gera relatorio em diagnosticos/."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=80)
        parser.add_argument("--detalhado", action="store_true")

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        limite = options["limite"]
        detalhado = options["detalhado"]
        diag_dir = base_dir / "diagnosticos"
        diag_dir.mkdir(exist_ok=True)

        agora = datetime.now().strftime("%Y%m%d_%H%M%S")
        relatorio = diag_dir / f"relatorio_riscos_manutencao_sac_{agora}.txt"

        linhas: list[str] = []
        self._add(linhas, "RELATORIO DE RISCOS DE MANUTENCAO DO SAC")
        self._add(linhas, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        self._add(linhas, f"Projeto: {base_dir}")
        self._add(linhas, "Modo: somente leitura - nao altera regras, banco ou arquivos")
        self._sep(linhas)

        py_files = [p for p in base_dir.rglob("*.py") if self._is_project_file(base_dir, p)]
        template_files = [p for p in (base_dir / "core" / "templates").rglob("*.html") if p.is_file()] if (base_dir / "core" / "templates").exists() else []

        self._auditar_arquivos_grandes(base_dir, py_files, template_files, linhas, limite)
        self._auditar_backups_e_lixo(base_dir, linhas, limite)
        self._auditar_funcoes_duplicadas(base_dir, py_files, linhas, limite, detalhado)
        self._auditar_except_generico(base_dir, py_files, linhas, limite)
        self._auditar_imports_views(base_dir, linhas)
        self._auditar_settings(base_dir, linhas)

        self._sep(linhas)
        self._add(linhas, "CONCLUSAO")
        self._add(linhas, "Este relatorio serve para orientar correcoes cirurgicas futuras.")
        self._add(linhas, "Nada foi modificado no sistema.")

        relatorio.write_text("\n".join(linhas), encoding="utf-8")

        for linha in linhas[:220]:
            self.stdout.write(linha)
        if len(linhas) > 220:
            self.stdout.write(f"... relatorio completo salvo em: {relatorio}")
        self.stdout.write(self.style.SUCCESS(f"Relatorio salvo em: {relatorio}"))

    def _is_project_file(self, base_dir: Path, p: Path) -> bool:
        texto = str(p.relative_to(base_dir)).replace("\\", "/")
        bloqueios = ("venv/", "__pycache__/", "backup_", "diagnosticos/", ".git/")
        return not any(texto.startswith(b) or f"/{b}" in texto for b in bloqueios)

    def _add(self, linhas: list[str], texto: str = ""):
        linhas.append(texto)

    def _sep(self, linhas: list[str]):
        linhas.append("=" * 78)

    def _rel(self, base_dir: Path, p: Path) -> str:
        try:
            return str(p.relative_to(base_dir))
        except Exception:
            return str(p)

    def _auditar_arquivos_grandes(self, base_dir: Path, py_files: list[Path], template_files: list[Path], linhas: list[str], limite: int):
        self._add(linhas, "1) ARQUIVOS GRANDES / RISCO DE REGRESSAO")
        candidatos = []
        for p in py_files + template_files:
            try:
                qtd = len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
                if qtd >= 400:
                    candidatos.append((qtd, p))
            except Exception:
                continue
        if not candidatos:
            self._add(linhas, "OK - nenhum arquivo acima do limite de risco encontrado.")
        else:
            for qtd, p in sorted(candidatos, reverse=True)[:limite]:
                self._add(linhas, f"ATENCAO - {self._rel(base_dir, p)} tem {qtd} linhas.")
            self._add(linhas, "Recomendacao: ao corrigir esses arquivos, aplicar patch pequeno e testar a tela afetada.")
        self._sep(linhas)

    def _auditar_backups_e_lixo(self, base_dir: Path, linhas: list[str], limite: int):
        self._add(linhas, "2) ARQUIVOS/Pastas QUE PODEM CONFUNDIR MANUTENCAO")
        encontrados = []
        padroes = ("*.bkp", "*.bak", "*.old", "*.orig", "*.pyc")
        for padrao in padroes:
            encontrados.extend(base_dir.rglob(padrao))
        encontrados.extend([p for p in base_dir.iterdir() if p.is_dir() and p.name.lower().startswith("backup")])
        encontrados = [p for p in encontrados if "venv" not in str(p).lower()]
        if not encontrados:
            self._add(linhas, "OK - nenhum arquivo obsoleto comum encontrado fora do venv.")
        else:
            for p in encontrados[:limite]:
                self._add(linhas, f"INFO - {self._rel(base_dir, p)}")
            self._add(linhas, "Recomendacao: nao apagar automaticamente. Apenas manter fora do caminho de imports e templates.")
        self._sep(linhas)

    def _auditar_funcoes_duplicadas(self, base_dir: Path, py_files: list[Path], linhas: list[str], limite: int, detalhado: bool):
        self._add(linhas, "3) NOMES DE FUNCOES/CLASSES REPETIDOS EM ARQUIVOS DIFERENTES")
        nomes = defaultdict(list)
        for p in py_files:
            try:
                tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    nomes[node.name].append((p, node.lineno, type(node).__name__))
        repetidos = [(nome, locs) for nome, locs in nomes.items() if len({x[0] for x in locs}) > 1]
        if not repetidos:
            self._add(linhas, "OK - nao foram encontrados nomes repetidos entre arquivos.")
        else:
            for nome, locs in sorted(repetidos, key=lambda x: (-len(x[1]), x[0]))[:limite]:
                self._add(linhas, f"ATENCAO - '{nome}' aparece em {len(locs)} pontos:")
                for p, line, tipo in locs[:8 if detalhado else 4]:
                    self._add(linhas, f"  - {self._rel(base_dir, p)}:{line} ({tipo})")
        self._sep(linhas)

    def _auditar_except_generico(self, base_dir: Path, py_files: list[Path], linhas: list[str], limite: int):
        self._add(linhas, "4) EXCEPT GENERICO / ERRO SILENCIOSO")
        achados = []
        for p in py_files:
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue
            for idx, line in enumerate(txt, start=1):
                l = line.strip()
                if l in {"except:", "except Exception:", "except Exception as e:"}:
                    achados.append((p, idx, l))
        if not achados:
            self._add(linhas, "OK - nenhum except generico encontrado.")
        else:
            for p, idx, l in achados[:limite]:
                self._add(linhas, f"ATENCAO - {self._rel(base_dir, p)}:{idx} -> {l}")
            self._add(linhas, "Recomendacao: trocar aos poucos por logging/diagnostico, sem mudar retorno da tela.")
        self._sep(linhas)

    def _auditar_imports_views(self, base_dir: Path, linhas: list[str]):
        self._add(linhas, "5) VIEWS MONOLITICAS X VIEWS MODULARES")
        urls = base_dir / "config" / "urls.py"
        if not urls.exists():
            self._add(linhas, "ATENCAO - config/urls.py nao encontrado.")
        else:
            txt = urls.read_text(encoding="utf-8", errors="ignore")
            usa_views = "core.views" in txt
            usa_modular = "views_modular" in txt or "core.views_modular" in txt
            self._add(linhas, f"config/urls.py importa core.views: {'SIM' if usa_views else 'NAO'}")
            self._add(linhas, f"config/urls.py importa views_modular: {'SIM' if usa_modular else 'NAO'}")
            if usa_views and usa_modular:
                self._add(linhas, "ATENCAO - imports mistos aumentam risco de regra duplicada. Modularizar somente por etapa.")
        self._sep(linhas)

    def _auditar_settings(self, base_dir: Path, linhas: list[str]):
        self._add(linhas, "6) SETTINGS / RISCOS DE PRODUCAO")
        settings_py = base_dir / "config" / "settings.py"
        if not settings_py.exists():
            self._add(linhas, "ATENCAO - config/settings.py nao encontrado.")
        else:
            txt = settings_py.read_text(encoding="utf-8", errors="ignore")
            checks = {
                "DEBUG padrao True": "DEBUG = True" in txt or "DEBUG=True" in txt,
                "Senha 123456 aparente": "123456" in txt,
                "SECRET_KEY visivel": "SECRET_KEY" in txt and "os.environ" not in txt[: txt.find("SECRET_KEY") + 200],
            }
            for nome, risco in checks.items():
                self._add(linhas, f"{'ATENCAO' if risco else 'OK'} - {nome}")
            self._add(linhas, "Recomendacao: corrigir depois com variaveis de ambiente, sem alterar ambiente local agora.")
        self._sep(linhas)
