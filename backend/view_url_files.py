#!/usr/bin/env python3
"""
View Individual URL Files

This script helps you browse and view the individual URL JSON files
that are saved for each scraped URL.

Usage:
    python view_url_files.py                    # List all job directories
    python view_url_files.py <job_id>           # View URLs for a specific job
    python view_url_files.py <job_id> youtube   # View YouTube URLs from a job
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime

SCRAPED_DATA_DIR = Path(__file__).parent / "scraped_data"


def list_job_directories():
    """List all job directories with their details."""
    print("=" * 80)
    print("AVAILABLE JOBS")
    print("=" * 80)

    job_dirs = [d for d in SCRAPED_DATA_DIR.iterdir() if d.is_dir() and d.name.startswith("job_")]

    if not job_dirs:
        print("No job directories found.")
        return []

    job_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    for idx, job_dir in enumerate(job_dirs, 1):
        job_id = job_dir.name.replace("job_", "")

        # Count URLs per source
        sources = {}
        for source_dir in job_dir.iterdir():
            if source_dir.is_dir():
                url_count = len(list(source_dir.glob("*.json")))
                sources[source_dir.name] = url_count

        total_urls = sum(sources.values())
        created_time = datetime.fromtimestamp(job_dir.stat().st_ctime)

        print(f"\n{idx}. Job ID: {job_id}")
        print(f"   Created: {created_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Total URLs: {total_urls}")
        print(f"   Sources: {', '.join([f'{k}({v})' for k, v in sources.items()])}")

    print("\n" + "=" * 80)
    return job_dirs


def view_job_urls(job_id: str, source_filter: str = None):
    """View URLs from a specific job."""
    # Find job directory
    job_dir = SCRAPED_DATA_DIR / f"job_{job_id}"

    if not job_dir.exists():
        # Try with full job ID
        matches = list(SCRAPED_DATA_DIR.glob(f"job_{job_id}*"))
        if matches:
            job_dir = matches[0]
        else:
            print(f"Error: Job directory not found for job_id: {job_id}")
            return

    print("=" * 80)
    print(f"JOB: {job_dir.name.replace('job_', '')}")
    print("=" * 80)

    # Get all sources or filter by specific source
    if source_filter:
        source_dirs = [d for d in job_dir.iterdir() if d.is_dir() and d.name == source_filter]
        if not source_dirs:
            print(f"Error: Source '{source_filter}' not found in this job")
            print(f"Available sources: {[d.name for d in job_dir.iterdir() if d.is_dir()]}")
            return
    else:
        source_dirs = [d for d in job_dir.iterdir() if d.is_dir()]

    # Display URLs from each source
    for source_dir in sorted(source_dirs):
        url_files = sorted(source_dir.glob("*.json"))

        print(f"\n{source_dir.name.upper()} ({len(url_files)} URLs)")
        print("-" * 80)

        for url_file in url_files:
            try:
                with open(url_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                metadata = data.get('metadata', {})
                url_data = data.get('data', {})

                # Display basic info
                print(f"\n  File: {url_file.name}")
                print(f"  Title: {url_data.get('title', 'N/A')[:70]}")
                print(f"  URL: {url_data.get('url', 'N/A')[:80]}")

                # If analyzed content exists, show analysis summary
                if 'analyzed_content' in url_data:
                    analysis = url_data['analyzed_content']
                    print(f"  [ANALYZED] Relevance: {analysis.get('relevance_score', 'N/A')}/10")
                    print(f"  [ANALYZED] Quality: {analysis.get('content_quality', 'N/A')}")
                    print(f"  [ANALYZED] Summary: {analysis.get('summary', 'N/A')[:100]}...")

                # If extracted content exists
                if 'extracted_content' in url_data:
                    extracted = url_data['extracted_content']
                    print(f"  [EXTRACTED] Status: {extracted.get('extraction_status', 'N/A')}")
                    print(f"  [EXTRACTED] Words: {extracted.get('word_count', 0)}")

            except Exception as e:
                print(f"  Error reading {url_file.name}: {e}")

    print("\n" + "=" * 80)


def view_single_url_file(filepath: str):
    """View a single URL file in detail."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print("=" * 80)
        print("URL FILE DETAILS")
        print("=" * 80)

        # Metadata
        if 'metadata' in data:
            print("\nMETADATA:")
            for key, value in data['metadata'].items():
                print(f"  {key}: {value}")

        # URL Data
        url_data = data.get('data', {})
        print("\nURL DATA:")
        print(f"  Title: {url_data.get('title', 'N/A')}")
        print(f"  URL: {url_data.get('url', 'N/A')}")
        print(f"  Description: {url_data.get('description', 'N/A')[:200]}")

        # Analyzed content
        if 'analyzed_content' in url_data:
            print("\nANALYZED CONTENT:")
            analysis = url_data['analyzed_content']
            print(f"  Summary: {analysis.get('summary', 'N/A')}")
            print(f"  Relevance Score: {analysis.get('relevance_score', 'N/A')}/10")
            print(f"  Content Quality: {analysis.get('content_quality', 'N/A')}")
            print(f"  Content Type: {analysis.get('content_type', 'N/A')}")
            print(f"  Target Audience: {analysis.get('target_audience', 'N/A')}")
            print(f"  Difficulty Level: {analysis.get('difficulty_level', 'N/A')}")

            if analysis.get('key_topics'):
                print(f"  Key Topics: {', '.join(analysis['key_topics'])}")

            if analysis.get('key_points'):
                print("  Key Points:")
                for point in analysis['key_points']:
                    print(f"    - {point}")

            if analysis.get('actionable_insights'):
                print("  Actionable Insights:")
                for insight in analysis['actionable_insights']:
                    print(f"    - {insight}")

        # Extracted content
        if 'extracted_content' in url_data:
            print("\nEXTRACTED CONTENT:")
            extracted = url_data['extracted_content']
            print(f"  Extraction Status: {extracted.get('extraction_status', 'N/A')}")
            print(f"  Extraction Method: {extracted.get('extraction_method', 'N/A')}")
            print(f"  Word Count: {extracted.get('word_count', 0)}")
            print(f"  Preview: {extracted.get('content_preview', 'N/A')[:300]}...")

        print("\n" + "=" * 80)

    except Exception as e:
        print(f"Error reading file: {e}")
        import traceback
        traceback.print_exc()


def main():
    if not SCRAPED_DATA_DIR.exists():
        print(f"Error: Scraped data directory not found: {SCRAPED_DATA_DIR}")
        return

    if len(sys.argv) == 1:
        # List all jobs
        list_job_directories()
        print("\nUsage:")
        print("  python view_url_files.py <job_id>           # View all URLs for a job")
        print("  python view_url_files.py <job_id> youtube   # View YouTube URLs only")
        print("  python view_url_files.py --file <path>      # View a specific file")

    elif len(sys.argv) == 2:
        if sys.argv[1] == '--help':
            print("Usage:")
            print("  python view_url_files.py                    # List all jobs")
            print("  python view_url_files.py <job_id>           # View all URLs for a job")
            print("  python view_url_files.py <job_id> youtube   # View YouTube URLs only")
            print("  python view_url_files.py --file <path>      # View a specific file")
        else:
            # View specific job
            view_job_urls(sys.argv[1])

    elif len(sys.argv) == 3:
        if sys.argv[1] == '--file':
            # View specific file
            view_single_url_file(sys.argv[2])
        else:
            # View specific job with source filter
            view_job_urls(sys.argv[1], sys.argv[2])

    else:
        print("Invalid arguments. Use --help for usage information.")


if __name__ == "__main__":
    main()
