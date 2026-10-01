from flask import Flask, request, jsonify, render_template_string
import requests
import re
import html
import json
import time
from urllib.parse import urlparse, quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree as ET
from datetime import datetime, timezone

app = Flask(__name__)


# ============================================================
# ABHYNEX API KEYS
# ============================================================

TAVILY_API_KEY = ""
EXA_API_KEY = ""

GROQ_API_KEY = ""
GEMINI_API_KEY = ""
COHERE_API_KEY = ""

MISTRAL_API_KEY = ""
XAI_API_KEY = ""
DEEPSEEK_API_KEY = ""
OPENROUTER_API_KEY = ""

NEWSDATA_API_KEY = ""
CURRENT_NEWS_API_KEY = ""

FIRECRAWL_API_KEY = ""

SUPABASE_URL = "PASTE_SUPABASE_URL_HERE"
SUPABASE_KEY = "PASTE_SUPABASE_KEY_HERE"

UPSTASH_REDIS_REST_URL = "PASTE_UPSTASH_REDIS_REST_URL_HERE"
UPSTASH_REDIS_REST_TOKEN = "PASTE_UPSTASH_REDIS_REST_TOKEN_HERE"


# ============================================================
# MODELS
# ============================================================

GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-2.0-flash"
COHERE_MODEL = "command-a-03-2025"
MISTRAL_MODEL = "mistral-small-latest"
XAI_MODEL = "grok-3-mini"
DEEPSEEK_MODEL = "deepseek-chat"
OPENROUTER_MODEL = "openai/gpt-4o-mini"


# ============================================================
# BASIC HELPERS
# ============================================================

def valid_key(key):
    if not key:
        return False

    placeholders = [
        "PASTE_",
        "YOUR_",
        "ENTER_",
        "_HERE"
    ]

    return not any(x in key for x in placeholders)


def clean_text(value, limit=700):
    if not value:
        return ""

    value = html.unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    value = value.strip()

    return value[:limit]


def domain_from_url(url):
    try:
        host = urlparse(url).netloc.lower()
        return host.replace("www.", "")
    except:
        return ""


def safe_get(url, **kwargs):
    try:
        kwargs.setdefault("timeout", 15)
        response = requests.get(url, **kwargs)

        if response.status_code >= 400:
            return None

        return response

    except:
        return None


def safe_post(url, **kwargs):
    try:
        kwargs.setdefault("timeout", 25)
        response = requests.post(url, **kwargs)

        if response.status_code >= 400:
            return None

        return response

    except:
        return None


def unique_results(results):
    seen = set()
    final = []

    for item in results:

        url = item.get("url", "").strip()

        if not url:
            continue

        key = url.lower().rstrip("/")

        if key in seen:
            continue

        seen.add(key)
        final.append(item)

    return final


# ============================================================
# TAVILY — LIVE WEB
# ============================================================

def tavily_search(query, max_results=8):

    if not valid_key(TAVILY_API_KEY):
        return []

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "topic": "general",
        "include_answer": False,
        "include_raw_content": False,
        "max_results": max_results
    }

    response = safe_post(
        "https://api.tavily.com/search",
        json=payload
    )

    if not response:
        return []

    try:

        data = response.json()
        results = []

        for item in data.get("results", []):

            url = item.get("url", "")

            results.append({
                "title": clean_text(
                    item.get("title"),
                    180
                ),
                "url": url,
                "snippet": clean_text(
                    item.get("content"),
                    600
                ),
                "source": domain_from_url(url),
                "type": "web",
                "published": item.get("published_date", ""),
                "retrieved": datetime.now(
                    timezone.utc
                ).isoformat()
            })

        return results

    except:
        return []


# ============================================================
# EXA — LIVE WEB
# ============================================================

def exa_search(query, max_results=8):

    if not valid_key(EXA_API_KEY):
        return []

    headers = {
        "x-api-key": EXA_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "query": query,
        "numResults": max_results,
        "contents": {
            "text": {
                "maxCharacters": 1400
            }
        }
    }

    response = safe_post(
        "https://api.exa.ai/search",
        headers=headers,
        json=payload
    )

    if not response:
        return []

    try:

        data = response.json()
        results = []

        for item in data.get("results", []):

            url = item.get("url", "")

            results.append({
                "title": clean_text(
                    item.get("title"),
                    180
                ),
                "url": url,
                "snippet": clean_text(
                    item.get("text") or
                    item.get("snippet"),
                    600
                ),
                "source": domain_from_url(url),
                "type": "web",
                "published": item.get("publishedDate", ""),
                "retrieved": datetime.now(
                    timezone.utc
                ).isoformat()
            })

        return results

    except:
        return []


# ============================================================
# GOOGLE NEWS RSS
# ============================================================

def google_news_search(query, max_results=8):

    url = (
        "https://news.google.com/rss/search?"
        "q="
        + quote_plus(query)
        + "&hl=en-IN&gl=IN&ceid=IN:en"
    )

    response = safe_get(url)

    if not response:
        return []

    results = []

    try:

        root = ET.fromstring(response.content)

        for item in root.findall(".//item")[:max_results]:

            title = item.findtext("title") or ""
            link = item.findtext("link") or ""
            description = item.findtext(
                "description"
            ) or ""
            published = item.findtext(
                "pubDate"
            ) or ""

            results.append({
                "title": clean_text(title, 180),
                "url": link,
                "snippet": clean_text(
                    description,
                    600
                ),
                "source": domain_from_url(link),
                "type": "news",
                "published": published,
                "retrieved": datetime.now(
                    timezone.utc
                ).isoformat()
            })

    except:
        pass

    return results


# ============================================================
# NEWSDATA
# ============================================================

