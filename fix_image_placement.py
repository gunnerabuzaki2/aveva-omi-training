#!/usr/bin/env python3
"""Fix image placement: vision-analyze each image, match to text position, rewrite HTML.
This is the definitive fix for image-content mismatches."""

import json
import os
import re
import html as html_mod

LESSONS_DIR = '/mnt/d/Manuals/AVEVA/omi-lessons'
IMAGES_DIR = f'{LESSONS_DIR}/images'
REFERENCE_DIR = f'{LESSONS_DIR}/reference'
LESSONS_OUT = f'{LESSONS_DIR}/lessons'

# Vision descriptions from the complete.md - keyed by page number
# These were pre-analyzed and describe what each page's screenshot shows
VISION_CACHE = {}


def load_vision_cache():
    """Load vision descriptions from the complete.md reference."""
    global VISION_CACHE
    ref_file = '/home/eng_zaki/.hermes/skills/software-development/aveva-system-platform/references/aveva_system_platform_complete.md'
    with open(ref_file, 'r') as f:
        content = f.read()
    
    # Extract all VISION blocks with page numbers
    for m in re.finditer(r'### Page (\d+)\s*\(page_(\d+)\.(png|jpeg)\)\s*[—–-]\s*(.+?)(?=\]|$)', content, re.DOTALL):
        page_num = int(m.group(2))
        desc = m.group(4).strip()
        desc = re.sub(r'\n\s*', ' ', desc)
        # Clean up common prefixes
        desc = re.sub(r'^Section \d+[–—-]\s*\d+:\s*', '', desc)
        desc = re.sub(r'^Lab \d+[–—-]\s*', 'Lab: ', desc)
        desc = re.sub(r'\(\d+-\d+\)', '', desc).strip()
        VISION_CACHE[page_num] = desc
    
    print(f"Loaded {len(VISION_CACHE)} vision descriptions")


def extract_text_sections(content_md):
    """Extract text content split by page markers, with position tracking."""
    sections = []
    current_text = []
    current_page = 0
    
    for line in content_md.split('\n'):
        stripped = line.strip()
        
        # Page marker
        page_match = re.match(r'^--- Page (\d+) ---', stripped)
        if page_match:
            if current_text:
                sections.append({
                    'page': current_page,
                    'text': '\n'.join(current_text)
                })
            current_page = int(page_match.group(1))
            current_text = []
            continue
        
        # Skip VISION blocks
        if stripped.startswith('[VISION:'):
            while ']' not in stripped and current_text:
                pass  # skip multi-line
            continue
        if stripped.startswith(']'):
            continue
        
        # Skip watermarks
        if is_skippable(stripped):
            continue
        
        if stripped:
            current_text.append(stripped)
    
    if current_text:
        sections.append({
            'page': current_page,
            'text': '\n'.join(current_text)
        })
    
    return sections


def is_skippable(stripped):
    if not stripped:
        return True
    patterns = [
        r'^Do Not Copy$', r'^AVEVA[™TM].*$', r'^\d+-\d+$',
        r'^Module \d+ –', r'^Table of Contents$',
    ]
    for pat in patterns:
        if re.match(pat, stripped):
            return True
    return False


def get_text_keywords(text):
    """Extract meaningful keywords from text for matching."""
    # Remove common words and get meaningful terms
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                  'should', 'may', 'might', 'shall', 'can', 'to', 'of', 'in', 'for',
                  'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
                  'before', 'after', 'above', 'below', 'between', 'out', 'off', 'over',
                  'under', 'again', 'further', 'then', 'once', 'click', 'step', 'note',
                  'that', 'this', 'these', 'those', 'and', 'or', 'but', 'not', 'no',
                  'you', 'your', 'it', 'its', 'we', 'they', 'he', 'she', 'you will',
                  'select', 'right', 'left', 'see', 'below', 'above', 'shown', 'image'}
    
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    return set(w for w in words if w not in stop_words)


