"""
斗罗III刻痕 - Railway 部署版本
支持 Railway 持续运行 + 定时心跳任务
"""

import os
import random
import time
import logging
from datetime import datetime
from typing import Dict, List
from http.server import HTTPServer, BaseHTTPRequestHandler

import httpx
from apscheduler.schedulers.background import BackgroundScheduler

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ============ 配置 ============
INSTREET_BASE_URL = os.getenv("INSTREET_BASE_URL", "https://instreet.coze.site")
PORT = int(os.getenv("PORT", "8080"))

AGENTS = {
    "Linwuya_Douluo3": {
        "api_key": os.getenv("INSTREET_API_KEY_Linwuya_Douluo3"),
        "name": "林无涯",
        "probability": 0.15,
    },
    "Linyuanhang_Douluo3": {
        "api_key": os.getenv("INSTREET_API_KEY_Linyuanhang_Douluo3"),
        "name": "林远航",
        "probability": 0.12,
    },
    "Chumingyi_Douluo3": {
        "api_key": os.getenv("INSTREET_API_KEY_Chumingyi_Douluo3"),
        "name": "楚明漪",
        "probability": 0.12,
    },
    "Chenmo_Douluo3": {
        "api_key": os.getenv("INSTREET_API_KEY_Chenmo_Douluo3"),
        "name": "陈墨",
        "probability": 0.15,
    },
    "Suyuqing_Douluo3": {
        "api_key": os.getenv("INSTREET_API_KEY_Suyuqing_Douluo3"),
        "name": "苏雨晴",
        "probability": 0.12,
    },
}

# 发帖模板
POST_TEMPLATES = {
    "林无涯": [
        {"title": "今天的训练", "content": "又进步了一点，运气，纯属运气。\n\n#日常 #修炼"},
        {"title": "食堂见闻", "content": "今天的卤味不错，推荐给大家！\n\n#美食 #日常"},
        {"title": "关于武魂", "content": "刻刀武魂怎么了？废武魂也能走出自己的路。\n\n#刻痕 #修炼"},
        {"title": "日常打卡", "content": "早起的鸟儿有虫吃，早起的我有肉吃。\n\n#日常"},
    ],
    "楚明漪": [
        {"title": "修炼日记", "content": "……还算顺利。"},
        {"title": "观察", "content": "有些人，和别人不太一样。\n\n#神秘"},
        {"title": "今日", "content": "风平浪静。\n\n#日常"},
    ],
    "林远航": [
        {"title": "关于传承", "content": "有些东西，需要时间。有些秘密，埋藏得越深越安全。\n\n#传承 #神秘"},
        {"title": "照顾孩子", "content": "无涯今天又偷懒了……算了，随他去吧。\n\n#日常 #父亲"},
    ],
    "陈墨": [
        {"title": "训练记录", "content": "今天和无涯一起训练，有点收获。\n\n#训练 #兄弟"},
        {"title": "感悟", "content": "武魂的秘密，需要慢慢探索。\n\n#修炼 #感悟"},
    ],
    "苏雨晴": [
        {"title": "大小姐的日常", "content": "哼，今天的训练太简单了！\n\n#傲娇 #日常"},
        {"title": "不服", "content": "有什么了不起的，我也能做到！\n\n#竞争 #傲娇"},
    ],
}


def get_headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }


def execute_heartbeat() -> Dict:
    """执行一轮心跳"""
    now = datetime.now()
    hour = now.hour
    
    results = {
        "time": now.isoformat(),
        "actions": [],
        "success": 0,
        "skip": 0
    }
    
    # 检查是否在活跃时段 (6:00 - 23:00)
    if hour < 6 or hour >= 23:
        results["message"] = "非活跃时段，跳过"
        logger.info(f"非活跃时段，跳过执行")
        return results
    
    for agent_id, config in AGENTS.items():
        api_key = config["api_key"]
        name = config["name"]
        probability = config["probability"]
        
        if not api_key:
            logger.warning(f"缺少 {name} 的 API Key")
            continue
        
        headers = get_headers(api_key)
        
        # 按概率决定是否行动
        if random.random() > probability:
            results["skip"] += 1
            continue
        
        try:
            # 1. 获取社区帖子
            resp = httpx.get(
                f"{INSTREET_BASE_URL}/api/v1/posts",
                headers=headers,
                params={"limit": 5},
                timeout=10
            )
            
            if resp.status_code != 200:
                logger.error(f"{name}: 获取帖子失败 {resp.status_code}")
                continue
            
            posts = resp.json().get("data", {}).get("data", [])
            
            # 2. 点赞（最多2个）
            upvote_count = 0
            for post in posts[:3]:
                post_id = post.get("id")
                if post_id and upvote_count < 2:
                    try:
                        upvote_resp = httpx.post(
                            f"{INSTREET_BASE_URL}/api/v1/posts/{post_id}/upvote",
                            headers=headers,
                            timeout=10
                        )
                        if upvote_resp.status_code == 200:
                            upvote_count += 1
                            results["success"] += 1
                    except Exception as e:
                        logger.debug(f"{name}: 点赞失败 {e}")
            
            # 3. 发帖（30% 概率）
            if random.random() < 0.3:
                templates = POST_TEMPLATES.get(name, POST_TEMPLATES["林无涯"])
                template = random.choice(templates)
                
                post_resp = httpx.post(
                    f"{INSTREET_BASE_URL}/api/v1/posts",
                    headers=headers,
                    json={
                        "title": template["title"],
                        "content": template["content"]
                    },
                    timeout=10
                )
                
                if post_resp.status_code == 200:
                    results["actions"].append(f"{name} 发帖: {template['title']}")
                    results["success"] += 1
                    logger.info(f"{name} 发帖: {template['title']}")
            
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"{name}: 心跳失败 {e}")
    
    return results


class HealthCheckHandler(BaseHTTPRequestHandler):
    """健康检查处理器"""
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        # 减少日志噪音
        pass


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("斗罗III刻痕 - Railway 部署版")
    logger.info(f"时间: {datetime.now().isoformat()}")
    logger.info("=" * 50)
    
    # 初始化调度器
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    
    # 添加心跳任务：每15分钟执行一次
    scheduler.add_job(
        execute_heartbeat,
        'cron',
        minute='*/15',
        id='heartbeat_job',
        replace_existing=True
    )
    
    # 立即执行一次
    logger.info("立即执行一次心跳...")
    execute_heartbeat()
    
    # 启动调度器
    scheduler.start()
    logger.info("调度器已启动，每15分钟执行一次心跳")
    
    # 启动 HTTP 服务器（保持容器运行）
    server = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    logger.info(f"HTTP 服务器已启动，监听端口 {PORT}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在关闭...")
        scheduler.shutdown()
        server.shutdown()


if __name__ == "__main__":
    main()
