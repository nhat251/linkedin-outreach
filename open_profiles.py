#!/usr/bin/env python3
"""
Extract LinkedIn Profiles from Google Search Results
Saves URLs to XLSX for later outreach.
Usage: python open_profiles.py [job_title_partial]
"""

import subprocess
import time
import json
import random
import os
import sys
import io
import re
from concurrent.futures import ThreadPoolExecutor

import requests

# XLSX storage (replaces CSV)
from xlsx_utils import read_xlsx, write_xlsx, get_xlsx_path

# Windows compatibility: Chrome automation via CDP
from chrome_utils import (
    execute_js, open_url_in_tab, get_active_tab,
    list_tabs, go_back, ensure_chrome_debugging,
    _load_last_tab, _save_last_tab
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
    # Country subdomain, e.g. vn.linkedin.com → linkedin.com (www. is kept)
    url = re.sub(r'\b[a-z]{2}\.linkedin\.com', 'linkedin.com', url)
    # Locale / details suffix: /in/<slug>/<locale>[/...] → /in/<slug>
    url = re.sub(r'(linkedin\.com/in/[^/]+)/(?:[a-z]{2}|details)(?:/.*)?$', r'\1', url)
    return url


def is_linkedin_profile(url):
    """True only if url is a real linkedin.com/in/ profile URL (host checked)."""
    if not url:
        return False
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.netloc or '').lower()
    if host.startswith('www.'):
        host = host[4:]
    return host == 'linkedin.com' and '/in/' in parsed.path


def normalize_urls(urls):
    """Normalize a list of LinkedIn URLs"""
    return [normalize_linkedin_url(url) for url in urls]


def extract_linkedin_urls():
    """Extract candidate LinkedIn profile URLs from the current search page.

    Google no longer puts the destination URL in the result anchor. Organic
    results now use an opaque token:

        <a href="/goto?url=CAESXAHrOzAVHv3SQ..." ping="/url?sa=t&...&url=CAES...">

    So we collect every plausible candidate (direct /in/ hrefs AND the
    redirect tokens) and let resolve_candidates() sort out which are real
    LinkedIn profiles.

    Returns list of raw hrefs (may still need resolving).
    """
    js = """
    (function() {
        var out = [];
        function add(h) { if (h && out.indexOf(h) === -1) { out.push(h); } }

        // 1) Direct profile links (old-style SERP, Bing, or already-resolved page)
        var direct = document.querySelectorAll('a[href*="linkedin.com/in/"], a[href*="linkedin.com%2Fin%2F"]');
        for (var i = 0; i < direct.length; i++) { add(direct[i].href); }

        // 2) Google's obfuscated redirect links (current SERP)
        var goto = document.querySelectorAll('a[href^="/goto?url="]');
        for (var g = 0; g < goto.length; g++) { add(goto[g].href); }

        // 3) Legacy /url?q= redirect links
        var legacy = document.querySelectorAll('a[href*="/url?"]');
        for (var l = 0; l < legacy.length; l++) {
            var h = legacy[l].href;
            if (h.indexOf('linkedin') > -1) { add(h); }
        }

        return JSON.stringify(out);
    })();
    """
    result = execute_js(js)
    if result and isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return []
    return result or []


# ─── Candidate Resolution ────────────────────────────────────────────────────

_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36')


def _unwrap_google_redirect(href):
    """Pull the target out of a legacy /url?q=... style link (no network)."""
    if '/url?' in href:
        from urllib.parse import urlparse, parse_qs, unquote
        qs = parse_qs(urlparse(href).query)
        for key in ('q', 'url'):
            if key in qs and qs[key]:
                return unquote(qs[key][0])
    return href


def _resolve_one(href):
    """Resolve a single candidate href to a real LinkedIn /in/ URL, or None."""
    from urllib.parse import unquote
    href = _unwrap_google_redirect(href)
    if href.startswith('/'):
        href = 'https://www.google.com' + href

    # Already a real profile URL — no network needed
    if 'linkedin.com' in href:
        decoded = normalize_linkedin_url(unquote(href))
        if is_linkedin_profile(decoded):
            return decoded

    # Opaque /goto?url= token — ask Google for the redirect target (302 only,
    # we never follow it, so no page is actually loaded).
    if '/goto?url=' in href or '/url?' in href:
        try:
            resp = requests.get(
                href, headers={'User-Agent': _UA},
                allow_redirects=False, timeout=10
            )
            location = resp.headers.get('Location', '')
        except requests.RequestException:
            return None

        # Google sometimes answers with a translate.google.com wrapper that
        # carries the real target in its ?u= parameter.
        if 'translate.google.com' in location:
            m = re.search(r'[?&]u=([^&]+)', location)
            location = unquote(m.group(1)) if m else ''

        # Normalize FIRST (drops the country subdomain), then validate the host.
        location = normalize_linkedin_url(location)
        if is_linkedin_profile(location):
            return location
    return None


