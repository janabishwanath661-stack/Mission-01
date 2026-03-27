# ✅ FEATURE IMPLEMENTED: Individual URL File Storage

## Summary

**Every scraped URL now gets saved to its own individual JSON file!**

This gives you complete granular control over your scraped data. Each URL has its own file with all metadata, scraped content, and analysis results.

---

## What Was Changed

### 1. **New Function: `save_individual_url_data()`**
   - Location: `backend/tasks.py`
   - Saves each URL to its own JSON file
   - Creates organized directory structure: `scraped_data/job_<id>/<source>/`
   - Generates safe filenames from URL titles
   - Adds metadata to each file

### 2. **Modified Function: `save_individual_scraper_results()`**
   - Location: `backend/tasks.py`
   - Now saves both aggregated source file AND individual URL files
   - Logs how many URL files were saved

### 3. **Updated Task: `scrape_topic_task()`**
   - Location: `backend/tasks.py`
   - Calls `save_individual_scraper_results()` after ranking content
   - Progress indicator shows "Saving individual URL files..."

### 4. **Updated Task: `analyze_content_task()`**
   - Location: `backend/tasks.py`
   - Saves individual URL files with analysis results included
   - Each analyzed URL gets its own file

### 5. **New Utility: `view_url_files.py`**
   - Location: `backend/view_url_files.py`
   - Command-line tool to browse and view individual URL files
   - Lists jobs, sources, and individual URLs
   - Shows analysis summaries

### 6. **New Documentation: `INDIVIDUAL_URL_FILES.md`**
   - Location: `backend/INDIVIDUAL_URL_FILES.md`
   - Complete documentation of the new file structure
   - Usage examples and code snippets
   - Programmatic access guide

### 7. **Test Script: `test_url_file_storage.py`**
   - Location: `backend/test_url_file_storage.py`
   - Validates the new feature
   - Shows sample files and structure

---

## File Structure

```
backend/scraped_data/
│
├── Deep_Learning_20260327_123456_226c184a.json    # Aggregated (all sources)
├── youtube_20260327_123456_226c184a.json          # Source-specific
├── github_20260327_123456_226c184a.json
│
└── job_226c184a/                                   # NEW: Job directory
    ├── youtube/                                    # NEW: Source subdirectory
    │   ├── 000_Roadmap_to_Become_a_Generative_AI.json  # NEW: Individual URL
    │   ├── 001_Deep_Learning_Full_Course_2024.json
    │   └── 002_Neural_Networks_Explained.json
    │
    ├── github/
    │   ├── 000_tensorflow_tensorflow.json
    │   ├── 001_pytorch_pytorch.json
    │   └── 002_keras-team_keras.json
    │
    ├── reddit/
    ├── blogs/
    ├── twitter/
    └── linkedin/
```

---

## Individual URL File Format

Each file contains:

```json
{
  "metadata": {
    "job_id": "226c184a-b433-402a-ab9c-3334c3ba2597",
    "source": "youtube",
    "url_index": 0,
    "saved_at": "2026-03-27T12:34:56.789",
    "file_path": "/app/scraped_data/job_226c184a/youtube/000_Roadmap.json"
  },
  "data": {
    "title": "Roadmap to Become a Generative AI Expert",
    "url": "https://www.youtube.com/watch?v=example",
    "description": "Complete guide...",

    // Deep analysis results (if performed):
    "extracted_content": {
      "extraction_status": "success",
      "word_count": 450,
      "content_preview": "..."
    },

    "analyzed_content": {
      "summary": "Comprehensive roadmap...",
      "relevance_score": 9,
      "content_quality": "high",
      "key_topics": ["AI", "ML", "Deep Learning"],
      "key_points": [...],
      "actionable_insights": [...]
    }
  }
}
```

---

## How to Use

### Test the Feature

Run a new search from the frontend:

```bash
# 1. Make sure Docker is running
docker-compose ps

# 2. Go to http://localhost:3000
# 3. Enter a topic and click "Search"
# 4. Wait for scraping to complete
# 5. Check the new files:

cd backend
python test_url_file_storage.py
```

### Browse URL Files

