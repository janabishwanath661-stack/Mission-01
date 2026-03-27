# Try to import Celery (optional for development)
try:
    from celery import Celery
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    Celery = None

import os
import sys
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path for proper imports in Celery context
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scrapers.youtube_scraper import scrape_youtube
from scrapers.universal_search_scraper import scrape_blogs, scrape_linkedin, scrape_facebook, scrape_instagram
from scrapers.reddit_scraper import scrape_reddit_communities
from scrapers.eventbrite_scraper import scrape_eventbrite
from scrapers.github_scraper import scrape_github_repos
from scrapers.twitter_scraper import scrape_twitter
from scrapers.quora_scraper import scrape_quora
from scrapers.blog_scraper import scrape_blog_articles
from llm import generate_search_queries, generate_deep_insights, rank_content, check_ollama_health
from database import save_results
import google_api

# Celery configuration (only if available)
if CELERY_AVAILABLE:
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
    celery_app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)
else:
    celery_app = None

# Directory to store scraped data
SCRAPED_DATA_DIR = os.path.join(os.path.dirname(__file__), "scraped_data")
os.makedirs(SCRAPED_DATA_DIR, exist_ok=True)


def save_scraped_data_to_file(job_id: str, topic: str, data: dict):
    """
    Save scraped data to a JSON file for inspection.

    Args:
        job_id: Unique job identifier
        topic: The search topic
        data: The complete scraped data
    """
    try:
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Clean topic for filename
        clean_topic = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in topic)
        clean_topic = clean_topic.replace(' ', '_')[:50]  # Limit length

        filename = f"{clean_topic}_{timestamp}_{job_id[:8]}.json"
        filepath = os.path.join(SCRAPED_DATA_DIR, filename)

        # Save data to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[Data Saved] Scraped data saved to: {filepath}")
        return filepath
    except Exception as e:
        print(f"[File Save Error] Could not save scraped data: {e}")
        return None


def save_individual_url_data(url_data: dict, source: str, job_id: str, url_index: int):
    """
    Save individual URL data to its own JSON file.

    Args:
        url_data: The data for a single URL
        source: The source/platform name (e.g., 'youtube', 'reddit')
        job_id: Unique job identifier
        url_index: Index of this URL in the source results

    Returns:
        Path to the saved file
    """
    try:
        # Create job-specific directory
        job_dir = os.path.join(SCRAPED_DATA_DIR, f"job_{job_id[:8]}")
        os.makedirs(job_dir, exist_ok=True)

        # Create source-specific subdirectory
        source_dir = os.path.join(job_dir, source)
        os.makedirs(source_dir, exist_ok=True)

        # Generate safe filename from URL or title
        if url_data.get('title'):
            # Use title for filename
            safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_'
                               for c in url_data['title'])
            safe_title = safe_title.replace(' ', '_')[:50]  # Limit length
            filename = f"{url_index:03d}_{safe_title}.json"
        else:
            # Fall back to index-based naming
            filename = f"{url_index:03d}_url.json"

        filepath = os.path.join(source_dir, filename)

        # Add metadata
        enriched_data = {
            "metadata": {
                "job_id": job_id,
                "source": source,
                "url_index": url_index,
                "saved_at": datetime.now().isoformat(),
                "file_path": filepath
            },
            "data": url_data
        }

        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(enriched_data, f, indent=2, ensure_ascii=False)

        return filepath

    except Exception as e:
        print(f"[URL Save Error] Could not save URL {url_index} from {source}: {e}")
        return None


def save_individual_scraper_results(source: str, data: list, job_id: str):
    """
    Save individual scraper results to a separate file.
    Also saves each URL to its own individual file.

    Args:
        source: The source/platform name (e.g., 'youtube', 'reddit')
        data: The scraped data from that source
        job_id: Unique job identifier
    """
    try:
        if not data:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{source}_{timestamp}_{job_id[:8]}.json"
        filepath = os.path.join(SCRAPED_DATA_DIR, filename)

        save_data = {
            "source": source,
            "timestamp": timestamp,
            "count": len(data),
            "data": data
        }

        # Save aggregated source file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

        print(f"[Individual Save] {source} data saved to: {filepath}")

        # Save each URL individually
        saved_urls = 0
        for idx, url_data in enumerate(data):
            url_file = save_individual_url_data(url_data, source, job_id, idx)
            if url_file:
                saved_urls += 1

        print(f"[URL Files] Saved {saved_urls}/{len(data)} individual URL files for {source}")

        return filepath
    except Exception as e:
        print(f"[Individual Save Error] Could not save {source} data: {e}")
        return None


