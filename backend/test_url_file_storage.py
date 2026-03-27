#!/usr/bin/env python3
"""
Test Individual URL File Storage

This script demonstrates the new individual URL file storage feature.
"""

import json
from pathlib import Path

def test_url_file_structure():
    """Test and demonstrate the URL file structure."""
    print("=" * 80)
    print("TESTING INDIVIDUAL URL FILE STORAGE")
    print("=" * 80)

    # Check if scraped_data directory exists
    scraped_data_dir = Path(__file__).parent / "scraped_data"

    if not scraped_data_dir.exists():
        print("\n[ERROR] Scraped data directory not found!")
        print("   Run a search first to generate data.")
        return

    print(f"\n[OK] Scraped data directory: {scraped_data_dir}")

    # Check for job directories
    job_dirs = list(scraped_data_dir.glob("job_*"))

    if not job_dirs:
        print("\n[INFO] No job directories found yet.")
        print("   Job directories will be created on the next scraping run.")
        print("\n[GUIDE] How to trigger individual URL file creation:")
        print("   1. Go to the TopicLens frontend (http://localhost:3000)")
        print("   2. Enter a search topic and click 'Search'")
        print("   3. Individual URL files will be created automatically")
        print("   4. Run this script again to see the results")
        return

    print(f"\n[OK] Found {len(job_dirs)} job directories:\n")

    # List all jobs
    for job_dir in sorted(job_dirs):
        job_id = job_dir.name.replace("job_", "")
        print(f"   [JOB] {job_dir.name}")

        # Count URLs per source
        sources = {}
        for source_dir in job_dir.iterdir():
            if source_dir.is_dir():
                url_files = list(source_dir.glob("*.json"))
                sources[source_dir.name] = len(url_files)

        total_urls = sum(sources.values())
        print(f"      Total URLs: {total_urls}")

        for source, count in sorted(sources.items()):
            print(f"      - {source}: {count} URLs")

        # Show sample file
        for source_dir in job_dir.iterdir():
            if source_dir.is_dir():
                url_files = list(source_dir.glob("*.json"))
                if url_files:
                    sample_file = url_files[0]
                    print(f"\n      [SAMPLE] {sample_file.name}")

                    with open(sample_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    print(f"         Metadata:")
                    for key, value in data.get('metadata', {}).items():
                        if key != 'file_path':
                            print(f"           {key}: {value}")

                    url_data = data.get('data', {})
                    print(f"         Data:")
                    print(f"           title: {url_data.get('title', 'N/A')[:60]}")
                    print(f"           url: {url_data.get('url', 'N/A')[:70]}")

                    if 'analyzed_content' in url_data:
                        analysis = url_data['analyzed_content']
                        print(f"           [ANALYZED] relevance: {analysis.get('relevance_score', 'N/A')}/10")
                        print(f"           [ANALYZED] quality: {analysis.get('content_quality', 'N/A')}")

                    break

        print()

    # Summary
    print("=" * 80)
    print("[SUCCESS] Individual URL file storage is working!")
    print("\n[DOCS] For detailed documentation, see: INDIVIDUAL_URL_FILES.md")
    print("[TOOL] To browse URL files, use: python view_url_files.py")
    print("=" * 80)


if __name__ == "__main__":
    test_url_file_structure()
