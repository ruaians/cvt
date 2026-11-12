
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


DURACAO_MAXIMA_GIF = 15
FPS_PADRAO_GIF = 12
FPS_MINIMO_GIF = 1
FPS_MAXIMO_GIF = 30


MIMES = {
    "image/png": ("imagem", "png"),
    "image/jpeg": ("imagem", "jpg"),
    "image/vnd.microsoft.icon": ("imagem", "ico"),
    "image/x-icon": ("imagem", "ico"),
    "image/webp": ("imagem", "webp"),
    "image/gif": ("imagem", "gif"),
    "audio/mpeg": ("audio", "mp3"),
    "audio/ogg": ("audio", "ogg"),
    "application/ogg": ("audio", "ogg"),
    "audio/wav": ("audio", "wav"),
    "audio/x-wav": ("audio", "wav"),
    "audio/vnd.wave": ("audio", "wav"),
    "video/mp4": ("video", "mp4"),
    "video/quicktime": ("video", "mov"),
    "video/mpeg": ("video", "mpeg"),
    "video/webm": ("video", "webm"),
    "video/x-matroska": ("video", "mkv"),
    "application/x-matroska": ("video", "mkv"),
}


FF = [
    "ffmpeg", "-nostdin", "-loglevel", "error",
    "-progress", "pipe:1", "-nostats",
    "-y", "-i", "{entrada}"
]


VIDEO_AAC = [
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac"
]


CONVERSOES = {
    "imagem": {
        "png": ["magick", "{entrada}[0]", "{saida}"],
        "jpg": [
            "magick", "{entrada}[0]",
            "-background", "white", "-flatten", "{saida}"
        ],
        "ico": [
            "magick", "{entrada}[0]",
            "-resize", "256x256>",
            "-define", "icon:auto-resize=256,128,64,48,32,16",
            "{saida}"
        ],
        "webp": ["magick", "{entrada}[0]", "{saida}"],
    },
    "audio": {
        "mp3": FF + [
            "-vn", "-c:a", "libmp3lame", "-q:a", "2", "{saida}"
        ],
        "ogg": FF + [
            "-vn", "-c:a", "libvorbis", "-q:a", "5", "{saida}"
        ],
        "wav": FF + [
            "-vn", "-c:a", "pcm_s16le", "{saida}"
        ],
    },
    "video": {
        "mp4": FF + VIDEO_AAC + ["{saida}"],
        "mov": FF + VIDEO_AAC + ["{saida}"],
        "webm": FF + [
            "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "32",
            "-c:a", "libopus", "{saida}"
        ],
        "mpeg": FF + [
            "-c:v", "mpeg2video", "-q:v", "4",
            "-c:a", "mp2", "{saida}"
        ],
        "mkv": FF + VIDEO_AAC + ["{saida}"],
        "gif": FF + [
            "-filter_complex",
            "[0:v:0]fps={fps},split[base][pal];"
            "[pal]palettegen[palette];"
            "[base][palette]paletteuse[out]",
            "-map", "[out]",
            "-loop", "0",
            "-an",
            "{saida}"
        ],
                "mp3": FF + [
            "-vn", "-c:a", "libmp3lame", "-q:a", "2", "{saida}"
        ],
        "ogg": FF + [
            "-vn", "-c:a", "libvorbis", "-q:a", "5", "{saida}"
        ],
        "wav": FF + [
            "-vn", "-c:a", "pcm_s16le", "{saida}"
        ],
    },
}


def _notificar(progresso, valor):
    if progresso is not None:
        progresso(valor)


def detectar(caminho):
    """Identifica o tipo e formato pelo conteúdo do arquivo."""
    try:
        r = subprocess.run(
            ["file", "--mime-type", "-b", str(caminho)],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "O programa 'file' não está instalado"
        ) from None
    except subprocess.CalledProcessError:
        raise RuntimeError(
            "Não foi possível identificar o arquivo"
        ) from None

    return MIMES.get(r.stdout.strip())


def opcoes(caminho):
    """Retorna os formatos de saída disponíveis."""
    det = detectar(caminho)

    if det is None:
        return []

    tipo, formato = det

    saidas = [
        saida
        for saida, cmd in CONVERSOES[tipo].items()
        if saida != formato and shutil.which(cmd[0])
    ]

    if tipo == "imagem" and formato == "gif" and shutil.which("magick"):
        saidas.append("zip")

    return saidas


def _obter_duracao(caminho):
    """Obtém a duração de um arquivo de áudio ou vídeo."""
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(caminho)
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        duracao = float(r.stdout.strip())

        if duracao > 0:
            return duracao

    except (OSError, subprocess.SubprocessError, ValueError):
        pass

    return None


