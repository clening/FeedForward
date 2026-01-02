# Quick Reference Card

## 🚀 Common Commands

### First Time Setup
```bash
cd /home/claude/article-automation
./setup.sh
nano .env  # Add your API key
```

### Daily Workflow

**1. Export from feedforward.py**
```bash
python3 export_to_json.py --pickle /path/to/processed_intelligence.pkl
```

**2. Process Articles**
```bash
# Test with 10 articles
python3 article_processor.py output/intelligence_results_*.json --test

# Process all articles
python3 article_processor.py output/intelligence_results_*.json
```

**3. Check Results**
```bash
ls -lh processed/
head -50 processed/First_Article.md
```

**4. Move to Obsidian**
```bash
cp processed/*.md /path/to/obsidian/Future\ Trends/Clippings/Unreviewed/
```

## 🔧 Troubleshooting

### Check API Key
```bash
grep ANTHROPIC_API_KEY .env
```

### View Latest Export
```bash
cat output/intelligence_results_*.json | jq '.total_items'
```

### Process Just One Article
```bash
python3 article_processor.py output/intelligence_results_*.json --limit 1
```

### Clean Up
```bash
rm -rf processed/*
rm -rf output/intelligence_results_*.json
```

## 📊 Check Stats

### Count Processed Articles
```bash
ls -1 processed/ | wc -l
```

### View Processing Summary
```bash
# Scroll to bottom of output
python3 article_processor.py <file> | tail -20
```

### Check File Sizes
```bash
du -sh processed/
```

## 🎯 Useful Filters

### Find Long Summaries
```bash
for f in processed/*.md; do 
  lines=$(wc -l < "$f")
  if [ $lines -gt 200 ]; then
    echo "$f: $lines lines"
  fi
done
```

### Find Articles by Tag
```bash
grep -l "#surveillance" processed/*.md
```

### Count Tags
```bash
grep -h "tags:" processed/*.md | sort | uniq -c | sort -rn
```

## 💡 Tips

- **Test first**: Always use `--test` flag when trying new things
- **Small batches**: Process 10-20 articles at a time to avoid rate limits
- **Check costs**: Monitor Claude API usage at console.anthropic.com
- **Review carefully**: AI summaries are good but not perfect
- **Backup**: Keep original HTML output from feedforward.py

## 🔗 Important Paths

```
~/article-automation/           # This project
~/article-automation/output/    # feedforward.py exports
~/article-automation/processed/ # Ready for Obsidian
~/Obsidian/Future Trends/       # Your vault (adjust path)
```

## 🆘 Getting Help

1. Check README.md for detailed docs
2. Look at error messages carefully
3. Test with sample_input.json first
4. Reduce MAX_CONCURRENT_REQUESTS in .env if having issues
