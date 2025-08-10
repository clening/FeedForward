#!/usr/bin/env python3
"""
Enhanced Data Protection Keyword Parser
Monitors RSS feeds and government sources for data protection related content

OVERVIEW:
This script is an intelligence gathering system that:
1. Reads RSS feeds from an OPML file
2. Searches government APIs (Federal Register, etc.)
3. Filters content based on keywords from a provided text file
4. Generates HTML reports of relevant findings

"""

import argparse
import os
import sys
import re
import json
import xml.etree.ElementTree as ET
import feedparser  # Third-party library for parsing RSS feeds
from datetime import datetime, timedelta, timezone
from pathlib import Path
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning  # HTML parsing
import pickle  # For saving/loading processing history
import warnings
import dateutil.parser  # Better date parsing
import requests
import time
import asyncio  # For concurrent processing
import aiohttp  # Async HTTP requests
from typing import Dict, List, Optional

# Suppress warnings from BeautifulSoup about HTML-like strings
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

class PalantirIntelligenceProcessor:
    """
    Main class that handles all intelligence gathering operations.
    
    PURPOSE: Centralize all the logic for monitoring multiple data sources,
    filtering content, and generating reports.
    
    WHY CLASS-BASED: Keeps state (processed items, configuration) and 
    provides clean separation of concerns.
    """
    
    def __init__(self, opml_file=None, output_dir="output", keywords=None, days_back=7):
        """
        Initialize the intelligence processor with configuration.
        
        PARAMETERS:
        - opml_file: File containing RSS feed URLs (OPML format)
        - output_dir: Where to save reports and history
        - keywords: List of terms to search for
        - days_back: How many days of historical data to process
        
        WHY THESE PARAMETERS: Flexibility to change what we monitor,
        where we save results, and how far back we look.
        """
        self.opml_file = opml_file
        self.output_dir = output_dir
        self.keywords = keywords or []
        self.days_back = days_back
        
        # Storage for feeds and results
        self.feeds = []  # List of RSS feed URLs and metadata
        self.results = {}  # Dictionary of processed intelligence items
        
        # History tracking to avoid reprocessing same items
        self.history_file = os.path.join(output_dir, "processed_intelligence.pkl")
        self.processed_items = self.load_history()  # Load previously processed URLs
        
        # Government API endpoints (simplified for demo)
        # WHY THESE: Government sources often have different APIs than RSS
        self.gov_sources = {
            'federal_register': 'https://www.federalregister.gov/api/v1/documents.json',
            'sam_gov': 'https://api.sam.gov/opportunities/v2/search'
        }
        
        # User feedback about initialization
        print(f"🎯 Intelligence Processor initialized")
        print(f"📊 Monitoring {len(self.keywords)} keywords")
        print(f"📅 Looking back {self.days_back} days")
    
    def is_recent(self, entry):
        """
        Check if RSS entry is within our time window.
        
        PURPOSE: Filter out old content - only process recent items.
        
        WHY NEEDED: RSS feeds often contain old items, and we only want
        items from the last N days.
        
        COMPLEXITY: Different feeds use different date fields and formats.
        """
        try:
            # Try different date fields (feeds vary in naming)
            date_str = None
            if hasattr(entry, 'published'):
                date_str = entry.published
            elif hasattr(entry, 'updated'):
                date_str = entry.updated
            
            if date_str:
                try:
                    # Parse the date string
                    entry_date = dateutil.parser.parse(date_str)
                    
                    # Ensure timezone awareness (assume UTC if none)
                    if entry_date.tzinfo is None:
                        entry_date = entry_date.replace(tzinfo=timezone.utc)
                    
                    # Check if within our time window
                    cutoff = datetime.now(timezone.utc) - timedelta(days=self.days_back)
                    return entry_date >= cutoff
                except Exception:
                    pass  # Date parsing failed
            
            # If we can't parse date, include it (better to include than miss)
            return True
            
        except Exception:
            return True  # Default to including the item
    
    def load_history(self):
        """
        Load previously processed items to avoid duplicates.
        
        PURPOSE: Performance optimization - don't reprocess items we've already seen.
        
        MECHANISM: Uses pickle to serialize/deserialize a dictionary of processed URLs.
        
        WHY PICKLE: Simple way to persist Python objects between runs.
        Could use JSON, but pickle handles complex objects better.
        """
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"⚠️  Error loading history: {e}")
                return {}  # Start fresh if history is corrupted
        return {}  # No history file exists yet
    
    def save_history(self):
        """
        Save processing history for next run.
        
        PURPOSE: Persist the URLs/IDs we've already processed so we don't 
        reprocess them in future runs.
        
        WHY NEEDED: RSS feeds often contain the same items across multiple fetches.
        Without this, we'd generate duplicate reports.
        """
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            with open(self.history_file, 'wb') as f:
                pickle.dump(self.processed_items, f)
            print(f"💾 Saved processing history")
        except Exception as e:
            print(f"⚠️  Error saving history: {e}")
    
    def load_keywords(self, file_path):
        """
        Load keywords from a text file (one keyword per line).
        
        PURPOSE: External keyword configuration - allows changing what we monitor
        without modifying code.
        
        WHY FILE-BASED: Easier to maintain keyword lists, can be edited by 
        non-programmers, version controlled separately.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                keywords = [line.strip() for line in f if line.strip()]
                print(f"📋 Loaded {len(keywords)} keywords from {file_path}")
                return keywords
        except Exception as e:
            print(f"⚠️  Error loading keywords: {e}")
            return []
    
    def parse_opml(self):
        """
        Parse OPML (Outline Processor Markup Language) file for RSS feed URLs.
        
        PURPOSE: OPML is a standard format for exporting RSS subscriptions from
        feed readers. This lets users export their feeds and use them here.
        
        WHY OPML: Standard format, supported by most RSS readers (Feedly, etc.)
        
        WHAT IT DOES:
        1. Reads XML file
        2. Finds <outline> elements with xmlUrl attributes
        3. Extracts feed titles and URLs
        4. Stores in self.feeds list
        """
        if not self.opml_file or not os.path.exists(self.opml_file):
            print("📂 No OPML file provided. Please add a file.")
            return
        
        try:
            with open(self.opml_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Fix common XML issues (unescaped ampersands)
            # WHY NEEDED: Many OPML exports have malformed XML
            fixed_content = re.sub(r'&(?!amp;|lt;|gt;|apos;|quot;)', '&amp;', content)
            root = ET.fromstring(fixed_content)
            
            # Find all outline elements with RSS URLs
            for outline in root.findall(".//outline[@xmlUrl]"):
                feed_title = outline.get("title", "Unnamed Feed")
                feed_url = outline.get("xmlUrl")
                
                if feed_url:
                    self.feeds.append({
                        "title": feed_title,
                        "url": feed_url,
                        "type": "rss"  # Tag for later processing
                    })
            
            print(f"📡 Loaded {len(self.feeds)} RSS feeds from OPML")
        except Exception as e:
            print(f"⚠️  Error parsing OPML: {e}")
            
    def contains_keywords(self, text):
        """
        Check if text contains any of our target keywords.
        
        PURPOSE: Core filtering logic - determines if content is relevant.
        
        RETURNS: (bool, list) - whether keywords found and which ones
        
        WHY CASE-INSENSITIVE: Keywords might appear in different cases
        in source material.
        """
        if not self.keywords:
            return True, []  # If no keywords specified, include everything
        
        text_lower = text.lower()
        matched = []
        
        # Check each keyword against the text
        for keyword in self.keywords:
            if keyword.lower() in text_lower:
                matched.append(keyword)
        
        return len(matched) > 0, matched
    
    def extract_content(self, entry):
        """
        Extract clean text content from RSS entry.
        
        PURPOSE: RSS entries can have content in different fields and formats.
        This normalizes that into clean text.
        
        WHY MULTIPLE FIELDS: Different RSS feeds structure content differently:
        - Some use 'content' field
        - Some use 'summary' 
        - Some use 'description'
        
        WHY HTML CLEANING: RSS content is often HTML, but we want plain text
        for keyword matching and display.
        """
        content = ""
        
        # Try different content fields in order of preference
        if hasattr(entry, 'content') and entry.content:
            content = entry.content[0].value  # Content is usually a list
        elif hasattr(entry, 'summary'):
            content = entry.summary
        elif hasattr(entry, 'description'):
            content = entry.description
        
        # Clean HTML tags and convert to plain text
        if content:
            try:
                soup = BeautifulSoup(content, "html.parser")
                content = soup.get_text(separator=' ', strip=True)
            except Exception:
                pass  # If parsing fails, use original content
        
        return content
        
    def generate_summary(self, content, title, keywords):
        """
        Generate a focused summary highlighting keyword relevance.
        
        PURPOSE: Create concise summaries that show WHY an item was flagged.
        
        STRATEGY:
        1. Find sentences containing keywords
        2. Use those as the summary
        3. Fall back to first sentences if needed
        4. Add context about matched keywords
        
        WHY SENTENCE-BASED: More readable than word-based extraction.
        """
        # Split content into sentences
        sentences = re.split(r'[.!?]+', content)
        relevant_sentences = []
        
        # Find sentences that contain our keywords
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 30:  # Skip very short sentences
                sentence_lower = sentence.lower()
                if any(kw.lower() in sentence_lower for kw in keywords):
                    relevant_sentences.append(sentence)
                    if len(relevant_sentences) >= 6:  # Limit summary length
                        break
        
        if relevant_sentences:
            summary = ". ".join(relevant_sentences) + "."
        else:
            # Fallback: use first few sentences
            summary = ". ".join([s.strip() for s in sentences[:2] if s.strip()]) + "."
        
        # Add context about keyword matches
        if keywords:
            summary += f"\n\n🎯 Relevant keywords found: {', '.join(keywords)}"
        
        return summary
    
    def extract_entities(self, text):
        """
        Extract key entities like companies, agencies, and dollar amounts.
        
        PURPOSE: Provide structured data about what's mentioned in content.
        This helps with analysis and filtering.
        
        WHY REGEX: Simple pattern matching for common entity types.
        Could use NLP libraries, but regex is faster and good enough for basic extraction.
        
        ENTITY TYPES:
        - amounts: Dollar figures ($1M, $500K, etc.)
        - agencies: Government departments and agencies
        - companies: Organizations with common suffixes
        - people: (skeleton implementation)
        """
        entities = {
            'companies': [],
            'agencies': [],
            'amounts': [],
            'people': []
        }
        
        # Extract monetary amounts ($1M, $500,000, etc.)
        amount_pattern = r'[\$€£¥][\d,]+(?:\.\d{2})?\s*(?:million|billion|thousand|M|B|K)?'
        amounts = re.findall(amount_pattern, text, re.IGNORECASE)
        entities['amounts'] = amounts[:5]  # Limit to avoid spam
        
        # Extract government agencies
        agency_patterns = [
            r'Department of [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',  # Department of X
            r'DOD|Pentagon|CIA|FBI|NSA|DHS|ICE|CBP',  # Common abbreviations
            r'Office of [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*'  # Office of X
            
        ]
        
        for pattern in agency_patterns:
            matches = re.findall(pattern, text)
            entities['agencies'].extend(matches)
        
        # Extract companies (look for common corporate suffixes)
        company_indicators = ['Inc', 'Corp', 'LLC', 'Ltd', 'Technologies', 'Systems', 'GmbH']
        words = text.split()
        
        for i, word in enumerate(words):
            if any(indicator in word for indicator in company_indicators):
                # Get company name (assume it's the previous 1-2 words + this word)
                start = max(0, i-2)
                company = ' '.join(words[start:i+1])
                if len(company) > 5:  # Avoid very short matches
                    entities['companies'].append(company)
        
        # Remove duplicates and limit results
        for key in entities:
            entities[key] = list(set(entities[key]))[:5]
        
        return entities
    
    async def process_rss_feeds(self, session):
        """
        Process all RSS feeds asynchronously.
        
        PURPOSE: Main RSS processing logic - fetches feeds, extracts content,
        filters by keywords, and structures results.
        
        WHY ASYNC: RSS feeds can be slow to fetch, so process multiple
        feeds concurrently for better performance.
        
        WORKFLOW:
        1. Iterate through each RSS feed
        2. Parse RSS XML
        3. Check each entry for keywords and recency
        4. Extract and clean content
        5. Generate summaries and extract entities
        6. Store results and mark as processed
        """
        items = []
        
        for feed in self.feeds:
            if feed.get('type') != 'rss':
                continue  # Skip non-RSS feeds
                
            print(f"📡 Processing: {feed['title']}")
            
            try:
                # Use feedparser library to handle RSS complexity
                parsed_feed = feedparser.parse(feed['url'])
                
                # Process each entry in the feed
                for entry in parsed_feed.entries[:50]:  # Limit entries per feed
                    entry_url = entry.get('link', '')
                    
                    # Skip if already processed or no URL
                    if not entry_url or entry_url in self.processed_items:
                        continue
                    
                    # Skip if too old
                    if not self.is_recent(entry):
                        continue
                    
                    # Extract basic info
                    title = entry.get('title', '')
                    content = self.extract_content(entry)
                    
                    # Check for keyword matches
                    has_keywords, matched_keywords = self.contains_keywords(f"{title} {content}")
                    
                    if has_keywords:
                        # Generate summary focusing on keywords
                        summary = self.generate_summary(content, title, matched_keywords)
                        
                        # Extract structured entities
                        entities = self.extract_entities(f"{title} {content}")
                        
                        # Store the processed item
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
                        
                        # Mark as processed to avoid duplicates
                        self.processed_items[entry_url] = datetime.now().isoformat()
                
                # Rate limiting to be nice to RSS servers
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"⚠️  Error processing {feed['title']}: {e}")
        
        return items
    
    async def process_all_sources(self):
        """
        Main orchestrator - processes all intelligence sources.
        
        PURPOSE: Coordinate the processing of RSS feeds and other sources.
        
        WHY ASYNC: Some sources are slow, so process them concurrently.
        
        WORKFLOW:
        1. Create HTTP session for efficient connection reuse
        2. Process RSS feeds
        3. Process other sources 
        4. Combine all results
        5. Save processing history
        """
        print(f"🚀 Starting intelligence collection...")
        
        all_items = []
        
        # Create HTTP session with timeout
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Process RSS feeds
            rss_items = await self.process_rss_feeds(session)
            all_items.extend(rss_items)
            
            # Process Federal Register (if keywords specified)
            #if self.keywords:
            #    fed_items = await self.fetch_federal_register(session)
            #    all_items.extend(fed_items)
        
        # Store results in instance variable
        for item in all_items:
            self.results[item['id']] = item
        
        # Save processing history for next run
        self.save_history()
        
        print(f"✅ Collected {len(all_items)} intelligence items")
        return len(all_items)
    
    def generate_intelligence_report(self):
        """
        Generate comprehensive HTML intelligence report.
        
        PURPOSE: Create a readable, formatted report of all findings.
        
        WHY HTML: Rich formatting, can include links, easy to view and share.
        
        WORKFLOW:
        1. Sort results by date
        2. Generate statistics
        3. Create HTML content
        4. Save to file
        """
        if not self.results:
            print("📭 No intelligence items found")
            return None
        
        # Create timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        report_path = os.path.join(self.output_dir, f"intelligence_{timestamp}.html")
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Sort by date (newest first)
        sorted_items = sorted(
            self.results.values(),
            key=lambda x: x.get('date', ''),
            reverse=True
        )
        
        # Generate summary statistics
        stats = self.generate_stats(sorted_items)
        
        # Create HTML content
        html = self.generate_html_content(sorted_items, stats, timestamp)
        
        # Write to file
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"📊 Intelligence report generated: {report_path}")
        return report_path
    
    def generate_stats(self, items):
        """
        Generate summary statistics for the report.
        
        PURPOSE: Provide overview metrics to help users understand
        the scope and nature of findings.
        
        METRICS:
        - Total items found
        - Breakdown by source type
        - Keyword frequency
        - Companies & agencies mentioned
        - Dollar amounts found
        """
        stats = {
            'total_items': len(items),
            'source_breakdown': {},
            'keyword_frequency': {},
            'agencies_mentioned': set(),
            'companies_mentioned': set(),
            'total_amounts': []
        }
        
        # Count items by source type
        for item in items:
            source_type = item.get('source_type', 'unknown')
            stats['source_breakdown'][source_type] = stats['source_breakdown'].get(source_type, 0) + 1
        
        # Count keyword frequency
        for item in items:
            for keyword in item.get('keywords', []):
                stats['keyword_frequency'][keyword] = stats['keyword_frequency'].get(keyword, 0) + 1
        
        # Collect agencies and amounts mentioned
        for item in items:
            entities = item.get('entities', {})
            if entities.get('agencies'):
                stats['agencies_mentioned'].update(entities['agencies'])
            if entities.get('companies'):
                stats['agencies_mentioned'].update(entities['companies'])    
            if entities.get('amounts'):
                stats['total_amounts'].extend(entities['amounts'])
        
        return stats
    
    def generate_html_content(self, items, stats, timestamp):
        """
        Generate the complete HTML content for the report.
        
        PURPOSE: Create formatted, styled HTML report with all findings.
        
        STRUCTURE:
        1. Header with metadata
        2. Statistics dashboard
        3. Individual item details
        
        WHY INLINE CSS: Self-contained file, easier to share.
        """
        # HTML header with embedded CSS
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Intelligence Report - {timestamp}</title>
    <style>
        /* Modern, clean styling for the intelligence report */
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
        /* Grid layout for statistics cards */
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
        /* Individual intelligence item styling */
        .intelligence-item {{
            background: white;
            margin: 20px 0;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-left: 5px solid #3498db;
        }}
        /* Source type badges */
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
        /* Content sections */
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
        
        # Add source breakdown statistics
        for source_type, count in stats['source_breakdown'].items():
            html += f"""
        <div class="stat-card">
            <div class="stat-number">{count}</div>
            <div>{source_type.replace('_', ' ').title()} Sources</div>
        </div>
