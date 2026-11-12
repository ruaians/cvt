
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

from pathlib import Path
import subprocess
import random
import colorsys
import threading

from . import engine


class CvtWindow(Gtk.ApplicationWindow):
    def rolar_miniaturas(self, controlador, dx, dy):
        ajuste = self.scroll_miniaturas.get_hadjustment()

        ajuste.set_value(
            ajuste.get_value() + dy * 40
        )
        return True

    def __init__(self, app):
        super().__init__(application=app)

        self.set_title("cvt")
        self.set_default_size(480, 620)
        self.set_resizable(False)

        self.arquivo = None
        self.arquivos = []
        self.formatos = []
        self.formato_selecionado = None
        self.botoes_formatos = []
        self.janela_preview = None

        self.preview_animacao = None
        self.preview_grande_animacao = None

        self.cores_audio = {}
        self.provedores_cores_audio = {}
        self.cor_audio_classe_atual = None

        self.convertendo = False
        self.timer_progresso = None

        self.criar_interface()
        self.configurar_drag_drop()
        self.configurar_cliques_preview()
        self.configurar_hover_preview()

    def obter_cor_audio(self, caminho):
        caminho = Path(caminho)

        if caminho not in self.cores_audio:
            matiz = random.random()

            vermelho, verde, azul = colorsys.hsv_to_rgb(
                matiz,
                0.28,
                1.0
            )

            cor = "#{:02X}{:02X}{:02X}".format(
                int(vermelho * 255),
                int(verde * 255),
                int(azul * 255)
            )

            nome_classe = "audio-cor-" + cor.replace("#", "")

            css = Gtk.CssProvider()
            css.load_from_data(
                f".{nome_classe} {{ background-color: {cor}; }}".encode()
            )

            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            self.cores_audio[caminho] = cor

            self.provedores_cores_audio[caminho] = (
                nome_classe,
                css
            )

        return self.provedores_cores_audio[caminho][0]

    def recortar_pixbuf_quadrado(self, pixbuf, tamanho=72):
        largura = pixbuf.get_width()
        altura = pixbuf.get_height()

        lado = min(largura, altura)

        x = (largura - lado) // 2
        y = (altura - lado) // 2

        pixbuf_quadrado = pixbuf.new_subpixbuf(
            x,
            y,
            lado,
            lado
        )

        return pixbuf_quadrado.scale_simple(
            tamanho,
            tamanho,
            GdkPixbuf.InterpType.BILINEAR
        )

    def criar_interface(self):
        self.overlay_principal = Gtk.Overlay()
        self.set_child(self.overlay_principal)

        principal = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12
        )
        principal.set_margin_top(20)
        principal.set_margin_bottom(20)
        principal.set_margin_start(24)
        principal.set_margin_end(24)

        self.overlay_principal.set_child(principal)

        titulo = Gtk.Label(label="cvt")
        titulo.add_css_class("title-1")
        principal.append(titulo)

        descricao = Gtk.Label(
            label="Conversor de arquivos"
        )
        descricao.add_css_class("dim-label")
        principal.append(descricao)

        self.area = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL
        )
        self.area.set_halign(Gtk.Align.FILL)
        self.area.set_hexpand(True)
        self.area.set_size_request(-1, 110)
        self.area.add_css_class("card")
        self.area.set_margin_top(8)

        espaco_superior = Gtk.Box()
        espaco_superior.set_vexpand(True)

        conteudo = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12
        )
        conteudo.set_halign(Gtk.Align.CENTER)

        icone = Gtk.Image.new_from_icon_name(
            "document-open-symbolic"
        )
        icone.set_pixel_size(42)

        texto = Gtk.Label(
            label="Arraste arquivos aqui"
        )
        texto.add_css_class("heading")

        conteudo.append(icone)
        conteudo.append(texto)

        espaco_inferior = Gtk.Box()
        espaco_inferior.set_vexpand(True)

        self.area.append(espaco_superior)
        self.area.append(conteudo)
        self.area.append(espaco_inferior)

        principal.append(self.area)

        self.botao_arquivo = Gtk.Button(
            label="Selecionar arquivo(s)"
        )
        self.botao_arquivo.set_halign(Gtk.Align.CENTER)
        self.botao_arquivo.connect(
            "clicked",
            self.selecionar_arquivo
        )
        principal.append(self.botao_arquivo)

        self.preview = Gtk.Picture()
        self.preview.set_can_shrink(True)
        self.preview.set_size_request(200, 140)
        self.preview.set_halign(Gtk.Align.CENTER)
        self.preview.set_content_fit(
            Gtk.ContentFit.CONTAIN
        )
        self.preview.set_visible(False)

        self.preview_container = Gtk.Overlay()
        self.preview_container.set_size_request(200, 140)
        self.preview_container.set_halign(Gtk.Align.CENTER)
        self.preview_container.set_child(self.preview)
        self.preview_container.set_visible(False)

        principal.append(self.preview_container)

        self.info_arquivo = Gtk.Label(
            label="Nenhum arquivo selecionado"
        )
        self.info_arquivo.set_wrap(True)
        self.info_arquivo.set_ellipsize(3)
        self.info_arquivo.set_halign(Gtk.Align.START)
        self.info_arquivo.set_hexpand(True)

        principal.append(self.info_arquivo)

        self.lista_container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6
        )
        self.lista_container.set_visible(False)

        titulo_lista = Gtk.Label(
            label="Arquivos selecionados"
        )
        titulo_lista.set_halign(Gtk.Align.START)
        titulo_lista.add_css_class("heading")

        self.lista_container.append(titulo_lista)

        self.scroll_miniaturas = Gtk.ScrolledWindow()
        self.scroll_miniaturas.set_policy(
            Gtk.PolicyType.AUTOMATIC,
            Gtk.PolicyType.NEVER
        )
        self.scroll_miniaturas.set_min_content_height(94)
        self.scroll_miniaturas.set_max_content_height(94)
        self.scroll_miniaturas.set_hexpand(True)

        self.faixa_miniaturas = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0
        )

        self.faixa_miniaturas.set_margin_top(4)
        self.faixa_miniaturas.set_margin_bottom(4)

        self.scroll_miniaturas.set_child(
            self.faixa_miniaturas
        )

        movimento_rodinha = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )

        movimento_rodinha.connect(
            "scroll",
            self.rolar_miniaturas
        )

        self.scroll_miniaturas.add_controller(
            movimento_rodinha
        )
        self.lista_container.append(
            self.scroll_miniaturas
        )

        principal.append(self.lista_container)

        separador = Gtk.Separator()
        principal.append(separador)

        formato_titulo = Gtk.Label(
            label="Converter para"
        )
        formato_titulo.set_halign(Gtk.Align.START)
        formato_titulo.add_css_class("heading")
        principal.append(formato_titulo)

        self.seletor_formato = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8
        )
        self.seletor_formato.set_halign(Gtk.Align.CENTER)
        self.seletor_formato.set_sensitive(False)

        principal.append(self.seletor_formato)

        self.controles_gif = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6
        )
        self.controles_gif.set_visible(False)

        self.titulo_fps = Gtk.Label(
            label="Quantidade de frames (FPS)"
        )
        self.titulo_fps.set_halign(Gtk.Align.START)
        self.titulo_fps.add_css_class("heading")

        self.slider_fps = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL,
            1,
            30,
            1
        )
        self.slider_fps.set_digits(0)
        self.slider_fps.set_value(12)
        self.slider_fps.set_draw_value(True)
        self.slider_fps.set_value_pos(Gtk.PositionType.RIGHT)
        self.slider_fps.set_hexpand(True)

        self.controles_gif.append(self.titulo_fps)
        self.controles_gif.append(self.slider_fps)

        principal.append(self.controles_gif)

        self.botao_converter = Gtk.Button(
            label="Converter"
        )
        self.botao_converter.add_css_class(
            "suggested-action"
        )
        self.botao_converter.set_sensitive(False)
        self.botao_converter.connect(
            "clicked",
            self.converter_arquivo
        )
        principal.append(self.botao_converter)

        self.barra_progresso = Gtk.ProgressBar()
        self.barra_progresso.set_show_text(True)
        self.barra_progresso.set_visible(False)
        self.barra_progresso.set_hexpand(True)

        principal.append(self.barra_progresso)

        self.status = Gtk.Label(label="")
        self.status.set_wrap(True)
        self.status.add_css_class("dim-label")
        principal.append(self.status)

        self.criar_overlay_arraste()

    def criar_overlay_arraste(self):
        css = Gtk.CssProvider()

        css.load_from_data(b"""
            .drag-overlay {
                background-color: rgba(0, 0, 0, 0.78);
            }

            .drag-overlay-titulo {
                color: white;
                font-size: 23px;
                font-weight: bold;
            }

            .drag-overlay-descricao {
                color: rgba(255, 255, 255, 0.75);
                font-size: 13px;
            }

            .miniatura-arredondada {
                border-radius: 10px;
            }

            .miniatura-selecionada {
                filter: brightness(0.45);
            }

            .audio-preview-background {
                border-radius: 10px;
            }

            .audio-preview-icon {
                color: #65439A;
            }
        """)

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.drag_css_provider = css

        camada = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12
        )

        camada.add_css_class("drag-overlay")
        camada.set_halign(Gtk.Align.FILL)
        camada.set_valign(Gtk.Align.FILL)
        camada.set_can_target(False)

        titulo = Gtk.Label(
            label="Solte os arquivos para converter"
        )
        titulo.add_css_class("drag-overlay-titulo")

        descricao = Gtk.Label(
            label="Solte aqui seus arquivos e deixe o cvt fazer o resto."
        )
        descricao.add_css_class("drag-overlay-descricao")
        descricao.set_wrap(True)
        descricao.set_justify(Gtk.Justification.CENTER)

        conteudo = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12
        )
        conteudo.set_halign(Gtk.Align.CENTER)
        conteudo.set_valign(Gtk.Align.CENTER)
        conteudo.set_vexpand(True)

        conteudo.append(titulo)
        conteudo.append(descricao)

        camada.append(conteudo)

        self.overlay_arraste = camada
        self.overlay_arraste.set_visible(False)

        self.overlay_principal.add_overlay(
            self.overlay_arraste
        )

    def configurar_hover_preview(self):
        movimento = Gtk.EventControllerMotion()

        movimento.connect(
            "enter",
            self.entrar_preview
        )

        movimento.connect(
            "leave",
            self.sair_preview
        )

        self.preview_container.add_controller(movimento)

    def entrar_preview(self, controlador, x, y):
        if self.arquivo is not None:
            self.preview.set_opacity(0.4)

    def sair_preview(self, controlador):
        self.preview.set_opacity(1.0)

    def configurar_cliques_preview(self):
        clique_esquerdo = Gtk.GestureClick()
        clique_esquerdo.set_button(1)
        clique_esquerdo.connect(
            "pressed",
            self.clique_esquerdo_preview
        )
        self.preview_container.add_controller(clique_esquerdo)

        clique_direito = Gtk.GestureClick()
        clique_direito.set_button(3)
        clique_direito.connect(
            "pressed",
            self.clique_direito_preview
        )
        self.preview_container.add_controller(clique_direito)

    def clique_esquerdo_preview(
        self, gesture, n_press, x, y
    ):
        if self.arquivo is None:
            return

        try:
            tipo, formato = engine.detectar(self.arquivo)

            if tipo == "video":
                subprocess.Popen([
                    "xdg-open",
                    str(self.arquivo)
                ])
                return

            self.abrir_preview()

        except (OSError, RuntimeError) as erro:
            self.status.set_text(
                f"Não foi possível abrir o arquivo: {erro}"
            )

    def clique_direito_preview(
        self, gesture, n_press, x, y
    ):
        if self.arquivo is None:
            return

        if len(self.arquivos) > 1:
            self.remover_arquivo_lista(self.arquivo)
        else:
            self.limpar_arquivo()

    def iniciar_animacao(self, picture, caminho, ampliada=False):
        try:
            animacao = GdkPixbuf.PixbufAnimation.new_from_file(
                str(caminho)
            )

            if animacao.is_static_image():
                picture.set_paintable(
                    Gdk.Texture.new_for_pixbuf(
                        animacao.get_static_image()
                    )
                )
                return None

            iterador = animacao.get_iter(None)

            picture.set_paintable(
                Gdk.Texture.new_for_pixbuf(
                    iterador.get_pixbuf()
                )
            )

            estado = {
                "animacao": animacao,
                "iterador": iterador,
                "timeout": None
            }

            def atualizar():
                if ampliada and self.janela_preview is None:
                    estado["timeout"] = None
                    return GLib.SOURCE_REMOVE

                iterador.advance(None)

                picture.set_paintable(
                    Gdk.Texture.new_for_pixbuf(
                        iterador.get_pixbuf()
                    )
                )

                intervalo = max(
                    iterador.get_delay_time(),
                    20
                )

                estado["timeout"] = GLib.timeout_add(
                    intervalo,
                    atualizar
                )

                return GLib.SOURCE_REMOVE

            intervalo = max(
                iterador.get_delay_time(),
                20
            )

            estado["timeout"] = GLib.timeout_add(
                intervalo,
                atualizar
            )

            return estado

        except GLib.Error:
            picture.set_visible(False)
            return None

    def parar_animacao(self, estado):
        if estado is not None:
            timeout = estado.get("timeout")

            if timeout is not None:
                GLib.source_remove(timeout)
                estado["timeout"] = None

    def abrir_preview(self):
        if self.arquivo is None:
            return

        if self.janela_preview is not None:
            self.janela_preview.present()
            return

        janela = Gtk.Window()
        janela.set_title(self.arquivo.name)
        janela.set_default_size(800, 600)
        janela.set_transient_for(self)
        janela.set_modal(False)

        tipo, formato = engine.detectar(self.arquivo)

        if tipo == "audio":
            fundo_audio = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL
            )
            fundo_audio.add_css_class(
                "audio-preview-background"
            )
            fundo_audio.add_css_class(
                self.obter_cor_audio(self.arquivo)
            )
            fundo_audio.set_hexpand(True)
            fundo_audio.set_vexpand(True)
            fundo_audio.set_halign(Gtk.Align.FILL)
            fundo_audio.set_valign(Gtk.Align.FILL)

            icone_audio = Gtk.Image.new_from_icon_name(
                "audio-x-generic-symbolic"
            )
            icone_audio.set_pixel_size(80)
            icone_audio.add_css_class(
                "audio-preview-icon"
            )
            icone_audio.set_halign(Gtk.Align.CENTER)
            icone_audio.set_valign(Gtk.Align.CENTER)
            icone_audio.set_vexpand(True)

            fundo_audio.append(icone_audio)
            janela.set_child(fundo_audio)

        else:
            imagem = Gtk.Picture()
            imagem.set_can_shrink(True)
            imagem.set_content_fit(
                Gtk.ContentFit.CONTAIN
            )
            imagem.set_hexpand(True)
            imagem.set_vexpand(True)

            janela.set_child(imagem)

            if formato.lower() == "gif":
                self.preview_grande_animacao = self.iniciar_animacao(
                    imagem,
                    self.arquivo,
                    ampliada=True
                )
            else:
                imagem.set_filename(str(self.arquivo))

        self.janela_preview = janela

        janela.connect(
            "close-request",
            self.fechar_preview
        )

        janela.present()

    def fechar_preview(self, janela):
        self.parar_animacao(
            self.preview_grande_animacao
        )
        self.preview_grande_animacao = None
        self.janela_preview = None

        return False

    def configurar_drag_drop(self):
        formatos = Gdk.ContentFormats.new_for_gtype(
            Gdk.FileList.__gtype__
        )

        alvo = Gtk.DropTargetAsync.new(
            formatos,
            Gdk.DragAction.COPY
        )

        alvo.connect(
            "accept",
            self.aceitar_arraste
        )

        alvo.connect(
            "drag-enter",
            self.entrar_arraste
        )

        alvo.connect(
            "drag-motion",
            self.mover_arraste
        )

        alvo.connect(
            "drag-leave",
            self.sair_arraste
        )

        alvo.connect(
            "drop",
            self.arquivo_arrastado
        )

        self.add_controller(alvo)

    def aceitar_arraste(self, alvo, drop):
        formatos = drop.get_formats()

        return formatos.contain_gtype(
            Gdk.FileList.__gtype__
        )

    def entrar_arraste(self, alvo, drop, x, y):
        self.overlay_arraste.set_visible(True)
        return Gdk.DragAction.COPY

    def mover_arraste(self, alvo, drop, x, y):
        return Gdk.DragAction.COPY

    def sair_arraste(self, alvo, drop):
        self.overlay_arraste.set_visible(False)

    def arquivo_arrastado(self, alvo, drop, x, y):
        self.overlay_arraste.set_visible(False)

        drop.read_value_async(
            Gdk.FileList.__gtype__,
            GLib.PRIORITY_DEFAULT,
            None,
            self.receber_arquivo_arrastado
        )

        return True

    def receber_arquivo_arrastado(self, drop, resultado):
        self.overlay_arraste.set_visible(False)

        try:
            arquivos = drop.read_value_finish(resultado)
            lista_arquivos = arquivos.get_files()

            caminhos = [
                arquivo.get_path()
                for arquivo in lista_arquivos
                if arquivo.get_path()
            ]

            if caminhos:
                self.carregar_arquivos(caminhos)
            else:
                self.status.set_text(
                    "Não foi possível acessar esses arquivos."
                )

            drop.finish(Gdk.DragAction.COPY)

        except Exception as erro:
            print("Erro ao receber arquivos arrastados:", erro)

            self.status.set_text(
                "Não foi possível receber esses arquivos."
            )

            drop.finish(0)

    def selecionar_arquivo(self, botao):
        seletor = Gtk.FileChooserNative.new(
            "Selecionar arquivos",
            self,
            Gtk.FileChooserAction.OPEN,
            "Selecionar",
            "Cancelar"
        )

        seletor.set_select_multiple(True)

        seletor.connect(
            "response",
            self.arquivo_selecionado
        )

        seletor.show()

    def arquivo_selecionado(self, seletor, resposta):
        if resposta == Gtk.ResponseType.ACCEPT:
            arquivos = seletor.get_files()

            caminhos = [
                arquivo.get_path()
                for arquivo in arquivos
                if arquivo.get_path()
            ]

            if caminhos:
                self.carregar_arquivos(caminhos)

        seletor.destroy()

    def limpar_botoes_formatos(self):
        while True:
            filho = self.seletor_formato.get_first_child()

            if filho is None:
                break

            self.seletor_formato.remove(filho)

        self.botoes_formatos = []
        self.formato_selecionado = None
        self.controles_gif.set_visible(False)

    def selecionar_formato(self, botao, formato):
        if botao.get_active():
            self.formato_selecionado = formato

            self.controles_gif.set_visible(
                formato == "gif"
            )

    def criar_botoes_formatos(self):
        self.limpar_botoes_formatos()

        primeiro_botao = None

        for formato in self.formatos:
            botao = Gtk.ToggleButton(
                label=formato.upper()
            )

            if primeiro_botao is None:
                primeiro_botao = botao
            else:
                botao.set_group(primeiro_botao)

            botao.connect(
                "toggled",
                self.selecionar_formato,
                formato
            )

            self.seletor_formato.append(botao)
            self.botoes_formatos.append(botao)

        if self.botoes_formatos:
            self.botoes_formatos[0].set_active(True)

        self.seletor_formato.set_sensitive(
            bool(self.botoes_formatos)
        )

    def calcular_formatos(self, caminhos):
        opcoes_por_arquivo = [
            engine.opcoes(caminho)
            for caminho in caminhos
        ]

        formatos_comuns = set(opcoes_por_arquivo[0])

        for opcoes in opcoes_por_arquivo[1:]:
            formatos_comuns.intersection_update(opcoes)

        formatos = [
            formato
            for formato in opcoes_por_arquivo[0]
            if formato in formatos_comuns
        ]

        if len(caminhos) > 1:
            formatos = [
                formato
                for formato in formatos
                if formato not in ("gif", "zip")
            ]

        return formatos

    def carregar_arquivo(self, caminho):
        self.carregar_arquivos([caminho])

    def carregar_arquivos(self, caminhos):
        if self.convertendo:
            return

        novos_caminhos = list(dict.fromkeys(
            Path(caminho) for caminho in caminhos
        ))

        if not novos_caminhos:
            self.status.set_text(
                "Nenhum arquivo foi selecionado."
            )
            return

        caminhos = list(dict.fromkeys(
            self.arquivos + novos_caminhos
        ))

        deteccoes = []

        try:
            for caminho in caminhos:
                if not caminho.exists() or not caminho.is_file():
                    raise RuntimeError(
                        f"Arquivo inválido: {caminho.name}"
                    )

                deteccao = engine.detectar(caminho)

                if deteccao is None:
                    raise RuntimeError(
                        f"Arquivo não compatível: {caminho.name}"
                    )

                deteccoes.append(deteccao)

            tipos = {
                deteccao[0]
                for deteccao in deteccoes
            }

            if len(tipos) != 1:
                raise RuntimeError(
                    "Selecione apenas arquivos da mesma categoria "
                    "(imagens, vídeos ou áudios)."
                )

            formatos = self.calcular_formatos(caminhos)

            if not formatos:
                raise RuntimeError(
                    "Não existe um formato de saída compatível "
                    "com todos os arquivos selecionados."
                )

        except (RuntimeError, OSError) as erro:
            self.status.set_text(str(erro))
            return

        self.parar_animacao(self.preview_animacao)
        self.preview_animacao = None

        if self.janela_preview is not None:
            self.janela_preview.close()
            self.janela_preview = None

        self.arquivos = caminhos
        self.formatos = formatos

        self.arquivo = caminhos[0]

        self.criar_botoes_formatos()
        self.atualizar_lista_miniaturas()
        self.atualizar_preview_atual()

        self.botao_converter.set_sensitive(True)

        self.status.set_text(
            f"{len(caminhos)} arquivos prontos para conversão."
        )

    def atualizar_preview_atual(self):
        if self.arquivo is None:
            return

        tipo, formato = engine.detectar(self.arquivo)

        self.info_arquivo.set_text(
            f"Nome: {self.arquivo.name}\n"
            f"Tipo: {tipo.upper()} · Formato: {formato.upper()}"
        )

        self.carregar_preview(
            self.arquivo,
            tipo,
            formato
        )

    def carregar_preview(self, caminho, tipo, formato):
        self.preview.set_opacity(1.0)
        self.preview.set_paintable(None)
        self.preview.set_visible(False)
        self.preview_container.set_visible(False)

        self.parar_animacao(self.preview_animacao)
        self.preview_animacao = None

        while True:
            filho = self.preview_container.get_last_child()

            if filho is None or filho == self.preview:
                break

            self.preview_container.remove_overlay(filho)

        self.preview_container.remove_css_class(
            "audio-preview-background"
        )

        if self.cor_audio_classe_atual is not None:
            self.preview_container.remove_css_class(
                self.cor_audio_classe_atual
            )
            self.cor_audio_classe_atual = None

        if tipo == "imagem":
            if formato.lower() == "gif":
                self.preview_animacao = self.iniciar_animacao(
                    self.preview,
                    caminho
                )

                self.preview.set_visible(True)
                self.preview_container.set_visible(True)

            else:
                try:
                    imagem = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        str(caminho),
                        200,
                        140,
                        True
                    )

                    textura = Gdk.Texture.new_for_pixbuf(imagem)

                    self.preview.set_paintable(textura)
                    self.preview.set_visible(True)
                    self.preview_container.set_visible(True)

                except GLib.Error:
                    self.preview.set_visible(False)
                    self.preview_container.set_visible(False)

        elif tipo == "video":
            try:
                resultado = subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i", str(caminho),
                        "-frames:v", "1",
                        "-f", "image2pipe",
                        "-vcodec", "png",
                        "-"
                    ],
                    capture_output=True,
                    check=True
                )

                imagem = GdkPixbuf.PixbufLoader.new_with_type(
                    "png"
                )
                imagem.write(resultado.stdout)
                imagem.close()

                pixbuf = imagem.get_pixbuf().scale_simple(
                    200,
                    140,
                    GdkPixbuf.InterpType.BILINEAR
                )

                self.preview.set_paintable(
                    Gdk.Texture.new_for_pixbuf(pixbuf)
                )
                self.preview.set_visible(True)
                self.preview_container.set_visible(True)

            except (GLib.Error, subprocess.CalledProcessError, OSError):
                self.preview.set_visible(False)
                self.preview_container.set_visible(False)

        elif tipo == "audio":
            self.preview_container.add_css_class(
                "audio-preview-background"
            )

            self.cor_audio_classe_atual = (
                self.obter_cor_audio(caminho)
            )

            self.preview_container.add_css_class(
                self.cor_audio_classe_atual
            )

            icone = Gtk.Image.new_from_icon_name(
                "audio-x-generic-symbolic"
            )
            icone.set_pixel_size(64)
            icone.add_css_class("audio-preview-icon")
            icone.set_halign(Gtk.Align.CENTER)
            icone.set_valign(Gtk.Align.CENTER)

            self.preview_container.add_overlay(icone)
            self.preview_container.set_visible(True)

    def criar_miniatura(self, caminho):
        tipo, formato = engine.detectar(caminho)

        if tipo == "imagem":
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(
                    str(caminho)
                )

                pixbuf = self.recortar_pixbuf_quadrado(
                    pixbuf,
                    72
                )

                imagem = Gtk.Picture()
                imagem.set_can_shrink(True)
                imagem.set_size_request(72, 72)
                imagem.set_content_fit(
                    Gtk.ContentFit.FILL
                )
                imagem.set_paintable(
                    Gdk.Texture.new_for_pixbuf(pixbuf)
                )

            except GLib.Error:
                imagem = Gtk.Image.new_from_icon_name(
                    "image-x-generic-symbolic"
                )
                imagem.set_pixel_size(38)
                imagem.set_halign(Gtk.Align.CENTER)
                imagem.set_valign(Gtk.Align.CENTER)

        elif tipo == "video":
            try:
                resultado = subprocess.run(
                    [
                        "ffmpeg",
                        "-loglevel", "error",
                        "-i", str(caminho),
                        "-frames:v", "1",
                        "-f", "image2pipe",
                        "-vcodec", "png",
                        "-"
                    ],
                    capture_output=True,
                    check=True
                )

                loader = GdkPixbuf.PixbufLoader.new_with_type(
                    "png"
                )
                loader.write(resultado.stdout)
                loader.close()

                pixbuf = loader.get_pixbuf()

                pixbuf = self.recortar_pixbuf_quadrado(
                    pixbuf,
                    72
                )

                imagem = Gtk.Picture()
                imagem.set_can_shrink(True)
                imagem.set_size_request(72, 72)
                imagem.set_content_fit(
                    Gtk.ContentFit.FILL
                )
                imagem.set_paintable(
                    Gdk.Texture.new_for_pixbuf(pixbuf)
                )

            except (GLib.Error, subprocess.CalledProcessError, OSError):
                imagem = Gtk.Image.new_from_icon_name(
                    "video-x-generic-symbolic"
                )
                imagem.set_pixel_size(38)
                imagem.set_halign(Gtk.Align.CENTER)
                imagem.set_valign(Gtk.Align.CENTER)

        else:
            imagem = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL
            )
            imagem.set_size_request(72, 72)
            imagem.set_halign(Gtk.Align.FILL)
            imagem.set_valign(Gtk.Align.FILL)
            imagem.add_css_class(
                "audio-preview-background"
            )
            imagem.add_css_class(
                self.obter_cor_audio(caminho)
            )

            icone = Gtk.Image.new_from_icon_name(
                "audio-x-generic-symbolic"
            )
            icone.set_pixel_size(38)
            icone.add_css_class("audio-preview-icon")
            icone.set_halign(Gtk.Align.CENTER)
            icone.set_valign(Gtk.Align.CENTER)
            icone.set_vexpand(True)

            imagem.append(icone)

        quadro = Gtk.Overlay()
        quadro.set_size_request(72, 72)
        quadro.set_overflow(Gtk.Overflow.HIDDEN)
        quadro.set_halign(Gtk.Align.CENTER)
        quadro.set_valign(Gtk.Align.CENTER)
        quadro.add_css_class("miniatura-arredondada")
        quadro.set_child(imagem)

        botao_selecionar = Gtk.Button()
        botao_selecionar.set_child(quadro)
        botao_selecionar.set_size_request(72, 72)
        botao_selecionar.set_hexpand(False)
        botao_selecionar.set_vexpand(False)
        botao_selecionar.set_halign(Gtk.Align.CENTER)
        botao_selecionar.add_css_class("flat")
        botao_selecionar.set_tooltip_text(
            f"Visualizar {caminho.name}"
        )

        botao_selecionar.connect(
            "clicked",
            lambda botao, arquivo=caminho:
                self.selecionar_miniatura(arquivo)
        )

        clique_direito = Gtk.GestureClick()
        clique_direito.set_button(3)
        clique_direito.connect(
            "pressed",
            lambda gesture, n_press, x, y, arquivo=caminho:
                self.remover_arquivo_lista(arquivo)
        )
        botao_selecionar.add_controller(clique_direito)

        item = Gtk.Overlay()
        item.set_size_request(72, 72)
        item.set_hexpand(False)
        item.set_vexpand(False)
        item.set_halign(Gtk.Align.START)
        item.set_child(botao_selecionar)

        botao_remover = Gtk.Button()
        botao_remover.set_child(
            Gtk.Image.new_from_icon_name(
                "window-close-symbolic"
            )
        )
        botao_remover.set_size_request(22, 22)
        botao_remover.add_css_class("circular")
        botao_remover.add_css_class("flat")
        botao_remover.set_tooltip_text(
            "Remover da seleção"
        )

        botao_remover.set_halign(Gtk.Align.END)
        botao_remover.set_valign(Gtk.Align.START)
        botao_remover.set_margin_top(1)
        botao_remover.set_margin_end(1)

        botao_remover.connect(
            "clicked",
            lambda botao, arquivo=caminho:
                self.remover_arquivo_lista(arquivo)
        )

        item.add_overlay(botao_remover)

        if caminho == self.arquivo:
            botao_selecionar.add_css_class(
                "suggested-action"
            )
            imagem.add_css_class(
                "miniatura-selecionada"
            )

        return item

    def atualizar_lista_miniaturas(self):
        while True:
            filho = self.faixa_miniaturas.get_first_child()

            if filho is None:
                break

            self.faixa_miniaturas.remove(filho)

        mostrar = len(self.arquivos) > 1
        self.lista_container.set_visible(mostrar)

        if not mostrar:
            return

        for caminho in self.arquivos:
            try:
                miniatura = self.criar_miniatura(caminho)
                self.faixa_miniaturas.append(miniatura)

            except (RuntimeError, OSError) as erro:
                print(
                    f"Não foi possível criar miniatura de "
                    f"{caminho.name}: {erro}"
                )

    def selecionar_miniatura(self, caminho):
        if self.convertendo:
            return

        if caminho not in self.arquivos:
            return

        if caminho == self.arquivo:
            return

        self.parar_animacao(self.preview_animacao)
        self.preview_animacao = None

        if self.janela_preview is not None:
            self.janela_preview.close()
            self.janela_preview = None

        self.arquivo = caminho

        self.atualizar_preview_atual()
        self.atualizar_lista_miniaturas()

        self.status.set_text(
            f"Visualizando: {caminho.name}"
        )

    def remover_arquivo_lista(self, caminho):
        if self.convertendo:
            return

        if caminho not in self.arquivos:
            return

        indice = self.arquivos.index(caminho)
        era_atual = caminho == self.arquivo

        self.arquivos.remove(caminho)

        if not self.arquivos:
            self.limpar_arquivo()
            return

        self.formatos = self.calcular_formatos(
            self.arquivos
        )

        self.criar_botoes_formatos()

        if era_atual:
            novo_indice = min(
                indice,
                len(self.arquivos) - 1
            )

            self.parar_animacao(self.preview_animacao)
            self.preview_animacao = None

            if self.janela_preview is not None:
                self.janela_preview.close()
                self.janela_preview = None

            self.arquivo = self.arquivos[novo_indice]
            self.atualizar_preview_atual()

        self.atualizar_lista_miniaturas()

        self.botao_converter.set_sensitive(
            bool(self.formatos)
        )

        self.status.set_text(
            f"{len(self.arquivos)} arquivo(s) na seleção."
        )

    def limpar_arquivo(self):
        if self.convertendo:
            return

        self.preview.set_opacity(1.0)

        if self.janela_preview is not None:
            self.janela_preview.close()
            self.janela_preview = None

        self.parar_animacao(self.preview_animacao)
        self.preview_animacao = None

        self.arquivo = None
        self.arquivos = []
        self.formatos = []

        self.info_arquivo.set_text(
            "Nenhum arquivo selecionado"
        )

        self.preview.set_paintable(None)
        self.preview.set_visible(False)
        self.preview_container.set_visible(False)
        self.preview_container.remove_css_class(
            "audio-preview-background"
        )

        if self.cor_audio_classe_atual is not None:
            self.preview_container.remove_css_class(
                self.cor_audio_classe_atual
            )
            self.cor_audio_classe_atual = None

        while True:
            filho = self.preview_container.get_last_child()

            if filho is None or filho == self.preview:
                break

            self.preview_container.remove_overlay(filho)

        self.lista_container.set_visible(False)

        while True:
            filho = self.faixa_miniaturas.get_first_child()

            if filho is None:
                break

            self.faixa_miniaturas.remove(filho)

        self.limpar_botoes_formatos()
        self.seletor_formato.set_sensitive(False)

        self.botao_converter.set_sensitive(False)

        self.status.set_text("")

    def converter_arquivo(self, botao):
        if self.convertendo:
            return

        if not self.arquivos or not self.formato_selecionado:
            return

        seletor = Gtk.FileChooserNative.new(
            "Escolher onde salvar os arquivos",
            self,
            Gtk.FileChooserAction.SELECT_FOLDER,
            "Salvar aqui",
            "Cancelar"
        )

        seletor.connect(
            "response",
            self.pasta_destino_selecionada
        )

        seletor.show()

    def pasta_destino_selecionada(self, seletor, resposta):
        if resposta == Gtk.ResponseType.ACCEPT:
            pasta = seletor.get_file()
            caminho = pasta.get_path()

            if caminho:
                self.executar_conversao(caminho)

        seletor.destroy()

    def executar_conversao(self, pasta_destino):
        if not self.arquivos or not self.formato_selecionado:
            return

        if self.convertendo:
            return

        formato = self.formato_selecionado
        arquivos = list(self.arquivos)
        quantidade = len(arquivos)
        fps = int(self.slider_fps.get_value())

        self.convertendo = True

        self.botao_converter.set_sensitive(False)
        self.botao_arquivo.set_sensitive(False)
        self.seletor_formato.set_sensitive(False)
        self.slider_fps.set_sensitive(False)

        self.barra_progresso.set_fraction(0)
        self.barra_progresso.set_text("Preparando...")
        self.barra_progresso.set_visible(True)

        self.status.set_text(
            f"Convertendo {quantidade} arquivo(s)..."
        )

        thread = threading.Thread(
            target=self.processar_conversao,
            args=(arquivos, formato, pasta_destino, fps),
            daemon=True
        )

        thread.start()

    def processar_conversao(
        self,
        arquivos,
        formato,
        pasta_destino,
        fps
    ):
        try:
            resultados = engine.converter_varios(
                arquivos,
                formato,
                pasta_destino=pasta_destino,
                fps=fps,
                progresso=self.receber_progresso
            )

            GLib.idle_add(
                self.finalizar_conversao,
                resultados,
                None
            )

        except Exception as erro:
            GLib.idle_add(
                self.finalizar_conversao,
                None,
                str(erro)
            )

    def receber_progresso(
        self,
        valor,
        indice,
        total,
        caminho
    ):
        GLib.idle_add(
            self.atualizar_progresso,
            valor,
            indice,
            total,
            caminho
        )

    def atualizar_progresso(
        self,
        valor,
        indice,
        total,
        caminho
    ):
        if not self.convertendo:
            return GLib.SOURCE_REMOVE

        if valor is None:
            if self.timer_progresso is None:
                self.timer_progresso = GLib.timeout_add(
                    100,
                    self.pulsar_barra
                )

            self.barra_progresso.set_text(
                f"Processando {caminho.name}..."
            )

        else:
            if self.timer_progresso is not None:
                GLib.source_remove(self.timer_progresso)
                self.timer_progresso = None

            progresso_total = (indice + valor) / total

            self.barra_progresso.set_fraction(
                min(progresso_total, 1.0)
            )

            porcentagem = int(progresso_total * 100)

            self.barra_progresso.set_text(
                f"{porcentagem}% · {caminho.name}"
            )

        return GLib.SOURCE_REMOVE

    def pulsar_barra(self):
        if not self.convertendo:
            self.timer_progresso = None
            return GLib.SOURCE_REMOVE

        self.barra_progresso.pulse()
        return GLib.SOURCE_CONTINUE

    def finalizar_conversao(self, resultados, erro):
        self.convertendo = False

        if self.timer_progresso is not None:
            GLib.source_remove(self.timer_progresso)
            self.timer_progresso = None

        self.botao_converter.set_sensitive(
            bool(self.arquivos and self.formato_selecionado)
        )

        self.botao_arquivo.set_sensitive(True)
        self.seletor_formato.set_sensitive(
            bool(self.botoes_formatos)
        )
        self.slider_fps.set_sensitive(True)

        self.barra_progresso.set_visible(False)
        self.barra_progresso.set_fraction(0)

        if erro is not None:
            self.status.set_text(f"Erro: {erro}")
            return GLib.SOURCE_REMOVE

        sucessos = [
            resultado
            for entrada, resultado, falha in resultados
            if resultado is not None
        ]

        falhas = [
            (entrada, falha)
            for entrada, resultado, falha in resultados
            if falha is not None
        ]

        quantidade = len(resultados)

        if not falhas:
            self.status.set_text(
                f"Conversão concluída!\n"
                f"{len(sucessos)} arquivo(s) convertido(s)."
            )

        else:
            mensagem = (
                f"Concluído: {len(sucessos)} de "
                f"{quantidade} arquivo(s).\n"
            )

            for entrada, falha in falhas:
                mensagem += (
                    f"\n{entrada.name}: {falha}"
                )

            self.status.set_text(mensagem)

        return GLib.SOURCE_REMOVE
