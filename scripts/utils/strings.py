import re

def clean_name(name):
    if not name:
        return ""
    # Replace slashes and backslashes with underscores (filesystem safety)
    name = name.replace("/", "_").replace("\\", "_")
    # Replace colons with a space-dash (common for titles: subtitle)
    name = name.replace(":", " -")
    # Strip other Windows/Linux illegal characters: < > " | ? *
    name = re.sub(r'[<>\"|?*]', '', name)
    # Remove leading/trailing dots/spaces (problematic on Windows)
    name = name.strip(". ")
    # Replace multiple spaces with single space
    name = re.sub(r'\s+', ' ', name)
    return name.strip()

def clean_html(text):
    if not text:
        return ""
    
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Remove link attributes like {:target="_blank" ...}
    text = re.sub(r'\{:[^\}]+\}', '', text)
    
    # Strip bold markers (**text**, __text__)
    text = re.sub(r'(\*\*|__)', '', text)
    
    # Convert Markdown links [text](url) to "text (url)"
    # We do this BEFORE stripping single * or _ to avoid hitting URLs
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
    
    # Strip single italics markers (*text*, _text_) surgical to avoid URLs
    # This regex looks for * or _ that are NOT surrounded by non-whitespace (simplified)
    # But often it's safer to just remove them if they are at start/end of words
    text = re.sub(r'\b(_|\*)\b', '', text)
    
    # Strip Markdown headers (e.g., # Header)
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    
    # Remove backslash escapes (e.g., \_ -> _)
    text = re.sub(r'\\(.)', r'\1', text)
    
    # Replace common HTML block elements with newlines or spaces to avoid text joining
    text = re.sub(r'<(br|/br|br/)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    
    # Strip all remaining HTML tags
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)
    
    # Collapse 3 or more newlines into 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()
