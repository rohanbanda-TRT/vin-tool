from typing import Any, List, Optional
import httpx
from mcp.server.fastmcp import FastMCP
import os
import asyncio
import json
from datetime import datetime, timedelta
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("news")

# Constants
NEWS_API_BASE = "https://newsapi.org/v2"
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")  # Get API key from environment variable
USER_AGENT = "news-app/1.0"

# Cache for storing news to reduce API calls
news_cache = {}
CACHE_DURATION = 30  # minutes


async def make_news_request(endpoint: str, params: dict) -> dict[str, Any] | None:
    """Make a request to the News API with proper error handling."""
    if not NEWS_API_KEY:
        return {"error": "News API key is not configured. Please set the NEWS_API_KEY environment variable."}
    
    params["apiKey"] = NEWS_API_KEY
    
    async with httpx.AsyncClient() as client:
        try:
            url = f"{NEWS_API_BASE}/{endpoint}"
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Error making News API request: {e}"}


def get_from_cache(cache_key: str) -> Optional[dict]:
    """Get data from cache if it exists and is not expired."""
    if cache_key in news_cache:
        cached_data = news_cache[cache_key]
        cache_time = cached_data["timestamp"]
        current_time = datetime.now()
        
        # Check if cache is still valid
        if current_time - cache_time < timedelta(minutes=CACHE_DURATION):
            return cached_data["data"]
    
    return None


def save_to_cache(cache_key: str, data: dict) -> None:
    """Save data to cache with current timestamp."""
    news_cache[cache_key] = {
        "data": data,
        "timestamp": datetime.now()
    }


def format_article(article: dict) -> str:
    """Format an article into a readable string."""
    return f"""
Title: {article.get('title', 'No title')}
Source: {article.get('source', {}).get('name', 'Unknown source')}
Published: {article.get('publishedAt', 'Unknown date')}
Description: {article.get('description', 'No description available')}
URL: {article.get('url', '#')}
"""


@mcp.tool()
async def get_top_headlines(country: str = "us", category: str = "") -> str:
    """Get top headlines for a specific country and optional category.
    
    Args:
        country: Two-letter country code (e.g. us, gb, in)
        category: Optional category (business, entertainment, general, health, science, sports, technology)
    """
    # Check cache first
    cache_key = f"headlines_{country}_{category}"
    cached_data = get_from_cache(cache_key)
    if cached_data:
        return cached_data
    
    # Build parameters
    params = {"country": country}
    if category:
        params["category"] = category
    
    # Make API request
    data = await make_news_request("top-headlines", params)

    if not data or "articles" not in data:
        if "error" in data:
            return data["error"]
        return "Unable to fetch headlines or no headlines found."
    
    if not data["articles"]:
        return f"No headlines found for {country} in category {category or 'general'}."
    
    # Format articles
    articles = [format_article(article) for article in data["articles"][:5]]  # Limit to 5 articles
    result = f"Top Headlines for {country.upper()}" + (f" - {category.title()}" if category else "") + ":\n"
    result += "\n---\n".join(articles)
    
    # Save to cache
    save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
async def search_news(query: str, language: str = "en", sort_by: str = "relevancy") -> str:
    """Search for news articles based on a keyword or phrase.
    
    Args:
        query: Keywords or a phrase to search for
        language: Two-letter language code (e.g. en, es, fr)
        sort_by: How to sort articles (relevancy, popularity, publishedAt)
    """
    # Check cache first
    cache_key = f"search_{query}_{language}_{sort_by}"
    cached_data = get_from_cache(cache_key)
    if cached_data:
        return cached_data
    
    # Build parameters
    params = {
        "q": query,
        "language": language,
        "sortBy": sort_by
    }
    
    # Make API request
    data = await make_news_request("everything", params)
    
    if not data or "articles" not in data:
        if "error" in data:
            return data["error"]
        return f"Unable to find news about '{query}'."
    
    if not data["articles"]:
        return f"No articles found for '{query}'."
    
    # Format articles
    articles = [format_article(article) for article in data["articles"][:5]]  # Limit to 5 articles
    result = f"News Search Results for '{query}':\n"
    result += "\n---\n".join(articles)
    
    # Save to cache
    save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
async def get_sources(category: str = "", language: str = "en", country: str = "") -> str:
    """Get available news sources with optional filters.
    
    Args:
        category: Optional category filter
        language: Two-letter language code (e.g. en, es, fr)
        country: Two-letter country code (e.g. us, gb, in)
    """
    # Check cache first
    cache_key = f"sources_{category}_{language}_{country}"
    cached_data = get_from_cache(cache_key)
    if cached_data:
        return cached_data
    
    # Build parameters
    params = {"language": language}
    if category:
        params["category"] = category
    if country:
        params["country"] = country
    
    # Make API request
    data = await make_news_request("sources", params)
    
    if not data or "sources" not in data:
        if "error" in data:
            return data["error"]
        return "Unable to fetch news sources."
    
    if not data["sources"]:
        return "No sources found with the specified filters."
    
    # Format sources
    sources_list = []
    for source in data["sources"][:10]:  # Limit to 10 sources
        source_info = f"""
Name: {source.get('name', 'Unknown')}
Category: {source.get('category', 'Not specified').title()}
Language: {source.get('language', 'Not specified').upper()}
Country: {source.get('country', 'Not specified').upper()}
Description: {source.get('description', 'No description available')}
URL: {source.get('url', '#')}
"""
        sources_list.append(source_info)
    
    result = "News Sources:\n"
    result += "\n---\n".join(sources_list)
    
    # Save to cache
    save_to_cache(cache_key, result)
    
    return result


def main():
    """Run the News API MCP server."""
    if len(sys.argv) > 1:
        # If arguments are provided, run the MCP server
        mcp.run(transport='stdio')
    else:
        # Otherwise, run a simple test
        async def test():
            print(f"Using News API key: {'*' * (len(NEWS_API_KEY) - 4) + NEWS_API_KEY[-4:] if NEWS_API_KEY else 'Not configured'}")
            
            # Test the top headlines function
            print("\nTesting get_top_headlines:")
            headlines = await get_top_headlines()
            print(headlines)
            
            # Test the search function
            print("\nTesting search_news:")
            search_results = await search_news("climate change")
            print(search_results)
            
            # Test the sources function
            print("\nTesting get_sources:")
            sources = await get_sources(category="technology")
            print(sources)
        
        # Run the test
        asyncio.run(test())


if __name__ == "__main__":
    main()
