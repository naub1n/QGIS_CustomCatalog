#!/bin/bash
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PLUGIN_DIR="$(dirname "$SCRIPT_DIR")"
pyrcc5 -o $PLUGIN_DIR/resources.py $PLUGIN_DIR/resources.qrc