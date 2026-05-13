from __future__ import annotations

import ast
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.core.management.base import BaseCommand


@dataclass
class Achado:
    nivel: str
    origem: str
    mensagem: str
    detalhe: str = ""


class Command(BaseCommand):
    help = "Auditoria preventiva de blindagem do SAC. Somente leitura: nao altera regras, banco ou arquivos existentes."

    HARD_CODED_TERMS = [
        "Concluído",
        "Em Análise",
        "Diretoria",
        "Logística",
        "Assessoria Cientifica",
        "Assessoria Científica",
        "Aguardando",
        "Fluxo não configurado",
        "Emissão do Pedido",
    ]

    def add_arguments(self, parser):
        parser.add_argument("--detalhado", action="store_true", help="Mostra mais detalhes por arquivo.")
        parser.add_argument("--limite", type=int, default=80, help="Limite de achados exibidos por grupo.")
        parser.add_argument("--sem-banco", action="store_true", help="Nao executa verificacoes de banco.")

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        limite = int(options.get("limite") or 80)
        detalhado = bool(options.get("detalhado"))
        sem_banco = bool(options.get("sem_banco"))

        achados: list[Achado] = []
        achados.extend(self._auditar_arquivos(base_dir, detalhado=detalhado))
        achados.extend(self._auditar_urls(base_dir))
        if not sem_banco:
            achados.extend(self._auditar_banco())

        relatorio = self._montar_relatorio(achados, base_dir, limite)
        destino = base_dir / "diagnosticos"
        destino.mkdir(exist_ok=True)
        arquivo = destino / f"auditoria_blindagem_sac_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        arquivo.write_text(relatorio, encoding="utf-8")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("AUDITORIA DE BLINDAGEM CONCLUIDA - SOMENTE LEITURA"))
        self.stdout.write(f"Relatorio salvo em: {arquivo}")
        self.stdout.write("")
        self.stdout.write(relatorio)

    def _arquivos_alvo(self, base_dir: Path) -> Iterable[Path]:
        ignorar_partes = {"venv", "__pycache__", ".git", "backup", "backups", "media", "staticfiles"}
        for pasta in [base_dir / "core", base_dir / "config"]:
            if not pasta.exists():
                continue
            for caminho in pasta.rglob("*"):
                if not caminho.is_file():
                    continue
                if caminho.suffix.lower() not in {".py", ".html"}:
                    continue
                partes = {p.lower() for p in caminho.parts}
                if partes.intersection(ignorar_partes):
                    continue
                yield caminho

    def _auditar_arquivos(self, base_dir: Path, detalhado: bool) -> list[Achado]:
        achados: list[Achado] = []
        for caminho in self._arquivos_alvo(base_dir):
            rel = str(caminho.relative_to(base_dir))
            try:
                texto = caminho.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                achados.append(Achado("ALTO", rel, "Nao foi possivel ler o arquivo.", str(exc)))
                continue

            linhas = texto.splitlines()
            if caminho.suffix == ".py" and len(linhas) > 1500:
                achados.append(Achado("MEDIO", rel, f"Arquivo muito grande ({len(linhas)} linhas).", "Risco de regressao em alteracoes futuras."))

            if caminho.suffix == ".py":
                achados.extend(self._auditar_python(caminho, rel, texto, detalhado))
            elif caminho.suffix == ".html":
                achados.extend(self._auditar_template(rel, texto))

        return achados

    def _auditar_python(self, caminho: Path, rel: str, texto: str, detalhado: bool) -> list[Achado]:
        achados: list[Achado] = []
        try:
            arvore = ast.parse(texto)
        except SyntaxError as exc:
            achados.append(Achado("ALTO", rel, "Erro de sintaxe Python.", f"linha {exc.lineno}: {exc.msg}"))
            return achados

        for no in ast.walk(arvore):
            if isinstance(no, ast.ExceptHandler):
                tipo = self._nome_excecao(no.type)
                corpo_pass = any(isinstance(item, ast.Pass) for item in no.body)
                if tipo in {"Exception", "BaseException", ""}:
                    achados.append(Achado("MEDIO", rel, f"Tratamento generico de excecao na linha {getattr(no, 'lineno', '?')}.", "Pode esconder erro real se nao houver log claro."))
                if corpo_pass:
                    achados.append(Achado("ALTO", rel, f"except com pass na linha {getattr(no, 'lineno', '?')}." , "Erro pode ficar invisivel para o usuario e para manutencao."))

            if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == "print":
                if "management" not in rel.replace("\\", "/"):
                    achados.append(Achado("BAIXO", rel, f"print encontrado na linha {getattr(no, 'lineno', '?')}." , "Preferir logging em codigo de tela/servico."))

        if "TODO" in texto or "FIXME" in texto:
            achados.append(Achado("BAIXO", rel, "Arquivo possui TODO/FIXME.", "Revisar pendencias antes de novas alteracoes."))

        if detalhado:
            encontrados = [t for t in self.HARD_CODED_TERMS if t in texto]
            if encontrados:
                achados.append(Achado("BAIXO", rel, "Textos de fluxo/status/setor encontrados no codigo.", ", ".join(sorted(set(encontrados))) + ". Informativo: nao alterar regra sem validar banco."))

        return achados

    def _nome_excecao(self, tipo) -> str:
        if tipo is None:
            return ""
        if isinstance(tipo, ast.Name):
            return tipo.id
        if isinstance(tipo, ast.Attribute):
            return tipo.attr
        if isinstance(tipo, ast.Tuple):
            nomes = [self._nome_excecao(el) for el in tipo.elts]
            return ",".join(nomes)
        return ""

    def _auditar_template(self, rel: str, texto: str) -> list[Achado]:
        achados: list[Achado] = []
        if "csrf_token" not in texto and "<form" in texto.lower():
            achados.append(Achado("MEDIO", rel, "Template com formulario sem csrf_token aparente.", "Verificar se e GET ou se token esta em include."))
        if texto.count("{% block") != texto.count("{% endblock"):
            achados.append(Achado("ALTO", rel, "Quantidade de block/endblock divergente.", "Pode quebrar renderizacao do template."))
        return achados

    def _auditar_urls(self, base_dir: Path) -> list[Achado]:
        achados: list[Achado] = []
        urls = base_dir / "config" / "urls.py"
        if not urls.exists():
            return achados
        texto = urls.read_text(encoding="utf-8", errors="replace")
        nomes = re.findall(r"name\s*=\s*['\"]([^'\"]+)['\"]", texto)
        duplicados = [nome for nome, qtd in Counter(nomes).items() if qtd > 1]
        for nome in duplicados:
            achados.append(Achado("MEDIO", "config/urls.py", f"Nome de URL duplicado: {nome}.", "Pode causar reverse() indo para rota errada."))
        return achados

    def _auditar_banco(self) -> list[Achado]:
        achados: list[Achado] = []
        try:
            from core.models import AcaoEmEspera, FluxoAcaoSetor, Setor, StatusSAC
        except Exception as exc:
            return [Achado("ALTO", "Banco/Models", "Nao foi possivel importar models principais.", str(exc))]

        modelos_codigo = [
            ("StatusSAC", StatusSAC),
            ("Setor", Setor),
            ("AcaoEmEspera", AcaoEmEspera),
        ]
        for nome, modelo in modelos_codigo:
            if not hasattr(modelo, "codigo"):
                continue
            try:
                vazios = modelo.objects.filter(codigo__isnull=True).count() + modelo.objects.filter(codigo="").count()
                if vazios:
                    achados.append(Achado("ALTO", nome, f"Existem {vazios} registros sem codigo.", "Codigos vazios dificultam blindagem sem depender de nome exibido."))
                codigos = list(modelo.objects.values_list("codigo", flat=True))
                repetidos = [c for c, qtd in Counter(codigos).items() if c and qtd > 1]
                if repetidos:
                    achados.append(Achado("ALTO", nome, "Codigos duplicados encontrados.", ", ".join(map(str, repetidos[:20]))))
            except Exception as exc:
                achados.append(Achado("MEDIO", nome, "Nao foi possivel auditar codigos no banco.", str(exc)))

        try:
            total_fluxos = FluxoAcaoSetor.objects.count()
            if total_fluxos == 0:
                achados.append(Achado("ALTO", "FluxoAcaoSetor", "Nenhuma regra de fluxo cadastrada.", "As telas podem ficar sem proximo status/setor/acao."))
            campos = [f.name for f in FluxoAcaoSetor._meta.fields]
            filtros_nulos = []
            for campo in ["status_destino", "proximo_setor", "acao_destino", "proxima_acao"]:
                if campo in campos:
                    filtros_nulos.append(campo)
            for campo in filtros_nulos:
                kwargs = {f"{campo}__isnull": True}
                qtd = FluxoAcaoSetor.objects.filter(**kwargs).count()
                if qtd:
                    achados.append(Achado("MEDIO", "FluxoAcaoSetor", f"{qtd} fluxo(s) com {campo} vazio.", "Pode ser esperado para conclusao; revisar antes de alterar regras."))
        except Exception as exc:
            achados.append(Achado("MEDIO", "FluxoAcaoSetor", "Nao foi possivel auditar fluxos.", str(exc)))

        return achados

    def _montar_relatorio(self, achados: list[Achado], base_dir: Path, limite: int) -> str:
        por_nivel: dict[str, list[Achado]] = defaultdict(list)
        for achado in achados:
            por_nivel[achado.nivel].append(achado)

        linhas = []
        linhas.append("AUDITORIA DE BLINDAGEM PREVENTIVA DO SAC")
        linhas.append(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        linhas.append(f"Projeto: {base_dir}")
        linhas.append("Modo: SOMENTE LEITURA - nenhuma regra, banco ou arquivo existente foi alterado")
        linhas.append("")
        linhas.append("RESUMO")
        linhas.append(f"ALTO : {len(por_nivel.get('ALTO', []))}")
        linhas.append(f"MEDIO: {len(por_nivel.get('MEDIO', []))}")
        linhas.append(f"BAIXO: {len(por_nivel.get('BAIXO', []))}")
        linhas.append("")

        for nivel in ["ALTO", "MEDIO", "BAIXO"]:
            itens = por_nivel.get(nivel, [])
            linhas.append(f"[{nivel}] {len(itens)} achado(s)")
            for idx, achado in enumerate(itens[:limite], start=1):
                linhas.append(f"{idx}. {achado.origem} - {achado.mensagem}")
                if achado.detalhe:
                    linhas.append(f"   Detalhe: {achado.detalhe}")
            if len(itens) > limite:
                linhas.append(f"   ... mais {len(itens) - limite} achado(s) ocultos pelo limite.")
            linhas.append("")

        if not achados:
            linhas.append("Nenhum risco relevante encontrado pelos criterios atuais.")
            linhas.append("")

        linhas.append("ORIENTACAO")
        linhas.append("- Achados ALTO devem ser revisados antes de novas mudancas grandes.")
        linhas.append("- Achados MEDIO indicam risco de manutencao/regressao.")
        linhas.append("- Achados BAIXO sao informativos e nao exigem alteracao imediata.")
        linhas.append("- Este comando nao substitui homologacao manual das telas do SAC.")
        return "\n".join(linhas)
