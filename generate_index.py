import os
from datetime import datetime

BASE_DIR = "/Users/Yoo/.openclaw/workspace/Intelligence_Web"
FOLDERS = {
    "Inbox": "Inbox",
    "Validated": "intelligene_web/Validated", # Note: following the user's typo in directory structure for consistency with their request if needed, but I will use actual paths. 
    # Wait, looking at my mkdir command: /Users/Yoo/.openclaw/workspace/Intelligence_Web/intelligene_web/Validated (typo 'intelligene')
    # User requested: intelligene_web/Validated (with typo). Let's check the actual folder names created.
}

def generate_index():
    # Re-calculating based on what I actually created in step 1
    paths = {
        "Inbox": "/Users/Yoo/.openclaw/workspace/Intelligence_Web/Inbox",
        "Validated": "/Users/Yoo/.openclaw/workspace/Intelligence_Web/intelligene_web/Validated",
        "Distilling": "/Users/Yoo/.openclaw/workspace/Intelligence_Web/intelligence_web/Distilling"
    }
    
    index_content = [f"# Intelligence Web Portal\n*Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"]
    
    for label, path in paths.items():
        index_content.append(f"## {label}")
        if not os.path.exists(path):
            index_content.append("_No items found._")
            continue
            
        files = [f for f in os.listdir(path) if f.endswith('.md')]
        if not files:
            index_content.append("_No items found._")
        else:
            for file in sorted(files):
                # Extract metadata from the file content to show status/date properly 
                # (Simple version: just list them, but let's try to read the date)
                filepath = os.path.join(path, file)
                try:
                    with open(filepath, 'r') as f:
                        first_line = f.readline() # Title
                        index_content.append(f"- [{file}]({file})") 
                except:
                    index_content.append(f"- {file}")

    with open(os.path.join(BASE_DIR, "Index.md"), 'w') as f:
        f.write("\n".join(index_content))

if __name__ == "__main__":
    generate_index()
