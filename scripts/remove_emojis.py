#!/usr/bin/env python3
"""
Script to remove emojis from files while preserving specific ones (✅, ⛔, )
"""

import os
import re
import sys
from pathlib import Path

def remove_emojis_from_text(text):
    """
    Remove emojis from text while preserving ✅, ⛔, 
    """
    # Define emoji ranges and specific emojis to remove
    # Keep specific emojis: ✅, ⛔, 
    keep_emojis = {'✅', '⛔', ''}
    
    # Remove all emojis except the ones we want to keep
    cleaned_text = ""
    for char in text:
        if char in keep_emojis:
            cleaned_text += char
        elif is_emoji(char):
            continue  # Skip this emoji
        else:
            cleaned_text += char
    
    return cleaned_text

def is_emoji(char):
    """
    Check if a character is an emoji
    """
    # Unicode ranges for emojis
    emoji_ranges = [
        (0x1F600, 0x1F64F),  # Emoticons
        (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs
        (0x1F680, 0x1F6FF),  # Transport and Map
        (0x1F1E0, 0x1F1FF),  # Regional indicator symbols
        (0x2600, 0x26FF),    # Misc symbols
        (0x2700, 0x27BF),    # Dingbats
        (0xFE00, 0xFE0F),    # Variation Selectors
        (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
        (0x1F018, 0x1F0F5),  # Playing cards
        (0x1F200, 0x1F2FF),  # Enclosed characters
    ]
    
    code_point = ord(char)
    for start, end in emoji_ranges:
        if start <= code_point <= end:
            return True
    
    # Check for emoji modifiers and other emoji-related characters
    if (0x1F3FB <= code_point <= 0x1F3FF) or (0x1F9B0 <= code_point <= 0x1F9B3):
        return True
    
    return False

def process_file(file_path):
    """Process a single file to remove emojis"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        cleaned_content = remove_emojis_from_text(content)
        
        if cleaned_content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_content)
            print(f"✅ Processed: {file_path}")
            return True
        else:
            print(f"⏭  No changes needed: {file_path}")
            return False
            
    except Exception as e:
        print(f" Error processing {file_path}: {e}")
        return False

def main():
    """Main function to process all files"""
    project_root = Path(__file__).parent.parent
    
    # File extensions to process
    extensions = {'.py', '.ts', '.tsx', '.js', '.jsx', '.md', '.sh', '.json', '.txt'}
    
    # Directories to skip (third-party packages and build artifacts)
    skip_dirs = {
        '.git', '__pycache__', 'node_modules', '.next', 'dist', 'build',
        '.venv', 'venv', 'env', '.env',  # Python virtual environments
        '.pytest_cache', '.mypy_cache', '.coverage',  # Python tool caches
        'site-packages',  # Python packages
        '.tox', '.nox',  # Python testing environments
        'target', 'Cargo.lock',  # Rust
        '.gradle', 'build',  # Java/Gradle
        'vendor',  # Go/Composer
        '.bundle', 'Gemfile.lock',  # Ruby
        'bower_components',  # Bower
        'coverage', '.nyc_output',  # Coverage tools
        '.DS_Store', 'Thumbs.db',  # OS files
        'logs', 'tmp', 'temp'  # Temporary directories
    }
    
    processed_count = 0
    total_files = 0
    
    print(" Starting emoji removal process...")
    print(f" Project root: {project_root}")
    
    for file_path in project_root.rglob('*'):
        # Skip directories
        if file_path.is_dir():
            continue
            
        # Skip if in skip directories
        if any(skip_dir in file_path.parts for skip_dir in skip_dirs):
            continue
            
        # Skip if not a file we want to process
        if file_path.suffix not in extensions:
            continue
            
        total_files += 1
        
        if process_file(file_path):
            processed_count += 1
    
    print(f"\n Summary:")
    print(f"   Total files checked: {total_files}")
    print(f"   Files processed: {processed_count}")
    print(f"   Files unchanged: {total_files - processed_count}")

if __name__ == "__main__":
    main()