def find_best_position(img_desc, sections, after_page=0):
    """Find the best text position to place an image based on its description."""
    if not img_desc or not sections:
        return len(sections) - 1  # Default: last position
    
    img_keywords = get_text_keywords(img_desc)
    if not img_keywords:
        return len(sections) - 1
    
    best_score = -1
    best_idx = len(sections) - 1
    
    for i, section in enumerate(sections):
        if section['page'] < after_page:
            continue
        
        section_keywords = get_text_keywords(section['text'])
        # Calculate overlap
        overlap = len(img_keywords & section_keywords)
        if overlap > best_score:
            best_score = overlap
            best_idx = i
    
    return best_idx


def rebuild_lesson_html(lesson, content_md, images_for_lesson):
    """Rebuild a lesson HTML with correct image placement using vision descriptions."""
    # Get all images sorted
    page_imgs = {}
    for img_file in images_for_lesson:
        m = re.match(r'page_(\d+)_(\d+)\.(png|jpeg)', img_file)
        if m:
            p = int(m.group(1))
            if p not in page_imgs:
                page_imgs[p] = []
            page_imgs[p].append((int(m.group(2)), img_file))
    for p in page_imgs:
        page_imgs[p].sort()
    
    # Extract text sections
    sections = extract_text_sections(content_md)
    
    # Build image list with descriptions
    all_images = []
    for page_num in sorted(page_imgs.keys()):
        for _, img_file in page_imgs[page_num]:
            desc = VISION_CACHE.get(page_num, f'Page {page_num}')
            all_images.append({
                'file': img_file,
                'page': page_num,
                'desc': desc
            })
    
    # Find placement positions for each image
    placements = []
    last_page = 0
    for img in all_images:
        # Find best position based on description matching
        pos = find_best_position(img['desc'], sections, after_page=last_page)
        placements.append((pos, img))
        last_page = img['page']
    
    # Build HTML with images at correct positions
    html_parts = []
    current_section_idx = 0
    
    # Group images by position
    pos_images = {}
    for pos, img in placements:
        if pos not in pos_images:
            pos_images[pos] = []
        pos_images[pos].append(img)
    
    # Interleave text and images
    for i, section in enumerate(sections):
        # Output text for this section
        for line in section['text'].split('\n'):
            stripped = line.strip()
            if stripped:
                html_parts.append(format_line(stripped))
        
        # Output images placed at this position
        if i in pos_images:
            for img in pos_images[i]:
                caption = img['desc']
                # Clean caption
                caption = re.sub(r'Screenshot \d+\s*[—–-]\s*', '', caption)
                caption = re.sub(r'^Step \d+\s*[—–-]\s*', '', caption)
                if not caption or len(caption) < 5:
                    caption = f'Page {img["page"]}'
                html_parts.append(make_img_html(img['file'], caption))
    
    # Add any remaining images at the end
    remaining = [img for pos, img in placements if pos >= len(sections)]
    for img in remaining:
        caption = img['desc'] or f'Page {img["page"]}'
        html_parts.append(make_img_html(img['file'], caption))
    
    return '\n'.join(html_parts)


def format_line(text):
    if not text:
        return ''
    
    # Headers
    if text.startswith('#### '):
        return f'<h4>{html_mod.escape(text[5:].strip())}</h4>'
    if text.startswith('### '):
        return f'<h3>{html_mod.escape(text[4:].strip())}</h3>'
    if text.startswith('## '):
        return f'<h2>{html_mod.escape(text[3:].strip())}</h2>'
    if text.startswith('# '):
        return f'<h1>{html_mod.escape(text[2:].strip())}</h1>'
    
    # Bold/italic/code
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    
    # Bullets
    if re.match(r'^[-*•]\s', text):
        return f'<p>• {text[1:].strip()}</p>'
    
    # Numbered lists
    num_match = re.match(r'^(\d+)\.\s*(.+)', text)
    if num_match:
        return f'<p><strong>{num_match.group(1)}.</strong> {num_match.group(2)}</p>'
    
    # Note/Tip
    if text.startswith('Note:') or text.startswith('Tip:'):
        cls = 'tip' if text.startswith('Tip:') else 'key-concept'
        return f'<div class="{cls}">{html_mod.escape(text)}</div>'
    
    return f'<p>{text}</p>'


