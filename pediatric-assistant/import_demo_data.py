#!/usr/bin/env python3
"""
导入演示数据到数据库
将 yanshi.py 生成的演示数据导入到对应数据库和文件中
"""

import json
import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

# 项目路径
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
DATA_DIR = BACKEND_DIR / "app" / "data"
KNOWLEDGE_BASE_DIR = DATA_DIR / "knowledge_base"
DEMO_DATA_DIR = BASE_DIR / "demo_data"
DB_PATH = DATA_DIR / "pediatric_assistant.db"

def load_demo_data():
    """加载演示数据"""
    print("📂 加载演示数据...")

    with open(DEMO_DATA_DIR / "knowledge_base.json", "r", encoding="utf-8") as f:
        kb_data = json.load(f)

    with open(DEMO_DATA_DIR / "test_cases.json", "r", encoding="utf-8") as f:
        test_data = json.load(f)

    with open(DEMO_DATA_DIR / "mock_users.json", "r", encoding="utf-8") as f:
        user_data = json.load(f)

    return kb_data["knowledge_base"], test_data["test_cases"], user_data

def import_knowledge_base(kb_entries):
    """导入知识库数据"""
    print("📚 导入知识库数据...")

    # 按topic分组
    topics = {}
    for entry in kb_entries:
        topic = entry["topic"]
        if topic not in topics:
            topics[topic] = {
                "topic": topic,
                "category": "症状护理",  # 默认分类
                "source": "默沙东诊疗手册（家庭版）",  # 默认来源
                "entries": []
            }

        # 转换格式为系统期望的格式
        formatted_entry = {
            "id": entry["id"],
            "title": entry["title"],
            "content": entry["content"],
            "source": entry.get("source", "默沙东诊疗手册（家庭版）"),
            "tags": entry.get("tags", []),
            "age_range": entry.get("age_range", "0-36个月")
        }

        # 添加可选字段
        if "alert_level" in entry:
            formatted_entry["alert_level"] = entry["alert_level"]
        if "contraindications" in entry:
            formatted_entry["contraindications"] = entry["contraindications"]

        topics[topic]["entries"].append(formatted_entry)

    # 写入文件
    for topic, data in topics.items():
        # 生成文件名（中文转拼音或使用topic作为文件名）
        filename = f"{topic}.json"
        filepath = KNOWLEDGE_BASE_DIR / filename

        # 如果文件已存在，合并并覆盖数据
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)

                # 创建现有条目的ID映射
                existing_entries = {e["id"]: e for e in existing_data.get("entries", [])}

                # 更新或添加新条目
                for new_entry in data["entries"]:
                    existing_entries[new_entry["id"]] = new_entry

                # 转换回列表
                existing_data["entries"] = list(existing_entries.values())
                data = existing_data
                print(f"  🔄 {topic}: 更新 {len(data['entries'])} 条记录（覆盖重复ID）")
            except Exception as e:
                print(f"⚠️  读取现有文件 {filename} 失败: {e}")

        # 写入文件
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"  ✅ {topic}: 写入 {len(data['entries'])} 条记录 -> {filename}")

    print(f"🎯 知识库导入完成，共处理 {len(topics)} 个主题")

def import_test_cases(test_cases):
    """导入测试用例数据"""
    print("🧪 导入测试用例数据...")

    test_cases_path = DATA_DIR / "test_cases.json"

    # 加载现有测试用例
    existing_cases = []
    if test_cases_path.exists():
        try:
            with open(test_cases_path, "r", encoding="utf-8") as f:
                existing_cases = json.load(f)
            print(f"  现有测试用例: {len(existing_cases)} 条")
        except Exception as e:
            print(f"⚠️  读取现有测试用例失败: {e}")

    # 合并测试用例，覆盖重复ID
    # 创建现有用例的ID映射
    case_map = {case["id"]: case for case in existing_cases}
    updated_count = 0
    new_count = 0

    for case in test_cases:
        # 转换格式为系统期望的格式
        formatted_case = {
            "id": case["id"],
            "category": case["category"],
            "description": case.get("description", ""),
            "input": case["input"],
            "expected": case["expected"]
        }

        if case["id"] in case_map:
            # 更新现有用例
            case_map[case["id"]] = formatted_case
            updated_count += 1
        else:
            # 添加新用例
            case_map[case["id"]] = formatted_case
            new_count += 1

    # 转换回列表
    all_cases = list(case_map.values())

    # 写入文件
    with open(test_cases_path, "w", encoding="utf-8") as f:
        json.dump(all_cases, f, indent=2, ensure_ascii=False)

    print(f"  ✅ 新增 {new_count} 条测试用例，更新 {updated_count} 条已有用例")
    print(f"  📊 总计 {len(all_cases)} 条测试用例")

