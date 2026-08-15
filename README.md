# Intern Search Monitor

Watches public career boards for software-engineering intern postings and emails you when a new one appears. Checks every 20 minutes, stores seen jobs in SQLite, and skips duplicates.

The first run **seeds** the database with whatever is already posted, so you are not flooded with every current internship. After that, only newly detected listings trigger email.

## Setup

```bash
cd intern-search
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with a Gmail (or other SMTP) account:

1. Turn on 2-Step Verification for the Gmail account.
2. Create an [App Password](https://myaccount.google.com/apppasswords).
3. Put that 16-character password in `SMTP_PASSWORD`.
4. Set `ALERT_TO` to the inbox that should receive alerts.

## Run

One pass, no email (recommended first):

```bash
python intern_monitor.py --once --dry-run
```

One pass, send email for anything new (after the DB is seeded):

```bash
python intern_monitor.py --once
```

Keep running and check every 20 minutes:

```bash
python intern_monitor.py
```

Useful flags:

| Flag | What it does |
| --- | --- |
| `--once` | Single check, then exit |
| `--dry-run` | Log new jobs instead of emailing |
| `--company Stripe` | Only check companies whose name contains this text |
| `--seed` | Record current listings without sending alerts |

Logs: `data/intern_monitor.log`  
Database: `data/seen_jobs.db`

## Add or remove companies

Edit `companies.py`. Each entry is a `Company(...)` block.

- **Remove:** delete the block, or set `enabled=False`.
- **Add:** copy a nearby company that uses the same ATS and change `name` / `slug` / `careers_url`.

Typical `source` values:

- `greenhouse` — slug from `boards.greenhouse.io/{slug}`
- `ashby` — slug from `jobs.ashbyhq.com/{slug}`
- `lever` — slug from `jobs.lever.co/{slug}`
- `workday` — needs `tenant`, `dc` (`wd1`/`wd5`/…), and `site` in `extra`
- `html` — last-resort scrape of a public careers page

AIQ Markets is in the list but **disabled**. LinkedIn company pages cannot be scraped reliably; turn it on after they publish a real careers URL.

Groq and X were left out on request.

## Run on Oracle Cloud (free)

Oracle Cloud's **Always Free** tier gives you a real Linux VM that stays online with persistent disk. That is a much better home for this script than a laptop that sleeps. Signup requires a credit card for identity verification, but Always Free shapes never bill you.

### 1. Create the account and VM

1. Sign up at [cloud.oracle.com](https://cloud.oracle.com/) and pick a home region close to you.
2. In the console, go to **Compute → Instances → Create instance**.
3. **Image:** Canonical Ubuntu 22.04 (or 24.04).
4. **Shape:** open **Change shape** and pick one of the Always Free options:
   - Preferred: **VM.Standard.A1.Flex** (ARM Ampere, 1 OCPU / 6 GB). Best headroom.
   - Fallback: **VM.Standard.E2.1.Micro** (x86, 1 GB). ARM capacity is often unavailable; the micro shape is more than enough for this script.
5. **SSH keys:** upload your public key, or let Oracle generate one and download the private key.
6. **Networking:** the default VCN/subnet is fine. Under the VCN's security list, keep the default **ingress rule for TCP 22 (SSH)** — restrict the source to your IP if you can. No other inbound ports are needed. Outbound is open by default; the script needs outbound HTTPS (443) and SMTP submission (587).
7. Launch. Note the **public IPv4** once it is running.

### 2. Install and configure

SSH in and set up the app:

```bash
ssh ubuntu@<public-ip>

sudo apt update
sudo apt install -y git python3-venv python3-pip

git clone <your-repo-url> intern-search
cd intern-search

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env   # fill in SMTP_USERNAME, SMTP_PASSWORD (Gmail App Password), ALERT_TO
```

Optional: copy your already-seeded database from the laptop so you do not re-alert on every currently-open posting:

```bash
# from your laptop
scp data/seen_jobs.db ubuntu@<public-ip>:/home/ubuntu/intern-search/data/seen_jobs.db
```

Sanity check on the VM:

```bash
.venv/bin/python intern_monitor.py --once --dry-run
```

### 3. Install as a systemd service

A unit file lives at [deploy/intern-monitor.service](deploy/intern-monitor.service). Copy it into place and enable it:

```bash
sudo cp deploy/intern-monitor.service /etc/systemd/system/intern-monitor.service
sudo systemctl daemon-reload
sudo systemctl enable --now intern-monitor
```

Watch it run:

```bash
journalctl -u intern-monitor -f
sudo systemctl status intern-monitor
```

Restart after editing `.env` or `companies.py`:

```bash
sudo systemctl restart intern-monitor
```

If your image uses a non-`ubuntu` user (Oracle Linux uses `opc`, for example), edit `User=`, `WorkingDirectory=`, `EnvironmentFile=`, and `ExecStart=` in the unit file to match.

### Gotchas

- Oracle blocks outbound **port 25**. Gmail on **587** (as in [.env.example](.env.example)) works. If mail sending fails with a connect timeout, that is the Oracle block, not the script.
- ARM shape (`A1.Flex`) is frequently "Out of capacity" at launch. Try another AD (availability domain), try a different day, or fall back to `E2.1.Micro`.
- The free tier reclaims idle instances after long idle periods for some accounts. A running service like this counts as active use.
- The same [deploy/intern-monitor.service](deploy/intern-monitor.service) works on a Google Cloud `e2-micro` free VM or any other Ubuntu VPS with only path edits.

## How filtering works

A posting is kept only if the title/details look like an intern role **and** a software/engineering role (`intern` / `internship` / `co-op` / `university` / `student` plus `software` / `engineer` / `SWE` / `developer` / `SDE`).

## Notes

- Uses public job-board JSON APIs (Greenhouse, Ashby, Lever, Workday, etc.) where they exist. HTML is a fallback.
- Requests are rate-limited (~2 seconds between calls) with retries on 429/5xx.
- Career sites change. If a company starts failing, check `data/intern_monitor.log` and update that row in `companies.py`.
- Leave this running on a machine that stays online, or a free/cheap VPS. A laptop that sleeps will miss the polling cadence. See **Run on Oracle Cloud (free)** below.