"""
        
        # Add top keyword statistic
        if stats['keyword_frequency']:
            top_keyword = max(stats['keyword_frequency'].items(), key=lambda x: x[1])
            html += f"""
        <div class="stat-card">
            <div class="stat-number">{top_keyword[1]}</div>
            <div>Top Keyword: {top_keyword[0]}</div>
        </div>
"""
        
        # Main content section
        html += """
    </div>
    
    <div class="intelligence-items">
        <h2>📋 Intelligence Items</h2>
"""
        
        # Add items or no-results message
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
        
        # Close HTML
        html += """
    </div>
</body>
</html>
"""
        return html
    
    def generate_item_html(self, item, index):
        """
        Generate HTML for a single intelligence item.
        
        PURPOSE: Format individual findings with all relevant information.
        
        INCLUDES:
        - Title and link
        - Source badge
        - Summary
        - Keywords found
        - Entities extracted
        - Metadata
        """
        source_type = item.get('source_type', 'unknown')
        
        html = f"""
        <div class="intelligence-item">
            <h3>{index}. <a href="{item.get('url', '#')}" target="_blank">{item.get('title', 'Untitled')}</a></h3>
            
            <span class="source-badge source-{source_type}">{source_type.replace('_', ' ').title()}</span>
"""
        
        # Add summary section
        if item.get('summary'):
            html += f"""
            <div class="summary">
                <strong>📝 Summary:</strong><br>
                {item['summary'].replace('\\n', '<br>')}
            </div>