def import_user_profiles(user_profiles):
    """导入用户档案数据到数据库"""
    print("👥 导入用户档案数据...")

    if not DB_PATH.exists():
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        print("💡 请先启动后端服务以创建数据库")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 检查表结构
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        table_names = [t[0] for t in tables]
        print(f"  数据库表: {table_names}")

        # 检查profiles表是否存在
        if 'profiles' not in table_names:
            print("❌ profiles表不存在")
            return

        cursor.execute("SELECT * FROM profiles LIMIT 1")
        columns = [description[0] for description in cursor.description]
        print(f"  profiles表结构: {columns}")

        # 准备插入/更新数据
        inserted_count = 0
        updated_count = 0

        for user in user_profiles:
            user_id = user["user_id"]
            baby_info = user["baby_info"]
            vitals = user["vitals"]
            health_history = user["health_history"]

            # 检查用户是否已存在，获取旧的created_at（如果存在）
            cursor.execute("SELECT created_at FROM profiles WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            if result:
                # 用户已存在，使用旧的created_at
                created_at = result[0]
                updated_count += 1
                if updated_count <= 5:
                    print(f"  🔄 用户 {user_id} 已存在，更新数据")
            else:
                # 新用户，使用当前时间作为created_at
                created_at = datetime.now().isoformat()
                inserted_count += 1
                if inserted_count <= 5:
                    print(f"  ✅ 用户 {user_id} 为新用户，插入数据")

            current_time = datetime.now().isoformat()

            # 准备JSON数据
            baby_info_json = json.dumps(baby_info, ensure_ascii=False)

            # 过敏史 - 转换为JSON数组
            allergies = []
            for allergy in health_history.get("allergies", []):
                if allergy != "无":
                    allergies.append({
                        "id": f"allergy_{inserted_count+updated_count}_{len(allergies)}",
                        "allergen": allergy,
                        "reaction": "未知",
                        "severity": "mild",
                        "confirmed": True
                    })
            allergy_history_json = json.dumps(allergies, ensure_ascii=False)

            # 病史 - 转换为JSON数组
            medical_conditions = []
            for condition in health_history.get("chronic_conditions", []):
                medical_conditions.append({
                    "id": f"med_{inserted_count+updated_count}_{len(medical_conditions)}",
                    "condition": condition,
                    "status": "ongoing",
                    "confirmed": True
                })
            medical_history_json = json.dumps(medical_conditions, ensure_ascii=False)

            # 用药史 - 空数组
            medication_history_json = "[]"

            # 待确认列表 - 空数组
            pending_confirmations_json = "[]"

            # 插入或替换profiles表数据
            cursor.execute("""
                INSERT OR REPLACE INTO profiles
                (user_id, baby_info, allergy_history, medical_history,
                 medication_history, pending_confirmations, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                baby_info_json,
                allergy_history_json,
                medical_history_json,
                medication_history_json,
                pending_confirmations_json,
                created_at,
                current_time
            ))

            # 同时插入members表（如果需要）
            if 'members' in table_names:
                # 生成成员ID
                member_id = f"member_{user_id}"

                # 解析性别
                gender = baby_info.get("gender", "male")
                if gender not in ["male", "female"]:
                    gender = "male"

                # 解析出生日期
                try:
                    birth_date = baby_info.get("birth_date", "2025-01-01")
                except:
                    birth_date = "2025-01-01"

                # 检查成员是否已存在，获取旧的created_at（如果存在）
                cursor.execute("SELECT created_at FROM members WHERE id = ?", (member_id,))
                member_result = cursor.fetchone()
                if member_result:
                    member_created_at = member_result[0]
                else:
                    member_created_at = current_time

                # 插入或替换成员数据
                cursor.execute("""
                    INSERT OR REPLACE INTO members
                    (id, user_id, name, relationship, id_card_type,
                     id_card_number, gender, birth_date, phone, avatar_url,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    member_id,
                    user_id,
                    baby_info.get("nickname", f"宝宝_{inserted_count+updated_count}"),
                    "child",  # 关系：孩子
                    "id_card",
                    None,
                    gender,
                    birth_date,
                    None,
                    None,
                    member_created_at,
                    current_time
                ))

                # 插入体征数据到vital_signs表
                if 'vital_signs' in table_names:
                    cursor.execute("""
                        INSERT OR REPLACE INTO vital_signs
                        (member_id, height_cm, weight_kg, bmi, bmi_status,
                         blood_pressure_systolic, blood_pressure_diastolic,
                         blood_sugar, blood_sugar_type, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        member_id,
                        vitals.get("latest_height_cm", 60.0),
                        vitals.get("latest_weight_kg", 6.0),
                        None,  # BMI自动计算
                        None,  # BMI状态
                        None,  # 收缩压
                        None,  # 舒张压
                        None,  # 血糖
                        None,  # 血糖类型
                        vitals.get("updated_at", current_time)
                    ))

            total_processed = inserted_count + updated_count
            if total_processed % 20 == 0:
                print(f"  ✅ 已处理 {total_processed} 个用户档案（新增: {inserted_count}, 更新: {updated_count}）...")

        conn.commit()
        print(f"🎯 用户档案导入完成: 新增 {inserted_count} 个用户，更新 {updated_count} 个已有用户")

    except sqlite3.Error as e:
        print(f"❌ 数据库错误: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"❌ 导入用户档案时出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

def rebuild_vector_index():
    """重建向量索引"""
    print("🔄 重建向量索引...")

    try:
        # 导入RAGService并重建索引
        sys.path.insert(0, str(BACKEND_DIR))
        from app.services.rag_service import rag_service

        # 重新加载知识库
        rag_service.knowledge_base = rag_service._load_knowledge_base()

        # 重建本地索引（如果方法可用）
        if hasattr(rag_service, '_build_local_index'):
            rag_service._build_local_index()
            print("  ✅ 向量索引重建完成")
        else:
            print("  ⚠️  _build_local_index 方法不可用")

    except ImportError as e:
        print(f"⚠️  无法导入RAG服务: {e}")
        print("💡 请确保后端依赖已安装并设置PYTHONPATH")
    except Exception as e:
        print(f"⚠️  重建索引失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主函数"""
    print("🚀 开始导入演示数据")
    print("=" * 50)

    # 检查演示数据是否存在
    if not DEMO_DATA_DIR.exists():
        print(f"❌ 演示数据目录不存在: {DEMO_DATA_DIR}")
        print("💡 请先运行 yanshi.py 生成演示数据")
        return

    # 加载演示数据
    try:
        kb_entries, test_cases, user_profiles = load_demo_data()
        print(f"📊 加载数据: {len(kb_entries)} 条知识, {len(test_cases)} 条测试用例, {len(user_profiles)} 个用户")
    except Exception as e:
        print(f"❌ 加载演示数据失败: {e}")
        return

    # 导入知识库数据
    import_knowledge_base(kb_entries)
    print("-" * 30)

    # 导入测试用例数据
    import_test_cases(test_cases)
    print("-" * 30)

    # 导入用户档案数据
    import_user_profiles(user_profiles)
    print("-" * 30)

    # 重建向量索引
    rebuild_vector_index()
    print("-" * 30)

    print("🎉 演示数据导入完成！")
    print("=" * 50)
    print("📋 下一步操作:")
    print("  1. 启动后端服务: cd backend && python -m app.main")
    print("  2. 测试知识库检索是否正常")
    print("  3. 运行测试用例验证功能: pytest tests/")

if __name__ == "__main__":
    main()