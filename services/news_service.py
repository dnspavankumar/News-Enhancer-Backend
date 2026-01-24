"""
News Service - Handles RSS feed fetching and article scraping
"""
import feedparser
from newspaper import Article
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict
import hashlib
from html import unescape
import re

# RSS Feed mapping for different interests
RSS_FEEDS = {
    # Technology & Programming
    "coding": [
        "https://hnrss.org/frontpage",
        "https://www.reddit.com/r/programming/.rss",
        "https://dev.to/feed"
    ],
    "technology": [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://www.wired.com/feed/rss"
    ],
    "cloud architecture": [
        "https://aws.amazon.com/blogs/aws/feed/",
        "https://cloud.google.com/blog/rss",
        "https://devblogs.microsoft.com/azure-sdk/feed/"
    ],
    "ai": [
        "https://www.artificialintelligence-news.com/feed/",
        "https://openai.com/blog/rss.xml"
    ],
    
    # Health & Fitness
    "fitness": [
        "https://www.menshealth.com/rss/all.xml/",
        "https://www.bodybuilding.com/rss/latest-articles.xml"
    ],
    "health": [
        "https://www.health.com/syndication/feed",
        "https://www.healthline.com/rss"
    ],
    "yoga": [
        "https://www.yogajournal.com/feed/"
    ],
    "meditation": [
        "https://www.mindful.org/feed/"
    ],
    
    # Business & Finance
    "startup": [
        "https://techcrunch.com/tag/startups/feed/",
        "https://www.reddit.com/r/startups/.rss",
        "https://news.ycombinator.com/rss"
    ],
    "business": [
        "https://www.businessinsider.com/rss",
        "https://www.reddit.com/r/business/.rss",
        "https://hbr.org/feed"
    ],
    "stock trading": [
        "https://www.investopedia.com/feedbuilder/feed/getfeed?feedName=rss_headline",
        "https://www.marketwatch.com/rss/",
        "https://www.reddit.com/r/stocks/.rss"
    ],
    "finance": [
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://finance.yahoo.com/news/rssindex",
        "https://www.reddit.com/r/finance/.rss"
    ],
    
    # Lifestyle
    "cooking": [
        "https://www.bonappetit.com/feed/rss",
        "https://www.seriouseats.com/rss/recipes.xml"
    ],
    "gaming": [
        "https://www.ign.com/feed.xml",
        "https://www.polygon.com/rss/index.xml"
    ],
    "travel": [
        "https://www.lonelyplanet.com/feed",
        "https://www.travelandleisure.com/rss"
    ],
    "hiking": [
        "https://www.outsideonline.com/rss/",
        "https://www.backpacker.com/rss/"
    ],
    
    # Default fallback
    "general": [
        "https://news.google.com/rss",
        "https://www.reddit.com/r/news/.rss"
    ]
}

# Cache for articles (simple in-memory cache)
article_cache = {}


def get_cache_key(url: str) -> str:
    """Generate cache key from URL"""
    return hashlib.md5(url.encode()).hexdigest()


def scrape_article_content(url: str, timeout: int = 8) -> tuple[Optional[str], Optional[str]]:
    """
    Scrape the full article content and image from a URL using newspaper3k.
    Returns (content, image_url)
    """
    # Check cache first
    cache_key = get_cache_key(url)
    if cache_key in article_cache:
        return article_cache[cache_key]
    
    try:
        article = Article(url)
        
        # Add user agent to bypass some blocks
        article.config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        article.config.request_timeout = timeout
        article.config.fetch_images = False  # Skip image fetching for speed
        
        article.download()
        article.parse()
        
        content = article.text[:2000] if article.text else None  # Limit to 2000 chars
        image = article.top_image if article.top_image else None
        
        # Cache the result
        result = (content, image)
        article_cache[cache_key] = result
        
        return result
    except Exception as e:
        # Don't print error for every blocked/timeout site (too noisy)
        if "403" not in str(e) and "404" not in str(e) and "timed out" not in str(e):
            print(f"Error scraping article {url}: {str(e)}")
        return None, None


def find_feeds_for_interest(interest: str) -> List[str]:
    """
    Find relevant RSS feeds for a given interest.
    Uses fuzzy matching to find the best feeds.
    """
    interest_lower = interest.lower()
    
    # Direct match
    if interest_lower in RSS_FEEDS:
        return RSS_FEEDS[interest_lower]
    
    # Partial match
    for key in RSS_FEEDS:
        if key in interest_lower or interest_lower in key:
            return RSS_FEEDS[key]
    
    # Fallback to general news
    return RSS_FEEDS["general"]


def fetch_rss_entries(feed_url: str, max_entries: int = 10) -> List[dict]:
    """
    Fetch entries from a single RSS feed.
    """
    try:
        feed = feedparser.parse(feed_url)
        entries = []
        
        for entry in feed.entries[:max_entries]:
            entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "published": entry.get("published", ""),
                "source": feed.feed.get("title", "Unknown")
            })
        
        return entries
    except Exception as e:
        print(f"Error fetching RSS feed {feed_url}: {str(e)}")
        return []


def process_single_article(entry: dict) -> Optional[Dict]:
    """
    Process a single RSS entry and scrape its content.
    Returns dict instead of NewsArticle for JSON serialization
    """
    try:
        # Try to scrape full content
        content, image = scrape_article_content(entry["link"])
        
        # Use RSS summary as fallback if scraping fails
        if not content and entry.get("summary"):
            # Clean HTML tags from summary
            summary = entry.get("summary", "")
            # Remove HTML tags
            summary = re.sub('<[^<]+?>', '', summary)
            # Unescape HTML entities
            summary = unescape(summary)
            content = summary.strip()
        
        # Skip if no content at all
        if not content or len(content) < 50:
            return None
        
        return {
            "title": entry["title"],
            "link": entry["link"],
            "source": entry["source"],
            "snippet": entry.get("summary", "")[:200] if entry.get("summary") else None,
            "date": entry.get("published", ""),
            "content": content[:2000],  # Limit content length
            "image": image
        }
    except Exception as e:
        print(f"Error processing article {entry.get('link', '')}: {str(e)}")
        return None


def fetch_news_for_interest(interest: str, num_results: int = 5) -> List[Dict]:
    """
    Fetch news articles for a specific interest using RSS feeds.
    Uses parallel processing for efficiency.
    Returns list of dicts for JSON serialization
    """
    # Find relevant RSS feeds
    feed_urls = find_feeds_for_interest(interest)
    
    # Fetch entries from all feeds in parallel
    all_entries = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_feed = {executor.submit(fetch_rss_entries, url, 8): url for url in feed_urls}
        
        for future in as_completed(future_to_feed):
            try:
                entries = future.result()
                all_entries.extend(entries)
            except Exception as e:
                print(f"Error in feed fetch: {str(e)}")
    
    # Limit to requested number * 3 (to account for failures)
    all_entries = all_entries[:num_results * 3]
    
    # Process articles in parallel with more workers
    articles = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_entry = {executor.submit(process_single_article, entry): entry for entry in all_entries}
        
        for future in as_completed(future_to_entry):
            try:
                article = future.result()
                if article:
                    articles.append(article)
                    if len(articles) >= num_results:
                        break
            except Exception as e:
                print(f"Error in article processing: {str(e)}")
    
    return articles[:num_results]