def newsdata_search(query, max_results=6):

    if not valid_key(NEWSDATA_API_KEY):
        return []

    url = (
        "https://newsdata.io/api/1/latest?"
        "apikey="
        + NEWSDATA_API_KEY
        + "&q="
        + quote_plus(query)
        + "&language=en"
        + "&country=in"
    )

    response = safe_get(url)

    if not response:
        return []

    try:

        data = response.json()
        results = []

        for item in data.get(
            "results",
            []
        )[:max_results]:

            url = item.get(
                "link",
                ""
            )

            results.append({
                "title": clean_text(
                    item.get("title"),
                    180
                ),
                "url": url,
                "snippet": clean_text(
                    item.get("description"),
                    600
                ),
                "source": domain_from_url(url),
                "type": "news",
                "published": item.get(
                    "pubDate",
                    ""
                ),
                "retrieved": datetime.now(
                    timezone.utc
                ).isoformat()
            })

        return results

    except:
        return []


# ============================================================
# CURRENT NEWS
# ============================================================

def current_news_search(query, max_results=6):

    if not valid_key(CURRENT_NEWS_API_KEY):
        return []

    url = (
        "https://api.currentsapi.services/v1/search?"
        "apiKey="
        + CURRENT_NEWS_API_KEY
        + "&keywords="
        + quote_plus(query)
        + "&language=en"
    )

    response = safe_get(url)

    if not response:
        return []

    try:

        data = response.json()
        results = []

        for item in data.get(
            "news",
            []
        )[:max_results]:

            url = item.get(
                "url",
                ""
            )

            results.append({
                "title": clean_text(
                    item.get("title"),
                    180
                ),
                "url": url,
                "snippet": clean_text(
                    item.get("description"),
                    600
                ),
                "source": domain_from_url(url),
                "type": "news",
                "published": item.get(
                    "published",
                    ""
                ),
                "retrieved": datetime.now(
                    timezone.utc
                ).isoformat()
            })

        return results

    except:
        return []


# ============================================================
# FIRECRAWL
# ============================================================

def firecrawl_scrape(url):

    if not valid_key(FIRECRAWL_API_KEY):
        return ""

    headers = {
        "Authorization":
            f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type":
            "application/json"
    }

    payload = {
        "url": url,
        "formats": ["markdown"]
    }

    response = safe_post(
        "https://api.firecrawl.dev/v1/scrape",
        headers=headers,
        json=payload
    )

    if not response:
        return ""

    try:

        data = response.json()

        return clean_text(
            data.get(
                "data",
                {}
            ).get(
                "markdown",
                ""
            ),
            5000
        )

    except:
        return ""


# ============================================================
# QUERY INTENT
# ============================================================

def is_news_query(query):

    q = query.lower()

    words = [
        "latest",
        "today",
        "now",
        "current",
        "breaking",
        "news",
        "recent",
        "this week",
        "live",
        "update",
        "updates",
        "2026"
    ]

    return any(
        word in q
        for word in words
    )


# ============================================================
# SEARCH ROUTER
# ============================================================

def perform_search(query, mode="all"):

    query = query.strip()

    if not query:
        return []

    results = []

    # --------------------------------------------------------
    # NEWS MODE
    # --------------------------------------------------------

    if mode == "news":

        jobs = []

        with ThreadPoolExecutor(
            max_workers=3
        ) as executor:

            jobs.append(
                executor.submit(
                    google_news_search,
                    query,
                    8
                )
            )

            if valid_key(NEWSDATA_API_KEY):

                jobs.append(
                    executor.submit(
                        newsdata_search,
                        query,
                        6
                    )
                )

            if valid_key(
                CURRENT_NEWS_API_KEY
            ):

                jobs.append(
                    executor.submit(
                        current_news_search,
                        query,
                        6
                    )
                )

            for job in as_completed(jobs):

                try:
                    results.extend(
                        job.result()
                    )
                except:
                    pass

        return unique_results(
            results
        )[:20]


    # --------------------------------------------------------
    # NORMAL / LIVE SEARCH
    # --------------------------------------------------------

    jobs = []

    with ThreadPoolExecutor(
        max_workers=3
    ) as executor:

        jobs.append(
            executor.submit(
                tavily_search,
                query,
                8
            )
        )

        jobs.append(
            executor.submit(
                exa_search,
                query,
                8
            )
        )

        # Current/news query gets news too.
        if is_news_query(query):

            jobs.append(
                executor.submit(
                    google_news_search,
                    query,
                    6
                )
            )

            if valid_key(
                NEWSDATA_API_KEY
            ):

                jobs.append(
                    executor.submit(
                        newsdata_search,
                        query,
                        5
                    )
                )

        for job in as_completed(jobs):

            try:
                results.extend(
                    job.result()
                )
            except:
                pass

    return unique_results(
        results
    )[:20]


# ============================================================
# ABHI AI PROMPT
# ============================================================

def make_ai_prompt(query, results):

    source_blocks = []

    for i, item in enumerate(
        results[:12],
        1
    ):

        source_blocks.append(
            f"""
SOURCE {i}
Title: {item.get('title', '')}
Website: {item.get('source', '')}
Published: {item.get('published', '')}
Information: {item.get('snippet', '')}
URL: {item.get('url', '')}
"""
        )

    context = "\n".join(
        source_blocks
    )

    return f"""
You are Abhi AI inside ABHYNEX Search.

USER QUESTION:
{query}

CURRENT WEB INFORMATION:
{context}

RULES:

- Answer the exact question.
- Use the supplied web information.
- Prefer recent information for current/latest questions.
- Do not invent facts.
- Do not tell the user only to open links.
- Give the useful answer directly.
- Clearly distinguish facts and uncertainty.
- Use concise headings.
- Use bullet points when useful.
- If the question asks "latest", prioritize recent sources.
- If sources disagree, mention the disagreement.
- Do not mention API names.
- Do not mention internal systems.
- Do not say you are Google.
- Do not say you are ChatGPT.
- Your name is Abhi AI.
- You are part of ABHYNEX Search.

Write a clear, useful answer.
"""


