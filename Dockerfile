FROM python:3.11-slim

WORKDIR /app

# 安装依赖环境（预留爬虫所需库）
RUN pip install --no-cache-dir requests beautifulsoup4 pandas

# 复制项目文件到容器内
COPY . /app/

# 设置环境变量，确保 Python 输出不被缓冲以便实时查看日志
ENV PYTHONUNBUFFERED=1

# 默认启动命令：运行探测引擎
CMD ["python", "engine.py"]
