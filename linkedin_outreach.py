#!/usr/bin/env python3
"""
UCTalent Bounty Jobs - Workflow Automation
RUN 1: Fetches 25 bounty jobs, generates queries + messages, opens job tabs
       For manual referral link extraction
RUN 2: Reads CSV, generates social media posts with referral links, 
       opens draft tabs for posting
"""

import requests
import json
import csv
import re
import glob
import os
import sys
import io
import time
import random
import urllib.parse
import subprocess
from datetime import datetime
from bs4 import BeautifulSoup

# Windows compatibility: Chrome automation via CDP instead of AppleScript
from chrome_utils import (
    execute_js, switch_to_last_tab, navigate_to_url, open_url_in_tab,
    get_clipboard, set_clipboard, ensure_chrome_debugging,
    is_chrome_running, list_tabs, new_tab, activate_tab
)


# ─── CSV Field Definitions ───────────────────────────────────────────────────

CSV_FIELDNAMES = [
    'id', 'title', 'referral_link', 'bounty', 'bounty_display', 'bounty_currency',
    'location', 'salary', 'priority',
    'tags', 'description', 'boolean_query', 'outreach_message',
    'linkedin_post', 'x_post', 'facebook_post',
    'image_text', 'linkedin_comment', 'x_comment', 'facebook_comment',
    'linkedin_profiles', 'status', 'connect_status', 'message_status',
    'created_at', 'last_updated'
]

# ─── Content Cleaning ────────────────────────────────────────────────────────

def clean_content(text):
    """Clean LLM-generated content for ready copy-paste"""
    if not text:
        return text
    
    # Replace non-breaking spaces with regular spaces
    text = text.replace('\xa0', ' ')
    
    # Remove markdown-style asterisks for emphasis (e.g., *word* -> word)
    # This handles both single and double asterisks from LLM output
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold** -> word
    text = re.sub(r'\*([^*]+)\*', r'\1', text)      # *italic* -> word
    
    # Replace remaining isolated asterisks (patterns like "*and*" or "*something*")
    text = re.sub(r'\*([a-zA-Z]{2,})\*', r'\1', text)
    
    # Remove any remaining standalone asterisks that are surrounded by spaces or at word boundaries
    text = re.sub(r'\s+\*\s+', ' ', text)  # " * " -> " "
    text = re.sub(r'^\*', '', text, flags=re.MULTILINE)  # leading asterisk
    text = re.sub(r'\*$', '', text, flags=re.MULTILINE)  # trailing asterisk
    
    # Remove markdown underscores for emphasis
    text = re.sub(r'_([^_]+)_', r'\1', text)
    
    # Remove excessive newlines (more than 2 -> make exactly 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove trailing whitespace on each line
    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    # Remove excessive spaces between words
    text = re.sub(r' {2,}', ' ', text)
    
    # Fix common LLM artifacts
    text = text.replace(' . ', '. ')
    text = text.replace(' , ', ', ')
    text = text.replace('  ', ' ')
    
    # Remove backticks
    text = text.replace('`', '')
    
    # Trim start/end
    text = text.strip()
    
    return text


# ─── Gemini API Integration ─────────────────────────────────────────────────

GEMINI_SYSTEM_PROMPT = """You are {name}, {role}.

BRAND VOICE:
{brand_voice}

PERSONAL STORY:
{personal_story}

MISSION:
{mission_statement}

YOUR AUTHENTIC VOICE:
{founder_logs}

INDUSTRY TAKES:
{industry_takes}

RECENT INSIGHTS:
{recent_insights}

TARGET AUDIENCE:
You randomly target either:
1. TALENT: {talent_focus}
   CTA: {talent_cta}
2. REFERRER: {referrer_focus}
   CTA: {referrer_cta}

HASHTAGS: {hashtags}

RULES:
- Write as if you're personally typing this - not a marketing team
- Use your real opinions and observations
- No corporate buzzwords or AI-sounding language
- Be direct, bold, authentic
- Keep posts under platform limits (LinkedIn: ~3000 chars, X: 280 chars)
- Include relevant emojis naturally
- Never sound desperate or salesy
- Sound like a real founder, not a bot

TONE: Founder-to-founder. Direct. No fluff."""


def build_system_prompt(config):
    """Build the system prompt from config"""
    targets = config.get('targets', {})
    talent = targets.get('talent', {})
    referrer = targets.get('referrer', {})
    
    return GEMINI_SYSTEM_PROMPT.format(
        name=config.get('name', 'Your Name'),
        role=config.get('role', 'Your Role'),
        brand_voice=config.get('brand_voice', 'Bold, authentic, founder-to-founder'),
        personal_story=config.get('personal_story', ''),
        mission_statement=config.get('mission_statement', ''),
        founder_logs=config.get('founder_logs', ''),
        industry_takes=config.get('industry_takes', ''),
        recent_insights=config.get('recent_insights', ''),
        talent_focus=talent.get('focus', 'Career growth'),
        talent_cta=talent.get('cta_phrases', {}).get('linkedin', ''),
        referrer_focus=referrer.get('focus', 'Passive income'),
        referrer_cta=referrer.get('cta_phrases', {}).get('linkedin', ''),
        hashtags=config.get('common_hashtags', '#Web3Jobs #UCTalent')
    )


def call_qwen(system_prompt, user_prompt, api_key):
    """Call Qwen 3.6 Flash via DashScope API (International endpoint)"""
    import requests
    import json
    
    # Use international endpoint for accounts from modelstudio.console.alibabacloud.com
    url = "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "qwen-plus",  # qwen-turbo = Qwen3-0.5B, qwen-plus = Qwen3-8B (Qwen3.6-flash)
        "input": {
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ]
        },
        "parameters": {
            "temperature": 0.9,
            "max_tokens": 2048
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            # International endpoint returns: output.text
            return result.get('output', {}).get('text', '')
        else:
            print(f"  ⚠️  Qwen API error: {response.status_code}")
            return None
    except Exception as e:
        print(f"  ⚠️  Qwen call failed: {e}")
        return None


def call_nvidia(system_prompt, user_prompt, api_key):
    """Call NVIDIA Nemotron via OpenAI-compatible API"""
    try:
        from openai import OpenAI
        
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )
        
        completion = client.chat.completions.create(
            model="nvidia/nemotron-3-ultra-550b-a55b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.9,
            top_p=0.95,
            max_tokens=4096,
            extra_body={
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": 4096
            },
            stream=False
        )
        
        if completion.choices and len(completion.choices) > 0:
            return completion.choices[0].message.content
        return None
        
    except ImportError:
        print("  ⚠️  openai package not installed. Run: pip install openai")
        return None
    except Exception as e:
        print(f"  ⚠️  NVIDIA API error: {e}")
        return None


def build_qwen_system_prompt(config):
    """Build system prompt for Qwen from config"""
    targets = config.get('targets', {})
    talent = targets.get('talent', {})
    referrer = targets.get('referrer', {})
    
    return f"""You are {config.get('name', 'Your Name')}, {config.get('role', 'Your Role')}.

BRAND VOICE: {config.get('brand_voice', 'Bold, authentic, founder-to-founder')}

PERSONAL STORY: {config.get('personal_story', '')}

MISSION: {config.get('mission_statement', '')}

YOUR AUTHENTIC VOICE: {config.get('founder_logs', '')}

INDUSTRY TAKES: {config.get('industry_takes', '')}

RECENT INSIGHTS: {config.get('recent_insights', '')}

TARGET AUDIENCE:
You randomly target either:
1. TALENT: {talent.get('focus', 'Career growth')}
   CTA: {talent.get('cta_phrases', {}).get('linkedin', '')}
2. REFERRER: {referrer.get('focus', 'Passive income')}
   CTA: {referrer.get('cta_phrases', {}).get('linkedin', '')}

HASHTAGS: {config.get('common_hashtags', '#Web3Jobs #DecentralizedHiring #UCTalent')}

RULES:
- Write as if you're personally typing this - not a marketing team
- Use your real opinions and observations
- No corporate buzzwords or AI-sounding language
- Be direct, bold, authentic
- Keep posts under platform limits (LinkedIn: ~3000 chars, X: 280 chars)
- Include relevant emojis naturally
- Never sound desperate or salesy
- Sound like a real founder, not a bot

TONE: Founder-to-founder. Direct. No fluff."""


def linkedin_post_prompt(job, referral_link, config):
    """Build prompt for LinkedIn post"""
    title = job.get('title', '')
    bounty = float(job.get('bounty', 0) or 0)
    location = job.get('location', '')
    salary = job.get('salary', '')
    tags = job.get('tags', '')
    
    system_prompt = build_qwen_system_prompt(config)
    
    user_prompt = f"""Write a LinkedIn post for a job opportunity:

Job: {title}
Bounty: ${bounty:,.0f}
Location: {location}
Salary: {salary}
Skills: {tags}
Referral Link (put in comments): {referral_link}

Requirements:
- Hook: Short, attention-grabbing, use your real voice
- Body: Brief but compelling, tell a story
- CTA: Tell them to check comments for the link
- Include 1-3 relevant hashtags
- Keep under 2000 characters
- Write naturally like you're typing to a peer, not a marketing team

Write ONE post only. No explanations."""
    
    return system_prompt, user_prompt


