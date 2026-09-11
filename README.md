# Organizador de arquivos

Programa iniciante em Python para verificar arquivos duplicados ou organizar arquivos de qualquer tipo.

## Preparacao

Instale o Python 3 pelo site oficial (marcando a opcao para adicionar Python ao `PATH`). Depois confirme no PowerShell:

```powershell
python --version
```

## Como executar

Por padrao, o programa abre uma interface grafica. Nela, escolha a pasta com o
botao **Escolher pasta...**, selecione uma aba e clique em **Analisar pasta**.
Na organizacao, confira a simulacao e clique em **Mover arquivos**. Na busca
por duplicados, selecione as linhas dos arquivos com `Ctrl` ou `Shift` e clique
em **Enviar selecionados para a Lixeira**. As operacoes ainda pedem confirmacao
antes de alterar qualquer arquivo.

Para abrir a interface:

```powershell
python organizador_arquivos.py
```

O modo antigo no terminal continua disponivel com `--cli`:

Abra o PowerShell nesta pasta e rode:

```powershell
python organizador_arquivos.py --cli "C:\caminho\da\pasta"
```

Se o caminho tiver espacos, mantenha as aspas. Para usar a pasta atual:

```powershell
python organizador_arquivos.py --cli
```

Quando nenhum caminho for informado no comando, o programa perguntara qual pasta
deve ser organizada e mostrara um exemplo de preenchimento. Voce tambem pode
deixar a resposta vazia para usar a pasta atual.

## O que acontece

1. No inicio, escolha `1` para verificar duplicados ou `2` para organizar arquivos.
2. O programa considera arquivos de qualquer extensao, inclusive arquivos sem extensao.
3. No modo de duplicados, calcula o hash SHA-256 e mostra arquivos com o mesmo conteudo.
4. Voce escolhe quais copias enviar para a Lixeira. A opcao **Manter os mais antigos** seleciona automaticamente os arquivos mais novos de cada grupo para revisao. Nada e removido sem confirmacao.
5. No modo de organizacao, o programa mostra uma simulacao dos movimentos.
6. Os arquivos sao organizados em `Organizados\EXTENSAO` ou `Organizados\SemExtensao`.
7. Nada e movido sem digitar `MOVER`.
8. O arquivo `organizador_log.txt` registra exclusoes, movimentos e erros com data e hora.
9. Se ja existir um nome no destino, o programa usa sufixos como `_1`, `_2` e assim por diante.

O log preserva o caminho original e o novo caminho dos arquivos movidos, o que permite desfazer manualmente uma operacao com seguranca.

## Conceitos principais

- `pathlib.Path`: representa caminhos de forma segura no Windows e em outros sistemas.
- `hashlib.sha256`: calcula uma assinatura do conteudo; nomes iguais ou diferentes nao importam.
- `shutil.move`: move um arquivo depois da confirmacao.
- A API nativa do Windows envia arquivos para a Lixeira, permitindo recupera-los.
- `input`: permite que voce escolha as acoes durante a execucao.
- `dry-run`: simulacao que apenas exibe o que aconteceria.
