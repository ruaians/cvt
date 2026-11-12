cvt

Conversor de arquivos leve para Linux. Você arrasta imagens, áudios ou vídeos para a janela, o app detecta o tipo pelo conteúdo e mostra só as conversões possíveis. Escolha o formato, escolha a pasta e pronto.

Tudo roda localmente: nada é enviado para a internet. O app é uma casca fina em Python + GTK4 que chama o ffmpeg e o ImageMagick, sem embutir conversores nem bibliotecas extras.

Feito e testado no Arch Linux com Hyprland (Wayland). Deve funcionar em qualquer distro com as dependências abaixo, mas não foi testado fora do Arch.

Formatos
Tipo	Entrada	Saída	Ferramenta
Imagem	png, jpg, ico, webp, gif	png, jpg, ico, webp	ImageMagick
Áudio	mp3, ogg, wav	mp3, ogg, wav	ffmpeg
Vídeo	mp4, mov, mpeg, webm, mkv	mp4, mov, mpeg, webm, mkv, gif	ffmpeg

Extras:

Vídeo para GIF animado, com FPS ajustável (1 a 30) e limite de 15 segundos.
GIF para ZIP, com um PNG por quadro.
Detecção pelo conteúdo do arquivo, não pela extensão: um JPEG renomeado para .png continua sendo tratado como JPEG.
Lote: vários arquivos de uma vez, desde que sejam da mesma categoria (só imagens, só áudios ou só vídeos). Se um arquivo falha, os outros continuam.
Miniaturas e preview (com animação para GIFs).
Barra de progresso real nas conversões do ffmpeg.

Documentos (PDF, DOCX, ODT...) ficaram de fora de propósito: uma conversão fiel exigiria o LibreOffice, que pesa centenas de MB e vai contra o objetivo do projeto.

Comportamento
Nunca sobrescreve: se o nome já existe, o resultado vira foto (2).jpg.
Escrita segura: grava num arquivo temporário oculto e só move para o nome final quando a conversão termina. Se falhar, não sobra arquivo quebrado.
Só mostra o que dá para fazer: se um programa não está instalado, as conversões que dependem dele não aparecem.
Não oferece converter para o mesmo formato.
PNG com transparência convertido para JPG recebe fundo branco.
ICO é gerado com vários tamanhos (até 256×256).
Dependências

No Arch Linux:

sudo pacman -S --needed ffmpeg imagemagick python-gobject gtk4 file
ffmpeg (inclui o ffprobe) e imagemagick: fazem as conversões.
python-gobject e gtk4: a janela.
file: detecta o tipo do arquivo.

Se o seletor de pasta não abrir, instale também o xdg-desktop-portal-gtk.

Instalação
git clone https://github.com/ruaians/cvt
cd cvt
./install.sh

Sem sudo: o script copia o app para ~/.local/share/cvt, cria o comando cvt-app em ~/.local/bin e instala o cvt.app.desktop para o app aparecer no launcher.

O comando se chama cvt-app porque cvt já é uma ferramenta do X (/usr/bin/cvt, calculadora de modelines de vídeo).

Se o cvt-app não for encontrado, adicione ~/.local/bin ao PATH:

echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

Para remover: ./uninstall.sh.

Uso
Abra com cvt-app ou pelo launcher (procure por "cvt").
Arraste os arquivos para a janela, ou clique para escolher.
Escolha o formato de saída.
Escolha a pasta onde salvar.

Para rodar direto da pasta do projeto, sem instalar:

python -m conv
Hyprland

O application_id do app é cvt.app, e é esse o nome que o Hyprland vê como class da janela. Para abrir flutuante e centralizada:

# sintaxe recente
windowrule = float on, match:class ^(cvt\.app)$
windowrule = center on, match:class ^(cvt\.app)$

# sintaxe antiga
windowrulev2 = float, class:^(cvt\.app)$
windowrulev2 = center, class:^(cvt\.app)$

Use só o par que a sua versão aceita (hyprctl version mostra qual).

Estrutura
cvt/
  conv/
    engine.py    # detecção, tabela de conversões e execução (sem GTK)
    window.py    # janela GTK4
    main.py      # aplicação
    __main__.py  # permite `python -m conv`
  cvt.app.desktop
  install.sh
  uninstall.sh

O motor (engine.py) não depende de GTK, então pode ser reaproveitado numa CLI ou num menu. Cada conversão é uma linha na tabela CONVERSOES: para adicionar um formato basta declarar o comando.

Limitações conhecidas
Vídeo para GIF aceita só um vídeo por vez e até 15 segundos.
GIF para ZIP aceita só um GIF por vez.
Aparece um aviso do GTK no terminal (No property named "overflow") ao abrir. É inofensivo.
Ainda não existe conversão de vídeo para áudio nem opções de qualidade (bitrate, resolução).
Licença

Ainda não definida. Se for publicar, vale adicionar um arquivo LICENSE (MIT é a escolha mais comum para projetos pequenos).