def x_post_prompt(job, referral_link, config):
    """Build prompt for X/Twitter post"""
    title = job.get('title', '')
    bounty = float(job.get('bounty', 0) or 0)
    location = job.get('location', '')
    salary = job.get('salary', '')
    tags = job.get('tags', '')
    
    system_prompt = build_qwen_system_prompt(config)
    
    user_prompt = f"""Write a short X/Twitter post for a job opportunity:

Job: {title}
Bounty: ${bounty:,.0f}
Location: {location}
Skills: {tags}
Referral Link: {referral_link}

Requirements:
- Hook: Attention-grabbing, your real voice
- Body: Brief, punchy, max 200 characters
- CTA: Tell them to check comments for the link
- Include relevant hashtags (1-2 max)
- Keep under 280 characters total

Write ONE tweet only. No explanations."""
    
    return system_prompt, user_prompt


def facebook_post_prompt(job, referral_link, config):
    """Build prompt for Facebook post (Vietnamese/English mix)"""
    title = job.get('title', '')
    bounty = float(job.get('bounty', 0) or 0)
    location = job.get('location', '')
    salary = job.get('salary', '')
    tags = job.get('tags', '')
    
    system_prompt = build_qwen_system_prompt(config)
    
    user_prompt = f"""Write a Facebook post in Vietnamese (or mix EN/VN naturally) for a job opportunity:

Job: {title}
Bounty: ${bounty:,.0f}
Location: {location}
Salary: {salary}
Skills: {tags}
Referral Link: {referral_link}

Requirements:
- Hook: Something relatable to Vietnamese tech community
- Body: Describe opportunity naturally in Vietnamese style
- CTA: Natural call to action in Vietnamese
- Use Vietnamese emojis appropriately
- Include hashtags
- Keep under 500 characters

Write ONE post only. No explanations."""
    
    return system_prompt, user_prompt


def linkedin_message_prompt(job, referral_link, config):
    """Build prompt for LinkedIn outreach message"""
    title = job.get('title', '')
    location = job.get('location', '')
    salary = job.get('salary', '')
    tags = job.get('tags', '')
    
    system_prompt = build_qwen_system_prompt(config)
    
    user_prompt = f"""Write a LinkedIn connection request message for a job referral:

Job: {title}
Location: {location}
Salary: {salary}
Skills: {tags}
Referral Link: {referral_link}

Requirements:
- Short (under 300 characters)
- This is the SAME message you'll send to multiple candidates for this job
- Focus on the JOB opportunity, not their specific profile
- Include the referral link in the message
- Sound like a real founder reaching out, not a templated message
- Include a subtle call to action

Write ONE message only. No explanations."""
    
    return system_prompt, user_prompt


def x_message_prompt(job, referral_link, config):
    """Build prompt for X/Twitter DM outreach message"""
    title = job.get('title', '')
    bounty = float(job.get('bounty', 0) or 0)
    location = job.get('location', '')
    
    system_prompt = build_qwen_system_prompt(config)
    
    user_prompt = f"""Write a short X/Twitter DM message for a job referral:

Job: {title}
Bounty: ${bounty:,.0f}
Location: {location}
Referral Link: {referral_link}

Requirements:
- Very short (under 200 characters)
- Sound like a real founder, not a bot
- Include the referral link
- Include a subtle call to action

Write ONE message only. No explanations."""
    
    return system_prompt, user_prompt


def generate_with_qwen(job, referral_link, config, content_type):
    """Generate content using Qwen"""
    api_key = config.get('qwen_api_key', '')
    
    if not api_key:
        return None
    
    prompt_funcs = {
        'linkedin_post': linkedin_post_prompt,
        'x_post': x_post_prompt,
        'facebook_post': facebook_post_prompt,
        'linkedin_message': linkedin_message_prompt,
        'x_message': x_message_prompt
    }
    
    prompt_func = prompt_funcs.get(content_type)
    if not prompt_func:
        return None
    
    system_prompt, user_prompt = prompt_func(job, referral_link, config)
    
    return call_qwen(system_prompt, user_prompt, api_key)


def generate_with_nvidia(job, referral_link, config, content_type):
    """Generate content using NVIDIA Nemotron"""
    api_key = config.get('nvidia_api_key', '')
    
    if not api_key:
        return None
    
    prompt_funcs = {
        'linkedin_post': linkedin_post_prompt,
        'x_post': x_post_prompt,
        'facebook_post': facebook_post_prompt,
        'linkedin_message': linkedin_message_prompt,
        'x_message': x_message_prompt
    }
    
    prompt_func = prompt_funcs.get(content_type)
    if not prompt_func:
        return None
    
    system_prompt, user_prompt = prompt_func(job, referral_link, config)
    
    return call_nvidia(system_prompt, user_prompt, api_key)


def call_gemini(system_prompt, user_prompt, api_key):
    """Call Gemini 3 Flash Preview using google-genai SDK with retry"""
    import time
    
    try:
        from google import genai
        
        # Set the API key
        import os
        os.environ["GEMINI_API_KEY"] = api_key
        
        client = genai.Client()
        
        # Retry up to 2 times on 503 errors
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=user_prompt,
                    config={
                        "system_instruction": system_prompt,
                        "temperature": 0.9,
                        "max_output_tokens": 2048
                    }
                )
                
                if response.text:
                    return response.text
                    
            except Exception as e:
                error_str = str(e)
                if "503" in error_str or "UNAVAILABLE" in error_str or "high demand" in error_str:
                    if attempt < 1:
                        print(f"  ⏳ Model busy, retrying in 2 seconds...")
                        time.sleep(2)
                        continue
                    else:
                        print("  ⚠️  Gemini 3 overloaded, trying gemini-2.0-flash...")
                        try:
                            response = client.models.generate_content(
                                model="gemini-2.0-flash",
                                contents=user_prompt,
                                config={
                                    "system_instruction": system_prompt,
                                    "temperature": 0.9,
                                    "max_output_tokens": 2048
                                }
                            )
                            return response.text
                        except:
                            print("  ⚠️  All Gemini models unavailable")
                            return None
                else:
                    raise
        
        return None
        
    except ImportError:
        print("  ⚠️  google-genai not installed. Run: pip install google-genai")
        return None
    except Exception as e:
        print(f"  ⚠️  Gemini API error: {e}")
        return None


def generate_with_gemini(job, referral_link, config, content_type):
    """Generate content using Gemini API"""
    api_key = config.get('gemini_api_key', '')
    if not api_key:
        print("  ⚠️  No Gemini API key configured")
        return None
    
    system_prompt = build_system_prompt(config)
    
    title = job.get('title', '')
    bounty = float(job.get('bounty', 0) or 0)
    location = job.get('location', '')
    salary = job.get('salary', '')
    tags = job.get('tags', '')
    
    # Clean up tags - handle various formats from CSV
    if tags and isinstance(tags, str):
        tags = tags.strip()
        # Remove surrounding quotes if present
        if tags.startswith('"') and tags.endswith('"'):
            tags = tags[1:-1]
        # If tags look like "Item1,Item2,Item3" keep as is
        if ',' in tags:
            # Take first 5 tags max for prompt
            tag_list = [t.strip() for t in tags.split(',') if t.strip()]
            tags = ', '.join(tag_list[:5])
    elif not tags:
        # Fall back to extracting from description
        desc = job.get('description', '')
        if desc:
            # Try to extract key skills from description
            common_skills = ['Python', 'Java', 'SQL', 'JavaScript', 'React', 'Node', 'AWS', 'Agile', 'API', 'SQL']
            found = [s for s in common_skills if s.lower() in desc.lower()]
            tags = ', '.join(found[:5]) if found else 'Relevant tech skills'
    
    if content_type == 'linkedin_post':
        user_prompt = f"""Write a LinkedIn post for a job opportunity:

Job: {title}
Bounty: ${bounty:,.0f}
Location: {location}
Skills (INCLUDE AT LEAST 2): {tags}
Referral Link in comment

Requirements:
- Hook: Short, attention-grabbing
- Body: Brief but compelling
- CTA: Tell them to check comments
- Include 1-2 relevant hashtags
- Keep under 2000 characters
- Write naturally like a founder, not a marketing team

Write ONE post only. No explanations."""
        
    elif content_type == 'x_post':
        user_prompt = f"""Write a short X/Twitter post for a job opportunity:

Job: {title}
Bounty: ${bounty:,.0f}
Location: {location}
Skills: {tags}
Referral Link: {referral_link}

Requirements:
- Hook: Attention-grabbing, short
- Body: Brief, punchy, max 200 characters
- CTA: Tell them to check comments for the link
- Include 1-2 relevant hashtags max
- Keep under 280 characters total

Write ONE tweet only. No explanations."""
        
    elif content_type == 'facebook_post':
        user_prompt = f"""Write a Facebook post in Vietnamese (or mix EN/VN naturally) for a job opportunity:

Job: {title}
Bounty: ${bounty:,.0f}
Location: {location}
Skills: {tags}
Referral Link: {referral_link}

Requirements:
- Hook: Something relatable to Vietnamese tech community
- Body: Describe opportunity naturally in Vietnamese style
- CTA: Natural call to action in Vietnamese
- Use Vietnamese emojis appropriately
- Include hashtags

Write ONE post only. No explanations."""
        
    elif content_type == 'outreach_message':
        user_prompt = f"""Write a LinkedIn connection request message for a job referral:

Job: {title}
Location: {location}
Salary: {salary}
Skills: {tags}
Referral Link: {referral_link}

Requirements:
- Short (under 300 characters)
- This is the SAME message you'll send to multiple candidates for this job
- Focus on the JOB opportunity, not their specific profile
- Include the referral link in the message
- Sound like a real founder reaching out, not a templated message
- Include a subtle call to action

Write ONE message only. No explanations."""
        
    else:
        return None
    
    print(f"  🤖 Calling Gemini API for {content_type}...")
    return call_gemini(system_prompt, user_prompt, api_key)


