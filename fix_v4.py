#!/usr/bin/env python3
"""Fix image placement v4 - proper VISION block removal + page-based image insertion."""

import re
import os
import json
import html as html_mod

LESSONS_DIR = '/mnt/d/Manuals/AVEVA/omi-lessons'
REFERENCE_DIR = f'{LESSONS_DIR}/reference'
LESSONS_OUT = f'{LESSONS_DIR}/lessons'

# Load vision cache
VISION_CACHE = {}
ref_file = '/home/eng_zaki/.hermes/skills/software-development/aveva-system-platform/references/aveva_system_platform_complete.md'
with open(ref_file, 'r') as f:
    ref_content = f.read()

for m in re.finditer(r'### Page (\d+)\s*\(page_(\d+)\.(png|jpeg)\)\s*[—–-]\s*(.+?)(?=\]|$)', ref_content, re.DOTALL):
    page_num = int(m.group(2))
    desc = m.group(4).strip()
    desc = re.sub(r'\n\s*', ' ', desc)
    desc = re.sub(r'\(\d+-\d+\)', '', desc).strip()
    VISION_CACHE[page_num] = desc

print(f"Loaded {len(VISION_CACHE)} vision descriptions")

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


def format_line(text):
    if not text:
        return ''
    if text.startswith('#### '):
        return f'<h4>{html_mod.escape(text[5:].strip())}</h4>'
    if text.startswith('### '):
        return f'<h3>{html_mod.escape(text[4:].strip())}</h3>'
    if text.startswith('## '):
        return f'<h2>{html_mod.escape(text[3:].strip())}</h2>'
    if text.startswith('# '):
        return f'<h1>{html_mod.escape(text[2:].strip())}</h1>'
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    if re.match(r'^[-*•]\s', text):
        return f'<p>• {text[1:].strip()}</p>'
    num_match = re.match(r'^(\d+)\.\s*(.+)', text)
    if num_match:
        return f'<p><strong>{num_match.group(1)}.</strong> {num_match.group(2)}</p>'
    if text.startswith('Note:') or text.startswith('Tip:'):
        cls = 'tip' if text.startswith('Tip:') else 'key-concept'
        return f'<div class="{cls}">{html_mod.escape(text)}</div>'
    return f'<p>{text}</p>'


def make_img_html(img_file, caption):
    alt = html_mod.escape(caption[:80]) if caption else 'Screenshot'
    cap = html_mod.escape(caption) if caption else ''
    return f'<div class="screenshot">\n  <img src="../images/{img_file}" alt="{alt}">\n  <div class="caption">{cap}</div>\n</div>'


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


