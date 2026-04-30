#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$HOME/.local/src"
SQLITE_VERSION="3.53.0"
SQLITE_AUTOCONF="3530000"
SQLITE_PREFIX="$HOME/.local/sqlite-$SQLITE_VERSION"
SQLITE_TARBALL="sqlite-autoconf-$SQLITE_AUTOCONF.tar.gz"
PYTHON_VERSION="3.14.2"
PYTHON_PREFIX="$HOME/.local/python-$PYTHON_VERSION"
PYTHON_TARBALL="Python-$PYTHON_VERSION.tgz"
PYTHON_DIR="Python-$PYTHON_VERSION"

log() {
    printf '\n[%s] %s\n' "setup" "$1"
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Comando obrigatório ausente: %s\n' "$1" >&2
        exit 1
    fi
}

install_sqlite() {
    if [ -x "$SQLITE_PREFIX/bin/sqlite3" ]; then
        log "SQLite $SQLITE_VERSION já está instalado em $SQLITE_PREFIX"
        return
    fi

    log "Instalando SQLite $SQLITE_VERSION em $SQLITE_PREFIX"
    mkdir -p "$SRC_DIR"
    cd "$SRC_DIR"

    if [ ! -f "$SQLITE_TARBALL" ]; then
        curl -LO "https://www.sqlite.org/2026/$SQLITE_TARBALL"
    fi

    rm -rf "sqlite-autoconf-$SQLITE_AUTOCONF"
    tar -xzf "$SQLITE_TARBALL"
    cd "sqlite-autoconf-$SQLITE_AUTOCONF"
    ./configure --prefix="$SQLITE_PREFIX"
    make -j"$(nproc)"
    make install
}

install_python() {
    if [ -x "$PYTHON_PREFIX/bin/python3.14" ]; then
        log "Python $PYTHON_VERSION já está instalado em $PYTHON_PREFIX"
        return
    fi

    log "Instalando Python $PYTHON_VERSION em $PYTHON_PREFIX"
    mkdir -p "$SRC_DIR"
    cd "$SRC_DIR"

    if [ ! -f "$PYTHON_TARBALL" ]; then
        curl -LO "https://www.python.org/ftp/python/$PYTHON_VERSION/$PYTHON_TARBALL"
    fi

    rm -rf "$PYTHON_DIR"
    tar -xzf "$PYTHON_TARBALL"
    cd "$PYTHON_DIR"

    export PKG_CONFIG_PATH="$SQLITE_PREFIX/lib/pkgconfig"
    export CPPFLAGS="-I$SQLITE_PREFIX/include"
    export LDFLAGS="-L$SQLITE_PREFIX/lib -Wl,-rpath,$SQLITE_PREFIX/lib"

    ./configure --prefix="$PYTHON_PREFIX" --with-ensurepip=install
    make -j"$(nproc)"
    make install
}

recreate_venv() {
    log "Recriando .venv com Python $PYTHON_VERSION"
    cd "$ROOT_DIR"
    rm -rf .venv
    "$PYTHON_PREFIX/bin/python3.14" -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
}

main() {
    require_command curl
    require_command gcc
    require_command make
    require_command tar

    install_sqlite
    install_python
    recreate_venv

    log "Concluído. Para usar o ambiente: source .venv/bin/activate"
}

main "$@"
