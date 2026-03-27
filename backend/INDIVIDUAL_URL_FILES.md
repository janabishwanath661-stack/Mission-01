# Individual URL File Storage

## Overview

Every scraped URL now gets saved to its own individual JSON file! This gives you complete granular control over your scraped data.

## File Structure

```
backend/scraped_data/
├── Deep_Learning_20260327_123456_226c184a.json    # Aggregated results (all sources)
├── youtube_20260327_123456_226c184a.json          # Source-specific aggregated file
├── github_20260327_123456_226c184a.json           # Source-specific aggregated file
│
└── job_226c184a/                                  # Job-specific directory
    ├── youtube/                                    # Source subdirectory
    │   ├── 000_Roadmap_to_Become_a_Generative_AI.json
    │   ├── 001_Deep_Learning_Full_Course_2024.json
    │   └── 002_Neural_Networks_Explained.json
    │
    ├── github/                                     # Source subdirectory
    │   ├── 000_tensorflow_tensorflow.json
    │   ├── 001_pytorch_pytorch.json
    │   └── 002_keras-team_keras.json
    │
    ├── reddit/
    │   ├── 000_MachineLearning_subreddit.json
    │   └── 001_deeplearning_discussion.json
    │
    └── blogs/
        ├── 000_Understanding_Deep_Learning.json
        └── 001_Neural_Network_Basics.json
```

## Individual URL File Format

Each URL file contains:

```json
{
  "metadata": {
    "job_id": "226c184a-b433-402a-ab9c-3334c3ba2597",
    "source": "youtube",
    "url_index": 0,
    "saved_at": "2026-03-27T12:34:56.789",
    "file_path": "/app/scraped_data/job_226c184a/youtube/000_Roadmap_to_Become.json"
  },
  "data": {
    "title": "Roadmap to Become a Generative AI Expert",
    "url": "https://www.youtube.com/watch?v=example",
    "description": "Complete guide to learning generative AI...",
    "views": "1.2M views",
    "channel": "AI Learning Hub",

    // If deep analysis was performed:
    "extracted_content": {
      "extraction_status": "success",
      "extraction_method": "youtube_page_scraping",
      "word_count": 450,
      "content_preview": "This video covers...",
      "main_content": "Full extracted text content..."
    },

    "analyzed_content": {
      "summary": "Comprehensive roadmap for learning generative AI...",
      "relevance_score": 9,
      "content_quality": "high",
      "content_type": "tutorial",
      "target_audience": "beginners",
      "difficulty_level": "intermediate",
      "sentiment": "informative",
      "key_topics": [
        "generative AI",
        "machine learning",
        "neural networks",
        "transformers",
        "diffusion models"
      ],
      "key_points": [
        "Start with Python fundamentals",
        "Learn PyTorch or TensorFlow",
        "Understand transformer architecture",
        "Practice with real projects"
      ],
      "entities": ["OpenAI", "GPT", "DALL-E", "Midjourney"],
      "actionable_insights": [
        "Follow the structured learning path",
        "Build projects to solidify understanding",
        "Join AI communities for support"
      ],
      "related_concepts": ["LLMs", "computer vision", "NLP"],
      "credibility_score": 8
    }
  }
}
```

## Benefits

1. **Granular Access**: Access data for any specific URL without loading entire datasets
2. **Easy Analysis**: Analyze individual URLs programmatically
3. **Debugging**: Debug issues with specific URLs easily
4. **Data Management**: Delete, update, or re-process individual URLs
5. **Scalability**: Handle large datasets efficiently
6. **Backup**: Easy to backup/restore specific URLs or sources

## Usage

### View All Jobs

```bash
python view_url_files.py
```

Output:
```
================================================================================
AVAILABLE JOBS
================================================================================

1. Job ID: 226c184a
   Created: 2026-03-27 12:34:56
   Total URLs: 120
   Sources: youtube(10), github(10), reddit(10), blogs(15), ...

2. Job ID: af977b47
   Created: 2026-03-27 11:20:30
   Total URLs: 95
   Sources: youtube(10), github(8), twitter(15), ...
```