# ============================================================
# GROQ
# ============================================================

def groq_answer(prompt):

    if not valid_key(GROQ_API_KEY):
        return ""

    headers = {
        "Authorization":
            f"Bearer {GROQ_API_KEY}",
        "Content-Type":
            "application/json"
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content":
                    "You are Abhi AI."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.15,
        "max_tokens": 1200
    }

    response = safe_post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload
    )

    if not response:
        return ""

    try:

        return (
            response.json()
            ["choices"][0]
            ["message"]["content"]
            .strip()
        )

    except:
        return ""


# ============================================================
# GEMINI
# ============================================================

def gemini_answer(prompt):

    if not valid_key(GEMINI_API_KEY):
        return ""

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/"
        + GEMINI_MODEL
        + ":generateContent?key="
        + GEMINI_API_KEY
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    response = safe_post(
        url,
        json=payload
    )

    if not response:
        return ""

    try:

        return (
            response.json()
            ["candidates"][0]
            ["content"]["parts"][0]
            ["text"]
            .strip()
        )

    except:
        return ""


# ============================================================
# COHERE
# ============================================================

def cohere_answer(prompt):

    if not valid_key(COHERE_API_KEY):
        return ""

    headers = {
        "Authorization":
            f"Bearer {COHERE_API_KEY}",
        "Content-Type":
            "application/json"
    }

    payload = {
        "model": COHERE_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    response = safe_post(
        "https://api.cohere.com/v2/chat",
        headers=headers,
        json=payload
    )

    if not response:
        return ""

    try:

        return (
            response.json()
            ["message"]["content"][0]
            ["text"]
            .strip()
        )

    except:
        return ""


# ============================================================
# OTHER AI FALLBACKS
# ============================================================

def openai_style_answer(
    api_key,
    endpoint,
    model,
    prompt,
    extra_headers=None
):

    if not valid_key(api_key):
        return ""

    headers = {
        "Authorization":
            f"Bearer {api_key}",
        "Content-Type":
            "application/json"
    }

    if extra_headers:
        headers.update(
            extra_headers
        )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2
    }

    response = safe_post(
        endpoint,
        headers=headers,
        json=payload
    )

    if not response:
        return ""

    try:

        return (
            response.json()
            ["choices"][0]
            ["message"]["content"]
            .strip()
        )

    except:
        return ""


def mistral_answer(prompt):

    return openai_style_answer(
        MISTRAL_API_KEY,
        "https://api.mistral.ai/v1/chat/completions",
        MISTRAL_MODEL,
        prompt
    )


def xai_answer(prompt):

    return openai_style_answer(
        XAI_API_KEY,
        "https://api.x.ai/v1/chat/completions",
        XAI_MODEL,
        prompt
    )


def deepseek_answer(prompt):

    return openai_style_answer(
        DEEPSEEK_API_KEY,
        "https://api.deepseek.com/chat/completions",
        DEEPSEEK_MODEL,
        prompt
    )


def openrouter_answer(prompt):

    return openai_style_answer(
        OPENROUTER_API_KEY,
        "https://openrouter.ai/api/v1/chat/completions",
        OPENROUTER_MODEL,
        prompt,
        {
            "HTTP-Referer":
                "http://localhost:8160",
            "X-Title":
                "ABHYNEX Search"
        }
    )


# ============================================================
# ABHI AI ROUTER
# ============================================================

def generate_ai_answer(query, results):

    if not results:

        return (
            "I couldn't find enough current web "
            "information to answer this question."
        )

    prompt = make_ai_prompt(
        query,
        results
    )

    engines = [
        groq_answer,
        gemini_answer,
        cohere_answer,
        mistral_answer,
        xai_answer,
        deepseek_answer,
        openrouter_answer
    ]

    for engine in engines:

        try:

            answer = engine(prompt)

            if answer:
                return answer

        except:
            continue

    # Safe fallback
    first = results[0]

    return (
        f"### {first.get('title', 'Search result')}\n\n"
        f"{first.get('snippet', '')}"
    )


# ============================================================
# SUPABASE
# ============================================================

def save_history(query, answer):

    if not valid_key(SUPABASE_URL):
        return

    if not valid_key(SUPABASE_KEY):
        return

    url = (
        SUPABASE_URL.rstrip("/")
        + "/rest/v1/search_history"
    )

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization":
            f"Bearer {SUPABASE_KEY}",
        "Content-Type":
            "application/json",
        "Prefer":
            "return=minimal"
    }

    payload = {
        "query": query,
        "answer": answer[:5000],
        "created_at":
            datetime.utcnow().isoformat()
    }

    safe_post(
        url,
        headers=headers,
        json=payload
    )


# ============================================================
# API SEARCH
# ============================================================

@app.route("/api/search")
def api_search():

    query = request.args.get(
        "q",
        ""
    ).strip()

    mode = request.args.get(
        "mode",
        "all"
    ).strip()

    if not query:

        return jsonify({
            "ok": False,
            "error":
                "Please enter a search query."
        })

    # IMPORTANT:
    # No local/static answer database.
    # Search APIs are called for current information.
    results = perform_search(
        query,
        mode
    )

    # Deep mode extracts top pages.
    if mode == "deep":

        for item in results[:3]:

            extracted = firecrawl_scrape(
                item.get("url", "")
            )

            if extracted:

                item["snippet"] = (
                    extracted[:900]
                )

    answer = generate_ai_answer(
        query,
        results
    )

    now = datetime.now(
        timezone.utc
    )

    response = {
        "ok": True,
        "query": query,
        "mode": mode,
        "answer": answer,

        "results": results,

        "sources": results[:8],

        "related": [
            f"{query} explained",
            f"{query} latest",
            f"{query} news",
            f"{query} official information"
        ],

        "live": True,

        "retrieved_at":
            now.isoformat(),

        "display_time":
            now.strftime(
                "%d %b %Y • %I:%M %p UTC"
            )
    }

    try:
        save_history(
            query,
            answer
        )
    except:
        pass

    return jsonify(response)


