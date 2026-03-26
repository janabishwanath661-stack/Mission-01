import httpx
import json
import os
import re

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "sorc/qwen3.5-claude-4.6-opus")


def call_ollama(prompt: str, temperature: float = 0.3) -> str:
    """Call the local Ollama instance."""
    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "num_ctx": 4096}
            },
            timeout=120.0
        )
        return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"[Ollama Error] {e}")
        return ""


def generate_search_queries(topic: str) -> dict:
    prompt = f"""Generate search engine queries to find info about "{topic}".
Return ONLY a valid JSON object:
{{
  "youtube_query": "best {topic} tutorials beginners",
  "linkedin_query": "{topic} linkedin profiles and groups",
  "facebook_query": "{topic} facebook groups",
  "instagram_query": "{topic} instagram accounts",
  "blog_query": "{topic} best blog tutorial article",
  "reddit_query": "{topic}",
  "events_query": "{topic} workshop webinar",
  "github_query": "{topic}",
  "twitter_query": "{topic} expert tweets threads",
  "quora_query": "{topic} questions answers"
}}"""
    response = call_ollama(prompt, temperature=0.1)
    try:
        return json.loads(response[response.find("{"):response.rfind("}") + 1])
    except:
        t = topic.lower()
        return {k: f"{t} {k.split('_')[0]}" for k in [
            "youtube_query", "linkedin_query", "facebook_query",
            "instagram_query", "blog_query", "reddit_query",
            "events_query", "github_query", "twitter_query", "quora_query"
        ]}


def rank_content(topic: str, results: dict, per_platform: bool = True) -> dict:
    """
    Uses LLM to rank content based on multiple criteria:
    - Engagement metrics (views, likes, upvotes, stars)
    - Relevance to the topic
    - Content quality indicators
    - Recency/freshness

    Returns ranked results per-platform and a global top 10.
    """
    ranked_results = {}
    all_items = []

    # Rank each platform separately
    for platform, items in results.items():
        if not items:
            ranked_results[platform] = []
            continue

        # Prepare content for LLM ranking
        content_list = []
        for idx, item in enumerate(items):
            content_info = {
                "index": idx,
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "engagement": _extract_engagement_metrics(item, platform),
                "platform": platform
            }
            content_list.append(content_info)
            all_items.append((platform, idx, item, content_info["engagement"]))

        # Create ranking prompt for this platform
        if len(content_list) > 1:
            ranked_indices = _rank_with_llm(topic, content_list, platform)
            ranked_results[platform] = [items[i] for i in ranked_indices if i < len(items)]
        else:
            ranked_results[platform] = items

    # Create global top 10
    top_10_global = _create_global_top_10(topic, all_items)
    ranked_results["top_10_overall"] = top_10_global

    return ranked_results


def _extract_engagement_metrics(item: dict, platform: str) -> dict:
    """Extract engagement metrics from scraped item based on platform."""
    metrics = {"score": 0, "details": ""}

    if platform == "youtube":
        # Extract view count from description if available
        desc = item.get("description", "")
        if "views" in desc.lower():
            try:
                # Try to extract number like "1.2M views" or "1,234 views"
                import re
                match = re.search(r'([\d,.]+[KMB]?)\s*views?', desc, re.IGNORECASE)
                if match:
                    view_str = match.group(1)
                    metrics["details"] = f"{view_str} views"
                    # Convert to approximate score
                    metrics["score"] = _parse_engagement_number(view_str)
            except:
                pass

    elif platform == "reddit":
        metrics["score"] = item.get("score", 0) or item.get("subscribers", 0)
        if "score" in item:
            metrics["details"] = f"{item['score']} upvotes"
        elif "subscribers" in item:
            metrics["details"] = f"{item['subscribers']} subscribers"

    elif platform == "github":
        stars = item.get("stars", 0)
        metrics["score"] = stars
        metrics["details"] = f"{stars} stars"

    elif platform == "twitter":
        # Twitter engagement could be in description
        desc = item.get("description", "")
        if "like" in desc.lower() or "retweet" in desc.lower():
            metrics["details"] = desc

    return metrics


def _parse_engagement_number(num_str: str) -> int:
    """Parse engagement numbers like '1.2M', '10K', '1,234' to integers."""
    try:
        num_str = num_str.strip().replace(",", "")
        multiplier = 1

        if num_str.endswith("K"):
            multiplier = 1000
            num_str = num_str[:-1]
        elif num_str.endswith("M"):
            multiplier = 1000000
            num_str = num_str[:-1]
        elif num_str.endswith("B"):
            multiplier = 1000000000
            num_str = num_str[:-1]

        return int(float(num_str) * multiplier)
    except:
        return 0


