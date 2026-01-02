#!/usr/bin/env python3
"""
Export feedforward.py results to JSON

This script reads the pickle file created by feedforward.py
and exports the results to JSON format that article_processor.py can use.
"""

import pickle
import json
import sys
import os
from datetime import datetime
from pathlib import Path

def export_to_json(pickle_file, output_dir="output"):
    """
    Read pickle file and export to JSON
    
    PARAMETERS:
    - pickle_file: Path to processed_intelligence.pkl
    - output_dir: Where to save the JSON
    """
    if not os.path.exists(pickle_file):
        print(f"❌ Pickle file not found: {pickle_file}")
        return None
    
    try:
        # Load pickle file
        with open(pickle_file, 'rb') as f:
            processed_items = pickle.load(f)
        
        print(f"📦 Loaded pickle file with {len(processed_items)} entries")
        
        # The pickle stores items with timestamps as keys
        # We need to extract the actual item data (the values)
        if isinstance(processed_items, dict):
            # Get the values from the dictionary (the actual article data)
            items = []
            for key, value in processed_items.items():
                # Skip if value is just a timestamp string
                if isinstance(value, dict):
                    items.append(value)
                else:
                    print(f"⚠️  Skipping non-dict item: {key}")
            print(f"✅ Extracted {len(items)} valid article items")
        else:
            items = processed_items
        
        # Create export data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_data = {
            "generated_at": datetime.now().isoformat(),
            "total_items": len(items),
            "items": items
        }
        
        # Save to JSON
        os.makedirs(output_dir, exist_ok=True)
        json_file = os.path.join(output_dir, f"intelligence_results_{timestamp}.json")
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Exported {len(items)} items to: {json_file}")
        return json_file
        
    except Exception as e:
        print(f"❌ Error exporting: {e}")
        return None


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Export feedforward results to JSON")
    parser.add_argument("--pickle", "-p", 
                       default="output/processed_intelligence.pkl",
                       help="Path to pickle file (default: output/processed_intelligence.pkl)")
    parser.add_argument("--output", "-o",
                       default="output",
                       help="Output directory (default: output)")
    
    args = parser.parse_args()
    
    json_file = export_to_json(args.pickle, args.output)
    
    if json_file:
        print(f"\n✅ Success! JSON file ready for article_processor.py")
        print(f"📝 Run: python3 article_processor.py {json_file} --test")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()