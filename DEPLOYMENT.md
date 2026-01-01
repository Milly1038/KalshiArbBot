# Ubuntu VPS setup (Ashburn, VA)

```bash
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3-pip

python3.10 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

export KALSHI_ENV=DEMO
export KALSHI_API_KEY=your_kalshi_key
export KALSHI_KEY_ID=your_kalshi_key_id
export ODDS_API_KEY=your_odds_api_key

python main.py
```
