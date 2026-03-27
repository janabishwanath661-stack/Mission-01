import json
import os
import re
import time
import threading
from typing import Dict, Optional

# Hugging Face configuration
HF_MODEL_ID = os.getenv("HF_MODEL_ID", "microsoft/phi-2")
HF_DEVICE = os.getenv("HF_DEVICE", "auto")  # "auto", "cpu", "cuda", "cuda:0", etc.
HF_MAX_NEW_TOKENS = int(os.getenv("HF_MAX_NEW_TOKENS", "512"))

# Global model instance (lazy loaded)
_model = None
_tokenizer = None
_model_lock = threading.Lock()
_model_loaded = False
_model_error = None


def _load_model():
    """Load the Hugging Face model lazily on first use."""
    global _model, _tokenizer, _model_loaded, _model_error

    with _model_lock:
        if _model_loaded:
            return _model is not None

        try:
            print(f"[HuggingFace] Loading model: {HF_MODEL_ID}")
            print(f"[HuggingFace] Device: {HF_DEVICE}")

            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch

            # Determine device
            if HF_DEVICE == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                device = HF_DEVICE

            print(f"[HuggingFace] Using device: {device}")

            # Load tokenizer
            _tokenizer = AutoTokenizer.from_pretrained(
                HF_MODEL_ID,
                trust_remote_code=True
            )

            # Set pad token if not set
            if _tokenizer.pad_token is None:
                _tokenizer.pad_token = _tokenizer.eos_token

            # Load model with appropriate settings
            load_kwargs = {
                "trust_remote_code": True,
                "low_cpu_mem_usage": True,
            }

            if device == "cuda":
                load_kwargs["dtype"] = torch.float16
                load_kwargs["device_map"] = "auto"
            else:
                load_kwargs["dtype"] = torch.float32

            _model = AutoModelForCausalLM.from_pretrained(
                HF_MODEL_ID,
                **load_kwargs
            )

            if device == "cpu":
                _model = _model.to(device)

            _model.eval()
            _model_loaded = True
            _model_error = None

            print(f"[HuggingFace] Model loaded successfully!")
            return True

        except Exception as e:
            _model_error = str(e)
            _model_loaded = True  # Mark as loaded to prevent retry loops
            print(f"[HuggingFace] Failed to load model: {e}")
            return False


def check_model_health(model_id: str = None) -> Dict:
    """
    Check if the Hugging Face model is loaded and ready.

    Returns:
        {
            "healthy": bool,
            "model": str,
            "device": str,
            "error": str or None,
            "response_time": float
        }
    """
    model_id = model_id or HF_MODEL_ID

    result = {
        "healthy": False,
        "model": model_id,
        "device": HF_DEVICE,
        "error": None,
        "response_time": None
    }

    try:
        start_time = time.time()

        # Try to load model if not loaded
        if not _model_loaded:
            success = _load_model()
            if not success:
                result["error"] = _model_error or "Failed to load model"
                return result

        if _model is None:
            result["error"] = _model_error or "Model not loaded"
            return result

        # Test with a simple generation
        test_response = call_llm("Say OK", temperature=0.1, max_tokens=10)
        result["response_time"] = round(time.time() - start_time, 2)

        if test_response:
            result["healthy"] = True
            # Get actual device
            import torch
            if hasattr(_model, 'device'):
                result["device"] = str(_model.device)
            elif torch.cuda.is_available() and next(_model.parameters()).is_cuda:
                result["device"] = "cuda"
            else:
                result["device"] = "cpu"
        else:
            result["error"] = "Model test generation failed"

    except Exception as e:
        result["error"] = str(e)

    return result


# Backward compatibility alias
def check_ollama_health(url: str = None, model: str = None) -> Dict:
    """Backward compatible alias for check_model_health."""
    health = check_model_health(model)
    # Add url field for backward compatibility
    health["url"] = "local"
    health["models_available"] = [HF_MODEL_ID]
    return health


def call_llm(prompt: str, temperature: float = 0.3, max_tokens: int = None, max_retries: int = 2) -> str:
    """
    Call the local Hugging Face model for text generation.

    Args:
        prompt: The prompt to send to the model
        temperature: Generation temperature (0.0 to 1.0)
        max_tokens: Maximum new tokens to generate
        max_retries: Maximum number of retry attempts

    Returns:
        Generated text response or empty string on failure
    """
    max_tokens = max_tokens or HF_MAX_NEW_TOKENS
    last_error = None

    # Ensure model is loaded
    if not _model_loaded:
        if not _load_model():
            print(f"[HuggingFace] Model not loaded: {_model_error}")
            return ""

    if _model is None or _tokenizer is None:
        print(f"[HuggingFace] Model not available: {_model_error}")
        return ""

    for attempt in range(max_retries + 1):
        try:
            import torch

            # Tokenize input
            inputs = _tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=2048
            )

            # Move to same device as model
            device = next(_model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}

            # Generate
            with torch.no_grad():
                outputs = _model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature if temperature > 0 else 0.01,
                    do_sample=temperature > 0,
                    pad_token_id=_tokenizer.pad_token_id,
                    eos_token_id=_tokenizer.eos_token_id,
                )

            # Decode response (only the new tokens)
            input_length = inputs["input_ids"].shape[1]
            response_tokens = outputs[0][input_length:]
            response_text = _tokenizer.decode(response_tokens, skip_special_tokens=True).strip()

            if attempt > 0:
                print(f"[HuggingFace] Retry {attempt} successful!")

            return response_text

        except Exception as e:
            last_error = f"Generation error: {e}"

        if attempt < max_retries:
            wait_time = 2 ** attempt
            print(f"[HuggingFace] Attempt {attempt + 1} failed: {last_error}")
            print(f"[HuggingFace] Retrying in {wait_time}s...")
            time.sleep(wait_time)

    print(f"[HuggingFace Error] All attempts failed. Last error: {last_error}")
    return ""


# Backward compatibility alias
def call_ollama(prompt: str, temperature: float = 0.3, max_retries: int = 2) -> str:
    """Backward compatible alias for call_llm."""
    return call_llm(prompt, temperature, max_retries=max_retries)


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
    response = call_llm(prompt, temperature=0.1)
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

    response = call_llm(prompt, temperature=0.2)

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

    response = call_llm(prompt, temperature=0.3)

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
    response = call_llm(prompt, temperature=0.4)
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
