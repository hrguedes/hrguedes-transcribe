# Build do executável no Windows

Passo a passo para gerar o `Transcribe.exe` em uma máquina Windows 10 ou 11 (64 bits).
Todos os comandos são para o **PowerShell**, rodados na pasta do projeto.

O resultado é uma pasta `dist\Transcribe\` com o `Transcribe.exe` e as bibliotecas dele.
Para levar a outro computador, basta copiar ou zipar essa pasta inteira. Quem for usar não precisa ter Python instalado.

---

## 1. Pré-requisitos (uma vez só)

### 1.1 uv (gerenciador de Python do projeto)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Feche e abra o PowerShell de novo e confira:

```powershell
uv --version
```

Não é preciso instalar Python: o `uv` baixa sozinho o Python 3.12 que o projeto usa (definido em `.python-version`).

### 1.2 Microsoft Visual C++ Redistributable

O motor de transcrição (`ctranslate2` e `onnxruntime`) depende dele. A maioria dos Windows já tem; se não tiver:

```powershell
winget install Microsoft.VCRedist.2015+.x64
```

### 1.3 Git (opcional)

Só se for clonar o projeto em vez de copiar a pasta:

```powershell
winget install Git.Git
```

---

## 2. Trazer o projeto para o Windows

Copie a pasta do projeto (pendrive, nuvem, `git clone`, etc.). **Não copie** as pastas `.venv`, `.tmp`, `build` e `dist`:
elas são do Mac e serão recriadas.

Confira se estes arquivos vieram junto:

- `pyproject.toml`, `uv.lock`, `.python-version`
- `run.py` e `transcribe.spec`
- `app\` (código) e `imgs\creator.jpeg` (foto da tela de apresentação)

---

## 3. Instalar as dependências

```powershell
cd C:\caminho\para\hrguedes-transcribe
uv sync
```

Isso cria o `.venv` com o Python 3.12 e instala PySide6, faster-whisper, sounddevice e numpy nas versões do `uv.lock`.

---

## 4. Testar antes de buildar

```powershell
uv run pytest -q
uv run python -m app.main
```

No app: grave alguns segundos, pare e veja se a transcrição aparece.
Se o Windows perguntar sobre acesso ao microfone, permita (veja a seção 8 se o áudio vier mudo).

---

## 5. Gerar o executável

```powershell
uv run --with pyinstaller pyinstaller transcribe.spec --noconfirm
```

O `--with pyinstaller` usa o PyInstaller só durante esse comando, sem adicioná-lo ao projeto.
Leva alguns minutos. No final:

```
dist\Transcribe\Transcribe.exe
```

Teste:

```powershell
.\dist\Transcribe\Transcribe.exe
```

---

## 6. Distribuir

Zipe a pasta inteira (o `.exe` sozinho não funciona, ele precisa das bibliotecas ao lado):

```powershell
Compress-Archive -Path dist\Transcribe -DestinationPath dist\Transcribe-windows.zip -Force
```

Quem receber descompacta em qualquer lugar (por exemplo `C:\Programas\Transcribe`) e abre o `Transcribe.exe`.
Dá para criar um atalho na Área de Trabalho com botão direito › *Enviar para* › *Área de trabalho*.

---

## 7. Modelo de transcrição

O modelo **não vai dentro do executável** (são de 0,5 a 3 GB). Há duas opções:

**A. Baixar pelo app (precisa de internet uma vez).** Abra *Configurações*, escolha o modelo e clique em *Baixar*.
Recomendado: **Large v3 Turbo** (melhor qualidade) ou **Small** (mais rápido em PCs modestos).

**B. Copiar do Mac (100% offline).** Copie a pasta do modelo de:

```
~/Library/Application Support/Transcribe/models/faster-whisper-small
```

para:

```
%APPDATA%\Transcribe\models\faster-whisper-small
```

(No Windows, digite `%APPDATA%\Transcribe` na barra do Explorador de Arquivos.)
Depois selecione o modelo em *Configurações*.

Os dados do app no Windows ficam em `%APPDATA%\Transcribe\`:

| Pasta/arquivo | Conteúdo |
|---|---|
| `sessions\` | Gravações, transcrições e metadados |
| `models\` | Modelos baixados |
| `settings.json` | Modelo escolhido e vocabulário |
| `app.log` | Log do executável (útil para investigar erros) |

---

## 8. Áudio no Windows

**Microfone:** funciona direto. Se a gravação vier muda, libere em
*Configurações › Privacidade e segurança › Microfone* › ative **Permitir que aplicativos da área de trabalho acessem o microfone**.

**Áudio da reunião (o que sai no alto-falante):** o equivalente ao BlackHole no Windows é a **Mixagem estéreo**:

1. Abra *Painel de Controle › Som* (ou rode `mmsys.cpl`) › aba **Gravação**.
2. Clique com o botão direito na lista › marque **Mostrar dispositivos desabilitados**.
3. Botão direito em **Mixagem estéreo** (ou *Stereo Mix*) › **Ativar**.
4. No app, clique em **Atualizar**: ela aparece selecionada sozinha em "Áudio do sistema".

Nem todo computador tem Mixagem estéreo (depende do driver de som). Se não tiver, instale o
[VB-Audio Virtual Cable](https://vb-audio.com/Cable/) (gratuito):

1. Defina **CABLE Input** como saída do Teams/Zoom/Meet (ou como saída padrão do Windows).
2. Para continuar ouvindo: em *Painel de Controle › Som › Gravação*, abra **CABLE Output** › aba **Escutar** ›
   marque *Escutar este dispositivo* e escolha seus fones/alto-falantes.
3. No app, o **CABLE Output** é detectado como "Áudio do sistema".

---

## 9. Problemas comuns

| Sintoma | Solução |
|---|---|
| "O Windows protegeu o computador" (SmartScreen) | O executável não é assinado. Clique em *Mais informações › Executar assim mesmo*. |
| Antivírus bloqueia ou apaga o `.exe` | Falso positivo comum em apps do PyInstaller. Adicione uma exceção para a pasta `Transcribe`. |
| Erro de DLL ao abrir (`VCRUNTIME140.dll`, `MSVCP140.dll`) | Instale o Visual C++ Redistributable (seção 1.2). |
| App abre e fecha sem mensagem | Veja `%APPDATA%\Transcribe\app.log`. Para ver o erro no terminal, rode `uv run python -m app.main`. |
| "O modelo ... ainda não foi baixado" | Baixe em *Configurações* ou copie do Mac (seção 7). |
| Transcrição muito lenta | Use o modelo **Small** em *Configurações*. |
| `uv sync` falha baixando pacotes | Rede corporativa/proxy: tente de outra rede ou configure `HTTPS_PROXY`. |

---

## 10. Ainda não implementado no Windows

- **Captura direta do áudio do sistema** (loopback WASAPI com `pyaudiowpatch`), sem precisar de Mixagem estéreo ou VB-Cable.
- **GPU NVIDIA (CUDA):** hoje a transcrição roda só no processador (`int8`).
- **Instalador** (Inno Setup) com atalho no menu Iniciar e desinstalador. Por enquanto a distribuição é a pasta zipada.