```bash
# List all jobs
python view_url_files.py

# View all URLs from a specific job
python view_url_files.py 226c184a

# View URLs from a specific source
python view_url_files.py 226c184a youtube

# View a specific URL file
python view_url_files.py --file scraped_data/job_226c184a/youtube/000_Roadmap.json
```

### Programmatic Access

```python
import json
from pathlib import Path

# Load a specific URL
with open('scraped_data/job_226c184a/youtube/000_Roadmap.json', 'r') as f:
    url_data = json.load(f)

print(url_data['data']['title'])
print(url_data['data']['analyzed_content']['summary'])

# Find all high-quality URLs (score >= 8)
for source_dir in Path("scraped_data/job_226c184a").iterdir():
    for url_file in source_dir.glob("*.json"):
        with open(url_file, 'r') as f:
            data = json.load(f)

        analysis = data['data'].get('analyzed_content', {})
        if analysis.get('relevance_score', 0) >= 8:
            print(f"{analysis['relevance_score']}/10 - {data['data']['title']}")
```

---

## Benefits

✅ **Granular Access** - Access any specific URL without loading entire datasets
✅ **Easy Analysis** - Analyze individual URLs programmatically
✅ **Better Debugging** - Debug issues with specific URLs easily
✅ **Data Management** - Delete, update, or re-process individual URLs
✅ **Scalability** - Handle large datasets efficiently
✅ **Backup Friendly** - Easy to backup/restore specific URLs or sources

---

## What Happens When You Run a Search

1. **User enters topic** and clicks "Search"
2. **Scraping happens** across all selected platforms
3. **LLM ranks results** by relevance
4. **Individual URL files created**:
   - Creates `job_<id>` directory
   - Creates subdirectories for each source
   - Saves each URL to its own file
   - Logs: "Saved X/Y individual URL files for <source>"
5. **Aggregated files also created** (for backward compatibility)
6. **Database updated** with job status

### When Deep Analysis is Run

1. **User clicks "Start Deep Analysis"**
2. **Content extraction** happens for each URL
3. **Ollama analyzes** the extracted content
4. **Individual URL files updated** with:
   - `extracted_content` section
   - `analyzed_content` section
5. **New analyzed files created**:
   - In `job_<id>_ANALYZED` directory
   - Each URL has full analysis results

---

## Storage Impact

- **Without analysis**: ~2-5KB per URL
- **With analysis**: ~5-15KB per URL
- **100 URLs**: ~500KB - 1.5MB total
- **1000 URLs**: ~5MB - 15MB total

Files are stored on the host machine via Docker volume mounts, so they persist across container restarts.

---

## Next Run

The next time you run a search:

1. A new `job_<id>` directory will be created
2. Individual URL files will be saved automatically
3. Run `python view_url_files.py` to browse them
4. Each URL will have its own searchable, analyzable JSON file

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `python test_url_file_storage.py` | Test the feature |
| `python view_url_files.py` | List all jobs |
| `python view_url_files.py <job_id>` | View job URLs |
| `python view_url_files.py <job_id> youtube` | View source URLs |
| `cat INDIVIDUAL_URL_FILES.md` | Full documentation |

---

## Troubleshooting

**Q: I don't see job directories**
A: Run a new search from the frontend. Old searches won't have individual files.

**Q: Can I delete old job directories?**
A: Yes! `rm -rf backend/scraped_data/job_<old_id>`

**Q: Do I still get aggregated files?**
A: Yes! Both individual AND aggregated files are created.

**Q: Can I re-analyze individual URLs?**
A: Not yet, but this could be added as a future feature.

---

## Files Added/Modified

### Modified:
- `backend/tasks.py` - Core file storage logic

### Added:
- `backend/view_url_files.py` - Browse URLs tool
- `backend/INDIVIDUAL_URL_FILES.md` - Full documentation
- `backend/test_url_file_storage.py` - Test script
- `backend/IMPLEMENTATION_SUMMARY.md` - This file

---

## ✅ Status: READY TO USE

The feature is fully implemented and ready to use. Just run a new search from the frontend!

**Next search = Individual URL files automatically created!**
