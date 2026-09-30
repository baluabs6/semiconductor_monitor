#!/usr/bin/env bash
# Compiles the C data-acquisition module and the C++ anomaly engine
# into shared libraries that Python loads via ctypes.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/lib"
mkdir -p "$LIB_DIR"

echo "Building libdaq (C)..."
gcc -O2 -fPIC -shared "$SCRIPT_DIR/c_src/daq.c" -o "$LIB_DIR/libdaq.so"

echo "Building libanomaly (C++)..."
g++ -O2 -fPIC -shared -std=c++17 "$SCRIPT_DIR/cpp_src/anomaly_engine.cpp" -o "$LIB_DIR/libanomaly.so"

echo "Build complete. Shared libraries written to $LIB_DIR"
