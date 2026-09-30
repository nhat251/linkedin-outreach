#!/usr/bin/env python3
"""
UCTalent referral link automation.

The job page has a "Refer & Earn" button that opens a modal containing a
per-job referral link plus a "Copy Link" button. Previously the user had to
click both by hand and paste the link into the terminal (guide.py step 1).

This module does it end to end:
  1. click the "Refer & Earn" BUTTON
  2. wait for the modal to render the link
  3. read the link straight out of the DOM  (primary, most reliable)
  4. click "Copy Link" so the link also lands on the clipboard (side effect
     the user relies on, and a cross-check on the DOM value)

Two site details that matter:

* There is an `<a href="/refer-earn">` with the same caption as the button.
  Clicking that navigates away from the job page, so we only ever click
  `<button>` elements.
* The link is displayed with CSS ellipsis ("https://...so…"). The full URL is
  in the DOM, so we read textContent rather than trusting what is visible.

Scoping note: the modal root is `.MuiModal-root` with `role="presentation"`.
The page's only `[role="dialog"]` is an unrelated empty element, so scoping
reads to that selector silently finds nothing — we look inside the modal root
and fall back to the whole document.

Clipboard note: the link is read from the page, never from the clipboard. The
"Copy Link" button is still clicked, but a synthetic click does not satisfy the
user-gesture requirement of navigator.clipboard.writeText, so the site leaves
the clipboard untouched. When that happens we write the value ourselves so the
user still ends up with a usable clipboard.
"""

import json
import os
import re
import sys
import io
import time

from chrome_utils import execute_js, poll_js, get_clipboard, set_clipboard, open_url_in_tab


# The modal title, e.g. "You're referring a candidate to Data QA ENGINEER"
_TITLE_PREFIX = "You're referring a candidate to"

# ─── JavaScript ──────────────────────────────────────────────────────────────

# Shared readers. Kept in one place so the read and the copy click agree on
# what "the modal" is.
_JS_FINDERS = """
    var URL_RE = /https?:\\/\\/[a-z0-9.-]*uctalent\\.io\\/referral\\/[^\\s"'<>]+/i;

    function findLink(root) {
        var nodes = root.querySelectorAll('p,span,div,a,code');
        for (var i = 0; i < nodes.length; i++) {
            if (nodes[i].children.length > 0) { continue; }
            var t = (nodes[i].textContent || '').trim();
            if (t.toLowerCase().indexOf('uctalent.io/referral/') === -1) { continue; }
            var m = t.match(URL_RE);
            if (m) { return m[0]; }
        }
        return '';
    }

    function findTitle(root) {
        var all = root.querySelectorAll('div,h1,h2,h3,p,span');
        for (var i = 0; i < all.length; i++) {
            var tt = (all[i].innerText || '').replace(/\\s+/g, ' ').trim();
            if (tt.length < 120 && tt.indexOf(TITLE_PREFIX) === 0) { return tt; }
        }
        return '';
    }

    // The referral modal, or null if it is not open
    function findModal() {
        var modals = document.querySelectorAll('.MuiModal-root');
        for (var m = 0; m < modals.length; m++) {
            if (findLink(modals[m])) { return modals[m]; }
        }
        return null;
    }
"""

# Reads the modal: the referral link and the job title it belongs to.
JS_READ_REFERRAL = ("(function() {" + _JS_FINDERS + """
    var modal = findModal();
    var root = modal || document;
    return JSON.stringify({
        link: findLink(root),
        title: findTitle(root),
        open: !!modal
    });
})()""").replace('TITLE_PREFIX', json.dumps(_TITLE_PREFIX))

# Clicks the "Refer & Earn" BUTTON. Never an <a> — the anchor navigates away.
JS_CLICK_REFERRAL = """(function() {
    var all = document.querySelectorAll('button');
    for (var i = 0; i < all.length; i++) {
        var t = (all[i].innerText || '').replace(/\\s+/g, ' ').trim();
        if (t !== 'Refer & Earn') { continue; }
        var r = all[i].getBoundingClientRect();
        // Skip the hidden responsive duplicates MUI renders
        if (r.width < 40 || r.height < 20) { continue; }
        all[i].scrollIntoView({ block: 'center' });
        ['mousedown', 'mouseup', 'click'].forEach(function(type) {
            all[i].dispatchEvent(new MouseEvent(type, {
                bubbles: true, cancelable: true, view: window, button: 0
            }));
        });
        return 'clicked';
    }
    return 'not_found';
})()"""

# The job page is a React SPA, so the button can appear after load fires.
JS_HAS_REFERRAL_BUTTON = """(function() {
    var all = document.querySelectorAll('button');
    for (var i = 0; i < all.length; i++) {
        if ((all[i].innerText || '').replace(/\\s+/g, ' ').trim() !== 'Refer & Earn') { continue; }
        var r = all[i].getBoundingClientRect();
        if (r.width >= 40 && r.height >= 20) { return 'found'; }
    }
    return '';
})()"""

