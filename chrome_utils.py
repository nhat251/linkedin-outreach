#!/usr/bin/env python3
"""
Chrome Automation Utilities for Windows
Replaces macOS AppleScript-based Chrome control with Chrome DevTools Protocol (CDP).

Requirements:
- Chrome launched with: --remote-debugging-port=9222
- pip install websocket-client requests pyperclip
"""

import json
import time
import re
import subprocess
import requests
import pyperclip
import os
import io
import sys


# ─── Configuration ───────────────────────────────────────────────────────────

CDP_HOST = "127.0.0.1"
CDP_PORT = 9222
CDP_URL = f"http://{CDP_HOST}:{CDP_PORT}"


# ─── Connection Check ───────────────────────────────────────────────────────

def ensure_chrome_debugging():
    """Check if Chrome with remote debugging is accessible.
    Returns True if CDP endpoint responds, False otherwise.
    """
    try:
        resp = requests.get(f"{CDP_URL}/json/version", timeout=3)
        return resp.status_code == 200
    except requests.ConnectionError:
        return False


def get_chrome_version():
    """Get Chrome version string from CDP endpoint."""
    try:
        resp = requests.get(f"{CDP_URL}/json/version", timeout=3)
        if resp.status_code == 200:
            return resp.json().get("Browser", "unknown")
    except Exception:
        pass
    return None


def list_tabs():
    """List all open tabs/pages in Chrome.
    Returns list of dicts with keys: id, title, url, webSocketDebuggerUrl
    """
    try:
        resp = requests.get(f"{CDP_URL}/json", timeout=5)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception as e:
        print(f"  ⚠️  CDP list_tabs error: {e}")
        return []


# ─── Tab Management ─────────────────────────────────────────────────────────

def new_tab(url="about:blank"):
    """Open a URL in a new Chrome tab.
    Returns the tab info dict or None on failure.
    """
    import urllib.parse
    encoded = urllib.parse.quote(url, safe='')
    try:
        resp = requests.get(f"{CDP_URL}/json/new?url={encoded}", timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"  ⚠️  CDP new_tab error: {e}")
        return None


