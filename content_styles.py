"""
Content Styles for UCTalent Outreach & Social Posts.

Each style defines the voice, tone, format, and structure for:
  - Outreach messages (LinkedIn connection requests, DMs)
  - Social media posts (LinkedIn, X/Twitter, Facebook)

Usage:
    from content_styles import get_style, list_styles, STYLES
    
    style = get_style("bold_edgy")       # returns style dict
    style = get_style()                   # returns default "professional"
    
    for key, name, desc in list_styles():
        print(f"{key}: {name} — {desc}")
"""

STYLES = {
    "professional": {
        "name": "Professional",
        "description": "Polished, direct, and approachable — the default recruiter voice",
        "system_voice": (
            "Professional, polished, approachable recruiter. "
            "Write with clarity and confidence. No corporate fluff, no slang. "
            "Be respectful and focused on the opportunity."
        ),
        "outreach": {
            "voice": (
                "Professional and respectful. You are an experienced headhunter "
                "presenting a curated opportunity. Sound confident but not pushy."
            ),
            "format_notes": (
                "Start with a sincere compliment about their background. "
                "State the role, location, and salary clearly. "
                "End with a gentle call to action."
            ),
            "greeting": "Hi",
            "signoff": "Best regards",
            "max_chars": 300,
            "tone": "Professional recruiter reaching out to a respected candidate.",
        },
        "post": {
            "voice": (
                "Professional and compelling. Market the opportunity clearly "
                "without sounding like a salesperson."
            ),
            "hook_style": "Short, attention-grabbing statement or observation",
            "body_style": "Brief but compelling — describe the opportunity and why it matters",
            "cta": 'Say "Link in comments" — do NOT include any URL in the post body',
            "hashtag_count": "1-3",
            "emoji_usage": "Use relevant emojis naturally and sparingly (📍💰🔧)",
            "linkedin_max": 2000,
            "x_max": 280,
            "facebook_max": 500,
        },
    },

    "bold_edgy": {
        "name": "Bold & Edgy",
        "description": "Direct, provocative, challenges the reader — stands out in a crowded feed",
        "system_voice": (
            "Bold, direct, unapologetic. Challenge the reader. "
            "Cut through the noise. No corporate speak. Be opinionated and confident. "
            "Don't sound like every other recruiter."
        ),
        "outreach": {
            "voice": (
                "Direct and confident. You know a great opportunity when you see one, "
                "and this is it. No fluff, no beating around the bush."
            ),
            "format_notes": (
                "Open with a direct observation about their work or industry. "
                "State the role in one punchy line. "
                "Make the candidate feel this is THE opportunity, not just AN opportunity."
            ),
            "greeting": "Hey",
            "signoff": "",
            "max_chars": 250,
            "tone": "Confident insider who spots talent and doesn't waste time.",
        },
        "post": {
            "voice": (
                "Unfiltered, opinionated, cuts through the noise. "
                "Don't sound like every other recruiter. Take a stand."
            ),
            "hook_style": "Hot take, bold claim, or provocative question",
            "body_style": "Punchy, benefits-focused, minimal fluff",
            "cta": 'Say "Link in comments 👇" — do NOT include any URL in the post body',
            "hashtag_count": "1-2",
            "emoji_usage": "Use emojis strategically for emphasis (🔥, 👇, 🚀, ⚡)",
            "linkedin_max": 1500,
            "x_max": 260,
            "facebook_max": 400,
        },
    },

    "minimalist": {
        "name": "Minimalist",
        "description": "Ultra-short, just the facts — no fluff, no storytelling, no filler",
        "system_voice": (
            "Concise, factual, minimal. Say more with less. "
            "No adjectives, no stories, no filler words. "
            "Every word must earn its place."
        ),
        "outreach": {
            "voice": (
                "Short and surgical. Get straight to the point. "
                "No compliments, no pleasantries — just the opportunity."
            ),
            "format_notes": (
                "State role, location, and salary in one line. "
                "One sentence about skills match. "
                "End with a short call to action."
            ),
            "greeting": "Hi",
            "signoff": "",
            "max_chars": 200,
            "tone": "Efficient, no-nonsense professional.",
        },
        "post": {
            "voice": (
                "Minimal. Just the essential information. "
                "No padding, no stories, no adjectives."
            ),
            "hook_style": "One line — just the role or a single compelling fact",
            "body_style": "Bullet points or one sentence. Bare minimum.",
            "cta": 'Say "Link in comments" — do NOT include any URL in the post body',
            "hashtag_count": "1",
            "emoji_usage": "Minimal emojis (📍💰 only for location/salary if needed)",
            "linkedin_max": 1000,
            "x_max": 200,
            "facebook_max": 300,
        },
    },

    "warm_empathetic": {
        "name": "Warm & Empathetic",
        "description": "Friendly, supportive, human-first — connects on a personal level",
        "system_voice": (
            "Warm, empathetic, human. Speak like a real person who understands "
            "the struggles of job hunting. Be supportive, encouraging, and genuine."
        ),
        "outreach": {
            "voice": (
                "Warm and personal. Show you understand their journey "
                "and want to help."
            ),
            "format_notes": (
                "Start with a friendly, human opening. "
                "Share a brief personal connection or observation. "
                "Present the role as a genuine opportunity, not a sales pitch. "
                "No pressure — just curiosity."
            ),
            "greeting": "Hi",
            "signoff": "Warmly",
            "max_chars": 350,
            "tone": "Helpful peer who genuinely wants to see them succeed.",
        },
        "post": {
            "voice": (
                "Warm, supportive, community-oriented. "
                "Speak to people, not at them."
            ),
            "hook_style": "Relatable, human moment or observation about the job market",
            "body_style": "Conversational, benefits-driven with a human touch",
            "cta": 'Say "Link in comments" — do NOT include any URL in the post body',
            "hashtag_count": "2-3",
            "emoji_usage": "Use warm, friendly emojis (🙌, 💛, 👋, ✨, 🤝)",
            "linkedin_max": 2000,
            "x_max": 280,
            "facebook_max": 500,
        },
    },

    "storytelling": {
        "name": "Storytelling",
        "description": "Narrative-driven, paints a picture — makes the reader feel something",
        "system_voice": (
            "Storyteller. Paint a picture, create a narrative arc. "
            "Start with a scene, a problem, or a moment of insight. "
            "Make the reader feel something before you inform them of anything."
        ),
        "outreach": {
            "voice": (
                "Personal and narrative. Share a brief context "
                "before the ask. Connect dots the candidate hasn't connected."
            ),
            "format_notes": (
                "Open with a scene, observation, or shared context. "
                "Build towards the opportunity naturally. "
                "Frame the role as the next chapter, not just another job."
            ),
            "greeting": "Hi",
            "signoff": "Best",
            "max_chars": 400,
            "tone": "Thoughtful connector who sees the bigger picture.",
        },
        "post": {
            "voice": (
                "Narrative hook, scene-setting, then the opportunity. "
                "Make people stop scrolling and read."
            ),
            "hook_style": "A short story, scene, or 'the other day...' opening",
            "body_style": "Narrative flow — set up a problem, present the role as the solution",
            "cta": 'Say "Link in comments 👇" — do NOT include any URL in the post body',
            "hashtag_count": "1-2",
            "emoji_usage": "Use emojis to punctuate narrative moments, not decorate",
            "linkedin_max": 2500,
            "x_max": 280,
            "facebook_max": 600,
        },
    },

    "hype_builder": {
        "name": "Hype Builder",
        "description": "High-energy, exciting, FOMO-inducing — gets people excited to apply",
        "system_voice": (
            "High-energy, exciting, urgent. This opportunity is special "
            "and the reader should feel that. Use enthusiasm strategically. "
            "Create a sense of 'this is THE one'."
        ),
        "outreach": {
            "voice": (
                "Excited but not desperate. You've found something special "
                "and you think they're the person for it."
            ),
            "format_notes": (
                "Lead with excitement about the role. "
                "Highlight what makes this opportunity unique. "
                "Create urgency without being pushy."
            ),
            "greeting": "Hey",
            "signoff": "Cheers",
            "max_chars": 280,
            "tone": "Enthusiastic talent spotter who found a gem.",
        },
        "post": {
            "voice": (
                "High-energy, exciting, creates FOMO. "
                "Make people feel they might miss out if they don't act."
            ),
            "hook_style": "Big claim, exciting stat, or 'opportunity alert' energy",
            "body_style": "Fast-paced, benefit-heavy, urgency-driven",
            "cta": 'Say "Link in comments 👇 — don\'t sleep on this one" — do NOT include any URL in the post body',
            "hashtag_count": "2-3",
            "emoji_usage": "Energy emojis (🚀, 🔥, 💥, ⚡, 🎯)",
            "linkedin_max": 1800,
            "x_max": 270,
            "facebook_max": 450,
        },
    },
}

DEFAULT_STYLE = "professional"


def get_style(style_name=None):
    """Return style dict by key. Falls back to default if not found or None."""
    if style_name and style_name in STYLES:
        return STYLES[style_name]
    return STYLES[DEFAULT_STYLE]


def list_styles():
    """Return list of (key, display_name, description) tuples for menu rendering."""
    return [(key, s["name"], s["description"]) for key, s in STYLES.items()]


def choose_style_interactive(prompt_label="style"):
    """Interactive helper: let the user pick a style from the menu.
    Returns the style key string.
    """
    print(f"\n  🎨 Select {prompt_label}:")
    print(f"  {'─' * 60}")
    style_options = list_styles()
    for i, (key, name, desc) in enumerate(style_options, 1):
        default_mark = "  (default)" if key == DEFAULT_STYLE else ""
        print(f"  {i}. {name}{default_mark}")
        print(f"     {desc}")
    print(f"  {'─' * 60}")
    
    while True:
        choice = input(f"  Enter number [1-{len(style_options)}] or press Enter for default: ").strip()
        if not choice:
            return DEFAULT_STYLE
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(style_options):
                return style_options[idx][0]
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(style_options)}.")
