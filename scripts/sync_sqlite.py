#!/usr/bin/env python3
"""同步两个 SQLite 数据库之间的数据"""

import sqlite3
import sys
import json

def sync_databases(source_db, target_db):
    """从 source_db 同步数据到 target_db"""
    
    print(f"源数据库：{source_db}")
    print(f"目标数据库：{target_db}")
    print()
    
    # 打开数据库
    src_conn = sqlite3.connect(source_db)
    tgt_conn = sqlite3.connect(target_db)
    
    # 获取源数据库的所有表
    src_tables = [row[0] for row in src_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()]
    
    print(f"需要同步的表：{', '.join(src_tables)}")
    print()
    
    synced_count = 0
    
    for table in src_tables:
        # 获取表结构
        create_sql = src_conn.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'").fetchone()[0]
        
        # 获取源数据
        src_rows = src_conn.execute(f"SELECT * FROM {table}").fetchall()
        src_columns = [desc[1] for desc in src_conn.execute(f"PRAGMA table_info({table})").fetchall()]
        
        if not src_rows:
            print(f"  {table}: 空表，跳过")
            continue
        
        # 清空目标表
        tgt_conn.execute(f"DELETE FROM {table}")
        
        # 插入数据
        placeholders = ', '.join(['?'] * len(src_columns))
        insert_sql = f"INSERT INTO {table} ({', '.join(src_columns)}) VALUES ({placeholders})"
        
        tgt_conn.executemany(insert_sql, src_rows)
        tgt_conn.commit()
        
        print(f"  {table}: {len(src_rows)} 条记录")
        synced_count += len(src_rows)
    
    src_conn.close()
    tgt_conn.close()
    
    print()
    print(f"✅ 同步完成，共 {synced_count} 条记录")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"用法：{sys.argv[0]} <源数据库> <目标数据库>")
        sys.exit(1)
    
    sync_databases(sys.argv[1], sys.argv[2])