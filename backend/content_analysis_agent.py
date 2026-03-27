#!/usr/bin/env python3
"""
Content Analysis Agent Script

This script uses your local Ollama model as an intelligent agent to:
1. Read all scraped data from JSON files
2. Visit every URL found during scraping
3. Extract and analyze webpage content using AI
4. Generate comprehensive insights and save to JSON files

Author: AI Assistant
Usage: python content_analysis_agent.py [scraped_data_file.json]
"""

import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse
import re
import httpx
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import existing utilities and LLM functions
sys.path.append('backend')
from scrapers.utils import get_headers, rate_limit, clean_text, safe_request, get_browser_driver
from llm import call_ollama

# Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

# Processing settings
MAX_CONTENT_LENGTH = 8000  # Characters for LLM analysis
REQUEST_TIMEOUT = 15  # Seconds per webpage
LLM_TIMEOUT = 60  # Seconds per analysis
RATE_LIMIT_MIN = 0.3  # Minimum delay between requests (reduced for speed)
RATE_LIMIT_MAX = 0.8  # Maximum delay between requests (reduced for speed)
MAX_WORKERS = 8  # Parallel processing threads (increased from 3)


class WebContentExtractor:
    """Extract main content from web pages using multiple strategies."""

    def __init__(self):
        self.headers = get_headers()
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def extract_content(self, url: str, source_type: str = "unknown") -> Dict:
        """
        Extract content from a URL based on its type.

        Returns:
            {
                "url": str,
                "title": str,
                "main_content": str,
                "content_preview": str,  # First 500 chars
                "word_count": int,
                "extraction_method": str,
                "extraction_status": str,  # success|partial|failed
                "error": Optional[str],
                "extracted_at": str
            }
        """
        print(f"[EXTRACT] Extracting content from: {url}")

        result = {
            "url": url,
            "title": "",
            "main_content": "",
            "content_preview": "",
            "word_count": 0,
            "extraction_method": "",
            "extraction_status": "failed",
            "error": None,
            "extracted_at": datetime.utcnow().isoformat()
        }

        try:
            # Route to appropriate extractor
            if "youtube.com" in url or "youtu.be" in url:
                return self._extract_youtube(url, result)
            elif "github.com" in url:
                return self._extract_github(url, result)
            elif "reddit.com" in url:
                return self._extract_reddit(url, result)
            elif "twitter.com" in url or "x.com" in url:
                return self._extract_twitter(url, result)
            else:
                return self._extract_generic(url, result)

        except Exception as e:
            result["error"] = str(e)
            result["extraction_status"] = "failed"
            print(f"[ERROR] Extraction failed for {url}: {e}")
            return result

    def _extract_youtube(self, url: str, result: Dict) -> Dict:
        """Extract YouTube video information."""
        try:
            response = safe_request(url, timeout=REQUEST_TIMEOUT)
            if not response:
                result["error"] = "Could not fetch YouTube page"
                return result

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract title
            title_tag = soup.find('meta', property='og:title')
            if title_tag:
                result["title"] = title_tag.get('content', '')

            # Extract description
            desc_tag = soup.find('meta', property='og:description')
            description = desc_tag.get('content', '') if desc_tag else ''

            # Try to extract transcript/captions info from page
            # This is a simplified approach - in production you'd use YouTube API
            content_parts = []

            if result["title"]:
                content_parts.append(f"Title: {result['title']}")

            if description:
                content_parts.append(f"Description: {description}")

            # Look for any visible text content
            visible_text = soup.get_text()
            if visible_text:
                # Extract meaningful parts
                lines = [line.strip() for line in visible_text.split('\n') if line.strip()]
                content_lines = [line for line in lines if len(line) > 30 and not line.startswith('http')][:10]
                if content_lines:
                    content_parts.extend(content_lines)

            result["main_content"] = '\n\n'.join(content_parts)
            result["word_count"] = len(result["main_content"].split())
            result["content_preview"] = result["main_content"][:500] + "..." if len(result["main_content"]) > 500 else result["main_content"]
            result["extraction_method"] = "youtube_page_scraping"
            result["extraction_status"] = "success" if result["main_content"] else "partial"

        except Exception as e:
            result["error"] = str(e)
            result["extraction_status"] = "failed"

        return result

    def _extract_github(self, url: str, result: Dict) -> Dict:
        """Extract GitHub repository information."""
        try:
            # Check if it's a repository URL
            if '/blob/' in url or '/tree/' in url:
                # It's a file or directory, get the main repo page
                parts = url.split('/')
                if len(parts) >= 5:
                    repo_url = f"https://github.com/{parts[3]}/{parts[4]}"
                else:
                    repo_url = url
            else:
                repo_url = url

            response = safe_request(repo_url, timeout=REQUEST_TIMEOUT)
            if not response:
                result["error"] = "Could not fetch GitHub page"
                return result

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract repository name/title
            title_tag = soup.find('strong', {'itemprop': 'name'}) or soup.find('h1')
            if title_tag:
                result["title"] = clean_text(title_tag.get_text())

            content_parts = []

            if result["title"]:
                content_parts.append(f"Repository: {result['title']}")

            # Extract description
            desc_tag = soup.find('p', class_='f4') or soup.find('meta', property='og:description')
            if desc_tag:
                desc = desc_tag.get('content' if desc_tag.name == 'meta' else 'text', '')
                if desc:
                    content_parts.append(f"Description: {desc}")

            # Extract README content
            readme_section = soup.find('div', {'id': 'readme'}) or soup.find('article', class_='markdown-body')
            if readme_section:
                readme_text = clean_text(readme_section.get_text())[:3000]  # Limit README length
                content_parts.append(f"README:\n{readme_text}")

            # Extract language and stats
            lang_tags = soup.find_all('span', class_='color-fg-default')
            if lang_tags:
                languages = [tag.get_text().strip() for tag in lang_tags][:5]
                content_parts.append(f"Languages: {', '.join(languages)}")

            result["main_content"] = '\n\n'.join(content_parts)
            result["word_count"] = len(result["main_content"].split())
            result["content_preview"] = result["main_content"][:500] + "..." if len(result["main_content"]) > 500 else result["main_content"]
            result["extraction_method"] = "github_scraping"
            result["extraction_status"] = "success" if result["main_content"] else "partial"

        except Exception as e:
            result["error"] = str(e)
            result["extraction_status"] = "failed"

        return result

    def _extract_reddit(self, url: str, result: Dict) -> Dict:
        """Extract Reddit post/subreddit information."""
        try:
            # Add .json to Reddit URLs for API access
            json_url = url.rstrip('/') + '.json'

            response = safe_request(json_url, timeout=REQUEST_TIMEOUT)
            if response:
                try:
                    data = response.json()
                    content_parts = []

                    # Handle different Reddit JSON structures
                    if isinstance(data, list):
                        # Post with comments
                        post_data = data[0]['data']['children'][0]['data']
                        result["title"] = post_data.get('title', '')

                        if result["title"]:
                            content_parts.append(f"Title: {result['title']}")

                        if post_data.get('selftext'):
                            content_parts.append(f"Post: {post_data['selftext']}")

                        # Extract top comments
                        if len(data) > 1:
                            comments = data[1]['data']['children'][:5]  # Top 5 comments
                            for comment in comments:
                                if comment['kind'] == 't1' and comment['data'].get('body'):
                                    body = comment['data']['body']
                                    if len(body) > 50:  # Only meaningful comments
                                        content_parts.append(f"Comment: {body}")

                    elif isinstance(data, dict):
                        # Subreddit or other structure
                        if 'data' in data and 'children' in data['data']:
                            for child in data['data']['children'][:3]:
                                if child['data'].get('title'):
                                    content_parts.append(f"Post: {child['data']['title']}")
                                    if child['data'].get('selftext'):
                                        content_parts.append(child['data']['selftext'])

                    result["main_content"] = '\n\n'.join(content_parts)
                    result["extraction_method"] = "reddit_json_api"
                    result["extraction_status"] = "success"

                except json.JSONDecodeError:
                    # Fall back to HTML scraping
                    return self._extract_generic(url, result)
            else:
                # Fall back to HTML scraping
                return self._extract_generic(url, result)

            result["word_count"] = len(result["main_content"].split())
            result["content_preview"] = result["main_content"][:500] + "..." if len(result["main_content"]) > 500 else result["main_content"]

        except Exception as e:
            result["error"] = str(e)
            result["extraction_status"] = "failed"

        return result

    def _extract_twitter(self, url: str, result: Dict) -> Dict:
        """Extract Twitter/X post information (limited due to API restrictions)."""
        try:
            # Twitter requires more complex handling due to JavaScript
            # For now, attempt basic scraping
            response = safe_request(url, timeout=REQUEST_TIMEOUT)
            if not response:
                result["error"] = "Could not fetch Twitter page"
                return result

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract from meta tags
            title_tag = soup.find('meta', property='og:title')
            desc_tag = soup.find('meta', property='og:description')

            content_parts = []

            if title_tag:
                result["title"] = title_tag.get('content', '')
                content_parts.append(f"Tweet Title: {result['title']}")

            if desc_tag:
                description = desc_tag.get('content', '')
                if description:
                    content_parts.append(f"Tweet Content: {description}")

            result["main_content"] = '\n\n'.join(content_parts)
            result["word_count"] = len(result["main_content"].split())
            result["content_preview"] = result["main_content"][:500] + "..." if len(result["main_content"]) > 500 else result["main_content"]
            result["extraction_method"] = "twitter_meta_scraping"
            result["extraction_status"] = "partial" if result["main_content"] else "failed"

        except Exception as e:
            result["error"] = str(e)
            result["extraction_status"] = "failed"

        return result

    def _extract_generic(self, url: str, result: Dict) -> Dict:
        """Extract content from generic web pages."""
        try:
            response = safe_request(url, timeout=REQUEST_TIMEOUT)
            if not response:
                result["error"] = "Could not fetch webpage"
                return result

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract title
            title_tag = soup.find('title') or soup.find('meta', property='og:title')
            if title_tag:
                result["title"] = clean_text(title_tag.get_text() if title_tag.name == 'title' else title_tag.get('content', ''))

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()

            # Extract main content
            content_parts = []

            if result["title"]:
                content_parts.append(f"Title: {result['title']}")

            # Look for article content
            article = soup.find('article') or soup.find('main') or soup.find('div', class_=re.compile(r'content|article|post|entry', re.I))

            if article:
                # Extract text from article
                paragraphs = article.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'])
                for p in paragraphs[:20]:  # Limit to first 20 elements
                    text = clean_text(p.get_text())
                    if len(text) > 30:  # Only meaningful text
                        content_parts.append(text)
            else:
                # Fall back to body text
                body_text = soup.find('body')
                if body_text:
                    paragraphs = body_text.find_all('p')
                    for p in paragraphs[:10]:
                        text = clean_text(p.get_text())
                        if len(text) > 50:
                            content_parts.append(text)

            result["main_content"] = '\n\n'.join(content_parts)
            result["word_count"] = len(result["main_content"].split())
            result["content_preview"] = result["main_content"][:500] + "..." if len(result["main_content"]) > 500 else result["main_content"]
            result["extraction_method"] = "generic_html_scraping"
            result["extraction_status"] = "success" if result["main_content"] else "partial"

        except Exception as e:
            result["error"] = str(e)
            result["extraction_status"] = "failed"

        return result


