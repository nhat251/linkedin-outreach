# UCTalent Bounty Outreach Workflow

## Overview

Semi-automated LinkedIn outreach system for UCTalent bounty jobs. Fetches job listings, generates personalized social media content, extracts referral links, and opens draft tabs for posting — all while staying under platform detection limits.

---

## Files

| File | Purpose |
|------|---------|
| `guide.py` | **Start here** — Interactive step-by-step wizard |
| `linkedin_outreach.py` | Main script: fetches jobs, generates queries & messages |
| `open_profiles.py` | Extracts LinkedIn profile URLs from Google search results |
| `collect_founder_logs.py` | Collect your authentic stories/opinions for content |
| `config.json` | Personal context & brand voice configuration |
| `uctalent_jobs.csv` | **Single persistent file** — auto-created, tracks all jobs |

---

## Data Management

All job data is stored in a **single persistent file**: `uctalent_jobs.csv`

- New jobs are **appended** (not overwritten)
- Existing jobs are **updated** with new data
- Timestamps track when jobs were created and last updated

### CSV Columns

| Column | Description |
|--------|-------------|
| `id` | Job ID from UCTalent API |
| `title` | Job title |
| `referral_link` | Unique referral link (manual paste from job page) |
| `bounty` | Referral bounty amount |
| `location` | Job location |
| `salary` | Salary range |
| `priority` | Job priority level |
| `tags` | Comma-separated job tags/skills |
| `description` | Full job description |
| `boolean_query` | Google Boolean search query |
| `outreach_message` | Personalized message template |
| `linkedin_post` | Generated LinkedIn post |
| `x_post` | Generated X/Twitter post |
| `facebook_post` | Generated Facebook post (Vietnamese) |
| `image_text` | Text for image/creative |
| `linkedin_comment` | Comment with referral link for LinkedIn |
| `x_comment` | Comment with referral link for X |
| `facebook_comment` | Comment with referral link for Facebook |
| `linkedin_profiles` | Extracted LinkedIn profile URLs |
| `status` | Tracking: pending → done |
| `connect_status` | Tracking: pending → searching → ready_to_connect → sent |
| `message_status` | Tracking: pending → sent |
| `created_at` | When job was first added (YYYY-MM-DD HH:MM) |
| `last_updated` | Last time job data was updated (YYYY-MM-DD HH:MM) |

---

## Quick Start (Windows)

### 1. Install Dependencies
```bash
cd linkedin_outreach
pip install -r requirements.txt
```

### 2. Start Chrome with Remote Debugging
Close all Chrome windows first, then run:
```bash
start_chrome.bat
```
Or manually (PowerShell):
```
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir="C:\chrome-debug"
```

### 3. Run the Guide
```bash
python guide.py
```

Follow the prompts. Work on **one job per day** to stay safe.

---

> **macOS users**: Use `python3` instead of `python`. Chrome automation uses AppleScript (original version).

---

## Step-by-Step Workflow

### STEP 1: Open Chrome
- Open Chrome signed in to your accounts
- Verify LinkedIn, Twitter/X, and UCTalent are accessible
- Keep normal tabs open (looks more natural to platforms)

### STEP 1.5: Add Your Authentic Voice (Optional)
Run `collect_founder_logs.py` to add your personal stories, opinions, and insights. This makes content feel like YOU, not a template.

### STEP 2: Fetch Jobs
Runs `linkedin_outreach.py`:
- Fetches up to 25 bounty jobs from UCTalent
- Skips jobs already in CSV
- Generates Boolean search queries
- Creates outreach messages

### STEP 3: Work on Individual Jobs
Select a job number. When you enter a job, it **automatically** prepares:

1. **🔗 Opens job page** for manual referral link copying (if no link exists)
2. **📝 Generates outreach message** if not exists
3. **📢 Generates social posts** (LinkedIn, X, Facebook) if referral link exists but posts don't

Then use the menu for remaining actions:

| Option | Action |
|--------|--------|
| 1. 🔗 Get Referral Link | Opens job page in Chrome for manual link copying |
| 2. 📝 Generate Outreach Message | Creates personalized message for selected job |
| 3. 📢 Generate Social Posts | Creates LinkedIn, X, Facebook posts with referral link |
| 4. 🔍 Search | Opens Boolean query in Chrome tab |
| 5. 👥 Profiles | Extracts LinkedIn URLs from search page |
| 6. 🤝 Outreach | Send connection requests (manual, 20-25/day max) |
| 7. 📤 Post | View generated posts & open draft tabs |
| 8. ✅ Done | Mark job complete, go back to list |