# ─── Job Fetching ───────────────────────────────────────────────────────────

def get_previous_job_ids():
    """Read from single persistent CSV and collect job titles to skip"""
    seen_titles = set()
    csv_file = 'uctalent_jobs.csv'
    
    if os.path.exists(csv_file):
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    seen_titles.add(row['title'].strip().lower())
        except Exception:
            pass
    
    return seen_titles


def _extract_jobs_from_page(url, headers):
    """Extract jobs from a UCTalent page via __NEXT_DATA__.
    Handles both /jobs (1 query with jobs) and /jobs/bounties 
    (query[0]=meta, query[1]=jobs) structures.
    Returns list of raw job dicts.
    """
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    
    match = re.search(r'__NEXT_DATA__"[^>]*>([^<]+)', resp.text)
    if not match:
        return None
    
    data = json.loads(match.group(1))
    queries = data['props']['pageProps']['dehydratedState']['queries']
    
    # Scan all queries for jobs arrays
    all_jobs = []
    for q in queries:
        state = q.get('state', {})
        dk = state.get('data', {})
        inner = dk.get('data', dk)
        if isinstance(inner, dict):
            jobs = inner.get('jobs', [])
            if jobs:
                all_jobs.extend(jobs)
    
    return all_jobs if all_jobs else None


