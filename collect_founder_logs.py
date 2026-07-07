#!/usr/bin/env python3
"""
Collector Founder Logs & Industry Takes
Interactive prompts to collect authentic insights for content generation.
"""

import json
import os
import sys
import io


def clear():
    os.system('clear' if os.name == 'posix' else 'cls')


def wait():
    input("\nPress Enter to continue...")


def load_config():
    """Load config.json with defaults"""
    default_config = {
        "name": "Your Name",
        "role": "Your Role",
        "founder_logs": "",
        "industry_takes": "",
        "recent_insights": ""
    }
    
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            for key in default_config:
                if key not in config:
                    config[key] = default_config[key]
            return config
    except FileNotFoundError:
        print("  ⚠️  config.json not found, creating new one")
        return default_config


def save_config(config):
    """Save config to config.json"""
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    print("  ✅ Config saved!")


def collect_founder_logs():
    """Collect founder logs - personal stories, observations, experiences"""
    print("=" * 70)
    print("  FOUNDER LOGS — Personal Stories & Observations")
    print("=" * 70)
    print()
    print("  Share your real experiences, frustrations, or wins:")
    print("  • Conversations with founders you've had")
    print("  • Frustrations you've seen in hiring/recruiting")
    print("  • Success stories from UCTalent users")
    print("  • Anything that makes your voice AUTHENTIC")
    print()
    print("  💡 This will be used to generate bold, non-template content")
    print()
    
    lines = []
    first = input("  Your founder logs (paste or type, empty line to finish):\n\n")
    if first.strip():
        lines.append(first)
    while True:
        line = input("  ")
        if line.strip() == '':
            break
        lines.append(line)
    
    return '\n'.join(lines)


def collect_industry_takes():
    """Collect industry opinions and perspectives"""
    print("=" * 70)
    print("  INDUSTRY TAKES — Your Opinions & Perspectives")
    print("=" * 70)
    print()
    print("  Share your honest takes on:")
    print("  • Current state of tech hiring in Vietnam/global")
    print("  • AI's impact on recruitment")
    print("  • What companies get wrong about hiring")
    print("  • Predictions or trends you see")
    print()
    print("  💡 These make posts feel like THOUGHT LEADERSHIP, not ads")
    print()
    
    lines = []
    first = input("  Your industry takes (paste or type, empty line to finish):\n\n")
    if first.strip():
        lines.append(first)
    while True:
        line = input("  ")
        if line.strip() == '':
            break
        lines.append(line)
    
    return '\n'.join(lines)


def collect_recent_insights():
    """Collect recent insights or news you've observed"""
    print("=" * 70)
    print("  RECENT INSIGHTS — What You've Seen Lately")
    print("=" * 70)
    print()
    print("  Share what you've noticed recently:")
    print("  • Changes in job markets you've observed")
    print("  • New tools or approaches companies are using")
    print("  • Feedback from people you've spoken with")
    print("  • Any relevant news or trends")
    print()
    print("  💡 Recent examples make content feel TIMELY and CURRENT")
    print()
    
    lines = []
    first = input("  Your recent insights (paste or type, empty line to finish):\n\n")
    if first.strip():
        lines.append(first)
    while True:
        line = input("  ")
        if line.strip() == '':
            break
        lines.append(line)
    
    return '\n'.join(lines)


def main():
    # Fix console encoding for Windows (emoji & Unicode support)
    if hasattr(sys.stdout, 'reconfigure'):
        try: sys.stdout.reconfigure(encoding='utf-8')
        except: pass
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    clear()
    print("=" * 70)
    print("  UCTalent — Founder Content Collection")
    print("=" * 70)
    print()
    print("  This helps generate BOLD, AUTHENTIC content that doesn't")
    print("  look like generic templates. Your real voice > polished fluff.")
    print()
    wait()
    
    config = load_config()
    
    # Collect each type of input
    print("\n" + "=" * 70)
    print("  STEP 1/3: FOUNDER LOGS")
    print("=" * 70)
    print()
    if config.get('founder_logs'):
        print("  Current logs:")
        print("  " + "-" * 60)
        for line in config['founder_logs'].split('\n')[:5]:
            print(f"  {line}")
        if len(config['founder_logs'].split('\n')) > 5:
            print("  ...")
        print("  " + "-" * 60)
        print()
    
    update = input("  Update founder logs? (y/n): ").strip().lower()
    if update == 'y':
        config['founder_logs'] = collect_founder_logs()
        print()
    
    wait()
    
    # Step 2: Industry Takes
    print("\n" + "=" * 70)
    print("  STEP 2/3: INDUSTRY TAKES")
    print("=" * 70)
    print()
    if config.get('industry_takes'):
        print("  Current takes:")
        print("  " + "-" * 60)
        for line in config['industry_takes'].split('\n')[:5]:
            print(f"  {line}")
        if len(config['industry_takes'].split('\n')) > 5:
            print("  ...")
        print("  " + "-" * 60)
        print()
    
    update = input("  Update industry takes? (y/n): ").strip().lower()
    if update == 'y':
        config['industry_takes'] = collect_industry_takes()
        print()
    
    wait()
    
    # Step 3: Recent Insights
    print("\n" + "=" * 70)
    print("  STEP 3/3: RECENT INSIGHTS")
    print("=" * 70)
    print()
    if config.get('recent_insights'):
        print("  Current insights:")
        print("  " + "-" * 60)
        for line in config['recent_insights'].split('\n')[:5]:
            print(f"  {line}")
        if len(config['recent_insights'].split('\n')) > 5:
            print("  ...")
        print("  " + "-" * 60)
        print()
    
    update = input("  Update recent insights? (y/n): ").strip().lower()
    if update == 'y':
        config['recent_insights'] = collect_recent_insights()
        print()
    
    wait()
    
    # Save and summarize
    save_config(config)
    
    clear()
    print("=" * 70)
    print("  SUMMARY — Your Authentic Voice Assets")
    print("=" * 70)
    print()
    
    if config.get('founder_logs'):
        print("  ✓ Founder Logs: Collected")
    else:
        print("  ○ Founder Logs: Not provided")
    
    if config.get('industry_takes'):
        print("  ✓ Industry Takes: Collected")
    else:
        print("  ○ Industry Takes: Not provided")
    
    if config.get('recent_insights'):
        print("  ✓ Recent Insights: Collected")
    else:
        print("  ○ Recent Insights: Not provided")
    
    print()
    print("  💡 These will be used to generate BOLD, AUTHENTIC content")
    print("     that feels like YOU, not a template.")
    print()
    wait()


if __name__ == "__main__":
    main()