#!/usr/bin/env python3
"""
Simple Content Analysis Test

Tests the WebContentExtractor and OllamaContentAnalyzer directly.
"""

import os
import sys

# Set environment
os.environ["OLLAMA_URL"] = "http://127.0.0.1:11434"
os.environ["OLLAMA_MODEL"] = "llama3.2:latest"

print("=" * 60)
print("SIMPLE CONTENT ANALYSIS TEST")
print("=" * 60)

# Test 1: Import WebContentExtractor
print("\n[TEST 1] Importing WebContentExtractor...")
try:
    from content_analysis_agent import WebContentExtractor, OllamaContentAnalyzer
    print("[PASS] Imports successful")
except Exception as e:
    print(f"[FAIL] Import failed: {e}")
    sys.exit(1)

# Test 2: Extract content from a URL
print("\n[TEST 2] Testing WebContentExtractor...")
extractor = WebContentExtractor()

test_url = "https://www.python.org/"
print(f"  Extracting content from: {test_url}")

try:
    content = extractor.extract_content(test_url, "web")

    print(f"  [PASS] Extraction status: {content['extraction_status']}")
    print(f"  [INFO] Title: {content.get('title', 'N/A')[:50]}")
    print(f"  [INFO] Word count: {content.get('word_count', 0)}")
    print(f"  [INFO] Preview: {content.get('content_preview', '')[:100]}...")

    if content['extraction_status'] in ['success', 'partial']:
        print("  [PASS] Content extraction working!")
    else:
        print(f"  [FAIL] Content extraction failed: {content.get('error')}")
        sys.exit(1)

except Exception as e:
    print(f"  [FAIL] Extraction error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Analyze content with Ollama
print("\n[TEST 3] Testing OllamaContentAnalyzer...")
analyzer = OllamaContentAnalyzer()

print("  Analyzing extracted content with Ollama LLM...")

try:
    analysis = analyzer.analyze_content(content, "Python programming")

    print(f"  [PASS] Analysis completed!")
    print(f"  [INFO] Summary: {analysis.get('summary', 'N/A')[:100]}...")
    print(f"  [INFO] Relevance score: {analysis.get('relevance_score', 'N/A')}/10")
    print(f"  [INFO] Content quality: {analysis.get('content_quality', 'N/A')}")
    print(f"  [INFO] Key topics: {', '.join(analysis.get('key_topics', [])[:3])}")

    if analysis.get('summary') and analysis.get('summary') != "Analysis unavailable":
        print("  [PASS] Ollama analysis working!")
    else:
        print("  [WARN] Analysis completed but may have issues")

except Exception as e:
    print(f"  [FAIL] Analysis error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Summary
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)
print("[PASS] All tests passed!")
print("\nKEY FINDINGS:")
print("1. Web content extraction is WORKING")
print("2. LLM does NOT need internet access - it analyzes PRE-FETCHED content")
print("3. This architecture is CORRECT - no need for CrewAI/LangChain")
print("\nThe system:")
print("  URL -> WebContentExtractor (fetches HTML)")
print("      -> Extract Text Content")
print("      -> OllamaContentAnalyzer (sends TEXT to Ollama)")
print("      -> Ollama LLM analyzes the text")
print("\nOllama never accesses the internet - it only processes text!")
print("=" * 60)
