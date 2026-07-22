#!/usr/bin/env python3
"""Convert Markdown contract spec to professional PDF."""

import sys
import os
import re
import markdown
from weasyprint import HTML

def md_to_html(md_text):
    """Convert markdown to styled HTML."""
    
    # Pre-process: convert markdown tables to HTML tables
    # WeasyPrint + markdown library handles this via 'tables' extension
    
    # Convert markdown to HTML with extensions
    html_body = markdown.markdown(
        md_text,
        extensions=[
            'markdown.extensions.tables',
            'markdown.extensions.fenced_code',
            'markdown.extensions.codehilite',
            'markdown.extensions.toc',
            'markdown.extensions.nl2br',
        ]
    )
    
    # Full HTML document with CSS
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
@page {{
    size: A4;
    margin: 2.5cm 2cm 2cm 2cm;
    @bottom-center {{
        content: "— " counter(page) " —";
        font-family: 'Noto Sans CJK SC', 'Noto Sans SC', sans-serif;
        font-size: 9pt;
        color: #888;
    }}
}}

body {{
    font-family: 'Noto Sans CJK SC', 'Noto Sans SC', 'AR PL UMing CN', sans-serif;
    font-size: 10.5pt;
    line-height: 1.7;
    color: #1a1a1a;
}}

/* Cover / Title */
h1 {{
    font-family: 'Noto Serif CJK SC', 'Noto Serif SC', serif;
    font-size: 22pt;
    color: #1a3a5c;
    text-align: center;
    margin-top: 3cm;
    margin-bottom: 0.5cm;
    padding-bottom: 0.5cm;
    border-bottom: 3px solid #1a3a5c;
}}

h1 + blockquote {{
    text-align: center;
    font-size: 10pt;
    color: #555;
    font-style: italic;
    margin: 0.5cm auto 1.5cm auto;
    max-width: 80%;
    border: none;
    padding: 0;
}}

/* Section headings */
h2 {{
    font-family: 'Noto Serif CJK SC', 'Noto Serif SC', serif;
    font-size: 16pt;
    color: #1a3a5c;
    margin-top: 1.5cm;
    margin-bottom: 0.5cm;
    padding-bottom: 0.3cm;
    border-bottom: 2px solid #3b7cb8;
    page-break-after: avoid;
}}

h3 {{
    font-family: 'Noto Sans CJK SC', 'Noto Sans SC', sans-serif;
    font-size: 12pt;
    color: #2b5a8c;
    margin-top: 0.8cm;
    margin-bottom: 0.3cm;
    page-break-after: avoid;
}}

h4 {{
    font-family: 'Noto Sans CJK SC', 'Noto Sans SC', sans-serif;
    font-size: 11pt;
    color: #3b6a9c;
    margin-top: 0.5cm;
    margin-bottom: 0.2cm;
}}

/* Tables */
table {{
    width: 100%;
    border-collapse: collapse;
    margin: 0.5cm 0;
    font-size: 9.5pt;
    page-break-inside: auto;
}}

thead {{
    display: table-header-group;
}}

tr {{
    page-break-inside: avoid;
}}

th {{
    background-color: #1a3a5c;
    color: white;
    font-weight: bold;
    padding: 6px 10px;
    text-align: left;
    border: 1px solid #1a3a5c;
    font-size: 9pt;
}}

td {{
    padding: 5px 10px;
    border: 1px solid #ddd;
    vertical-align: top;
}}

tr:nth-child(even) td {{
    background-color: #f7f9fc;
}}

/* Horizontal rules */
hr {{
    border: none;
    border-top: 1px solid #ccc;
    margin: 0.8cm 0;
}}

/* Blockquote (for contract header) */
blockquote {{
    border-left: 4px solid #1a3a5c;
    padding: 8px 15px;
    margin: 0.5cm 0;
    background: #f0f4f8;
    color: #333;
    font-size: 10pt;
}}

/* Lists */
ul, ol {{
    margin: 0.3cm 0;
    padding-left: 1.5em;
}}

li {{
    margin-bottom: 0.15cm;
}}

/* Code */
code {{
    font-family: 'Courier New', monospace;
    font-size: 9pt;
    background: #f4f4f4;
    padding: 1px 4px;
    border-radius: 2px;
}}

pre {{
    background: #f4f4f4;
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
    overflow-x: auto;
}}

/* Strong */
strong {{
    color: #1a3a5c;
}}

/* Signature page */
h2:last-of-type {{
    margin-top: 2cm;
}}

/* First page special: make the contract note not a blockquote visually */
h1 + blockquote {{
    border-left: none;
    background: none;
    padding: 0;
}}

/* Section 5 - 验收总表 table styling */
/* Make the demand matrix table compact */
</style>
</head>
<body>
{html_body}
</body>
</html>"""
    return html


def main():
    md_path = "/home/uantek/dev/Applications/intelligence_web/docs/领域需求/凯闻集团_需求规格书.md"
    pdf_path = "/home/uantek/dev/Applications/intelligence_web/docs/领域需求/凯闻集团_需求规格书.pdf"
    
    # Read markdown
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()
    
    print(f"Read {len(md_text)} chars from markdown")
    
    # Convert to HTML
    html = md_to_html(md_text)
    html_path = md_path.replace('.md', '.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"HTML written to {html_path}")
    
    # Generate PDF
    HTML(string=html).write_pdf(pdf_path)
    
    pdf_size = os.path.getsize(pdf_path)
    print(f"PDF generated: {pdf_path} ({pdf_size/1024:.1f} KB)")


if __name__ == '__main__':
    main()