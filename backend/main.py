from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uuid
import threading
from datetime import datetime

# Try to import Celery components (optional)
try:
    from celery.result import AsyncResult
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    AsyncResult = None

from models import SearchRequest, SearchResponse, JobStatus, AnalyzeRequest, AnalyzeResponse
from database import init_db, create_job, get_job, update_job_status

# Try to import tasks and celery_app (optional)
try:
    from tasks import celery_app, scrape_topic_task, AVAILABLE_SOURCES
    TASKS_AVAILABLE = True
except ImportError:
    TASKS_AVAILABLE = False
    celery_app = None
    scrape_topic_task = None
    # Define fallback available sources
    AVAILABLE_SOURCES = [
        "youtube", "github", "reddit", "twitter", "blogs",
        "linkedin", "facebook", "instagram", "quora", "events"
    ]

import google_api

# Initialize FastAPI app
app = FastAPI(
    title="TopicLens API",
    description="Aggregate resources about any topic from across the internet",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "TopicLens API"}


@app.get("/api/config")
async def get_config():
    """
    Get API configuration and capabilities.
    Returns available search modes, platforms, API availability, and analysis status.
    """
    # Check content analysis availability
    analysis_status = {
        "available": False,
        "status": "unknown",
        "error": None,
        "ollama_info": None
    }

    try:
        from llm import check_ollama_health
        health = check_ollama_health()

        if health["healthy"]:
            analysis_status = {
                "available": True,
                "status": "healthy",
                "ollama_info": {
                    "url": health["url"],
                    "model": health["model"],
                    "response_time": health["response_time"],
                    "models_available": health.get("models_available", [])
                }
            }
        else:
            analysis_status = {
                "available": False,
                "status": "unhealthy",
                "error": health["error"],
                "ollama_info": {
                    "url": health["url"],
                    "model": health["model"],
                    "models_available": health.get("models_available", [])
                }
            }

    except ImportError as e:
        analysis_status = {
            "available": False,
            "status": "not_installed",
            "error": f"Analysis modules not available: {e}"
        }
    except Exception as e:
        analysis_status = {
            "available": False,
            "status": "error",
            "error": str(e)
        }

    return {
        "google_api_available": google_api.is_api_available(),
        "search_modes": ["scraping", "api"],
        "default_mode": "scraping",
        "available_sources": AVAILABLE_SOURCES,
        "source_descriptions": {
            "youtube": "YouTube videos and tutorials",
            "github": "GitHub repositories and code projects",
            "reddit": "Reddit communities and discussions",
            "twitter": "Twitter/X posts and threads",
            "blogs": "Blog articles (Medium, Dev.to, etc.)",
            "linkedin": "LinkedIn profiles and posts",
            "facebook": "Facebook groups and pages",
            "instagram": "Instagram accounts and posts",
            "quora": "Quora questions and answers",
            "events": "Events, workshops, and webinars"
        },
        "content_analysis": analysis_status
    }


@app.get("/api/sources")
async def get_sources():
    """
    Get list of available platforms/sources to search.
    """
    return {
        "sources": [
            {
                "id": "youtube",
                "name": "YouTube",
                "description": "Videos and tutorials",
                "icon": "🎥"
            },
            {
                "id": "github",
                "name": "GitHub",
                "description": "Code repositories and projects",
                "icon": "💻"
            },
            {
                "id": "reddit",
                "name": "Reddit",
                "description": "Communities and discussions",
                "icon": "🗨️"
            },
            {
                "id": "twitter",
                "name": "Twitter/X",
                "description": "Posts, threads, and experts",
                "icon": "🐦"
            },
            {
                "id": "blogs",
                "name": "Blogs",
                "description": "Articles (Medium, Dev.to, etc.)",
                "icon": "📝"
            },
            {
                "id": "linkedin",
                "name": "LinkedIn",
                "description": "Professional profiles and posts",
                "icon": "💼"
            },
            {
                "id": "facebook",
                "name": "Facebook",
                "description": "Groups and pages",
                "icon": "👥"
            },
            {
                "id": "instagram",
                "name": "Instagram",
                "description": "Accounts and posts",
                "icon": "📸"
            },
            {
                "id": "quora",
                "name": "Quora",
                "description": "Questions and answers",
                "icon": "❓"
            },
            {
                "id": "events",
                "name": "Events",
                "description": "Workshops and webinars",
                "icon": "📅"
            }
        ]
    }


