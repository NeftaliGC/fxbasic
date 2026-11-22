# SPDX-FileCopyrightText: 2026 NeftaliGC
# SPDX-License-Identifier: GPL-3.0-or-later
"""
fxbasic get - Descarga (SOLO LECTURA) la memoria principal de una
Casio fx-9750GII / fx-9860G por USB usando Protocol 7.00.

Uso:
    fxbasic get --check --detalle   # solo saludo + info del equipo (como p7 info)
    fxbasic get --detalle           # descarga todo a ./dump/

IMPORTANTE: conecta la calculadora DIRECTO a la PC (sin hub USB).

La calculadora debe estar conectada y en modo DataTrans (F1).
No escribe nada en la calculadora: solo pide (comando 29) que le
envie todos los archivos de su memoria principal.

Referencia del protocolo: documentacion de Cahute
  - packet-format, flows, casio-commands, specific-encodings
"""
import json
import os
import sys

from .proto import (Link, NOMBRES, T_ACK, T_CHECK, T_CMD, T_DATA,
                    T_ROLESWAP, T_TERM, hexdump, parse_cmd, unpad)

SOLO_CHECK = "--check" in sys.argv


def recibir_datos(link: Link, st_cmd: int) -> bytes:
    """Recibe paquetes DATA (subtipo = comando) hasta CN == TN."""
    partes = []
    while True:
        t, st, d = link.recv()
        if t != T_DATA or st != st_cmd:
            sys.exit(f"Esperaba DATA {st_cmd:02X}, llego {NOMBRES.get(t, hex(t))} {st:02X}")
        d = unpad(d)
        tn, cn = int(d[0:4], 16), int(d[4:8], 16)
        partes.append(d[8:])
        link.send(T_ACK, 0x00)
        if cn >= tn:
            return b"".join(partes)


def nombre_seguro(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s) or "_"


def info_equipo(link: Link):
    """Comando 01 (info del dispositivo), igual que p7 info."""
    link.send(T_CMD, 0x01)
    t, st, d = link.recv()
    if t != T_ACK or st != 0x02:
        sys.exit(f"Esperaba ACK extendido, llego {NOMBRES.get(t, hex(t))} {st:02X}")
    d = unpad(d)
    campos = [("HWID", 0, 8), ("CPUID", 8, 16), ("OS", 0x50, 16),
              ("Producto", 0x84, 16), ("Usuario", 0x94, 16)]
    for nombre, ini, tam in campos:
        print(f"   {nombre:9}: {d[ini:ini + tam].decode('latin-1').strip(chr(0xFF)).strip()}")


def main():
    link = Link()
    activo = False      # True mientras nosotros somos el lado activo
    terminado = False
    indice = []
    try:
        print("1) Check inicial...")
        link.send(T_CHECK, 0x00)
        link.expect_ack("check inicial")
        activo = True

        if SOLO_CHECK:
            print("2) Info del equipo (comando 01)...")
            info_equipo(link)
        else:
            os.makedirs("dump", exist_ok=True)
            print("2) Pidiendo todos los archivos de la memoria principal (cmd 29)...")
            link.send(T_CMD, 0x29)
            link.expect_ack("comando 29")
            link.send(T_ROLESWAP, 0x00)
            activo = False

            print("3) Recibiendo...")
            while True:
                t, st, d = link.recv()
                if t == T_ROLESWAP:
                    activo = True  # la calculadora termino; volvemos a ser activos
                    break
                if t == T_CHECK:
                    link.send(T_ACK, 0x00)
                    continue
                if t == T_TERM:
                    link.send(T_ACK, 0x00)
                    terminado = True
                    print("La calculadora cerro la conexion.")
                    break
                if t == T_CMD and st == 0x25:
                    info = parse_cmd(d)
                    link.send(T_ACK, 0x00)
                    datos = recibir_datos(link, 0x25)
                    dir_, nombre, grupo = info["d"][0], info["d"][1], info["d"][2]
                    archivo = (f"{info['dt']:02X}_{nombre_seguro(dir_)}_"
                               f"{nombre_seguro(grupo)}_{nombre_seguro(nombre)}.bin")
                    with open(os.path.join("dump", archivo), "wb") as f:
                        f.write(datos)
                    indice.append({"archivo": archivo, "tipo": info["dt"],
                                   "directorio": dir_, "nombre": nombre, "grupo": grupo,
                                   "tam_declarado": info["fs"], "tam_recibido": len(datos),
                                   "otros": info["d"][3:]})
                    print(f"   - tipo={info['dt']:02X} dir='{dir_}' grupo='{grupo}' "
                          f"nombre='{nombre}' {len(datos)} bytes")
                    continue
                print(f"   ? paquete inesperado {NOMBRES.get(t, hex(t))} {st:02X} {d!r}")
                link.send(T_ACK, 0x00)
    finally:
        # Cerrar SIEMPRE la sesion para no dejar la calculadora atorada.
        if not terminado:
            try:
                print("Cerrando conexion...")
                link.send(T_TERM, 0x00)
                if activo:
                    link.expect_ack("terminate")
            except BaseException as e:  # noqa: BLE001 - mejor esfuerzo
                print(f"  (no se pudo cerrar limpio: {e})")
        link.close()

    if SOLO_CHECK:
        print("\nSaludo OK: el script habla con la calculadora igual que p7.")
        return

    with open(os.path.join("dump", "indice.json"), "w") as f:
        json.dump(indice, f, indent=2, ensure_ascii=False)
    print(f"\nListo: {len(indice)} archivos en ./dump/ (ver dump/indice.json)\n")
    for e in indice:
        texto = (e["directorio"] + e["grupo"] + e["nombre"]).upper()
        if "PROG" in texto or "TOKENS" in texto:
            with open(os.path.join("dump", e["archivo"]), "rb") as f:
                print(f"=== {e['nombre']} ({e['grupo']}) ===")
                print(hexdump(f.read()))
                print()


if __name__ == "__main__":
    main()