class OllamaContentAnalyzer:
    """Analyze extracted content using local Ollama model."""

    def __init__(self):
        self.ollama_url = OLLAMA_URL
        self.model = OLLAMA_MODEL

    def analyze_content(self, content_data: Dict, topic: str) -> Dict:
        """
        Analyze extracted content using Ollama LLM.

        Returns comprehensive analysis with all requested fields.
        """
        print(f"[ANALYZE] Analyzing content with Ollama: {content_data['url'][:50]}...")

        # Prepare content for analysis
        analysis_content = self._prepare_content_for_analysis(content_data)

        if not analysis_content.strip():
            return self._generate_fallback_analysis(content_data, topic)

        # Create comprehensive analysis prompt
        prompt = self._create_analysis_prompt(analysis_content, content_data, topic)

        try:
            # Call Ollama
            response = call_ollama(prompt, temperature=0.3)

            if not response:
                print(f"[ERROR] Empty response from Ollama for {content_data['url']}")
                return self._generate_fallback_analysis(content_data, topic)

            # Parse response
            analysis = self._parse_ollama_response(response)

            # Add metadata
            analysis["analyzed_at"] = datetime.utcnow().isoformat()
            analysis["analysis_model"] = self.model
            analysis["content_word_count"] = content_data.get("word_count", 0)

            print(f"[OK] Analysis complete for {content_data['url'][:50]}... (Relevance: {analysis.get('relevance_score', 'N/A')})")
            return analysis

        except Exception as e:
            print(f"[ERROR] Analysis failed for {content_data['url']}: {e}")
            return self._generate_fallback_analysis(content_data, topic, error=str(e))

    def _prepare_content_for_analysis(self, content_data: Dict) -> str:
        """Prepare and truncate content for LLM analysis."""
        content = content_data.get("main_content", "")

        if not content:
            return f"Title: {content_data.get('title', 'No title')}\nURL: {content_data.get('url', '')}"

        # Truncate intelligently
        if len(content) <= MAX_CONTENT_LENGTH:
            return content

        # Keep beginning and end
        keep_start = int(MAX_CONTENT_LENGTH * 0.7)
        keep_end = int(MAX_CONTENT_LENGTH * 0.2)

        start_part = content[:keep_start]
        end_part = content[-keep_end:] if keep_end > 0 else ""

        return f"{start_part}\n\n[...content truncated...]\n\n{end_part}"

    def _create_analysis_prompt(self, content: str, content_data: Dict, topic: str) -> str:
        """Create comprehensive analysis prompt for Ollama."""
        return f"""You are an expert content analyst. Analyze the following webpage content about "{topic}" and provide a comprehensive JSON analysis.

URL: {content_data.get('url', 'Unknown')}
Title: {content_data.get('title', 'No title')}
Extraction Method: {content_data.get('extraction_method', 'Unknown')}

CONTENT TO ANALYZE:
{content}

Provide a detailed analysis as a valid JSON object with these exact fields:

{{
  "summary": "A clear 2-3 sentence summary of the main content and its purpose",
  "key_topics": ["topic1", "topic2", "topic3", "topic4", "topic5"],
  "key_points": [
    "Main takeaway or insight 1",
    "Main takeaway or insight 2",
    "Main takeaway or insight 3",
    "Main takeaway or insight 4"
  ],
  "entities": ["Entity1", "Entity2", "Entity3"],
  "relevance_score": 8,
  "content_quality": "high",
  "sentiment": "informative",
  "content_type": "tutorial",
  "target_audience": "beginners",
  "difficulty_level": "intermediate",
  "actionable_insights": [
    "Specific action readers can take based on this content",
    "Another actionable insight"
  ],
  "related_concepts": ["concept1", "concept2", "concept3"],
  "credibility_score": 7
}}

Guidelines:
- summary: Explain what this content is about and its main value
- key_topics: 3-5 main topics/themes covered (relevant to "{topic}")
- key_points: 3-5 specific insights, facts, or takeaways
- entities: Important names, technologies, tools, companies, or concepts mentioned
- relevance_score: 1-10 how relevant this is to "{topic}"
- content_quality: "high", "medium", or "low" based on depth, clarity, and usefulness
- sentiment: "positive", "negative", "neutral", or "informative"
- content_type: "tutorial", "overview", "opinion", "documentation", "news", "discussion", "reference", "case_study"
- target_audience: "beginners", "intermediate", "advanced", "general", "professionals"
- difficulty_level: "beginner", "intermediate", "advanced"
- actionable_insights: Specific actions someone could take based on this content
- related_concepts: Related topics someone might want to explore
- credibility_score: 1-10 based on source authority, evidence, and expertise shown

Return ONLY the valid JSON object, no other text."""

    def _parse_ollama_response(self, response: str) -> Dict:
        """Parse JSON response from Ollama."""
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start != -1 and json_end != 0:
                json_str = response[json_start:json_end]
                analysis = json.loads(json_str)

                # Validate required fields
                required_fields = [
                    "summary", "key_topics", "key_points", "entities",
                    "relevance_score", "content_quality", "sentiment", "content_type"
                ]

                for field in required_fields:
                    if field not in analysis:
                        analysis[field] = self._get_default_value(field)

                # Validate data types and constraints
                analysis["relevance_score"] = max(1, min(10, int(analysis.get("relevance_score", 5))))
                analysis["credibility_score"] = max(1, min(10, int(analysis.get("credibility_score", 5))))

                # Ensure lists are actually lists
                for list_field in ["key_topics", "key_points", "entities", "actionable_insights", "related_concepts"]:
                    if list_field in analysis and not isinstance(analysis[list_field], list):
                        analysis[list_field] = [str(analysis[list_field])]

                return analysis
            else:
                raise ValueError("No JSON found in response")

        except (json.JSONDecodeError, ValueError) as e:
            print(f"JSON parsing error: {e}")
            # Try to extract partial information
            return self._extract_partial_analysis(response)

    def _extract_partial_analysis(self, response: str) -> Dict:
        """Attempt to extract analysis from malformed response."""
        analysis = self._get_default_analysis()

        # Try to extract some fields using regex
        try:
            if '"summary"' in response:
                summary_match = re.search(r'"summary":\s*"([^"]+)"', response)
                if summary_match:
                    analysis["summary"] = summary_match.group(1)

            if '"relevance_score"' in response:
                score_match = re.search(r'"relevance_score":\s*(\d+)', response)
                if score_match:
                    analysis["relevance_score"] = int(score_match.group(1))

        except Exception:
            pass

        return analysis

    def _get_default_value(self, field: str):
        """Get default value for a field."""
        defaults = {
            "summary": "Analysis unavailable",
            "key_topics": [],
            "key_points": [],
            "entities": [],
            "relevance_score": 5,
            "content_quality": "unknown",
            "sentiment": "neutral",
            "content_type": "unknown",
            "target_audience": "general",
            "difficulty_level": "unknown",
            "actionable_insights": [],
            "related_concepts": [],
            "credibility_score": 5
        }
        return defaults.get(field, "unknown")

    def _get_default_analysis(self) -> Dict:
        """Generate default analysis structure."""
        return {
            "summary": "Content analysis unavailable",
            "key_topics": [],
            "key_points": [],
            "entities": [],
            "relevance_score": 5,
            "content_quality": "unknown",
            "sentiment": "neutral",
            "content_type": "unknown",
            "target_audience": "general",
            "difficulty_level": "unknown",
            "actionable_insights": [],
            "related_concepts": [],
            "credibility_score": 5
        }

    def _generate_fallback_analysis(self, content_data: Dict, topic: str, error: str = None) -> Dict:
        """Generate fallback analysis when LLM fails."""
        analysis = self._get_default_analysis()

        # Use available data
        title = content_data.get("title", "")
        url = content_data.get("url", "")

        if title:
            analysis["summary"] = f"Content about {topic}: {title}"
            analysis["key_topics"] = [topic]

        if error:
            analysis["analysis_error"] = error

        analysis["analyzed_at"] = datetime.utcnow().isoformat()
        analysis["analysis_model"] = self.model
        analysis["content_word_count"] = content_data.get("word_count", 0)

        return analysis


