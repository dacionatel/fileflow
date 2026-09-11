from __future__ import annotations

import argparse
import ctypes
import hashlib
import shutil
import threading
import tkinter as tk
from collections import defaultdict
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

COR_TEXTO_BOTAO_ACAO = "#111827"
COR_FUNDO_BOTAO_ACAO = "#f3f4f6"


class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", wintypes.UINT),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", wintypes.LPVOID),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def enviar_para_lixeira(caminho: Path) -> None:
    """Envia um arquivo para a Lixeira do Windows sem exigir confirmacao extra."""
    operacao = SHFILEOPSTRUCTW(
        wFunc=3,
        pFrom=f"{caminho}\0\0",
        fFlags=0x0040 | 0x0010 | 0x0004 | 0x0400,
    )
    resultado = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operacao))
    if resultado != 0 or operacao.fAnyOperationsAborted:
        raise OSError(f"Falha ao enviar o arquivo para a Lixeira (codigo {resultado})")


def agora() -> str:
    """Retorna uma data legivel para os logs."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def calcular_percentual(atual: int, total: int) -> int:
    if total <= 0:
        return 0
    return max(0, min(100, int((atual / total) * 100)))


def arquivos_da_pasta(pasta: Path, callback=None) -> list[Path]:
    """Encontra todos os arquivos, sem entrar nas pastas criadas pelo programa."""
    arquivos = []
    pastas_ignoradas = {"Organizados"}
    itens = list(pasta.rglob("*"))
    total = len(itens)
    for index, caminho in enumerate(itens, start=1):
        if callback is not None:
            callback(calcular_percentual(index, total), caminho)
        if not caminho.is_file():
            continue
        if any(parente.name in pastas_ignoradas for parente in caminho.parents):
            continue
        if caminho.name == "organizador_log.txt":
            continue
        arquivos.append(caminho)

    return sorted(arquivos, key=lambda caminho: str(caminho).lower())


def pasta_organizados_existente(pasta: Path) -> bool:
    """Verifica se ja existe uma pasta Organizados dentro da pasta selecionada."""
    return (pasta / "Organizados").exists() and (pasta / "Organizados").is_dir()


def hash_arquivo(caminho: Path) -> str:
    """Calcula SHA-256 lendo o arquivo em blocos, sem carrega-lo inteiro na memoria."""
    sha256 = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            sha256.update(bloco)
    return sha256.hexdigest()


def encontrar_duplicados(arquivos: list[Path]) -> list[list[Path]]:
    """Agrupa arquivos diferentes que possuem exatamente o mesmo conteudo."""
    por_hash: dict[str, list[Path]] = defaultdict(list)
    for caminho in arquivos:
        por_hash[hash_arquivo(caminho)].append(caminho)
    return [grupo for grupo in por_hash.values() if len(grupo) > 1]


def registrar(caminho_log: Path, mensagem: str) -> None:
    with caminho_log.open("a", encoding="utf-8") as log:
        log.write(f"[{agora()}] {mensagem}\n")


def mostrar_duplicados(grupos: list[list[Path]], pasta: Path) -> None:
    print("\n=== Simulacao de duplicados ===")
    if not grupos:
        print("Nenhum duplicado encontrado.")
        return

    for numero, grupo in enumerate(grupos, start=1):
        print(f"\nGrupo {numero} (mesmo conteudo):")
        for indice, caminho in enumerate(grupo, start=1):
            print(f"  {indice}. {caminho.relative_to(pasta)}")


def indices_para_apagar(resposta: str, quantidade: int) -> set[int]:
    """Converte '1,3' em indices validos; entrada vazia significa nao apagar."""
    if not resposta.strip():
        return set()

    indices = set()
    for parte in resposta.replace(";", ",").split(","):
        try:
            indice = int(parte.strip())
        except ValueError:
            continue
        if 1 <= indice <= quantidade:
            indices.add(indice - 1)
    return indices


def escolhas_em_lote(resposta: str, grupos: list[list[Path]]) -> list[Path]:
    """Le escolhas no formato 'grupo:indices grupo:indices'."""
    apagar = []
    for selecao in resposta.split():
        try:
            grupo_texto, indices_texto = selecao.split(":", maxsplit=1)
            numero_grupo = int(grupo_texto)
            grupo = grupos[numero_grupo - 1]
        except (ValueError, IndexError):
            continue

        for indice in indices_para_apagar(indices_texto, len(grupo)):
            apagar.append(grupo[indice])
    return apagar


def escolher_duplicados(grupos: list[list[Path]], pasta: Path, caminho_log: Path) -> None:
    """Pergunta quais copias serao apagadas, sempre com confirmacao final."""
    if not grupos:
        return

    print("\nEscolha o modo de exclusao:")
    print("  1 - grupo por grupo")
    print("  2 - lote (uma resposta por grupo)")
    modo = input("Modo [1]: ").strip() or "1"
    apagar: list[Path] = []

    if modo == "2":
        print("Formato: grupo:indices, separado por espacos (ex: 1:2,3 2:1)")
        for numero, grupo in enumerate(grupos, start=1):
            print(f"  Grupo {numero}: {len(grupo)} arquivos")
        apagar.extend(escolhas_em_lote(input("Selecoes: "), grupos))
    else:
        for numero, grupo in enumerate(grupos, start=1):
            print(f"\nGrupo {numero}:")
            for indice, caminho in enumerate(grupo, start=1):
                print(f"  {indice}. {caminho.relative_to(pasta)}")
            resposta = input("Indices das copias a apagar (ex: 2,3; vazio mantem todas): ")
            for indice in indices_para_apagar(resposta, len(grupo)):
                apagar.append(grupo[indice])

    if not apagar:
        print("Nenhum arquivo selecionado para apagar.")
        return

    print("\nArquivos que serao apagados:")
    for caminho in apagar:
        print(f"  - {caminho.relative_to(pasta)}")
    confirmacao = input("Digite APAGAR para confirmar: ").strip()
    if confirmacao != "APAGAR":
        print("Exclusao cancelada.")
        return

    enviados = 0
    for caminho in apagar:
        try:
            enviar_para_lixeira(caminho)
            registrar(caminho_log, f"ENVIADO PARA A LIXEIRA | {caminho.relative_to(pasta)}")
            print(f"Enviado para a Lixeira: {caminho.relative_to(pasta)}")
            enviados += 1
        except OSError as erro:
            registrar(caminho_log, f"ERRO AO APAGAR | {caminho} | {erro}")
            print(f"Nao foi possivel apagar {caminho}: {erro}")

    if enviados:
        print(f"\n{enviados} arquivo(s) foram enviados para a Lixeira do Windows.")


def nome_destino_disponivel(destino: Path) -> Path:
    """Cria um sufixo numerado para nunca sobrescrever um arquivo."""
    if not destino.exists():
        return destino

    contador = 1
    while True:
        candidato = destino.with_name(
            f"{destino.stem}_{contador}{destino.suffix}"
        )
        if not candidato.exists():
            return candidato
        contador += 1


def destino_do_arquivo(caminho: Path, pasta: Path) -> Path | None:
    extensao = caminho.suffix.lower()
    categoria = extensao[1:].upper() if extensao else "SemExtensao"
    return pasta / "Organizados" / categoria / caminho.name


def simular_movimentos(
    arquivos: list[Path],
    pasta: Path,
    callback=None,
) -> list[tuple[Path, Path]]:
    movimentos = []
    destinos_reservados: set[Path] = set()
    for origem in arquivos:
        destino_base = destino_do_arquivo(origem, pasta)
        if destino_base is None:
            continue

        destino = destino_base
        contador = 1
        while destino.exists() or destino in destinos_reservados:
            destino = destino_base.with_name(
                f"{destino_base.stem}_{contador}{destino_base.suffix}"
            )
            contador += 1
        destinos_reservados.add(destino)
        item = (origem, destino)
        movimentos.append(item)
        if callback is not None:
            callback(item)
    return movimentos


def organizar(arquivos: list[Path], pasta: Path, caminho_log: Path) -> None:
    movimentos = simular_movimentos(arquivos, pasta)
    print("\n=== Simulacao de organizacao ===")
    if not movimentos:
        print("Nenhum arquivo encontrado para mover.")
        return

    for origem, destino in movimentos:
        print(f"  {origem.relative_to(pasta)} -> {destino.relative_to(pasta)}")

    confirmacao = input("\nDigite MOVER para confirmar: ").strip()
    if confirmacao != "MOVER":
        print("Movimentacao cancelada.")
        return

    movidos = 0
    pastas_destino: set[Path] = set()
    for origem, destino in movimentos:
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(origem), str(destino))
            registrar(
                caminho_log,
                f"MOVIDO | {origem.relative_to(pasta)} -> {destino.relative_to(pasta)}",
            )
            print(f"Movido: {destino.relative_to(pasta)}")
            movidos += 1
            pastas_destino.add(destino.parent)
        except OSError as erro:
            registrar(caminho_log, f"ERRO AO MOVER | {origem} | {erro}")
            print(f"Nao foi possivel mover {origem}: {erro}")

    if movidos:
        print(f"\n{movidos} arquivo(s) foram movidos com sucesso.")
        print("Pastas de destino:")
        for destino in sorted(pastas_destino, key=lambda caminho: str(caminho).lower()):
            print(f"  - {destino.relative_to(pasta)}")


def executar(pasta: Path, modo: str) -> None:
    pasta = pasta.expanduser().resolve()
    if not pasta.is_dir():
        raise SystemExit(f"A pasta nao existe: {pasta}")

    caminho_log = pasta / "organizador_log.txt"
    if pasta_organizados_existente(pasta):
        print("\nAVISO: a pasta 'Organizados' ja existe dentro da pasta selecionada.")
        print("Os arquivos dentro dela serao ignorados para evitar recursao e duplicacao de organizacao.")
    arquivos = arquivos_da_pasta(pasta)
    print(f"Pasta analisada: {pasta}")
    print(f"Arquivos encontrados: {len(arquivos)}")

    if modo == "1":
        grupos = encontrar_duplicados(arquivos)
        mostrar_duplicados(grupos, pasta)
        escolher_duplicados(grupos, pasta, caminho_log)
    else:
        organizar(arquivos, pasta, caminho_log)

    print(f"\nLog: {caminho_log}")


class OrganizadorGUI:
    def __init__(self, janela: tk.Tk, pasta_inicial: Path | None = None) -> None:
        self.janela = janela
        self.janela.title("Organizador de arquivos")
        self.janela.geometry("900x620")
        self.janela.minsize(720, 480)

        self.pasta = tk.StringVar(value=str(pasta_inicial) if pasta_inicial else "")
        self.status = tk.StringVar(value="Escolha uma pasta para começar.")
        self.arquivo_atual = tk.StringVar(value="Nenhuma atividade no momento.")
        self.progresso_texto = tk.StringVar(value="0%")
        self.percentual_analise = tk.StringVar(value="0% da análise concluída")
        self.arquivos: list[Path] = []
        self.grupos_duplicados: list[list[Path]] = []
        self.selecoes_duplicados: dict[Path, tk.BooleanVar] = {}
        self.movimentos: list[tuple[Path, Path]] = []
        self.trabalhando = False
        self._ultimo_percentual_atualizado = 0
        self._job_id = 0
        self.manter_antigos = tk.BooleanVar(value=False)

        self._configurar_estilo()
        self._montar_interface()

    def _configurar_estilo(self) -> None:
        estilo = ttk.Style(self.janela)
        try:
            estilo.theme_use("vista")
        except tk.TclError:
            estilo.theme_use("clam")
        estilo.configure("Title.TLabel", font=("Segoe UI", 22, "bold"))
        estilo.configure("Subtitle.TLabel", foreground="#5f6368")
        estilo.configure(
            "Action.TButton",
            padding=(14, 8),
            font=("Segoe UI", 10, "bold"),
            foreground=COR_TEXTO_BOTAO_ACAO,
            background=COR_FUNDO_BOTAO_ACAO,
        )
        estilo.configure(
            "Action.TButton",
            foreground=COR_TEXTO_BOTAO_ACAO,
            background=COR_FUNDO_BOTAO_ACAO,
        )
        estilo.configure("Trash.TButton", padding=(14, 8), font=("Segoe UI", 10, "bold"))
        estilo.map(
            "Action.TButton",
            foreground=[("disabled", "#8a8a8a"), ("active", COR_TEXTO_BOTAO_ACAO), ("!disabled", COR_TEXTO_BOTAO_ACAO)],
            background=[("disabled", "#e4e4e4"), ("active", "#dbeafe"), ("!disabled", COR_FUNDO_BOTAO_ACAO)],
        )
        estilo.map(
            "Trash.TButton",
            foreground=[("disabled", "#8a8a8a"), ("active", "#075985"), ("!disabled", "#075985")],
            background=[("disabled", "#e4e4e4"), ("active", "#dbeafe"), ("!disabled", "#e0f2fe")],
        )

    def _montar_interface(self) -> None:
        principal = ttk.Frame(self.janela, padding=24)
        principal.pack(fill="both", expand=True)

        ttk.Label(principal, text="Organizador de arquivos", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            principal,
            text="Organize por extensao e encontre duplicados com seguranca.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 18))

        modos = ttk.Frame(principal)
        modos.pack(fill="x", pady=(0, 12))
        self.botao_organizar = tk.Button(
            modos,
            text="Organizar arquivos",
            fg=COR_TEXTO_BOTAO_ACAO,
            bg=COR_FUNDO_BOTAO_ACAO,
            activeforeground=COR_TEXTO_BOTAO_ACAO,
            activebackground="#dbeafe",
            font=("Segoe UI", 10, "bold"),
            relief="raised",
            bd=1,
            padx=14,
            pady=8,
            command=lambda: self._mostrar_aba("organizar"),
        )
        self.botao_organizar.pack(side="left")
        self.botao_duplicados = tk.Button(
            modos,
            text="Encontrar arquivos duplicados",
            fg=COR_TEXTO_BOTAO_ACAO,
            bg=COR_FUNDO_BOTAO_ACAO,
            activeforeground=COR_TEXTO_BOTAO_ACAO,
            activebackground="#dbeafe",
            font=("Segoe UI", 10, "bold"),
            relief="raised",
            bd=1,
            padx=14,
            pady=8,
            command=lambda: self._mostrar_aba("duplicados"),
        )
        self.botao_duplicados.pack(side="left", padx=(10, 0))

        pasta_frame = ttk.LabelFrame(principal, text="Pasta de trabalho", padding=12)
        pasta_frame.pack(fill="x", pady=(0, 16))
        ttk.Entry(pasta_frame, textvariable=self.pasta).pack(side="left", fill="x", expand=True)
        self.botao_escolher_pasta = tk.Button(
            pasta_frame,
            text="Escolher pasta...",
            fg=COR_TEXTO_BOTAO_ACAO,
            bg=COR_FUNDO_BOTAO_ACAO,
            activeforeground=COR_TEXTO_BOTAO_ACAO,
            activebackground="#dbeafe",
            font=("Segoe UI", 9),
            relief="raised",
            bd=1,
            command=self.escolher_pasta,
        )
        self.botao_escolher_pasta.pack(
            side="left", padx=(10, 0)
        )

        self.painel_ativo = ttk.Frame(principal)
        self.painel_ativo.pack(fill="both", expand=True)
        self.aba_organizar = ttk.Frame(self.painel_ativo, padding=12)
        self.aba_duplicados = ttk.Frame(self.painel_ativo, padding=12)
        self._montar_aba_organizar()
        self._montar_aba_duplicados()
        self._mostrar_aba("organizar")

        rodape = ttk.Frame(principal)
        rodape.pack(fill="x", pady=(14, 0))
        info = ttk.Frame(rodape)
        info.pack(side="left", fill="x", expand=True)
        ttk.Label(info, textvariable=self.status, style="Subtitle.TLabel").pack(anchor="w")
        ttk.Label(info, textvariable=self.arquivo_atual, foreground="#1f2937", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(2, 0))
        ttk.Label(info, textvariable=self.progresso_texto, foreground="#374151", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(2, 0))
        self.progresso_texto.set("0%")
        self.percentual_analise.set("0% da análise concluída")
        self._configurar_hover_botoes()

    def _configurar_hover_botoes(self) -> None:
        botoes = (
            self.botao_organizar,
            self.botao_duplicados,
            self.botao_escolher_pasta,
            self.botao_analisar_organizacao,
            self.botao_mover,
            self.botao_procurar_duplicados,
            self.botao_lixeira,
            self.opcao_manter_antigos,
        )
        for botao in botoes:
            botao.bind("<Enter>", self._mostrar_hover_botao, add="+")
            botao.bind("<Leave>", self._remover_hover_botao, add="+")

    def _mostrar_hover_botao(self, evento) -> None:
        botao = evento.widget
        if str(botao.cget("state")) != "disabled":
            botao._cor_fundo_antes_hover = botao.cget("bg")
            botao.configure(bg="#dbeafe")

    def _remover_hover_botao(self, evento) -> None:
        botao = evento.widget
        cor_original = getattr(botao, "_cor_fundo_antes_hover", COR_FUNDO_BOTAO_ACAO)
        botao.configure(bg=cor_original)

    def _montar_aba_organizar(self) -> None:
        ttk.Label(
            self.aba_organizar,
            text="Destino previsto: os arquivos serao movidos para uma pasta Organizados\\EXTENSAO dentro da pasta selecionada.",
        ).pack(anchor="w")
        controles_analise = ttk.Frame(self.aba_organizar)
        controles_analise.pack(fill="x", pady=12)
        self.botao_analisar_organizacao = tk.Button(
            controles_analise,
            text="Analisar pasta",
            fg=COR_TEXTO_BOTAO_ACAO,
            bg=COR_FUNDO_BOTAO_ACAO,
            activeforeground=COR_TEXTO_BOTAO_ACAO,
            activebackground="#dbeafe",
            font=("Segoe UI", 10, "bold"),
            relief="raised",
            bd=1,
            command=self.analisar_organizacao,
        )
        self.botao_analisar_organizacao.pack(side="left")

        informacoes_analise = ttk.Frame(controles_analise)
        informacoes_analise.pack(side="left", padx=(14, 0), fill="x", expand=True)

        botoes = ttk.Frame(self.aba_organizar)
        botoes.pack(side="bottom", fill="x", pady=(10, 0), ipady=10)
        botoes.pack_propagate(False)
        botoes.configure(height=48)
        self.botao_mover = tk.Button(
            botoes,
            text="Mover arquivos",
            fg=COR_TEXTO_BOTAO_ACAO,
            bg=COR_FUNDO_BOTAO_ACAO,
            activeforeground=COR_TEXTO_BOTAO_ACAO,
            activebackground="#dbeafe",
            font=("Segoe UI", 10, "bold"),
            relief="raised",
            bd=1,
            padx=14,
            pady=8,
            command=self.mover_arquivos,
            state="disabled",
        )
        self.botao_mover.pack(side="right")

        self.percentual_analise_label = ttk.Label(
            informacoes_analise,
            textvariable=self.percentual_analise,
            foreground="#1f2937",
            font=("Segoe UI", 10, "bold"),
        )
        self.percentual_analise_label.pack(side="left")
        self.mensagem_organizacao = ttk.Label(
            informacoes_analise,
            text="Aguardando analise da pasta...",
            style="Subtitle.TLabel",
            foreground="#374151",
        )
        self.mensagem_organizacao.pack(side="left", padx=(14, 0))
        self.lista_movimentos = self._criar_lista(self.aba_organizar)

    def _montar_aba_duplicados(self) -> None:
        ttk.Label(
            self.aba_duplicados,
            text="Clique em Procurar duplicados. Depois selecione os arquivos que deseja remover.",
        ).pack(anchor="w")
        controles_duplicados = ttk.Frame(self.aba_duplicados)
        controles_duplicados.pack(fill="x", pady=12)
        self.botao_procurar_duplicados = tk.Button(
            controles_duplicados,
            text="Procurar duplicados",
            fg=COR_TEXTO_BOTAO_ACAO,
            bg=COR_FUNDO_BOTAO_ACAO,
            activeforeground=COR_TEXTO_BOTAO_ACAO,
            activebackground="#dbeafe",
            font=("Segoe UI", 10, "bold"),
            relief="raised",
            bd=1,
            command=self.analisar_duplicados,
        )
        self.botao_procurar_duplicados.pack(side="left")
        ttk.Label(
            controles_duplicados,
            textvariable=self.percentual_analise,
            foreground="#1f2937",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", padx=(14, 0))

        botoes = ttk.Frame(self.aba_duplicados)
        botoes.pack(side="bottom", fill="x", pady=(10, 0))
        self.botao_lixeira = tk.Button(
            botoes,
            text="Enviar selecao para a Lixeira",
            width=30,
            fg="#075985",
            bg="#e0f2fe",
            activeforeground="#075985",
            activebackground="#bae6fd",
            font=("Segoe UI", 10, "bold"),
            relief="raised",
            bd=1,
            command=self.enviar_selecionados,
            state="disabled",
        )
        self.botao_lixeira.pack(side="right")
        self.opcao_manter_antigos = tk.Checkbutton(
            botoes,
            text="Manter os mais antigos",
            variable=self.manter_antigos,
            command=self._selecionar_duplicados_mais_novos,
            bg="#f0f9ff",
            activebackground="#e0f2fe",
            font=("Segoe UI", 9),
            state="disabled",
        )
        self.opcao_manter_antigos.pack(side="left", padx=(0, 8))

        ttk.Label(
            self.aba_duplicados,
            text="Selecao: clique em um arquivo; use Ctrl para escolher varios ou Shift para escolher um intervalo.",
            style="Subtitle.TLabel",
        ).pack(side="bottom", anchor="w", pady=(6, 0))

        self.lista_duplicados = self._criar_lista(self.aba_duplicados)
        self.lista_duplicados.bind("<<ListboxSelect>>", self._atualizar_botao_lixeira)
        self.mensagem_duplicados = ttk.Label(
            self.aba_duplicados,
            text="Aguardando busca por duplicados...",
            style="Subtitle.TLabel",
            foreground="#374151",
        )
        self.mensagem_duplicados.pack(anchor="w", pady=(10, 0))

    def _criar_lista(self, pai: ttk.Frame) -> tk.Listbox:
        moldura = ttk.Frame(pai)
        moldura.pack(fill="both", expand=True)
        lista = tk.Listbox(moldura, selectmode="extended", activestyle="none", font=("Segoe UI", 10))
        barra = ttk.Scrollbar(moldura, orient="vertical", command=lista.yview)
        lista.configure(yscrollcommand=barra.set)
        lista.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        return lista

    def escolher_pasta(self) -> None:
        pasta = filedialog.askdirectory(title="Escolha a pasta para analisar")
        if pasta:
            self.pasta.set(pasta)
            self.status.set("Pasta selecionada. Escolha uma analise.")

    def _mostrar_aba(self, nome: str) -> None:
        for aba in (self.aba_organizar, self.aba_duplicados):
            aba.pack_forget()
        if nome == "organizar":
            self.aba_organizar.pack(fill="both", expand=True)
            self.botao_organizar.configure(bg="#dbeafe", fg=COR_TEXTO_BOTAO_ACAO)
            self.botao_duplicados.configure(bg=COR_FUNDO_BOTAO_ACAO, fg=COR_TEXTO_BOTAO_ACAO)
        else:
            self.aba_duplicados.pack(fill="both", expand=True)
            self.botao_duplicados.configure(bg="#dbeafe", fg=COR_TEXTO_BOTAO_ACAO)
            self.botao_organizar.configure(bg=COR_FUNDO_BOTAO_ACAO, fg=COR_TEXTO_BOTAO_ACAO)

    def _obter_pasta(self) -> Path | None:
        texto = self.pasta.get().strip()
        if not texto:
            messagebox.showwarning("Pasta obrigatoria", "Escolha uma pasta antes de continuar.")
            return None
        pasta = Path(texto).expanduser().resolve()
        if not pasta.is_dir():
            messagebox.showerror("Pasta invalida", "A pasta escolhida nao existe.")
            return None
        return pasta

    def _atualizar_progresso(self, percentual: int, texto: str | None = None, etapa: str = "análise") -> None:
        percentual = max(0, min(100, percentual))
        if percentual != self._ultimo_percentual_atualizado or texto:
            self.progresso_texto.set(texto or f"{percentual}%")
            self.percentual_analise.set(f"{percentual}% da {etapa} concluída")
            if percentual == 100 and etapa == "análise" and hasattr(self, "mensagem_organizacao"):
                self.mensagem_organizacao.configure(
                    text="Esta e a simulacao do destino final. Nenhuma pasta foi criada ainda."
                )
                self.botao_mover.configure(state="normal")
            self.janela.update_idletasks()
        self._ultimo_percentual_atualizado = percentual

    def _atualizar_progresso_movimentacao(self, indice: int, total: int, nome: str | None = None) -> None:
        if total <= 0:
            percentual = 0
        else:
            percentual = min(100, max(0, int((indice / total) * 100)))
        titulo = f"{percentual}% - {nome}" if nome else f"{percentual}%"
        self._atualizar_progresso(percentual, titulo, etapa="transferência")
        if nome:
            self.arquivo_atual.set(f"Arquivo atual: {nome}")

    def _set_estado_trabalho(self, trabalhando: bool, mensagem: str | None = None, arquivo: str | None = None) -> None:
        self.trabalhando = trabalhando
        if trabalhando:
            self.status.set(mensagem or "Processando arquivos...")
            self.arquivo_atual.set(arquivo or "Processando arquivos...")
            self._ultimo_percentual_atualizado = 0
            self.progresso_texto.set("0%")
            self.percentual_analise.set("0% da análise concluída")
        else:
            self.status.set(mensagem or "Pronto.")
            self.arquivo_atual.set(arquivo if arquivo is not None else "")
            self._ultimo_percentual_atualizado = 100
            self.progresso_texto.set("100%")
            self.percentual_analise.set("100% da análise concluída")
            self._resetar_mensagens_trabalho()
        self.janela.update_idletasks()

        for widget in (
            self.botao_mover,
            self.botao_lixeira,
            self.opcao_manter_antigos,
            self.botao_organizar,
            self.botao_duplicados,
            self.botao_analisar_organizacao,
            self.botao_procurar_duplicados,
        ):
            try:
                widget.configure(state="disabled" if trabalhando else "normal")
            except tk.TclError:
                pass

    def _resetar_mensagens_trabalho(self) -> None:
        if hasattr(self, "mensagem_organizacao"):
            self.mensagem_organizacao.configure(text="Aguardando analise da pasta...")
        if hasattr(self, "mensagem_duplicados"):
            self.mensagem_duplicados.configure(text="Aguardando busca por duplicados...")

    def _resetar_estado_final(self, mensagem: str = "Pronto.") -> None:
        self._ultimo_percentual_atualizado = 100
        self.progresso_texto.set("100%")
        self.percentual_analise.set("100% da análise concluída")
        self.status.set(mensagem)
        self.arquivo_atual.set("")
        self._resetar_mensagens_trabalho()
        self.trabalhando = False
        for widget in (
            self.botao_organizar,
            self.botao_duplicados,
            self.botao_analisar_organizacao,
            self.botao_procurar_duplicados,
        ):
            widget.configure(state="normal")
        self.janela.update_idletasks()

    def _iniciar_analise(self, acao) -> None:
        pasta = self._obter_pasta()
        if pasta is None:
            return
        if pasta_organizados_existente(pasta):
            messagebox.showwarning(
                "Pasta Organizados detectada",
                "A pasta 'Organizados' ja existe dentro da pasta selecionada.\n"
                "Ela sera ignorada para evitar recursao e processamento indevido."
            )
        self._job_id += 1
        job_id = self._job_id
        self._set_estado_trabalho(True, "Analisando arquivos... Este processo pode levar alguns segundos.", "Processando: listando arquivos da pasta...")

        def executar_em_segundo_plano() -> None:
            try:
                resultado = acao(pasta, job_id)
                self.janela.after(0, lambda: self._finalizar_analise(resultado, job_id))
            except OSError as erro:
                self.janela.after(0, lambda: self._mostrar_erro(erro, job_id))

        threading.Thread(target=executar_em_segundo_plano, daemon=True).start()

    def _finalizar_analise(self, resultado, job_id: int | None = None) -> None:
        if job_id is not None and job_id != self._job_id:
            return
        self._resetar_estado_final("Analise concluida.")
        self.janela.after(0, resultado)

    def _mostrar_erro(self, erro: OSError, job_id: int | None = None) -> None:
        if job_id is not None and job_id != self._job_id:
            return
        self.status.set("A analise nao foi concluida.")
        messagebox.showerror("Erro", str(erro))

    def analisar_organizacao(self) -> None:
        self.lista_movimentos.delete(0, tk.END)

        def analisar(pasta: Path, job_id: int):
            itens = list(pasta.rglob("*"))
            total_itens = len(itens) or 1
            arquivos: list[Path] = []
            ultimo_percentual = -1

            for indice, caminho in enumerate(itens, start=1):
                if self._job_id != job_id:
                    return lambda: None
                if not caminho.is_file():
                    continue
                if any(parente.name == "Organizados" for parente in caminho.parents):
                    continue
                if caminho.name == "organizador_log.txt":
                    continue
                arquivos.append(caminho)
                percentual = calcular_percentual(indice, total_itens)
                if percentual != ultimo_percentual and (percentual % 5 == 0 or percentual == 100):
                    nome = caminho.name if len(caminho.name) <= 40 else f"{caminho.name[:37]}..."
                    self.janela.after(0, lambda p=percentual, n=nome: self._atualizar_progresso(p, f"{p}% - {n}") if self._job_id == job_id else None)
                    ultimo_percentual = percentual

            movimentos: list[tuple[Path, Path]] = []

            def on_movimento(item: tuple[Path, Path]) -> None:
                if self._job_id != job_id:
                    return
                movimentos.append(item)
                self.janela.after(0, lambda item=item: self._adicionar_movimento(pasta, item, job_id))

            simular_movimentos(arquivos, pasta, callback=on_movimento)
            self.janela.after(0, lambda: self._atualizar_progresso(100, "100% - lista pronta") if self._job_id == job_id else None)
            return lambda: self._exibir_movimentos(pasta, movimentos)

        self._iniciar_analise(analisar)

    def _adicionar_movimento(self, pasta: Path, movimento: tuple[Path, Path], job_id: int | None = None) -> None:
        if job_id is not None and job_id != self._job_id:
            return
        origem, destino = movimento
        self.lista_movimentos.insert(tk.END, f"{origem.relative_to(pasta)}  ->  {destino.relative_to(pasta)}")
        self.arquivo_atual.set(f"Arquivo em processamento: {origem.name}")

    def _popular_lista_movimentos(self, pasta: Path, movimentos: list[tuple[Path, Path]], indice_inicial: int = 0, lote: int = 100) -> None:
        limite = min(indice_inicial + lote, len(movimentos))
        for i in range(indice_inicial, limite):
            origem, destino = movimentos[i]
            self.lista_movimentos.insert(tk.END, f"{origem.relative_to(pasta)}  ->  {destino.relative_to(pasta)}")
            self.arquivo_atual.set(f"Arquivo em processamento: {origem.name}")

        if limite < len(movimentos):
            self.janela.after(0, lambda: self._popular_lista_movimentos(pasta, movimentos, limite, lote))
            return

        self.botao_mover.configure(state="normal")
        self.status.set(f"{len(movimentos)} arquivo(s) pronto(s) para organizar.")
        self.mensagem_organizacao.configure(text="Esta e a simulacao do destino final. Nenhuma pasta foi criada ainda.")

    def _exibir_movimentos(self, pasta: Path, movimentos: list[tuple[Path, Path]]) -> None:
        self.movimentos = movimentos
        self.trabalhando = False
        self._ultimo_percentual_atualizado = 100
        self.progresso_texto.set("100%")
        self.percentual_analise.set("100% da análise concluída")
        self.arquivo_atual.set("")
        self.mensagem_organizacao.configure(text="Esta e a simulacao do destino final. Nenhuma pasta foi criada ainda.")
        self.mensagem_duplicados.configure(text="Aguardando busca por duplicados...")
        self.botao_organizar.configure(state="normal")
        self.botao_duplicados.configure(state="normal")
        self.botao_analisar_organizacao.configure(state="normal")
        self.botao_procurar_duplicados.configure(state="normal")
        if not movimentos:
            self.lista_movimentos.insert(tk.END, "Nenhum arquivo encontrado para mover.")
            self.status.set("Nenhum arquivo encontrado para organizar.")
            self.botao_mover.configure(state="disabled")
            self.janela.update_idletasks()
            return

        if self.lista_movimentos.size() == 0:
            for origem, destino in movimentos:
                self.lista_movimentos.insert(tk.END, f"{origem.relative_to(pasta)}  ->  {destino.relative_to(pasta)}")

        self.botao_mover.configure(state="normal")
        self.status.set(f"{len(movimentos)} arquivo(s) pronto(s) para organizar.")
        self.janela.update_idletasks()

    def mover_arquivos(self) -> None:
        pasta = self._obter_pasta()
        if pasta is None or not self.movimentos:
            return
        if not messagebox.askyesno("Confirmar movimentacao", f"Mover {len(self.movimentos)} arquivo(s) agora?"):
            return

        movimentos = list(self.movimentos)
        total = len(movimentos)
        self._set_estado_trabalho(True, "Movendo arquivos...", "Preparando a movimentacao...")

        def executar() -> None:
            log = pasta / "organizador_log.txt"
            movidos = 0
            try:
                for indice, (origem, destino) in enumerate(movimentos, start=1):
                    self.janela.after(0, lambda i=indice, t=total, o=origem: self._atualizar_progresso_movimentacao(i, t, o.name))
                    try:
                        destino.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(origem), str(destino))
                        registrar(log, f"MOVIDO | {origem.relative_to(pasta)} -> {destino.relative_to(pasta)}")
                        movidos += 1
                    except OSError as erro:
                        registrar(log, f"ERRO AO MOVER | {origem} | {erro}")
            finally:
                self.janela.after(0, lambda: self._finalizar_movimentacao(pasta, movidos))

        threading.Thread(target=executar, daemon=True).start()

    def _finalizar_movimentacao(self, pasta: Path, movidos: int) -> None:
        self.movimentos = []
        self.lista_movimentos.delete(0, tk.END)
        self.botao_mover.configure(state="disabled")
        self._ultimo_percentual_atualizado = 100
        self.progresso_texto.set("100%")
        self.percentual_analise.set("100% da transferência concluída")
        self.status.set(f"{movidos} arquivo(s) movido(s) com sucesso.")
        self.arquivo_atual.set("")
        self._resetar_mensagens_trabalho()
        self.trabalhando = False
        self.janela.update_idletasks()
        messagebox.showinfo("Concluido", f"{movidos} arquivo(s) foram organizados.")

    def analisar_duplicados(self) -> None:
        def analisar(pasta: Path, job_id: int):
            itens = list(pasta.rglob("*"))
            total_itens = len(itens) or 1
            arquivos: list[Path] = []
            ultimo_percentual = -1

            for indice, caminho in enumerate(itens, start=1):
                if self._job_id != job_id:
                    return lambda: None
                if not caminho.is_file():
                    continue
                if any(parente.name == "Organizados" for parente in caminho.parents):
                    continue
                if caminho.name == "organizador_log.txt":
                    continue
                arquivos.append(caminho)
                percentual = calcular_percentual(indice, total_itens)
                if percentual != ultimo_percentual and (percentual % 5 == 0 or percentual == 100):
                    nome = caminho.name if len(caminho.name) <= 40 else f"{caminho.name[:37]}..."
                    self.janela.after(
                        0,
                        lambda p=percentual, n=nome: self._atualizar_progresso(p, f"{p}% - {n}")
                        if self._job_id == job_id
                        else None,
                    )
                    ultimo_percentual = percentual

            grupos = encontrar_duplicados(arquivos)
            self.janela.after(
                0,
                lambda: self._atualizar_progresso(100, "100% - lista pronta")
                if self._job_id == job_id
                else None,
            )
            return lambda: self._exibir_duplicados(pasta, grupos)

        self._iniciar_analise(analisar)

    def _exibir_duplicados(self, pasta: Path, grupos: list[list[Path]]) -> None:
        self.grupos_duplicados = grupos
        self.selecoes_duplicados = {}
        self.manter_antigos.set(False)
        self.lista_duplicados.delete(0, tk.END)
        self.mensagem_duplicados.configure(text="")
        if not grupos:
            self.lista_duplicados.insert(tk.END, "Nenhum arquivo duplicado foi encontrado nesta pasta.")
            self.status.set("Nenhum arquivo duplicado encontrado.")
            self.botao_lixeira.configure(state="disabled")
            self.opcao_manter_antigos.configure(state="disabled")
            return

        for numero, grupo in enumerate(grupos, start=1):
            self.lista_duplicados.insert(tk.END, f"Grupo {numero} - {len(grupo)} copias")
            for caminho in grupo:
                self.lista_duplicados.insert(tk.END, f"    {caminho.relative_to(pasta)}")
        self.botao_lixeira.configure(state="disabled")
        self.opcao_manter_antigos.configure(state="normal")
        self.status.set(f"{len(grupos)} grupo(s) encontrado(s). Selecione as linhas dos arquivos para apagar.")

    def _selecionar_duplicados_mais_novos(self) -> None:
        self.lista_duplicados.selection_clear(0, tk.END)
        if not self.manter_antigos.get() or not self.grupos_duplicados:
            self.mensagem_duplicados.configure(text="Selecione manualmente os arquivos que deseja enviar para a Lixeira.")
            self._atualizar_botao_lixeira()
            return

        indice_lista = 0
        quantidade_selecionada = 0
        for grupo in self.grupos_duplicados:
            indice_lista += 1
            mais_antigo = min(grupo, key=lambda caminho: (caminho.stat().st_mtime, str(caminho).lower()))
            for caminho in grupo:
                if caminho != mais_antigo:
                    self.lista_duplicados.selection_set(indice_lista)
                    quantidade_selecionada += 1
                indice_lista += 1

        self.mensagem_duplicados.configure(
            text="Os arquivos mais novos foram selecionados. O mais antigo de cada grupo sera mantido."
        )
        self.status.set(f"{quantidade_selecionada} arquivo(s) selecionado(s) para a Lixeira.")
        self._atualizar_botao_lixeira()

    def _atualizar_botao_lixeira(self, _evento=None) -> None:
        if not self.grupos_duplicados:
            self.botao_lixeira.configure(state="disabled")
            return
        selecionados = self.lista_duplicados.curselection()
        indice_lista = -1
        existe_arquivo_selecionado = False
        for grupo in self.grupos_duplicados:
            indice_lista += 1
            for _caminho in grupo:
                indice_lista += 1
                if indice_lista in selecionados:
                    existe_arquivo_selecionado = True
        self.botao_lixeira.configure(state="normal" if existe_arquivo_selecionado else "disabled")
        if existe_arquivo_selecionado:
            self.status.set(f"{len(selecionados)} linha(s) selecionada(s). O botao da Lixeira esta disponivel.")
        else:
            self.status.set("Selecione um ou mais arquivos para habilitar o botao da Lixeira.")

    def enviar_selecionados(self) -> None:
        pasta = self._obter_pasta()
        if pasta is None or not self.grupos_duplicados:
            return
        selecionados = self.lista_duplicados.curselection()
        caminhos: list[Path] = []
        indice_lista = -1
        for grupo in self.grupos_duplicados:
            indice_lista += 1
            for caminho in grupo:
                indice_lista += 1
                if indice_lista in selecionados:
                    caminhos.append(caminho)
        if not caminhos:
            messagebox.showwarning("Nenhuma selecao", "Selecione os arquivos nas linhas da lista.")
            return
        if not messagebox.askyesno("Confirmar exclusao", f"Enviar {len(caminhos)} arquivo(s) para a Lixeira?"):
            return

        arquivos = list(caminhos)
        self._set_estado_trabalho(True, "Enviando arquivos para a Lixeira...", "Preparando exclusao...")

        def executar() -> None:
            log = pasta / "organizador_log.txt"
            enviados = 0
            try:
                for caminho in arquivos:
                    self.janela.after(0, lambda caminho=caminho: self._set_estado_trabalho(True, "Enviando arquivos para a Lixeira...", f"Arquivo atual: {caminho.name}"))
                    try:
                        enviar_para_lixeira(caminho)
                        registrar(log, f"ENVIADO PARA A LIXEIRA | {caminho.relative_to(pasta)}")
                        enviados += 1
                    except OSError as erro:
                        registrar(log, f"ERRO AO APAGAR | {caminho} | {erro}")
            finally:
                self.janela.after(0, self._finalizar_exclusao)

        threading.Thread(target=executar, daemon=True).start()

    def _finalizar_exclusao(self) -> None:
        self.analisar_duplicados()
        self._ultimo_percentual_atualizado = 100
        self.progresso_texto.set("100%")
        self.percentual_analise.set("100% da análise concluída")
        self.status.set(f"{len(self.grupos_duplicados)} arquivo(s) enviado(s) para a Lixeira.")
        self.arquivo_atual.set("")
        self._resetar_mensagens_trabalho()
        self.trabalhando = False
        self.janela.update_idletasks()


def iniciar_interface(pasta_inicial: Path | None = None) -> None:
    janela = tk.Tk()
    OrganizadorGUI(janela, pasta_inicial)
    janela.mainloop()


def solicitar_modo() -> str:
    while True:
        print("\nO que voce deseja fazer?")
        print("  1 - Verificar arquivos duplicados")
        print("  2 - Organizar arquivos")
        resposta = input("Escolha uma opcao [1 ou 2]: ").strip()
        if resposta in {"1", "2"}:
            return resposta
        print("Opcao invalida. Digite 1 ou 2.")


def solicitar_pasta() -> Path:
    print("\nQual pasta voce deseja organizar?")
    print(r"Digite o caminho completo, por exemplo: C:\Users\SeuNome\Downloads\arquivos")
    print("Voce pode colar o caminho com ou sem aspas. Deixe vazio para usar a pasta atual.")
    resposta = input("Caminho da pasta: ").strip()
    return Path(resposta.strip('"')) if resposta else Path(".")


def principal() -> None:
    parser = argparse.ArgumentParser(
        description="Verifica arquivos duplicados ou organiza arquivos por extensao."
    )
    parser.add_argument(
        "pasta",
        nargs="?",
        default=None,
        help="Pasta a analisar (se omitida, sera perguntada)",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Usa a interface antiga no terminal",
    )
    argumentos = parser.parse_args()
    if not argumentos.cli:
        iniciar_interface(Path(argumentos.pasta) if argumentos.pasta else None)
        return
    modo = solicitar_modo()
    pasta = Path(argumentos.pasta) if argumentos.pasta else solicitar_pasta()
    executar(pasta, modo)


if __name__ == "__main__":
    principal()