def analyze_urls_content(results: dict, topic: str, job_id: str, max_urls: int = 50, urls_per_source: int = 4) -> dict:
    """
    Analyze URLs content using the Content Analysis Agent.

    Args:
        results: Ranked results from scraping
        topic: Search topic
        job_id: Unique job identifier
        max_urls: Maximum TOTAL URLs to analyze (legacy parameter)
        urls_per_source: Maximum URLs to analyze per source/platform (default: 4)

    Returns:
        Enriched results with analyzed content or error info
    """
    print(f"[Content Analysis] Starting analysis for job {job_id}")
    print(f"[Content Analysis] Will analyze up to {urls_per_source} URLs per source")

    # Check Ollama health before starting analysis
    try:
        health = check_ollama_health()
        if not health["healthy"]:
            error_msg = f"Ollama not available: {health['error']}"
            print(f"[Content Analysis Error] {error_msg}")
            return {
                "error": error_msg,
                "health_check": health,
                "original_results": results
            }
        else:
            print(f"[Content Analysis] Ollama healthy: {health['url']} with {health['model']} ({health['response_time']}s)")
    except Exception as e:
        error_msg = f"Ollama health check failed: {e}"
        print(f"[Content Analysis Error] {error_msg}")
        return {
            "error": error_msg,
            "original_results": results
        }

    try:
        # Import content analysis agent with proper path
        try:
            from content_analysis_agent import ContentAnalysisAgent
        except ImportError as e:
            # Try alternative import path
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from content_analysis_agent import ContentAnalysisAgent

        print(f"[Content Analysis] ContentAnalysisAgent imported successfully")

        # Create temporary data file for the agent to process
        temp_data = {
            "topic": topic,
            "results": results,
            "total_results": sum(len(items) for items in results.values() if isinstance(items, list))
        }

        # Create temporary file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_filename = f"temp_analysis_{job_id}_{timestamp}.json"
        temp_filepath = os.path.join(SCRAPED_DATA_DIR, temp_filename)

        with open(temp_filepath, 'w', encoding='utf-8') as f:
            json.dump(temp_data, f, indent=2, ensure_ascii=False)

        print(f"[Content Analysis] Created temporary file: {temp_filepath}")

        # Initialize agent and run analysis using proper method
        agent = ContentAnalysisAgent()
        enriched_data = agent.analyze_scraped_data(
            temp_filepath,
            max_urls=max_urls,
            urls_per_source=urls_per_source
        )

        # Clean up temporary file
        try:
            os.remove(temp_filepath)
            print(f"[Content Analysis] Cleaned up temporary file")
        except Exception as cleanup_error:
            print(f"[Content Analysis] Warning: Could not clean up temp file: {cleanup_error}")

        if enriched_data is None:
            raise Exception("Content analysis agent returned None")

        print(f"[Content Analysis] Analysis completed successfully for {job_id}")
        return enriched_data.get("results", results)

    except ImportError as e:
        error_msg = f"Could not import content analysis agent: {e}"
        print(f"[Content Analysis Error] {error_msg}")
        print(f"[Content Analysis Error] Python path: {sys.path}")
        return {
            "error": error_msg,
            "import_error": True,
            "original_results": results
        }
    except Exception as e:
        error_msg = f"Content analysis failed: {e}"
        print(f"[Content Analysis Error] {error_msg}")
        import traceback
        print(f"[Content Analysis Error] Traceback: {traceback.format_exc()}")
        return {
            "error": error_msg,
            "original_results": results
        }


# Helper function to make task decorators optional
def celery_task_decorator(*args, **kwargs):
    """Decorator that works with or without Celery."""
    def decorator(func):
        if CELERY_AVAILABLE and celery_app:
            # Use actual Celery decorator
            return celery_app.task(*args, **kwargs)(func)
        else:
            # No Celery - just return the function unchanged but add apply_async method
            def apply_async(args_list=None, task_id=None, **kwargs):
                # Mock apply_async - just return a mock result
                return MockAsyncResult()
            func.apply_async = apply_async
            return func
    return decorator

class MockAsyncResult:
    """Mock AsyncResult for when Celery is not available."""
    def __init__(self):
        self.state = "PENDING"

    def ready(self):
        return False


