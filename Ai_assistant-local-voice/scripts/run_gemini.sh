#!/bin/bash
# run_gemini.sh
cd "$(dirname "$0")/.."
python3 server.py --profile gemini
