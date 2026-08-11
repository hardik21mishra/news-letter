import feedparser
from bs4 import BeautifulSoup
import re
import html
from datetime import timezone
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime

import json

feed_links = {
    "https://www.infoq.com/feed/": "InfoQ",
    "https://martinfowler.com/feed.atom": "Martin Fowler",
    "https://queue.acm.org/rss/": "ACM Queue",
    "https://lwn.net/headlines/rss": "LWN.net",
    "https://netflixtechblog.com/feed": "Netflix TechBlog",
    "https://blog.cloudflare.com/rss/": "Cloudflare Blog",
    "https://code.fb.com/feed/": "Meta Engineering",
    "https://github.blog/feed/": "GitHub Blog",

    # "https://engineering.linkedin.com/blog.rss.html": "LinkedIn Engineering",
    # "https://dropbox.tech/feed": "Dropbox Tech",
    # "https://stripe.com/blog/feed.rss": "Stripe Engineering",
    # "https://engineering.atspotify.com/feed/": "Spotify Engineering",
    # "https://www.datadoghq.com/blog/rss/": "Datadog Engineering",
    # "https://engineering.salesforce.com/feed/": "Salesforce Engineering",
    # "https://www.twilio.com/en-us/blog/rss.xml": "Twilio Engineering",


    # "https://aws.amazon.com/blogs/aws/feed/": "AWS",
    # "https://cloud.google.com/blog/products/rss/": "Google Cloud",
    # "https://www.cncf.io/feed/": "CNCF",
    # "https://kubernetes.io/feed.xml": "Kubernetes",
    # "https://istio.io/latest/feed.xml": "Istio",
    # "https://www.hashicorp.com/blog/feed.xml": "HashiCorp",
    # "https://grafana.com/blog/rss/": "Grafana Labs",
    # "https://prometheus.io/feed.xml": "Prometheus",
    # "https://www.elastic.co/blog/feed": "Elastic",
    # "https://helm.sh/feed.xml": "Helm",
    # "https://thenewstack.io/feed/": "The New Stack",

    # "https://openai.com/news/rss.xml": "OpenAI",
    # "https://huggingface.co/blog/feed.xml": "Hugging Face",
    # "https://research.google/blog/rss/": "Google Research",
    # "https://blogs.microsoft.com/ai/feed/": "Microsoft AI",
    # "https://www.anthropic.com/news/rss.xml": "Anthropic",
    # "https://pytorch.org/feed.xml": "PyTorch",
    # "https://www.tensorflow.org/feed.xml": "TensorFlow",
    # "https://engineering.fb.com/category/ai/feed/": "Meta AI Engineering",
    # "https://developer.nvidia.com/blog/feed": "NVIDIA",

    # "https://www.cockroachlabs.com/blog/rss.xml": "CockroachDB",
    # "https://www.timescale.com/blog/rss/": "TimescaleDB",
    # "https://planet.postgresql.org/rss20.xml": "Planet PostgreSQL",
    # "https://redis.com/feed/": "Redis",
    # "https://www.mongodb.com/blog/rss": "MongoDB",

    # "https://googleprojectzero.blogspot.com/feeds/posts/default": "Google Project Zero",
    # "https://feeds.feedburner.com/TheHackersNews": "The Hacker News",
    # "https://unit42.paloaltonetworks.com/feed/": "Palo Alto Unit 42",
    # "https://blog.talosintelligence.com/feeds/posts/default": "Cisco Talos",
    # "https://www.schneier.com/feed/atom/": "Schneier on Security",

    # "https://go.dev/blog/feed.atom": "Go Blog",
    # "https://blog.rust-lang.org/feed.xml": "Rust Blog",
    # "https://v8.dev/blog.atom": "V8 JavaScript Engine",
    # "https://developer.chrome.com/feed.xml": "Chrome Developers",
    # "https://webkit.org/feed/": "WebKit",
    # "https://blog.jetbrains.com/feed/": "JetBrains Blog",
    # "https://planet.kernel.org/rss20.xml": "Planet Kernel",
    # "https://planet.python.org/rss20.xml": "Planet Python",

    # "https://medium.com/feed/tag/artificial-intelligence": "Medium - AI",
    # "https://medium.com/feed/tag/machine-learning": "Medium - Machine Learning",
    # "https://medium.com/feed/tag/software-engineering": "Medium - Software Engineering",
    # "https://medium.com/feed/tag/programming": "Medium - Programming",
    # "https://medium.com/feed/tag/cloud-computing": "Medium - Cloud Computing",
    # "https://medium.com/feed/tag/devops": "Medium - DevOps",
    # "https://medium.com/feed/tag/kubernetes": "Medium - Kubernetes",
    # "https://medium.com/feed/tag/data-engineering": "Medium - Data Engineering",
    # "https://medium.com/feed/tag/cybersecurity": "Medium - Cybersecurity",

    # "https://feeds.arstechnica.com/arstechnica/index": "Ars Technica",
    # "https://rss.slashdot.org/Slashdot/slashdotMain": "Slashdot",
}

IST = ZoneInfo("Asia/Kolkata")

def normalize_published_date(date_string):
    if date_string == "Date not available":
        return None
    
    if not date_string:
        return None
    try:
        dt = parsedate_to_datetime(date_string)

        # Convert RSS timezone → IST
        dt = dt.astimezone(IST)

        # Remove timezone information because MySQL DATETIME
        # stores only date and time
        return dt.replace(tzinfo=None)
    except (TypeError, ValueError):
        return None

def clean_text(text):
    if not text:
        return "Description not found"

    text = html.unescape(text)
    text = BeautifulSoup(text, "html.parser").get_text(" ")
    text = re.sub(r'[\u200b-\u200d\uFEFF]', '', text)  # zero-width chars

    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")

    # strip all quote marks (straight + curly) instead of converting them,
    text = re.sub(r'["“”‘’]', '', text)

    text = re.sub(r'\s+([.,!?;:])', r'\1', text)      # no space before punctuation
    text = re.sub(r'([.,!?;:])([A-Za-z])', r'\1 \2', text)  # space after punctuation
    text = re.sub(r'([.!?]){2,}', r'\1', text)         # remove repeated punctuation
    text = re.sub(r'\s+', ' ', text)                  #remove whitespace

    return text.strip()


def fetch_news():
    articles = []
    for feed_url, source in feed_links.items():
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:2]:
            description = (
                entry.get("summary")
                or entry.get("description")
                or (
                    entry.get("content", [{}])[0].get("value", "") 
                    if entry.get("content") 
                    else ""
                )
            )
            rss_category = None

            if hasattr(entry, "tags") and entry.tags:
                rss_category = entry.tags[0].term
            elif entry.get("category"):
                rss_category = entry.get("category")

            article = {
                "title": clean_text(entry.get("title", "Title not found")),
                "source": source,
                "description": clean_text(description),
                "published_at": normalize_published_date(
                    entry.get("published")
                    or entry.get("updated")
                    or entry.get("pubDate")
                    or "Date not available"
                ),
                "link": entry.get("link", ""),
                "summary": None,
                "category": rss_category
            }  
            articles.append(article)
            # print(article)
            # print("\n")
    return articles

# main

def fetch_sum_save():
    from categorize import process_news
    from db import init_db, save_articles

    init_db() 

    articles = fetch_news()
    print(f"Fetched {len(articles)} articles total")


    print("Categorized and summarized articles")

    articles = process_news(articles)
    save_articles(articles)
    print("saved articles to the database")

if __name__ == "__main__":
    fetch_sum_save()
# fetch_news()