def make_img_html(img_file, caption):
    alt = html_mod.escape(caption[:80]) if caption else 'Screenshot'
    cap = html_mod.escape(caption) if caption else ''
    return f'<div class="screenshot">\n  <img src="../images/{img_file}" alt="{alt}">\n  <div class="caption">{cap}</div>\n</div>'


# CSS and nav from v3
CSS = """  body { font-family: Georgia, serif; max-width: 900px; margin: 2em auto; padding: 0 1em; line-height: 1.7; color: #1a1a1a; }
  h1 { font-size: 1.8em; border-bottom: 2px solid #333; padding-bottom: 0.3em; }
  h2 { font-size: 1.3em; color: #2c5f2d; margin-top: 1.5em; }
  h3 { font-size: 1.1em; color: #555; }
  .key-concept { background: #f0f7f0; border-left: 4px solid #2c5f2d; padding: 1em; margin: 1em 0; }
  .pitfall { background: #fff3f3; border-left: 4px solid #c0392b; padding: 1em; margin: 1em 0; }
  .lab { background: #f0f4ff; border-left: 4px solid #2c3e50; padding: 1em; margin: 1em 0; }
  .tip { background: #fffde7; border-left: 4px solid #f39c12; padding: 1em; margin: 1em 0; }
  table { border-collapse: collapse; width: 100%; margin: 1em 0; }
  th, td { border: 1px solid #ddd; padding: 0.5em; text-align: left; }
  th { background: #f5f5f5; }
  code { background: #f4f4f4; padding: 0.1em 0.4em; font-size: 0.95em; }
  .screenshot { text-align: center; margin: 1.5em 0; }
  .screenshot img { max-width: 100%; border: 1px solid #ccc; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
  .screenshot .caption { font-size: 0.85em; color: #666; font-style: italic; margin-top: 0.5em; }
  .quiz { background: #fffde7; border: 1px solid #f0e68c; padding: 1em; margin: 2em 0; }
  .quiz h3 { margin-top: 0; }
  .answer { color: #2c5f2d; font-weight: bold; }
  nav { margin-bottom: 2em; font-size: 0.9em; }
  nav a { color: #2c5f2d; }
  .source { font-size: 0.85em; color: #777; font-style: italic; }
  .checkbox-label { cursor: pointer; }
  .checkbox-label input { margin-right: 0.3em; }
  #progress-text { color: #2c5f2d; font-weight: bold; }"""

PROGRESS_JS = """
<script>
function saveProgress() {
  document.querySelectorAll('input[data-lesson]').forEach(cb => {
    localStorage.setItem('omi_' + cb.dataset.lesson, cb.checked ? '1' : '0');
  });
  updateProgressText();
}
function loadProgress() {
  document.querySelectorAll('input[data-lesson]').forEach(cb => {
    cb.checked = localStorage.getItem('omi_' + cb.dataset.lesson) === '1';
  });
  updateProgressText();
}
function updateProgressText() {
  var total = document.querySelectorAll('input[data-lesson]').length;
  var done = document.querySelectorAll('input[data-lesson]:checked').length;
  var el = document.getElementById('progress-text');
  if (el) el.textContent = done + ' / ' + total + ' lessons completed';
}
window.addEventListener('load', loadProgress);
</script>"""