@celery_task_decorator(bind=True, name="analyze_content")
def analyze_content_task(self, job_id: str, results: dict, topic: str, max_urls: int = 50, urls_per_source: int = 4):
    """
    Separate task to analyze content from existing search results.

    Args:
        job_id: Search job ID
        results: Existing search results
        topic: Search topic
        max_urls: Maximum TOTAL URLs to analyze (legacy, now uses urls_per_source)
        urls_per_source: Maximum URLs to analyze per source (default: 4)
    """
    try:
        # Count sources
        num_sources = sum(1 for k, v in results.items() if isinstance(v, list) and k != "top_10_overall")
        estimated_urls = num_sources * urls_per_source

        # Update task state with startup info
        self.update_state(
            state="PROGRESS",
            meta={
                "step": "Initializing content analysis...",
                "progress": 5,
                "details": f"Will analyze up to {urls_per_source} URLs per source (~{estimated_urls} total)"
            }
        )

        print(f"[Content Analysis Task] Starting analysis for job {job_id}")
        print(f"[Content Analysis Task] Topic: {topic}")
        print(f"[Content Analysis Task] URLs per source: {urls_per_source}")

        # Check total URLs available
        total_urls = sum(len(items) for items in results.values() if isinstance(items, list))
        print(f"[Content Analysis Task] Total URLs available: {total_urls}")
        print(f"[Content Analysis Task] Will analyze ~{estimated_urls} URLs (top {urls_per_source} from each source)")

        self.update_state(
            state="PROGRESS",
            meta={
                "step": f"Analyzing top {urls_per_source} URLs from each source...",
                "progress": 10,
                "details": f"Processing {num_sources} sources (~{estimated_urls} URLs total)"
            }
        )

        # Run content analysis with improved error handling
        analysis_result = analyze_urls_content(
            results,
            topic,
            job_id,
            max_urls=max_urls,
            urls_per_source=urls_per_source
        )

        # Check if analysis returned an error        # Check if analysis returned an error
        if isinstance(analysis_result, dict) and "error" in analysis_result:
            print(f"[Content Analysis Task Error] {analysis_result['error']}")

            # Update task state with specific error
            error_details = {
                "step": f"Analysis failed: {analysis_result['error']}",
                "progress": 0,
                "error": analysis_result['error']
            }

            # Add specific error context
            if "health_check" in analysis_result:
                health = analysis_result["health_check"]
                error_details["health_info"] = {
                    "ollama_url": health.get("url"),
                    "ollama_model": health.get("model"),
                    "models_available": health.get("models_available", []),
                    "error": health.get("error")
                }

            if analysis_result.get("import_error"):
                error_details["import_error"] = True
                error_details["troubleshooting"] = [
                    "Content analysis agent could not be imported",
                    "Check if content_analysis_agent.py exists in project root",
                    "Verify Python path configuration"
                ]

            self.update_state(state="PROGRESS", meta=error_details)

            # Return original results with error info
            return {
                "topic": topic,
                "results": analysis_result.get("original_results", results),
                "total_results": sum(len(items) for items in results.values() if isinstance(items, list)),
                "content_analysis_enabled": False,
                "analysis_error": analysis_result["error"],
                "error_details": error_details
            }

        self.update_state(
            state="PROGRESS",
            meta={
                "step": "Analysis complete, saving results...",
                "progress": 95,
                "details": "Finalizing and saving analyzed data"
            }
        )

        # Create final data structure with successful analysis
        counts = {k: len(v) for k, v in analysis_result.items() if isinstance(v, list)}

        final_data = {
            "topic": topic,
            "results": analysis_result,
            "total_results": sum(counts.values()),
            "counts": counts,
            "content_analysis_enabled": True,
            "analysis_job_id": job_id,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }

        # Save individual URL files with analyzed content
        print(f"[URL Save] Saving individual analyzed URL files for job {job_id}")
        total_analyzed_urls_saved = 0
        for source, data in analysis_result.items():
            if source != "top_10_overall" and isinstance(data, list) and len(data) > 0:
                save_individual_scraper_results(source, data, f"{job_id}_ANALYZED")
                total_analyzed_urls_saved += len(data)
        print(f"[URL Save] Completed: {total_analyzed_urls_saved} analyzed URL files saved")

        # Save analyzed data to file
        save_scraped_data_to_file(job_id, f"{topic}_ANALYZED", final_data)

        print(f"[Content Analysis Task] Successfully completed analysis for {job_id}")
        return final_data

    except Exception as e:
        error_msg = str(e)
        print(f"[Content Analysis Task Error] Unexpected error: {error_msg}")

        # Import traceback for detailed error info
        import traceback
        traceback_str = traceback.format_exc()
        print(f"[Content Analysis Task Error] Traceback: {traceback_str}")

        # Update task state with error
        self.update_state(
            state="PROGRESS",
            meta={
                "step": f"Critical error: {error_msg}",
                "progress": 0,
                "error": error_msg,
                "traceback": traceback_str[:1000]  # Limit traceback length
            }
        )

        # Return error data with original results
        return {
            "topic": topic,
            "results": results,  # Return original results
            "total_results": sum(len(items) for items in results.values() if isinstance(items, list)),
            "error": error_msg,
            "content_analysis_enabled": False,
            "critical_error": True
        }

