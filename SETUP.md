# Setup Guide

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd article-automation
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your environment**
   ```bash
   # Copy example files
   cp .env.example .env
   cp keywords.txt.example keywords.txt
   cp feeds.example.opml feeds.opml
   ```

4. **Edit configuration files**
   - `.env` - Add your Claude API key and paths
   - `keywords.txt` - Add your monitoring keywords
   - `feeds.opml` - Add your RSS feeds

5. **Run the tool**
   ```bash
   # Basic run (RSS filtering + HTML report)
   python3 feedforward.py

   # With article processing (requires Claude API)
   python3 feedforward.py -p
   ```

## Configuration Details

### .env File

Edit `.env` with your settings:

```bash
# Required: Get API key from https://console.anthropic.com/
ANTHROPIC_API_KEY=your_api_key_here

# Where to find your config files
KEYWORDS_FILE=keywords.txt
FEEDS_FILE=feeds.opml

# Where to save processed notes
OBSIDIAN_VAULT_PATH=./processed

# Optional: Rate limit settings
MAX_CONCURRENT_REQUESTS=3
REQUEST_TIMEOUT=30
```

### keywords.txt File

Structure your keywords by category:

```
#Social
## Healthcare
public health
healthcare access

## Education
education policy
learning outcomes

#Technological
## AI & Machine Learning
artificial intelligence
machine learning
neural networks
```

**Important:** Avoid short acronyms (3-4 letters) that might match unintended words.

### feeds.opml File

Add RSS feeds in OPML format. You can:
- Export from your RSS reader (Feedly, NewsBlur, etc.)
- Manually add feeds following the example structure
- Find RSS feed URLs on websites you want to monitor

## Usage Examples

```bash
# Use all defaults from .env
python3 feedforward.py

# Process articles with Claude (creates Obsidian notes)
python3 feedforward.py -p

# Limit to 10 articles for testing
python3 feedforward.py -p -l 10

# Look back 7 days instead of default 5
python3 feedforward.py -d 7

# Use custom files
python3 feedforward.py -k my_keywords.txt -f my_feeds.opml
```

## Output

The tool creates:
1. **HTML report** - Categorized intelligence report in `output/` directory
2. **Processed notes** (with `-p` flag) - Markdown files in your configured vault path
3. **Processing history** - Pickle file to avoid reprocessing items

## Troubleshooting

### Rate Limit Errors
If you hit Claude API rate limits:
- Reduce `MAX_CONCURRENT_REQUESTS` in `.env` (try 2 or 1)
- Use `-l` to limit articles processed
- The tool will automatically retry with exponential backoff

### No Items Found
- Check that your keywords.txt has relevant terms
- Increase `-d` days back to search more history
- Verify your feeds.opml has valid RSS URLs

### Permission Errors
- Ensure `OBSIDIAN_VAULT_PATH` directory exists and is writable
- Use absolute paths if relative paths cause issues

## Next Steps

- Customize `keywords.txt` for your research interests
- Add more RSS feeds to `feeds.opml`
- Set up a cron job for automated daily processing
- Adjust `MAX_CONCURRENT_REQUESTS` based on your API tier