# ============================================================
# STATUS
# ============================================================

@app.route("/api/status")
def status():

    return jsonify({

        "ABHYNEX": "ONLINE",

        "live_search": True,

        "search": {
            "Tavily":
                valid_key(
                    TAVILY_API_KEY
                ),

            "Exa":
                valid_key(
                    EXA_API_KEY
                ),

            "Google News":
                True,

            "NewsData":
                valid_key(
                    NEWSDATA_API_KEY
                ),

            "Current News":
                valid_key(
                    CURRENT_NEWS_API_KEY
                )
        },

        "ai": {
            "Groq":
                valid_key(
                    GROQ_API_KEY
                ),

            "Gemini":
                valid_key(
                    GEMINI_API_KEY
                ),

            "Cohere":
                valid_key(
                    COHERE_API_KEY
                ),

            "Mistral":
                valid_key(
                    MISTRAL_API_KEY
                ),

            "xAI":
                valid_key(
                    XAI_API_KEY
                ),

            "DeepSeek":
                valid_key(
                    DEEPSEEK_API_KEY
                ),

            "OpenRouter":
                valid_key(
                    OPENROUTER_API_KEY
                )
        },

        "tools": {
            "Firecrawl":
                valid_key(
                    FIRECRAWL_API_KEY
                ),

            "Supabase":
                valid_key(
                    SUPABASE_URL
                ),

            "Upstash":
                valid_key(
                    UPSTASH_REDIS_REST_URL
                )
        }
    })


# ============================================================
# PREMIUM ABHYNEX UI
# ============================================================

HTML = r"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta
name="viewport"
content="width=device-width,initial-scale=1.0"
>

<title>ABHYNEX Search</title>

<style>

*{
    box-sizing:border-box;
    margin:0;
    padding:0;
}

html,
body{
    min-height:100%;
}

body{

    font-family:
        Inter,
        Arial,
        sans-serif;

    color:#172033;

    background:

        radial-gradient(
            circle at 10% 10%,
            rgba(255,153,51,.10),
            transparent 30%
        ),

        radial-gradient(
            circle at 90% 20%,
            rgba(0,130,255,.09),
            transparent 32%
        ),

        radial-gradient(
            circle at 50% 100%,
            rgba(19,136,8,.09),
            transparent 35%
        ),

        #f8fafc;

    overflow-x:hidden;
}


/* ========================================================
   PREMIUM TOP
======================================================== */

.top{

    height:70px;

    display:flex;

    align-items:center;

    justify-content:center;

    border-bottom:
        1px solid #e9edf3;

    background:
        rgba(255,255,255,.82);

    backdrop-filter:
        blur(18px);

    position:
        sticky;

    top:0;

    z-index:100;
}


.brand{

    display:flex;

    align-items:center;

    gap:12px;

    user-select:none;
}


.brand-mark{

    width:40px;

    height:40px;

    display:flex;

    align-items:center;

    justify-content:center;

    border-radius:12px;

    font-size:24px;

    font-weight:950;

    color:white;

    background:

        linear-gradient(
            145deg,
            #ff9933 0%,
            #ff9933 33%,
            #ffffff 34%,
            #ffffff 65%,
            #138808 66%,
            #138808 100%
        );

    text-shadow:
        0 1px 4px rgba(0,0,0,.35);

    box-shadow:
        0 7px 22px
        rgba(0,0,0,.15);
}


.brand-text{

    font-size:22px;

    font-weight:900;

    letter-spacing:-.7px;

    background:

        linear-gradient(
            90deg,
            #e87916,
            #4157d9 46%,
            #158b36
        );

    -webkit-background-clip:text;

    background-clip:text;

    color:transparent;
}


.brand-small{

    color:#87909f;

    font-size:10px;

    letter-spacing:2px;

    margin-top:1px;
}


/* ========================================================
   HOME
======================================================== */

.home{

    min-height:
        calc(100vh - 70px);

    display:flex;

    justify-content:center;

    align-items:center;

    padding:
        35px 18px 65px;
}


.home-inner{

    width:
        min(880px,100%);

    text-align:center;
}


/* ========================================================
   WORDMARK
======================================================== */

.hero{

    margin-bottom:25px;
}


.hero-mark{

    display:inline-flex;

    align-items:center;

    justify-content:center;

    width:92px;

    height:92px;

    border-radius:28px;

    font-size:55px;

    font-weight:950;

    color:white;

    background:

        linear-gradient(
            145deg,
            #ff9933 0%,
            #ff9933 31%,
            #ffffff 32%,
            #ffffff 65%,
            #138808 66%,
            #138808 100%
        );

    box-shadow:
        0 20px 45px
        rgba(30,45,70,.17);

    text-shadow:
        0 2px 8px
        rgba(0,0,0,.45);
}


.hero-title{

    margin-top:13px;

    font-size:
        clamp(38px,8vw,72px);

    line-height:1;

    font-weight:950;

    letter-spacing:-4px;

    background:

        linear-gradient(
            90deg,
            #e87916 0%,
            #e87916 25%,
            #5063d9 50%,
            #138808 78%,
            #138808 100%
        );

    -webkit-background-clip:text;

    background-clip:text;

    color:transparent;
}


.hero-search{

    font-size:11px;

    letter-spacing:5px;

    color:#7b8492;

    margin-top:9px;
}


.tagline{

    margin-top:12px;

    color:#697386;

    font-size:15px;
}


/* ========================================================
   SEARCH BOX
======================================================== */

.search-wrap{

    width:
        min(760px,100%);

    margin:
        27px auto 0;

    position:relative;
}


