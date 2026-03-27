#!/usr/bin/env python3
"""
Test Deep Analysis Fix

This script tests the fixed deep analysis functionality without requiring
a full backend server setup.
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Set working Ollama configuration
os.environ["OLLAMA_URL"] = "http://127.0.0.1:11434"
os.environ["OLLAMA_MODEL"] = "llama3.2:latest"

# Add backend to path
sys.path.append('backend')
sys.path.insert(0, '.')

def test_deep_analysis_integration():
    """Test the deep analysis integration that was failing before."""

    print("="*60)
    print("TESTING DEEP ANALYSIS FIX")
    print("="*60)

    # Test 1: Check Ollama health
    try:
        from llm import check_ollama_health
        health = check_ollama_health()

        if health["healthy"]:
            print("[PASS] Ollama Health Check: PASSED")
            print(f"   URL: {health['url']}")
            print(f"   Model: {health['model']}")
            print(f"   Response Time: {health['response_time']}s")
        else:
            print("[FAIL] Ollama Health Check: FAILED")
            print(f"   Error: {health['error']}")
            return False

    except Exception as e:
        print(f"[FAIL] Ollama Health Check: ERROR - {e}")
        return False

    # Test 2: Import analyze_urls_content function
    try:
        from tasks import analyze_urls_content
        print("[PASS] Import analyze_urls_content: PASSED")
    except Exception as e:
        print(f"[FAIL] Import analyze_urls_content: FAILED - {e}")
        return False

    # Test 3: Prepare test data similar to what the API would send
    try:
        # Find existing scraped data
        scraped_dir = Path("backend/scraped_data")
        files = [f for f in scraped_dir.glob("*.json") if "ANALYZED" not in f.name]

        if not files:
            print("[FAIL] No test data available")
            return False

        test_file = max(files, key=lambda x: x.stat().st_mtime)
        print(f"[PASS] Found test data: {test_file.name}")

        # Load test data
        with open(test_file) as f:
            test_data = json.load(f)

        test_results = test_data["results"]
        test_topic = test_data["topic"]

        print(f"[PASS] Test data loaded: topic='{test_topic}', sources={len(test_results)}")

    except Exception as e:
        print(f"[FAIL] Test data preparation: FAILED - {e}")
        return False

    # Test 4: Run analyze_urls_content (the fixed function)
    try:
        print("[RUN] Running analyze_urls_content with 2 URLs...")

        result = analyze_urls_content(
            results=test_results,
            topic=test_topic,
            job_id="test_integration",
            max_urls=2
        )

        # Check if result indicates an error
        if isinstance(result, dict) and "error" in result:
            print("[FAIL] Analysis Function: FAILED")
            print(f"   Error: {result['error']}")

            if "health_check" in result:
                health = result["health_check"]
                print("   Health Check Details:")
                print(f"     URL: {health.get('url')}")
                print(f"     Model: {health.get('model')}")
                print(f"     Error: {health.get('error')}")

            if result.get("import_error"):
                print("   Import Error: ContentAnalysisAgent could not be imported")

            return False
        else:
            print("[PASS] Analysis Function: SUCCESS")

            # Verify results have analysis content
            has_analysis = False
            for source, items in result.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and "analyzed_content" in item:
                            has_analysis = True
                            analysis = item["analyzed_content"]
                            print(f"   Found analysis for: {item.get('title', 'Unknown')[:50]}...")
                            print(f"     Relevance: {analysis.get('relevance_score', 'N/A')}")
                            print(f"     Quality: {analysis.get('content_quality', 'N/A')}")
                            break
                if has_analysis:
                    break

            if has_analysis:
                print("[PASS] Analysis Content: FOUND - URLs are being properly analyzed!")
            else:
                print("[FAIL] Analysis Content: MISSING - No analyzed_content found in results")
                return False

    except Exception as e:
        print(f"[FAIL] Analysis Function: ERROR - {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False

    print("\n[SUCCESS] ALL TESTS PASSED!")
    print("[PASS] The deep analysis integration is working correctly")
    print("[PASS] Ollama connection established")
    print("[PASS] Content analysis agent functioning")
    print("[PASS] URLs being visited and analyzed with AI insights")

    return True

def main():
    """Run the integration test."""
    success = test_deep_analysis_integration()

    if success:
        print("\n[SUCCESS] DEEP ANALYSIS FIX: SUCCESSFUL!")
        print("The issue you encountered in the frontend should now be resolved.")
        print("The system will now properly visit URLs and generate AI insights.")
    else:
        print("\n[FAIL] DEEP ANALYSIS FIX: NEEDS MORE WORK")
        print("There are still issues that need to be addressed.")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)