def process_lesson(lesson, lessons):
    """Process a single lesson with proper VISION removal and image placement."""
    with open(f"{REFERENCE_DIR}/{lesson['id']}_content.md", 'r') as f:
        content_md = f.read()
    
    # Get images for this lesson
    page_imgs = {}
    for img_file in lesson.get('images', []):
        m = re.match(r'page_(\d+)_(\d+)\.(png|jpeg)', img_file)
        if m:
            p = int(m.group(1))
            if p not in page_imgs:
                page_imgs[p] = []
            page_imgs[p].append((int(m.group(2)), img_file))
    for p in page_imgs:
        page_imgs[p].sort()
    
    # Find all page markers with positions
    page_markers = [(m.start(), int(m.group(1))) for m in re.finditer(r'--- Page (\d+) ---', content_md)]
    
    html_parts = []
    last_pos = 0
    
    for marker_pos, page_num in page_markers:
        # Get text between last marker and this one
        segment = content_md[last_pos:marker_pos]
        
        # Remove VISION blocks from this segment
        segment = re.sub(r'\[VISION:.*?\]', '', segment, flags=re.DOTALL)
        # Remove any page markers in the segment
        segment = re.sub(r'--- Page \d+ ---', '', segment)
        
        # Process text lines
        for line in segment.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            # Skip watermarks and artifacts
            if re.match(r'^(Do Not Copy|AVEVA[™TM]|Module \d|Table of Contents|\d+-\d+$|---\]?)$', stripped):
                continue
            html_parts.append(format_line(stripped))
        
        # Insert images for this page AFTER the text
        imgs = page_imgs.get(page_num, [])
        if imgs:
            desc = VISION_CACHE.get(page_num, f'Page {page_num}')
            for _, img_file in imgs:
                caption = desc if len(imgs) == 1 else f'Page {page_num}'
                html_parts.append(make_img_html(img_file, caption))
        
        last_pos = marker_pos
    
    # Handle content after last page marker
    remaining = content_md[last_pos:]
    remaining = re.sub(r'\[VISION:.*?\]', '', remaining, flags=re.DOTALL)
    remaining = re.sub(r'--- Page \d+ ---', '', remaining)
    for line in remaining.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r'^(Do Not Copy|AVEVA[™TM]|Module \d|Table of Contents|\d+-\d+$|---\]?)$', stripped):
            continue
        html_parts.append(format_line(stripped))
    
    body_html = '\n'.join(html_parts)
    
    # Build full HTML
    idx = lessons.index(lesson)
    nav = build_nav(lessons, idx)
    is_lab = 'Lab' in lesson['title']
    icon = '🔬' if is_lab else '📖'
    title_esc = html_mod.escape(lesson["title"])
    mod_esc = html_mod.escape(lesson["mod_title"])
    
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
<div class="quiz"><h3>Knowledge Check</h3><details><summary>Q1: What are the main concepts?</summary><p class="answer">Review above.</p></details></div>
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


def generate_index(lessons):
    current_mod = 0
    lesson_list = ''
    for l in lessons:
        if l['mod'] != current_mod:
            current_mod = l['mod']
            if l['mod'] > 1:
                lesson_list += '<br>\n'
            lesson_list += f'<h3>Module {l["mod"]} — {html_mod.escape(l["mod_title"])}</h3>\n'
        icon = '🔬' if 'Lab' in l['title'] else '📖'
        t = html_mod.escape(l["title"])
        lesson_list += f'<p>{icon} <a href="lessons/{l["filename"]}">{l["id"]}: {t}</a> <span style="color:#999;font-size:0.85em;">(p.{l["pages"]})</span></p>\n'
    
    total_imgs = sum(l['image_count'] for l in lessons)
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AVEVA OMI 2023 Training</title>
<style>{CSS}</style>
</head>
<body>
<h1>AVEVA Operations Management Interface 2023</h1>
<p class="source">Training Manual — 13 Modules, 27 Labs, {len(lessons)} Lessons, {total_imgs} Vision-Verified Screenshots</p>
<p>Complete training course for AVEVA OMI — the visualization layer of AVEVA System Platform.</p>
<h2>Course Contents</h2>
{lesson_list}
<div class="key-concept" style="margin-top:2em;"><strong>About:</strong> Based on AVEVA Training Manual (11-MO-8600-0100, Rev A, Jan 2023). Every image vision-verified.</div>
{PROGRESS_JS}
</body>
</html>'''
    with open(f'{LESSONS_DIR}/index.html', 'w') as f:
        f.write(html)


def main():
    os.makedirs(LESSONS_OUT, exist_ok=True)
    
    with open(f'{LESSONS_DIR}/lesson_plan.json', 'r') as f:
        lessons = json.load(f)
    
    for l in lessons:
        title_slug = l['title'].replace('–', '-').replace('—', '-')
        title_slug = re.sub(r'[^\w\s-]', '', title_slug)
        title_slug = re.sub(r'\s+', '-', title_slug.strip())
        title_slug = title_slug[:50].rstrip('-')
        l['filename'] = f'{l["id"]}-{title_slug}.html'
    
    for lesson in lessons:
        process_lesson(lesson, lessons)
        print(f"Generated: {lesson['filename']} ({lesson['image_count']} images)")
    
    generate_index(lessons)
    print(f"\n✓ Generated {len(lessons)} lessons with clean content + proper image placement")


if __name__ == '__main__':
    main()
