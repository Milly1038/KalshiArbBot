#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y python3.10 python3.10-venv python3-pip

python3.10 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo "Export KALSHI_ENV, KALSHI_API_KEY, KALSHI_KEY_ID, KALSHI_PRIVATE_KEY_B64, ODDS_API_KEY before running."