.search{

    width:100%;

    height:62px;

    background:white;

    border:
        1px solid #dfe4eb;

    border-radius:32px;

    display:flex;

    align-items:center;

    padding:
        0 9px 0 20px;

    box-shadow:
        0 9px 30px
        rgba(36,51,75,.09);

    transition:.2s;
}


.search:focus-within{

    border-color:
        #8e98aa;

    box-shadow:
        0 12px 36px
        rgba(36,51,75,.14);
}


.search-icon{

    color:#697386;

    font-size:21px;
}


.input{

    flex:1;

    border:0;

    outline:0;

    background:transparent;

    height:100%;

    padding:
        0 12px;

    font-size:16px;

    color:#172033;
}


.input::placeholder{

    color:#9aa2af;
}


.voice{

    width:43px;

    height:43px;

    border:0;

    background:transparent;

    border-radius:50%;

    cursor:pointer;

    font-size:19px;
}


.voice:hover{

    background:#f2f4f7;
}


.go{

    height:45px;

    padding:
        0 23px;

    border:0;

    border-radius:24px;

    cursor:pointer;

    color:white;

    font-weight:800;

    background:

        linear-gradient(
            110deg,
            #e87d19,
            #5366dc,
            #168b38
        );

    box-shadow:
        0 8px 18px
        rgba(74,91,180,.23);
}


/* ========================================================
   SUGGESTIONS
======================================================== */

.suggestions{

    display:none;

    position:absolute;

    top:70px;

    left:0;

    right:0;

    z-index:50;

    text-align:left;

    background:white;

    border:
        1px solid #e2e6ec;

    border-radius:19px;

    overflow:hidden;

    box-shadow:
        0 20px 45px
        rgba(20,30,50,.15);
}


.suggestion{

    padding:
        13px 18px;

    border-bottom:
        1px solid #f0f2f5;

    cursor:pointer;

    font-size:14px;
}


.suggestion:hover{

    background:#f7f8fa;
}


/* ========================================================
   QUICK
======================================================== */

.quick{

    margin-top:19px;

    display:flex;

    justify-content:center;

    flex-wrap:wrap;

    gap:8px;
}


.quick button{

    border:
        1px solid #dfe4ea;

    background:white;

    color:#424b5a;

    border-radius:20px;

    padding:
        9px 15px;

    cursor:pointer;

    font-size:13px;

    transition:.2s;
}


.quick button:hover{

    border-color:#a9b1bd;

    transform:
        translateY(-1px);
}


/* ========================================================
   LIVE STRIP
======================================================== */

.live-strip{

    margin:
        30px auto 0;

    width:
        min(760px,100%);

    display:flex;

    align-items:center;

    justify-content:center;

    gap:9px;

    color:#596475;

    font-size:12px;
}


.live-dot{

    width:8px;

    height:8px;

    border-radius:50%;

    background:#19a34a;

    box-shadow:
        0 0 0 5px
        rgba(25,163,74,.10);

    animation:pulse 1.7s infinite;
}


@keyframes pulse{

    0%,100%{
        opacity:1;
    }

    50%{
        opacity:.35;
    }
}


/* ========================================================
   FEATURES
======================================================== */

.features{

    display:grid;

    grid-template-columns:
        repeat(4,1fr);

    gap:11px;

    margin-top:30px;
}


.feature{

    text-align:left;

    background:
        rgba(255,255,255,.88);

    border:
        1px solid #e5e9ef;

    border-radius:18px;

    padding:16px;

    box-shadow:
        0 6px 20px
        rgba(40,55,75,.04);
}


.feature-icon{

    font-size:20px;

    margin-bottom:9px;
}


.feature b{

    display:block;

    font-size:13px;

    margin-bottom:4px;
}


.feature span{

    color:#7b8492;

    font-size:11px;

    line-height:1.4;
}


/* ========================================================
   RESULTS
======================================================== */

.results{

    display:none;

    width:
        min(1060px,100%);

    margin:auto;

    padding:
        22px 16px 70px;
}


.result-search{

    display:flex;

    gap:8px;

    margin-bottom:17px;
}


.result-search .search{

    height:56px;

    flex:1;
}


.result-search .go{

    height:56px;
}


/* ========================================================
   LIVE RESULT HEADER
======================================================== */

.live-header{

    display:flex;

    align-items:center;

    gap:8px;

    color:#687386;

    font-size:11px;

    margin-bottom:14px;
}


.live-badge{

    color:#17883d;

    font-weight:800;

    letter-spacing:1px;
}


/* ========================================================
   TABS
======================================================== */

.tabs{

    display:flex;

    gap:7px;

    overflow-x:auto;

    padding-bottom:10px;

    margin-bottom:17px;
}


.tab{

    flex-shrink:0;

    border:
        1px solid #dfe4ea;

    background:white;

    color:#566071;

    border-radius:19px;

    padding:
        9px 16px;

    cursor:pointer;

    font-size:13px;
}


.tab.active{

    color:white;

    border-color:#202b40;

    background:#202b40;
}


/* ========================================================
   ABHI AI
======================================================== */

.ai{

    background:

        radial-gradient(
            circle at 90% 0%,
            rgba(67,95,255,.25),
            transparent 35%
        ),

        linear-gradient(
            135deg,
            #0c1020,
            #13182b
        );

    border:
        1px solid #28304a;

    color:white;

    border-radius:23px;

    padding:23px;

    margin-bottom:18px;

    box-shadow:
        0 20px 50px
        rgba(11,16,32,.18);
}


.ai-head{

    display:flex;

    align-items:center;

    gap:11px;

    margin-bottom:14px;
}


.ai-icon{

    width:43px;

    height:43px;

    display:flex;

    align-items:center;

    justify-content:center;

    border-radius:13px;

    color:#111;

    background:

        linear-gradient(
            135deg,
            #ff9933,
            white 48%,
            #138808
        );

    font-weight:950;

    font-size:21px;
}


.ai-name{

    font-size:18px;

    font-weight:850;
}


