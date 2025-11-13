#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的用户统计服务器
只统计有多少人在使用闲鱼自动回复系统
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any
import sqlite3
from datetime import datetime
import uvicorn
from pathlib import Path

app = FastAPI(title="闲鱼自动回复系统用户统计", version="1.0.0")

# 数据库文件路径
DB_PATH = Path(__file__).parent / "data" / "user_stats.db"


class UserStats(BaseModel):
    """用户统计数据模型"""
    anonymous_id: str
    timestamp: str
    project: str
    info: Dict[str, Any]


def init_database():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建用户统计表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anonymous_id TEXT UNIQUE NOT NULL,
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            os TEXT,
            version TEXT,
            total_reports INTEGER DEFAULT 1
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_anonymous_id ON user_stats(anonymous_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_seen ON user_stats(last_seen)')
    
    conn.commit()
    conn.close()


def save_user_stats(data: UserStats):
    """保存用户统计数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        info = data.info
        os_info = info.get('os', 'unknown')
        version = info.get('version', '2.2.0')
        
        # 检查用户是否已存在
        cursor.execute('SELECT id, total_reports FROM user_stats WHERE anonymous_id = ?', (data.anonymous_id,))
        existing = cursor.fetchone()
        
        if existing:
            # 更新现有用户的最后访问时间和报告次数
            cursor.execute('''
                UPDATE user_stats 
                SET last_seen = CURRENT_TIMESTAMP, 
                    total_reports = total_reports + 1,
                    os = ?,
                    version = ?
                WHERE anonymous_id = ?
            ''', (os_info, version, data.anonymous_id))
        else:
            # 插入新用户
            cursor.execute('''
                INSERT INTO user_stats (anonymous_id, os, version) 
                VALUES (?, ?, ?)
            ''', (data.anonymous_id, os_info, version))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"保存用户统计失败: {e}")
        return False
    finally:
        conn.close()


@app.post('/statistics')
async def receive_user_stats(data: UserStats):
    """接收用户统计数据"""
    try:
        success = save_user_stats(data)
        
        if success:
            print(f"收到用户统计: {data.anonymous_id}")
            return {"status": "success", "message": "用户统计已收到"}
        else:
            return {"status": "error", "message": "保存统计数据失败"}
            
    except Exception as e:
        print(f"处理用户统计失败: {e}")
        return {"status": "error", "message": "处理统计数据失败"}


@app.get('/stats')
async def get_user_stats():
    """获取用户统计摘要"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 总用户数
        cursor.execute('SELECT COUNT(*) FROM user_stats')
        total_users = cursor.fetchone()[0]
        
        # 今日活跃用户
        cursor.execute('''
            SELECT COUNT(*) 
            FROM user_stats 
            WHERE DATE(last_seen) = DATE('now')
        ''')
        daily_active = cursor.fetchone()[0]
        
        # 本周活跃用户
        cursor.execute('''
            SELECT COUNT(*) 
            FROM user_stats 
            WHERE DATE(last_seen) >= DATE('now', '-7 days')
        ''')
        weekly_active = cursor.fetchone()[0]
        
        # 操作系统分布
        cursor.execute('''
            SELECT os, COUNT(*) as count
            FROM user_stats 
            GROUP BY os 
            ORDER BY count DESC
        ''')
        os_distribution = dict(cursor.fetchall())
        
        # 版本分布
        cursor.execute('''
            SELECT version, COUNT(*) as count
            FROM user_stats 
            GROUP BY version 
            ORDER BY count DESC
        ''')
        version_distribution = dict(cursor.fetchall())
        
        return {
            "total_users": total_users,
            "daily_active_users": daily_active,
            "weekly_active_users": weekly_active,
            "os_distribution": os_distribution,
            "version_distribution": version_distribution,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"error": f"获取统计失败: {e}"}
    finally:
        conn.close()


@app.get('/stats/recent')
async def get_recent_users():
    """获取最近活跃的用户（匿名）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT anonymous_id, first_seen, last_seen, os, version, total_reports
            FROM user_stats 
            ORDER BY last_seen DESC
            LIMIT 20
        ''')
        
        records = cursor.fetchall()
        
        return {
            "recent_users": [
                {
                    "anonymous_id": record[0][:8] + "****",  # 部分隐藏ID
                    "first_seen": record[1],
                    "last_seen": record[2],
                    "os": record[3],
                    "version": record[4],
                    "total_reports": record[5]
                }
                for record in records
            ]
        }
        
    except Exception as e:
        return {"error": f"获取最近用户失败: {e}"}
    finally:
        conn.close()


@app.get('/')
async def root():
    """根路径"""
    return {
        "message": "闲鱼自动回复系统用户统计服务器",
        "description": "只统计有多少人在使用这个系统",
        "endpoints": {
            "POST /statistics": "接收用户统计数据",
            "GET /stats": "获取用户统计摘要",
            "GET /stats/recent": "获取最近活跃用户"
        }
    }


if __name__ == "__main__":
    # 初始化数据库
    init_database()
    print("用户统计数据库初始化完成")
    
    # 启动服务器
    print("启动用户统计服务器...")
    print("访问 http://localhost:8081/stats 查看统计信息")
    uvicorn.run(app, host="0.0.0.0", port=8081)
