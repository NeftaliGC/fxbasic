# Registro de cambios

Todos los cambios importantes de este proyecto se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

## [0.1.0] - 2026-11-22

Primera versión publicada.

### Agregado

- `fxbasic send`: convierte un programa Casio BASIC escrito en texto a los
  códigos de la calculadora, lo envía a la memoria principal por USB
  (Protocol 7.00) y lo descarga de vuelta para comprobar que llegó idéntico.
  - `--seco` para revisar el resultado sin usar el USB.
  - `--nombre` para elegir el nombre en la calculadora.
  - `--forzar` para sobrescribir sin preguntar.
  - `--sin-verificar` para omitir la descarga de comprobación.
- `fxbasic get`: descarga en solo lectura la memoria principal a `./dump/`,
  con un índice en `dump/indice.json`. Con `--check` solo muestra la
  información del equipo, como `p7 info`.
- `-d` / `--detalle` para mostrar cada paquete enviado y recibido.
- `-v` / `--version` para mostrar la versión y la licencia, y `--help` en
  cada subcomando, sin abrir el USB.
- Tokenizador basado en la tabla `chars.toml` de Cahute: reconoce siempre el
  comando más largo, decide el signo `-` por contexto y rechaza las palabras
  desconocidas indicando la línea.
- Programas de ejemplo en `programas/`: PRUEBA, DIST, VEC y TABU.
- Instalación como paquete con `pyproject.toml`.

[Sin publicar]: https://github.com/NeftaliGC/fxbasic/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/NeftaliGC/fxbasic/releases/tag/v0.1.0
