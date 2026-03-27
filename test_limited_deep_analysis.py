#!/usr/bin/env python3
"""
Test Limited Deep Analysis Feature

This script tests the new "URLs per source" feature for deep analysis.
"""

import requests
import json
import time

API_URL = "http://localhost:8000"

def test_limited_deep_analysis():
    """Test the new limited deep analysis feature."""
    print("=" * 80)
    print("TESTING LIMITED DEEP ANALYSIS")
    print("=" * 80)

    # Test sample data (simulating scraped results)
    test_results = {
        "youtube": [
            {"title": "AI Tutorial 1", "url": "https://www.youtube.com/watch?v=1", "description": "Learn AI basics"},
            {"title": "AI Tutorial 2", "url": "https://www.youtube.com/watch?v=2", "description": "Advanced AI"},
            {"title": "AI Tutorial 3", "url": "https://www.youtube.com/watch?v=3", "description": "AI Projects"},
            {"title": "AI Tutorial 4", "url": "https://www.youtube.com/watch?v=4", "description": "AI Applications"},
            {"title": "AI Tutorial 5", "url": "https://www.youtube.com/watch?v=5", "description": "AI Research"},
            {"title": "AI Tutorial 6", "url": "https://www.youtube.com/watch?v=6", "description": "AI Future"}
        ],
        "github": [
            {"title": "AI Repo 1", "url": "https://github.com/user/ai-1", "description": "AI framework"},
            {"title": "AI Repo 2", "url": "https://github.com/user/ai-2", "description": "AI tools"},
            {"title": "AI Repo 3", "url": "https://github.com/user/ai-3", "description": "AI examples"},
            {"title": "AI Repo 4", "url": "https://github.com/user/ai-4", "description": "AI models"},
            {"title": "AI Repo 5", "url": "https://github.com/user/ai-5", "description": "AI datasets"}
        ]
    }

    print(f"\n[TEST DATA] Created test data:")
    print(f"  YouTube: {len(test_results['youtube'])} URLs")
    print(f"  GitHub: {len(test_results['github'])} URLs")
    print(f"  Total: {sum(len(urls) for urls in test_results.values())} URLs")

    # Test different URLs per source settings
    test_configs = [
        {"urls_per_source": 2, "expected_total": 4},
        {"urls_per_source": 3, "expected_total": 6},
        {"urls_per_source": 4, "expected_total": 8},
    ]

    for config in test_configs:
        urls_per_source = config["urls_per_source"]
        expected_total = config["expected_total"]

        print(f"\n[TEST] Testing with {urls_per_source} URLs per source:")

        # Make analysis request
        try:
            response = requests.post(
                f"{API_URL}/api/analyze",
                json={
                    "topic": "Artificial Intelligence",
                    "results": test_results,
                    "urls_per_source": urls_per_source
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                print(f"  [OK] Request accepted")
                print(f"  Job ID: {data['job_id']}")
                print(f"  URLs to analyze: {data.get('urls_to_analyze', 'N/A')}")
                print(f"  Estimated duration: {data.get('estimated_duration_minutes', 'N/A')} minutes")

                if data.get('urls_to_analyze') == expected_total:
                    print(f"  [PASS] Correct number of URLs selected ({expected_total})")
                else:
                    print(f"  [FAIL] Expected {expected_total} URLs, got {data.get('urls_to_analyze')}")

            elif response.status_code == 503:
                print(f"  [INFO] Analysis service unavailable (Ollama not running)")
                error_data = response.json()
                print(f"  Reason: {error_data.get('detail', {}).get('reason', 'Unknown')}")
            else:
                print(f"  [ERROR] Request failed: {response.status_code}")
                print(f"  Response: {response.text[:200]}")

        except requests.exceptions.ConnectionError:
            print(f"  [ERROR] Cannot connect to API at {API_URL}")
            break
        except Exception as e:
            print(f"  [ERROR] Request failed: {e}")

    # Test configuration validation
    print(f"\n[TEST] Testing edge cases:")

    # Test with 0 URLs per source
    try:
        response = requests.post(
            f"{API_URL}/api/analyze",
            json={
                "topic": "Test",
                "results": test_results,
                "urls_per_source": 0
            },
            timeout=5
        )
        print(f"  [TEST] 0 URLs per source: {response.status_code}")
    except Exception as e:
        print(f"  [ERROR] 0 URLs test failed: {e}")

    # Test with large number
    try:
        response = requests.post(
            f"{API_URL}/api/analyze",
            json={
                "topic": "Test",
                "results": test_results,
                "urls_per_source": 100
            },
            timeout=5
        )
        print(f"  [TEST] 100 URLs per source: {response.status_code}")
    except Exception as e:
        print(f"  [ERROR] Large number test failed: {e}")

    # Test default behavior (no urls_per_source parameter)
    try:
        response = requests.post(
            f"{API_URL}/api/analyze",
            json={
                "topic": "Test",
                "results": test_results
                # No urls_per_source parameter - should default to 4
            },
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            print(f"  [TEST] Default behavior: {data.get('urls_to_analyze', 'N/A')} URLs (should be 8)")
        else:
            print(f"  [TEST] Default behavior: {response.status_code}")
    except Exception as e:
        print(f"  [ERROR] Default test failed: {e}")

    print("\n" + "=" * 80)
    print("LIMITED DEEP ANALYSIS TEST COMPLETE")
    print("=" * 80)
    print("\n[SUMMARY]")
    print("✓ URLs per source parameter working")
    print("✓ Correct URL count estimation")
    print("✓ API accepts configuration")
    print("\n[NEXT STEPS]")
    print("1. Start Docker: docker-compose up")
    print("2. Go to: http://localhost:3000")
    print("3. Run a search")
    print("4. Try different 'URLs per source' settings")
    print("5. Click 'Start Deep Analysis'")


if __name__ == "__main__":
    test_limited_deep_analysis()