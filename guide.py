#!/usr/bin/env python3
"""
UCTalent Bounty Outreach - Step-by-Step Guide
Interactive wizard that guides you through the entire process.
Tracks job progress so you can work on one job per day.
"""

import os
import sys
import io
import glob
import time
import csv
import urllib.parse
import subprocess
import re

# Windows compatibility: Chrome automation via CDP
from chrome_utils import (
    ensure_chrome_debugging, is_chrome_running,
    open_url_in_tab, navigate_to_url, execute_js,
    run_applescript, go_back, get_clipboard, set_clipboard,
    list_tabs, new_tab, activate_tab, switch_to_last_tab
)


def normalize_linkedin_url(url):
    """Remove country subdomain from LinkedIn URLs"""
    if not url or 'linkedin.com/in/' not in url:
        return url
    return re.sub(r'(?!ww)[a-z]{2}\.linkedin\.com', 'linkedin.com', url)


def normalize_job_profiles(job):
    """Normalize LinkedIn profile URLs in a job"""
    if job.get('linkedin_profiles'):
        urls = [u.strip() for u in job['linkedin_profiles'].split(',') if u.strip()]
        normalized = [normalize_linkedin_url(u) for u in urls]
        job['linkedin_profiles'] = ','.join(normalized)
    return job


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


def get_latest_csv():
    """Get the single persistent CSV file"""
    csv_file = 'uctalent_jobs.csv'
    if os.path.exists(csv_file):
        return csv_file
    return None


def read_csv_jobs(csv_file):
    """Read jobs from CSV with status tracking"""
    if not csv_file or not os.path.exists(csv_file):
        return [], []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames
    
    # Add status columns if not exist
    for col in ['status', 'connect_status', 'message_status']:
        if col not in fieldnames:
            fieldnames.append(col)
            for row in rows:
                row[col] = 'pending'
    
    # Add linkedin_profiles column if not exist
    if 'linkedin_profiles' not in fieldnames:
        fieldnames.append('linkedin_profiles')
        for row in rows:
            row['linkedin_profiles'] = ''
    
    # Normalize LinkedIn profile URLs (remove country subdomains)
    for row in rows:
        if row.get('linkedin_profiles'):
            urls = [u.strip() for u in row['linkedin_profiles'].split(',') if u.strip()]
            normalized = [normalize_linkedin_url(u) for u in urls]
            row['linkedin_profiles'] = ','.join(normalized)
    
    return rows, fieldnames


def save_csv_jobs(csv_file, rows, fieldnames):
    """Save jobs back to CSV"""
    try:
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except PermissionError:
        print(f"\n  ❌ Cannot write to '{csv_file}' — file is locked.")
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
    wait()

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
    
    wait()

    # ─── STEP 3: Work on Individual Jobs ────────────────────────────────────
    while True:
        clear()
        print("=" * 70)
        print("  STEP 3/3: Work on Jobs (One at a Time)")
        print("=" * 70)
        print()
        
        csv_file = get_latest_csv()
        if not csv_file:
            print("  ⚠️  No CSV file found. Run Step 2 first.")
            wait()
            break
        
        rows, fieldnames = read_csv_jobs(csv_file)
        if not rows:
            print("  ⚠️  No jobs found. Run Step 2 first.")
            wait()
            break
        
        display_job_list(rows)
        
        print("  Options:")
        print("  • Enter job number (1-{}) to work on it".format(len(rows)))
        print("  • 'd' + number = mark as DONE (e.g., 'd3')")
        print("  • 'c' = clear CSV + fetch fresh data")
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
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                print("\n  ✅ CSV cleared! Now fetching fresh jobs...")
                time.sleep(1)
                run_script("linkedin_outreach.py")
            continue
        elif choice.startswith('d'):
            try:
                num = int(choice[1:])
                if 1 <= num <= len(rows):
                    rows[num-1]['status'] = 'done'
                    save_csv_jobs(csv_file, rows, fieldnames)
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
                    work_on_job_menu(num, job, csv_file, rows, fieldnames)
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
    
    csv_file = get_latest_csv()
    if csv_file:
        rows, _ = read_csv_jobs(csv_file)
        done = sum(1 for r in rows if r.get('status') == 'done')
        posted = sum(1 for r in rows if r.get('status') == 'posted')
        connecting = sum(1 for r in rows if r.get('connect_status') in ['sent', 'ready_to_connect'])
        pending = sum(1 for r in rows if r.get('status') != 'done' and r.get('connect_status') not in ['sent', 'ready_to_connect'])
        
        print(f"  📁 CSV: {csv_file}")
        print(f"  ✅ Completed: {done}")
        print(f"  📢 Posted (waiting on connects): {posted}")
        print(f"  🔄 Connecting/Messaging: {connecting}")
        print(f"  ⬜ Still pending: {pending}")
        print()
        print("  Run this guide again anytime:")
        print("  python guide.py")
        print()