# Available platforms for searching
AVAILABLE_SOURCES = [
    "youtube", "github", "reddit", "twitter", "blogs",
    "linkedin", "facebook", "instagram", "quora", "events"
]

# Celery configuration (only if Celery is available)
if CELERY_AVAILABLE and celery_app:
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        result_extended=True,
    )


@celery_task_decorator(bind=True, name="scrape_topic")
def scrape_topic_task(self, topic: str, job_id: str, search_mode: str = "scraping", sources: list = None):
    """
    Main task that orchestrates all scraping/API and LLM operations.

    Args:
        topic: The search topic
        job_id: Unique job identifier
        search_mode: "scraping" or "api" (default: "scraping")
        sources: List of platforms to search (default: all platforms)
    """
    try:
        # If no sources specified, use all available sources
        if not sources:
            sources = AVAILABLE_SOURCES

        # Validate sources
        sources = [s.lower() for s in sources if s.lower() in AVAILABLE_SOURCES]
        if not sources:
            sources = AVAILABLE_SOURCES

        # Step 1: Generate search queries using LLM
        self.update_state(
            state="PROGRESS",
            meta={"step": "Local LLM generating queries...", "progress": 10}
        )
        q = generate_search_queries(topic)

        results = {}

        # Determine which method to use
        use_api = (search_mode == "api" and google_api.is_api_available())

        if use_api:
            # Use Google API for selected platforms
            self.update_state(
                state="PROGRESS",
                meta={"step": "Fetching results via Google API...", "progress": 30}
            )

            # Search only selected platforms
            if "youtube" in sources:
                results["youtube"] = google_api.search_youtube_videos(q.get("youtube_query", topic))
            if "github" in sources:
                results["github"] = google_api.search_github_repos(q.get("github_query", topic))
            if "reddit" in sources:
                results["reddit"] = google_api.search_reddit_content(q.get("reddit_query", topic))
            if "twitter" in sources:
                results["twitter"] = google_api.search_twitter_content(q.get("twitter_query", topic))
            if "blogs" in sources:
                results["blogs"] = google_api.search_blog_articles(q.get("blog_query", f"{topic} tutorial"))
            if "linkedin" in sources:
                results["linkedin"] = google_api.search_linkedin_content(q.get("linkedin_query", topic))
            if "quora" in sources:
                results["quora"] = google_api.search_quora_content(q.get("quora_query", topic))
            if "events" in sources:
                results["events"] = google_api.search_events(q.get("events_query", f"{topic} event"))

            # Fill in platforms that API doesn't support with scraping (if selected)
            if "facebook" in sources:
                results["facebook"] = scrape_facebook(q.get("facebook_query", f"{topic} facebook groups"))
            if "instagram" in sources:
                results["instagram"] = scrape_instagram(q.get("instagram_query", f"{topic} instagram"))

        else:
            # Use traditional web scraping for selected platforms
            if search_mode == "api":
                print("[Warning] API mode requested but not available. Falling back to scraping.")

            # PARALLEL SCRAPING - All scrapers run simultaneously for speed
            self.update_state(
                state="PROGRESS",
                meta={"step": "Scraping all sources in parallel...", "progress": 30}
            )

            # Build scraper tasks dynamically based on selected sources
            scraper_tasks = {}
            if "youtube" in sources:
                scraper_tasks["youtube"] = (scrape_youtube, q.get("youtube_query", topic))
            if "github" in sources:
                scraper_tasks["github"] = (scrape_github_repos, q.get("github_query", topic))
            if "linkedin" in sources:
                scraper_tasks["linkedin"] = (scrape_linkedin, q.get("linkedin_query", f"{topic} linkedin"))
            if "facebook" in sources:
                scraper_tasks["facebook"] = (scrape_facebook, q.get("facebook_query", f"{topic} facebook groups"))
            if "instagram" in sources:
                scraper_tasks["instagram"] = (scrape_instagram, q.get("instagram_query", f"{topic} instagram"))
            if "twitter" in sources:
                scraper_tasks["twitter"] = (scrape_twitter, q.get("twitter_query", f"{topic} expert tweets"))
            if "quora" in sources:
                scraper_tasks["quora"] = (scrape_quora, q.get("quora_query", f"{topic} questions answers"))
            if "blogs" in sources:
                scraper_tasks["blogs"] = (scrape_blog_articles, q.get("blog_query", f"{topic} tutorial blog"))
            if "reddit" in sources:
                scraper_tasks["reddit"] = (scrape_reddit_communities, q.get("reddit_query", topic))
            if "events" in sources:
                scraper_tasks["events"] = (scrape_eventbrite, q.get("events_query", f"{topic} workshop"))

            # Execute all scrapers in parallel
            print(f"[PARALLEL] Starting {len(scraper_tasks)} scrapers in parallel...")
            with ThreadPoolExecutor(max_workers=10) as executor:
                # Submit all scraper tasks
                future_to_source = {
                    executor.submit(func, query): source_name
                    for source_name, (func, query) in scraper_tasks.items()
                }

                # Collect results as they complete
                completed = 0
                for future in as_completed(future_to_source):
                    source_name = future_to_source[future]
                    completed += 1
                    try:
                        results[source_name] = future.result(timeout=120)
                        print(f"[PARALLEL] Completed {source_name} ({completed}/{len(scraper_tasks)})")
                    except Exception as e:
                        print(f"[PARALLEL] Error scraping {source_name}: {e}")
                        results[source_name] = []

                    # Update progress
                    progress = 30 + int((completed / len(scraper_tasks)) * 50)
                    self.update_state(
                        state="PROGRESS",
                        meta={"step": f"Scraped {completed}/{len(scraper_tasks)} sources...", "progress": progress}
                    )

        # Step 6: Rank content using LLM
        self.update_state(
            state="PROGRESS",
            meta={"step": "Ranking content using LLM...", "progress": 85}
        )
        ranked_results = rank_content(topic, results)

        # Step 6.5: Save individual URL files for each source
        self.update_state(
            state="PROGRESS",
            meta={"step": "Saving individual URL files...", "progress": 90}
        )
        print(f"[URL Save] Saving individual URL files for job {job_id}")
        total_urls_saved = 0
        for source, data in ranked_results.items():
            if source != "top_10_overall" and isinstance(data, list) and len(data) > 0:
                save_individual_scraper_results(source, data, job_id)
                total_urls_saved += len(data)
        print(f"[URL Save] Completed: {total_urls_saved} individual URL files saved")

        # Step 7: Generate deep insights using LLM
        self.update_state(
            state="PROGRESS",
            meta={"step": "Local LLM generating deep insights...", "progress": 95}
        )
        insights = generate_deep_insights(topic, ranked_results)

        # Calculate totals
        counts = {k: len(v) for k, v in ranked_results.items()}

        final_data = {
            "topic": topic,
            "insights": insights,
            "results": ranked_results,
            "total_results": sum(counts.values()),
            "counts": counts,
            "search_mode": "api" if use_api else "scraping",
            "sources_searched": sources
        }

        # Save to JSON file for inspection
        save_scraped_data_to_file(job_id, topic, final_data)

        # Save to database
        save_results(job_id, topic, final_data)

        return final_data

    except Exception as e:
        print(f"[Task Error] {e}")
        # Return minimal data on error
        error_data = {
            "topic": topic,
            "insights": {
                "summary": f"An error occurred while researching {topic}. Please try again.",
                "trends": ["Unable to fetch trends"],
                "action_plan": ["Try searching again"]
            },
            "results": {},
            "total_results": 0,
            "error": str(e)
        }
        # Save error data to file
        save_scraped_data_to_file(job_id, topic, error_data)
        save_results(job_id, topic, error_data)
        return error_data
