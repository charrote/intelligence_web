"""API entry point - uses core.app.create_app factory."""

import os
import sys

# Add /app to Python path so 'core' module can be imported
sys.path.insert(0, '/app')

from core.domain import build_spec
from core.app import create_app

# Build domain spec
SPEC = build_spec(
    slug="intelligence_web",
    port=8766,
    title_prefix="情报管理系统",
    scout_label="制造情报采集",
    agent_names=["贾维斯", "美雪", "南希", "马格南"],
    theme_color="#722ed1",
    inbox_rel="../inbox/",
    db_filename="intelligence",
    domain_key="research",

    default_data_sources=[
        {"name": "智能制造产业联盟", "type": "website", "url": "https://www.afmii.org.cn",
         "indicators": ["政策解读", "标准发布", "行业动态"], "schedule": "daily"},
        {"name": "工业互联网产业联盟", "type": "website", "url": "https://www.iiot-aalliance.org",
         "indicators": ["技术白皮书", "案例分享", "行业报告"], "schedule": "weekly"},
        {"name": "制造工程科技网", "type": "website", "url": "https://www.manufacturing-technology.com",
         "indicators": ["新技术发布", "设备评测", "工艺创新"], "schedule": "daily"},
        {"name": "国际电工委员会 IEC", "type": "website", "url": "https://www.iec.ch",
         "indicators": ["标准更新", "技术报告", "合规要求"], "schedule": "weekly"},
        {"name": "智能制造标准体系", "type": "website", "url": "https://www.gb688.cn",
         "indicators": ["国家标准", "行业标准", "推荐性标准"], "schedule": "weekly"},
        {"name": "中国工业安全网", "type": "website", "url": "https://www.ciiis.org.cn",
         "indicators": ["安全事件", "合规通报", "防护指南"], "schedule": "daily"},
        {"name": "Industrial IoT News", "type": "website", "url": "https://www.iiot-world.com",
         "indicators": ["IoT案例", "传感器技术", "边缘计算"], "schedule": "daily"},
        {"name": "自动化杂志社", "type": "website", "url": "https://www.automation.org.cn",
         "indicators": ["PLC技术", "SCADA系统", "DCS应用"], "schedule": "weekly"},
        {"name": "质量工程协会", "type": "website", "url": "https://www.asq.org",
         "indicators": ["质量检测技术", "六西格玛", "SPC统计"], "schedule": "weekly"},
        {"name": "工信部政策法规", "type": "website", "url": "https://www.miit.gov.cn",
         "indicators": ["智能制造政策", "产业政策", "规划指南"], "schedule": "weekly"},
        {"name": "IEEE 工业互联网", "type": "website", "url": "https://ieeexplore.ieee.org/xpl/RecentIssue?punumber=6287",
         "indicators": ["论文", "技术趋势", "实验验证"], "schedule": "weekly"},
        {"name": "制造业数字化转型网", "type": "website", "url": "https://www.mfg-digital.com",
         "indicators": ["MES系统", "数字孪生", "数据采集"], "schedule": "daily"},
    ],
)

# Create app using factory
app = create_app("/app", SPEC)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8766, debug=True)