class ContentAnalysisAgent:
    """Main agent orchestrating the content analysis pipeline."""

    def __init__(self):
        self.extractor = WebContentExtractor()
        self.analyzer = OllamaContentAnalyzer()
        self.stats = {
            "total_urls": 0,
            "successful_extractions": 0,
            "successful_analyses": 0,
            "failed_urls": [],
            "start_time": None,
            "end_time": None
        }

    def analyze_scraped_data(self, scraped_file_path: str, max_urls: int = None, urls_per_source: int = 4) -> Dict:
        """
        Main function to analyze all URLs from scraped data.

        Args:
            scraped_file_path: Path to the scraped JSON data file
            max_urls: Maximum TOTAL URLs to process (None = use urls_per_source limit)
            urls_per_source: Maximum URLs to analyze per source (default: 4)

        Returns:
            Enriched data with analysis results
        """
        print(f"[START] Starting Content Analysis Agent")
        print(f"[FILE] Loading scraped data from: {scraped_file_path}")
        print(f"[CONFIG] Analyzing up to {urls_per_source} URLs per source")

        self.stats["start_time"] = datetime.utcnow()

        # Load scraped data
        try:
            with open(scraped_file_path, 'r', encoding='utf-8') as f:
                scraped_data = json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to load scraped data: {e}")
            return None

        topic = scraped_data.get("topic", "Unknown Topic")
        results = scraped_data.get("results", {})

        print(f"[INFO] Topic: {topic}")
        print(f"[SEARCH] Found {len(results)} data sources")

        # Collect URLs to analyze - LIMITED PER SOURCE
        all_urls = []
        for source, items in results.items():
            if source == "top_10_overall":  # Skip this special key
                continue

            # Limit URLs per source to save time
            source_urls = []
            for item in items[:urls_per_source]:  # Only take first N URLs from each source
                if "url" in item:
                    source_urls.append({
                        "url": item["url"],
                        "title": item.get("title", ""),
                        "description": item.get("description", ""),
                        "source": source,
                        "original_item": item
                    })

            all_urls.extend(source_urls)
            if source_urls:
                print(f"[SOURCE] {source}: Selected {len(source_urls)} URLs for analysis (out of {len(items)} total)")

        self.stats["total_urls"] = len(all_urls)

        if max_urls and len(all_urls) > max_urls:
            print(f"[LIMIT] Limiting analysis to {max_urls} URLs (from {len(all_urls)} total)")
            all_urls = all_urls[:max_urls]

        print(f"[TARGET] Analyzing {len(all_urls)} URLs with local Ollama model...")

        # Process URLs with controlled parallelism
        enriched_results = {}

        # Initialize result structure
        for source in results.keys():
            enriched_results[source] = []

        # Process URLs in parallel
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit tasks
            future_to_url = {
                executor.submit(self._process_single_url, url_data, topic): url_data
                for url_data in all_urls
            }

            # Collect results
            processed = 0
            for future in as_completed(future_to_url):
                url_data = future_to_url[future]
                processed += 1

                try:
                    enriched_item = future.result(timeout=LLM_TIMEOUT + REQUEST_TIMEOUT + 10)
                    source = enriched_item["source"]
                    enriched_results[source].append(enriched_item)

                    if enriched_item.get("extraction_status") == "success":
                        self.stats["successful_extractions"] += 1

                    if enriched_item.get("analyzed_content"):
                        self.stats["successful_analyses"] += 1

                    progress = (processed / len(all_urls)) * 100
                    print(f"[PROGRESS] Progress: {processed}/{len(all_urls)} ({progress:.1f}%) - {enriched_item['title'][:50]}...")

                except Exception as e:
                    print(f"[ERROR] Failed to process {url_data['url']}: {e}")
                    self.stats["failed_urls"].append(url_data["url"])
                    # Add original item to results
                    source = url_data["source"]
                    enriched_results[source].append(url_data["original_item"])

        # Preserve top_10_overall if it exists
        if "top_10_overall" in results:
            enriched_results["top_10_overall"] = results["top_10_overall"]

        # Create final enriched data
        enriched_data = scraped_data.copy()
        enriched_data["results"] = enriched_results
        enriched_data["content_analysis_enabled"] = True

        # Add analysis statistics
        self.stats["end_time"] = datetime.utcnow()
        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()

        enriched_data["analysis_stats"] = {
            "total_urls_found": self.stats["total_urls"],
            "urls_analyzed": len(all_urls),
            "successful_extractions": self.stats["successful_extractions"],
            "successful_analyses": self.stats["successful_analyses"],
            "failed_urls_count": len(self.stats["failed_urls"]),
            "analysis_duration_seconds": round(duration, 2),
            "avg_time_per_url": round(duration / len(all_urls), 2) if all_urls else 0,
            "analyzed_at": self.stats["end_time"].isoformat(),
            "ollama_model": self.analyzer.model
        }

        # Print statistics
        print(f"\n[INFO] Analysis Complete!")
        print(f"[TIME]  Total time: {duration:.1f} seconds")
        print(f"[TARGET] URLs analyzed: {len(all_urls)}/{self.stats['total_urls']}")
        print(f"[OK] Successful extractions: {self.stats['successful_extractions']}")
        print(f"[ANALYZE] Successful analyses: {self.stats['successful_analyses']}")
        print(f"[ERROR] Failed URLs: {len(self.stats['failed_urls'])}")

        return enriched_data

    def _process_single_url(self, url_data: Dict, topic: str) -> Dict:
        """Process a single URL: extract content and analyze."""
        try:
            # Extract content
            content_data = self.extractor.extract_content(url_data["url"], url_data["source"])

            # Create enriched item
            enriched_item = url_data["original_item"].copy()
            enriched_item["extracted_content"] = content_data

            # Analyze content if extraction was successful
            if content_data["extraction_status"] in ["success", "partial"] and content_data["main_content"]:
                analysis = self.analyzer.analyze_content(content_data, topic)
                enriched_item["analyzed_content"] = analysis
            else:
                enriched_item["analyzed_content"] = None

            # Add extraction preview
            enriched_item["content_preview"] = content_data.get("content_preview", "")

            # Rate limiting
            rate_limit(RATE_LIMIT_MIN, RATE_LIMIT_MAX)

            return enriched_item

        except Exception as e:
            print(f"[ERROR] Error processing {url_data['url']}: {e}")
            # Return original item with error info
            enriched_item = url_data["original_item"].copy()
            enriched_item["analysis_error"] = str(e)
            return enriched_item

    def save_results(self, enriched_data: Dict, output_file: str = None) -> str:
        """Save enriched results to JSON file."""
        if not output_file:
            # Generate output filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            topic = enriched_data.get("topic", "Unknown")
            clean_topic = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in topic)
            clean_topic = clean_topic.replace(' ', '_')[:50]

            output_file = f"backend/scraped_data/{clean_topic}_ANALYZED_{timestamp}.json"

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(enriched_data, f, indent=2, ensure_ascii=False)

            print(f"[SAVE] Analyzed data saved to: {output_file}")

            # Also save a summary file
            summary_file = output_file.replace('.json', '_SUMMARY.json')
            summary = self._generate_summary(enriched_data)

            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)

            print(f"[SUMMARY] Analysis summary saved to: {summary_file}")

            return output_file

        except Exception as e:
            print(f"[ERROR] Failed to save results: {e}")
            return None

    def _generate_summary(self, enriched_data: Dict) -> Dict:
        """Generate analysis summary."""
        results = enriched_data.get("results", {})
        analysis_stats = enriched_data.get("analysis_stats", {})

        summary = {
            "topic": enriched_data.get("topic"),
            "analysis_overview": analysis_stats,
            "source_breakdown": {},
            "top_insights": {
                "highest_relevance": [],
                "best_quality": [],
                "most_actionable": []
            },
            "content_types": {},
            "target_audiences": {},
            "difficulty_levels": {}
        }

        all_analyzed_items = []

        # Collect analysis data
        for source, items in results.items():
            if source == "top_10_overall":
                continue

            analyzed_count = 0
            for item in items:
                if item.get("analyzed_content"):
                    analyzed_count += 1
                    analyzed_item = {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "source": source,
                        "analysis": item["analyzed_content"]
                    }
                    all_analyzed_items.append(analyzed_item)

            summary["source_breakdown"][source] = {
                "total_items": len(items),
                "analyzed_items": analyzed_count,
                "analysis_rate": round((analyzed_count / len(items)) * 100, 1) if items else 0
            }

        # Generate insights
        if all_analyzed_items:
            # Highest relevance
            relevant_items = sorted(all_analyzed_items,
                                  key=lambda x: x["analysis"].get("relevance_score", 0),
                                  reverse=True)[:5]
            summary["top_insights"]["highest_relevance"] = [
                {
                    "title": item["title"],
                    "url": item["url"],
                    "source": item["source"],
                    "relevance_score": item["analysis"].get("relevance_score", 0),
                    "summary": item["analysis"].get("summary", "")
                }
                for item in relevant_items
            ]

            # Best quality
            quality_items = [item for item in all_analyzed_items
                           if item["analysis"].get("content_quality") == "high"][:5]
            summary["top_insights"]["best_quality"] = [
                {
                    "title": item["title"],
                    "url": item["url"],
                    "source": item["source"],
                    "quality": item["analysis"].get("content_quality", ""),
                    "summary": item["analysis"].get("summary", "")
                }
                for item in quality_items
            ]

            # Count categories
            for item in all_analyzed_items:
                analysis = item["analysis"]

                content_type = analysis.get("content_type", "unknown")
                summary["content_types"][content_type] = summary["content_types"].get(content_type, 0) + 1

                audience = analysis.get("target_audience", "unknown")
                summary["target_audiences"][audience] = summary["target_audiences"].get(audience, 0) + 1

                difficulty = analysis.get("difficulty_level", "unknown")
                summary["difficulty_levels"][difficulty] = summary["difficulty_levels"].get(difficulty, 0) + 1

        return summary