### View URLs from a Specific Job

```bash
python view_url_files.py 226c184a
```

### View URLs from a Specific Source

```bash
python view_url_files.py 226c184a youtube
```

### View a Specific URL File

```bash
python view_url_files.py --file scraped_data/job_226c184a/youtube/000_Roadmap_to_Become.json
```

## File Naming Convention

- **Prefix**: 3-digit index (000, 001, 002, etc.)
- **Title**: Sanitized title from the URL (alphanumeric + underscores)
- **Extension**: .json

Examples:
- `000_Roadmap_to_Become_a_Generative_AI.json`
- `001_Deep_Learning_Full_Course_2024.json`
- `042_Understanding_Transformers.json`

## Programmatic Access

### Load a Single URL

```python
import json

# Load a specific URL file
with open('scraped_data/job_226c184a/youtube/000_Roadmap_to_Become.json', 'r') as f:
    url_data = json.load(f)

# Access the data
print(url_data['data']['title'])
print(url_data['data']['analyzed_content']['summary'])
```

### Load All URLs from a Source

```python
from pathlib import Path
import json

job_id = "226c184a"
source = "youtube"

# Get all YouTube URL files
youtube_dir = Path(f"scraped_data/job_{job_id}/{source}")
url_files = sorted(youtube_dir.glob("*.json"))

for url_file in url_files:
    with open(url_file, 'r') as f:
        url_data = json.load(f)

    data = url_data['data']
    print(f"Title: {data['title']}")
    print(f"Relevance: {data['analyzed_content']['relevance_score']}/10")
    print()
```

### Filter URLs by Analysis Score

```python
from pathlib import Path
import json

# Find high-quality URLs (relevance >= 8)
high_quality_urls = []

for source_dir in Path("scraped_data/job_226c184a").iterdir():
    if source_dir.is_dir():
        for url_file in source_dir.glob("*.json"):
            with open(url_file, 'r') as f:
                url_data = json.load(f)

            data = url_data['data']
            if 'analyzed_content' in data:
                score = data['analyzed_content'].get('relevance_score', 0)
                if score >= 8:
                    high_quality_urls.append({
                        'title': data['title'],
                        'url': data['url'],
                        'score': score,
                        'source': url_data['metadata']['source']
                    })

# Sort by score
high_quality_urls.sort(key=lambda x: x['score'], reverse=True)

# Display
for item in high_quality_urls:
    print(f"{item['score']}/10 - [{item['source']}] {item['title']}")
    print(f"  {item['url']}\n")
```

## Storage Space

- **Aggregated files**: ~500KB - 5MB per job (depending on results)
- **Individual URL files**: ~2-10KB per URL (without analysis), ~5-20KB (with analysis)
- **Total for 100 URLs**: ~500KB - 2MB

## Retention

All files are persistent and stored in the `backend/scraped_data` directory. They are:
- ✅ Backed up if you backup the project directory
- ✅ Accessible even after container restarts (volume mounted)
- ✅ Organized by job for easy cleanup

## Cleanup

To remove old job data:

```bash
# Remove a specific job
rm -rf backend/scraped_data/job_226c184a

# Remove jobs older than 7 days
find backend/scraped_data -name "job_*" -type d -mtime +7 -exec rm -rf {} \;

# Keep only the 10 most recent jobs
ls -t backend/scraped_data/job_* -d | tail -n +11 | xargs rm -rf
```

## Integration with Existing Features

The individual URL files work alongside existing features:

1. **Aggregated Files**: Still created for backward compatibility
2. **Database**: Job status and metadata still stored in SQLite
3. **Frontend**: Compatible with existing UI (uses aggregated data)
4. **Analysis**: Deep analysis enriches individual URL files

## Future Enhancements

Possible future improvements:

- [ ] Web UI to browse individual URL files
- [ ] Export selected URLs to CSV/Excel
- [ ] Bulk re-analysis of specific URLs
- [ ] URL tagging and categorization
- [ ] Search across all URL files
- [ ] Duplicate URL detection
- [ ] URL content diffing (track changes over time)
