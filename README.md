# UCTalent LinkedIn Outreach

Automate LinkedIn bounty job outreach for UCTalent. Fetch jobs, generate Boolean search queries, create outreach messages, and publish social media posts.

## Quick Start

### 1. Setup

```powershell
# Install dependencies
pip install -r requirements.txt
```

### 2. Chrome Profile Setup (First Time Only)

The scripts use a **separate Chrome profile** at `C:\chrome-debug` so your personal browsing isn't affected. Chrome will **auto-create** this folder the first time you run.

```powershell
# 1. Start Chrome with remote debugging
.\start_chrome.bat
```

A new Chrome window will open. **Sign in to these accounts** (one time only, cookies are saved):

| Account | Why |
|---------|-----|
| 🔗 **LinkedIn** (linkedin.com) | Post jobs, send connection requests |
| 🐦 **X/Twitter** (x.com) | Post job tweets |
| 📘 **Facebook** (facebook.com) | Post in Vietnamese tech groups |
| 🏢 **UCTalent** (uctalent.io) | Get referral links |

After signing in, close Chrome. Next time you run `run.bat` or `start_chrome.bat`, you'll already be logged in.

### 3. Configure

```powershell
# Copy example config and fill in your info
cp config.example.json config.json
```

Edit `config.json`:
- `name`, `role`, `location` — your personal info
- `personal_story`, `mission_statement` — your authentic voice
- `linkedin_url` — your LinkedIn profile URL
- API keys: at least one AI model (NVIDIA recommended):
  - `nvidia_api_key` from [build.nvidia.com](https://build.nvidia.com)
  - Or `gemini_api_key` from [aistudio.google.com](https://aistudio.google.com)
  - Or `qwen_api_key` from [modelstudio.console.alibabacloud.com](https://modelstudio.console.alibabacloud.com)
- Set `use_nvidia: true` (or your chosen model)

### 4. Run

**One-click:**

Double-click `run.bat`

Or from terminal:

```powershell
.\run.bat
```

This will:
1. Start Chrome with remote debugging (port 9222)
2. Launch the interactive guide

### Manual steps

```powershell
# Start Chrome with dedicated profile (auto-created at C:\chrome-debug)
.\start_chrome.bat

# Then run the guide (set UTF-8 so Vietnamese/emoji display correctly)
$env:PYTHONIOENCODING='utf-8'; python guide.py
```

## Workflow

The guide walks you through each job:

| Step | Description |
|------|-------------|
| 1. Get Referral Link | Opens job page → paste link in terminal |
| 2. Generate Outreach Message | Auto-generated LinkedIn message |
| 3. Generate Social Posts | LinkedIn, X, Facebook posts |
| 4. Search | Opens Google Boolean query for candidates |
| 5. Extract Profiles | Saves LinkedIn profile URLs from search |
| 6. Open Saved Profiles | Opens all saved profiles in Chrome tabs |
| 7. Send Outreach | Send connection requests |
| 8. View Posts | Preview posts & open draft tabs |

### Refresh jobs

In the job list menu, press `c` to clear the CSV and fetch fresh jobs from UCTalent.

## Project Structure

```
├── run.bat                  # One-click launcher (Chrome + guide)
├── start_chrome.bat         # Chrome with remote debugging
├── guide.py                 # Interactive step-by-step wizard
├── linkedin_outreach.py     # Main automation logic
├── chrome_utils.py          # Chrome DevTools Protocol bridge
├── open_profiles.py         # Extract LinkedIn URLs from search results
├── collect_founder_logs.py  # Collect personal stories for content
├── config.json              # Your personal config (gitignored)
├── config.example.json      # Template for config.json
├── uctalent_jobs.csv        # Job database (auto-managed)
└── requirements.txt         # Python dependencies
```

## Requirements

- Python 3.11+
- Google Chrome
- Windows (primary support)