def main():
    """Main function."""
    print("[ANALYZE] Content Analysis Agent - Powered by Local Ollama")
    print("=" * 60)

    # Get input file
    if len(sys.argv) > 1:
        scraped_file = sys.argv[1]
    else:
        # Look for the most recent scraped data file
        scraped_dir = Path("backend/scraped_data")
        if scraped_dir.exists():
            json_files = list(scraped_dir.glob("*.json"))
            if json_files:
                # Get most recent file
                scraped_file = str(max(json_files, key=lambda x: x.stat().st_mtime))
                print(f"[SEARCH] Auto-detected latest scraped file: {scraped_file}")
            else:
                print("[ERROR] No scraped data files found in backend/scraped_data/")
                return
        else:
            print("[ERROR] No scraped data directory found. Run scraping first.")
            return

    if not os.path.exists(scraped_file):
        print(f"[ERROR] File not found: {scraped_file}")
        return

    # Initialize agent
    agent = ContentAnalysisAgent()

    # Ask for URL limit
    try:
        max_urls_input = input(f"\n[TARGET] Maximum URLs to analyze (Enter for unlimited): ").strip()
        max_urls = int(max_urls_input) if max_urls_input else None
    except ValueError:
        max_urls = None

    print(f"\n[START] Starting analysis with Ollama model: {OLLAMA_MODEL}")
    print(f"[NETWORK] Ollama URL: {OLLAMA_URL}")

    # Test Ollama connection
    try:
        test_response = call_ollama("Test connection. Reply with: OK", temperature=0.1)
        if "OK" in test_response or test_response:
            print("[OK] Ollama connection successful")
        else:
            print("[WARN] Ollama connection test unclear - proceeding anyway")
    except Exception as e:
        print(f"[WARN] Ollama connection test failed: {e}")
        proceed = input("Continue anyway? (y/N): ").strip().lower()
        if proceed != 'y':
            return

    # Run analysis
    enriched_data = agent.analyze_scraped_data(scraped_file, max_urls)

    if enriched_data:
        # Save results
        output_file = agent.save_results(enriched_data)

        if output_file:
            print(f"\n[SUCCESS] Analysis complete! Results saved to:")
            print(f"   [EXTRACT] Full data: {output_file}")
            print(f"   [SUMMARY] Summary: {output_file.replace('.json', '_SUMMARY.json')}")
            print(f"\n[TIP] Use view_scraped_data.py to view the results")
        else:
            print("[ERROR] Failed to save results")
    else:
        print("[ERROR] Analysis failed")


if __name__ == "__main__":
    main()