def _verificar_duracao_video(caminho):
    """Verifica se o vídeo respeita o limite de duração para GIF."""
    if not shutil.which("ffprobe"):
        raise RuntimeError(
            "O programa 'ffprobe' não está instalado"
        )

    duracao = _obter_duracao(caminho)

    if duracao is None:
        raise RuntimeError(
            "Não foi possível verificar a duração do vídeo"
        )

    if duracao > DURACAO_MAXIMA_GIF:
        raise RuntimeError(
            f"O vídeo tem {duracao:.1f} segundos. "
            f"O limite para GIF é de {DURACAO_MAXIMA_GIF} segundos."
        )


def _nome_livre(pasta, nome, ext):
    """Gera um nome que não sobrescreve arquivos existentes."""
    alvo = pasta / f"{nome}.{ext}"
    n = 2

    while alvo.exists():
        alvo = pasta / f"{nome} ({n}).{ext}"
        n += 1

    return alvo


def _extrair_frames_gif(caminho, pasta, progresso=None):
    """Extrai os frames de um GIF para um ZIP."""
    _notificar(progresso, None)

    final = _nome_livre(
        pasta,
        f"{caminho.stem}_frames",
        "zip"
    )

    with tempfile.TemporaryDirectory(
        prefix=".cvt-frames-",
        dir=pasta
    ) as temp_dir:

        temp_dir = Path(temp_dir)
        padrao = temp_dir / "%d.png"

        r = subprocess.run(
            [
                "magick",
                str(caminho),
                "-coalesce",
                str(padrao)
            ],
            capture_output=True,
            text=True,
        )

        if r.returncode != 0:
            raise RuntimeError(
                r.stderr.strip() or "Falha ao extrair os frames"
            )

        frames = sorted(
            temp_dir.glob("*.png"),
            key=lambda arquivo: int(arquivo.stem)
        )

        if not frames:
            raise RuntimeError("Nenhum frame foi encontrado no GIF")

        fd, temp_zip = tempfile.mkstemp(
            prefix=f".{final.stem}.",
            suffix=".zip",
            dir=pasta,
        )

        os.close(fd)

        try:
            with zipfile.ZipFile(
                temp_zip,
                "w",
                zipfile.ZIP_DEFLATED
            ) as arquivo_zip:

                for frame in frames:
                    arquivo_zip.write(
                        frame,
                        arcname=frame.name
                    )

            os.replace(temp_zip, final)

        finally:
            Path(temp_zip).unlink(missing_ok=True)

    _notificar(progresso, 1.0)
    return final


def _executar_ffmpeg(cmd, duracao, progresso=None):
    """Executa o FFmpeg acompanhando o progresso real."""
    processo = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    try:
        for linha in processo.stdout:
            linha = linha.strip()

            if "=" not in linha:
                continue

            chave, valor = linha.split("=", 1)

            if chave == "out_time_us" and duracao:
                try:
                    segundos = int(valor) / 1_000_000
                    percentual = min(
                        segundos / duracao,
                        1.0
                    )
                    _notificar(progresso, percentual)
                except ValueError:
                    pass

            elif chave == "progress" and valor == "end":
                _notificar(progresso, 1.0)

        erro = processo.stderr.read()
        retorno = processo.wait()

        if retorno != 0:
            raise RuntimeError(
                erro.strip() or "A conversão falhou"
            )

    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait()

        if processo.stdout:
            processo.stdout.close()

        if processo.stderr:
            processo.stderr.close()