### STEP 4: Session Summary
Shows completed vs remaining jobs. Run `guide.py` again anytime to continue.

---

## Anti-Detection Guidelines

### Daily Limits
- **Google searches**: 20-30/hour max
- **LinkedIn connections**: 20-25/day (~100/week hard limit)
- **Profile views**: 30-40/day
- **Spread across days**: Don't do everything in one session

### Safety Rules
- Use your **normal Chrome profile** (not incognito)
- Add random delays between actions (built into scripts)
- Never automate connection sends — always manual
- Mix automation with real usage (scroll feed, like posts)
- Stop if you see CAPTCHA or warnings
- Run during normal working hours

---

## Configuring Personal Context (`config.json`)

Edit `config.json` to customize your brand voice and target audiences:

```json
{
  "name": "Your Name",
  "role": "CEO & Founder at UCTalent",
  "personal_story": "...",
  "mission_statement": "...",
  "brand_voice": "Bold, authentic, founder-to-founder",
  "common_hashtags": "#Web3Jobs #DecentralizedHiring #UCTalent",
  "targets": {
    "talent": {
      "focus": "Career growth, AI matching, bypassing gatekeepers.",
      "cta_phrases": {
        "linkedin": "Stop being ghosted. Apply directly via our AI Agent here 👉",
        "twitter": "Tired of black-hole job apps? Level up your career here 🚀",
        "facebook": "Apply ngay để AI Agent giúp bạn kết nối trực tiếp với hiring manager! 💪"
      }
    },
    "referrer": {
      "focus": "Passive income, decentralized headhunting, network value.",
      "cta_phrases": {
        "linkedin": "Grab your unique link, share it with your network, and earn 💸",
        "twitter": "Your network is an asset. Copy the link, share it, get paid 🚀",
        "facebook": "Copy link và share cho network của bạn. Nhận thưởng referral minh bạch! 🚀"
      }
    }
  }
}
```

### How Random Target Selection Works
Each post randomly picks either **talent** or **referrer** focus:

**Talent-focused posts:**
- Hook: "AI-powered matching that bypasses gatekeepers..."
- CTA: "Stop being ghosted. Apply directly via our AI Agent 👉"
- Focus: Career growth, skill matching, no middlemen

**Referrer-focused posts:**
- Hook: "Your network is your net worth. Monetize it."
- CTA: "Grab your unique link, share it, and earn 💸"
- Focus: Passive income, decentralized headhunting, blockchain rewards

---

## Qwen AI Integration (Optional)

The workflow uses Alibaba's **Qwen AI API** to generate more authentic, AI-powered content with your personal brand voice.

### Setup