def fetch_bounty_jobs(limit=25):
    """Fetch jobs with bounty from UCTalent by extracting Next.js data.
    Tries /jobs/bounties first (shows only bounty jobs), then /jobs as fallback.
    No upper bounty limit — all bounties are valid (can be $200k+).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    # Try /jobs/bounties first (user says more jobs there)
    urls_to_try = [
        "https://uctalent.io/jobs/bounties",
        "https://uctalent.io/jobs",
    ]
    
    all_jobs = None
    for url in urls_to_try:
        all_jobs = _extract_jobs_from_page(url, headers)
        if all_jobs:
            break
    
    if not all_jobs:
        raise Exception("Could not extract jobs from UCTalent. Both /jobs/bounties and /jobs failed.")
    
    # Deduplicate by ID
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        jid = job.get('id', '')
        if jid and jid not in seen:
            seen.add(jid)
            unique_jobs.append(job)
    
    # VND to USD rate (approximate)
    VND_TO_USD = 25000
    
    bounty_jobs = []
    for job in unique_jobs:
        value_obj = job.get('referral', {}).get('value', {})
        raw_cents = int(value_obj.get('raw_cents', '0'))
        iso_code = value_obj.get('iso_code', 'USD')
        
        # Convert to USD for consistent sorting/comparison
        if iso_code == 'VND':
            bounty_usd = raw_cents / VND_TO_USD
            bounty_display = f"{raw_cents:,.0f} VND"
        else:
            # USD: raw_cents is in cents
            bounty_usd = raw_cents / 100
            bounty_display = f"${raw_cents/100:,.0f}"
        
        # Only skip $0 bounty (internships)
        if bounty_usd > 0:
            location_val = job.get('location', {}).get('value', '') or ''
            bounty_jobs.append({
                'id': job['id'],
                'title': job['title'],
                'bounty': bounty_usd,
                'bounty_display': bounty_display,
                'bounty_currency': iso_code,
                'priority': job.get('priority', 'normal'),
                'location': location_val,
                'salary': job.get('salary', {}).get('text', '') or '',
                'tags': [tag['name'] for tag in job.get('tags', [])],
            })
    
    # Sort by USD bounty descending (highest value first)
    bounty_jobs.sort(key=lambda j: j['bounty'], reverse=True)
    
    return bounty_jobs[:limit]


def fetch_job_description(job_id, job_title):
    """Fetch full job description from detail page"""
    encoded_title = urllib.parse.quote(job_title.replace(' ', '-').replace('/', '-'))
    url = f"https://uctalent.io/jobs/detail/{encoded_title}.{job_id}"
    
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        about_header = soup.find(string=re.compile(r'About the Job', re.IGNORECASE))
        if about_header:
            section = about_header.find_parent().find_next_sibling()
            if section:
                return section.get_text(strip=True)
        
        title_tag = soup.find('h5', string=re.compile(re.escape(job_title[:30])))
        if title_tag:
            content = title_tag.find_next_sibling('p')
            if content:
                return content.get_text(strip=True)
        
        return "Description not available"
    except Exception as e:
        print(f"  Warning: Could not fetch description for {job_title}: {e}")
        return "Description not available"


# ─── Query & Message Generation ─────────────────────────────────────────────

def simplify_job_title(job_title):
    """Extract core role from job title for LinkedIn search"""
    title = job_title.strip()
    # Remove parenthetical skill lists — they go into skills instead
    title = re.sub(r'\([^)]*\)', '', title)
    title = re.sub(r'\[[^\]]*\]', '', title)
    title = re.sub(r'\s[-–—]\s.*$', '', title)
    if '/' in title:
        parts = [p.strip() for p in title.split('/')]
        title = max(parts, key=lambda p: len(p.split()))
    title = re.sub(r'^R&D\s+', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*[-–]?\s*(middle|junior)\s+level', '', title, flags=re.IGNORECASE)
    if title.isupper() and len(title) > 10:
        title = title.title()
    title = title.strip()
    title = re.sub(r'\s+', ' ', title)
    stop_words = {'for', 'and', 'or', 'the', 'a', 'an', 'in', 'at', 'to', 'of', 'with'}
    words = [w for w in title.split() if w.lower() not in stop_words]
    title = ' '.join(words)
    words = title.split()
    if len(words) > 4:
        title = ' '.join(words[:4])
    return title


def _is_skill_token(token):
    """Check if a token looks like a genuine skill vs. a role/seniority descriptor."""
    non_skills = {
        'ceo', 'cto', 'cfo', 'cio', 'coo', 'vp', 'vice president',
        'manager', 'senior', 'junior', 'mid', 'middle', 'lead', 'staff',
        'principal', 'director', 'head', 'associate', 'entry', 'level',
        'engineer', 'developer', 'analyst', 'specialist', 'consultant',
        'designer', 'admin', 'coordinator', 'officer', 'representative',
        'intern', 'apprentice', 'fellow', 'architect',
        'hybrid', 'remote', 'onsite', 'on-site',
        'solution', 'strategy', 'strategies', 'management',
        'digital', 'asset', 'quantitative', 'institutional',
    }
    token_lower = token.lower().strip()
    # Exact match
    if token_lower in non_skills:
        return False
    # Any-word match: if any word in the token is a non-skill, reject it
    words = token_lower.split()
    for w in words:
        if w in non_skills:
            return False
    return True


def extract_skills_from_title(title):
    """Extract comma-separated skills from title parentheses like (React, NextJS, TypeScript).
    
    Cleans up artifacts like 'and TypeScript' -> 'TypeScript'.
    Filters out role/seniority descriptors. Splits on em-dash to extract tech terms.
    Handles slash-separated tokens like 'Senior/ Mid level'.
    """
    skills = []
    parens = re.findall(r'\(([^)]+)\)', title)
    for paren in parens:
        # Split on slashes first to handle 'Senior/ Mid level'
        slash_parts = [p.strip() for p in re.split(r'/', paren)]
        for slash_part in slash_parts:
            # Also split on commas within each slash part
            comma_parts = [p.strip() for p in re.split(r'[,\;]', slash_part)]
            for p in comma_parts:
                # Remove leading conjunctions
                p = re.sub(r'^(and|or)\s+', '', p, flags=re.IGNORECASE).strip()
                
                # Split on em-dash / en-dash — take the right side if left is descriptive
                if '\u2013' in p:  # em-dash
                    p = p.split('\u2013')[-1].strip()
                elif '\u2014' in p:  # en-dash
                    p = p.split('\u2014')[-1].strip()
                
                # Skip if empty or non-skill token
                if p and _is_skill_token(p.strip()):
                    skills.append(p.strip())
    return skills


def _word_boundary_match(skill, text):
    """Check if skill exists in text using word boundaries to avoid substring false positives."""
    # Escape special regex chars in skill
    escaped = re.escape(skill)
    # For multi-word skills, check each word independently
    words = skill.lower().split()
    if len(words) > 1:
        # Multi-word: all words must appear near each other
        pattern = escaped
    else:
        # Single word: use word boundaries
        pattern = r'\b' + escaped + r'\b'
    return bool(re.search(pattern, text, re.IGNORECASE))


def _extract_role_keywords(title):
    """Extract role-level keywords from title for fallback skill mapping.
    
    Unlike extract_skills_from_title, this keeps ALL words including 
    seniority levels to use as lookup keys. Also generates compound keywords.
    """
    title = title.strip()
    # Remove parenthetical content
    title = re.sub(r'\([^)]*\)', '', title)
    title = re.sub(r'\[[^\]]*\]', '', title)
    # Split on slashes and take all parts
    parts = [p.strip().lower() for p in re.split(r'/', title)]
    # Remove R&D prefix
    parts = [re.sub(r'^r&d\s+', '', p).strip() for p in parts]
    
    keywords = []
    for part in parts:
        if part:
            keywords.append(part)
            # Also add individual words as potential matches
            words = part.split()
            for i in range(len(words)):
                for j in range(i + 1, len(words) + 1):
                    compound = ' '.join(words[i:j])
                    if compound not in keywords:
                        keywords.append(compound)
    return keywords


def extract_must_have_skills(job_title, job_description, tags):
    """Extract must-have skills with priority ordering.
    
    Priority:
    1. Skills explicitly listed in title parentheses (e.g., React, NextJS, TypeScript)
    2. Specific API tags (exclude generic ones like "Engineering", "Services")
    3. Common technical skills from description text (with word-boundary matching)
    4. Role-specific fallback based on job title keywords
    """
    must_have = []
    seen = set()
    
    # Generic tags to exclude — too broad for targeting LinkedIn profiles
    generic_tags = {
        'engineering', 'software', 'it services', 'services', 'management',
        'engineering management', 'software and it services',
        'application programming interface (api)',
        'sale or bd', 'business to business (b2b)', 'product', 'problem solving',
        'design', 'development', 'analytics', 'data analytics',
        'qaqc', 'executive management', 'partnership',
    }
    
    # Single-char or very short tokens to ignore
    short_tokens = {'llm', 'api', 'ui', 'ux', 'bd', 'cio', 'cto', 'ceo', 'cfo', 'hr', 'it'}
    
    # Step 1: Extract skills from title parentheses (highest priority)
    title_skills = extract_skills_from_title(job_title)
    for s in title_skills:
        s_lower = s.lower()
        if s_lower not in seen and len(s_lower) > 1:
            seen.add(s_lower)
            must_have.append(s)
    
    # Step 2: Filter tags by specificity
    for tag in tags:
        tag_lower = tag.lower().strip()
        if tag_lower in generic_tags:
            continue
        if tag_lower in short_tokens:
            continue
        if tag_lower not in seen and len(tag_lower) > 3:
            seen.add(tag_lower)
            must_have.append(tag)
    
    # Step 3: Fall back to common technical skills found in description
    # Use word-boundary matching to avoid false positives (e.g., "go" won't match inside "engineering")
    high_quality_skills = [
        "python", "javascript", "typescript", "react", "next.js", "nextjs", "node.js", "nodejs",
        "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "k8s",
        "terraform", "argocd", "crossplane", "linux", "ci/cd", "cicd",
        "java", "golang", "go", "rust", "swift", "kotlin", "flutter",
        "mongodb", "postgresql", "mysql", "redis", "elasticsearch",
        "machine learning", "deep learning", "nlp", "computer vision",
        "ai automation", "claude", "cursor", "llm", "prompt engineering",
        "solidity", "smart contracts", "blockchain", "web3", "defi",
        "android", "ios", "mobile development", "embedded systems",
        "test automation", "selenium", "cypress", "playwright",
        "game development", "unity", "unreal engine", "liveops",
        "silicon validation", "soc", "asic", "firmware", "bsp", "aosp",
        "product owner", "product management", "scrum", "agile",
        "digital marketing", "sales", "business development",
        "full stack", "backend", "frontend", "devops",
        "rest api", "graphql", "microservices", "git", "github",
        "consumer insights", "data science", "data engineering",
    ]
    
    desc_lower = job_description.lower()
    for skill in high_quality_skills:
        if skill not in seen and _word_boundary_match(skill, desc_lower):
            seen.add(skill.lower())
            must_have.append(skill)
        if len(must_have) >= 5:
            break
    
    # Step 4: Role-specific fallback — only if NO skills were found yet
    if not must_have:
        title_lower = job_title.lower()
        role_skill_map = {
            'devops': ['linux', 'docker', 'kubernetes', 'ci/cd', 'terraform'],
            'cloud': ['aws', 'azure', 'gcp', 'docker', 'linux'],
            'embedded': ['c++', 'firmware', 'bsp', 'aosp', 'linux'],
            'android': ['android', 'kotlin', 'java', 'bdk', 'ndk'],
            'sales': ['sales', 'business development', 'crm', 'pipeline'],
            'product owner': ['product management', 'scrum', 'agile', 'analytics'],
            'test automation': ['selenium', 'cypress', 'playwright', 'python', 'java'],
            'game': ['unity', 'unreal engine', 'c#', 'game development', 'liveops'],
            'ai': ['python', 'machine learning', 'deep learning', 'nlp', 'pytorch'],
            'backend': ['python', 'java', 'golang', 'node.js', 'sql', 'docker'],
            'frontend': ['react', 'typescript', 'css', 'html', 'javascript'],
            'full-stack': ['react', 'node.js', 'typescript', 'sql', 'docker'],
            'software engineer': ['java', 'python', 'javascript', 'sql', 'docker'],
            'principal': ['java', 'python', 'system design', 'architecture'],
            'senior software': ['java', 'python', 'javascript', 'sql', 'docker'],
            'ceo': ['strategy', 'fundraising', 'business development'],
            'head of ai': ['python', 'machine learning', 'pytorch', 'leadership'],
            'analyst': ['excel', 'sql', 'python', 'tableau', 'power bi'],
            'consumer insights': ['sql', 'python', 'tableau', 'statistics', 'analytics'],
        }
        for keyword, fallback_skills in role_skill_map.items():
            if keyword in title_lower:
                for skill in fallback_skills:
                    if skill not in seen and _word_boundary_match(skill, desc_lower):
                        seen.add(skill.lower())
                        must_have.append(skill)
                    if len(must_have) >= 3:
                        break
                if must_have:
                    break
        
        # Second pass: reverse matching — check if any map key is contained in the keyword
        if not must_have:
            role_keywords = _extract_role_keywords(job_title)
            for kw in role_keywords:
                for map_key, fallback_skills in role_skill_map.items():
                    if map_key in kw:
                        for skill in fallback_skills:
                            if skill not in seen and _word_boundary_match(skill, desc_lower):
                                seen.add(skill.lower())
                                must_have.append(skill)
                            if len(must_have) >= 3:
                                break
                        if must_have:
                            break
                if must_have:
                    break
        
        # Final pass: if description is unusable (generic/not available), return 
        # generic engineering skills based on role category only
        if not must_have:
            generic_tech = ['java', 'python', 'javascript', 'sql', 'docker']
            for kw in role_keywords:
                for map_key, fallback_skills in role_skill_map.items():
                    if map_key in kw:
                        # Use top 3 skills from the matched category regardless of desc
                        for skill in fallback_skills[:3]:
                            if skill not in seen:
                                seen.add(skill.lower())
                                must_have.append(skill)
                        break
                if must_have:
                    break
    
    return must_have[:5]


def extract_language_skills(description):
    """Extract language requirements from job description"""
    languages = {
        'vietnamese': 'vietnamese',
        'tiếng việt': 'vietnamese',
        'english': 'english',
        'tiếng anh': 'english',
        'mandarin': 'mandarin',
        'tiếng trung': 'mandarin',
        'chinese': 'chinese',
        'japanese': 'japanese',
        'tiếng nhật': 'japanese',
        'korean': 'korean',
        'tiếng hàn': 'korean',
        'french': 'french',
        'tiếng pháp': 'french',
        'german': 'german',
        'tiếng đức': 'german',
        'spanish': 'spanish',
        'tiếng tây ban nha': 'spanish',
    }
    
    found = []
    desc_lower = description.lower()
    
    for key, value in languages.items():
        if key in desc_lower and value not in found:
            found.append(value)
    
    return found


def extract_domain_expertise(description, tags):
    """Extract domain/industry expertise from job description"""
    domains = {
        'fintech': ['fintech', 'financial technology', 'banking', 'payments', 'payment'],
        'healthcare': ['healthcare', 'health tech', 'medical', 'biotech', 'life sciences'],
        'ecommerce': ['ecommerce', 'e-commerce', 'retail tech', 'marketplace', 'commerce'],
        'saas': ['saas', 'enterprise software', 'b2b software', 'cloud platform'],
        'gaming': ['gaming', 'game development', 'interactive entertainment'],
        'crypto': ['cryptocurrency', 'blockchain', 'web3', 'defi', 'nft', 'token'],
        'ai_ml': ['artificial intelligence', 'machine learning', 'deep learning', 'ml ops'],
        'cybersecurity': ['cybersecurity', 'infosec', 'information security', 'security'],
        'logistics': ['logistics', 'supply chain', 'shipping', 'transportation'],
        'edtech': ['edtech', 'education technology', 'learning', 'training platform'],
        'hr_tech': ['hr tech', 'human resources', 'recruiting', 'talent acquisition'],
        'adtech': ['adtech', 'advertising technology', 'mar tech', 'marketing technology'],
        'insurtech': ['insurtech', 'insurance technology'],
        'proptech': ['proptech', 'real estate technology', 'property tech'],
    }
    
    found = []
    desc_lower = description.lower()
    
    # Check tags first
    for tag in tags:
        tag_lower = tag.lower()
        for domain, keywords in domains.items():
            if any(kw in tag_lower for kw in keywords):
                if domain not in found:
                    found.append(domain)
    
    # Check description
    for domain, keywords in domains.items():
        if domain not in found:
            if any(kw in desc_lower for kw in keywords):
                found.append(domain)
    
    return found


def generate_boolean_query(job_title, job_description, tags, location):
    """Generate Google Boolean search query for LinkedIn profiles.
    
    Strategy:
    - Role title in quotes (from simplified job title)
    - Must-have skills with OR grouping (prioritized)
    - Domain expertise (if identified from description)
    - Language requirements (if specified)
    - Location if specified
    """
    query_parts = ["site:linkedin.com/in"]
    
    # Part 1: Clean role title
    title_clean = simplify_job_title(job_title)
    if title_clean and len(title_clean) > 3:
        query_parts.append(f'"{title_clean}"')
    
    # Part 2: Must-have skills (priority ordered)
    skills = extract_must_have_skills(job_title, job_description, tags)
    
    if skills:
        # Deduplicate while preserving order
        seen = set()
        unique_skills = []
        for s in skills:
            s_lower = s.lower()
            if s_lower not in seen:
                seen.add(s_lower)
                unique_skills.append(s)
        
        skills_str = " OR ".join([f'"{s}"' for s in unique_skills[:5]])
        query_parts.append(f"({skills_str})")
    
    # Part 3: Domain expertise (from description analysis)
    domains = extract_domain_expertise(job_description, tags)
    if domains:
        # Use most specific domain as additional filter
        primary_domain = domains[0]
        domain_map = {
            'fintech': '"fintech" OR "financial technology"',
            'healthcare': '"healthcare" OR "health tech"',
            'ecommerce': '"ecommerce" OR "e-commerce" OR "marketplace"',
            'gaming': '"gaming" OR "game development"',
            'crypto': '"web3" OR "blockchain" OR "defi"',
            'ai_ml': '"machine learning" OR "artificial intelligence"',
            'cybersecurity': '"cybersecurity" OR "infosec"',
        }
        if primary_domain in domain_map:
            query_parts.append(f"({domain_map[primary_domain]})")
    
    # Part 4: Language requirements (if specified in description)
    languages = extract_language_skills(job_description)
    if languages:
        lang_str = " OR ".join([f'"{lang}"' for lang in languages])
        query_parts.append(f"({lang_str})")
    
    # Part 5: Location
    if location:
        query_parts.append(f'"{location}"')
    
    return " ".join(query_parts)


def generate_outreach_message(job_title, job_description, location, salary, tags, referral_link=None, name=None):
    """Generate a customized outreach message template for the job"""
    key_skills = tags[:3] if tags else ["relevant skills"]
    skills_str = ", ".join(key_skills)
    clean_title = re.sub(r'\([^)]*\)', '', job_title).strip()
    location_line = f"based in {location}" if location else ""
    salary_line = f" ({salary})" if salary else ""
    
    if not name:
        # Try to get name from config as fallback
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            name = config.get('name', 'Your Name')
        except Exception:
            name = 'Your Name'
    
    return f"""Hi [FirstName],

