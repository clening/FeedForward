#!/usr/bin/env python3
"""
Article Processor - Automated Content Extraction and Obsidian Integration

PURPOSE:
Takes intelligence items from feedforward.py and:
1. Fetches full article content
2. Summarizes using Claude API
3. Auto-tags based on keywords
4. Creates formatted Obsidian notes

WORKFLOW:
feedforward.py → article_processor.py → Obsidian vault
"""

import os
import sys
import json
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import re
import time
from dotenv import load_dotenv
import anthropic
import trafilatura
from tqdm.asyncio import tqdm

# Load environment variables
load_dotenv()

class ArticleProcessor:
    """Main processor for fetching, summarizing, and saving articles"""
    
    def __init__(self, config_path=None):
        """Initialize with configuration"""
        # Load API key
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key or self.api_key == 'your_api_key_here':
            raise ValueError("Please set ANTHROPIC_API_KEY in .env file")
        
        # Initialize Claude client
        self.client = anthropic.Anthropic(api_key=self.api_key)
        
        # Configuration
        self.obsidian_vault_path = os.getenv('OBSIDIAN_VAULT_PATH', 'Future Trends/Clippings/Unreviewed')
        self.max_concurrent = int(os.getenv('MAX_CONCURRENT_REQUESTS', '3'))  # Reduced from 5 to 3 to avoid rate limits
        self.request_timeout = int(os.getenv('REQUEST_TIMEOUT', '30'))
        self.use_jina = os.getenv('USE_JINA_READER', 'true').lower() == 'true'
        
        # Summarization prompt template
        self.summary_prompt = """Provide a bullet point summary of the page, including key themes and interesting observations. Suggest one or more relevant tags and list them in the format #{{tag}}. For example, #legal, #AI, #neuraltech, #artificial-intelligence, #data-protection, #brain-computer-interface, #quantum-computing

Article Title: {title}
Article URL: {url}
Article Content:
{content}"""
        
        # Stats tracking
        self.stats = {
            'total': 0,
            'fetched': 0,
            'summarized': 0,
            'created': 0,
            'failed': 0,
            'errors': []
        }
        
        print("🤖 Article Processor initialized")
        print(f"📝 Using Claude API")
        print(f"🗂️  Obsidian path: {self.obsidian_vault_path}")
    
    async def fetch_article_content(self, url: str, session: aiohttp.ClientSession) -> Optional[str]:
        """
        Fetch article content with fallback chain
        
        CHAIN: trafilatura → Jina Reader → fail gracefully
        
        WHY: Different sites need different approaches
        """
        # Method 1: Try trafilatura first (fast, works for most sites)
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                content = trafilatura.extract(
                    downloaded,
                    include_comments=False,
                    include_tables=True,
                    output_format='markdown'
                )
                if content and len(content) > 200:  # Minimum viable content
                    return content
        except Exception as e:
            print(f"  ⚠️ trafilatura failed for {url[:50]}: {e}")
        
        # Method 2: Try Jina Reader (handles JS-heavy sites and paywalls better)
        if self.use_jina:
            try:
                jina_url = f"https://r.jina.ai/{url}"
                async with session.get(jina_url, timeout=self.request_timeout) as response:
                    if response.status == 200:
                        content = await response.text()
                        if content and len(content) > 200:
                            return content
            except Exception as e:
                print(f"  ⚠️ Jina Reader failed for {url[:50]}: {e}")
        
        # Method 3: Could add Playwright here but skipping for now (too slow)
        # For production, you'd want to add it as a last resort
        
        return None
    
    def summarize_with_claude(self, title: str, url: str, content: str, max_retries: int = 5) -> Dict:
        """
        Use Claude API to summarize article and extract tags

        RETURNS: {
            'summary': str,
            'tags': list,
            'raw_response': str
        }
        """
        # Truncate content if too long (Claude has context limits)
        max_content_length = 15000  # ~15k chars should be safe
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n\n[Content truncated...]"

        # Format prompt
        prompt = self.summary_prompt.format(
            title=title,
            url=url,
            content=content
        )

        # Retry logic with exponential backoff
        for attempt in range(max_retries):
            try:
                # Call Claude API
                message = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )

                # Extract response
                response_text = message.content[0].text

                # Parse tags from response
                tags = self.extract_tags_from_summary(response_text)

                return {
                    'summary': response_text,
                    'tags': tags,
                    'raw_response': response_text
                }

            except anthropic.RateLimitError as e:
                # Rate limit hit - wait and retry
                wait_time = (2 ** attempt) * 2  # Exponential backoff: 2s, 4s, 8s, 16s, 32s
                if attempt < max_retries - 1:
                    print(f"  ⏱️  Rate limit hit, waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                else:
                    print(f"  ❌ Rate limit error after {max_retries} attempts: {e}")
                    return {
                        'summary': f"Rate limit exceeded after {max_retries} retries",
                        'tags': [],
                        'raw_response': ''
                    }

            except Exception as e:
                print(f"  ❌ Claude API error: {e}")
                return {
                    'summary': f"Error generating summary: {e}",
                    'tags': [],
                    'raw_response': ''
                }

        # Should not reach here, but just in case
        return {
            'summary': "Error: Max retries exceeded",
            'tags': [],
            'raw_response': ''
        }
    
    def extract_tags_from_summary(self, summary: str) -> List[str]:
        """
        Extract hashtags from Claude's summary
        
        PATTERN: Looks for #tag format
        """
        tags = []
        # Find all hashtags
        tag_pattern = r'#([a-zA-Z0-9_-]+)'
        matches = re.findall(tag_pattern, summary)
        
        for match in matches:
            tags.append(match.lower())
        
        return list(set(tags))  # Remove duplicates
    
    def create_obsidian_note(self, item: Dict, summary_data: Dict, content: str) -> str:
        """
        Create formatted Obsidian note
        
        FORMAT: Markdown with YAML frontmatter
        """
        # Extract metadata
        title = item.get('title', 'Untitled')
        url = item.get('url', '')
        source = item.get('source', 'Unknown')
        date = item.get('date', 'Unknown')
        keywords = item.get('keywords', [])
        
        # Combine tags: keywords from RSS + Claude suggestions
        all_tags = list(set(keywords + summary_data['tags']))
        
        # Clean title for filename
        filename = self.sanitize_filename(title)
        
        # Create frontmatter
        frontmatter = f"""---
title: "{title}"
source: "{url}"
feed_source: "{source}"
published: "{date}"
created: "{datetime.now().strftime('%Y-%m-%d')}"
tags: [{', '.join([f'{tag}' for tag in all_tags])}]
status: unreviewed
---

"""
        
        # Create note body
        body = f"""# {title}

## AI-Generated Summary
{summary_data['summary']}

## Original Article
{content}

---
**Source:** {source}
**URL:** {url}
**Date:** {date}
**Keywords Matched:** {', '.join(keywords)}

*Review notes:*
- [ ] Read and verify summary
- [ ] Adjust tags as needed
- [ ] Add supplementary observations
"""
        
        return frontmatter + body, filename
    
    def sanitize_filename(self, title: str, max_length: int = 100) -> str:
        """
        Clean title for use as filename
        
        RULES:
        - Remove special characters
        - Replace spaces with underscores
        - Limit length
        """
        # Remove special characters, keep alphanumeric and spaces
        clean = re.sub(r'[^\w\s-]', '', title)
        # Replace spaces with underscores
        clean = re.sub(r'\s+', '_', clean)
        # Remove leading/trailing underscores
        clean = clean.strip('_')
        # Limit length
        if len(clean) > max_length:
            clean = clean[:max_length]
        
        return clean + '.md'
    
    async def process_single_article(self, item: Dict, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore) -> bool:
        """
        Process a single article through the full pipeline
        
        RETURNS: True if successful, False if failed
        """
        async with semaphore:  # Limit concurrent requests
            url = item.get('url', '')
            title = item.get('title', 'Untitled')
            
            print(f"\n📰 Processing: {title[:60]}...")
            
            # Step 1: Fetch content
            print(f"  🌐 Fetching from {url[:50]}...")
            content = await self.fetch_article_content(url, session)
            
            if not content:
                print(f"  ❌ Failed to fetch content")
                self.stats['failed'] += 1
                self.stats['errors'].append(f"Failed to fetch: {title}")
                return False
            
            self.stats['fetched'] += 1
            print(f"  ✅ Fetched {len(content)} characters")
            
            # Step 2: Summarize with Claude
            print(f"  🤖 Summarizing with Claude...")
            summary_data = await asyncio.to_thread(
                self.summarize_with_claude,
                title, url, content
            )
            
            if not summary_data['summary']:
                print(f"  ❌ Failed to generate summary")
                self.stats['failed'] += 1
                return False
            
            self.stats['summarized'] += 1
            print(f"  ✅ Generated summary ({len(summary_data['tags'])} tags)")

            # Small delay to be nice to API rate limits
            await asyncio.sleep(0.5)

            # Step 3: Create Obsidian note
            print(f"  📝 Creating Obsidian note...")
            note_content, filename = self.create_obsidian_note(item, summary_data, content)
            
            # Step 4: Save to Obsidian vault
            output_path = os.path.join(self.obsidian_vault_path, filename)
            os.makedirs(self.obsidian_vault_path, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(note_content)

            self.stats['created'] += 1
            print(f"  ✅ Created note: {filename}")
            
            return True
    
    async def process_articles(self, items: List[Dict], limit: Optional[int] = None):
        """
        Process multiple articles concurrently
        
        PARAMETERS:
        - items: List of article items from makeitmakesense
        - limit: Optional limit on number to process (for testing)
        """
        # Limit for testing
        if limit:
            items = items[:limit]
        
        self.stats['total'] = len(items)
        print(f"\n🚀 Starting processing of {len(items)} articles")
        print(f"⚙️  Max concurrent requests: {self.max_concurrent}\n")
        
        # Create semaphore for rate limiting
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # Create aiohttp session
        async with aiohttp.ClientSession() as session:
            # Process all items
            tasks = [
                self.process_single_article(item, session, semaphore)
                for item in items
            ]
            
            # Run with progress bar
            results = await tqdm.gather(*tasks, desc="Processing articles")
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print processing summary"""
        print("\n" + "="*60)
        print("📊 PROCESSING SUMMARY")
        print("="*60)
        print(f"Total articles:     {self.stats['total']}")
        print(f"✅ Fetched:          {self.stats['fetched']}")
        print(f"✅ Summarized:       {self.stats['summarized']}")
        print(f"✅ Created:          {self.stats['created']}")
        print(f"❌ Failed:           {self.stats['failed']}")
        print("="*60)
        
        if self.stats['errors']:
            print("\n⚠️  ERRORS:")
            for error in self.stats['errors'][:10]:  # Show first 10
                print(f"  - {error}")
            if len(self.stats['errors']) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Process articles and create Obsidian notes")
    parser.add_argument("input_file", help="JSON file with articles from feedforward.py")
    parser.add_argument("--limit", "-l", type=int, default=None, help="Limit number of articles to process (for testing)")
    parser.add_argument("--test", "-t", action="store_true", help="Test mode: process only first 10 articles")
    
    args = parser.parse_args()
    
    # Test mode sets limit to 10
    if args.test:
        args.limit = 10
    
    # Load input file
    if not os.path.exists(args.input_file):
        print(f"❌ Input file not found: {args.input_file}")
        sys.exit(1)
    
    with open(args.input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    items = data.get('items', [])
    if not items:
        print("⚠️  No items found in input file")
        sys.exit(0)
    
    # Initialize processor
    try:
        processor = ArticleProcessor()
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    
    # Process articles
    await processor.process_articles(items, limit=args.limit)

    print("\n✅ Processing complete!")
    print(f"📁 Notes saved to: {processor.obsidian_vault_path}")


if __name__ == "__main__":
    asyncio.run(main())