@app.post("/api/search", response_model=SearchResponse)
async def start_search(request: SearchRequest):
    """
    Start a new topic search.
    Returns a job_id to poll for results.

    Request body:
        topic: The search topic (required)
        search_mode: "scraping" or "api" (optional, default: "scraping")
        sources: List of platforms to search (optional, default: all platforms)
                 Available: youtube, github, reddit, twitter, blogs, linkedin,
                           facebook, instagram, quora, events
    """
    if not request.topic or len(request.topic.strip()) < 2:
        raise HTTPException(status_code=400, detail="Topic must be at least 2 characters")

    # Validate search_mode
    if request.search_mode not in ["scraping", "api"]:
        raise HTTPException(status_code=400, detail="search_mode must be 'scraping' or 'api'")

    # Validate sources if provided
    sources = request.sources
    if sources:
        # Filter out invalid sources
        valid_sources = [s.lower() for s in sources if s.lower() in AVAILABLE_SOURCES]
        if not valid_sources:
            raise HTTPException(
                status_code=400,
                detail=f"No valid sources provided. Available sources: {', '.join(AVAILABLE_SOURCES)}"
            )
        sources = valid_sources
    else:
        # If no sources specified, use all
        sources = AVAILABLE_SOURCES

    topic = request.topic.strip()
    search_mode = request.search_mode or "scraping"
    job_id = str(uuid.uuid4())

    # Create job in database
    create_job(job_id, topic)

    # Dispatch Celery task with search_mode and sources
    scrape_topic_task.apply_async(
        args=[topic, job_id, search_mode, sources],
        task_id=job_id
    )

    return SearchResponse(job_id=job_id, status="pending")


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """
    Get the status of a search job.
    Returns progress updates or final results.
    """
    # Check if Celery is available
    if CELERY_AVAILABLE and AsyncResult and celery_app:
        # Use Celery to check task status
        task_result = AsyncResult(job_id, app=celery_app)

        if task_result.state == "PENDING":
            # Check if job exists in database
            db_job = get_job(job_id)
            if db_job:
                return {
                    "id": job_id,
                    "status": db_job["status"],
                    "step": "Queued...",
                    "progress": 0
                }
            raise HTTPException(status_code=404, detail="Job not found")

        elif task_result.state == "PROGRESS":
            meta = task_result.info or {}
            return {
                "id": job_id,
                "status": "progress",
                "step": meta.get("step", "Processing..."),
                "progress": meta.get("progress", 0)
            }

        elif task_result.state == "SUCCESS":
            result = task_result.result
            return {
                "id": job_id,
                "status": "done",
                "topic": result.get("topic", ""),
                "insights": result.get("insights", {}),
                "results": result.get("results", {}),
                "total_results": result.get("total_results", 0),
                "counts": result.get("counts", {}),
                "content_analysis_enabled": result.get("content_analysis_enabled", False)
            }

        elif task_result.state == "FAILURE":
            return {
                "id": job_id,
                "status": "error",
                "error": str(task_result.info)
            }

        else:
            return {
                "id": job_id,
                "status": task_result.state.lower(),
                "step": "Processing..."
            }

    else:
        # Fallback: Check database job status directly
        db_job = get_job(job_id)
        if db_job:
            # Map database status to API status
            if db_job["status"] == "pending":
                return {
                    "id": job_id,
                    "status": "progress",
                    "step": "Starting...",
                    "progress": 0
                }
            elif db_job["status"] in ["completed", "done"]:
                results = db_job["results"] or {}
                return {
                    "id": job_id,
                    "status": "done",
                    "topic": results.get("topic", ""),
                    "insights": results.get("insights", {}),
                    "results": results.get("results", {}),
                    "total_results": results.get("total_results", 0),
                    "counts": results.get("counts", {}),
                    "content_analysis_enabled": results.get("content_analysis_enabled", False),
                    "analysis_error": results.get("analysis_error"),
                    "error_details": results.get("error_details")
                }
            elif db_job["status"] == "error":
                results = db_job["results"] or {}
                return {
                    "id": job_id,
                    "status": "error",
                    "error": results.get("error", "Unknown error"),
                    "error_details": results.get("error_details")
                }
            else:
                return {
                    "id": job_id,
                    "status": "progress",
                    "step": f"Status: {db_job['status']}",
                    "progress": 50
                }
        else:
            raise HTTPException(status_code=404, detail="Job not found")