I came across your profile and was impressed by your experience. We're currently hiring for a {clean_title} role {location_line}{salary_line}, and your background seems like a great match.

Key skills we're looking for: {skills_str}.

Would you be open to a quick chat to explore this opportunity?

Best regards,
{name}""".strip()


# ─── Referral Link Extraction ───────────────────────────────────────────────

def execute_js(js_code, timeout=10):
    """Execute JavaScript in the active Chrome tab via CDP (cross-platform)"""
    from chrome_utils import execute_js as _cdp_execute_js
    return _cdp_execute_js(js_code, timeout=timeout)


def switch_to_last_tab():
    """Switch Chrome to the last opened tab via CDP (cross-platform)"""
    from chrome_utils import switch_to_last_tab as _cdp_switch
    return _cdp_switch()


def navigate_to_url(url):
    """Navigate the current active tab to a URL via CDP (cross-platform)"""
    from chrome_utils import navigate_to_url as _cdp_navigate
    return _cdp_navigate(url)


def open_url_in_tab(url):
    """Open URL in a new Chrome tab via CDP (cross-platform)"""
    from chrome_utils import open_url_in_tab as _cdp_open
    return _cdp_open(url)


def get_job_url(job_id, job_title):
    """Build job detail URL"""
    encoded_title = urllib.parse.quote(job_title.replace(' ', '-').replace('/', '-'))
    return f"https://uctalent.io/jobs/detail/{encoded_title}.{job_id}"


def extract_referral_link_api(job_id):
    """Try to extract referral link via API (usually fails due to dynamic generation)"""
    url = f"https://uctalent.io/jobs/detail/temp.{job_id}"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if "referral" in response.text.lower():
            match = re.search(r'https?://[^"\s]*uctalent\.io/referral/[^"\s]*', response.text)
            if match:
                return match.group(0)
    except Exception:
        pass
    return None


def extract_referral_link():
    """Click Refer & Earn button, then COPY LINK button in modal, read from clipboard"""
    time.sleep(5)
    
    # Click Refer & Earn button
    click_js = """(function() {
        var buttons = document.querySelectorAll('button');
        for (var i = 0; i < buttons.length; i++) {
            var text = buttons[i].textContent.trim();
            if (text === 'Refer & Earn') {
                var parent = buttons[i].closest('header, nav');
                if (!parent) { buttons[i].click(); return 'clicked'; }
            }
        }
        return 'not_found';
    })();"""
    
    result = execute_js(click_js)
    if result != 'clicked':
        return None
    
    time.sleep(3)
    
    # Click COPY LINK button
    copy_js = """(function() {
        var buttons = document.querySelectorAll('button');
        for (var i = 0; i < buttons.length; i++) {
            var text = buttons[i].textContent.trim();
            if (text.includes('COPY') && text.includes('LINK')) {
                buttons[i].click(); return 'clicked';
            }
        }
        return 'not_found';
    })();"""
    
    result = execute_js(copy_js)
    time.sleep(1)
    
    # Read clipboard (cross-platform)
    clip_result = get_clipboard()
    if clip_result and "uctalent.io/referral" in clip_result:
        return clip_result
    
    # Fallback: extract from input
    extract_js = """(function() {
        var inputs = document.querySelectorAll('input');
        for (var i = 0; i < inputs.length; i++) {
            if (inputs[i].value && inputs[i].value.includes('uctalent.io/referral')) {
                return inputs[i].value;
            }
        }
        return 'not_found';
    })();"""
    return execute_js(extract_js)


# ─── Config Loading ────────────────────────────────────────────────────────

def load_config():
    """Load personal context from config.json"""
    default_config = {
        "name": "Your Name",
        "role": "Your Role",
        "location": "Your City, Vietnam",
        "personal_story": "Write your story here",
        "mission_statement": "Write your mission here",
        "brand_voice": "Bold, authentic, founder-to-founder",
        "linkedin_url": "https://linkedin.com/in/yourprofile",
        "uctalent_url": "https://uctalent.io",
        "common_hashtags": "#Web3Jobs #DecentralizedHiring #UCTalent #BlockchainRecruiting",
        "qwen_api_key": "",
        "nvidia_api_key": "",
        "use_nvidia": False,
        "use_gemini": False,
        "cta_phrases": {
            "linkedin": "DM me if you want an intro or more details 👉",
            "twitter": "RT if you know someone perfect for this 🚀",
            "facebook": "Share với bạn bè nếu thấy phù hợp! 💪"
        }
    }
    
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            for key in default_config:
                if key not in config:
                    config[key] = default_config[key]
            return config
    except FileNotFoundError:
        print("  ⚠️  config.json not found, using defaults")
        return default_config


# ─── Social Media Post Generation ───────────────────────────────────────────

def select_target(config):
    """Randomly select a target audience for this post"""
    targets = config.get('targets', {})
    if not targets:
        return 'referrer'  # default
    target_names = list(targets.keys())
    return random.choice(target_names)


def clean_title(title):
    """Clean job title for social posts"""
    title = re.sub(r'\([^)]*\)', '', title)
    title = re.sub(r'\[[^\]]*\]', '', title)
    title = re.sub(r'\s[-–—]\s.*$', '', title)
    return title.strip()


def extract_key_skills(job_description, tags):
    """Extract most relevant 2-3 skills from description and tags"""
    # Convert tags to list if it's a string
    if isinstance(tags, str):
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
    else:
        tag_list = list(tags) if tags else []
    
    # Filter out generic/meaningless tags
    exclude = {'product', 'services', 'management', 'engineering', 'business', 'information technology'}
    filtered = [t for t in tag_list if t.lower() not in exclude]
    
    return filtered[:3] if filtered else tag_list[:3] if tag_list else ["relevant experience"]


def generate_authentic_hook(config, job, target_name):
    """Generate authentic hook using founder logs when available"""
    founder_logs = config.get('founder_logs', '').strip()
    industry_takes = config.get('industry_takes', '').strip()
    recent_insights = config.get('recent_insights', '').strip()
    
    hooks = []
    
    # Use founder logs if available
    if founder_logs:
        log_lines = [line.strip() for line in founder_logs.split('\n') if line.strip()]
        if log_lines:
            import random
            hooks.append(random.choice(log_lines))
    
    # Use industry takes if available
    if industry_takes:
        take_lines = [line.strip() for line in industry_takes.split('\n') if line.strip()]
        if take_lines:
            hooks.append(random.choice(take_lines))
    
    # Use recent insights if available
    if recent_insights:
        insight_lines = [line.strip() for line in recent_insights.split('\n') if line.strip()]
        if insight_lines:
            hooks.append(random.choice(insight_lines))
    
    # Fallback to default hooks if no custom content
    if not hooks:
        if target_name == 'talent':
            hooks = [
                "I've been headhunting this role all week.",
                "This is one of the most interesting {title} roles I've seen recently.",
                "I personally reviewed 50+ profiles for this position."
            ]
        else:
            hooks = [
                "I've been looking for a {title} for one of my clients.",
                "Great opportunity for someone with the right skills.",
                "This {title} role is open and I'm helping them find the right fit."
            ]
    
    title = job.get('title', '')
    bounty = float(job.get('bounty', 0) or 0)
    return hooks[0].format(title=title, bounty=bounty)


def generate_linkedin_post(job, referral_link, config):
    """Generate short LinkedIn main post (no external links)"""
    # Try AI generation (NVIDIA first, then Qwen, then Gemini)
    if config.get('use_nvidia', False):
        nvidia_result = generate_with_nvidia(job, referral_link, config, 'linkedin_post')
        if nvidia_result:
            return clean_content(nvidia_result.strip())
    
    if config.get('use_qwen', False):
        qwen_result = generate_with_qwen(job, referral_link, config, 'linkedin_post')
        if qwen_result:
            return clean_content(qwen_result.strip())
    
    if config.get('use_gemini', False):
        gemini_result = generate_with_gemini(job, referral_link, config, 'linkedin_post')
        if gemini_result:
            return clean_content(gemini_result.strip())
    
    # Fall back to template-based generation
    title = clean_title(job['title'])
    bounty = float(job.get('bounty', 0) or 0)
    location = job.get('location', '')
    salary = job.get('salary', '')
    desc = job.get('description', '')
    tags = job.get('tags', [])
    
    skills = extract_key_skills(desc, tags)
    skills_str = ", ".join(skills)
    
    # Randomly select target audience
    target_name = select_target(config)
    target = config.get('targets', {}).get(target_name, {})
    
    name = config.get('name', 'Your Name')
    role = config.get('role', 'Your Role')
    
    # Generate authentic hook
    authentic_hook = generate_authentic_hook(config, job, target_name)
    
    if target_name == 'talent':
        return clean_content(f"""{authentic_hook}

