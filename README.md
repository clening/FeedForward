# FeedForward

**Automated RSS intelligence processing for futures research**

FeedForward monitors RSS feeds, filters by keywords, summarizes articles with AI, and creates ready-to-review Obsidian notes. Built for futures forecasting and weak signal detection.

## 🎯 What This Does

**Before FeedForward:**
```
Morning routine: Check RSS → Open 30 tabs → Read articles →
Copy to Leo AI → Summarize → Copy summary → Paste into Obsidian →
Add tags → Repeat 30 times → 90 minutes gone
```

**After FeedForward:**
```
Morning routine: Run feedforward.py -p → Get coffee →
Review polished notes in Obsidian → 15 minutes
```

## ⚡ Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
cp keywords.txt.example keywords.txt
cp feeds.example.opml feeds.opml
# Edit these files with your settings

# 3. Run
python3 feedforward.py -p
```

See [SETUP.md](SETUP.md) for detailed instructions.

## 📋 Features

- **Smart Keyword Filtering**: Organize keywords into categories for better signal detection
- **Multi-Source Content Fetching**: trafilatura → Jina Reader fallback chain
- **AI Summarization**: Claude Sonnet 4 generates bullet-point summaries
- **Auto-Tagging**: Combines keyword matching + Claude's suggestions
- **Rate Limit Handling**: Exponential backoff handles Claude API limits gracefully
- **Direct Obsidian Integration**: Saves formatted notes directly to your vault
- **Deduplication**: Pickle-based tracking prevents reprocessing articles

## 🚀 Usage

### Basic Workflow

```bash
# Generate HTML report only (no AI processing)
python3 feedforward.py

# Full pipeline: RSS → Filter → Summarize → Obsidian notes
python3 feedforward.py -p

# Process limited number of articles (for testing)
python3 feedforward.py -p -l 10

# Custom configuration
python3 feedforward.py -k my_keywords.txt -f my_feeds.opml -d 7
```

### Automated Daily Run

Add to crontab:
```bash
# Run every morning at 6 AM
0 6 * * * cd /path/to/feedforward && python3 feedforward.py -p
```

### Command Line Options

```
Options:
  -k, --keywords FILE       Keywords file (default: from .env)
  -f, --feeds FILE          OPML feed file (default: from .env)
  -o, --output-dir DIR      Output directory (default: output)
  -d, --days-back N         Days to look back (default: 5)
  -p, --process-articles    Process with Claude and create notes
  -l, --article-limit N     Limit articles to process
  --reset                   Reset processing history
```

## 🔧 Configuration

All settings in `.env`:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-xxxxx

# File paths
KEYWORDS_FILE=keywords.txt
FEEDS_FILE=feeds.opml
OUTPUT_DIR=output
DAYS_BACK=5

# Obsidian integration
OBSIDIAN_VAULT_PATH=/path/to/vault/Unreviewed

# Optional: Email HTML reports
EMAIL_ADDRESS=your@email.com

# Article processing
MAX_CONCURRENT_REQUESTS=3    # Lower = slower but avoids rate limits
REQUEST_TIMEOUT=30
USE_JINA_READER=true
```

## 📁 Project Structure

```
feedforward/
├── feedforward.py           # Main RSS processor
├── article_processor.py     # Claude integration & note creation
├── .env                     # Your configuration (gitignored)
├── keywords.txt             # Your keywords (gitignored)
├── feeds.opml               # Your feeds (gitignored)
├── *.example                # Templates for configuration
├── output/                  # HTML reports & processing history
│   ├── intelligence_*.html
│   └── processed_intelligence.pkl
└── processed/               # Or your Obsidian vault path
    └── *.md                 # Generated notes
```

## 🎨 Output Format

Generated Obsidian notes include:

```markdown
---
title: "Article Title"
source: "https://example.com/article"
feed_source: "MIT Technology Review"
published: "2025-01-02"
created: "2025-01-02"
tags: [artificial-intelligence, neuraltech, brain-computer-interface]
status: unreviewed
---

# Article Title

## AI-Generated Summary
- Key theme 1
- Key theme 2
- Interesting observation

#AI #neuraltech #brain-computer-interface

## Original Article
[Full article content in markdown]

---
**Source:** MIT Technology Review
**URL:** https://example.com/article
**Keywords Matched:** artificial intelligence, brain-computer interface
```

## 🔍 How It Works

### Pipeline

1. **Load Configuration** - Read `.env`, keywords, feeds
2. **Fetch RSS Feeds** - Parse your configured OPML file
3. **Filter by Keywords** - Match against your structured keyword list
4. **Generate HTML Report** - Categorized intelligence report
5. **Process Articles** (if `-p` flag):
   - Fetch full article content (trafilatura → Jina Reader)
   - Summarize with Claude API (with retry logic)
   - Extract and suggest tags
   - Create formatted Obsidian notes
   - Save directly to vault

### Content Fetching Strategy

```python
# Two-tier fallback:
1. trafilatura (fast, works for ~70% of sites)
   ↓ (if fails)
2. Jina Reader (handles JS-heavy sites, ~95% success)
   ↓ (if fails)
3. Skip gracefully
```

### Deduplication

Uses pickle file to track processed URLs:
```python
# Prevents reprocessing same articles
processed_items = {
  'https://article-url': '2025-01-02T08:30:00',
  # ... tracks all processed URLs
}
```

## 💰 Costs

Claude API usage (Sonnet 4):
- **Per article**: ~$0.01-0.03
- **20 articles/day**: ~$0.20-0.60/day
- **Monthly** (20/day): ~$6-18/month

## 🚨 Troubleshooting

### Rate Limit Errors

```bash
# Reduce concurrent requests in .env
MAX_CONCURRENT_REQUESTS=2

# Or process in smaller batches
python3 feedforward.py -p -l 10
```

The system has built-in exponential backoff, so it will automatically retry with increasing delays (2s → 4s → 8s → 16s → 32s).

### No Articles Found

```bash
# Check if feeds are loading
python3 feedforward.py  # Should generate HTML report

# Increase days back
python3 feedforward.py -d 10

# Check keywords.txt has valid entries
cat keywords.txt
```

### Failed Content Fetching

Most sites work with trafilatura + Jina Reader. If many fail:
```bash
# Ensure Jina Reader is enabled
USE_JINA_READER=true  # in .env
```

## 🔮 Planned Improvements

- **Source credibility scoring**: Weight articles by feed reliability (Ground News/Wikipedia-style)
- **Better categorization**: Use Claude to suggest keyword additions based on missed articles
- **Foreign language support**: Identify and process non-English sources
- **Mindmap integration**: Connect with existing mindmap tools
- **Web interface**: GUI for easier configuration and review

## 📄 License

MIT License - See LICENSE file

## 🙏 Acknowledgments

Built with:
- [Claude API](https://www.anthropic.com/) for summarization
- [trafilatura](https://github.com/adbar/trafilatura) for content extraction
- [Jina Reader](https://jina.ai/) for fallback fetching
- [feedparser](https://github.com/kurtmckee/feedparser) for RSS parsing

---

**Made with ☕ for futures forecasting and weak signal detection**