"""
        
        # Add keywords section
        if item.get('keywords'):
            html += f"""
            <div class="keywords">
                <strong>🎯 Keywords:</strong>
                {' '.join([f'<span class="keyword">{kw}</span>' for kw in item['keywords']])}
            </div>
"""
        
        # Add entities section
        entities = item.get('entities', {})
        if any(entities.values()):
            html += '<div class="entities"><strong>🏢 Entities:</strong><br>'
            
            if entities.get('agencies'):
                html += f"<strong>Agencies:</strong> {', '.join(entities['agencies'][:3])}<br>"
            
            if entities.get('amounts'):
                html += f"<strong>Amounts:</strong> {', '.join(entities['amounts'][:3])}<br>"
            
            if entities.get('companies'):
                html += f"<strong>Companies:</strong> {', '.join(entities['companies'][:3])}<br>"
                
            if entities.get('people'):
                html += f"<strong>People:</strong> {', '.join(entities['people'][:3])}<br>"
            
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
    """
    Main function - entry point for the application.
    
    PURPOSE: Handle command-line arguments and orchestrate the entire process.
    
    WORKFLOW:
    1. Parse command-line arguments
    2. Load keywords from file
    3. Initialize processor
    4. Parse RSS feeds
    5. Process all sources
    6. Generate report
    
    WHY MAIN FUNCTION: Clean separation between CLI handling and core logic.
    """
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(
        description="Enhanced Intelligence Processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 palantir_intelligence.py -k keywords.txt -f Reader_Feeds.opml -d 3
  python3 palantir_intelligence.py -k keywords.txt --gov -f Reader_Feeds.opml -d 3
        """
    )
    
    # Define command-line arguments
    parser.add_argument("--keywords", "-k", default="keywords.txt", help="Default keywords file")
    parser.add_argument("--feeds", "-f", default="Reader_Feeds.opml", help="Default OPML file")
    parser.add_argument("--output-dir", "-o", default="output", help="Output directory")
    parser.add_argument("--days-back", "-d", type=int, default=3, help="Days back to search")
    parser.add_argument("--gov", action="store_true", help="Include government sources")
    parser.add_argument("--reset", action="store_true", help="Reset processing history")
    
    args = parser.parse_args()
    
    # Load keywords from file
    keywords = []
    with open('keywords.txt', 'r', encoding='utf-8') as f:
        keywords = [line.strip() for line in f if line.strip()]
    
    # Initialize the intelligence processor
    processor = PalantirIntelligenceProcessor(
        opml_file='Reader_Feeds.opml',
        output_dir=args.output_dir,
        keywords=keywords,
        days_back=args.days_back
    )
    
    # Reset processing history if requested
    if args.reset and os.path.exists(processor.history_file):
        try:
            os.remove(processor.history_file)
            print("🔄 Processing history reset")
        except Exception as e:
            print(f"⚠️  Error resetting history: {e}")
    
    # Parse RSS feeds from OPML
    processor.parse_opml()
    
    # Run the main processing
    try:
        # Create and run async event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Process all sources
        items_found = loop.run_until_complete(processor.process_all_sources())
        
        # Generate report if items were found
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

# Entry point - only run if script is executed directly
if __name__ == "__main__":
    main()