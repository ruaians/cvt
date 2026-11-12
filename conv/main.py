import sys

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from .window import CvtWindow


class CvtApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="cvt.app")

    def do_activate(self):
        janela = self.props.active_window

        if janela is None:
            janela = CvtWindow(self)

        janela.present()


def main():
    return CvtApplication().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())