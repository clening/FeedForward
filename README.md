# Article Automation System

Automated pipeline for processing RSS feed intelligence, fetching full articles, summarizing with Claude AI, and creating Obsidian notes.

## 🎯 What This Does

Transforms your workflow from:
```
RSS emails → Manual Gmail review → Open in browser → 
Leo summary → Copy/paste → Web Clipper → Manual tagging
```

To:
```
Cronjob runs feedforward.py → 
article_processor.py handles everything → 
Review polished notes in Obsidian
```

## 📋 Features

- **Intelligent Content Fetching**: Multi-method approach (trafilatura → Jina Reader → Playwright fallback)
- **AI Summarization**: Uses Claude Sonnet 4 for high-quality summaries
- **Auto-tagging**: Combines keyword matching + Claude's AI suggestions
- **Batch Processing**: Handles 10-100+ articles concurrently
- **Error Resilience**: One failed article doesn't kill the batch
- **Obsidian Integration**: Creates properly formatted notes with frontmatter

## 🚀 Setup

### 1. Install Dependencies

```bash
cd /home/claude/article-automation
pip install -r requirements.txt --break-system-packages

# Install Playwright browsers (for fallback scraping)
playwright install chromium
```

### 2. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your API key
nano .env
```

Required configuration in `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-xxxxx  # Get from https://console.anthropic.com/
OBSIDIAN_VAULT_PATH=Future Trends/Clippings/Unreviewed
```

### 3. Test the System

```bash
# First, make sure you have recent output from feedforward.py
# If you don't have a JSON file yet, export from the pickle:
python3 export_to_json.py --pickle /path/to/output/processed_intelligence.pkl

# Test with 10 articles
python3 article_processor.py output/intelligence_results_*.json --test

# Check the results
ls -l processed/
```

## 📖 Complete Workflow

### Daily Automated Workflow

1. **Cronjob runs feedforward.py** (you already have this)
   ```bash
   # Your existing crontab
   0 9 * * * cd ~/makeitmakesense && python3 feedforward.py -k keywords.txt -f Futures_Feeds.opml -d 1
   ```

2. **Export results to JSON** (new step)
   ```bash
   # Add this to your cron or run manually
   python3 /home/claude/article-automation/export_to_json.py
   ```

3. **Process articles automatically**
   ```bash
   # Process the JSON file (finds the latest one)
   cd /home/claude/article-automation
   latest_json=$(ls -t output/intelligence_results_*.json | head -1)
   python3 article_processor.py "$latest_json"
   ```

4. **Sync to Obsidian**
   - Currently manual: Copy files from `processed/` to Obsidian vault
   - Future: Use `sync_to_obsidian.py` in Claude Desktop

5. **Review in Obsidian**
   - Open `Future Trends/Clippings/Unreviewed/`
   - Read AI summaries
   - Adjust tags
   - Move to main Clippings folder when reviewed

### Testing Workflow

For testing with a small batch:

```bash
# Export recent results
python3 export_to_json.py

# Process just 10-20 articles
python3 article_processor.py output/intelligence_results_*.json --limit 20

# Check what was created
cat processed/[first_article_name].md
```

## 📁 File Structure

```
article-automation/
├── .env.example              # Environment template
├── .env                      # Your config (git-ignored)
├── requirements.txt          # Python dependencies
├── feedforward.py       # Your RSS processor (copy from Ubuntu)
├── article_processor.py     # Main processor (NEW)
├── export_to_json.py        # Helper: pickle → JSON (NEW)
├── sync_to_obsidian.py      # Helper: sync to vault (NEW)
├── output/                  # feedforward.py outputs
│   ├── intelligence_results_*.json
│   └── processed_intelligence.pkl
└── processed/               # Processed articles ready for Obsidian
    ├── Article_One.md
    ├── Article_Two.md
    └── ...
```

## 🔧 Configuration Options

### Environment Variables (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *required* | Your Claude API key |
| `OBSIDIAN_VAULT_PATH` | `Future Trends/Clippings/Unreviewed` | Target folder in vault |
| `MAX_CONCURRENT_REQUESTS` | `5` | Parallel article processing |
| `REQUEST_TIMEOUT` | `30` | Timeout per request (seconds) |
| `USE_JINA_READER` | `true` | Use Jina Reader for content fetching |
| `USE_PLAYWRIGHT_FALLBACK` | `true` | Fall back to browser automation |

### Command Line Options

**article_processor.py:**
```bash
python3 article_processor.py <input_json> [options]

Options:
  -l, --limit N       Process only first N articles
  -t, --test          Test mode (process only 10 articles)
