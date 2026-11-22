# SPDX-FileCopyrightText: 2026 NeftaliGC
# SPDX-License-Identifier: GPL-3.0-or-later
"""
tokens.py - Convierte texto Casio BASIC <-> bytes de la fx-9860G/9750GII.

La tabla sale de chars/chars.toml de Cahute (tabla "9860").
Reglas del tokenizador:
    - Fuera de comillas se ignoran los espacios: "Lbl 0" y "Lbl0" dan lo mismo.
    - Se reconoce siempre el comando mas largo posible ("IfEnd" antes que "If").
    - Dentro de comillas el texto va tal cual (ASCII).
    - '-' se decide por contexto: resta (0x99) despues de un valor,
        negativo (0x87) en cualquier otro caso (inicio, despues de Step, '(', ',', etc.).
    - Lineas vacias y lineas que empiezan con '##' se ignoran.
    - Cualquier palabra o simbolo desconocido es ERROR (nunca se manda como texto).
"""
import os
import re
import tomllib

# Simbolos de un caracter que en un programa son operadores (no ASCII).
OPERADORES = {"+": 0x89, "^": 0xA8, "*": 0xA9, "×": 0xA9, "/": 0xB9, "÷": 0xB9,
                "−": 0x99}  # U+2212 = resta explicita
RESTA, NEGATIVO = 0x99, 0x87

# Codigos que "terminan un valor": despues de ellos, '-' es resta.
_FIN_VALOR = (set(range(0x30, 0x3A)) | set(range(0x41, 0x5B))
                | {0x2E, 0x29, 0x5D, 0x7D, 0x8B, 0x9B, 0xC0, 0xC1, 0xCD, 0xCE, 0xD0})

# Tokens que NO se deben reconocer desde texto (chocan con variables o con
# la forma normal de escribir).  List1..List6 especiales: "List 1" debe ser
# 7F51 + '1', que es lo que guarda la calculadora (verificado en el volcado).
_EXCLUIR = set(range(0x7F6A, 0x7F70))

# Empates especiales.
_PREFERIR = {"Not": 0x7FB3}


def _es_display(code: int) -> bool:
    return 0xE500 <= code <= 0xE7FF