The best engineers aren't on job boards — they're quietly scrolling LinkedIn, waiting for the right opportunity.

I'm helping a client hire a {title}:
📍 {location or 'Remote'}
💰 {salary or 'Competitive'}
🔧 Skills: {skills_str}

No more black-hole applications. No ghosting. Just direct connections.

P.S. If you want an intro to the hiring team, DM me.

{name} | {role}

{config.get('common_hashtags', '#Web3Jobs #UCTalent')}""".strip())
    else:
        return clean_content(f"""{authentic_hook}

Right now, one of our clients is hiring a {title}:
📍 {location or 'Remote'}
{'💰 ' + salary if salary else ''}{'💰 Competitive' if not salary else ''}
🔧 Skills: {skills_str}

Know someone who fits? Let me know!

{name} | {role}

{config.get('common_hashtags', '#Web3Jobs #UCTalent')}""".strip())


def generate_linkedin_comment(job, referral_link, config):
    """Generate LinkedIn comment with referral link"""
    target_name = select_target(config)
    
    if target_name == 'talent':
        return clean_content(f"Apply directly via our AI Agent — no middlemen, no ghosting:\n{referral_link}")
    else:
        return clean_content(f"Apply directly via our AI Agent:\n{referral_link}")


def generate_x_post(job, referral_link, config):
    """Generate short X/Twitter post (no external links)"""
    if config.get('use_nvidia', False):
        nvidia_result = generate_with_nvidia(job, referral_link, config, 'x_post')
        if nvidia_result:
            return clean_content(nvidia_result.strip())
    
    if config.get('use_qwen', False):
        qwen_result = generate_with_qwen(job, referral_link, config, 'x_post')
        if qwen_result:
            return clean_content(qwen_result.strip())
    
    if config.get('use_gemini', False):
        gemini_result = generate_with_gemini(job, referral_link, config, 'x_post')
        if gemini_result:
            return clean_content(gemini_result.strip())
    
    title = clean_title(job['title'])
    bounty = float(job.get('bounty', 0) or 0)
    location = job.get('location', '')
    salary = job.get('salary', '')
    desc = job.get('description', '')
    tags = job.get('tags', [])
    
    location_text = f"📍 {location}" if location else "🌏 Remote"
    salary_text = f"💰 {salary}" if salary else ""
    skills = extract_key_skills(desc, tags)[:2]
    skills_str = " + ".join(skills) if skills else ""
    
    target_name = select_target(config)
    target = config.get('targets', {}).get(target_name, {})
    
    # Generate authentic hook
    authentic_hook = generate_authentic_hook(config, job, target_name)
    
    if target_name == 'talent':
        return clean_content(f"""{authentic_hook}

One client is hiring a {title}:

{skills_str}
{salary_text}
{location_text}

Link in comments 👇

{config.get('common_hashtags', '#Web3Jobs #UCTalent')}""")
    else:
        return clean_content(f"""{authentic_hook}

Know someone who fits? Link in comments 👇

{config.get('common_hashtags', '#Web3Jobs #UCTalent')}""")


def generate_x_comment(job, referral_link, config):
    """Generate X/Twitter comment with referral link"""
    target_name = select_target(config)
    
    if target_name == 'talent':
        return clean_content(f"Apply directly via our AI Agent:\n{referral_link}")
    else:
        return clean_content(f"Apply directly:\n{referral_link}")


def generate_facebook_post(job, referral_link, config):
    """Generate short Facebook post in Vietnamese (no external links)"""
    if config.get('use_nvidia', False):
        nvidia_result = generate_with_nvidia(job, referral_link, config, 'facebook_post')
        if nvidia_result:
            return clean_content(nvidia_result.strip())
    
    if config.get('use_qwen', False):
        qwen_result = generate_with_qwen(job, referral_link, config, 'facebook_post')
        if qwen_result:
            return clean_content(qwen_result.strip())
    
    if config.get('use_gemini', False):
        gemini_result = generate_with_gemini(job, referral_link, config, 'facebook_post')
        if gemini_result:
            return clean_content(gemini_result.strip())
    
    title = clean_title(job['title'])
    bounty = float(job.get('bounty', 0) or 0)
    location = job.get('location', '')
    salary = job.get('salary', '')
    desc = job.get('description', '')
    tags = job.get('tags', [])
    
    location_text = f"📍 {location}" if location else "🌏 Làm việc từ xa"
    salary_text = f"💰 {salary}" if salary else ""
    skills = extract_key_skills(desc, tags)
    skills_str = ", ".join(skills)
    
    target_name = select_target(config)
    target = config.get('targets', {}).get(target_name, {})
    
    # Generate authentic hook (translated to Vietnamese context)
    founder_logs = config.get('founder_logs', '').strip()
    industry_takes = config.get('industry_takes', '').strip()
    recent_insights = config.get('recent_insights', '').strip()
    
    vietnamese_hooks = []
    
    # Try to use founder logs (keep original language or translate key insights)
    if founder_logs:
        log_lines = [line.strip() for line in founder_logs.split('\n') if line.strip()]
        if log_lines:
            import random
            vietnamese_hooks.append(f"Tôi đã trải nghiệm thực tế: {random.choice(log_lines)}")
    
    if industry_takes:
        take_lines = [line.strip() for line in industry_takes.split('\n') if line.strip()]
        if take_lines:
            import random
            vietnamese_hooks.append(f"Góc nhìn của tôi về thị trường: {random.choice(take_lines)}")
    
    if recent_insights:
        insight_lines = [line.strip() for line in recent_insights.split('\n') if line.strip()]
        if insight_lines:
            import random
            vietnamese_hooks.append(f"Điều tôi thấy gần đây: {random.choice(insight_lines)}")
    
    if not vietnamese_hooks:
        if target_name == 'talent':
            vietnamese_hooks = [
                "Bạn đã bao giờ apply một công ty và chẳng nghe lại gì chưa?",
                "Tôi đã gặp quá nhiều engineer giỏi bị bỏ qua chỉ vì ATS filter."
            ]
        else:
            vietnamese_hooks = [
                "Thị trường tuyển dụng tech hiện tại: công ty thất vọng vì không tìm được người giỏi.",
                "Một cơ hội việc làm đang cần gấp."
            ]
    
    authentic_hook_vn = vietnamese_hooks[0]
    
    if target_name == 'talent':
        return clean_content(f"""{authentic_hook_vn}

Hiện tại có một vị trí đang cần gấp: {title}

{location_text}
{salary_text}
🔧 Cần: {skills_str}

Apply ngay hoặc giới thiệu người phù hợp!

{config.get('common_hashtags', '#Web3Jobs #TuyenDungIT')}""".strip())
    else:
        return clean_content(f"""{authentic_hook_vn}

Vị trí đang cần gấp: {title}

{location_text}
{salary_text}
🔧 Cần: {skills_str}

Apply hoặc giới thiệu người phù hợp!

