#!/usr/bin/env python3
"""
Intelligence Web — Slidev HTML 演示启动器

用法:
  python scripts/gen_slidev.py serve    # 启动本地开发服务器 (localhost:3030)
  python scripts/gen_slidev.py build    # 构建静态 HTML 到 docs/slidev-dist/
  python scripts/gen_slidev.py export   # 导出 PDF
"""
import subprocess
import sys
import re
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SLIDEV_DIR = PROJECT_ROOT / "docs" / "slidev"
SLIDEV_FILE = SLIDEV_DIR / "intelligence-web.md"
DIST_DIR = PROJECT_ROOT / "docs" / "slidev-dist"

def serve():
    """启动本地 HTTP 服务器"""
    print(f"🌐 启动 HTTP 服务器...")
    print(f"   目录: {DIST_DIR}")
    print(f"   访问: http://localhost:3030")
    print(f"   (按 Ctrl+C 停止)")
    print()

    import http.server
    import threading
    import webbrowser
    import os

    os.chdir(str(DIST_DIR))

    handler = http.server.SimpleHTTPRequestHandler

    server = http.server.HTTPServer(("0.0.0.0", 3030), handler)

    # 3 秒后自动打开浏览器
    def open_browser():
        import time
        time.sleep(3)
        webbrowser.open("http://localhost:3030")

    t = threading.Thread(target=open_browser, daemon=True)
    t.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
        server.shutdown()


def build():
    """构建静态 HTML"""
    print(f"📦 构建静态 HTML...")
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["slidev", "build", str(SLIDEV_FILE), "--out", str(DIST_DIR)],
        cwd=str(SLIDEV_DIR),
    )
    if result.returncode == 0:
        # 移除外部依赖（Google Fonts、CDN favicon），确保离线可用
        html_file = DIST_DIR / "index.html"
        content = html_file.read_text(encoding="utf-8")

        # 移除 Google Fonts
        content = re.sub(
            r'<link rel="stylesheet" href="https://fonts\.googleapis\.com[^"]*">',
            "",
            content,
        )

        # 替换 favicon 为内联 SVG
        content = content.replace(
            'href="https://cdn.jsdelivr.net/gh/slidevjs/slidev/assets/favicon.png"',
            'href="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22%3E%3Ctext y=%22.9em%22 font-size=%2290%22%3EIW%3C/text%3E%3C/svg%3E"',
        )

        # 移除构建后可能留下的空 link 标签
        content = re.sub(r'<link rel="stylesheet" +type="text/css">', "", content)

        html_file.write_text(content, encoding="utf-8")
        print(f"✅ 构建完成: {DIST_DIR}（已移除外部依赖，离线可用）")
        # 列出输出文件
        html_files = list(DIST_DIR.glob("*.html"))
        for f in html_files[:5]:
            print(f"   {f.name} ({f.stat().st_size / 1024:.0f} KB)")
    else:
        print(f"❌ 构建失败")
        sys.exit(1)


def export():
    """导出 PDF"""
    print(f"📄 导出 PDF...")
    output_pdf = PROJECT_ROOT / "docs" / "Intelligence_Web_Slidev.pdf"

    result = subprocess.run(
        ["slidev", "export", str(SLIDEV_FILE), str(output_pdf)],
        cwd=str(SLIDEV_DIR),
    )
    if result.returncode == 0:
        print(f"✅ PDF 已生成: {output_pdf}")
    else:
        print(f"❌ 导出失败（需要安装 Chromium）")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "serve":
        serve()
    elif cmd == "build":
        build()
    elif cmd == "export":
        export()
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()