.ai-sub{

    color:#9299ab;

    font-size:11px;

    margin-top:2px;
}


.ai-answer{

    color:#e9edf6;

    font-size:15px;

    line-height:1.75;
}


.ai-answer h1,
.ai-answer h2,
.ai-answer h3{

    color:white;

    margin:
        12px 0 7px;
}


.ai-answer p{

    margin-bottom:9px;
}


.ai-answer ul{

    padding-left:21px;

    margin-bottom:9px;
}


/* ========================================================
   SECTIONS
======================================================== */

.section{

    background:white;

    border:
        1px solid #e3e7ed;

    border-radius:21px;

    padding:20px;

    margin-bottom:16px;
}


.section-title{

    font-weight:850;

    font-size:17px;

    margin-bottom:13px;
}


/* ========================================================
   RESULT
======================================================== */

.result{

    display:block;

    text-decoration:none;

    padding:
        14px 0;

    border-bottom:
        1px solid #edf0f3;
}


.result:last-child{

    border-bottom:0;
}


.domain{

    color:#707a89;

    font-size:11px;

    margin-bottom:5px;
}


.title{

    color:#1769d5;

    font-size:17px;

    font-weight:700;

    margin-bottom:5px;
}


.snippet{

    color:#5d6674;

    font-size:13px;

    line-height:1.55;
}


.date{

    color:#8b94a2;

    font-size:10px;

    margin-top:5px;
}


/* ========================================================
   RELATED
======================================================== */

.related{

    display:flex;

    flex-wrap:wrap;

    gap:8px;
}


.related button{

    border:0;

    background:#f2f4f7;

    color:#475162;

    border-radius:18px;

    padding:
        9px 13px;

    cursor:pointer;

    font-size:12px;
}


/* ========================================================
   LOADING
======================================================== */

.loading{

    text-align:center;

    padding:60px 20px;

    color:#778191;
}


.spinner{

    width:35px;

    height:35px;

    border:
        3px solid #e4e8ed;

    border-top-color:#4d5fd2;

    border-radius:50%;

    animation:
        spin .8s linear infinite;

    margin:
        0 auto 14px;
}


@keyframes spin{

    to{
        transform:rotate(360deg);
    }
}


/* ========================================================
   MOBILE
======================================================== */

@media(max-width:760px){

    .top{
        height:62px;
    }

    .brand-text{
        font-size:19px;
    }

    .brand-mark{
        width:36px;
        height:36px;
        font-size:21px;
    }

    .home{
        min-height:
            calc(100vh - 62px);

        padding:
            28px 13px 45px;
    }

    .hero-mark{
        width:74px;
        height:74px;
        font-size:43px;
        border-radius:23px;
    }

    .hero-title{
        letter-spacing:-2.5px;
    }

    .search{
        height:58px;
    }

    .voice{
        display:none;
    }

    .go{
        padding:
            0 17px;
    }

    .features{

        grid-template-columns:
            repeat(2,1fr);

    }

    .results{

        padding:
            16px 11px 55px;
    }

    .result-search .go{
        padding:
            0 15px;
    }

    .ai{
        padding:18px;

        border-radius:19px;
    }

    .section{
        padding:16px;
        border-radius:18px;
    }

    .title{
        font-size:15px;
    }

}


@media(max-width:420px){

    .features{
        grid-template-columns:1fr;
    }

    .hero-search{
        letter-spacing:3px;
    }

    .result-search{
        flex-direction:column;
    }

    .result-search .go{
        width:100%;
    }

}

</style>

</head>


<body>


<!-- ======================================================
     TOP
====================================================== -->

<header class="top">

    <div class="brand">

        <div class="brand-mark">
            A
        </div>

        <div>

            <div class="brand-text">
                ABHYNEX
            </div>

            <div class="brand-small">
                SEARCH
            </div>

        </div>

    </div>

</header>


<!-- ======================================================
     HOME
====================================================== -->

<main
id="home"
class="home"
>

<div class="home-inner">


    <div class="hero">

        <div class="hero-mark">
            A
        </div>

        <div class="hero-title">
            ABHYNEX
        </div>

        <div class="hero-search">
            SEARCH
        </div>

        <div class="tagline">
            Search smarter • Think deeper • With Abhi AI
        </div>

    </div>


    <div class="search-wrap">

        <div class="search">

            <span class="search-icon">
                ⌕
            </span>

            <input
                id="homeInput"
                class="input"
                autocomplete="off"
                placeholder="Search anything..."
            >

            <button
                class="voice"
                onclick="voiceSearch('homeInput')"
            >
                🎙
            </button>

            <button
                class="go"
                onclick="startSearch()"
            >
                Search
            </button>

        </div>


        <div
            id="suggestions"
            class="suggestions"
        ></div>

    </div>


    <div class="quick">

        <button
        onclick="quickSearch('latest news')">
            📰 News
        </button>

        <button
        onclick="quickSearch('artificial intelligence latest')">
            ✦ AI
        </button>

        <button
        onclick="quickSearch('deep science latest')">
            🔬 Science
        </button>

        <button
        onclick="quickSearch('India latest news')">
            🇮🇳 India
        </button>

        <button
        onclick="quickSearch('technology latest')">
            ⚡ Technology
        </button>

    </div>


    <div class="live-strip">

        <span class="live-dot"></span>

        <span>
            ABHYNEX Live Web • Current information on demand
        </span>

    </div>


    <div class="features">


        <div class="feature">

            <div class="feature-icon">
                ✦
            </div>

            <b>
                Abhi AI
            </b>

            <span>
                Clear answers grounded in web information.
            </span>

        </div>


        <div class="feature">

            <div class="feature-icon">
                ◉
            </div>

            <b>
                Live Web
            </b>

            <span>
                Fresh search results when you search.
            </span>

        </div>


        <div class="feature">

            <div class="feature-icon">
                ◎
            </div>

            <b>
                Global Sources
            </b>

            <span>
                Results from multiple web sources.
            </span>

        </div>


        <div class="feature">

            <div class="feature-icon">
                ◈
            </div>

            <b>
                Deep Search
            </b>

            <span>
                Explore multiple sources for complex questions.
            </span>

        </div>


    </div>