1. Create account at [Model Studio](https://modelstudio.console.alibabacloud.com/ap-southeast-1) (international region)
2. Go to **API Key** → **Create API Key**
3. Copy and add to `config.json`:

```json
{
  "qwen_api_key": "YOUR_API_KEY_HERE",
  "use_qwen": true
}
```

**Important**: The workflow uses the international endpoint (`dashscope-intl.aliyuncs.com`). API keys from China region (`dashscope.aliyuncs.com`) will not work.

### System Prompt

When enabled, Qwen uses your config to generate content:
- **Name & Role**: From config
- **Brand Voice**: Bold, authentic, founder-to-founder
- **Personal Story**: Your founder story
- **Founder Logs**: Your real opinions and observations
- **Industry Takes**: Your views on the market
- **Recent Insights**: What's on your mind lately
- **Target Audience**: Talent vs Referrer focus with different CTAs

### Content Types Generated

| Type | Description |
|------|-------------|
| **LinkedIn Post** | Hook + body + CTA + sign-off + hashtags (~3000 chars) |
| **X/Twitter Post** | Short hook + body + "link in comments" CTA (~280 chars) |
| **Facebook Post** | Vietnamese/English mix, relatable to VN tech community |
| **Outreach Message** | Same message for all candidates, focused on job, includes referral link |

### How It Works

1. If `use_qwen: true`, the system calls Qwen API with your system prompt
2. User prompt includes job details (title, bounty, location, skills, referral link)
3. Qwen generates content following the rules (founder voice, no corporate fluff)
4. If API fails, falls back to template-based generation

### Rules Given to AI

- Write as if you're personally typing this - not a marketing team
- Use your real opinions and observations
- No corporate buzzwords or AI-sounding language
- Be direct, bold, authentic
- Keep posts under platform limits
- Include relevant emojis naturally
- Never sound desperate or salesy
- Sound like a real founder, not a bot

---

## Social Media Posting Strategy

### Hybrid Approach (Zero Ban Risk)
Instead of fully automating posts (which risks account restriction), this tool uses a hybrid method:

1. **Content generation**: Fully automated
2. **Draft tabs**: Open manually when you choose "Post" option
3. **Posting**: Manual one-click confirmation

**Why?** Platforms detect non-human patterns. One flag = restricted account = lost outreach channel.

### Platform Instructions

| Platform | Method | Steps |
|----------|--------|-------|
| **LinkedIn** | Homepage | Open linkedin.com → Paste text → Click Post |
| **X/Twitter** | Intent URL | Opens with text pre-filled → Click Tweet |
| **Facebook** | Homepage | Open facebook.com → Paste text → Click Share |

### Best Times to Post
- **LinkedIn**: Tuesday-Thursday, 8-10 AM or 12-2 PM (local time)
- **Twitter/X**: Monday-Friday, 9-11 AM or 6-8 PM
- **Facebook**: Wednesday-Sunday, 7-9 PM (Vietnam time)

---

## Troubleshooting

### "Could not find referral link"
- This is expected. Referral links are dynamically generated when you click "Refer & Earn"
- Use option "1. Get Referral Link" in STEP 3 to open the job page
- Then manually copy the link to CSV

### "Chrome remote debugging not accessible" (Windows)
- Make sure Chrome is running with `--remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir="C:\chrome-debug"`
- Run `start_chrome.bat` to start Chrome correctly with the debug flags
- Verify with: `python chrome_utils.py diagnose`
- If Chrome is already running, close all windows and restart with debugging enabled

### CDP / WebSocket errors (Windows)
- Scripts now use Chrome DevTools Protocol (CDP) instead of AppleScript
- Ensure Chrome remote debugging is active on port 9222
- If you see "CDP execute_js error" or connection refused:
  1. Close all Chrome windows
  2. Run `start_chrome.bat`
  3. Wait a few seconds for Chrome to fully load
  4. Retry the script

### Clipboard not working (Windows)
- The script uses `pyperclip` library (cross-platform)
- Falls back to PowerShell `Get-Clipboard` / `Set-Clipboard`
- If clipboard operations fail, install pyperclip: `pip install pyperclip`

### No new jobs found
- All jobs have been processed before. Wait for new bounty listings

### Profile extraction returns 0 results
- Make sure you're viewing a Google search results page
- Try scrolling the page first before running extraction
- Page 2 extraction may fail if Google changes navigation

### LinkedIn URL Normalization
- Country subdomains are automatically removed during extraction and display
- Example: `https://vn.linkedin.com/in/name` → `https://linkedin.com/in/name`
- Example: `https://uk.linkedin.com/in/johndoe` → `https://linkedin.com/in/johndoe`
- Preserves `www` prefix: `https://www.linkedin.com/in/name` stays unchanged
- This ensures consistent URL format across all profiles

### Qwen API Returns Empty
- Verify your API key is from **Model Studio international** (not China)
- Check `config.json` has correct key in `qwen_api_key` field
- Ensure `use_qwen` is set to `true`
- If API fails, system automatically falls back to template-based generation

### Qwen API Errors
- **401 Unauthorized**: API key is invalid or expired — get a new key from Model Studio
- **403 Forbidden**: API key doesn't have permission — check key settings in console
- **429 Too Many Requests**: Rate limit hit — wait and retry
- System auto-falls back to templates if API fails

---

## Requirements

- Python 3.9+
- Chrome browser (signed in to your personal accounts)
- Windows 10/11 (or macOS with AppleScript for original version)

### Windows Setup

1. **Install required packages:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Enable Chrome Remote Debugging (CDP):**
   - Close all Chrome windows
   - Run `start_chrome.bat` (double-click) OR
   - Open PowerShell and run:
      ```powershell
      & "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir="C:\chrome-debug"
      ```
    - Uses separate profile at `C:\chrome-debug` so Chrome automation works reliably
    - Sign into LinkedIn ONCE in this Chrome — cookies persist for future sessions

3. **Verify setup:**
   ```bash
   python chrome_utils.py diagnose
   ```

### macOS Setup (Original)

- Required packages:
  ```bash
  pip install requests beautifulsoup4
  ```
- Enable JavaScript from Apple Events in Chrome: **View** → **Developer** → **Allow JavaScript from Apple Events**

### Optional: Qwen AI API Key

- Get from https://modelstudio.console.alibabacloud.com/ap-southeast-1#/api-key
- Add to `config.json` under `qwen_api_key`
- If not set, system uses template-based content generation

---

## License

Personal use only. Do not redistribute.