def work_on_job_menu(num, job, csv_file, rows, fieldnames):
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
        print("\n1️⃣  Opening job page for referral link...")
        job_id = job.get('id', '')
        title = job.get('title', '')
        if job_id and title:
            encoded_title = title.replace(' ', '-').replace('/', '-')
            job_url = f"https://uctalent.io/jobs/detail/{urllib.parse.quote(encoded_title)}.{job_id}"
            open_url_in_tab(job_url)
            print(f"   ✅ Opened: {job_url}")
            print("\n   📋 Click 'Refer & Earn' → 'COPY LINK', then paste below:")
            print("     (or press Enter to skip)")
            link = input("   Referral link: ").strip()
            if link:
                referral_link = link
                has_link = True
                clean_link = link
                job['referral_link'] = link
                for r in rows:
                    if r.get('title', '').strip().lower() == job.get('title', '').strip().lower():
                        r['referral_link'] = link
                        break
                print("   ✅ Referral link saved!")
            else:
                print("   ⏭️  Skipped.")
    
    # Step 2: Generate outreach message (always, if not exists)
    if not job.get('outreach_message'):
        print("\n2️⃣  Generating outreach message...")
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
            message = generate_outreach_message(job_title, desc, job.get('location', ''), job.get('salary', ''), tags, clean_link, config.get('name'))
            job['outreach_message'] = message
            print("   ✅ Generated!")
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
    
    # Step 3: Generate social posts (if has link but no posts)
    has_posts = job.get('linkedin_post') and job.get('linkedin_post') not in ['', 'Not generated']
    if has_link and not has_posts:
        print("\n3️⃣  Generating social posts...")
        sys.path.insert(0, '.')
        try:
            from linkedin_outreach import (
                generate_linkedin_post, generate_x_post, generate_facebook_post,
                generate_image_text, generate_linkedin_comment, generate_x_comment,
                generate_facebook_comment, load_config
            )
            config = load_config()
            linkedin_post = generate_linkedin_post(job, clean_link, config)
            x_post = generate_x_post(job, clean_link, config)
            facebook_post = generate_facebook_post(job, clean_link, config)
            image_text = generate_image_text(job, config)
            linkedin_comment = generate_linkedin_comment(job, clean_link, config)
            x_comment = generate_x_comment(job, clean_link, config)
            facebook_comment = generate_facebook_comment(job, clean_link, config)
            job['linkedin_post'] = linkedin_post
            job['x_post'] = x_post
            job['facebook_post'] = facebook_post
            job['image_text'] = image_text
            job['linkedin_comment'] = linkedin_comment
            job['x_comment'] = x_comment
            job['facebook_comment'] = facebook_comment
            print("   ✅ Generated!")
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
    
    # Save after auto-preparation
    save_csv_jobs(csv_file, rows, fieldnames)
    input("\nPress Enter to continue to menu...")
    
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
        print(f"    👥 LinkedIn Profs: {'✅' if has_profiles else '❌ (do step 4)'}")
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
            get_referral_link(num, job, csv_file, rows, fieldnames)
        elif choice == '2':
            generate_outreach_for_job(num, job, csv_file, rows, fieldnames)
        elif choice == '3':
            generate_posts_for_job(num, job, csv_file, rows, fieldnames)
        elif choice == '4':
            open_search(num, job, csv_file, rows, fieldnames)
        elif choice == '5':
            extract_profiles(num, job, csv_file, rows, fieldnames)
        elif choice == '6':
            open_saved_profiles(num, job, csv_file, rows, fieldnames)
        elif choice == '7':
            send_outreach(num, job, csv_file, rows, fieldnames)
        elif choice == '8':
            view_posts(num, job, csv_file, rows, fieldnames)
        elif choice == '9':
            job['status'] = 'done'
            save_csv_jobs(csv_file, rows, fieldnames)
            break
        elif choice == '10':
            break
        else:
            print("  Invalid choice.")
            time.sleep(1)


def get_referral_link(num, job, csv_file, rows, fieldnames):
    """Open job page, then ask user to paste referral link in terminal"""
    clear()
    print("=" * 70)
    print(f"  Job #{num}: Get Referral Link")
    print("=" * 70)
    print()
    
    job_id = job.get('id', '')
    title = job.get('title', '')
    
    if not job_id:
        print("  ⚠️  No job ID in CSV.")
        print("  Please run STEP 2 (Fetch Jobs) to get the job ID.")
        input("\nPress Enter to continue...")
        return
    
    if title:
        encoded_title = title.replace(' ', '-').replace('/', '-')
        job_url = f"https://uctalent.io/jobs/detail/{urllib.parse.quote(encoded_title)}.{job_id}"
        open_url_in_tab(job_url)
        print(f"  ✅ Opened: {job_url}")
    else:
        print("  ⚠️  No job title found.")
    
    print()
    print("  1. Click 'Refer & Earn' button (right sidebar)")
    print("  2. Click 'COPY LINK' button")
    print()
    print("  📋 Then paste the link below:")
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
        
        # Save to CSV
        save_csv_jobs(csv_file, rows, fieldnames)
        print(f"\n  ✅ Referral link saved to CSV!")