def activate_tab(tab_id):
    """Bring a tab to the foreground (activate it)."""
    try:
        resp = requests.get(f"{CDP_URL}/json/activate/{tab_id}", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def close_tab(tab_id):
    """Close a specific tab by ID."""
    try:
        resp = requests.get(f"{CDP_URL}/json/close/{tab_id}", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


# Track the tab we most recently created/activated
_last_opened_tab = None

def get_active_tab():
    """Get the tab that automation should use.
    First tries to find the last-opened tab (saved to file across processes).
    Falls back to the last page tab in the list.
    """
    global _last_opened_tab
    
    # Try file-persisted tab first (survives across Python processes)
    saved_tab = _load_last_tab()
    if saved_tab and saved_tab.get("id"):
        tabs = list_tabs()
        for t in tabs:
            if t.get("id") == saved_tab.get("id"):
                _last_opened_tab = t
                return t
    
    # Try in-memory stored tab
    if _last_opened_tab:
        tabs = list_tabs()
        for t in tabs:
            if t.get("id") == _last_opened_tab.get("id"):
                return t
    
    # Fallback: return the last page tab (newest = most recently created)
    tabs = list_tabs()
    page_tabs = [t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    if page_tabs:
        last = page_tabs[-1]
        _last_opened_tab = last
        _save_last_tab(last)
        return last
    for tab in tabs:
        if tab.get("type") == "page":
            _last_opened_tab = tab
            _save_last_tab(tab)
            return tab
    return None


def navigate_to_url(url):
    """Navigate the current active tab to a URL."""
    global _last_opened_tab
    import urllib.parse
    tab = get_active_tab()
    if not tab:
        print("  ⚠️  No active tab found")
        return False

    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        print("  ⚠️  No WebSocket URL for active tab")
        return False

    import websocket
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        cmd = {
            "id": 1,
            "method": "Page.navigate",
            "params": {"url": url}
        }
        ws.send(json.dumps(cmd))
        result = ws.recv()
        ws.close()
        # Refresh the stored tab (same tab, just navigated)
        _last_opened_tab = tab
        return True
    except Exception as e:
        print(f"  ⚠️  CDP navigate error: {e}")
        return False


def switch_to_last_tab():
    """Switch focus to the last opened tab (newest tab).
    Returns True on success.
    """
    tabs = list_tabs()
    page_tabs = [t for t in tabs if t.get("type") == "page"]
    if len(page_tabs) >= 2:
        # The last tab in the list is typically the newest
        last_tab = page_tabs[-1]
        tab_id = last_tab.get("id")
        if tab_id:
            return activate_tab(tab_id)
    return False


# ─── JavaScript Execution ───────────────────────────────────────────────────

def execute_js(js_code, timeout=10, target_tab=None):
    """Execute JavaScript in a Chrome tab via CDP and return the result.
    
    If target_tab is None, uses the active tab.
    Returns parsed JSON result, or None on failure.
    """
    tab = target_tab or get_active_tab()
    if not tab:
        print("  ⚠️  No available tab for JS execution")
        return None

    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        print("  ⚠️  No WebSocket URL for tab")
        return None

    import websocket
    try:
        ws = websocket.create_connection(ws_url, timeout=timeout)

        # Send Runtime.evaluate command
        cmd = {
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": js_code,
                "returnByValue": True,
                "awaitPromise": True
            }
        }
        ws.send(json.dumps(cmd))

        # Receive response(s)
        result = None
        while True:
            raw = ws.recv()
            if not raw:
                break
            try:
                msg = json.loads(raw)
                if msg.get("id") == 1:
                    result = msg
                    break
            except json.JSONDecodeError:
                continue

        ws.close()

        if result:
            if "error" in result:
                print(f"  ⚠️  JS execution error: {result['error']}")
                return None
            outer = result.get("result", {})
            if "exceptionDetails" in outer and outer["exceptionDetails"]:
                print(f"  ⚠️  JS exception: {outer['exceptionDetails']}")
                return None
            # The result is nested: Runtime.evaluate returns {result: {result: {type, value}, exceptionDetails}}
            inner = outer.get("result", outer)
            if inner.get("type") == "string" and "value" in inner:
                return inner["value"]
            if "value" in inner:
                return inner["value"]
            # Debug: show raw response if nothing matched
            if "type" in inner:
                return f"[{inner['type']}] {inner.get('value', inner.get('description', ''))}"
            print(f"  ⚠️  execute_js: unexpected response shape: {str(result)[:200]}")
            return None

        return None

    except Exception as e:
        print(f"  ⚠️  CDP execute_js error: {e}")
        return None


# ─── URL Opening (High-Level) ───────────────────────────────────────────────

# File to persist the last opened tab_id across Python processes
_LAST_TAB_FILE = os.path.join(os.path.dirname(__file__), '.last_tab')

def _save_last_tab(tab_info):
    """Save the last opened tab info to a temp file (survives across Python processes)."""
    try:
        with open(_LAST_TAB_FILE, 'w') as f:
            json.dump(tab_info, f)
    except Exception:
        pass

def _load_last_tab():
    """Load the last opened tab info from temp file."""
    try:
        with open(_LAST_TAB_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return None

def _cdp_send(ws, method, params=None, timeout_val=15):
    """Send a CDP command and wait for the response with matching id. Returns response dict or None."""
    import websocket
    cmd_id = int(time.time() * 1000) % 100000
    cmd = {"id": cmd_id, "method": method}
    if params:
        cmd["params"] = params
    ws.send(json.dumps(cmd))
    ws.settimeout(timeout_val)
    while True:
        try:
            raw = ws.recv()
            if not raw:
                break
            msg = json.loads(raw)
            if msg.get("id") == cmd_id:
                return msg
        except websocket.WebSocketTimeoutException:
            break
        except Exception:
            continue
    return None

def focus_chrome_window():
    """Bring Chrome window to foreground (Windows only)."""
    try:
        subprocess.run(
            ["powershell", "-Command", """
                $chrome = Get-Process chrome -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($chrome) {
                    Add-Type @'
                        using System;
                        using System.Runtime.InteropServices;
                        public class Win32 {
                            [DllImport("user32.dll")]
                            public static extern bool SetForegroundWindow(IntPtr hWnd);
                            [DllImport("user32.dll")]
                            public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                        }
'@
                    [Win32]::ShowWindow($chrome.MainWindowHandle, 5)  # SW_SHOW
                    [Win32]::SetForegroundWindow($chrome.MainWindowHandle)
                }
            """],
            capture_output=True, timeout=5
        )
        return True
    except Exception:
        return False


def open_url_in_tab(url):
    """Open URL in a new Chrome tab, wait for full page load, activate it, and focus the window.
    Uses Target.createTarget via WebSocket (more reliable than HTTP /json/new).
    Saves tab info to a file so subsequent Python processes can find the same tab.
    """
    global _last_opened_tab
    import websocket
    
    try:
        # Step 1: Get any existing tab's WebSocket to send commands
        tabs = list_tabs()
        page_tabs = [t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
        if not page_tabs:
            print("  ⚠️  No page tabs available to create a new tab")
            return False
        
        first_tab = page_tabs[0]
        ws_url = first_tab.get("webSocketDebuggerUrl")
        
        # Step 2: Connect and create a new target (tab)
        ws = websocket.create_connection(ws_url, timeout=15)
        
        # Create a new tab via Target.createTarget
        resp = _cdp_send(ws, "Target.createTarget", {"url": "about:blank"})
        if not resp:
            print("  ⚠️  Target.createTarget: no response")
            ws.close()
            return False
        if "error" in resp:
            print(f"  ⚠️  Target.createTarget error: {resp['error']}")
            ws.close()
            return False
        
        target_info = resp.get("result", {})
        new_target_id = target_info.get("targetId")
        new_ws_url = target_info.get("webSocketDebuggerUrl") or \
                     f"ws://{CDP_HOST}:{CDP_PORT}/devtools/page/{new_target_id}"
        
        if not new_target_id:
            print("  ⚠️  Target.createTarget: no targetId returned")
            ws.close()
            return False
        
        ws.close()
        
        # Step 3: Connect to the NEW tab and navigate
        new_tab_info = {
            "id": new_target_id,
            "type": "page",
            "url": "about:blank",
            "webSocketDebuggerUrl": new_ws_url
        }
        
        ws2 = websocket.create_connection(new_ws_url, timeout=15)
        
        # Enable Page events
        resp = _cdp_send(ws2, "Page.enable")
        if resp and "error" in resp:
            print(f"  ⚠️  Page.enable error: {resp['error']}")
            ws2.close()
            return False
        
        # Navigate to URL
        nav_resp = _cdp_send(ws2, "Page.navigate", {"url": url})
        if nav_resp and "error" in nav_resp:
            print(f"  ⚠️  Page.navigate error: {nav_resp['error']}")
            ws2.close()
            return False
        
        # Wait for Page.loadEventFired
        ws2.settimeout(20)
        loaded = False
        while True:
            try:
                raw = ws2.recv()
                if not raw:
                    break
                msg = json.loads(raw)
                if msg.get("method") == "Page.loadEventFired":
                    loaded = True
                    break
            except websocket.WebSocketTimeoutException:
                break
            except Exception:
                continue
        
        ws2.close()
        
        if not loaded:
            print(f"  ⚠️  Page load timeout for: {url[:60]}...")
        
        # Step 4: Update tab info with final URL and activate
        new_tab_info["url"] = url
        
        if new_target_id:
            activate_tab(new_target_id)
        focus_chrome_window()
        
        _last_opened_tab = new_tab_info
        _save_last_tab(new_tab_info)
        return True
        
    except Exception as e:
        print(f"  ⚠️  open_url_in_tab error: {e}")
        return False
        
        tab_id = result.get("id")
        ws_url = result.get("webSocketDebuggerUrl")
        
        # Step 2: Use WebSocket CDP to navigate and wait for page load
        if tab_id and ws_url:
            import websocket
            try:
                ws = websocket.create_connection(ws_url, timeout=15)
                
                # Enable Page events so we can listen for loadEventFired
                ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
                # Drain until we get the response to id=1
                while True:
                    raw = ws.recv()
                    if not raw:
                        break
                    try:
                        msg = json.loads(raw)
                        if msg.get("id") == 1:
                            break
                    except json.JSONDecodeError:
                        continue
                
                # Navigate to the URL
                nav_cmd = {
                    "id": 2,
                    "method": "Page.navigate",
                    "params": {"url": url}
                }
                ws.send(json.dumps(nav_cmd))
                
                # Wait for Page.loadEventFired (page fully loaded)
                ws.settimeout(15)
                loaded = False
                while True:
                    raw = ws.recv()
                    if not raw:
                        break
                    try:
                        msg = json.loads(raw)
                        if msg.get("method") == "Page.loadEventFired":
                            loaded = True
                            break
                        if msg.get("id") == 2:
                            # Navigation started, continue waiting for load event
                            continue
                    except json.JSONDecodeError:
                        continue
                
                ws.close()
                
                if not loaded:
                    print(f"  ⚠️  Page load timeout for: {url[:60]}...")
                    
            except Exception as e:
                print(f"  ⚠️  CDP navigate error: {e}")
        
        # Step 3: Activate the tab and focus the window
        if tab_id:
            activate_tab(tab_id)
        focus_chrome_window()
        _last_opened_tab = result  # Store for subsequent execute_js calls
        return True
        
    except Exception as e:
        print(f"  ⚠️  open_url_in_tab error: {e}")
        return False


# ─── Clipboard ──────────────────────────────────────────────────────────────

def get_clipboard():
    """Read clipboard contents (cross-platform, Windows via pyperclip + fallback)."""
    try:
        return pyperclip.paste()
    except Exception:
        pass

    # Fallback: PowerShell Get-Clipboard
    try:
        result = subprocess.run(
            ["powershell", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    return None


def set_clipboard(text):
    """Write text to clipboard."""
    try:
        pyperclip.copy(text)
        return True
    except Exception:
        pass

    # Fallback: PowerShell
    try:
        escaped = text.replace("'", "''")
        subprocess.run(
            ["powershell", "-Command", f"Set-Clipboard -Value '{escaped}'"],
            capture_output=True, timeout=5
        )
        return True
    except Exception:
        return False


# ─── Process Check ─────────────────────────────────────────────────────────

def is_chrome_running():
    """Check if any Chrome process is running (Windows via tasklist)."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/NH"],
            capture_output=True, text=True, timeout=5
        )
        return "chrome.exe" in result.stdout
    except Exception:
        return False


# ─── Legacy Compatibility Bridges ───────────────────────────────────────────

def run_applescript(script, timeout=10):
    """BRIDGE: Replaces macOS osascript calls on Windows.
    Not truly applescript — provides analogous behavior.
    For simple URL-open scripts, use open_url_in_tab() instead.
    This function tries to interpret simple patterns and delegates to CDP.
    """
    # Detect common patterns
    # Pattern: make new tab with properties {URL:"..."}
    url_match = re.search(r'URL:"([^"]+)"', script)
    if url_match:
        return open_url_in_tab(url_match.group(1))

    # Pattern: set URL of active tab of window 1 to "..."
    url_match2 = re.search(r'set URL of active tab.*?"([^"]+)"', script)
    if url_match2:
        return navigate_to_url(url_match2.group(1))

    # Pattern: history.back()
    if "history.back" in script:
        return execute_js("window.history.back();")

    # Pattern: execute activeTab javascript "..."
    js_match = re.search(r'javascript\s+"([^"]+)"', script)
    if js_match:
        js_raw = js_match.group(1)
        # Unescape double-quotes within
        js_raw = js_raw.replace('\\"', '"')
        return execute_js(js_raw, timeout=timeout)

    print("  ⚠️  AppleScript bridge: unrecognized script pattern")
    return None


def go_back():
    """Navigate browser back (bridge for osascript history.back)."""
    return execute_js("window.history.back();")


# ─── Auto-diagnostics ──────────────────────────────────────────────────────

def _ensure_utf8():
    """Ensure stdout uses UTF-8 encoding (required for emoji on Windows)."""
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def diagnose():
    """Print diagnostics about Chrome debugging status."""
    _ensure_utf8()
    
    print("=" * 60)
    print("Chrome CDP Diagnostics")
    print("=" * 60)

    print(f"\n[SEARCH] Checking {CDP_URL}...")
    if ensure_chrome_debugging():
        version = get_chrome_version()
        print(f"  [OK] Chrome is running with remote debugging!")
        print(f"  [INFO] Version: {version}")

        tabs = list_tabs()
        page_tabs = [t for t in tabs if t.get("type") == "page"]
        print(f"  [INFO] Open tabs: {len(page_tabs)}")

        active = get_active_tab()
        if active:
            print(f"  [TARGET] Active tab: {active.get('title', 'N/A')[:50]}")
    else:
        print(f"  [FAIL] Chrome remote debugging NOT accessible at {CDP_URL}")
        print()
        print("  To enable:")
        print("  1. Close all Chrome windows")
        print("  2. Run: start_chrome.bat")
        print("     Or open PowerShell and run:")
        print(f'     & "$env:ProgramFiles\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port={CDP_PORT} --remote-allow-origins=* --user-data-dir="C:\\chrome-debug"')
        print()
        print("  [TIP] Use start_chrome.bat for the correct setup")

    print(f"\n[SEARCH] Checking Chrome process...")
    if is_chrome_running():
        print("  [OK] Chrome process is running")
    else:
        print("  [WARN] Chrome process not found (may be running as different user)")

    print(f"\n[SEARCH] Clipboard...")
    clip = get_clipboard()
    if clip:
        print(f"  [OK] Clipboard has content ({len(clip)} chars)")
    else:
        print("  [WARN] Clipboard empty or inaccessible")

    print("=" * 60)
    return ensure_chrome_debugging()


# ─── Main (CLI) ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "diagnose":
        diagnose()
    elif len(sys.argv) > 2 and sys.argv[1] == "open":
        ok = open_url_in_tab(sys.argv[2])
        if ok:
            print(f"✅ Opened: {sys.argv[2]}")
        else:
            print(f"❌ Failed to open: {sys.argv[2]}")
    elif len(sys.argv) > 2 and sys.argv[1] == "js":
        result = execute_js(sys.argv[2])
        print(f"Result: {result}")
    elif len(sys.argv) > 1 and sys.argv[1] == "tabs":
        _tabs = list_tabs()
        if not _tabs:
            print("  No tabs found")
        else:
            print(f"  Found {len(_tabs)} tab(s):")
            for i, t in enumerate(_tabs):
                if t.get("type") == "page":
                    title = (t.get("title") or "")[:50]
                    url = (t.get("url") or "")[:80]
                    tid = (t.get("id") or "?")[:20]
                    print(f"  {i+1}. [{tid}] \"{title}\"")
                    print(f"      {url}")
        # Clean up saved tab if it no longer exists
        saved = _load_last_tab()
        if saved:
            still_exists = any(t.get("id") == saved.get("id") for t in _tabs)
            if not still_exists:
                try: os.remove(_LAST_TAB_FILE)
                except: pass
    else:
        print("Usage:")
        print("  python chrome_utils.py diagnose     - Check Chrome debugging status")
        print("  python chrome_utils.py tabs         - List open tabs")
        print("  python chrome_utils.py open <url>   - Open URL in new tab")
        print("  python chrome_utils.py js <code>    - Execute JavaScript")
