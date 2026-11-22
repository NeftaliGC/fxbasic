# fxbasic

Herramientas en Python para pasar programas **Casio BASIC** desde la PC (Linux) a una calculadora **Casio fx-9750GII** por USB, sin FA-124 ni Windows.

Escribes el programa en un `.txt` con la sintaxis normal (`→`, `⇒`, `If`, `Locate`, …). La herramienta lo convierte a los códigos internos de la calculadora, lo manda a la memoria principal y lo vuelve a descargar para comprobar que llegó idéntico.

Probado con una fx-9750GII (OS 02.04.0701) en CachyOS (Arch). En teoría también funciona con otros modelos de la familia fx-9860G (fx-9860GII, Graph 35+/75/85), aunque no se ha probado.

---

## Qué hay en el proyecto

| Archivo | Qué hace |
|---|---|
| `fxbasic/cli.py` | Comando `fxbasic`: recibe el subcomando (`send` o `get`) y llama al módulo correspondiente. |
| `fxbasic/send.py` | Subcomando `fxbasic send`: envía un programa `.txt` a la calculadora y lo verifica. |
| `fxbasic/get.py` | Subcomando `fxbasic get`: descarga (solo lectura) toda la memoria principal a `./dump/`. Sirve para respaldar y para investigar. |
| `fxbasic/tokens.py` | Tokenizador: convierte texto Casio BASIC a bytes, y bytes a texto. |
| `fxbasic/proto.py` | Enlace USB y paquetes de Protocol 7.00 (compartido). |
| `fxbasic/chars.toml` | Tabla de caracteres y comandos de CASIO, tomada de [Cahute](https://cahute.org). Ver [Licencia y créditos](#licencia-y-créditos). |
| `programas/` | Programas en texto listos para enviar (PRUEBA, DIST, VEC, TABU). |
| `dump/` | Lo que descarga `fxbasic get` (respaldo de la calculadora). Ignorado por git. |

---

## Requisitos

- Linux con udev (probado en CachyOS / Arch).
- Python 3.11 o superior (usa `tomllib`).
- [pyusb](https://pyusb.github.io/pyusb/) para el acceso USB.
- Permiso para usar el USB de la calculadora sin `sudo`. La regla udev de Cahute lo da a través del grupo `uucp`.
- Un cable **mini-USB que transmita datos** (algunos solo cargan).

### Instalación (Arch / CachyOS)

```bash
paru -S cahute                 # instala la regla udev; opcionalmente p7 para diagnóstico
sudo usermod -aG uucp $USER    # luego cerrar sesión y volver a entrar
```

Después, instala la herramienta. Elige una forma:

**A. Instalarla como comando (recomendado):**

```bash
pipx install git+https://github.com/NeftaliGC/fxbasic   # directo de GitHub
pipx install .                                          # o desde una copia clonada
```

Así queda disponible el comando `fxbasic` en cualquier carpeta. pyusb se instala solo. Si no tienes pipx: `sudo pacman -S python-pipx`. También sirve un entorno virtual:

```bash
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/fxbasic send programas/PRUEBA.txt --seco
```

**B. Sin instalar nada (con pyusb del sistema):**

Clona el repositorio (`git clone https://github.com/NeftaliGC/fxbasic`) y, dentro de la carpeta:

```bash
sudo pacman -S python-pyusb
python3 -m fxbasic send programas/PRUEBA.txt --seco   # en lugar de fxbasic send
python3 -m fxbasic get --check -v                     # en lugar de fxbasic get
```

En todos los casos hace falta `libusb` del sistema (en Arch ya viene como dependencia). Si Arch actualiza Python a una versión mayor, reinstala con `pipx reinstall fxbasic` o vuelve a crear `.venv/`.

---

## Uso

### Preparar la calculadora

1. Conecta la calculadora **directo a un puerto de la PC, sin hub USB** (ver [Problemas comunes](#problemas-comunes)).
2. En la ventana que aparece en la calculadora, elige **DataTrans (F1)**. Debe mostrar "Recibiendo… AC: Cancelar".

Después de cada envío o descarga, la calculadora sale de ese modo. Para la siguiente operación hay que volver a elegir DataTrans.

### Enviar un programa

```bash
# 1. Revisar sin USB qué se va a mandar (texto reconstruido y bytes)
fxbasic send programas/PRUEBA.txt --seco

# 2. Enviar
fxbasic send programas/PRUEBA.txt
```

Después, en la calculadora: **MENU > PRGM > PRUEBA > EXE**.

| Opción | Efecto |
|---|---|
| `--nombre N` | Nombre en la calculadora (A–Z y 0–9, máximo 8). Por defecto, el nombre del archivo. |
| `--forzar` | Sobrescribe sin preguntar si ya existe un programa con ese nombre. |
| `--seco` | No usa el USB: solo tokeniza y muestra el resultado. |
| `--sin-verificar` | No vuelve a descargar el programa para compararlo. |
| `-v` | Muestra cada paquete enviado y recibido. |

### Descargar la memoria de la calculadora

```bash
fxbasic get --check -v   # solo saludo e info del equipo (como `p7 info`)
fxbasic get -v           # descarga todo a ./dump/ y crea dump/indice.json
```

La descarga no modifica nada en la calculadora.

---

## Cómo escribir los programas `.txt`

Se escriben igual que en la pantalla de la calculadora, en UTF-8, una instrucción por línea.

```
## Las líneas que empiezan con ## son comentarios y no se envían
ClrText
"N PUNTOS"?→N
For 1→I To N Step 1
If List 1[I]≠0
Then
Locate 1,I,List 1[I]
IfEnd
Next
```

Reglas del tokenizador:

- **Fuera de comillas, los espacios no importan:** `Lbl 0` y `Lbl0` dan lo mismo.
- **Siempre se reconoce el comando más largo:** `IfEnd` no se lee como `If` + `End`.
- **Dentro de comillas, el texto va tal cual** (ASCII). Ahí se pueden usar letras minúsculas y acentos.
- **El signo `-` se decide por contexto:** es resta después de un valor (`A-1`, `List 2-List 2[I]`) y negativo en cualquier otro caso (`-1→A`, `Step -1`, `A×-2`). Si necesitas forzar una resta, usa `−` (U+2212).
- **Las palabras desconocidas son error:** si escribes `Lcoate`, el script se detiene y te dice la línea, en vez de mandar el texto letra por letra (eso haría que la calculadora marque `Syntax ERROR`).
- **Las líneas vacías se ignoran.**

Símbolos útiles:

| Escribe | Significa | | Escribe | Significa |
|---|---|---|---|---|
| `→` | asignar | | `×` o `*` | multiplicar |
| `⇒` | salto condicional | | `÷` o `/` | dividir |
| `≠ ≤ ≥` | comparaciones | | `²` `^` `√` | potencias y raíz |
| `◢` | pausa y mostrar | | `θ` `π` | variables especiales |

---

## Cómo funciona

### Protocolo

La calculadora habla **Protocol 7.00** por USB (VID `07cf`, PID `6101`, endpoints bulk). La documentación de referencia es la de [Cahute](https://cahute.org/topics/protocols/seven/). La secuencia para enviar un programa:

1. Flujo de control USB `0x41/0x01` (habilita Protocol 7.00).
2. Check inicial (`05`) → ACK.
3. Comando `25` "Transfer file" (memoria principal) con los datos del archivo → ACK. Si el programa ya existe, la calculadora responde NAK `02` y el script pide confirmación (ACK `01` para sobrescribir, NAK `03` para cancelar).
4. Paquetes de datos (`02`) de hasta 256 bytes, cada uno con su ACK.
5. Verificación: comando `24` "Request file transfer" → cambio de roles → la calculadora envía el programa de vuelta.
6. Fin (`18`) → ACK. El script siempre intenta cerrar la sesión, aunque algo falle a la mitad, para no dejar la calculadora atorada.

Los datos se codifican con el escape `0x5C` (bytes menores a `0x20` → `\` + byte+`0x20`) y cada paquete lleva un checksum de complemento a dos.

### Formato de un programa en memoria

Obtenido descargando programas de la calculadora con `fxbasic get`:

| Campo | Valor |
|---|---|
| Tipo de dato | `01` |
| Directorio | `system` |
| Nombre | p. ej. `PRUEBA` |
| Grupo | `PROGRAM` |
| Contenido | 10 bytes en cero (cabecera, probablemente la contraseña) + código + `00` + relleno hasta múltiplo de 4 |

### Tokens

Cada comando ocupa 1 o 2 bytes. Por ejemplo, `→` = `0E`, `⇒` = `13`, `If` = `F7 00`, `Locate` = `F7 10`, `List` = `7F 51`, `Lbl` = `E2`. La tabla completa sale de `chars.toml`. Unos cuantos tokens se excluyen a propósito, porque chocan con la forma normal de escribir:

- Unidades y caracteres de solo display (`E5xx`–`E7xx`), como `[J]` (joule), que se confundía con `List 1[J]`.
- `List1`…`List6` en un solo token: la calculadora guarda `List 1` como `7F 51` + `1`.
- Tokens que coinciden con variables: `P(`, `Q(`, `R(`, `MS`, `PV`, `10`, etc.

---

## Programas incluidos

| Programa | Qué hace |
|---|---|
| `PRUEBA` | Prueba rápida de la transferencia: muestra "FLECHAS OK", "DISTINTO OK" y un 3. |
| `DIST` | Arma la matriz de distancias **Mat A** desde coordenadas en List 2 (X) y List 3 (Y), euclidiana o Manhattan. |
| `VEC` | Genera los vecinos de la solución en **List 1** por swap o 2-opt y los guarda en **Mat C** (una fila por vecino; las dos últimas columnas indican el movimiento). |
| `TABU` | Programa completo de apoyo para búsqueda tabú: distancias, solución, vecinos (swap, inserción, 2-opt) y lista tabú. **Todavía no se ha probado en la calculadora.** |

Al terminar un programa, la calculadora muestra el último valor que calculó (por ejemplo, un `0` en DIST o un `4` en VEC). Es normal.

---

## Problemas comunes

**La calculadora no aparece o se cuelga a mitad de la conexión.**
Conéctala **directo a la PC, sin hub**. Con un hub, el puerto puede quedar dañado (en `dmesg` aparece `device descriptor read/64, error -110` o `unable to enumerate USB device`), y entonces ni p7 ni estos scripts la ven. Para revisar:
```bash
lsusb | grep -i casio        # debe mostrar 07cf:6101
sudo dmesg | tail -15
```
Si el controlador USB quedó en mal estado, reiniciar la PC lo arregla.

**La calculadora se queda en "Recibiendo…" y no responde.**
Desconecta el cable, presiona AC/EXIT y apágala y préndela. El botón RESTART de atrás es el último recurso: normalmente conserva los programas, pero pierde lo que no se haya respaldado desde la última vez que se apagó.

**`Syntax ERROR` al correr un programa.**
En la pantalla del error, presiona **◀** o **▶** (no EXIT): el editor abre con el cursor en el punto del error. Revisa los bytes de esa línea con `--seco`; si un comando salió con un código raro, puede ser una colisión del tokenizador.

**`No pude configurar el USB` o error de permisos.**
Revisa que tu usuario esté en el grupo `uucp` (`groups | grep uucp`) y que hayas cerrado sesión después de agregarlo.

---

## Límites actuales

- Solo envía **programas**. No envía listas, matrices ni imágenes.
- Un programa por sesión.
- Nombres de A–Z y 0–9, máximo 8 caracteres, sin contraseña.
- El tokenizador está probado con los ~35 comandos que usan los programas incluidos. Los demás de `chars.toml` deberían funcionar, pero no están verificados en la calculadora.

## Ideas pendientes

- Enviar varios programas en una sola sesión.
- Enviar listas y matrices desde archivos (CSV).
- Que `fxbasic get` guarde los programas descargados como `.txt` legibles.
- Probar y depurar TABU en la calculadora.

---

## Licencia y créditos

Este proyecto se distribuye bajo la licencia **GPL-3.0 o posterior** (ver [`LICENSE`](LICENSE)).

- **[Cahute](https://cahute.org)**, de Thomas Touhey: la documentación de Protocol 7.00 que hizo posible este proyecto, y el archivo `fxbasic/chars.toml`, que se incluye sin cambios bajo su licencia original [CeCILL 2.1](https://cecill.info) (compatible con la GPL). Su encabezado de licencia debe conservarse.
- Los formatos y el comportamiento de la fx-9750GII se verificaron con capturas USB (`usbmon`) y descargas de la propia calculadora.

Este proyecto no está afiliado a CASIO. Úsalo bajo tu propio riesgo. Escribir en la memoria principal es de bajo riesgo, pero lo peor que podría pasar es perder lo que tengas guardado en la calculadora.