def build_nav(lessons, current_idx):
    current = lessons[current_idx]
    prev_l = lessons[current_idx - 1] if current_idx > 0 else None
    next_l = lessons[current_idx + 1] if current_idx < len(lessons) - 1 else None
    
    nav_top = '<nav>\n'
    if current_idx == 0:
        nav_top += '  <a href="../index.html">← Home</a> &nbsp;|&nbsp;\n'
    else:
        t = html_mod.escape(prev_l["title"][:40])
        nav_top += f'  <a href="{prev_l["filename"]}">← {prev_l["id"]}: {t}</a> &nbsp;|&nbsp;\n'
    if current_idx < len(lessons) - 1:
        t = html_mod.escape(next_l["title"][:40])
        nav_top += f'  <a href="{next_l["filename"]}">{next_l["id"]}: {t} →</a>\n'
    else:
        nav_top += '  <a href="../index.html">Home →</a>\n'
    nav_top += '</nav>\n\n'
    
    nav_drop = '<nav style="margin-bottom:1.5em;">\n'
    nav_drop += '<summary style="cursor:pointer;font-weight:bold;font-size:1.1em;color:#2c5f2d;">📚 All Lessons</summary>\n'
    nav_drop += '<div style="margin-top:0.8em;line-height:2;">\n'
    
    current_mod = 0
    for l in lessons:
        if l['mod'] != current_mod:
            current_mod = l['mod']
            if l['mod'] > 1:
                nav_drop += '<br>\n'
            nav_drop += f'<strong>Module {l["mod"]} — {html_mod.escape(l["mod_title"])}</strong><br>\n'
        active = ' style="font-weight:bold;color:#1a1a1a;"' if l['id'] == current['id'] else ''
        t = html_mod.escape(l["title"][:50])
        nav_drop += f'<label style="cursor:pointer;"><input type="checkbox" data-lesson="{l["id"]}" onchange="saveProgress()"> <a href="{l["filename"]}"{active}>{l["id"]}: {t}</a></label><br>\n'
    
    nav_drop += f'<br><span id="progress-text"></span>\n</div>\n</nav>\n\n'
    return nav_top + nav_drop


def main():
    load_vision_cache()
    
    os.makedirs(LESSONS_OUT, exist_ok=True)
    
    with open(f'{LESSONS_DIR}/lesson_plan.json', 'r') as f:
        lessons = json.load(f)
    
    for l in lessons:
        title_slug = l['title'].replace('–', '-').replace('—', '-')
        title_slug = re.sub(r'[^\w\s-]', '', title_slug)
        title_slug = re.sub(r'\s+', '-', title_slug.strip())
        title_slug = title_slug[:50].rstrip('-')
        l['filename'] = f'{l["id"]}-{title_slug}.html'
    
    for idx, lesson in enumerate(lessons):
        with open(f"{REFERENCE_DIR}/{lesson['id']}_content.md", 'r') as f:
            content_md = f.read()
        
        body_html = rebuild_lesson_html(lesson, content_md, lesson.get('images', []))
        
        nav = build_nav(lessons, idx)
        is_lab = 'Lab' in lesson['title']
        icon = '🔬' if is_lab else '📖'
        title_esc = html_mod.escape(lesson["title"])
        mod_esc = html_mod.escape(lesson["mod_title"])
        
        quiz = '<div class="quiz"><h3>Knowledge Check</h3><details><summary>Q1: What are the main concepts?</summary><p class="answer">Review above.</p></details></div>'
        
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lesson {lesson["id"][1:]}: {title_esc}</title>
<style>{CSS}</style>
</head>
<body>
{nav}
<h1>{icon} {lesson["id"]}: {title_esc}</h1>
<p class="source">Module {lesson["mod"]} — {mod_esc} | Pages {lesson["pages"]}</p>
{body_html}
{quiz}
<nav style="margin-top:2em; border-top:1px solid #ddd; padding-top:1em;">
'''
        if idx > 0:
            prev = lessons[idx - 1]
            t = html_mod.escape(prev["title"][:40])
            html += f'  <a href="{prev["filename"]}">← {prev["id"]}: {t}</a> &nbsp;|&nbsp;\n'
        else:
            html += '  <a href="../index.html">← Home</a> &nbsp;|&nbsp;\n'
        if idx < len(lessons) - 1:
            nxt = lessons[idx + 1]
            t = html_mod.escape(nxt["title"][:40])
            html += f'  <a href="{nxt["filename"]}">{nxt["id"]}: {t} →</a>\n'
        else:
            html += '  <a href="../index.html">Home →</a>\n'
        html += f'</nav>\n{PROGRESS_JS}\n</body>\n</html>'
        
        with open(f"{LESSONS_OUT}/{lesson['filename']}", 'w') as f:
            f.write(html)
        print(f"Generated: {lesson['filename']} ({lesson['image_count']} images)")
    
    print(f"\n✓ Generated {len(lessons)} lessons with vision-based image placement")


if __name__ == '__main__':
    main()
