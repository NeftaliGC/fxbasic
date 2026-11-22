# SPDX-FileCopyrightText: 2026 NeftaliGC
# SPDX-License-Identifier: GPL-3.0-or-later
"""
proto.py - Enlace USB y paquetes de Protocol 7.00 (compartido).
Lo usan get.py y send.py. Probado con una fx-9750GII.
"""
import sys
from typing import Any, cast

try:
    import usb.core
    import usb.util
except ImportError:
    sys.exit("Falta pyusb. Instala con:  sudo pacman -S python-pyusb")

VID, PID = 0x07CF, 0x6101
TIMEOUT_MS = 10000
VERBOSE = "--detalle" in sys.argv or "-d" in sys.argv

# Tipos de paquete (T)
T_CMD, T_DATA, T_ROLESWAP, T_CHECK, T_ACK, T_NAK, T_TERM = (
    0x01, 0x02, 0x03, 0x05, 0x06, 0x15, 0x18)
NOMBRES = {T_CMD: "CMD", T_DATA: "DATA", T_ROLESWAP: "ROLESWAP",
            T_CHECK: "CHECK", T_ACK: "ACK", T_NAK: "NAK", T_TERM: "TERM"}


# ---------------------------------------------------------------- formato
def checksum(body: bytes) -> int:
    """Suma de ST..D, complemento a dos, byte bajo."""
    return (~sum(body) + 1) & 0xFF


def pad(data: bytes) -> bytes:
    """0x5C padding: bytes < 0x20 -> '\\' + (b+0x20); '\\' -> '\\\\'."""
    out = bytearray()
    for b in data:
        if b < 0x20:
            out += bytes([0x5C, b + 0x20])
        elif b == 0x5C:
            out += b"\\\\"
        else:
            out.append(b)
    return bytes(out)


def unpad(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        if b == 0x5C and i + 1 < len(data):
            n = data[i + 1]
            out.append(0x5C if n == 0x5C else n - 0x20)
            i += 2
        else:
            out.append(b)
            i += 1
    return bytes(out)


def build_packet(t: int, st: int, data: bytes | None = None) -> bytes:
    """data ya debe venir codificada (pad) si hace falta."""
    body = f"{st:02X}".encode()
    if data is None:
        body += b"0"
    else:
        body += b"1" + f"{len(data):04X}".encode() + data
    return bytes([t]) + body + f"{checksum(body):02X}".encode()


def hexdump(data: bytes, ancho: int = 16) -> str:
    lineas = []
    for i in range(0, len(data), ancho):
        trozo = data[i:i + ancho]
        hx = " ".join(f"{b:02X}" for b in trozo)
        tx = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in trozo)
        lineas.append(f"{i:04X}  {hx:<{ancho * 3}} {tx}")
    return "\n".join(lineas)


