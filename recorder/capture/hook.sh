#!/bin/sh
exec "$(command -v python3 || echo /opt/miniconda3/bin/python3)" "$(dirname "$0")/hook.py"
