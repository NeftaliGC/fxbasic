# SPDX-FileCopyrightText: 2026 NeftaliGC
# SPDX-License-Identifier: GPL-3.0-or-later
"""
casio-send - Envia un programa Casio BASIC (texto) a la memoria principal
de una fx-9750GII / fx-9860G por USB (Protocol 7.00).

Uso:
    casio-send programas/PRUEBA.txt --seco      # solo convertir y mostrar, sin USB
    casio-send programas/PRUEBA.txt -v          # enviar (y verificar)
    casio-send VEC.txt --nombre VEC2 --forzar   # otro nombre, sobrescribir sin preguntar

Opciones:
    --nombre N        nombre en la calculadora (A-Z, 0-9, max 8). Por defecto: nombre del archivo.
    --forzar          si ya existe un programa con ese nombre, sobrescribirlo sin preguntar.
    --seco            no usar USB: solo tokenizar y mostrar el resultado.
    --sin-verificar   no volver a descargar el programa para compararlo.
    -v                mostrar cada paquete.

La calculadora debe estar conectada DIRECTO (sin hub) y en DataTrans (F1).
"""
import os
import re
import sys

from .tokens import Tabla, empaquetar_programa

ARGS = sys.argv[1:]


def opcion(nombre, con_valor=False):
    if nombre not in ARGS:
        return None
    i = ARGS.index(nombre)
    if con_valor:
        if i + 1 >= len(ARGS):
            sys.exit(f"Falta el valor de {nombre}")
        return ARGS[i + 1]
    return True


def campos_programa(nombre: str, tam: int, ow: str = "00") -> bytes:
    """Campos del comando 24/25 para un programa: tipo 01, 'system', nombre, 'PROGRAM'
    (igual que los manda la calculadora; ver volcado de casio-get)."""
    d1, d2, d3 = b"system", nombre.encode(), b"PROGRAM"
    cab = f"{ow}01{tam:08X}{len(d1):02X}{len(d2):02X}{len(d3):02X}000000".encode()
    return cab + d1 + d2 + d3


def main():
    archivos = [a for a in ARGS if not a.startswith("-")
                and a != opcion("--nombre", True)]
    if len(archivos) != 1:
        sys.exit(__doc__)
    ruta = archivos[0]
    nombre_opcion = opcion("--nombre", True)
    nombre = (nombre_opcion if isinstance(nombre_opcion, str)
                else os.path.splitext(os.path.basename(ruta))[0]).upper()
    if not re.fullmatch(r"[A-Z0-9]{1,8}", nombre):
        sys.exit(f"Nombre invalido '{nombre}': usa solo A-Z y 0-9, maximo 8 caracteres "
                    "(o indica otro con --nombre).")

    tabla = Tabla()
    with open(ruta, encoding="utf-8") as f:
        fuente = f.read()
    try:
        tokens = tabla.tokenizar(fuente)
    except ValueError as e:
        sys.exit(f"Error en {ruta}: {e}")
    paquete = empaquetar_programa(tokens)

    print(f"Programa {nombre}: {len(tokens)} bytes de codigo, {len(paquete)} bytes en total.")
    print("Asi lo vera la calculadora:")
    print("  " + tabla.destokenizar(tokens).replace("\n", "\n  "))

    if opcion("--seco"):
        from .proto import hexdump
        print("\nBytes a enviar:")
        print(hexdump(paquete))
        return

    from . import proto as P

    link = P.Link()
    activo = terminado = False
    try:
        print("\n1) Check inicial...")
        link.send(P.T_CHECK, 0x00)
        link.expect_ack("check inicial")
        activo = True

        print(f"2) Anunciando el programa {nombre} (comando 25)...")
        link.send(P.T_CMD, 0x25, P.pad(campos_programa(nombre, len(paquete))))
        t, st, d = link.recv()
        if t == P.T_NAK and st == 0x02:
            if opcion("--forzar"):
                si = True
            else:
                r = input(f"   Ya existe un programa {nombre} en la calculadora. "
                            "¿Sobrescribir? [s/N] ")
                si = r.strip().lower() in ("s", "si", "sí", "y")
            if not si:
                link.send(P.T_NAK, 0x03)
                link.expect_ack("rechazo de sobrescritura")
                print("   No se envio nada.")
                return
            link.send(P.T_ACK, 0x01)
            link.expect_ack("confirmacion de sobrescritura")
        elif t == P.T_NAK and st == 0x05:
            sys.exit("   La calculadora dice que no hay memoria suficiente.")
        elif t != P.T_ACK:
            sys.exit(f"   Respuesta inesperada: {P.NOMBRES.get(t, hex(t))} {st:02X} {d!r}")

        trozos = [paquete[i:i + 256] for i in range(0, len(paquete), 256)]
        print(f"3) Enviando {len(trozos)} paquete(s) de datos...")
        for n, trozo in enumerate(trozos, 1):
            datos = f"{len(trozos):04X}{n:04X}".encode() + P.pad(trozo)
            for intento in range(3):
                link.send(P.T_DATA, 0x25, datos)
                t, st, d = link.recv()
                if t == P.T_ACK:
                    break
                if t == P.T_NAK and st == 0x01:
                    print(f"   paquete {n}: la calculadora pidio reenvio")
                    continue
                sys.exit(f"   Respuesta inesperada al paquete {n}: "
                            f"{P.NOMBRES.get(t, hex(t))} {st:02X} {d!r}")
            else:
                sys.exit(f"   El paquete {n} fallo 3 veces.")
        print("   Enviado.")

        if not opcion("--sin-verificar"):
            print("4) Verificando: descargo el programa de vuelta (comando 24)...")
            link.send(P.T_CMD, 0x24, P.pad(campos_programa(nombre, 0)))
            t, st, d = link.recv()
            if t != P.T_ACK:
                print(f"   No pude pedirlo de vuelta ({P.NOMBRES.get(t, hex(t))} {st:02X}); "
                        "revisalo en la calculadora.")
            else:
                link.send(P.T_ROLESWAP, 0x00)
                activo = False
                recibido = b""
                while True:
                    t, st, d = link.recv()
                    if t == P.T_ROLESWAP:
                        activo = True
                        break
                    if t == P.T_CMD and st == 0x25:
                        link.send(P.T_ACK, 0x00)
                        partes = []
                        while True:
                            t2, st2, d2 = link.recv()
                            d2 = P.unpad(d2)
                            partes.append(d2[8:])
                            link.send(P.T_ACK, 0x00)
                            if int(d2[4:8], 16) >= int(d2[0:4], 16):
                                break
                        recibido = b"".join(partes)
                        continue
                    link.send(P.T_ACK, 0x00)
                util = 10 + len(tokens) + 1  # cabecera + codigo + 0x00 (el relleno puede variar)
                if recibido[:util] == paquete[:util]:
                    print("   OK: la calculadora tiene exactamente el codigo enviado.")
                else:
                    print("   DIFERENCIA entre lo enviado y lo recibido:")
                    print("   enviado :", paquete[:util].hex(" "))
                    print("   recibido:", recibido[:util].hex(" "))
    finally:
        if not terminado:
            try:
                link.send(P.T_TERM, 0x00)
                if activo:
                    link.expect_ack("terminate")
            except BaseException as e:  # noqa: BLE001 - mejor esfuerzo
                print(f"  (no se pudo cerrar limpio: {e})")
        link.close()

    print(f"\nListo. En la calculadora: MENU > PRGM > {nombre} > EXE")


if __name__ == "__main__":
    main()
