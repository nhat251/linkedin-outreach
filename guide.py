#!/usr/bin/env python3
"""
UCTalent Bounty Outreach - Step-by-Step Guide
Interactive wizard that guides you through the entire process.
Tracks job progress so you can work on one job per day.
"""

import os
import sys
import io
import json
import glob
import time
import urllib.parse
import subprocess
import re

# Content style system
from content_styles import get_style, list_styles, STYLES, DEFAULT_STYLE, choose_style_interactive

# XLSX storage
from xlsx_utils import read_xlsx, write_xlsx, clear_xlsx, get_xlsx_path

# Windows compatibility: Chrome automation via CDP
from chrome_utils import (
    ensure_chrome_debugging, is_chrome_running,
    open_url_in_tab, navigate_to_url, execute_js,
    run_applescript, go_back, get_clipboard, set_clipboard,
    list_tabs, new_tab, activate_tab, switch_to_last_tab
)


def normalize_linkedin_url(url):
    """Normalize a LinkedIn profile URL.

    - Drops the country subdomain (vn.linkedin.com → linkedin.com)
    - Drops locale/detail suffixes (/in/name/vi → /in/name)
    - Strips query string and trailing slash
    """
    if not url or 'linkedin.com' not in url:
        return url
    url = url.split('?')[0].rstrip('/')
    url = re.sub(r'\b[a-z]{2}\.linkedin\.com', 'linkedin.com', url)
    url = re.sub(r'(linkedin\.com/in/[^/]+)/(?:[a-z]{2}|details)(?:/.*)?$', r'\1', url)
    return url


def normalize_job_profiles(job):
    """Normalize LinkedIn profile URLs in a job"""
    if job.get('linkedin_profiles'):
        urls = [u.strip() for u in job['linkedin_profiles'].split(',') if u.strip()]
        normalized = [normalize_linkedin_url(u) for u in urls]
        job['linkedin_profiles'] = ','.join(normalized)
    return job


# ─── LinkedIn Composer ───────────────────────────────────────────────────────
# LinkedIn ships hashed CSS class names (e.g. "auyll5 auyguo auyhq4") and
# obfuscates them between deploys, so nothing here may depend on a class name.
# The composer is a separate page (/sharing/compose) whose editor is TipTap +
# ProseMirror now — an innerHTML assignment is silently ignored, the text has
# to go in through the real input pipeline.

LINKEDIN_FEED = "https://www.linkedin.com/feed/"
LINKEDIN_COMPOSE = "https://www.linkedin.com/sharing/compose"

# Wording note: the Vietnamese trigger used to be "Bắt đầu bài viết" and is
# now "Bắt đầu bài đăng". There is no aria-label on the trigger at all.
JS_CLICK_SHARE_BOX = """(function() {
    var want = ['Start a post', 'Bắt đầu bài đăng', 'Bắt đầu bài viết'];
    function norm(s) { return (s || '').replace(/\\s+/g, ' ').trim(); }
    var pool = Array.prototype.slice.call(
        document.querySelectorAll('[role="button"], button'));
    for (var i = 0; i < pool.length; i++) {
        var el = pool[i];
        var label = norm(el.getAttribute('aria-label')) || norm(el.innerText);
        if (want.indexOf(label) === -1) { continue; }
        // Several hidden responsive duplicates exist — only click a visible one
        var r = el.getBoundingClientRect();
        if (r.width < 40 || r.height < 20) { continue; }
        el.scrollIntoView({ block: 'center' });
        ['mousedown', 'mouseup', 'click'].forEach(function(type) {
            el.dispatchEvent(new MouseEvent(type, {
                bubbles: true, cancelable: true, view: window, button: 0
            }));
        });
        return 'clicked';
    }
    return 'not_found';
})()"""

# The editor lives in the main document on the compose page, but older
# layouts put it in the #interop-outlet shadow root — check both.
# A function *expression* so it can be embedded in either snippet below.
JS_FIND_EDITOR = """(function() {
    var host = document.querySelector('#interop-outlet');
    var roots = [document];
    if (host && host.shadowRoot) { roots.unshift(host.shadowRoot); }
    for (var r = 0; r < roots.length; r++) {
        var ed = roots[r].querySelector(
            '.ql-editor[contenteditable="true"], ' +
            'div[role="textbox"][contenteditable="true"], ' +
            '[contenteditable="true"]'
        );
        if (ed) { return ed; }
    }
    return null;
})"""

# Returns 'found' when an editor is present, '' otherwise (keeps _poll_js waiting)
JS_HAS_EDITOR = (
    "(function() {"
    "    var findEditor = " + JS_FIND_EDITOR + ";"
    "    return findEditor() ? 'found' : '';"
    "})()"
)