</div>

</main>


<!-- ======================================================
     RESULTS
====================================================== -->

<main
id="results"
class="results"
>


    <div class="result-search">

        <div class="search">

            <span class="search-icon">
                ⌕
            </span>

            <input
                id="resultInput"
                class="input"
                autocomplete="off"
                placeholder="Search ABHYNEX"
            >

        </div>

        <button
            class="go"
            onclick="searchAgain()"
        >
            Search
        </button>

    </div>


    <div class="live-header">

        <span class="live-dot"></span>

        <span class="live-badge">
            LIVE
        </span>

        <span id="retrieved">
            Searching current web...
        </span>

    </div>


    <div class="tabs">

        <button
            class="tab active"
            onclick="setMode('all',this)"
        >
            All
        </button>

        <button
            class="tab"
            onclick="setMode('all',this)"
        >
            Abhi AI
        </button>

        <button
            class="tab"
            onclick="setMode('news',this)"
        >
            News
        </button>

        <button
            class="tab"
            onclick="setMode('deep',this)"
        >
            Deep Search
        </button>

    </div>


    <div id="content"></div>

</main>


<script>


let currentQuery = "";
let currentMode = "all";


/* ========================================================
   SUGGESTIONS
======================================================== */

const suggestionsList = [

    "latest AI news",
    "latest technology news",
    "India latest news",
    "what is artificial intelligence",
    "how does machine learning work",
    "latest science news",
    "Indian history",
    "UPSC preparation",
    "Mechanical Engineering",
    "Python programming",
    "C++ programming",
    "latest space news"

];


const homeInput =
    document.getElementById(
        "homeInput"
    );


const suggestions =
    document.getElementById(
        "suggestions"
    );


homeInput.addEventListener(
    "input",
    function(){

        const value =
            this.value
            .trim()
            .toLowerCase();

        if(!value){

            suggestions.style.display =
                "none";

            return;
        }

        const matches =
            suggestionsList
            .filter(
                x =>
                    x.toLowerCase()
                    .includes(value)
            )
            .slice(0,6);

        if(!matches.length){

            suggestions.style.display =
                "none";

            return;
        }

        suggestions.innerHTML =
            matches.map(
                x => `

                <div
                    class="suggestion"
                    onclick='quickSearch(${JSON.stringify(x)})'
                >
                    ⌕ ${escapeHtml(x)}
                </div>

                `
            ).join("");

        suggestions.style.display =
            "block";

    }
);


homeInput.addEventListener(
    "keydown",
    function(event){

        if(event.key === "Enter"){
            startSearch();
        }

    }
);


document
.getElementById("resultInput")
.addEventListener(
    "keydown",
    function(event){

        if(event.key === "Enter"){
            searchAgain();
        }

    }
);


/* ========================================================
   START SEARCH
======================================================== */

function startSearch(){

    const q =
        homeInput
        .value
        .trim();

    if(!q){
        return;
    }

    currentQuery = q;
    currentMode = "all";

    document
    .getElementById("resultInput")
    .value = q;

    document
    .getElementById("home")
    .style.display = "none";

    document
    .getElementById("results")
    .style.display = "block";

    suggestions.style.display =
        "none";

    window.scrollTo(
        0,
        0
    );

    runSearch(
        q,
        "all"
    );
}


function quickSearch(q){

    homeInput.value = q;

    startSearch();

}


function searchAgain(){

    const q =
        document
        .getElementById("resultInput")
        .value
        .trim();

    if(!q){
        return;
    }

    currentQuery = q;

    runSearch(
        q,
        currentMode
    );
}


/* ========================================================
   MODE
======================================================== */

function setMode(
    mode,
    button
){

    currentMode = mode;

    document
    .querySelectorAll(".tab")
    .forEach(
        x =>
            x.classList.remove(
                "active"
            )
    );

    button.classList.add(
        "active"
    );

    runSearch(
        currentQuery,
        mode
    );
}


/* ========================================================
   LIVE SEARCH
======================================================== */

async function runSearch(
    query,
    mode
){

    const content =
        document.getElementById(
            "content"
        );

    const retrieved =
        document.getElementById(
            "retrieved"
        );

    retrieved.textContent =
        "Fetching fresh web information...";


    content.innerHTML = `

        <div class="loading">

            <div class="spinner"></div>

            <div>
                Searching the live web...
            </div>

        </div>

    `;


    try{

        /*
         * cache-busting parameter:
         * latest/current queries should
         * request fresh backend data.
         */

        const url =
            "/api/search?q="
            + encodeURIComponent(query)
            + "&mode="
            + encodeURIComponent(mode)
            + "&live="
            + Date.now();


        const response =
            await fetch(
                url,
                {
                    cache:"no-store"
                }
            );


        const data =
            await response.json();


        if(!data.ok){

            content.innerHTML = `

                <div class="section">
                    ${escapeHtml(
                        data.error
                    )}
                </div>

            `;

            return;
        }


        retrieved.textContent =
            "Retrieved "
            + data.display_time
            + " • "
            + data.results.length
            + " results";


        render(data);

    }
    catch(error){

        retrieved.textContent =
            "Live connection unavailable";


        content.innerHTML = `

            <div class="section">

                <div class="section-title">
                    ABHYNEX
                </div>

                <div>
                    Live web search could not
                    connect right now.
                </div>

            </div>

        `;

    }

}


/* ========================================================
   RENDER
======================================================== */