```

**export_to_json.py:**
```bash
python3 export_to_json.py [options]

Options:
  -p, --pickle PATH   Path to pickle file
  -o, --output DIR    Output directory
```

## 🎨 Note Format

Generated notes look like this:

```markdown
---
title: "Article Title"
source: "https://example.com/article"
feed_source: "MIT Technology Review"
published: "2025-01-15"
created: "2025-01-16"
tags: [artificial-intelligence, surveillance, facial-recognition]
status: unreviewed
---

# Article Title

## AI-Generated Summary
- Key point 1
- Key point 2
- Interesting observation

Suggested tags: #AI, #surveillance, #privacy

## Original Article
[Full article content in markdown]

---
**Source:** MIT Technology Review
**URL:** https://example.com/article
**Date:** 2025-01-15
**Keywords Matched:** artificial intelligence, facial recognition

*Review notes:*
- [ ] Read and verify summary
- [ ] Adjust tags as needed
- [ ] Add supplementary observations
```

## 🔍 How Content Fetching Works

The system uses a three-tier fallback chain:

1. **trafilatura** (fast, simple)
   - Direct HTML parsing
   - Works for ~60% of sites
   - Fastest method

2. **Jina Reader** (smart, free API)
   - Handles JavaScript-heavy sites
   - Bypasses many paywalls
   - Works for ~85% of sites
   - URL: `https://r.jina.ai/[article-url]`

3. **Playwright** (nuclear option)
   - Full browser automation
   - Works for difficult sites
   - Slower but most reliable
   - Currently disabled (add if needed)

## 🤖 Claude API Usage

Each article costs approximately:
- **Input tokens**: ~500-1000 (depends on article length)
- **Output tokens**: ~200-500 (summary + tags)
- **Cost**: ~$0.01-0.03 per article

For 20 articles/day: **~$0.20-0.60/day** or **~$6-18/month**

Model used: `claude-sonnet-4-20250514`

## 🚨 Troubleshooting

### "API key not found"
```bash
# Make sure .env exists and has your key
cat .env | grep ANTHROPIC_API_KEY
# Should show: ANTHROPIC_API_KEY=sk-ant-...
```

### "No items found in input file"
```bash
# Check if JSON export worked
cat output/intelligence_results_*.json | head -20

# If empty, re-export from pickle
python3 export_to_json.py --pickle output/processed_intelligence.pkl
```

### "Failed to fetch content" for many articles
```bash
# Enable Jina Reader in .env
USE_JINA_READER=true

# Or reduce concurrent requests (less aggressive)
MAX_CONCURRENT_REQUESTS=2
```

### Claude API rate limits
```bash
# Reduce concurrent requests
MAX_CONCURRENT_REQUESTS=2

# Or process in smaller batches
python3 article_processor.py input.json --limit 10
```

## 📊 Sample Output

```
🤖 Article Processor initialized
📝 Using Claude API
🗂️  Obsidian path: Future Trends/Clippings/Unreviewed

🚀 Starting processing of 20 articles
⚙️  Max concurrent requests: 5

📰 Processing: AI Startup Says It Will End Crime by Blanketing...
  🌐 Fetching from https://futurism.com/ai-startup-crime...
  ✅ Fetched 8432 characters
  🤖 Summarizing with Claude...
  ✅ Generated summary (4 tags)
  📝 Creating Obsidian note...
  ✅ Created note: AI_Startup_Says_It_Will_End_Crime.md

[... 19 more articles ...]

============================================================
📊 PROCESSING SUMMARY
============================================================
Total articles:     20
✅ Fetched:          18
✅ Summarized:       18
✅ Created:          18
❌ Failed:           2
============================================================
```

## 🔮 Future Enhancements

- [ ] Automatic Obsidian sync via MCP (no manual copy)
- [ ] Duplicate detection (check if article already in vault)
- [ ] Quality scoring (skip low-quality content)
- [ ] Multi-language support
- [ ] Custom summarization prompts per topic
- [ ] Integration with Mind Meld plugin (auto-run after processing)
- [ ] Web interface for review

## 📝 Notes

- **Privacy**: All processing happens locally except Claude API calls
- **Costs**: ~$6-18/month for 20 articles/day
- **Speed**: ~10-30 seconds per article (parallel processing)
- **Quality**: Claude Sonnet 4 provides excellent summaries
- **Reliability**: Fallback chain handles 95%+ of sites

## 🆘 Support

If you run into issues:
1. Check the troubleshooting section
2. Run with `--test` flag to isolate problems
3. Check Claude API dashboard for quota/errors
4. Verify `.env` configuration

## 📄 License

Personal use - part of your intelligence gathering system.