def converter(
    caminho,
    formato_saida,
    pasta_destino=None,
    fps=FPS_PADRAO_GIF,
    progresso=None
):
    """Converte um arquivo e devolve o caminho do resultado."""
    caminho = Path(caminho)

    if not caminho.exists():
        raise RuntimeError("O arquivo selecionado não existe")

    if not caminho.is_file():
        raise RuntimeError("O caminho selecionado não é um arquivo")

    if not os.access(caminho, os.R_OK):
        raise RuntimeError("Sem permissão para ler o arquivo")

    det = detectar(caminho)

    if det is None:
        raise RuntimeError("Tipo de arquivo não suportado")

    tipo, formato = det

    if formato_saida not in opcoes(caminho):
        raise RuntimeError(
            f"Não dá para converter {formato} para {formato_saida}"
        )

    if formato_saida == "gif":
        if tipo != "video":
            raise RuntimeError(
                "A conversão para GIF só está disponível para vídeos"
            )

        if not isinstance(fps, int) or not FPS_MINIMO_GIF <= fps <= FPS_MAXIMO_GIF:
            raise RuntimeError(
                f"O FPS deve ser um número inteiro entre "
                f"{FPS_MINIMO_GIF} e {FPS_MAXIMO_GIF}"
            )

        _verificar_duracao_video(caminho)

    pasta = Path(pasta_destino) if pasta_destino else caminho.parent

    if not pasta.exists():
        raise RuntimeError("A pasta de destino não existe")

    if not pasta.is_dir():
        raise RuntimeError("O destino não é uma pasta")

    if not os.access(pasta, os.W_OK):
        raise RuntimeError("Sem permissão para escrever na pasta")

    if formato_saida == "zip":
        return _extrair_frames_gif(
            caminho,
            pasta,
            progresso
        )

    final = _nome_livre(pasta, caminho.stem, formato_saida)

    fd, temp_nome = tempfile.mkstemp(
        prefix=f".{final.stem}.",
        suffix=f".{formato_saida}",
        dir=pasta,
    )

    os.close(fd)

    temp = Path(temp_nome)
    temp.unlink()

    cmd = [
        c.format(
            entrada=str(caminho),
            saida=str(temp),
            fps=fps
        )
        for c in CONVERSOES[tipo][formato_saida]
    ]

    try:
        if cmd[0] == "ffmpeg":
            duracao = _obter_duracao(caminho)
            _executar_ffmpeg(
                cmd,
                duracao,
                progresso
            )
        else:
            _notificar(progresso, None)

            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            if r.returncode != 0:
                raise RuntimeError(
                    r.stderr.strip() or "A conversão falhou"
                )

        if not temp.exists():
            raise RuntimeError("O arquivo convertido não foi criado")

        os.replace(temp, final)
        _notificar(progresso, 1.0)

    finally:
        temp.unlink(missing_ok=True)

    return final


def converter_varios(
    caminhos,
    formato_saida,
    pasta_destino=None,
    fps=FPS_PADRAO_GIF,
    progresso=None
):
    """Converte vários arquivos e informa o progresso de cada um."""
    caminhos = [Path(caminho) for caminho in caminhos]

    if not caminhos:
        raise RuntimeError("Nenhum arquivo foi selecionado")

    total = len(caminhos)
    resultados = []

    if total > 1:
        deteccoes = []

        for caminho in caminhos:
            if not caminho.exists() or not caminho.is_file():
                raise RuntimeError(
                    f"Arquivo inválido: {caminho.name}"
                )

            deteccao = detectar(caminho)

            if deteccao is None:
                raise RuntimeError(
                    f"Arquivo não compatível: {caminho.name}"
                )

            deteccoes.append(deteccao)

        tipos = {deteccao[0] for deteccao in deteccoes}

        if len(tipos) != 1:
            raise RuntimeError(
                "Selecione arquivos da mesma categoria: imagens, vídeos ou áudios."
            )

        tipo = deteccoes[0][0]

        if tipo == "video" and formato_saida == "gif":
            raise RuntimeError(
                "A conversão de vários vídeos para GIF não está disponível."
            )

        if tipo == "imagem" and formato_saida == "zip":
            raise RuntimeError(
                "A conversão de vários GIFs para ZIP não está disponível."
            )

        formatos_comuns = None

        for caminho in caminhos:
            disponiveis = set(opcoes(caminho))

            if formatos_comuns is None:
                formatos_comuns = disponiveis
            else:
                formatos_comuns.intersection_update(disponiveis)

        if formato_saida not in (formatos_comuns or set()):
            raise RuntimeError(
                f"O formato {formato_saida.upper()} não é compatível "
                "com todos os arquivos selecionados."
            )

    for indice, caminho in enumerate(caminhos):
        def atualizar(valor, indice=indice, caminho=caminho):
            if progresso is not None:
                progresso(
                    valor,
                    indice,
                    total,
                    caminho
                )

        try:
            resultado = converter(
                caminho,
                formato_saida,
                pasta_destino,
                fps,
                progresso=atualizar
            )

            resultados.append((caminho, resultado, None))

        except (RuntimeError, OSError) as erro:
            resultados.append((caminho, None, str(erro)))

            if progresso is not None:
                progresso(
                    1.0,
                    indice,
                    total,
                    caminho
                )

    return resultados


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python engine.py <arquivo> [formato_saida] [fps]")
        sys.exit(1)

    arq = sys.argv[1]

    try:
        if len(sys.argv) == 2:
            print(detectar(arq), "->", opcoes(arq))
        else:
            formato = sys.argv[2]
            fps = int(sys.argv[3]) if len(sys.argv) > 3 else FPS_PADRAO_GIF

            print("criado:", converter(arq, formato, fps=fps))

    except (RuntimeError, ValueError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        sys.exit(1)
