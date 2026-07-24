#!/usr/bin/env python3
"""
Intelligence Web — 苹果风格 PPT 配图生成器
使用 Agnes Image 2.1 Flash 生成高质量配图
"""

import json
import requests
import os

# Agnes AI 配置
AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"
AGNES_API_KEY = os.getenv("AGNES_API_KEY", "your-api-key-here")  # 需要从环境变量或配置获取

# 配图生成提示词
IMAGES = {
    "cover": "Minimalist tech illustration, abstract data flow visualization, clean lines, white background, Apple style design, soft gradients, blue and white color scheme, professional corporate image, high quality, 4K",
    "pain_points": "Abstract representation of information chaos, fragmented data streams, confused business people, modern illustration style, clean design, blue and gray tones, professional corporate art",
    "solution": "Clean minimalist platform interface mockup, data visualization dashboard, smooth flows, Apple design aesthetic, white space, soft shadows, blue accent, professional tech image",
    "ai_flywheel": "Circular flow diagram, human and AI collaboration, positive feedback loop, minimalist illustration, clean lines, green and blue gradients, modern tech art, white background",
    "manufacturing": "Modern manufacturing facility, Industry 4.0, smart factory, clean technology, minimalist style, blue and white tones, professional corporate photography style",
    "sales": "Sales team collaboration, data-driven decision making, pipeline visualization, modern office, clean design, blue accents, professional corporate image",
    "architecture": "Tech architecture diagram, clean lines, layered system design, minimalist illustration, blue and green tones, white background, professional tech art",
    "security": "Security shield icon, protection concept, lock and key, minimalist design, clean lines, blue and green tones, professional corporate image",
    "roi": "Financial growth chart, upward trend, positive numbers, clean minimalist design, green and blue accents, white background, professional business illustration",
    "closing": "Minimalist closing slide, clean design, white space, subtle gradient, professional corporate image, Apple style",
}

def generate_image(prompt, output_path, size="1024x1024"):
    """使用 Agnes Image 2.1 Flash 生成图片"""
    url = f"{AGNES_BASE_URL}/images/generations"
    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "agnes-image-2.1-flash",
        "prompt": prompt,
        "size": size,
        "n": 1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        if "data" in result and len(result["data"]) > 0:
            image_url = result["data"][0]["url"]
            # 下载图片
            img_response = requests.get(image_url, timeout=30)
            img_response.raise_for_status()
            
            with open(output_path, "wb") as f:
                f.write(img_response.content)
            print(f"✓ 已生成：{output_path}")
            return True
        else:
            print(f"✗ 生成失败：{result}")
            return False
    except Exception as e:
        print(f"✗ 生成错误：{e}")
        return False

def main():
    output_dir = "docs/images"
    os.makedirs(output_dir, exist_ok=True)
    
    generated = []
    for key, prompt in IMAGES.items():
        output_path = os.path.join(output_dir, f"{key}.png")
        if generate_image(prompt, output_path):
            generated.append(key)
    
    print(f"\n成功生成 {len(generated)}/{len(IMAGES)} 张图片")
    print(f"图片目录：{output_dir}/")
    
    # 保存生成记录
    with open(os.path.join(output_dir, "generated.json"), "w") as f:
        json.dump({
            "generated": generated,
            "total": len(IMAGES),
            "timestamp": "2026-07-24"
        }, f, indent=2)

if __name__ == "__main__":
    main()