@app.get("/api/history")
async def get_history(limit: int = 10):
    """
    Get recent search history.
    """
    from database import SessionLocal, SearchJob

    db = SessionLocal()
    try:
        jobs = db.query(SearchJob).order_by(
            SearchJob.created_at.desc()
        ).limit(limit).all()

        return [
            {
                "id": job.id,
                "topic": job.topic,
                "status": job.status,
                "created_at": job.created_at.isoformat() if job.created_at else None
            }
            for job in jobs
        ]
    finally:
        db.close()


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def start_analysis(request: AnalyzeRequest):
    """
    Start deep content analysis on existing search results.
    Returns a job_id to poll for analysis progress.

    Request body:
        topic: The original search topic (required)
        results: The search results to analyze (required)
    """
    if not request.topic or len(request.topic.strip()) < 2:
        raise HTTPException(status_code=400, detail="Topic must be at least 2 characters")

    if not request.results:
        raise HTTPException(status_code=400, detail="Results are required for analysis")

    # Pre-flight check: Verify Ollama is available before starting analysis
    try:
        from llm import check_ollama_health
        health = check_ollama_health()

        if not health["healthy"]:
            # Ollama not available - return detailed error
            error_details = {
                "error": "Content analysis not available",
                "reason": health["error"],
                "ollama_config": {
                    "url": health["url"],
                    "model": health["model"],
                    "models_available": health.get("models_available", [])
                },
                "troubleshooting": []
            }

            # Add specific troubleshooting tips based on error type
            if "Connection refused" in health["error"]:
                error_details["troubleshooting"].extend([
                    "Ollama server is not running",
                    "Start Ollama with: 'ollama serve'",
                    "Check if Ollama is installed: https://ollama.ai/"
                ])
            elif "not found" in health["error"] or "not available" in health["error"]:
                error_details["troubleshooting"].extend([
                    f"Model '{health['model']}' is not installed",
                    f"Install model with: 'ollama pull {health['model']}'",
                    f"Or use an available model: {', '.join(health.get('models_available', []))}"
                ])
            elif "timeout" in health["error"].lower():
                error_details["troubleshooting"].extend([
                    "Ollama server is slow to respond",
                    "Check system resources and network connectivity",
                    "Try restarting Ollama service"
                ])

            raise HTTPException(
                status_code=503,  # Service Unavailable
                detail=error_details
            )

        print(f"[API] Ollama health check passed: {health['url']} with {health['model']} ({health['response_time']}s)")

    except ImportError:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Content analysis system not available",
                "reason": "Analysis modules not properly installed",
                "troubleshooting": [
                    "Check if content_analysis_agent.py exists",
                    "Verify all dependencies are installed"
                ]
            }
        )
    except Exception as e:
        print(f"[API] Unexpected error during health check: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Content analysis system error",
                "reason": str(e),
                "troubleshooting": [
                    "Check server logs for detailed error information",
                    "Verify Ollama installation and configuration"
                ]
            }
        )

    topic = request.topic.strip()
    job_id = str(uuid.uuid4())
    urls_per_source = request.urls_per_source or 4

    # Count total URLs available
    total_urls = sum(len(items) for items in request.results.values() if isinstance(items, list))
    num_sources = sum(1 for k, v in request.results.items() if isinstance(v, list) and k != "top_10_overall")
    estimated_analysis_urls = num_sources * urls_per_source

    print(f"[API] Starting analysis for '{topic}' with {total_urls} URLs (job: {job_id})")
    print(f"[API] Will analyze up to {urls_per_source} URLs per source (~{estimated_analysis_urls} URLs total)")

    # Create job in database
    create_job(job_id, f"Analysis: {topic}")

    # Try to import and run analysis task with fallback
    try:
        # Try Celery first
        try:
            from tasks import analyze_content_task
            # Check if Celery is actually available
            import celery

            # Dispatch analysis task with validated data
            analyze_content_task.apply_async(
                args=[job_id, request.results, topic],
                kwargs={'urls_per_source': urls_per_source},
                task_id=job_id
            )
            print(f"[API] Analysis dispatched to Celery queue (job: {job_id})")

        except (ImportError, Exception) as celery_error:
            print(f"[API] Celery not available ({celery_error}), running analysis synchronously...")

            # Fallback: Run analysis synchronously in background thread
            import threading
            from tasks import analyze_urls_content
            from database import update_job_status

            def run_analysis_sync():
                try:
                    # Update job status to indicate start
                    update_job_status(job_id, "progress", "Starting analysis...", 5, None)

                    # Run the analysis function directly
                    analysis_result = analyze_urls_content(
                        results=request.results,
                        topic=topic,
                        job_id=job_id,
                        max_urls=50,  # Legacy parameter
                        urls_per_source=urls_per_source
                    )

                    # Process results like the Celery task would
                    if isinstance(analysis_result, dict) and "error" in analysis_result:
                        # Analysis failed
                        error_details = {
                            "step": f"Analysis failed: {analysis_result['error']}",
                            "progress": 0,
                            "error": analysis_result['error']
                        }

                        if "health_check" in analysis_result:
                            health = analysis_result["health_check"]
                            error_details["health_info"] = {
                                "ollama_url": health.get("url"),
                                "ollama_model": health.get("model"),
                                "models_available": health.get("models_available", []),
                                "error": health.get("error")
                            }

                        final_data = {
                            "topic": topic,
                            "results": analysis_result.get("original_results", request.results),
                            "total_results": sum(len(items) for items in request.results.values() if isinstance(items, list)),
                            "content_analysis_enabled": False,
                            "analysis_error": analysis_result["error"],
                            "error_details": error_details
                        }

                        update_job_status(job_id, "error", final_data.get("analysis_error", "Analysis failed"), 0, final_data)

                    else:
                        # Analysis succeeded
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

                        # Save analyzed data to file
                        from tasks import save_scraped_data_to_file
                        save_scraped_data_to_file(job_id, f"{topic}_ANALYZED", final_data)

                        update_job_status(job_id, "done", "Analysis complete!", 100, final_data)

                except Exception as e:
                    error_msg = str(e)
                    print(f"[API] Sync analysis error: {error_msg}")

                    error_data = {
                        "topic": topic,
                        "results": request.results,
                        "total_results": sum(len(items) for items in request.results.values() if isinstance(items, list)),
                        "error": error_msg,
                        "content_analysis_enabled": False,
                        "critical_error": True
                    }

                    update_job_status(job_id, "error", error_msg, 0, error_data)

            # Start analysis in background thread
            analysis_thread = threading.Thread(target=run_analysis_sync)
            analysis_thread.daemon = True
            analysis_thread.start()

            print(f"[API] Analysis started in background thread (job: {job_id})")

        return AnalyzeResponse(
            job_id=job_id,
            status="pending",
            urls_to_analyze=estimated_analysis_urls,
            estimated_duration_minutes=max(1, estimated_analysis_urls // 8)  # ~8 URLs per minute
        )

    except ImportError:
        raise HTTPException(status_code=500, detail="Content analysis not available")
    except Exception as e:
        print(f"[API] Error starting analysis task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")
