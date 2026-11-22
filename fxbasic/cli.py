# SPDX-FileCopyrightText: 2026 NeftaliGC
# SPDX-License-Identifier: GPL-3.0-or-later
"""
fxbasic - Pasa programas Casio BASIC entre la PC y una fx-9750GII / fx-9860G por USB.

Uso:
    fxbasic send PROGRAMA.txt [opciones]   enviar un programa a la calculadora
    fxbasic get [--check] [-v]             descargar la memoria principal a ./dump/
    fxbasic --version                      mostrar la version y la licencia

Ayuda de cada subcomando:  fxbasic send --help  /  fxbasic get --help
"""
import sys

from . import __version__

SUBCOMANDOS = ("send", "get")

AVISO = f"""fxbasic {__version__}  Copyright (C) 2026  NeftaliGC
Este programa se distribuye SIN NINGUNA GARANTIA. Es software libre y puedes
redistribuirlo bajo los terminos de la GPL-3.0 o posterior (ver LICENSE)."""


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        sys.exit(__doc__)
    if sys.argv[1] == "--version":
        print(AVISO)
        return
    sub = sys.argv[1]
    if sub not in SUBCOMANDOS:
        sys.exit(f"Subcomando desconocido '{sub}'. Usa: {', '.join(SUBCOMANDOS)}.\n{__doc__}")

    # Los subcomandos leen sys.argv al importarse (p. ej. -v en proto.py), asi
    # que se quita el subcomando antes de importarlos.
    sys.argv = [f"fxbasic {sub}"] + sys.argv[2:]
    if sub == "send":
        from . import send as modulo
    else:
        from . import get as modulo
    if "-h" in sys.argv or "--help" in sys.argv:
        print(modulo.__doc__.strip())  # sin tocar el USB
        return
    modulo.main()


if __name__ == "__main__":
    main()