{config.get('common_hashtags', '#Web3Jobs #TuyenDungIT')}""".strip())


def generate_facebook_comment(job, referral_link, config):
    """Generate Facebook comment with referral link"""
    target_name = select_target(config)
    
    if target_name == 'talent':
        return clean_content(f"Apply ngay để AI Agent giúp bạn kết nối trực tiếp với hiring manager:\n{referral_link}")
    else:
        return clean_content(f"Apply ngay:\n{referral_link}")


def generate_image_text(job, config):
    """Generate eye-catching text for image/creative - customized for target"""
    title = clean_title(job['title'])
    bounty = float(job.get('bounty', 0) or 0)
    location = job.get('location', '')
    salary = job.get('salary', '')
    
    # Randomly select target audience for image
    target_name = select_target(config)
    
    uctalent_domain = config.get('uctalent_url', 'https://uctalent.io').replace('https://', '').replace('http://', '')
    
    lines = [f"HIRING: {title}", ""]
    
    if target_name == 'talent':
        lines.extend([
            "Stop being ghosted by job apps.",
            "AI matches you directly to hiring managers.",
            "",
            f"📍 {location or 'Remote'}",
        ])
        if salary:
            lines.append(f"💰 {salary}")
        lines.extend([
            "",
            f"Apply via {config.get('name', 'Our')}",
            uctalent_domain
        ])
    else:
        lines.extend([
            f"📍 {location or 'Remote'}",
        ])
        if salary:
            lines.append(f"💰 {salary}")
        lines.extend([
            "",
            f"Apply via {config.get('name', 'Our')}",
            uctalent_domain
        ])
    
    return "\n".join(lines)


def open_draft_tabs(job, referral_link, config):
    """Open draft tabs for each platform with pre-filled content (cross-platform via CDP)"""
    linkedin_content = generate_linkedin_post(job, referral_link, config)
    x_content = generate_x_post(job, referral_link, config)
    fb_content = generate_facebook_post(job, referral_link, config)
    
    # Copy LinkedIn post to clipboard
    set_clipboard(linkedin_content)
    
    # Open LinkedIn feed page
    open_url_in_tab("https://www.linkedin.com/feed/")
    time.sleep(2)
    
    # Try to click compose box
    execute_js("""(function() {
        var buttons = document.querySelectorAll('[aria-label="Start a post"]');
        for (var i = 0; i < buttons.length; i++) { buttons[i].click(); return 'clicked'; }
        return 'not_found';
    })();""")
    time.sleep(2)
    
    # Paste into textarea
    execute_js("""(function() {
        var ta = document.querySelector('textarea');
        if (ta) { ta.focus(); document.execCommand('paste'); return 'pasted'; }
        return 'not_found';
    })();""")
    
    # Open X intent post URL (without link for better reach)
    encoded_x = urllib.parse.quote(x_content)
    open_url_in_tab(f"https://twitter.com/intent/tweet?text={encoded_x}")
    
    # Open Facebook homepage
    open_url_in_tab("https://www.facebook.com/")
    
    return linkedin_content, x_content, fb_content


# ─── Content Generation ─────────────────────────────────────────────────────

def generate_all_posts(results, config):
    """Generate social media posts for jobs that have referral links (STEP 2 OF 2)"""
    print("=" * 70)
    print("STEP 2 OF 2: GENERATING SOCIAL MEDIA POSTS")
    print("=" * 70)
    
    results_with_posts = []
    for i, result in enumerate(results, 1):
        referral_link = result['referral_link'] or '[REFERRAL_LINK]'
        
        if referral_link in ['', '[MANUAL_PASTE]', '[REFERRAL_LINK]', '[NO_LINK]']:
            print(f"  [{i}/{len(results)}] ⚠️  No link: {result['title'][:50]}...")
            results_with_posts.append(result)
        else:
            print(f"  [{i}/{len(results)}] ✅ Generated: {result['title'][:50]}...")
            result['linkedin_post'] = generate_linkedin_post(result, referral_link, config)
            result['x_post'] = generate_x_post(result, referral_link, config)
            result['facebook_post'] = generate_facebook_post(result, referral_link, config)
            result['image_text'] = generate_image_text(result, config)
            result['linkedin_comment'] = generate_linkedin_comment(result, referral_link, config)
            result['x_comment'] = generate_x_comment(result, referral_link, config)
            result['facebook_comment'] = generate_facebook_comment(result, referral_link, config)
            results_with_posts.append(result)
    
    return results_with_posts


def open_draft_tabs_for_all(results, config):
    """Open draft tabs for first job with posts (STEP 2 OF 2)"""
    print("\n" + "=" * 70)
    print("STEP 2 OF 2: OPENING DRAFT TABS FOR SOCIAL POSTS")
    print("=" * 70)
    
    jobs_with_posts = [r for r in results if r.get('linkedin_post') and r['linkedin_post'] != 'Not generated']
    
    if not jobs_with_posts:
        print("  ⚠️  No jobs have posts yet. Add referral links first.\n")
        return
    
    # Display all content for first job
    first_job = jobs_with_posts[0]
    referral_link = first_job['referral_link'] or '[REFERRAL_LINK]'
    
    print("\n" + "=" * 70)
    print(f"  CONTENT PREVIEW — {first_job['title'][:50]}")
    print("=" * 70)
    
    # LinkedIn Post
    print("\n📱 LINKEDIN POST:")
    print("  " + "-" * 60)
    for line in first_job.get('linkedin_post', '').split('\n')[:15]:
        print(f"  {line}")
    print("  " + "-" * 60)
    
    # LinkedIn Comment
    print("\n💬 LINKEDIN COMMENT (add after posting):")
    print("  " + "-" * 60)
    for line in first_job.get('linkedin_comment', '').split('\n'):
        print(f"  {line}")
    print("  " + "-" * 60)
    
    # X/Twitter Post
    print("\n🐦 X/TWITTER POST:")
    print("  " + "-" * 60)
    for line in first_job.get('x_post', '').split('\n')[:15]:
        print(f"  {line}")
    print("  " + "-" * 60)
    
    # X/Twitter Comment
    print("\n💬 X/TWITTER COMMENT (reply to yourself after posting):")
    print("  " + "-" * 60)
    for line in first_job.get('x_comment', '').split('\n'):
        print(f"  {line}")
    print("  " + "-" * 60)
    
    # Facebook Post
    print("\n📘 FACEBOOK POST:")
    print("  " + "-" * 60)
    for line in first_job.get('facebook_post', '').split('\n')[:15]:
        print(f"  {line}")
    print("  " + "-" * 60)
    
    # Facebook Comment
    print("\n💬 FACEBOOK COMMENT (add after posting):")
    print("  " + "-" * 60)
    for line in first_job.get('facebook_comment', '').split('\n'):
        print(f"  {line}")
    print("  " + "-" * 60)
    
    # Image text
    image_text = first_job.get('image_text', '')
    if image_text:
        print("\n🖼️  IMAGE TEXT:")
        print("  " + "-" * 60)
        for line in image_text.split('\n'):
            print(f"  {line}")
        print("  " + "-" * 60)
    
    print()
    print("  💡 Posts have NO external links (better reach).")
    print("     After posting, add referral link as COMMENT using the texts above.")
    print()
    
    confirm_drafts = input("Open draft tabs now? (y/n): ").strip().lower()
    
    if confirm_drafts == 'y':
        linkedin_content, x_content, fb_content = open_draft_tabs(first_job, referral_link, config)
        
        print("\n✅ Draft tabs opened!")
        print("📋 Instructions:")
        print("   1. LinkedIn tab: Paste post → Post → Then add comment with link")
        print("   2. X tab: Review text → Post → Then reply to yourself with link")
        print("   3. Facebook tab: Paste post → Share → Then add comment with link")
        print("\n💡 Full comment texts are displayed above ^^^")
    else:
        print("  Skipped.")
    
    print()


# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    # Fix console encoding for Windows (emoji & Unicode support)
    if hasattr(sys.stdout, 'reconfigure'):
        try: sys.stdout.reconfigure(encoding='utf-8')
        except: pass
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    """
    RUN 1 (no referral links in CSV): Fetch jobs, open tabs for manual link extraction
    RUN 2 (referral links added): Generate social posts with links, open draft tabs
    """
    print("=" * 70)
    print("UCTalent Bounty Jobs - Workflow Automation")
    print("=" * 70)
    
    # CSV file for persistent storage
    csv_filename = 'uctalent_jobs.csv'
    
    # Load personal config
    print("\n📋 Loading personal context...")
    config = load_config()
    print(f"   Name: {config.get('name', 'Your Name')}")
    print(f"   Role: {config.get('role', 'Your Role')}")
    
    print("\n📋 Fetching bounty jobs from UCTalent...")
    
    # Check previous jobs
    previous_titles = get_previous_job_ids()
    if previous_titles:
        print(f"\nFound {len(previous_titles)} jobs in previous list (will skip duplicates)")
    
    # Read existing CSV to find jobs needing processing
    existing_rows = []
    if os.path.exists(csv_filename):
        with open(csv_filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)
    
    existing_titles = {row['title'].strip().lower(): row for row in existing_rows}
    if existing_titles:
        print(f"Found {len(existing_titles)} existing job(s) in CSV (will skip duplicates)\n")
    
    # Fetch bounty jobs from API
    print("\n📊 Fetching bounty jobs from UCTalent...")
    all_jobs = fetch_bounty_jobs(limit=25)
    
    # Filter: keep new jobs only (not in CSV)
    results = []
    
    for job in all_jobs:
        title_lower = job['title'].strip().lower()
        if title_lower not in existing_titles:
            results.append(job)
    
    skipped = len(all_jobs) - len(results)
    if skipped > 0:
        print(f"Skipped {skipped} already-processed job(s)")
    print(f"\n✅ Found {len(results)} new job(s)")
    
    if not results:
        # No new jobs, but we may need to refresh bounty_currency/bounty_display for existing jobs
        print("✅ No new jobs found. Checking if existing jobs need bounty info refresh...")
        
        # Build API job map for existing job title matching
        api_jobs_by_title = {}
        for job in all_jobs:
            api_jobs_by_title[job['title'].strip().lower()] = job
        
        # Update bounty fields for matching existing jobs
        updated_count = 0
        for row in existing_rows:
            title_lower = row.get('title', '').strip().lower()
            if title_lower in api_jobs_by_title:
                api_job = api_jobs_by_title[title_lower]
                if not row.get('bounty_display'):
                    row['bounty_display'] = api_job.get('bounty_display', '')
                    row['bounty_currency'] = api_job.get('bounty_currency', 'USD')
                    row['bounty'] = str(api_job.get('bounty', row.get('bounty', '0')))
                    updated_count += 1
        
        if updated_count:
            # Re-save CSV with updated bounty info
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
            for row in existing_rows:
                row['last_updated'] = now_str
            
            with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
                writer.writeheader()
                writer.writerows(existing_rows)
            print(f"✅ Updated bounty info for {updated_count} existing job(s)")
        else:
            print("   All existing jobs already have bounty info.")
        
        print("\n📋 Run guide.py to work on existing jobs.\n")
        return
    
    # Process each job
    processed_jobs = []
    api_job_map = {}  # Map title -> API job object (for getting ID)
    
    for i, job in enumerate(results, 1):
        print(f"[{i}/{len(results)}] Processing: {job['title']}")
        bdisp = job.get('bounty_display', '')
        if bdisp:
            print(f"  Bounty: {bdisp} | Location: {job['location']}")
        else:
            bounty_val = float(job.get('bounty', 0) or 0)
            print(f"  Bounty: ${bounty_val:,.0f} | Location: {job['location']}")
        
        desc = fetch_job_description(job['id'], job['title'])
        query = generate_boolean_query(job['title'], desc, job['tags'], job['location'])
        
        # Check if this job exists in CSV with a referral link
        title_lower = job['title'].strip().lower()
        existing_row = existing_titles.get(title_lower, {})
        existing_link = existing_row.get('referral_link', '')
        clean_link = existing_link if existing_link and existing_link not in ['', '[MANUAL_PASTE]', '[REFERRAL_LINK]', '[NO_LINK]'] else ''
        
        message = generate_outreach_message(job['title'], desc, job['location'], job['salary'], job['tags'], clean_link, config.get('name'))
        
        # Generate social content if referral link exists
        linkedin_post = existing_row.get('linkedin_post', '') if existing_row else ''
        x_post = existing_row.get('x_post', '') if existing_row else ''
        facebook_post = existing_row.get('facebook_post', '') if existing_row else ''
        image_text = existing_row.get('image_text', '') if existing_row else ''
        linkedin_comment = existing_row.get('linkedin_comment', '') if existing_row else ''
        x_comment = existing_row.get('x_comment', '') if existing_row else ''
        facebook_comment = existing_row.get('facebook_comment', '') if existing_row else ''
        linkedin_profiles = existing_row.get('linkedin_profiles', '') if existing_row else ''
        
        if clean_link and not linkedin_post:
            linkedin_post = generate_linkedin_post(job, clean_link, config)
            x_post = generate_x_post(job, clean_link, config)
            facebook_post = generate_facebook_post(job, clean_link, config)
            image_text = generate_image_text(job, config)
            linkedin_comment = generate_linkedin_comment(job, clean_link, config)
            x_comment = generate_x_comment(job, clean_link, config)
            facebook_comment = generate_facebook_comment(job, clean_link, config)
        
        # Store API job for later ID lookup
        api_job_map[job['title'].strip().lower()] = job
        
        processed_jobs.append({
            'id': job['id'],
            'title': job['title'], 'bounty': float(job['bounty']),
            'bounty_display': job.get('bounty_display', ''),
            'bounty_currency': job.get('bounty_currency', 'USD'),
            'location': job['location'], 'salary': job['salary'],
            'priority': job['priority'], 'description': desc,
            'tags': ','.join(job.get('tags', [])),
            'boolean_query': query, 'outreach_message': message,
            'referral_link': clean_link,
            'linkedin_post': linkedin_post,
            'x_post': x_post,
            'facebook_post': facebook_post,
            'image_text': image_text,
            'linkedin_comment': linkedin_comment,
            'x_comment': x_comment,
            'facebook_comment': facebook_comment,
            'linkedin_profiles': linkedin_profiles, 'status': 'pending',
            'connect_status': 'pending', 'message_status': 'pending',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'last_updated': '',
        })
        print(f"  Query: {query[:80]}...\n")
    
    # Use processed_jobs as results
    results = processed_jobs
    
    print("\n" + "=" * 70)
    print("SAVING JOBS TO CSV")
    print("=" * 70)
    
    csv_filename = 'uctalent_jobs.csv'
    
    # Read existing CSV if exists
    existing_rows = []
    if os.path.exists(csv_filename):
        with open(csv_filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)
    
    # Merge: update existing or add new
    merged = []
    existing_titles = {row['title'].strip().lower(): row for row in existing_rows}
    
    for result in results:
        title_lower = result['title'].strip().lower()
        if title_lower in existing_titles:
            # Preserve user-filled fields before merging new data
            existing_row = existing_titles[title_lower]
            preserved = {
                'id': existing_row.get('id', ''),
                'tags': existing_row.get('tags', ''),
                'referral_link': existing_row.get('referral_link', ''),
                'linkedin_post': existing_row.get('linkedin_post', ''),
                'x_post': existing_row.get('x_post', ''),
                'facebook_post': existing_row.get('facebook_post', ''),
                'image_text': existing_row.get('image_text', ''),
                'linkedin_comment': existing_row.get('linkedin_comment', ''),
                'x_comment': existing_row.get('x_comment', ''),
                'facebook_comment': existing_row.get('facebook_comment', ''),
                'linkedin_profiles': existing_row.get('linkedin_profiles', ''),
                'status': existing_row.get('status', ''),
                'connect_status': existing_row.get('connect_status', ''),
                'message_status': existing_row.get('message_status', ''),
                'created_at': existing_row.get('created_at', ''),
            }
            
            # Merge new data into existing row
            existing_row.update(result)
            
            # Restore preserved fields so user data isn't lost
            existing_row.update(preserved)
            
            merged.append(existing_row)
        else:
            merged.append(result)
    
    # Keep old jobs not in this batch
    for row in existing_rows:
        if row['title'].strip().lower() not in {r['title'].strip().lower() for r in results}:
            merged.append(row)
    
    # Add timestamps
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    for row in merged:
        if not row.get('created_at'):
            row['created_at'] = now_str
        row['last_updated'] = now_str
    
    with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(merged)
    
    print("\n" + "=" * 70)
    total_in_file = len(merged)
    new_count = sum(1 for r in results if r['title'].strip().lower() not in {r2['title'].strip().lower() for r2 in existing_rows})
    existing_count = total_in_file - new_count
    if not os.path.exists(csv_filename):
        print("STEP 1 OF 2 COMPLETE!")
    else:
        print("STEP 2 OF 2 IN PROGRESS...")
    print(f"✅ Saved to: {csv_filename}")
    print(f"✅ Total jobs in file: {total_in_file} ({new_count} new, {existing_count} existing)")
    print("=" * 70)
    
    # Check if any jobs have referral links (RUN 2 only)
    jobs_with_links = sum(1 for r in results 
                          if r.get('referral_link') 
                          and r['referral_link'] not in ['', '[MANUAL_PASTE]', '[REFERRAL_LINK]', '[NO_LINK]'])
    
    if jobs_with_links == 0:
        print("\n⚠️  No jobs have referral links yet.")
        print("\n📋 You're on RUN 2 but no links found.")
        print("   Add referral links to CSV and run again.\n")
        return
    
    # Generate posts for jobs with links (RUN 2)
    results = generate_all_posts(results, config)
    
    # Merge updated results back into CSV
    results_titles = {r['title'].strip().lower(): r for r in results}
    for row in merged:
        title_lower = row['title'].strip().lower()
        if title_lower in results_titles:
            updated = results_titles[title_lower]
            preserved = {
                'referral_link': row.get('referral_link', ''),
                'linkedin_profiles': row.get('linkedin_profiles', ''),
                'status': row.get('status', ''),
                'connect_status': row.get('connect_status', ''),
                'message_status': row.get('message_status', ''),
                'created_at': row.get('created_at', ''),
            }
            
            old_posts = [
                'linkedin_post', 'x_post', 'facebook_post',
                'image_text', 'linkedin_comment', 'x_comment', 'facebook_comment'
            ]
            for field in old_posts:
                if row.get(field) and row[field] not in ['', 'Not generated']:
                    preserved[field] = row[field]
            
            row.update(updated)
            row.update(preserved)
    
    # Save updated CSV with posts (RUN 2)
    with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(merged)
    
    print("\n" + "=" * 70)
    print("STEP 2 OF 2: COMPLETE!")
    print("=" * 70)
    print(f"\n✅ All done! Check {csv_filename} for complete data.")
    print("=" * 70)
    
    if results and os.path.exists(csv_filename):
        print("\n📋 Next steps:")
        print("   • Work on individual jobs using guide.py")
        print("   • Send connection requests (manual, 20-25/day max)")
        print("   • Post on social media using draft tabs")
        print()


if __name__ == "__main__":
    main()