# ---------------------------------------------------------------- enlace USB
class Link:
    def __init__(self):
        # PyUSB tipa `find` como una unión con Generator cuando se usan
        # stubs que también cubren `find_all`; aquí no se solicita `find_all`.
        dev = cast(usb.core.Device | None,
                usb.core.find(idVendor=VID, idProduct=PID))
        if dev is None:
            sys.exit("No encontre la calculadora (07cf:6101). "
                        "Conectala y elige DataTrans (F1).")
        try:
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)
        except (NotImplementedError, usb.core.USBError):
            pass
        try:
            # Solo configurar si no lo esta: volver a configurar puede
            # reiniciar el estado USB de la calculadora.
            try:
                cfg = dev.get_active_configuration()
            except usb.core.USBError:
                cfg = None
            if cfg is None:
                dev.set_configuration()
        except usb.core.USBError as e:
            sys.exit(f"No pude configurar el USB: {e}\n"
                        "Revisa permisos (grupo uucp) o prueba con sudo.")
        # PyUSB expone la configuración como interfez indexable, aunque sus
        # stubs pueden tiparla de forma más amplia (por ejemplo, Generator).
        intf = cast(Any, dev.get_active_configuration())[(0, 0)]
        usb.util.claim_interface(dev, intf)
        # Flujo de control que habilita Protocol 7.00 (doc. de Cahute):
        # bmRequestType 0x41, bRequest 0x01, wValue 0, wIndex 0, sin datos.
        try:
            dev.ctrl_transfer(0x41, 0x01, 0x0000, 0x0000, None, 300)
            if VERBOSE:
                print("  (flujo de control USB 0x41/0x01 enviado)")
        except usb.core.USBError as e:
            print(f"  aviso: el flujo de control USB fallo ({e}); sigo igual")

        def es(direccion):
            return lambda e: (
                usb.util.endpoint_direction(e.bEndpointAddress) == direccion
                and usb.util.endpoint_type(e.bmAttributes)
                == usb.util.ENDPOINT_TYPE_BULK)

        # Algunos stubs de PyUSB tipan `find_descriptor` como Generator o None;
        # en tiempo de ejecucion devuelve el endpoint encontrado.
        self.ep_out = cast(Any, usb.util.find_descriptor(
            intf, custom_match=es(usb.util.ENDPOINT_OUT)))
        self.ep_in = cast(Any, usb.util.find_descriptor(
            intf, custom_match=es(usb.util.ENDPOINT_IN)))
        if self.ep_in is None or self.ep_out is None:
            sys.exit("No encontre los endpoints bulk de la calculadora.")
        self.dev, self.intf = dev, intf
        self.buf = bytearray()
        self.io_errores = 0

    def close(self):
        usb.util.release_interface(self.dev, self.intf)
        usb.util.dispose_resources(self.dev)

    def _read(self, n: int) -> bytes:
        while len(self.buf) < n:
            try:
                self.buf += bytes(self.ep_in.read(32768, TIMEOUT_MS))
            except usb.core.USBTimeoutError:
                sys.exit("\nTiempo agotado esperando a la calculadora. "
                            "Vuelve a intentarlo con --detalle y reporta la salida en un issue.")
            except usb.core.USBError as e:
                if getattr(e, "errno", None) == 5 and self.io_errores < 3:
                    # EIO: limpiar el endpoint y volver a leer
                    self.io_errores += 1
                    print(f"  aviso: error de E/S al leer ({e}); limpio el endpoint y reintento")
                    try:
                        self.dev.clear_halt(self.ep_in)
                    except usb.core.USBError:
                        pass
                    continue
                raise
        r = bytes(self.buf[:n])
        del self.buf[:n]
        return r

    def send(self, t: int, st: int, data: bytes | None = None):
        pkt = build_packet(t, st, data)
        if VERBOSE:
            print(f"  -> {NOMBRES.get(t, hex(t))} {st:02X}  {pkt[:80]!r}")
        self.ep_out.write(pkt, TIMEOUT_MS)

    def recv(self):
        t = self._read(1)[0]
        st = self._read(2)
        ex = self._read(1)
        body, d = st + ex, b""
        if ex == b"1":
            ds = self._read(4)
            d = self._read(int(ds, 16))
            body += ds + d
        cs = self._read(2)
        if int(cs, 16) != checksum(body):
            print(f"  !! checksum invalido en paquete {t:02X} {st!r}")
        if VERBOSE:
            raw = bytes([t]) + body + cs
            print(f"  <- {NOMBRES.get(t, hex(t))} {st.decode()}  {raw[:80]!r}")
        return t, int(st, 16), d

    def expect_ack(self, que: str):
        t, st, d = self.recv()
        if t != T_ACK:
            sys.exit(f"Esperaba ACK tras {que}, llego {NOMBRES.get(t, hex(t))} "
                        f"subtipo {st:02X} {d!r}")


# ---------------------------------------------------------------- comandos
def parse_cmd(d: bytes) -> dict:
    d = unpad(d)
    sizes = [int(d[12 + 2 * i:14 + 2 * i], 16) for i in range(6)]
    pos, campos = 24, []
    for s in sizes:
        campos.append(d[pos:pos + s].decode("latin-1"))
        pos += s
    return {"ow": d[0:2].decode(), "dt": int(d[2:4], 16),
            "fs": int(d[4:12], 16), "d": campos}