# Clicks "Copy Link" inside the modal so the link reaches the clipboard.
JS_CLICK_COPY = ("(function() {" + _JS_FINDERS + """
    var root = findModal() || document;
    var all = root.querySelectorAll('button');
    for (var i = 0; i < all.length; i++) {
        var t = (all[i].innerText || '').replace(/\\s+/g, ' ').trim().toLowerCase();
        if (t !== 'copy link') { continue; }
        var r = all[i].getBoundingClientRect();
        if (r.width < 20 || r.height < 15) { continue; }
        all[i].click();
        return 'clicked';
    }
    return 'not_found';
})()""").replace('TITLE_PREFIX', json.dumps(_TITLE_PREFIX))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _read_state():
    """Return {'link','title','open'} from the open modal, or blanks."""
    result = execute_js(JS_READ_REFERRAL, timeout=20)
    if not result or not isinstance(result, str):
        return {'link': '', 'title': '', 'open': False}
    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        return {'link': '', 'title': '', 'open': False}
    return {
        'link': (data.get('link') or '').strip(),
        'title': (data.get('title') or '').strip(),
        'open': bool(data.get('open')),
    }


def _norm(s):
    """Loose title comparison: collapse whitespace, casefold, drop punctuation."""
    s = (s or '').lower()
    s = re.sub(r'[^\w]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def title_matches(modal_title, job_title):
    """True if the modal is showing a link for the job we asked about.

    The referral URL is opaque (it does not contain the job id), so the modal
    title is the only way to confirm we are not about to save another job's
    link. Titles on both sides come from the same source, so this is a
    safety net rather than a hard gate.
    """
    if not job_title:
        return True
    if not modal_title:
        return False
    got = _norm(modal_title.split(_TITLE_PREFIX, 1)[-1])
    want = _norm(job_title)
    return got == want or want in got or got in want


# ─── Main API ────────────────────────────────────────────────────────────────

def fetch_referral_link(job_title=None, timeout=30, verbose=True):
    """Click Refer & Earn, wait for the modal, return the referral link.

    The job detail page must already be open in the automation tab (call
    open_url_in_tab(job_url) first).

    Args:
        job_title:  job to confirm the modal belongs to (optional, but it is
                    the only way to verify an opaque link is not another
                    job's — worth passing)
        timeout:    seconds to wait for the modal to render the link
        verbose:    print progress

    Returns the referral link, or None if it could not be obtained.
    """
    state = _read_state()
    need_click = True

    # Modal may already be open with the right link (retry / user opened it)
    if state['link'] and title_matches(state['title'], job_title):
        need_click = False
        if verbose:
            print("  ℹ️  Referral modal already open — reading link from it.")

    if need_click:
        if verbose:
            print("  🔄 Clicking 'Refer & Earn'...")
        # The job page is a React SPA, so the button may render after load
        if not poll_js(JS_HAS_REFERRAL_BUTTON, timeout=15, interval=1.0):
            if verbose:
                print("  ⚠️  Could not find the 'Refer & Earn' button.")
                print("     Is the job page open and fully loaded? Are you signed in?")
            return None

        clicked = execute_js(JS_CLICK_REFERRAL, timeout=20)
        if clicked != 'clicked':
            if verbose:
                print("  ⚠️  Could not click 'Refer & Earn'.")
            return None

        # The modal renders asynchronously, so poll instead of sleeping blindly
        if verbose:
            print("  ⏳ Waiting for the referral modal...")
        state = _wait_for_link(timeout)
        if not state:
            if verbose:
                print("  ⚠️  Modal did not show a referral link in time.")
            return None

    # The link is opaque (no job id inside), so the modal title is the only way
    # to be sure it belongs to this job and not a stale modal left on screen.
    if job_title and not title_matches(state['title'], job_title):
        if verbose:
            print(f"  ⚠️  Modal is for a different job — refusing to save.")
            print(f"     Modal says: {state['title'] or '(no title)'}")
            print(f"     Expected:   {job_title}")
        return None

    link = state['link']

    # Click "Copy Link" as well, so the button behaves the way the user expects.
    # The site's own copy is unreliable from automation (see below), so we make
    # sure the clipboard ends up holding *this* link before reporting success.
    before = (get_clipboard() or '').strip()
    copied = execute_js(JS_CLICK_COPY, timeout=20)
    clip = before
    if copied == 'clicked':
        for _ in range(4):
            time.sleep(0.4)
            clip = (get_clipboard() or '').strip()
            if clip and clip != before:
                break

    # The clipboard is a convenience and must never influence the result: a
    # synthetic click does not satisfy the user-gesture requirement of
    # navigator.clipboard.writeText, so the site often leaves the previous
    # job's link sitting on the clipboard. The DOM is the source of truth.
    if clip != link:
        if verbose:
            print("  ℹ️  Site's copy did not update the clipboard — copying it directly.")
        set_clipboard(link)
        clip = link

    if verbose:
        print(f"  ✅ Referral link captured ({len(link)} chars)")
        print(f"     {link}")
        if copied != 'clicked':
            print("  ℹ️  'Copy Link' button not found — link taken from the page.")

    return link


def _wait_for_link(timeout=30, step=1.0):
    """Poll the modal until a referral link shows up. Returns state or None."""
    waited = 0.0
    while waited < timeout:
        state = _read_state()
        if state['link']:
            return state
        time.sleep(step)
        waited += step
    return None


# ─── CLI (handy for testing) ────────────────────────────────────────────────

def _ensure_utf8():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass


if __name__ == '__main__':
    _ensure_utf8()
    print("=" * 60)
    print("UCTalent referral link fetcher")
    print("=" * 60)

    url = sys.argv[1] if len(sys.argv) > 1 else None
    title = sys.argv[2] if len(sys.argv) > 2 else None

    if url:
        print(f"\nOpening: {url}")
        open_url_in_tab(url)
        import time
        time.sleep(5)

    result = fetch_referral_link(job_title=title)
    print()
    if result:
        print(f"RESULT: {result}")
    else:
        print("RESULT: None — could not get the referral link.")