JS_FILL_EDITOR = (
    "(function() {\n"
    "    var findEditor = " + JS_FIND_EDITOR + ";\n"
    "    var ed = findEditor();\n"
    "    if (!ed) { return 'editor_not_found'; }\n"
    "    var text = __TEXT__;\n"
    "    ed.focus();\n"
    "    try {\n"
    "        document.execCommand('selectAll', false, null);\n"
    "        document.execCommand('delete', false, null);\n"
    "        if (document.execCommand('insertText', false, text)) { return 'filled'; }\n"
    "    } catch (e) {}\n"
    "    var html = text.split('\\n').map(function(p) {\n"
    "        return '<p>' + p.replace(/</g, '&lt;') + '</p>';\n"
    "    }).join('');\n"
    "    ed.innerHTML = html;\n"
    "    ed.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));\n"
    "    return 'filled';\n"
    "})()"
)


def _poll_js(check_js, timeout=25, interval=1.5):
    """Poll a JS snippet until it returns a non-empty value or we time out.

    Needed because the composer navigates to a new page, so execute_js can
    return None while the old document is being torn down.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = execute_js(check_js, timeout=10)
        except Exception:
            result = None
        if result and str(result).strip():
            return result
        time.sleep(interval)
    return None


def build_job_url(title, job_id):
    """Build the UCTalent job detail URL for a job."""
    encoded_title = title.replace(' ', '-').replace('/', '-')
    return f"https://uctalent.io/jobs/detail/{urllib.parse.quote(encoded_title)}.{job_id}"


# Columns step 3 fills in, in the order they are generated.
POST_FIELDS = [
    'linkedin_post', 'x_post', 'facebook_post', 'image_text',
    'linkedin_comment', 'x_comment', 'facebook_comment',
]


def generate_all_posts(job, referral_link, style_name, verbose=True):
    """Generate every piece of content for a job.

    Kept sequential on purpose. Firing the three posts at a ThreadPoolExecutor
    was measured and does not pay off: Gemini throttles concurrent requests, so
    three in parallel land in a 4-25s spread while the same three one after
    another came in at 9-10s. The apparent win in a single trial was noise from
    the provider, not real. All three calls are independent round-trips, so if
    this ever runs against an endpoint that does not throttle, parallelising the
    three _post calls is a one-line change.

    image_text and the three comments are template-only — they pick a random
    target audience and paste the referral link into a fixed string — so they
    cost nothing and were never worth batching.
    """
    from linkedin_outreach import (
        generate_linkedin_post, generate_x_post, generate_facebook_post,
        generate_image_text, generate_linkedin_comment, generate_x_comment,
        generate_facebook_comment, load_config
    )

    config = load_config()

    generated = {}
    for field, fn in [
        ('linkedin_post', lambda: generate_linkedin_post(job, referral_link, config, style_name)),
        ('x_post', lambda: generate_x_post(job, referral_link, config, style_name)),
        ('facebook_post', lambda: generate_facebook_post(job, referral_link, config, style_name)),
        ('image_text', lambda: generate_image_text(job, config)),
        ('linkedin_comment', lambda: generate_linkedin_comment(job, referral_link, config)),
        ('x_comment', lambda: generate_x_comment(job, referral_link, config)),
        ('facebook_comment', lambda: generate_facebook_comment(job, referral_link, config)),
    ]:
        try:
            generated[field] = fn()
        except Exception as e:
            print(f"  ⚠️  {field} failed: {e}")
            generated[field] = ''
        if verbose and field.endswith('_post'):
            print(f"    {'✅' if generated[field] else '⚠️ '} {field}: {len(generated[field])} chars")

    return generated


def apply_generated_posts(job, rows, generated):
    """Copy generated content onto the job row. Returns True if a row matched."""
    for r in rows:
        if r.get('title', '').strip().lower() == job['title'].strip().lower():
            for field in POST_FIELDS:
                if field in generated:
                    r[field] = generated[field]
            return True
    return False


def fetch_referral_link(job_url, job_title):
    """Open the job page and get its referral link automatically.

    Opens the page, clicks "Refer & Earn", waits for the modal, and reads the
    link (also putting it on the clipboard). Returns None if anything goes
    wrong, so the caller can fall back to asking the user.
    """
    try:
        from uctalent_referral import fetch_referral_link as _fetch
    except Exception as e:
        print(f"   ⚠️  Referral automation unavailable: {e}")
        return None

    try:
        open_url_in_tab(job_url)
        print(f"   ✅ Opened: {job_url}")
        link, info = _fetch(job_title=job_title, verbose=True)
    except Exception as e:
        print(f"   ⚠️  Could not fetch referral link: {e}")
        return None

    if not link:
        return None

    # A link attributed to a headhunter only pays 80% (uctalent.io's own
    # "net earning" tooltip). An internal referrer gets 100%, which is what the
    # /referral/quick_process/ links with utm_content=recruiter indicate.
    if info.get('kind') == 'legacy':
        print("   ⚠️  This is an older headhunter-style link (80% net).")
        print("      Re-fetch it after signing in on the internal account for 100%.")

    return link


def clear():
    os.system('clear' if os.name == 'posix' else 'cls')


def wait():
    input("\nPress Enter to continue...")


def check_chrome_running():
    """Check if Chrome is running (Windows via tasklist)"""
    return is_chrome_running()


def run_applescript(script, timeout=10):
    """BRIDGE: Replaces macOS osascript with Windows CDP equivalents.
    Delegates to chrome_utils.run_applescript() which interprets common patterns.
    """
    from chrome_utils import run_applescript as _bridge
    return _bridge(script, timeout=timeout)


def get_latest_xlsx():
    """Get the single persistent XLSX file path"""
    return get_xlsx_path()


def read_xlsx_jobs(xlsx_file):
    """Read jobs from XLSX with status tracking.
    Returns (list_of_dict_rows, fieldnames) — same interface as old read_csv_jobs.
    """
    if not xlsx_file or not os.path.exists(xlsx_file):
        return [], []
    
    rows, fieldnames = read_xlsx(xlsx_file)
    
    # Ensure required columns exist
    fieldnames_list = list(fieldnames) if fieldnames else []
    for col in ['status', 'connect_status', 'message_status']:
        if col not in fieldnames_list:
            fieldnames_list.append(col)
            for row in rows:
                row[col] = 'pending'
    
    if 'linkedin_profiles' not in fieldnames_list:
        fieldnames_list.append('linkedin_profiles')
        for row in rows:
            row['linkedin_profiles'] = ''
    
    # Normalize LinkedIn profile URLs (remove country subdomains)
    for row in rows:
        if row.get('linkedin_profiles'):
            urls = [u.strip() for u in row['linkedin_profiles'].split(',') if u.strip()]
            normalized = [normalize_linkedin_url(u) for u in urls]
            row['linkedin_profiles'] = ','.join(normalized)
    
    return rows, fieldnames_list


def save_xlsx_jobs(xlsx_file, rows, fieldnames):
    """Save jobs back to XLSX"""
    try:
        write_xlsx(xlsx_file, rows, fieldnames)
    except PermissionError:
        print(f"\n  ❌ Cannot write to '{xlsx_file}' — file is locked.")
        print("     Close it in Excel/editor if open, then try again.")
        wait()
        raise


def display_job_list(rows):
    """Display jobs with status and checkboxes"""
    print("=" * 120)
    print(f"  {'#':<4} {'Stt':<6} {'Connect':<10} {'Message':<10} {'Bounty':<14} {'Curr':<6} {'Title'}")
    print("=" * 120)
    
    for i, row in enumerate(rows, 1):
        status = row.get('status', 'pending')
        connect = row.get('connect_status', 'pending')
        message = row.get('message_status', 'pending')
        
        # Overall marker (short)
        if status == 'done':
            marker = "✅"
        elif status == 'posted':
            marker = "📢"
        elif connect == 'sent' or message == 'sent':
            marker = "🔄"
        else:
            marker = "⬜"
        
        # Format bounty as clean number
        raw_bounty = row.get('bounty', '0').strip()
        try:
            bounty_num = float(raw_bounty) if raw_bounty else 0
        except ValueError:
            bounty_num = 0
        currency = row.get('bounty_currency', 'USD').strip()
        if currency == 'VND':
            bounty_str = f"{bounty_num * 25000:,.0f}"
        else:
            bounty_str = f"${bounty_num:,.0f}"
        
        title = row.get('title', '')[:40]
        
        print(f"  {i:<4} {marker:<6} {connect:<10} {message:<10} {bounty_str:<14} {currency:<6} {title}")
    
    print("=" * 120)
    print()


def run_script(script_name, args=None):
    """Run a Python script (Windows: use 'python')"""
    cmd = ["python", script_name]
    if args:
        cmd.extend(args)
    
    if os.path.exists(script_name):
        subprocess.run(cmd)
    else:
        print(f"  ⚠️  Script not found: {script_name}")


def main():
    # Fix console encoding for Windows (emoji & Unicode support)
    if hasattr(sys.stdout, 'reconfigure'):
        try: sys.stdout.reconfigure(encoding='utf-8')
        except: pass
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    clear()
    print("=" * 70)
    print("  UCTalent Bounty Outreach - Step-by-Step Guide")
    print("=" * 70)
    print()
    print("This wizard guides you through the process.")
    print("Work on one job per day. Track progress here.")

    # ─── STEP 1: Open Chrome ────────────────────────────────────────────────
    clear()
    print("=" * 70)
    print("  STEP 1/3: Open Chrome (Profile 1)")
    print("=" * 70)
    print()
    print("  1. Open Google Chrome (Profile 1)")
    print("  2. Make sure you're signed in to your accounts")
    print("  3. Verify LinkedIn and UCTalent are accessible")
    print()
    
    # Reminder about personal config
    print("  📝 FIRST TIME? Update config.json with YOUR info:")
    print("     - name, role, linkedin_url, personal_story")
    print("     - See config.template.json for reference")
    print()
    
    if check_chrome_running():
        print("  ✅ Chrome is already running")
    else:
        print("  🔵 Opening Chrome with remote debugging port 9222...")
        print("  📂 Using C:\\chrome-debug (separate profile for automation)")
        try:
            # Windows path for Chrome
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
            ]
            chrome_exe = None
            for p in chrome_paths:
                if os.path.exists(p):
                    chrome_exe = p
                    break
            if chrome_exe:
                subprocess.Popen([chrome_exe, "--remote-debugging-port=9222", "--remote-allow-origins=*", '--user-data-dir="C:\\chrome-debug"'], shell=False)
            else:
                # Try launching via start command
                subprocess.run(["start", "chrome", "--remote-debugging-port=9222", "--remote-allow-origins=*", '--user-data-dir="C:\\chrome-debug"'], shell=True)
            time.sleep(3)
        except Exception as e:
            print(f"  ⚠️  Failed to open Chrome: {e}")
    
    # Check Chrome remote debugging
    print()
    if ensure_chrome_debugging():
        print("  ✅ Chrome remote debugging is active")
    else:
        print("  ⚠️  Chrome remote debugging NOT detected!")
        print("  📋 Run: start_chrome.bat")
        print("     (opens Chrome with --remote-debugging-port=9222 --remote-allow-origins=*)")
    
    print()
    print("  💡 Keep your normal tabs open — looks more natural")

    # ─── STEP 2: Fetch Jobs ─────────────────────────────────────────────────
    clear()
    print("=" * 70)
    print("  STEP 2/3: Fetch Jobs")
    print("=" * 70)
    print()
    print("  This will:")
    print("  • Fetch up to 25 bounty jobs from UCTalent")
    print("  • Skip jobs you've already processed")
    print("  • Generate Boolean search queries")
    print("  • Create outreach messages")
    print()
    
    confirm = input("Run now? (y/n): ").strip().lower()
    if confirm == 'y':
        print("\n🔄 Running linkedin_outreach.py...\n")
        run_script("linkedin_outreach.py")
    else:
        print("  Skipped.")
    
    # ─── STEP 3: Work on Individual Jobs ────────────────────────────────────
    while True:
        clear()
        print("=" * 70)
        print("  STEP 3/3: Work on Jobs (One at a Time)")
        print("=" * 70)
        print()
        
        xlsx_file = get_latest_xlsx()
        if not xlsx_file or not os.path.exists(xlsx_file):
            print("  ⚠️  No data file found. Run Step 2 first.")
            wait()
            break
        
        rows, fieldnames = read_xlsx_jobs(xlsx_file)
        if not rows:
            print("  ⚠️  No jobs found. Run Step 2 first.")
            wait()
            break
        
        display_job_list(rows)
        
        print("  Options:")
        print("  • Enter job number (1-{}) to work on it".format(len(rows)))
        print("  • 'd' + number = mark as DONE (e.g., 'd3')")
        print("  • 'c' = clear data + fetch fresh jobs")
        print("  • 'r' = refresh list")
        print("  • 'q' = quit")
        print()
        
        choice = input("Your choice: ").strip().lower()
        
        if choice == 'q':
            break
        elif choice == 'r':
            continue
        elif choice == 'c':
            confirm = input("\n  ⚠️  Clear ALL jobs and fetch fresh? (y/n): ").strip().lower()
            if confirm == 'y':
                from linkedin_outreach import CSV_FIELDNAMES
                clear_xlsx(xlsx_file, CSV_FIELDNAMES)
                print("\n  ✅ Data cleared! Now fetching fresh jobs...")
                time.sleep(1)
                run_script("linkedin_outreach.py")
            continue
        elif choice.startswith('d'):
            try:
                num = int(choice[1:])
                if 1 <= num <= len(rows):
                    rows[num-1]['status'] = 'done'
                    save_xlsx_jobs(xlsx_file, rows, fieldnames)
                    print(f"\n  ✅ Job {num} marked as DONE!")
                    time.sleep(1)
                else:
                    print("  Invalid job number.")
            except ValueError:
                print("  Invalid format. Use 'd' + number (e.g., 'd3')")
            wait()
        else:
            try:
                num = int(choice)
                if 1 <= num <= len(rows):
                    job = rows[num-1]
                    work_on_job_menu(num, job, xlsx_file, rows, fieldnames)
                else:
                    print("  Invalid job number.")
                    wait()
            except ValueError:
                print("  Invalid input.")
                wait()

    # ─── Session Summary ────────────────────────────────────────────────────
    clear()
    print("=" * 70)
    print("  SESSION SUMMARY")
    print("=" * 70)
    print()
    
    xlsx_file = get_latest_xlsx()
    if xlsx_file and os.path.exists(xlsx_file):
        rows, _ = read_xlsx_jobs(xlsx_file)
        done = sum(1 for r in rows if r.get('status') == 'done')
        posted = sum(1 for r in rows if r.get('status') == 'posted')
        connecting = sum(1 for r in rows if r.get('connect_status') in ['sent', 'ready_to_connect'])
        pending = sum(1 for r in rows if r.get('status') != 'done' and r.get('connect_status') not in ['sent', 'ready_to_connect'])
        
        print(f"  📁 File: {xlsx_file}")
        print(f"  ✅ Completed: {done}")
        print(f"  📢 Posted (waiting on connects): {posted}")
        print(f"  🔄 Connecting/Messaging: {connecting}")
        print(f"  ⬜ Still pending: {pending}")
        print()
        print("  Run this guide again anytime:")
        print("  python guide.py")
        print()


def work_on_job_menu(num, job, xlsx_file, rows, fieldnames):
    """Show menu for working on one job"""
    # Auto-run steps 1, 2, 3 when entering (if not done)
    print("\n" + "=" * 70)
    print("  Auto-preparing job...")
    print("=" * 70)
    
    # Determine if we have a valid referral link
    referral_link = job.get('referral_link', '')
    has_link = referral_link and referral_link not in ['', '[MANUAL_PASTE]', '[REFERRAL_LINK]', '[NO_LINK]']
    clean_link = referral_link if has_link else ''
    
# Step 1: Get referral link (opens job page) - ONLY if no link
    if not has_link:
        print("\n1️⃣  Getting referral link...")
        job_id = job.get('id', '')
        title = job.get('title', '')
        if job_id and title:
            job_url = build_job_url(title, job_id)
            link = fetch_referral_link(job_url, title)
            if link:
                referral_link = link
                has_link = True
                clean_link = link
                job['referral_link'] = link
                for r in rows:
                    if r.get('title', '').strip().lower() == title.strip().lower():
                        r['referral_link'] = link
                        break
                print("   ✅ Referral link saved!")
            else:
                link = input("   Paste the referral link (or press Enter to skip): ").strip()
                if link:
                    referral_link = link
                    has_link = True
                    clean_link = link
                    job['referral_link'] = link
                    for r in rows:
                        if r.get('title', '').strip().lower() == title.strip().lower():
                            r['referral_link'] = link
                            break
                    print("   ✅ Referral link saved!")
                else:
                    print("   ⏭️  Skipped.")
    
    # Step 2: Generate outreach message (always, if not exists)
    if not job.get('outreach_message'):
        print("\n2️⃣  Generating outreach message...")
        # Let user pick style for the message
        outreach_style = choose_style_interactive("outreach message style")
        sys.path.insert(0, '.')
        try:
            from linkedin_outreach import generate_outreach_message, fetch_job_description, load_config
            config = load_config()
            job_id = job.get('id', '')
            job_title = job.get('title', '')
            if job_id:
                desc = fetch_job_description(job_id, job_title)
            else:
                desc = job.get('description', 'Description not available')
            tags = job.get('tags', '').split(',') if job.get('tags') else []
            message = generate_outreach_message(job_title, desc, job.get('location', ''), job.get('salary', ''), tags, clean_link, config.get('name'), outreach_style)
            job['outreach_message'] = message
            print(f"   ✅ Generated! (Style: {get_style(outreach_style)['name']})")
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
    
    # Step 3: Generate social posts (if has link but no posts)
    has_posts = job.get('linkedin_post') and job.get('linkedin_post') not in ['', 'Not generated']
    if has_link and not has_posts:
        print("\n3️⃣  Generating social posts...")
        post_style = choose_style_interactive("social post style")
        sys.path.insert(0, '.')
        try:
            generated = generate_all_posts(job, clean_link, post_style)
            for field in POST_FIELDS:
                if field in generated:
                    job[field] = generated[field]
            apply_generated_posts(job, rows, generated)
            print(f"   ✅ Generated! (Style: {get_style(post_style)['name']})")
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
    
    # Save after auto-preparation
    save_xlsx_jobs(xlsx_file, rows, fieldnames)
    
    # Now show menu
    while True:
        clear()
        raw_bounty = job.get('bounty', '0').strip()
        try:
            bounty_num = float(raw_bounty) if raw_bounty else 0
        except ValueError:
            bounty_num = 0
        currency = job.get('bounty_currency', 'USD').strip()
        if currency == 'VND':
            bounty_str = f"{bounty_num * 25000:,.0f} VND"
        else:
            bounty_str = f"${bounty_num:,.0f}"
        print("=" * 70)
        print(f"  Job #{num}: {job['title'][:50]}")
        print(f"  Bounty: {bounty_str} | Location: {job.get('location', 'N/A')}")
        print("=" * 70)
        print()
        
        # Show current status
        has_link = job.get('referral_link') and job['referral_link'] not in ['', '[MANUAL_PASTE]', '[REFERRAL_LINK]', '[NO_LINK]']
        has_posts = job.get('linkedin_post') and job['linkedin_post'] not in ['', 'Not generated']
        has_profiles = job.get('linkedin_profiles') and job['linkedin_profiles']
        
        print(f"  Status:")
        print(f"    🔗 Referral Link: {'✅' if has_link else '❌ (do step 1)'}")
        print(f"    📝 Outreach Msg:  {'✅' if job.get('outreach_message') else '❌ (do step 2)'}")
        print(f"    📢 Social Posts:  {'✅' if has_posts else '❌ (do step 3)'}")
        print(f"    👥 LinkedIn Profs: {'✅' if has_profiles else '❌ (do step 5)'}")
        print()
        
        print("  Options:")
        print("  1. 🔗 Get Referral Link")
        print("  2. 📝 Generate Outreach Message")
        print("  3. 📢 Generate Social Posts (LinkedIn, X, Facebook)")
        print("  4. 🔍 Search (opens Boolean query)")
        print("  5. 👥 Extract Profiles (run search → save URLs)")
        print("  6. 👤 Open Saved Profiles (in Chrome tabs)")
        print("  7. 🤝 Outreach (send connection requests)")
        print("  8. 📤 View Posts (preview + draft in Chrome)")
        print("  9. ✅ Done (mark complete)")
        print("  10. 🔙 Back to job list")
        print()
        
        choice = input("Select option (1-10): ").strip()
        
        if choice == '1':
            get_referral_link(num, job, xlsx_file, rows, fieldnames)
        elif choice == '2':
            generate_outreach_for_job(num, job, xlsx_file, rows, fieldnames)
        elif choice == '3':
            generate_posts_for_job(num, job, xlsx_file, rows, fieldnames)
        elif choice == '4':
            open_search(num, job, xlsx_file, rows, fieldnames)
        elif choice == '5':
            extract_profiles(num, job, xlsx_file, rows, fieldnames)
        elif choice == '6':
            open_saved_profiles(num, job, xlsx_file, rows, fieldnames)
        elif choice == '7':
            send_outreach(num, job, xlsx_file, rows, fieldnames)
        elif choice == '8':
            view_posts(num, job, xlsx_file, rows, fieldnames)
        elif choice == '9':
            job['status'] = 'done'
            save_xlsx_jobs(xlsx_file, rows, fieldnames)
            break
        elif choice == '10':
            break
        else:
            print("  Invalid choice.")
            time.sleep(1)


def get_referral_link(num, job, xlsx_file, rows, fieldnames):
    """Open the job page, click Refer & Earn, and save the link"""
    clear()
    print("=" * 70)
    print(f"  Job #{num}: Get Referral Link")
    print("=" * 70)
    print()

    job_id = job.get('id', '')
    title = job.get('title', '')

    if not job_id:
        print("  ⚠️  No job ID in file.")
        print("  Please run STEP 2 (Fetch Jobs) to get the job ID.")
        input("\nPress Enter to continue...")
        return

    if not title:
        print("  ⚠️  No job title found.")
        input("\nPress Enter to continue...")
        return

    job_url = build_job_url(title, job_id)
    link = fetch_referral_link(job_url, title)

    if not link:
        # Automation failed — fall back to the manual flow
        print()
        print("  📋 Fall back to manual: click 'Refer & Earn' → 'Copy Link'")
        print("     (or press Enter to skip)")
        print()
        link = input("  Referral link: ").strip()

    if link:
        # Update job in memory
        job['referral_link'] = link

        # Update the row in the rows list
        for r in rows:
            if r.get('title', '').strip().lower() == job.get('title', '').strip().lower():
                r['referral_link'] = link
                break

        # Save to XLSX
        save_xlsx_jobs(xlsx_file, rows, fieldnames)
        print(f"\n  ✅ Referral link saved!")
    else:
        print("\n  ⏭️  Skipped.")



def generate_outreach_for_job(num, job, xlsx_file, rows, fieldnames):
    """Generate outreach message for selected job"""
    clear()
    print("=" * 70)
    print(f"  Job #{num}: Generate Outreach Message")
    print("=" * 70)
    print()
    
    # Let user pick style
    style_name = choose_style_interactive("outreach message style")
    selected_style = get_style(style_name)
    print(f"\n  🎨 Using style: {selected_style['name']} — {selected_style['description']}")
    print()
    
    sys.path.insert(0, '.')
    try:
        from linkedin_outreach import (
            load_config, clean_content,
            generate_with_nvidia, generate_with_qwen, generate_with_gemini,
            generate_outreach_message, fetch_job_description
        )
        
        config = load_config()
        message = None
        
        # Try AI first (NVIDIA → Qwen → Gemini)
        if config.get('use_nvidia', False):
            message = generate_with_nvidia(job, job.get('referral_link', ''), config, 'outreach_message', style_name)
        if not message and config.get('use_qwen', False):
            message = generate_with_qwen(job, job.get('referral_link', ''), config, 'outreach_message', style_name)
        if not message and config.get('use_gemini', False):
            message = generate_with_gemini(job, job.get('referral_link', ''), config, 'outreach_message', style_name)
        
        # Fallback to template if AI not available
        if not message:
            desc = fetch_job_description(job['id'], job['title'])
            tags = job.get('tags', '').split(',') if job.get('tags') else []
            referral_link = job.get('referral_link', '')
            clean_link = referral_link if referral_link and referral_link not in ['', '[MANUAL_PASTE]', '[REFERRAL_LINK]', '[NO_LINK]'] else ''
            message = generate_outreach_message(job['title'], desc, job.get('location', ''), job.get('salary', ''), tags, clean_link, config.get('name'), style_name)
        else:
            message = clean_content(message.strip())
        
        # Update job
        for r in rows:
            if r.get('title', '').strip().lower() == job['title'].strip().lower():
                r['outreach_message'] = message
                break
        
        save_xlsx_jobs(xlsx_file, rows, fieldnames)
        print(f"  ✅ Outreach message generated! (Style: {selected_style['name']})")
        print()
        print("  " + "-" * 60)
        for line in message.split('\n'):
            print(f"  {line}")
        print("  " + "-" * 60)
        print()
        print("  💡 Not happy? Run option 2 again to regenerate with a different style.")
    except Exception as e:
        print(f"  ⚠️  Error: {e}")


def generate_posts_for_job(num, job, xlsx_file, rows, fieldnames):
    """Generate social posts for selected job"""
    clear()
    print("=" * 70)
    print(f"  Job #{num}: Generate Social Posts")
    print("=" * 70)
    print()
    
    referral_link = job.get('referral_link', '')
    if not referral_link or referral_link in ['', '[MANUAL_PASTE]', '[REFERRAL_LINK]', '[NO_LINK]']:
        print("  ⚠️  No referral link found. Do step 1 first!")
        input("\nPress Enter to continue...")
        return
    
    # Let user pick style
    style_name = choose_style_interactive("social post style")
    selected_style = get_style(style_name)
    print(f"\n  🎨 Using style: {selected_style['name']} — {selected_style['description']}")
    print()
    
    sys.path.insert(0, '.')
    try:
        generated = generate_all_posts(job, referral_link, style_name)

        if not apply_generated_posts(job, rows, generated):
            print("  ⚠️  Could not match this job's title in the sheet — nothing saved.")

        save_xlsx_jobs(xlsx_file, rows, fieldnames)
        print(f"  ✅ Social posts generated! (Style: {selected_style['name']})")
        print(f"    📱 LinkedIn post: {len(generated.get('linkedin_post', ''))} chars")
        print(f"    🐦 X/Twitter post: {len(generated.get('x_post', ''))} chars")
        print(f"    📘 Facebook post: {len(generated.get('facebook_post', ''))} chars")
    except Exception as e:
        print(f"  ⚠️  Error: {e}")


def open_search(num, job, xlsx_file, rows, fieldnames):
    """Open Boolean search in Chrome"""
    clear()
    print("=" * 70)
    print(f"  Job #{num}: Open Boolean Search")
    print("=" * 70)
    print()
    
    query = job.get('boolean_query', '')
    if not query:
        print("  ⚠️  No boolean_query found for this job.")
        print("  Run linkedin_outreach.py to generate queries.")
        input("\nPress Enter to continue...")
        return
    
    print(f"  Query: {query[:100]}...")
    print()
    
    job['connect_status'] = 'searching'
    save_xlsx_jobs(xlsx_file, rows, fieldnames)
    
    google_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    open_url_in_tab(google_url)
    print("  ✅ Search opened in new Chrome tab")
    print()
    print("  Next step: Browse results, then run option 5 to extract LinkedIn profiles")


def extract_profiles(num, job, xlsx_file, rows, fieldnames):
    """Extract LinkedIn profiles from search"""
    clear()
    print("=" * 70)
    print(f"  Job #{num}: Extract LinkedIn Profiles")
    print("=" * 70)
    print()
    print("  1. Browse Google search results in Chrome")
    print("  2. Come back here to run extraction")
    print()
    
    job_title = job.get('title', '')
    confirm = input("Run extraction? (y/n): ").strip().lower()
    if confirm == 'y':
        # Pass job title as argument so it saves to correct job
        run_script("open_profiles.py", [job_title])
        
        # Reload XLSX to get profiles
        xlsx_file = get_latest_xlsx()
        if xlsx_file and os.path.exists(xlsx_file):
            all_rows, _ = read_xlsx(xlsx_file)
            for r in all_rows:
                if r.get('title', '').strip().lower() == job['title'].strip().lower():
                    profiles = r.get('linkedin_profiles', '')
                    if profiles:
                        job['linkedin_profiles'] = profiles
                    break
        
        job['connect_status'] = 'ready_to_connect'
        save_xlsx_jobs(xlsx_file, rows, fieldnames)
        print("  ✅ Profiles extracted!")


def open_saved_profiles(num, job, xlsx_file, rows, fieldnames):
    """Open all saved LinkedIn profiles in Chrome tabs"""
    clear()
    print("=" * 70)
    print(f"  Job #{num}: Open Saved Profiles")
    print("=" * 70)
    print()
    
    profiles = job.get('linkedin_profiles', '')
    if not profiles:
        print("  ⚠️  No saved profiles found. Do step 5 first.")
        input("\nPress Enter to continue...")
        return
    
    profile_list = [normalize_linkedin_url(p.strip()) for p in profiles.split(',') if p.strip()]
    
    if not profile_list:
        print("  ⚠️  No valid profile URLs found.")
        input("\nPress Enter to continue...")
        return
    
    print(f"  👤 Found {len(profile_list)} saved profiles")
    print()
    
    confirm = input(f"  Open all {len(profile_list)} profiles in Chrome tabs? (y/n): ").strip().lower()
    if confirm != 'y':
        print("  Skipped.")
        input("\nPress Enter to continue...")
        return
    
    print()
    for i, url in enumerate(profile_list, 1):
        try:
            open_url_in_tab(url)
            print(f"  {i}. ✅ Opened: {url[:60]}...")
            time.sleep(0.5)
        except Exception as e:
            print(f"  {i}. ⚠️  Failed to open: {url[:60]}... ({e})")
    
    print()
    print(f"  ✅ All {len(profile_list)} profiles opened in Chrome tabs!")
    print("  💡 Keep them open, visit each one to send connection requests")
    input("\nPress Enter to continue...")


def send_outreach(num, job, xlsx_file, rows, fieldnames):
    """Send connection requests"""
    clear()
    print("=" * 70)
    print(f"  Job #{num}: Send Connection Requests")
    print("=" * 70)
    print()
    
    profiles = job.get('linkedin_profiles', '')
    if profiles:
        profile_list = [normalize_linkedin_url(p.strip()) for p in profiles.split(',') if p.strip()]
        print(f"  📋 Profiles ({len(profile_list)} found):")
        for p in profile_list[:5]:
            print(f"     - {p[:60]}...")
    else:
        print("  ⚠️  No profiles found. Do step 5 first.")
        return
    
    # Show current message
    msg = job.get('outreach_message', '')
    if msg:
        print()
        print("  📝 Message:")
        print("  " + "=" * 66)
        for line in msg.split('\n'):
            print(f"  {line}")
        print("  " + "=" * 66)
        print()
    else:
        print("  ⚠️  No message yet. Run option 2 first.")
        return
    
    print("  ⚠️  LIMITS: Max 20-25/day, wait 2-3 min between each")
    print()
    confirm = input("  Mark as sent? (y/n): ").strip().lower()
    if confirm == 'y':
        job['connect_status'] = 'sent'
        save_xlsx_jobs(xlsx_file, rows, fieldnames)
        print("  ✅ Marked as sent!")


def view_posts(num, job, xlsx_file, rows, fieldnames):
    """View generated posts and open draft tabs"""
    clear()
    print("=" * 70)
    print(f"  Job #{num}: View Generated Posts")
    print("=" * 70)
    print()
    
    linkedin_post = job.get('linkedin_post', '')
    if not linkedin_post or linkedin_post == 'Not generated':
        print("  ⚠️  No posts generated. Do step 3 first.")
        input("Press Enter to continue...")
        return
    
    print("📱 LINKEDIN POST:")
    print("=" * 66)
    print(linkedin_post)
    print("=" * 66)
    print()
    
    print("🐦 X/TWITTER POST:")
    print("=" * 66)
    print(job.get('x_post', ''))
    print("=" * 66)
    print()
    
    print("💬 LINKEDIN COMMENT (with referral link):")
    print("-" * 60)
    print(job.get('linkedin_comment', ''))
    print()
    
    confirm = input("Open draft tabs in Chrome? (y/n): ").strip().lower()
    if confirm == 'y':
        referral_link = job.get('referral_link', '')

        # Open LinkedIn feed, then click the share box.
        # LinkedIn obfuscates its CSS class names, so we match on role/text
        # instead of .share-box-v2__trigger, and the Vietnamese wording of the
        # trigger changed from "Bắt đầu bài viết" to "Bắt đầu bài đăng".
        open_url_in_tab(LINKEDIN_FEED)
        print("  ⏳ Waiting for LinkedIn to load...")
        time.sleep(3)

        fill_js = JS_FILL_EDITOR.replace('__TEXT__', json.dumps(linkedin_post))

        # Reuse the composer if it is already open (retry / previous attempt)
        if _poll_js(JS_HAS_EDITOR, timeout=3):
            print("  ℹ️  Composer already open. Filling text...")
            status = execute_js(fill_js, timeout=25)
        else:
            status = execute_js(JS_CLICK_SHARE_BOX, timeout=20)
            if status != 'clicked':
                print("  ⚠️  Could not find the share box — opening composer directly.")
                navigate_to_url(LINKEDIN_COMPOSE)
            else:
                print("  ✅ Compose box opened. Filling text...")

            # The share box is a separate page now (/sharing/compose), so wait
            # for it to load and hydrate before touching the editor.
            if not _poll_js(JS_HAS_EDITOR, timeout=30):
                status = 'composer_missing'
            else:
                status = execute_js(fill_js, timeout=25)

        if status == 'filled':
            print("  ✅ Post text filled! Review and publish.")
        elif status == 'composer_missing':
            print("  ⚠️  Composer did not open. Paste manually.")
        else:
            print("  ⚠️  Could not fill the editor. Paste manually.")

        # Auto-open X with pre-filled text
        x_post = job.get('x_post', '')
        x_text = x_post if x_post else linkedin_post
        x_url = f"https://twitter.com/compose/tweet?text={urllib.parse.quote(x_text[:280])}"
        open_url_in_tab(x_url)
        print("  ✅ X/Twitter draft ready!")
        
        print("  💡 Switch to each tab, review, and Post.")
        print()
        print("  ──── 📋 Referral Link ────")
        print(f"  🔗 {referral_link}")
        print("  ──────────────────────────")
        print()
        input("  Press Enter to return to menu...")


if __name__ == "__main__":
    main()