function render(data){

    const content =
        document.getElementById(
            "content"
        );


    const answer =
        markdown(
            data.answer || ""
        );


    content.innerHTML = `


        <!-- ABHI AI -->

        <section class="ai">

            <div class="ai-head">

                <div class="ai-icon">
                    A
                </div>

                <div>

                    <div class="ai-name">
                        Abhi AI
                    </div>

                    <div class="ai-sub">
                        Live web-grounded answer
                    </div>

                </div>

            </div>


            <div class="ai-answer">

                ${answer}

            </div>

        </section>


        <!-- SOURCES -->

        <section class="section">

            <div class="section-title">
                Sources
            </div>

            ${renderResults(
                data.sources || []
            )}

        </section>


        <!-- WEB -->

        <section class="section">

            <div class="section-title">
                Web Results
            </div>

            ${renderResults(
                data.results || []
            )}

        </section>


        <!-- RELATED -->

        <section class="section">

            <div class="section-title">
                Related Searches
            </div>

            <div class="related">

                ${(data.related || [])
                .map(
                    item => `

                    <button
                        onclick='quickSearch(${JSON.stringify(item)})'
                    >
                        ${escapeHtml(item)}
                    </button>

                    `
                )
                .join("")}

            </div>

        </section>

    `;

}


/* ========================================================
   RESULTS
======================================================== */

function renderResults(
    items
){

    if(!items.length){

        return `
            <div>
                No results found.
            </div>
        `;

    }


    return items
    .slice(0,10)
    .map(
        item => {

            const url =
                item.url || "#";

            const domain =
                item.source ||
                getDomain(url);

            let date = "";

            if(item.published){

                date =
                    "Published • "
                    + item.published;

            }


            return `

                <a
                    class="result"
                    href="${safeUrl(url)}"
                    target="_blank"
                    rel="noopener noreferrer"
                >

                    <div class="domain">
                        ${escapeHtml(domain)}
                    </div>

                    <div class="title">
                        ${escapeHtml(
                            item.title ||
                            "Web result"
                        )}
                    </div>

                    <div class="snippet">
                        ${escapeHtml(
                            item.snippet ||
                            ""
                        )}
                    </div>

                    ${
                        date
                        ?
                        `<div class="date">
                            ${escapeHtml(date)}
                        </div>`
                        :
                        ""
                    }

                </a>

            `;

        }
    )
    .join("");

}


/* ========================================================
   MARKDOWN
======================================================== */

function markdown(text){

    let x =
        escapeHtml(text);


    x =
        x.replace(
            /^### (.*)$/gm,
            "<h3>$1</h3>"
        );


    x =
        x.replace(
            /^## (.*)$/gm,
            "<h2>$1</h2>"
        );


    x =
        x.replace(
            /^# (.*)$/gm,
            "<h1>$1</h1>"
        );


    x =
        x.replace(
            /\*\*(.*?)\*\*/g,
            "<strong>$1</strong>"
        );


    x =
        x.replace(
            /^\- (.*)$/gm,
            "<li>$1</li>"
        );


    x =
        x.replace(
            /(<li>.*<\/li>)/gs,
            "<ul>$1</ul>"
        );


    x =
        x.replace(
            /\n\n/g,
            "</p><p>"
        );


    return "<p>"
        + x
        + "</p>";

}


/* ========================================================
   SAFE HTML
======================================================== */

function escapeHtml(value){

    return String(value || "")
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );

}


function safeUrl(url){

    if(
        !url.startsWith(
            "http://"
        )
        &&
        !url.startsWith(
            "https://"
        )
    ){

        return "#";

    }

    return url.replace(
        /"/g,
        "%22"
    );

}


function getDomain(url){

    try{

        return new URL(url)
            .hostname
            .replace(
                "www.",
                ""
            );

    }
    catch{

        return "";

    }

}


/* ========================================================
   VOICE
======================================================== */

function voiceSearch(
    inputId
){

    const Recognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;


    if(!Recognition){

        alert(
            "Voice search is not supported."
        );

        return;
    }


    const recognition =
        new Recognition();


    recognition.lang =
        "en-IN";


    recognition.interimResults =
        false;


    recognition.continuous =
        false;


    recognition.onresult =
        function(event){

            const text =
                event
                .results[0][0]
                .transcript;


            document
            .getElementById(
                inputId
            )
            .value = text;


            if(
                inputId ===
                "homeInput"
            ){

                startSearch();

            }
            else{

                searchAgain();

            }

        };


    recognition.start();

}

</script>

</body>

</html>
"""


# ============================================================
# HOME ROUTE
# ============================================================

@app.route("/")
def home():

    return render_template_string(
        HTML
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 65)
    print("                    ABHYNEX SEARCH")
    print("=" * 65)

    print()
    print("LIVE WEB")
    print(
        "Tavily:",
        "ON"
        if valid_key(TAVILY_API_KEY)
        else "OFF"
    )

    print(
        "Exa:",
        "ON"
        if valid_key(EXA_API_KEY)
        else "OFF"
    )

    print(
        "Google News: ON"
    )

    print(
        "NewsData:",
        "ON"
        if valid_key(NEWSDATA_API_KEY)
        else "OFF"
    )

    print(
        "Current News:",
        "ON"
        if valid_key(CURRENT_NEWS_API_KEY)
        else "OFF"
    )

    print()
    print("ABHI AI")

    print(
        "Groq:",
        "ON"
        if valid_key(GROQ_API_KEY)
        else "OFF"
    )

    print(
        "Gemini:",
        "ON"
        if valid_key(GEMINI_API_KEY)
        else "OFF"
    )

    print(
        "Cohere:",
        "ON"
        if valid_key(COHERE_API_KEY)
        else "OFF"
    )

    print()
    print("SERVER")
    print(
        "http://127.0.0.1:8160"
    )

    print(
        "Network: http://0.0.0.0:8160"
    )

    print()
    print(
        "ABHYNEX SEARCH IS RUNNING"
    )

    print("=" * 65)
    print()


    app.run(
        host="0.0.0.0",
        port=8160,
        debug=False
    )