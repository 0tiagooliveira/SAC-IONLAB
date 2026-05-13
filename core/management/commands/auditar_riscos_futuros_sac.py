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
    help = "Auditoria preventiva profunda do SAC. Somente leitura: nao altera regras, arquivos ou banco."

    TERMOS_FLUXO = [
        "Concluído", "Concluido", "Em Análise", "Em Analise", "Diretoria", "Logística", "Logistica",
        "Assessoria Cientifica", "Assessoria Científica", "Aguardando", "Emissão do Pedido",
        "Emissao do Pedido", "Fluxo não configurado", "Fluxo nao configurado",
    ]

    PASTAS_IGNORADAS = {
        "venv", ".venv", "__pycache__", ".git", "node_modules", "staticfiles",
        "backup", "backups", "media", "diagnosticos",
    }

    def add_arguments(self, parser):
        parser.add_argument("--detalhado", action="store_true", help="Exibe mais ocorrencias no console.")
        parser.add_argument("--limite", type=int, default=80, help="Limite de itens por grupo no console.")

    def handle(self, *args, **options):
        base = Path(settings.BASE_DIR)
        detalhado = options["detalhado"]
        limite = options["limite"]

        achados = []
        metricas = {}

        py_files = list(self._arquivos(base, "*.py"))
        html_files = list(self._arquivos(base, "*.html"))

        metricas["arquivos_python"] = len(py_files)
        metricas["templates_html"] = len(html_files)

        achados.extend(self._auditar_tamanho_arquivos(py_files))
        achados.extend(self._auditar_sintaxe(py_files))
        achados.extend(self._auditar_exceptions(py_files))
        achados.extend(self._auditar_hardcoded(py_files, html_files))
        achados.extend(self._auditar_funcoes_duplicadas(py_files))
        achados.extend(self._auditar_includes_templates(base, html_files))
        achados.extend(self._auditar_migrations(base))
        achados.extend(self._auditar_settings(base))

        contador = Counter(a["nivel"] for a in achados)
        relatorio = {
            "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "base_dir": str(base),
            "resumo": dict(contador),
            "metricas": metricas,
            "achados": achados,
            "observacao": "Auditoria somente leitura. Nenhuma regra, arquivo ou dado foi alterado.",
        }

        diag_dir = base / "diagnosticos"
        diag_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = diag_dir / f"relatorio_riscos_futuros_sac_{stamp}.json"
        txt_path = diag_dir / f"relatorio_riscos_futuros_sac_{stamp}.txt"
        json_path.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
        txt_path.write_text(self._montar_txt(relatorio), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS("Auditoria de riscos futuros concluida."))
        self.stdout.write(f"Relatorio TXT:  {txt_path}")
        self.stdout.write(f"Relatorio JSON: {json_path}")
        self.stdout.write("")
        self.stdout.write("Resumo:")
        for nivel in ["CRITICO", "ALTO", "MEDIO", "BAIXO"]:
            self.stdout.write(f"- {nivel}: {contador.get(nivel, 0)}")

        self.stdout.write("")
        self.stdout.write("Principais achados:")
        for a in achados[:limite if detalhado else min(limite, 25)]:
            self.stdout.write(f"[{a['nivel']}] {a['origem']} - {a['mensagem']}")
            if detalhado and a.get("detalhe"):
                self.stdout.write(f"    {a['detalhe']}")

        if contador.get("CRITICO", 0):
            self.stdout.write(self.style.WARNING("Foram encontrados riscos criticos para revisar antes de novos patches."))
        else:
            self.stdout.write(self.style.SUCCESS("Nenhum risco critico automatico encontrado."))

    def _arquivos(self, base: Path, padrao: str):
        for p in base.rglob(padrao):
            partes = set(p.parts)
            if partes.intersection(self.PASTAS_IGNORADAS):
                continue
            if any(part.lower().startswith("backup") or part.lower().startswith("bkp") for part in p.parts):
                continue
            yield p

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(settings.BASE_DIR)).replace("\\", "/")
        except Exception:
            return str(path)

    def _ler(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1", errors="ignore")
        except Exception as exc:
            return f"__ERRO_LEITURA__ {exc}"

    def _achado(self, nivel, origem, mensagem, detalhe=""):
        return {"nivel": nivel, "origem": origem, "mensagem": mensagem, "detalhe": detalhe}

    def _auditar_tamanho_arquivos(self, py_files):
        achados = []
        for p in py_files:
            txt = self._ler(p)
            linhas = txt.count("\n") + 1
            rel = self._rel(p)
            if rel.endswith("core/views.py") and linhas > 2500:
                achados.append(self._achado("ALTO", rel, f"Arquivo central muito grande ({linhas} linhas).", "Risco de regressao em telas nao relacionadas."))
            elif rel.endswith("core/forms.py") and linhas > 1200:
                achados.append(self._achado("ALTO", rel, f"Forms muito grande ({linhas} linhas).", "Risco de acoplamento entre formularios."))
            elif linhas > 1500:
                achados.append(self._achado("MEDIO", rel, f"Arquivo grande ({linhas} linhas).", "Revisar modularizacao futura sem alterar regra."))
        return achados

    def _auditar_sintaxe(self, py_files):
        achados = []
        for p in py_files:
            txt = self._ler(p)
            try:
                ast.parse(txt)
            except SyntaxError as exc:
                achados.append(self._achado("CRITICO", self._rel(p), "Erro de sintaxe Python.", f"Linha {exc.lineno}: {exc.msg}"))
        return achados

    def _auditar_exceptions(self, py_files):
        achados = []
        for p in py_files:
            txt = self._ler(p)
            rel = self._rel(p)
            for i, linha in enumerate(txt.splitlines(), start=1):
                l = linha.strip()
                if re.match(r"except\s+Exception\s*(as\s+\w+)?\s*:", l):
                    achados.append(self._achado("MEDIO", f"{rel}:{i}", "except Exception generico encontrado.", "Pode esconder erro real se nao houver log/diagnostico."))
                if re.match(r"except\s*:", l):
                    achados.append(self._achado("ALTO", f"{rel}:{i}", "except aberto encontrado.", "Risco maior de erro silencioso."))
        return achados

    def _auditar_hardcoded(self, py_files, html_files):
        achados = []
        for p in list(py_files) + list(html_files):
            txt = self._ler(p)
            rel = self._rel(p)
            if "auditar_riscos_futuros_sac.py" in rel:
                continue
            for termo in self.TERMOS_FLUXO:
                qtd = txt.count(termo)
                if qtd >= 5:
                    achados.append(self._achado("MEDIO", rel, f"Termo de fluxo hardcoded muitas vezes: '{termo}' ({qtd} ocorrencias).", "Futuro ideal: usar codigos/cadastro central e nome apenas para exibicao."))
        return achados

    def _auditar_funcoes_duplicadas(self, py_files):
        funcoes = defaultdict(list)
        achados = []
        for p in py_files:
            txt = self._ler(p)
            try:
                tree = ast.parse(txt)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    funcoes[node.name].append((self._rel(p), node.lineno))
        for nome, locais in funcoes.items():
            if len(locais) >= 3 and not nome.startswith("_"):
                detalhe = "; ".join(f"{arq}:{lin}" for arq, lin in locais[:10])
                achados.append(self._achado("BAIXO", nome, f"Funcao com mesmo nome em {len(locais)} locais.", detalhe))
        return achados

    def _auditar_includes_templates(self, base, html_files):
        achados = []
        templates_dir = base / "core" / "templates"
        padrao = re.compile(r"{%\s*(?:include|extends)\s+['\"]([^'\"]+)['\"]")
        for p in html_files:
            txt = self._ler(p)
            for m in padrao.finditer(txt):
                alvo = m.group(1)
                if any(x in alvo for x in ["{{", "{%"]):
                    continue
                if not (templates_dir / alvo).exists():
                    achados.append(self._achado("ALTO", self._rel(p), f"Template referenciado nao encontrado: {alvo}", "Pode quebrar renderizacao da tela."))
        return achados

    def _auditar_migrations(self, base):
        achados = []
        mig_dir = base / "core" / "migrations"
        if not mig_dir.exists():
            achados.append(self._achado("CRITICO", "core/migrations", "Pasta de migrations nao encontrada."))
            return achados
        nums = []
        for p in mig_dir.glob("[0-9][0-9][0-9][0-9]_*.py"):
            try:
                nums.append(int(p.name[:4]))
            except ValueError:
                pass
        if nums:
            faltando = sorted(set(range(min(nums), max(nums) + 1)) - set(nums))
            if faltando:
                achados.append(self._achado("ALTO", "core/migrations", f"Numeracao de migrations com lacunas: {faltando}", "Pode ser normal, mas merece conferencia antes de migrate."))
        return achados

    def _auditar_settings(self, base):
        achados = []
        p = base / "config" / "settings.py"
        if not p.exists():
            return [self._achado("CRITICO", "config/settings.py", "settings.py nao encontrado.")]
        txt = self._ler(p)
        if "DEBUG = True" in txt or "DEBUG=True" in txt:
            achados.append(self._achado("MEDIO", "config/settings.py", "DEBUG True fixo/localizado.", "Em producao deve vir de ambiente; nao alterar agora sem validar deploy."))
        if "123456" in txt:
            achados.append(self._achado("ALTO", "config/settings.py", "Senha padrao ou sensivel encontrada no settings.", "Risco de seguranca em producao."))
        if "SECRET_KEY" in txt and "os.environ" not in txt and "config(" not in txt:
            achados.append(self._achado("MEDIO", "config/settings.py", "SECRET_KEY possivelmente fixa no codigo.", "Ideal futuro: usar variavel de ambiente."))
        return achados

    def _montar_txt(self, relatorio):
        linhas = []
        linhas.append("RELATORIO DE RISCOS FUTUROS - SAC")
        linhas.append("=" * 70)
        linhas.append(f"Gerado em: {relatorio['gerado_em']}")
        linhas.append(f"Projeto: {relatorio['base_dir']}")
        linhas.append("")
        linhas.append("RESUMO")
        for nivel in ["CRITICO", "ALTO", "MEDIO", "BAIXO"]:
            linhas.append(f"- {nivel}: {relatorio['resumo'].get(nivel, 0)}")
        linhas.append("")
        linhas.append("OBSERVACAO")
        linhas.append(relatorio["observacao"])
        linhas.append("")
        linhas.append("ACHADOS")
        linhas.append("-" * 70)
        for a in relatorio["achados"]:
            linhas.append(f"[{a['nivel']}] {a['origem']}")
            linhas.append(f"  {a['mensagem']}")
            if a.get("detalhe"):
                linhas.append(f"  Detalhe: {a['detalhe']}")
            linhas.append("")
        return "\n".join(linhas)