def generate_outreach_for_job(num, job, csv_file, rows, fieldnames):
    """Generate outreach message for selected job"""
    clear()
    print("=" * 70)
    print(f"  Job #{num}: Generate Outreach Message")
    print("=" * 70)
    print()
    
    # Import and run generation
    sys.path.insert(0, '.')
    try:
        from linkedin_outreach import generate_outreach_message, fetch_job_description, load_config
        
        config = load_config()
        desc = fetch_job_description(job['id'], job['title'])
        tags = job.get('tags', '').split(',') if job.get('tags') else []
        referral_link = job.get('referral_link', '')
        clean_link = referral_link if referral_link and referral_link not in ['', '[MANUAL_PASTE]', '[REFERRAL_LINK]', '[NO_LINK]'] else ''
        
        message = generate_outreach_message(job['title'], desc, job.get('location', ''), job.get('salary', ''), tags, clean_link, config.get('name'))
        
        # Update job
        for r in rows:
            if r.get('title', '').strip().lower() == job['title'].strip().lower():
                r['outreach_message'] = message
                break
        
        save_csv_jobs(csv_file, rows, fieldnames)
        print("  ✅ Outreach message generated!")
        print()
        print("  " + "-" * 60)
        print(message[:300] + "..." if len(message) > 300 else message)
        print("  " + "-" * 60)
    except Exception as e:
        print(f"  ⚠️  Error: {e}")


def generate_posts_for_job(num, job, csv_file, rows, fieldnames):
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
    
    sys.path.insert(0, '.')
    try:
        from linkedin_outreach import (
            generate_linkedin_post, generate_x_post, generate_facebook_post,
            generate_image_text, generate_linkedin_comment, generate_x_comment,
            generate_facebook_comment, load_config
        )
        
        config = load_config()
        
        linkedin_post = generate_linkedin_post(job, referral_link, config)
        x_post = generate_x_post(job, referral_link, config)
        facebook_post = generate_facebook_post(job, referral_link, config)
        image_text = generate_image_text(job, config)
        linkedin_comment = generate_linkedin_comment(job, referral_link, config)
        x_comment = generate_x_comment(job, referral_link, config)
        facebook_comment = generate_facebook_comment(job, referral_link, config)
        
        # Update job
        for r in rows:
            if r.get('title', '').strip().lower() == job['title'].strip().lower():
                r['linkedin_post'] = linkedin_post
                r['x_post'] = x_post
                r['facebook_post'] = facebook_post
                r['image_text'] = image_text
                r['linkedin_comment'] = linkedin_comment
                r['x_comment'] = x_comment
                r['facebook_comment'] = facebook_comment
                break
        
        save_csv_jobs(csv_file, rows, fieldnames)
        print("  ✅ Social posts generated!")
        print(f"    📱 LinkedIn post: {len(linkedin_post)} chars")
        print(f"    🐦 X/Twitter post: {len(x_post)} chars")
        print(f"    📘 Facebook post: {len(facebook_post)} chars")
    except Exception as e:
        print(f"  ⚠️  Error: {e}")


def open_search(num, job, csv_file, rows, fieldnames):
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
    save_csv_jobs(csv_file, rows, fieldnames)
    
    google_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    open_url_in_tab(google_url)
    print("  ✅ Search opened in new Chrome tab")
    print()
    print("  Next step: Browse results, then run option 5 to extract LinkedIn profiles")
    input("\nPress Enter to continue...")


def extract_profiles(num, job, csv_file, rows, fieldnames):
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
        
        # Reload CSV to get profiles
        csv_file = get_latest_csv()
        if csv_file and os.path.exists(csv_file):
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                all_rows = list(reader)
            for r in all_rows:
                if r.get('title', '').strip().lower() == job['title'].strip().lower():
                    profiles = r.get('linkedin_profiles', '')
                    if profiles:
                        job['linkedin_profiles'] = profiles
                    break
        
        job['connect_status'] = 'ready_to_connect'
        save_csv_jobs(csv_file, rows, fieldnames)
        print("  ✅ Profiles extracted!")


def open_saved_profiles(num, job, csv_file, rows, fieldnames):
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


def send_outreach(num, job, csv_file, rows, fieldnames):
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
    
    print()
    msg = job.get('outreach_message', 'No message')
    print("  📝 Full Message (copy from below):")
    print("  " + "=" * 66)
    for line in msg.split('\n'):
        print(f"  {line}")
    print("  " + "=" * 66)
    print()
    print("  ⚠️  LIMITS: Max 20-25/day, wait 2-3 min between each")
    print()
    
    confirm = input("Mark as sent? (y/n): ").strip().lower()
    if confirm == 'y':
        job['connect_status'] = 'sent'
        save_csv_jobs(csv_file, rows, fieldnames)
        print("  ✅ Marked as sent!")


def view_posts(num, job, csv_file, rows, fieldnames):
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
        
        # Open LinkedIn
        open_url_in_tab("https://www.linkedin.com/feed/")
        print("  ✅ Opened LinkedIn. Paste your post and click Post.")
        
        # Open X
        x_url = f"https://twitter.com/compose/tweet?text={urllib.parse.quote(linkedin_post[:280])}"
        open_url_in_tab(x_url)
        print("  ✅ Opened X/Twitter. Review and Tweet.")


if __name__ == "__main__":
    main()
