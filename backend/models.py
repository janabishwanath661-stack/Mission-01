from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class SearchRequest(BaseModel):
    topic: str
    search_mode: Optional[str] = "scraping"  # "scraping" or "api"
    sources: Optional[List[str]] = None  # List of platforms to search, e.g., ["youtube", "reddit", "github"]
                                         # If None or empty, searches all platforms


class SearchResponse(BaseModel):
    job_id: str
    status: str


class AnalyzeRequest(BaseModel):
    topic: str
    results: Dict[str, Any]  # The results to analyze
    urls_per_source: Optional[int] = 4  # Max URLs to analyze per source (default: 4)


class AnalyzeResponse(BaseModel):
    job_id: str
    status: str
    urls_to_analyze: Optional[int] = None
    estimated_duration_minutes: Optional[int] = None


class InsightsModel(BaseModel):
    summary: str
    trends: List[str]
    action_plan: List[str]


class ResultItem(BaseModel):
    title: str
    url: str
    description: Optional[str] = None
    thumbnail: Optional[str] = None
    source: Optional[str] = None
    # Engagement metrics (optional)
    score: Optional[int] = None
    subscribers: Optional[int] = None
    stars: Optional[int] = None
    channel: Optional[str] = None
    subreddit: Optional[str] = None


class JobStatus(BaseModel):
    id: str
    topic: str
    status: str
    step: Optional[str] = None
    progress: Optional[int] = None
    results: Optional[Dict[str, Any]] = None
    insights: Optional[InsightsModel] = None
    total_results: Optional[int] = None