class Tabla:
    def __init__(self, ruta_toml: str | None = None):
        if ruta_toml is None:
            ruta_toml = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chars.toml")
        with open(ruta_toml, "rb") as f:
            entradas = tomllib.load(f)["chars"]
        entradas = [e for e in entradas if e.get("table", "9860") == "9860"]

        uni = {}  # codigo -> texto unicode (para resolver opcodes compuestos)
        for e in entradas:
            if "unicode" in e:
                uni.setdefault(e["code"], "".join(chr(c) for c in e["unicode"]))

        def texto_de(e):
            if "opcode" in e:
                partes = []
                for c in e["opcode"]:
                    if c < 0x80:
                        partes.append(chr(c))
                    elif c in uni:
                        partes.append(uni[c])
                    else:
                        return None
                return "".join(partes)
            if "unicode" in e:
                return "".join(chr(c) for c in e["unicode"])
            return None

        self.texto = {}      # codigo -> texto (para mostrar)
        candidatos = {}      # clave sin espacios -> [codigos]
        for e in entradas:
            code, t = e["code"], texto_de(e)
            if t is None:
                continue
            self.texto.setdefault(code, t)
            if code in _EXCLUIR:
                continue
            clave = t.replace(" ", "")
            if not clave:
                continue
            candidatos.setdefault(clave, []).append(code)

        self.claves = {}
        for clave, codes in candidatos.items():
            if len(clave) == 1 and 0x20 < ord(clave) < 0x7F:
                continue  # los caracteres ASCII sueltos se tratan aparte
            if clave.isascii() and clave.isalpha() and clave.isupper():
                continue  # p. ej. "MS", "PV": chocarian con variables A-Z
            if re.fullmatch(r"[A-Z](\(|/[A-Z]|%)", clave):
                continue  # P( Q( R( P/Y C/Y I%: chocan con variable por parentesis/division
            if clave.isascii() and clave.isdigit():
                continue  # p. ej. 0xB5 "10": chocaria con el numero 10
            codes = [c for c in codes if not (_es_display(c) and len(clave) > 1)]
            if not codes:
                continue  # p. ej. unidades "[J]", "[m]": chocan con List 1[J]
            if clave in _PREFERIR:
                self.claves[clave] = _PREFERIR[clave]
                continue
            codes.sort(key=lambda c: (_es_display(c), c > 0xFF and c < 0x7F00, c))
            self.claves[clave] = codes[0]
        self.max_clave = max(len(k) for k in self.claves)

        # Para dentro de comillas: caracteres no ASCII (preferir los de display)
        self.en_texto = {}
        for clave, codes in candidatos.items():
            if len(clave) == 1 and not clave.isascii():
                codes = sorted(codes, key=lambda c: (not _es_display(c), c))
                self.en_texto[clave] = codes[0]

    # ------------------------------------------------------------ texto -> bytes
    def tokenizar(self, fuente: str) -> bytes:
        salida = bytearray()
        primera = True
        for num, linea in enumerate(fuente.splitlines(), 1):
            limpia = linea.strip()
            if not limpia or limpia.startswith("##"):
                continue
            if not primera:
                salida.append(0x0D)
            primera = False
            salida += self._linea(limpia, num)
        return bytes(salida)

    def _linea(self, s: str, num: int) -> bytes:
        out, prev = bytearray(), None
        i, n = 0, len(s)

        def emitir(code):
            nonlocal prev
            if code > 0xFF:
                out.extend([code >> 8, code & 0xFF])
            else:
                out.append(code)
            prev = code

        while i < n:
            c = s[i]
            if c in " \t":
                i += 1
                continue
            if c == '"':  # cadena: hasta la siguiente comilla
                fin = s.find('"', i + 1)
                if fin < 0:
                    raise ValueError(f"linea {num}: comillas sin cerrar\n  {s}")
                emitir(0x22)
                for ch in s[i + 1:fin]:
                    if 0x20 <= ord(ch) < 0x7F:
                        out.append(ord(ch))
                    elif ch in self.en_texto:
                        code = self.en_texto[ch]
                        out += bytes([code >> 8, code & 0xFF]) if code > 0xFF else bytes([code])
                    else:
                        raise ValueError(f"linea {num}: caracter '{ch}' no soportado en texto\n  {s}")
                emitir(0x22)
                i = fin + 1
                continue
            if c == "-":
                emitir(RESTA if prev in _FIN_VALOR else NEGATIVO)
                i += 1
                continue
            # comando mas largo que coincida (ignorando espacios de la fuente)
            hallado = None
            j, compacto, mapa = i, "", []
            while j < n and len(compacto) < self.max_clave:
                if s[j] == '"':
                    break
                if s[j] not in " \t":
                    compacto += s[j]
                    mapa.append(j)
                    if compacto in self.claves:
                        hallado = (self.claves[compacto], mapa[-1] + 1)
                j += 1
            if hallado:
                emitir(hallado[0])
                i = hallado[1]
                continue
            if c.isascii() and c.islower():
                ini = i
                while ini > 0 and s[ini - 1].isascii() and s[ini - 1].isalpha():
                    ini -= 1
                palabra = s[ini:i + 1]
                k = i + 1
                while k < n and s[k].isascii() and s[k].isalpha():
                    palabra += s[k]
                    k += 1
                raise ValueError(f"linea {num}, columna {ini + 1}: comando desconocido "
                                    f"cerca de '{palabra}'\n  {s}")
            if c in OPERADORES:
                emitir(OPERADORES[c])
            elif 0x20 < ord(c) < 0x7F:
                emitir(ord(c))
            else:
                raise ValueError(f"linea {num}, columna {i + 1}: simbolo '{c}' desconocido\n  {s}")
            i += 1
        return bytes(out)

    # ------------------------------------------------------------ bytes -> texto
    def destokenizar(self, data: bytes) -> str:
        out, i = [], 0
        while i < len(data):
            b = data[i]
            if b == 0x00:
                break
            if b in (0x7F, 0xE5, 0xE6, 0xE7, 0xF7, 0xF9) and i + 1 < len(data):
                code, i = (b << 8) | data[i + 1], i + 2
            else:
                code, i = b, i + 1
            if code == 0x0D:
                out.append("\n")
            elif 0x20 <= code < 0x7F:
                out.append(chr(code))
            else:
                out.append(self.texto.get(code, f"<{code:X}>"))
        return "".join(out)


def empaquetar_programa(tokens: bytes) -> bytes:
    """Formato observado: 10 bytes en 0 + codigo + 0x00, relleno a multiplo de 4."""
    datos = bytes(10) + tokens + b"\x00"
    return datos + bytes(-len(datos) % 4)
