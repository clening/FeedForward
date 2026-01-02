#!/usr/bin/env python3
import argparse
import os
import sys
import re
import xml.etree.ElementTree as ET
import feedparser
from datetime import datetime, timedelta, timezone
# import json
from pathlib import Path
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from urllib.parse import urlparse
# import time
import pickle
import warnings
import dateutil.parser

# Suppress BeautifulSoup warning about content resembling a file path
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


class RSSProcessor:
    def __init__(self, opml_file, output_dir, keywords=None, days_back=1):
        """
        Initialize the RSS processor.
        
        Args:
            opml_file (str): Path to the OPML file containing RSS feeds
            output_dir (str): Directory to store downloaded content
            keywords (list): List of keywords to search for
            days_back (int): Number of days back to look for articles
        """
        self.opml_file = opml_file
        self.output_dir = output_dir
        self.keywords = keywords or []
        self.days_back = days_back
        self.feeds = []
        self.results = {}  # Now keyed by article URL instead of keyword
        self.history_file = os.path.join(output_dir, "processed_articles.pkl")
        self.processed_articles = self.load_article_history()
        
    def load_article_history(self):
        """Load previously processed articles to avoid duplicates."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"Error loading article history: {e}")
                return {}
        return {}
    
    def save_article_history(self):
        """Save processed articles to avoid duplicates in future runs."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            
            with open(self.history_file, 'wb') as f:
                pickle.dump(self.processed_articles, f)
            print(f"Saved article history to {self.history_file}")
        except Exception as e:
            print(f"Error saving article history: {e}")

    def parse_opml(self):
        """Parse the OPML file and extract feed URLs."""
        try:
            # Read the file and fix common XML issues
            with open(self.opml_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Fix unescaped ampersands in URLs
            fixed_content = re.sub(r'&(?!amp;|lt;|gt;|apos;|quot;)', '&amp;', content)
            
            # Parse the fixed content
            root = ET.fromstring(fixed_content)
            
            # Find all outline elements with xmlUrl attribute (RSS feeds)
            for outline in root.findall(".//outline[@xmlUrl]"):
                feed_title = outline.get("title", "Unnamed Feed")
                feed_url = outline.get("xmlUrl")
                
                if feed_url:
                    self.feeds.append({
                        "title": feed_title,
                        "url": feed_url
                    })
            
            print(f"Found {len(self.feeds)} feeds in the OPML file.")
        except Exception as e:
            print(f"Error parsing OPML file: {e}")
            sys.exit(1)

    def get_context(self, text, keyword, context_length=50):
        """
        Get the context around a keyword in text.
        
        Args:
            text (str): The text to search in
            keyword (str): The keyword to find
            context_length (int): Number of characters before and after the keyword
            
        Returns:
            str: Context snippet with the keyword highlighted
        """
        keyword_lower = keyword.lower()
        text_lower = text.lower()
        
        matches = []
        start = 0
        
        # Find all occurrences of the keyword
        while True:
            pos = text_lower.find(keyword_lower, start)
            if pos == -1:
                break
                
            # Get the context around the keyword
            context_start = max(0, pos - context_length)
            context_end = min(len(text), pos + len(keyword) + context_length)
            
            # Extract the actual text with original casing
            before = text[context_start:pos]
            keyword_actual = text[pos:pos+len(keyword)]
            after = text[pos+len(keyword):context_end]
            
            # Create a formatted context
            if context_start > 0:
                before = f"...{before}"
            if context_end < len(text):
                after = f"{after}..."
                
            context = f"{before}**{keyword_actual}**{after}"
            matches.append(context)
            
            # Move to the next position
            start = pos + len(keyword)
            
            # Limit to first 3 occurrences to keep the report manageable
            if len(matches) >= 3:
                break
                
        return matches
    
    def parse_datetime(self, date_str):
        """Parse date string from feed entry into datetime object with better handling of timezones."""
        if not date_str:
            return None
        
        try:
            # Use dateutil parser first for best compatibility
            parsed_date = dateutil.parser.parse(date_str)
            
            # Make timezone-aware if it isn't already
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                
            return parsed_date
            
        except Exception as e:
            # Try more specific parsing if dateutil fails
            try:
                # Common RSS timezone abbreviations replacements
                timezone_replacements = {
                    'EDT': '-0400',
                    'EST': '-0500',
                    'CDT': '-0500',
                    'CST': '-0600',
                    'MDT': '-0600',
                    'MST': '-0700',
                    'PDT': '-0700',
                    'PST': '-0800',
                    'GMT': '+0000',
                    'UTC': '+0000'
                }
                
                # Replace timezone abbreviations with their offsets
                for tz_abbr, tz_offset in timezone_replacements.items():
                    if tz_abbr in date_str:
                        date_str = date_str.replace(tz_abbr, tz_offset)
                
                # Try specific formats
                formats = [
                    '%a, %d %b %Y %H:%M:%S %z',  # RFC 822 format
                    '%Y-%m-%dT%H:%M:%S.%f%z',    # ISO 8601 with microseconds
                    '%Y-%m-%dT%H:%M:%S%z',       # ISO 8601
                    '%Y-%m-%dT%H:%M:%SZ',        # ISO 8601 UTC
                    '%Y-%m-%d %H:%M:%S',         # Simple format
                    '%Y-%m-%d',                  # Just date
                    '%d %b %Y',                  # Format like '15 Mar 2023'
                    '%B %d, %Y'                  # Format like 'March 15, 2023'
                ]
                
                for fmt in formats:
                    try:
                        parsed_date = datetime.strptime(date_str, fmt)
                        
                        # Make timezone-aware if it isn't already
                        if parsed_date.tzinfo is None:
                            if 'Z' in fmt:  # UTC time
                                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                            else:
                                parsed_date = parsed_date.replace(tzinfo=timezone.utc)  # Assume UTC if no timezone
                                
                        return parsed_date
                    except ValueError:
                        continue
            
            except Exception as nested_error:
                pass
        
        # If all parsing attempts failed
        print(f"Warning: Unable to parse date format: {date_str}")
        return None

    def is_recent_article(self, entry):
        """Check if the article is recent enough to process based on the days_back setting."""
        # Get the published date
        published_date = None
        
        # Try different possible date fields
        date_fields = ['published', 'pubDate', 'updated', 'created', 'date']
        
        for field in date_fields:
            if field in entry and entry[field]:
                published_date = self.parse_datetime(entry[field])
                if published_date:
                    break
        
        if not published_date:
            # If we can't determine the date, assume it's recent
            return True
        
        # Calculate the cutoff date (ensure it's timezone-aware)
        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=self.days_back)
        
        # Check if the article is newer than the cutoff date
        try:
            return published_date >= cutoff_date
        except TypeError as e:
            # Extra debug info if comparison fails
            print(f"Date comparison error: published={published_date}, cutoff={cutoff_date}")
            # Assume it's recent if we can't compare properly
            return True

    def download_feeds(self, max_entries_per_feed=50):
        """Download and process the content of each feed."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # Create a directory for the raw feed content
        raw_dir = os.path.join(self.output_dir, "raw")
        if not os.path.exists(raw_dir):
            os.makedirs(raw_dir)
        
        for feed in self.feeds:
            feed_title = feed["title"]
            feed_url = feed["url"]
            
            print(f"Processing feed: {feed_title}")
            
            try:
                # Parse the feed
                parsed_feed = feedparser.parse(feed_url)
                
                # Create a sanitized filename from the feed title
                safe_title = re.sub(r'[^\w\s-]', '', feed_title).strip().replace(' ', '_')
                
                # Save the raw feed content
                feed_dir = os.path.join(raw_dir, safe_title)
                if not os.path.exists(feed_dir):
                    os.makedirs(feed_dir)
                
                # Process each entry in the feed
                entry_count = 0
                for entry in parsed_feed.entries:
                    if entry_count >= max_entries_per_feed:
                        break
                    
                    # Extract entry information
                    entry_title = entry.get("title", "Untitled")
                    entry_link = entry.get("link", "")
                    
                    # Skip if we've seen this article before
                    if entry_link in self.processed_articles:
                        print(f"Skipping previously processed article: {entry_title}")
                        continue
                    
                    # Check if article is recent enough
                    if not self.is_recent_article(entry):
                        print(f"Skipping older article: {entry_title}")
                        continue
                    
                    # Mark this article as processed
                    self.processed_articles[entry_link] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Get entry date
                    entry_date = entry.get("published", 
                                entry.get("pubDate", 
                                entry.get("updated", 
                                entry.get("created", datetime.now().strftime("%Y-%m-%d")))))
                    
                    # Try to get the content
                    content = ""
                    if "content" in entry:
                        content = entry.content[0].value
                    elif "summary" in entry:
                        content = entry.summary
                    elif "description" in entry:
                        content = entry.description
                    
                    # Skip entries with empty content
                    if not content:
                        print(f"Skipping article with no content: {entry_title}")
                        continue
                    
                    # Clean the HTML content to get plain text
                    try:
                        soup = BeautifulSoup(content, "html.parser")
                        clean_content = soup.get_text(separator=' ', strip=True)
                    except Exception as e:
                        print(f"Error parsing content for {entry_title}: {e}")
                        clean_content = content  # Use raw content if parsing fails
                    
                    # Create a filename for this entry
                    safe_entry_title = re.sub(r'[^\w\s-]', '', entry_title).strip().replace(' ', '_')
                    entry_filename = f"{entry_count+1:02d}_{safe_entry_title[:50]}.txt"
                    entry_path = os.path.join(feed_dir, entry_filename)
                    
                    # Save the entry content
                    with open(entry_path, "w", encoding="utf-8") as f:
                        f.write(f"Title: {entry_title}\n")
                        f.write(f"Link: {entry_link}\n")
                        f.write(f"Date: {entry_date}\n")
                        f.write(f"Feed: {feed_title}\n")
                        f.write("\n")
                        f.write(clean_content)
                    
                    # Search for keywords
                    if self.keywords:
                        matched_keywords = []
                        keyword_contexts = {}
                        
                        for keyword in self.keywords:
                            combined_text = f"{entry_title} {clean_content}".lower()
                            if keyword.lower() in combined_text:
                                matched_keywords.append(keyword)
                                
                                # Get context snippets for the keyword
                                title_context = []
                                if keyword.lower() in entry_title.lower():
                                    title_context = self.get_context(entry_title, keyword)
                                
                                content_context = []
                                if keyword.lower() in clean_content.lower():
                                    content_context = self.get_context(clean_content, keyword)
                                
                                keyword_contexts[keyword] = {
                                    "title_context": title_context,
                                    "content_context": content_context
                                }
                        
                        # If any keywords matched, store the result by article URL
                        if matched_keywords:
                            self.results[entry_link] = {
                                "feed": feed_title,
                                "title": entry_title,
                                "link": entry_link,
                                "date": entry_date,
                                "file": entry_path,
                                "keywords": matched_keywords,
                                "keyword_contexts": keyword_contexts
                            }
                    
                    entry_count += 1
                
                print(f"Processed {entry_count} entries from {feed_title}")
                
            except Exception as e:
                print(f"Error processing feed {feed_title}: {e}")
        
        # Save the processed articles to avoid duplicates in future runs
        self.save_article_history()
    
    def generate_report(self):
        """Generate a report of the articles found with context and clickable links."""
        if not self.results:
            print("No keyword matches found.")
            return None, None
        
        # Generate both a text report and an HTML report for clickable links
        timestamp = datetime.now().strftime("%Y-%m-%d")
        text_report_path = os.path.join(self.output_dir, f"keyword_report_{timestamp}.txt")
        html_report_path = os.path.join(self.output_dir, f"keyword_report_{timestamp}.html")

        
        # Sort articles by date (newest first, if possible)
        # Use a custom sorting function with better error handling
        def safe_date_key(item):
            try:
                date_str = item[1]['date']
                parsed_date = self.parse_datetime(date_str)
                if parsed_date:
                    return parsed_date
                else:
                    # Default to current time if parsing fails
                    return datetime.now(timezone.utc)
            except:
                # Safety fallback
                return datetime.now(timezone.utc)
                
        sorted_results = sorted(
            self.results.items(),
            key=safe_date_key,
            reverse=True
        )
        
        # Generate text report
        with open(text_report_path, "w", encoding="utf-8") as f:
            f.write("Keyword Search Report\n")
            f.write("====================\n\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Keywords: {', '.join(self.keywords)}\n")
            f.write(f"Articles from the last {self.days_back} day(s)\n\n")
            
            f.write(f"Found {len(self.results)} matching articles\n\n")
            
            for url, article in sorted_results:
                f.write(f"Article: {article['title']}\n")
                f.write(f"Feed: {article['feed']}\n")
                f.write(f"Link: {article['link']}\n")
                f.write(f"Date: {article['date']}\n")
                f.write(f"Keywords: {', '.join(article['keywords'])}\n")
                f.write(f"File: {article['file']}\n\n")
                
                # Show contexts for each keyword
                for keyword in article['keywords']:
                    contexts = article['keyword_contexts'][keyword]
                    f.write(f"Keyword: {keyword}\n")
                    
                    if contexts['title_context']:
                        f.write("  Found in title:\n")
                        for ctx in contexts['title_context']:
                            f.write(f"  - {ctx}\n")
                    
                    if contexts['content_context']:
                        f.write("  Found in content:\n")
                        for ctx in contexts['content_context']:
                            f.write(f"  - {ctx}\n")
                    
                    f.write("\n")
                
                f.write("-" * 60 + "\n\n")
        
        # Generate HTML report with clickable links
        with open(html_report_path, "w", encoding="utf-8") as f:
            f.write("<!DOCTYPE html>\n")
            f.write("<html lang='en'>\n")
            f.write("<head>\n")
            f.write("  <meta charset='UTF-8'>\n")
            f.write("  <meta name='viewport' content='width=device-width, initial-scale=1.0'>\n")
            f.write(f"  <title>Keyword Search Report - {timestamp}</title>\n")
            f.write("  <style>\n")
            f.write("    body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }\n")
            f.write("    h1, h2, h3 { color: #333; }\n")
            f.write("    .keyword { color: #2c5aa0; font-weight: bold; }\n")
            f.write("    .match { margin-bottom: 30px; border-bottom: 1px solid #eee; padding-bottom: 15px; }\n")
            f.write("    .context { margin-left: 20px; background-color: #f9f9f9; padding: 10px; border-left: 3px solid #ddd; }\n")
            f.write("    .highlight { background-color: #ffff00; font-weight: bold; }\n")
            f.write("    a { color: #0066cc; text-decoration: none; }\n")
            f.write("    a:hover { text-decoration: underline; }\n")
            f.write("    .file-link { font-family: monospace; }\n")
            f.write("    .keyword-tag { display: inline-block; background-color: #e0f0ff; padding: 2px 8px; margin-right: 5px; border-radius: 12px; font-size: 0.9em; }\n")
            f.write("  </style>\n")
            f.write("</head>\n")
            f.write("<body>\n")
            f.write("  <h1>Keyword Search Report</h1>\n")
            f.write(f"  <p>Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>\n")
            f.write(f"  <p>Keywords: {', '.join(['<span class=\"keyword\">' + k + '</span>' for k in self.keywords])}</p>\n")
            f.write(f"  <p>Articles from the last {self.days_back} day(s)</p>\n")
            f.write(f"  <p>Found {len(self.results)} matching articles</p>\n")
            
            for i, (url, article) in enumerate(sorted_results):
                f.write(f'  <div class="match">\n')
                f.write(f'    <h2>{i+1}. <a href="{article["link"]}" target="_blank">{article["title"]}</a></h2>\n')
                
                # Display keywords as tags
                f.write('    <p>\n')
                for keyword in article['keywords']:
                    f.write(f'      <span class="keyword-tag">{keyword}</span>\n')
                f.write('    </p>\n')
                
                f.write(f'    <p>Feed: {article["feed"]}<br>\n')
                f.write(f'    Date: {article["date"]}<br>\n')
                f.write(f'    File: <span class="file-link">{article["file"]}</span></p>\n')
                
                # Add context snippets for each keyword
                for keyword in article['keywords']:
                    contexts = article['keyword_contexts'][keyword]
                    f.write(f'    <h3>Keyword: {keyword}</h3>\n')
                    
                    if contexts['title_context']:
                        f.write('    <p><strong>Found in title:</strong></p>\n')
                        f.write('    <div class="context">\n')
                        for ctx in contexts['title_context']:
                            # Replace ** markers with HTML highlight spans
                            html_ctx = re.sub(r'\*\*(.*?)\*\*', r'<span class="highlight">\1</span>', ctx)
                            f.write(f'      <p>{html_ctx}</p>\n')
                        f.write('    </div>\n')
                    
                    if contexts['content_context']:
                        f.write('    <p><strong>Found in content:</strong></p>\n')
                        f.write('    <div class="context">\n')
                        for ctx in contexts['content_context']:
                            # Replace ** markers with HTML highlight spans
                            html_ctx = re.sub(r'\*\*(.*?)\*\*', r'<span class="highlight">\1</span>', ctx)
                            f.write(f'      <p>{html_ctx}</p>\n')
                        f.write('    </div>\n')
                
                f.write('  </div>\n')
            
            f.write("</body>\n")
            f.write("</html>\n")
        
        print(f"Text report generated: {text_report_path}")
        print(f"HTML report with clickable links generated: {html_report_path}")
        
        return text_report_path, html_report_path

# Load up the Keywords.txt file
def load_keywords(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file if line.strip()]
    except Exception as e:
        print(f"Error loading keywords file: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description="Process RSS feeds from OPML and search for keywords. E.g.: python3 .\rss_feed_processor.py --f keywords.txt -op .\Reader_Feeds.opml -d 2")
    parser.add_argument("--opml_file", "-op", help="Path to the OPML file containing RSS feeds")
    parser.add_argument("--output-dir", "-o", default="feed_content", help="Directory to store downloaded content")
    parser.add_argument("--file", "-f", help="Path to a file containing keywords, one per line")
    parser.add_argument("--keywords", "-k", nargs="+", help="Keywords to search for in the feed content")
    parser.add_argument("--max-entries", "-m", type=int, default=10, help="Maximum entries to process per feed")
    parser.add_argument("--days-back", "-d", type=int, default=1, 
                        help="Number of days back to look for new articles (default: 1)")
    parser.add_argument("--reset-history", "-r", action="store_true", 
                        help="Reset article history (process all articles again)")
    args = parser.parse_args()
    
    # Collect keywords from both file and command line arguments
    keywords = []
    
    # Read keywords from file if provided
    if args.file:
        file_keywords = load_keywords(args.file)
        keywords.extend(file_keywords)
        print(f"Loaded {len(file_keywords)} keywords from file")
    
    # Add command line keywords if provided
    if args.keywords:
        keywords.extend(args.keywords)
    
    if not keywords:
        print("Warning: No keywords specified. Will download feeds but won't search for keywords.")
    
    # Initialize and run the processor
    processor = RSSProcessor(args.opml_file, args.output_dir, keywords, args.days_back)
    
    # Clear history if requested
    if args.reset_history and os.path.exists(processor.history_file):
        try:
            os.remove(processor.history_file)
            print("Article history reset. All articles will be processed again.")
        except Exception as e:
            print(f"Error resetting article history: {e}")
    
    processor.parse_opml()
    processor.download_feeds(args.max_entries)
    processor.generate_report()

if __name__ == "__main__":
    main()