import anthropic
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import json
import os
import re
import subprocess

# ── Config ────────────────────────────────────────────────────────────────────
SITE_URL = "https://topicallyrandom.github.io/jlee-daily"
FEEDME_ARCHIVE = "https://www.readfeedme.com/archive"
FEEDME_BASE = "https://www.readfeedme.com"

# ── Step 1: Scrape Feed Me archive for latest posts ───────────────────────────
def scrape_feedme():
    print("Fetching Feed Me archive...")
    try:
        r = requests.get(FEEDME_ARCHIVE, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        posts = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/p/" in href and "readfeedme.com" in href:
                title = a.get_text(strip=True)
                if len(title) > 20:
                    posts.append({"title": title, "url": href})
        # Deduplicate
        seen = set()
        unique = []
        for p in posts:
            if p["url"] not in seen:
                seen.add(p["url"])
                unique.append(p)
        print(f"Found {len(unique)} posts.")
        return unique[:8]
    except Exception as e:
        print(f"Scrape error: {e}")
        return []

# ── Step 2: Fetch content of the most recent post ─────────────────────────────
def fetch_post_content(url):
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        # Try to get the article body
        body = soup.find("div", class_=re.compile(r"body|content|post", re.I))
        if body:
            return body.get_text(separator="\n", strip=True)[:3000]
        return soup.get_text(separator="\n", strip=True)[:3000]
    except Exception as e:
        print(f"Fetch error: {e}")
        return ""

# ── Step 3: Generate post via Claude ──────────────────────────────────────────
def generate_post(feed_context, today_str):
    print("Generating post with Claude...")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"""Today is {today_str}. You are writing a daily blog post for "The J Lee Daily" — a witty, editorial fan blog tracking JLee (Jason Lee, @carry_bradshaw_), Feed Me's semi-anonymous restaurant critic and host of the Expense Account podcast on Feed Me by Emily Sundberg.

Here is the latest content from Feed Me's archive:
{feed_context}

Write a blog post that:
- Summarizes what's new on Feed Me today
- Spends at least 4-5 paragraphs specifically on JLee — his writing style, his persona, his podcast, his takes, his cultural significance, random observations and opinions about him
- Is witty, editorial, opinionated — like a sharp food media insider wrote it
- Never uses bullet points, only flowing prose
- Is around 600-800 words total

Return ONLY a JSON object with these exact fields, no markdown, no backticks:
{{
  "title": "the post title",
  "subtitle": "a one-sentence italic subtitle",
  "body_html": "the full post body as HTML paragraphs only — just <p> tags, no other HTML. Use <a href=\\"url\\"> for any links."
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)

# ── Step 4: Build HTML files ──────────────────────────────────────────────────
def build_post_html(post_data, date_str, dispatch_num):
    title = post_data["title"]
    subtitle = post_data["subtitle"]
    body_html = post_data["body_html"]

    # Add drop cap class to first <p>
    body_html = body_html.replace("<p>", '<p class="drop-cap">', 1)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — The J Lee Daily</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400;1,700&family=DM+Mono:ital,wght@0,300;0,400;1,300&family=DM+Sans:wght@300;400&display=swap" rel="stylesheet">
<style>
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  :root{{--ink:#0f0e0d;--paper:#f5f0e8;--accent:#c8392b;--muted:#7a7060;--rule:#d4cfc4}}
  html{{background:var(--paper)}}
  body{{font-family:'DM Sans',sans-serif;background:var(--paper);color:var(--ink);min-height:100vh}}
  header{{border-bottom:3px double var(--ink);padding:0 2rem}}
  .header-top{{display:flex;justify-content:space-between;align-items:center;padding:.75rem 0;border-bottom:1px solid var(--rule);font-family:'DM Mono',monospace;font-size:.7rem;letter-spacing:.08em;color:var(--muted)}}
  .masthead{{text-align:center;padding:1.5rem 0 1rem}}
  .masthead a{{text-decoration:none;color:inherit}}
  .masthead h1{{font-family:'Playfair Display',serif;font-size:clamp(2rem,6vw,4rem);font-weight:900;line-height:.9;letter-spacing:-.02em}}
  .masthead h1 em{{font-style:italic;color:var(--accent)}}
  article{{max-width:680px;margin:0 auto;padding:3rem 2rem 5rem}}
  .post-meta{{font-family:'DM Mono',monospace;font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:1.25rem}}
  .post-title{{font-family:'Playfair Display',serif;font-size:clamp(2rem,5vw,3rem);font-weight:900;line-height:1.1;margin-bottom:.5rem}}
  .post-subtitle{{font-family:'Playfair Display',serif;font-style:italic;font-size:1.15rem;color:var(--muted);margin-bottom:2.5rem;font-weight:400;line-height:1.4}}
  .post-rule{{border:none;border-top:1px solid var(--rule);margin:2rem 0}}
  .post-body p{{font-size:1.05rem;line-height:1.75;font-weight:300;margin-bottom:1.5rem}}
  .post-body p.drop-cap::first-letter{{font-family:'Playfair Display',serif;font-size:4rem;font-weight:900;float:left;line-height:.75;margin:.1em .08em 0 0;color:var(--accent)}}
  .post-body a{{color:var(--accent);text-decoration:none;border-bottom:1px solid var(--accent)}}
  .back-link{{display:inline-block;margin-top:3rem;font-family:'DM Mono',monospace;font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);text-decoration:none;border-bottom:1px solid var(--rule);padding-bottom:2px}}
  .back-link:hover{{color:var(--accent);border-color:var(--accent)}}
  footer{{text-align:center;padding:2rem;font-family:'DM Mono',monospace;font-size:.65rem;letter-spacing:.1em;color:var(--muted);border-top:1px solid var(--rule)}}
  @media(max-width:600px){{.header-top{{flex-direction:column;gap:.25rem;text-align:center}}}}
</style>
</head>
<body>
<header>
  <div class="header-top">
    <span>Est. April 2026</span>
    <span>{SITE_URL}</span>
    <span>New York, NY</span>
  </div>
  <div class="masthead">
    <a href="../index.html"><h1>The <em>J Lee</em> Daily</h1></a>
  </div>
</header>
<article>
  <div class="post-meta">{date_str} &nbsp;&mdash;&nbsp; Dispatch No. {dispatch_num}</div>
  <h2 class="post-title">{title}</h2>
  <p class="post-subtitle">{subtitle}</p>
  <hr class="post-rule">
  <div class="post-body">{body_html}</div>
  <a href="../index.html" class="back-link">&larr; Back to all dispatches</a>
</article>
<footer>The J Lee Daily &mdash; {SITE_URL} &mdash; not affiliated with Feed Me or JLee</footer>
</body>
</html>"""

def update_index(date_str, slug, title, excerpt):
    with open("index.html", "r") as f:
        content = f.read()

    new_item = f"""
    <li class="post-item">
      <div class="post-date">{date_str[:6]}<br>{date_str[-4:]}</div>
      <div class="post-content">
        <a href="posts/{slug}.html">
          <div class="post-title">{title}</div>
          <div class="post-excerpt">{excerpt}</div>
        </a>
      </div>
    </li>
"""
    marker = "<!-- NEW POSTS GO HERE — copy the <li> block above and paste it below this comment -->"
    content = content.replace(marker, marker + new_item)

    with open("index.html", "w") as f:
        f.write(content)

# ── Step 5: Count existing posts for dispatch number ──────────────────────────
def count_posts():
    try:
        files = [f for f in os.listdir("posts") if f.endswith(".html")]
        return len(files) + 1
    except:
        return 1

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%B %d, %Y")
    slug = now.strftime("%Y-%m-%d")
    date_display = now.strftime("%b %d\n%Y")

    # Check if today's post already exists
    if os.path.exists(f"posts/{slug}.html"):
        print(f"Post for {slug} already exists. Skipping.")
        return

    # Scrape + fetch
    posts = scrape_feedme()
    feed_context = "\n\n".join([f"Title: {p['title']}\nURL: {p['url']}" for p in posts])

    if posts:
        top_content = fetch_post_content(posts[0]["url"])
        feed_context = f"LATEST POST CONTENT:\n{top_content}\n\nOTHER RECENT TITLES:\n" + "\n".join([p["title"] for p in posts[1:]])

    # Generate
    dispatch_num = count_posts()
    post_data = generate_post(feed_context, today_str)

    # Write post file
    os.makedirs("posts", exist_ok=True)
    post_html = build_post_html(post_data, today_str, dispatch_num)
    with open(f"posts/{slug}.html", "w") as f:
        f.write(post_html)
    print(f"Written posts/{slug}.html")

    # Update index
    excerpt = post_data["subtitle"]
    update_index(now.strftime("%b %d %Y"), slug, post_data["title"], excerpt)
    print("Updated index.html")

    # Git commit
    subprocess.run(["git", "config", "user.email", "action@github.com"])
    subprocess.run(["git", "config", "user.name", "J Lee Daily Bot"])
    subprocess.run(["git", "add", f"posts/{slug}.html", "index.html"])
    subprocess.run(["git", "commit", "-m", f"Daily post: {today_str}"])
    subprocess.run(["git", "push"])
    print("Pushed to GitHub!")

if __name__ == "__main__":
    main()
