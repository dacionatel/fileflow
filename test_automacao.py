from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "organizador_arquivos.py"


def garantir_base(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    return base


def executar_cli(pasta: Path, entradas: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--cli", str(pasta)],
        input=entradas,
        text=True,
        capture_output=True,
        check=False,
    )


def limpar_pasta(pasta: Path) -> None:
    if pasta.exists():
        shutil.rmtree(pasta)
    pasta.mkdir(parents=True, exist_ok=True)


def criar_pasta_organizacao(base: Path) -> Path:
    pasta = base / "teste_organizacao"
    limpar_pasta(pasta)
    (pasta / "pastinha").mkdir(parents=True, exist_ok=True)

    (pasta / "relatorio.txt").write_text("texto de teste", encoding="utf-8")
    (pasta / "foto.jpg").write_text("fake jpg data", encoding="utf-8")
    (pasta / "documento.pdf").write_text("fake pdf data", encoding="utf-8")
    (pasta / "arquivo_sem_extensao").write_text("sem extensao", encoding="utf-8")
    (pasta / "sub1.txt").write_text("mais um texto", encoding="utf-8")
    (pasta / "pastinha" / "arquivo2.txt").write_text("arquivo dentro de subpasta", encoding="utf-8")
    return pasta


def criar_pasta_duplicados(base: Path) -> Path:
    pasta = base / "teste_duplicados"
    limpar_pasta(pasta)

    (pasta / "copia_1.txt").write_text("conteudo idêntico", encoding="utf-8")
    shutil.copy2(pasta / "copia_1.txt", pasta / "copia_2.txt")
    (pasta / "unico.txt").write_text("conteudo diferente", encoding="utf-8")
    return pasta


def validar_organizacao(pasta: Path) -> None:
    resultado = executar_cli(pasta, "2\nMOVER\n")
    if resultado.returncode != 0:
        raise AssertionError(f"O programa falhou na organizacao: {resultado.stderr or resultado.stdout}")

    organizados = pasta / "Organizados"
    assert organizados.exists(), "A pasta Organizados nao foi criada."
    assert (organizados / "TXT").exists(), "Pasta TXT nao foi criada."
    assert (organizados / "JPG").exists(), "Pasta JPG nao foi criada."
    assert (organizados / "PDF").exists(), "Pasta PDF nao foi criada."
    assert any((organizados / "SemExtensao").iterdir()), "Nenhum arquivo foi movido para SemExtensao."
    print(f"[OK] Organizacao: {pasta}")


def validar_duplicados(pasta: Path) -> None:
    resultado = executar_cli(pasta, "1\n1\n2\nAPAGAR\n")
    if resultado.returncode != 0:
        raise AssertionError(f"O programa falhou na busca de duplicados: {resultado.stderr or resultado.stdout}")

    arquivos = sorted(pasta.iterdir())
    nomes = {arquivo.name for arquivo in arquivos if arquivo.is_file()}
    assert "copia_1.txt" in nomes or "copia_2.txt" in nomes, "Nenhum arquivo duplicado foi processado."
    assert "unico.txt" in nomes, "Arquivo unico foi removido indevidamente."
    print(f"[OK] Duplicados: {pasta}")


def main() -> None:
    if len(sys.argv) < 2:
        base = Path("E:\\CNC\\Laser\\DXF Files\\teste app")
        print(f"Nenhuma pasta informada. Usando padrao: {base}")
    else:
        base = Path(sys.argv[1]).expanduser().resolve()

    base = garantir_base(base)
    print(f"Pasta base de teste: {base}")

    organizacao = criar_pasta_organizacao(base)
    duplicados = criar_pasta_duplicados(base)

    validar_organizacao(organizacao)
    validar_duplicados(duplicados)

    print("\nTodos os testes automatizados passaram.")


if __name__ == "__main__":
    main()
