# Enhanced RSS Keyword Parser
Monitors RSS feeds and government sources for data protection related content

## What it does
This script is an intelligence gathering system that:
1. Reads RSS feeds from an OPML file (defaults to Reader_Feeds.opml)
2. Filters content based on keywords from a provided text file (defaults to keywords.txt)
3. Generates HTML reports of relevant findings, including keywords, entities, amounts, etc.

## Users can customize the following parameters
        --feeds / -f   ### File containing RSS feed URLs (OPML format)
        --output_dir / -o   ### Where to save reports and history
        --keywords / -k  ### List of terms to search for
        --days_back / -d  ### How many days of historical data to process

## Examples        
        python3 makeitmakesense.py -k keywords.txt -f Reader_Feeds.opml -d 3 
        python3 makeitmakesense.py -k <your file> -f <yourfile>.opml -o /outputs -d 5

## Nifty features: 
 - You can easily add RSS feeds and customize keywords by tweaking the keywords/OPML lists accordingly.
 - Nice entity extraction feature that pulls out companies, government entities, funding amounts, and other elements.
 - Clean visiual interface to make skimming/review even easier.

## TODO
- Integration with Readwise or Obsidian?

