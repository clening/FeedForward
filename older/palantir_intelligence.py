#!/usr/bin/env python3
"""
Enhanced Data Protection Keyword Parser
Monitors RSS feeds and government sources for datap protection related content
"""

import argparse
import os
import sys
import re
import json
import xml.etree.ElementTree as ET
import feedparser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
import pickle
import warnings
import dateutil.parser
import requests
import time
import asyncio
import aiohttp
from typing import Dict, List, Optional

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

class PalantirIntelligenceProcessor:
    """Enhanced intelligence processor for Palantir monitoring."""
    
    def __init__(self, opml_file=None, output_dir="output", keywords=None, days_back=7):
        self.opml_file = opml_file
        self.output_dir = output_dir
        self.keywords = keywords or []
        self.days_back = days_back
        self.feeds = []
        self.results = {}
        self.history_file = os.path.join(output_dir, "processed_intelligence.pkl")
        self.processed_items = self.load_history()
        
        # Government API endpoints (simplified for demo)
        self.gov_sources = {
            'federal_register': 'https://www.federalregister.gov/api/v1/documents.json',
            'sam_gov': 'https://api.sam.gov/opportunities/v2/search'
        }
        
        print(f"🎯 Intelligence Processor initialized")
        print(f"📊 Monitoring {len(self.keywords)} keywords")
        print(f"📅 Looking back {self.days_back} days")
    
    def load_history(self):
        """Load processing history to avoid duplicates."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"⚠️  Error loading history: {e}")
                return {}
        return {}
    
    def save_history(self):
        """Save processing history."""
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            with open(self.history_file, 'wb') as f:
                pickle.dump(self.processed_items, f)
            print(f"💾 Saved processing history")
        except Exception as e:
            print(f"⚠️  Error saving history: {e}")
    
    def load_keywords(self, file_path):
        """Load keywords from file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                keywords = [line.strip() for line in f if line.strip()]
                print(f"📋 Loaded {len(keywords)} keywords from {file_path}")
                return keywords
        except Exception as e:
            print(f"⚠️  Error loading keywords: {e}")
            return []
    
    def parse_opml(self):
        """Parse OPML file for RSS feeds."""
        if not self.opml_file or not os.path.exists(self.opml_file):
            print("📂 No OPML file provided, using default feeds")
            self.add_default_feeds()
            return
        
        try:
            with open(self.opml_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Fix XML issues
            fixed_content = re.sub(r'&(?!amp;|lt;|gt;|apos;|quot;)', '&amp;', content)
            root = ET.fromstring(fixed_content)
            
            for outline in root.findall(".//outline[@xmlUrl]"):
                feed_title = outline.get("title", "Unnamed Feed")
                feed_url = outline.get("xmlUrl")
                
                if feed_url:
                    self.feeds.append({
                        "title": feed_title,
                        "url": feed_url,
                        "type": "rss"
                    })
            
            print(f"📡 Loaded {len(self.feeds)} RSS feeds from OPML")
        except Exception as e:
            print(f"⚠️  Error parsing OPML: {e}")
            self.add_default_feeds()
    
    def add_default_feeds(self):
        """Add default RSS feeds focused on government and tech news."""
        default_feeds = 'Reader_Feeds.opml'
        
        self.feeds.extend(default_feeds)
        print(f"📡 Added {len(default_feeds)} default feeds")
    
    def contains_keywords(self, text):
        """Check if text contains any of our keywords."""
        if not self.keywords:
            return True  # If no keywords specified, include everything
        
        text_lower = text.lower()
        matched = []
        
        for keyword in self.keywords:
            if keyword.lower() in text_lower:
                matched.append(keyword)
        
        return len(matched) > 0, matched
    
    def extract_content(self, entry):
        """Extract clean content from RSS entry."""
        content = ""
        
        # Try different content fields
        if hasattr(entry, 'content') and entry.content:
            content = entry.content[0].value
        elif hasattr(entry, 'summary'):
            content = entry.summary
        elif hasattr(entry, 'description'):
            content = entry.description
        
        # Clean HTML
        if content:
            try:
                soup = BeautifulSoup(content, "html.parser")
                content = soup.get_text(separator=' ', strip=True)
            except Exception:
                pass
        
        return content
    
    def is_recent(self, entry):
        """Check if entry is recent enough."""
        try:
            # Try different date fields
            date_str = None
            if hasattr(entry, 'published'):
                date_str = entry.published
            elif hasattr(entry, 'updated'):
                date_str = entry.updated
            
            if date_str:
                try:
                    entry_date = dateutil.parser.parse(date_str)
                    if entry_date.tzinfo is None:
                        entry_date = entry_date.replace(tzinfo=timezone.utc)
                    
                    cutoff = datetime.now(timezone.utc) - timedelta(days=self.days_back)
                    return entry_date >= cutoff
                except Exception:
                    pass
            
            # If we can't parse date, include it
            return True
            
        except Exception:
            return True
    
    def generate_summary(self, content, title, keywords):
        """Generate a summary focusing on keyword relevance."""
        # Find sentences containing keywords
        sentences = re.split(r'[.!?]+', content)
        relevant_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 30:
                sentence_lower = sentence.lower()
                if any(kw.lower() in sentence_lower for kw in keywords):
                    relevant_sentences.append(sentence)
                    if len(relevant_sentences) >= 3:
                        break
        
        if relevant_sentences:
            summary = ". ".join(relevant_sentences) + "."
        else:
            # Fallback to first few sentences
            summary = ". ".join([s.strip() for s in sentences[:2] if s.strip()]) + "."
        
        # Add context about what makes this relevant
        if keywords:
            summary += f"\n\n🎯 Relevant keywords found: {', '.join(keywords)}"
        
        return summary
    
    def extract_entities(self, text):
        """Extract key entities like companies, agencies, amounts."""
        entities = {
            'companies': [],
            'agencies': [],
            'amounts': [],
            'people': []
        }
        
        # Extract monetary amounts
        amount_pattern = r'\$[\d,]+(?:\.\d{2})?\s*(?:million|billion|thousand|M|B|K)?'
        amounts = re.findall(amount_pattern, text, re.IGNORECASE)
        entities['amounts'] = amounts[:5]  # Limit results
        
        # Extract government agencies
        agency_patterns = [
            r'Department of [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',
            r'DOD|Pentagon|CIA|FBI|NSA|DHS|ICE|CBP',
            r'Office of [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*'
        ]
        
        for pattern in agency_patterns:
            matches = re.findall(pattern, text)
            entities['agencies'].extend(matches)
        
        # Extract companies
        company_indicators = ['Inc', 'Corp', 'LLC', 'Ltd', 'Technologies', 'Systems']
        words = text.split()
        
        for i, word in enumerate(words):
            if any(indicator in word for indicator in company_indicators):
                # Get company name (assume it's the previous 1-2 words + this word)
                start = max(0, i-2)
                company = ' '.join(words[start:i+1])
                if len(company) > 5:  # Avoid short matches
                    entities['companies'].append(company)
        
        # Remove duplicates and limit
        for key in entities:
            entities[key] = list(set(entities[key]))[:5]
        
        return entities
    
    async def fetch_government_sources(self, session):
        """Fetch from all government sources."""
        gov_items = []
        
        # Federal Register
        fed_items = await self.fetch_federal_register_data(session)
        gov_items.extend(fed_items)
        
        # USASpending.gov
        usa_items = await self.fetch_usaspending_awards(session)
        gov_items.extend(usa_items)
        
        # Defense.gov RSS
        def_items = await self.fetch_defense_contracts(session)
        gov_items.extend(def_items)
        
        return gov_items
    
    async def fetch_federal_register(self, session):
        """Fetch Federal Register documents (simplified)."""
        items = []
        
        try:
            # Build search query
            keywords_query = ' OR '.join([f'"{kw}"' for kw in self.keywords[:3]])  # Limit to avoid long URLs
            
            params = {
                'conditions[term]': keywords_query,
                'conditions[publication_date][gte]': (datetime.now() - timedelta(days=self.days_back)).strftime('%Y-%m-%d'),
                'per_page': 20,
                'fields[]': ['title', 'abstract', 'html_url', 'publication_date', 'agencies']
            }
            
            print(f"🏛️  Searching Federal Register for: {keywords_query}")
            
            async with session.get(self.gov_sources['federal_register'], params=params, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for doc in data.get('results', []):
                        item_id = doc.get('html_url', '')
                        if item_id and item_id not in self.processed_items:
                            items.append({
                                'id': item_id,
                                'title': doc.get('title', ''),
                                'content': doc.get('abstract', ''),
                                'url': item_id,
                                'date': doc.get('publication_date', ''),
                                'source': 'Federal Register',
                                'source_type': 'government',
                                'agencies': doc.get('agencies', [])
                            })
                            
                            self.processed_items[item_id] = datetime.now().isoformat()
                
                print(f"📄 Found {len(items)} Federal Register documents")
        
        except Exception as e:
            print(f"⚠️  Error fetching Federal Register: {e}")
        
        return items
    
    async def process_rss_feeds(self, session):
        """Process RSS feeds asynchronously."""
        items = []
        
        for feed in self.feeds:
            if feed.get('type') != 'rss':
                continue
                
            print(f"📡 Processing: {feed['title']}")
            
            try:
                # Use feedparser for RSS (it handles the complexity)
                parsed_feed = feedparser.parse(feed['url'])
                
                for entry in parsed_feed.entries[:30]:  # Limit per feed
                    entry_url = entry.get('link', '')
                    
                    if not entry_url or entry_url in self.processed_items:
                        continue
                    
                    if not self.is_recent(entry):
                        continue
                    
                    title = entry.get('title', '')
                    content = self.extract_content(entry)
                    
                    # Check for keyword matches
                    has_keywords, matched_keywords = self.contains_keywords(f"{title} {content}")
                    
                    if has_keywords:
                        # Generate summary
                        summary = self.generate_summary(content, title, matched_keywords)
                        
                        # Extract entities
                        entities = self.extract_entities(f"{title} {content}")
                        
                        items.append({
                            'id': entry_url,
                            'title': title,
                            'content': content,
                            'summary': summary,
                            'url': entry_url,
                            'date': entry.get('published', ''),
                            'source': feed['title'],
                            'source_type': 'rss',
                            'keywords': matched_keywords,
                            'entities': entities
                        })
                        
                        self.processed_items[entry_url] = datetime.now().isoformat()
                
                # Rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"⚠️  Error processing {feed['title']}: {e}")
        
        return items
    
    async def process_all_sources(self):
        """Process all intelligence sources."""
        print(f"🚀 Starting intelligence collection...")
        
        all_items = []
        
        # Create HTTP session
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Process RSS feeds
            rss_items = await self.process_rss_feeds(session)
            all_items.extend(rss_items)
            
            # Process Federal Register (if keywords specified)
            if self.keywords:
                fed_items = await self.fetch_federal_register(session)
                all_items.extend(fed_items)
        
        # Store results
        for item in all_items:
            self.results[item['id']] = item
        
        # Save history
        self.save_history()
        
        print(f"✅ Collected {len(all_items)} intelligence items")
        return len(all_items)
    
    def generate_intelligence_report(self):
        """Generate comprehensive HTML intelligence report."""
        if not self.results:
            print("📭 No intelligence items found")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        report_path = os.path.join(self.output_dir, f"palantir_intelligence_{timestamp}.html")
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Sort by date (newest first)
        sorted_items = sorted(
            self.results.values(),
            key=lambda x: x.get('date', ''),
            reverse=True
        )
        
        # Generate statistics
        stats = self.generate_stats(sorted_items)
        
        html = self.generate_html_content(sorted_items, stats, timestamp)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"📊 Intelligence report generated: {report_path}")
        return report_path
    
    def generate_stats(self, items):
        """Generate statistics for the report."""
        stats = {
            'total_items': len(items),
            'source_breakdown': {},
            'keyword_frequency': {},
            'agencies_mentioned': set(),
            'total_amounts': []
        }
        
        # Source breakdown
        for item in items:
            source_type = item.get('source_type', 'unknown')
            stats['source_breakdown'][source_type] = stats['source_breakdown'].get(source_type, 0) + 1
        
        # Keyword frequency
        for item in items:
            for keyword in item.get('keywords', []):
                stats['keyword_frequency'][keyword] = stats['keyword_frequency'].get(keyword, 0) + 1
        
        # Agencies and amounts
        for item in items:
            entities = item.get('entities', {})
            if entities.get('agencies'):
                stats['agencies_mentioned'].update(entities['agencies'])
            if entities.get('amounts'):
                stats['total_amounts'].extend(entities['amounts'])
        
        return stats
    
    def generate_html_content(self, items, stats, timestamp):
        """Generate the HTML content for the report."""
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Intelligence Report - {timestamp}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f7fa;
            line-height: 1.6;
        }}
        .header {{
            background: linear-gradient(135deg, #2c3e50, #3498db);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #3498db;
        }}
        .intelligence-item {{
            background: white;
            margin: 20px 0;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-left: 5px solid #3498db;
        }}
        .source-badge {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: bold;
            margin-right: 10px;
            color: white;
        }}
        .source-rss {{ background-color: #e74c3c; }}
        .source-government {{ background-color: #27ae60; }}
        .summary {{
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
            border-left: 3px solid #3498db;
        }}
        .keywords {{
            margin: 15px 0;
        }}
        .keyword {{
            display: inline-block;
            background-color: #3498db;
            color: white;
            padding: 3px 8px;
            border-radius: 15px;
            font-size: 0.85em;
            margin-right: 5px;
            margin-bottom: 5px;
        }}
        .entities {{
            margin: 15px 0;
            font-size: 0.9em;
            color: #7f8c8d;
        }}
        .metadata {{
            color: #7f8c8d;
            font-size: 0.9em;
            margin-top: 15px;
        }}
        a {{ color: #2980b9; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .no-results {{
            text-align: center;
            padding: 50px;
            color: #7f8c8d;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 Daily Intelligence Report</h1>
        <p>Generated: {datetime.now().strftime('%B %d, %Y at %H:%M UTC')}</p>
        <p>Monitoring Period: Last {self.days_back} day(s)</p>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <div class="stat-number">{stats['total_items']}</div>
            <div>Total Intelligence Items</div>
        </div>
"""
        
        # Add source breakdown stats
        for source_type, count in stats['source_breakdown'].items():
            html += f"""
        <div class="stat-card">
            <div class="stat-number">{count}</div>
            <div>{source_type.replace('_', ' ').title()} Sources</div>
        </div>
"""
        
        # Add keyword stats
        if stats['keyword_frequency']:
            top_keyword = max(stats['keyword_frequency'].items(), key=lambda x: x[1])
            html += f"""
        <div class="stat-card">
            <div class="stat-number">{top_keyword[1]}</div>
            <div>Top Keyword: {top_keyword[0]}</div>
        </div>
"""
        
        html += """
    </div>
    
    <div class="intelligence-items">
        <h2>📋 Intelligence Items</h2>
"""
        
        if not items:
            html += """
        <div class="no-results">
            <h3>No intelligence items found</h3>
            <p>Try adjusting your keywords or time range</p>
        </div>
"""
        else:
            for i, item in enumerate(items, 1):
                html += self.generate_item_html(item, i)
        
        html += """
    </div>
</body>
</html>
"""
        return html
    
    def generate_item_html(self, item, index):
        """Generate HTML for individual intelligence item."""
        source_type = item.get('source_type', 'unknown')
        
        html = f"""
        <div class="intelligence-item">
            <h3>{index}. <a href="{item.get('url', '#')}" target="_blank">{item.get('title', 'Untitled')}</a></h3>
            
            <span class="source-badge source-{source_type}">{source_type.replace('_', ' ').title()}</span>
"""
        
        # Add summary if available
        if item.get('summary'):
            html += f"""
            <div class="summary">
                <strong>📝 Summary:</strong><br>
                {item['summary'].replace('\\n', '<br>')}
            </div>
"""
        
        # Add keywords
        if item.get('keywords'):
            html += f"""
            <div class="keywords">
                <strong>🎯 Keywords:</strong>
                {' '.join([f'<span class="keyword">{kw}</span>' for kw in item['keywords']])}
            </div>
"""
        
        # Add entities
        entities = item.get('entities', {})
        if any(entities.values()):
            html += '<div class="entities"><strong>🏢 Entities:</strong><br>'
            
            if entities.get('agencies'):
                html += f"<strong>Agencies:</strong> {', '.join(entities['agencies'][:3])}<br>"
            
            if entities.get('amounts'):
                html += f"<strong>Amounts:</strong> {', '.join(entities['amounts'][:3])}<br>"
            
            if entities.get('companies'):
                html += f"<strong>Companies:</strong> {', '.join(entities['companies'][:3])}<br>"
            
            html += '</div>'
        
        # Add metadata
        html += f"""
            <div class="metadata">
                <strong>Source:</strong> {item.get('source', 'Unknown')}<br>
                <strong>Date:</strong> {item.get('date', 'Unknown')}<br>
                <strong>Type:</strong> {item.get('source_type', 'Unknown')}
            </div>
        </div>
"""
        return html

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Enhanced Palantir Intelligence Processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python palantir_intelligence.py -k keywords.txt -f Reader_Feeds.opml -d 7
  python palantir_intelligence.py -k keywords.txt --gov -f Reader_Feeds.opml -d 3
        """
    )
    
    parser.add_argument("--output-dir", "-o", default="output", help="Output directory")
    parser.add_argument("--days-back", "-d", type=int, default=7, help="Days back to search")
    parser.add_argument("--gov", action="store_true", help="Include government sources")
    parser.add_argument("--reset", action="store_true", help="Reset processing history")
    
    args = parser.parse_args()
    
    # Load keywords
    keywords = []
    with open('keywords.txt', 'r', encoding='utf-8') as f:
        keywords = [line.strip() for line in f if line.strip()]
    
 
    # Initialize processor
    processor = PalantirIntelligenceProcessor(
        opml_file='Reader_Feeds.opml',
        output_dir=args.output_dir,
        keywords=keywords,
        days_back=args.days_back
    )
    
    # Reset history if requested
    if args.reset and os.path.exists(processor.history_file):
        try:
            os.remove(processor.history_file)
            print("🔄 Processing history reset")
        except Exception as e:
            print(f"⚠️  Error resetting history: {e}")
    
    # Parse feeds
    processor.parse_opml()
    
    # Run processing
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        items_found = loop.run_until_complete(processor.process_all_sources())
        
        if items_found > 0:
            processor.generate_intelligence_report()
            print("✅ Intelligence collection complete!")
        else:
            print("📭 No new intelligence items found")
            
    except Exception as e:
        print(f"❌ Error during processing: {e}")
        sys.exit(1)
    finally:
        loop.close()

if __name__ == "__main__":
    main()
