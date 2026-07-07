#!/usr/bin/env python3
"""
Extract LinkedIn Profiles from Google Search Results
Saves URLs to CSV for later outreach.
Usage: python open_profiles.py [job_title_partial]
"""

import subprocess
import time
import json
import random
import csv
import os
import sys
import io
import re

# Windows compatibility: Chrome automation via CDP
from chrome_utils import (
    execute_js, open_url_in_tab, get_active_tab,
    list_tabs, go_back, ensure_chrome_debugging
)


def normalize_linkedin_url(url):
    """Remove country subdomain from LinkedIn URLs"""
    if not url or 'linkedin.com/in/' not in url:
        return url
    return re.sub(r'(?!ww)[a-z]{2}\.linkedin\.com', 'linkedin.com', url)


def normalize_urls(urls):
    """Normalize a list of LinkedIn URLs"""
    return [normalize_linkedin_url(url) for url in urls]


def extract_linkedin_urls():
    """Extract all LinkedIn profile URLs from current page"""
    js = """
    (function() {
        var links = document.querySelectorAll('a[href*="linkedin.com/in/"]');
        var urls = [];
        for (var i = 0; i < links.length; i++) {
            var href = links[i].href;
            if (href.includes('/url?q=')) {
                href = href.split('/url?q=')[1].split('&sa=')[0];
            }
            href = href.split('?')[0];
            href = decodeURIComponent(href);
            if (href && !urls.includes(href)) {
                urls.push(href);
            }
        }
        return JSON.stringify(urls);
    })();
    """
    result = execute_js(js)
    if result and isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return []
    return result or []


def go_to_page_2():
    """Navigate to page 2 by modifying URL"""
    js = """
    (function() {
        var url = window.location.href;
        var newUrl;
        if (url.indexOf('start=') > -1) {
            newUrl = url.replace(/start=[0-9]+/, 'start=10');
        } else {
            newUrl = url + '&start=10';
        }
        window.location.href = newUrl;
        return true;
    })();
    """
    return execute_js(js)


def go_back_to_page_1():
    """Go back to previous page via CDP"""
    return go_back()


def open_urls_in_tabs(urls):
    """Open URLs in new Chrome tabs with random delays and error handling"""
    for url in urls:
        try:
            open_url_in_tab(url)
        except Exception as e:
            print(f"  ⚠️  Exception opening URL: {e}")
        time.sleep(random.uniform(2, 5))


def save_profiles_to_csv(job_title, urls):
    """Save extracted URLs to the linkedin_profiles column in CSV"""
    # Normalize URLs to remove country subdomains
    urls = normalize_urls(urls)
    
    csv_file = 'uctalent_jobs.csv'
    if not os.path.exists(csv_file):
        print(f"\n  ⚠️  No CSV file found at {csv_file}")
        return False
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames
    
    # Add linkedin_profiles column if missing
    if 'linkedin_profiles' not in fieldnames:
        fieldnames.append('linkedin_profiles')
        for row in rows:
            row['linkedin_profiles'] = ''
    
    # Find matching job row and append URLs
    saved = False
    for row in rows:
        title = row.get('title', '').strip().lower()
        if job_title and job_title.lower() in title:
            existing = row.get('linkedin_profiles', '')
            if existing:
                # Append unique URLs (normalize existing URLs too)
                existing_urls = [normalize_linkedin_url(u.strip()) for u in existing.split(',') if u.strip()]
                new_urls = [u for u in urls if u not in existing_urls]
                if new_urls:
                    row['linkedin_profiles'] = ','.join(existing_urls + new_urls)
                    saved = True
                    print(f"  Appended {len(new_urls)} new profile(s) to '{row['title']}'")
            else:
                row['linkedin_profiles'] = ','.join(urls)
                saved = True
                print(f"  Saved {len(urls)} profile(s) to '{row['title']}'")
            break
    
    if saved:
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return True
    else:
        print(f"\n  ⚠️  No matching job found in CSV for: {job_title}")
        print("  Profiles saved to console output only.")
        return False


def main():
    # Fix console encoding for Windows (emoji & Unicode support)
    if hasattr(sys.stdout, 'reconfigure'):
        try: sys.stdout.reconfigure(encoding='utf-8')
        except: pass
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Extract LinkedIn Profiles from Google Search")
    print("=" * 60)
    
    # Get job title from command line or prompt
    job_title = sys.argv[1] if len(sys.argv) > 1 else None
    
    print("\nMake sure:")
    print("  1. Chrome is running")
    print("  2. Active tab is on Google search results")
    if job_title:
        print(f"  3. Saving to job: {job_title}")
    print()
    
    confirm = input("Extract profiles? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return
    
    # Step 1: Extract from page 1
    print("\nExtracting LinkedIn URLs from page 1...")
    page1_urls = extract_linkedin_urls()
    print(f"  Found {len(page1_urls)} profile(s)")
    
    # Step 2: Go to page 2 and extract
    print("\nNavigating to page 2...")
    if go_to_page_2():
        time.sleep(3)
        print("Extracting LinkedIn URLs from page 2...")
        page2_urls = extract_linkedin_urls()
        print(f"  Found {len(page2_urls)} profile(s)")
        print("\nGoing back to page 1...")
        go_back_to_page_1()
        time.sleep(2)
    else:
        print("  Could not navigate to page 2")
        page2_urls = []
    
    # Combine and deduplicate
    all_urls = list(dict.fromkeys(page1_urls + page2_urls))
    
    # Normalize URLs (remove country subdomains)
    all_urls = normalize_urls(all_urls)
    
    if all_urls:
        print(f"\nTotal unique profiles: {len(all_urls)}")
        for i, url in enumerate(all_urls, 1):
            print(f"  {i}. {url}")
        
        # Save to CSV
        if job_title:
            save_profiles_to_csv(job_title, all_urls)
        else:
            print("\n💡 Tip: Run again with job title to auto-save to CSV:")
            print("   python open_profiles.py \"Job Title Here\"")
        
        # Open tabs for manual review
        print(f"\nOpening {len(all_urls)} profiles in new tabs...")
        open_urls_in_tabs(all_urls)
        print("Done!")
    else:
        print("\nNo LinkedIn profile URLs found.")


if __name__ == "__main__":
    main()