def resolve_candidates(hrefs, workers=3, delay=(0.2, 0.5)):
    """Resolve raw candidate hrefs into real LinkedIn profile URLs.

    Each resolution is a single 302-only request, so the load on Google is
    small — but we still stagger them (3 concurrent max, random gap between
    each) to stay well inside normal browsing rates.
    """
    resolved = []
    if not hrefs:
        return resolved

    def staggered(href):
        time.sleep(random.uniform(*delay))
        return _resolve_one(href)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for url in pool.map(staggered, hrefs):
            if url and url not in resolved:
                resolved.append(url)

    return [normalize_linkedin_url(u) for u in resolved]


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
    """Open URLs in new Chrome tabs with random delays and error handling.

    Keeps the search tab registered as the automation target so a follow-up
    run of step 5 still scrapes the Google results, not a profile tab.
    """
    search_tab = _load_last_tab()
    try:
        for url in urls:
            try:
                open_url_in_tab(url)
            except Exception as e:
                print(f"  ⚠️  Exception opening URL: {e}")
            time.sleep(random.uniform(2, 5))
    finally:
        if search_tab and search_tab.get("id"):
            _save_last_tab(search_tab)


def save_profiles_to_xlsx(job_title, urls):
    """Save extracted URLs to the linkedin_profiles column in XLSX"""
    # Normalize URLs to remove country subdomains
    urls = normalize_urls(urls)
    
    xlsx_file = get_xlsx_path()
    if not os.path.exists(xlsx_file):
        print(f"\n  ⚠️  No data file found at {xlsx_file}")
        return False
    
    rows, fieldnames = read_xlsx(xlsx_file)
    fieldnames = list(fieldnames)
    
    # Add linkedin_profiles column if missing
    if 'linkedin_profiles' not in fieldnames:
        fieldnames.append('linkedin_profiles')
        for row in rows:
            row['linkedin_profiles'] = ''
    
    # Find matching job row and append URLs
    saved = False
    matched = False
    all_existing = False
    for row in rows:
        title = row.get('title', '').strip().lower()
        if job_title and title == job_title.lower():
            matched = True
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
                    all_existing = True
                    print(f"  All {len(existing_urls)} profile(s) already saved to '{row['title']}'")
            else:
                row['linkedin_profiles'] = ','.join(urls)
                saved = True
                print(f"  Saved {len(urls)} profile(s) to '{row['title']}'")
            break

    if saved:
        write_xlsx(xlsx_file, rows, fieldnames)
        return True
    elif all_existing:
        return True
    else:
        if not matched:
            print(f"\n  ⚠️  No job titled '{job_title}' in the file.")
            print("     Profiles were not saved. Check the job title matches exactly.")
        else:
            print("\n  ⚠️  Nothing to save (no profiles extracted).")
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
    
    # When called from guide.py with a job title, skip the y/n (already confirmed there)
    if not job_title:
        confirm = input("Extract profiles? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return
    
    # Step 1: Extract from page 1
    print("\nExtracting LinkedIn URLs from page 1...")
    page1_raw = extract_linkedin_urls()
    print(f"  Found {len(page1_raw)} result link(s) — resolving...")
    page1_urls = resolve_candidates(page1_raw)
    print(f"  Found {len(page1_urls)} profile(s)")

    # Step 2: Go to page 2 and extract
    print("\nNavigating to page 2...")
    if go_to_page_2():
        time.sleep(3)
        print("Extracting LinkedIn URLs from page 2...")
        page2_raw = extract_linkedin_urls()
        print(f"  Found {len(page2_raw)} result link(s) — resolving...")
        page2_urls = resolve_candidates(page2_raw)
        print(f"  Found {len(page2_urls)} profile(s)")
        print("\nGoing back to page 1...")
        go_back_to_page_1()
        time.sleep(2)
    else:
        print("  Could not navigate to page 2")
        page2_raw = []
        page2_urls = []
    
    # Combine and deduplicate
    all_urls = list(dict.fromkeys(page1_urls + page2_urls))
    
    # Normalize URLs (remove country subdomains)
    all_urls = normalize_urls(all_urls)
    
    if all_urls:
        print(f"\nTotal unique profiles: {len(all_urls)}")
        for i, url in enumerate(all_urls, 1):
            print(f"  {i}. {url}")
        
        # Save to XLSX
        if job_title:
            save_profiles_to_xlsx(job_title, all_urls)
        else:
            print("\n💡 Tip: Run again with job title to auto-save to file:")
            print("   python open_profiles.py \"Job Title Here\"")
        
        # Open tabs for manual review
        print(f"\nOpening {len(all_urls)} profiles in new tabs...")
        open_urls_in_tabs(all_urls)
        print("Done!")
    else:
        print("\n❌ No LinkedIn profile URLs found.")
        print()
        print("  Most likely causes:")
        print("   • The search tab isn't the active automation tab.")
        print("     Fix: press option 4 (Search) again to re-register the Google tab.")
        print("   • The results page hasn't loaded/finished rendering — scroll it once.")
        print("   • The query returned no LinkedIn profiles (too many quoted phrases).")
        print()
        print(f"  Raw result links detected on page 1: {len(page1_raw)}")
        print(f"  Raw result links detected on page 2: {len(page2_raw)}")


if __name__ == "__main__":
    main()
