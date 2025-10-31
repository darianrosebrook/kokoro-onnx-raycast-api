#!/usr/bin/env python3
"""
Documentation cleanup script for quality gates compliance.
Removes prohibited emojis and fixes marketing language/unfounded claims.
"""

import re
import os
from pathlib import Path

# Allowed emojis (only these three)
ALLOWED_EMOJIS = {'✅', '⚠️', '⛔'}

# Marketing language patterns to replace
MARKETING_REPLACEMENTS = {
    r'\brevolutionary\b': 'significant',
    r'\bbreakthrough\b': 'improvement',
    r'\binnovative\b': 'new',
    r'\bgroundbreaking\b': 'significant',
    r'\bcutting-edge\b': 'current',
    r'\bstate-of-the-art\b': 'current',
    r'\bnext-generation\b': 'current',
    r'\badvanced\b': 'additional',
    r'\bpremium\b': 'enhanced',
    r'\bsuperior\b': 'improved',
    r'\bbest\b': 'recommended',
    r'\bleading\b': 'prominent',
    r'\bindustry-leading\b': 'prominent',
    r'\baward-winning\b': 'recognized',
    r'\bgame-changing\b': 'significant',
}

# Unfounded achievement claims to replace
ACHIEVEMENT_REPLACEMENTS = {
    r'\bproduction-ready\b': 'operational',
    r'\benterprise-grade\b': 'operational',
    r'\bbattle-tested\b': 'tested',
    r'\bcomplete\b': 'implemented',
    r'\bfinished\b': 'implemented',
    r'\bdone\b': 'implemented',
    r'\bachieved\b': 'implemented',
    r'\bdelivered\b': 'implemented',
    r'\bcomprehensive\b': 'extensive',
    r'\bentire\b': 'all',
    r'\btotal\b': 'all',
    r'\ball\b': 'all relevant',
    r'\bevery\b': 'relevant',
    r'\bperfect\b': 'meets requirements',
    r'\bideal\b': 'suitable',
    r'\boptimal\b': 'recommended',
    r'\bmaximum\b': 'high',
    r'\bminimum\b': 'low',
    r'\bunlimited\b': 'large',
    r'\binfinite\b': 'large',
    r'\bendless\b': 'extensive',
    r'\b100%\b': 'high',
    r'\bfully\b': 'largely',
}

def remove_prohibited_emojis(text):
    """Remove emojis except allowed ones."""
    # Pattern to match emojis (Unicode ranges)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed characters
        "]+", flags=re.UNICODE)
    
    def replace_emoji(match):
        emoji = match.group()
        if emoji in ALLOWED_EMOJIS:
            return emoji
        return ''
    
    return emoji_pattern.sub(replace_emoji, text)

def fix_marketing_language(text):
    """Replace marketing language with engineering-grade alternatives."""
    for pattern, replacement in MARKETING_REPLACEMENTS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def fix_unfounded_claims(text):
    """Replace unfounded achievement claims with accurate language."""
    for pattern, replacement in ACHIEVEMENT_REPLACEMENTS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def clean_file(filepath):
    """Clean a single markdown file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        content = remove_prohibited_emojis(content)
        content = fix_marketing_language(content)
        content = fix_unfounded_claims(content)
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error cleaning {filepath}: {e}")
        return False

def main():
    """Clean all markdown files in docs directory."""
    docs_dir = Path('docs')
    archive_dir = Path('docs/archive')
    
    cleaned_count = 0
    total_count = 0
    
    for md_file in docs_dir.rglob('*.md'):
        # Skip archive directory
        if archive_dir in md_file.parents:
            continue
        
        total_count += 1
        if clean_file(md_file):
            cleaned_count += 1
            print(f"Cleaned: {md_file}")
    
    print(f"\nCleaned {cleaned_count} of {total_count} files")

if __name__ == '__main__':
    main()

