# UCTalent LinkedIn Outreach

Automate LinkedIn bounty job outreach for UCTalent. Fetch jobs, generate Boolean search queries, create outreach messages, and publish social media posts.

## Quick Start

### 1. Setup

```powershell
# Install dependencies
pip install -r requirements.txt
```

### 2. Configure

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

### 3. Run

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
# Just start Chrome (if run.bat didn't)
.\start_chrome.bat

# Then run the guide
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