def _rank_with_llm(topic: str, content_list: list, platform: str) -> list:
    """Use LLM to rank content based on multiple criteria."""
    if len(content_list) <= 1:
        return [0]

    # Create a concise representation for the LLM
    items_summary = []
    for item in content_list[:20]:  # Limit to top 20 to avoid context overflow
        items_summary.append(
            f"{item['index']}. {item['title'][:80]} | {item['engagement']['details'] or 'No metrics'}"
        )

    prompt = f"""You are ranking {platform} content about "{topic}". Consider these criteria:
1. Relevance to topic (most important)
2. Engagement metrics (views/likes/upvotes/stars)
3. Quality indicators (title clarity, description quality)
4. Freshness (if detectable)

Content to rank:
{chr(10).join(items_summary)}

Return ONLY a JSON array of indices in ranked order (best first). Example: [2, 0, 5, 1, 3, 4]
Return the indices as a simple array, nothing else.
"""

    response = call_ollama(prompt, temperature=0.2)

    try:
        # Extract JSON array from response
        match = re.search(r'\[[\d,\s]+\]', response)
        if match:
            ranked_indices = json.loads(match.group(0))
            # Validate indices
            valid_indices = [i for i in ranked_indices if 0 <= i < len(content_list)]
            # Add any missing indices at the end
            missing = [i for i in range(len(content_list)) if i not in valid_indices]
            return valid_indices + missing
    except:
        pass

    # Fallback: sort by engagement score
    sorted_items = sorted(enumerate(content_list),
                         key=lambda x: x[1]["engagement"]["score"],
                         reverse=True)
    return [i for i, _ in sorted_items]


def _create_global_top_10(topic: str, all_items: list) -> list:
    """Create a global top 10 across all platforms using LLM."""
    if not all_items:
        return []

    # Sort by engagement score first to get top candidates
    sorted_items = sorted(all_items, key=lambda x: x[3]["score"], reverse=True)[:30]

    # Prepare for LLM ranking
    items_summary = []
    for idx, (platform, _, item, engagement) in enumerate(sorted_items):
        items_summary.append(
            f"{idx}. [{platform.upper()}] {item.get('title', '')[:70]} | {engagement['details'] or 'No metrics'}"
        )

    prompt = f"""You are selecting the TOP 10 best resources about "{topic}" from multiple platforms.
Consider: relevance, engagement, quality, and diversity (include different platforms when possible).

Resources:
{chr(10).join(items_summary)}

Return ONLY a JSON array of the 10 best indices (best first). Example: [5, 12, 0, 8, 3, 15, 1, 9, 4, 7]
"""

    response = call_ollama(prompt, temperature=0.3)

    try:
        match = re.search(r'\[[\d,\s]+\]', response)
        if match:
            top_indices = json.loads(match.group(0))[:10]
            # Validate and return items
            top_10 = []
            for idx in top_indices:
                if 0 <= idx < len(sorted_items):
                    _, _, item, _ = sorted_items[idx]
                    top_10.append(item)
            return top_10
    except:
        pass

    # Fallback: return top 10 by engagement
    return [item for _, _, item, _ in sorted_items[:10]]


def generate_deep_insights(topic: str, results: dict) -> dict:
    """
    Feeds a sample of the scraped titles/descriptions to the LLM
    to generate a rich, multi-part intelligence report.
    """
    sample_context = []
    for cat, items in results.items():
        for item in items[:3]:
            sample_context.append(
                f"- {item.get('title', '')}: {item.get('description', '')[:100]}"
            )

    context_str = "\n".join(sample_context)[:2000]

    prompt = f"""You are a senior research analyst. Based on the topic "{topic}" and the following scraped web data, generate a deep insight report.

Scraped Data Context:
{context_str}

Return ONLY a valid JSON object with the following structure:
{{
  "summary": "A 2-sentence executive summary of what this topic is and why it matters today.",
  "trends": ["Trend 1 based on data", "Trend 2 based on data", "Trend 3 based on data"],
  "action_plan": ["Step 1 to start learning/engaging", "Step 2", "Step 3"]
}}
"""
    response = call_ollama(prompt, temperature=0.4)
    try:
        return json.loads(response[response.find("{"):response.rfind("}") + 1])
    except:
        return {
            "summary": f"Explore everything about {topic}. We've aggregated the best resources across the web.",
            "trends": [
                "Community growth",
                "Increasing open-source tools",
                "High demand for tutorials"
            ],
            "action_plan": [
                "Watch the top YouTube videos",
                "Join a Reddit community",
                "Follow GitHub repos"
            ]
        }
