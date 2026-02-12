#!/usr/bin/env python3
"""
多轮对话测试脚本

验证 conversation_id 是否正确传递和维护
"""

import requests
import json
import time

API_BASE_STREAM = "http://localhost:8000/api/v1/chat/stream"
USER_ID = "test_user"


def parse_sse_response(response_text):
    """解析 SSE 格式的响应"""
    lines = response_text.strip().split('\n')
    conversation_id = None
    message_content = []

    for line in lines:
        line = line.strip()
        if line.startswith('data: '):
            json_str = line[6:].strip()  # 移除 "data: " 前缀
            try:
                data = json.loads(json_str)
                if data.get('type') == 'done' and 'conversation_id' in data:
                    conversation_id = data['conversation_id']
                elif data.get('type') == 'content' and 'content' in data:
                    message_content.append(data['content'])
            except json.JSONDecodeError:
                pass

    return {
        'conversation_id': conversation_id,
        'message': ''.join(message_content) if message_content else None
    }


def test_multi_turn_conversation():
    """测试多轮对话是否维持同一会话"""

    print("\n" + "="*60)
    print("多轮对话测试 - 验证 conversation_id 传递")
    print("="*60)

    # 第一轮：发送年龄信息
    print("\n📝 第一轮：发送年龄信息")
    print("-" * 60)

    response1 = requests.post(
        API_BASE_STREAM,
        json={
            "user_id": USER_ID,
            "message": "宝宝8个月"
        }
    )

    # 解析 SSE 响应
    print(f"🔍 第一轮原始响应（状态码 {response1.status_code}）：")
    result1 = parse_sse_response(response1.text)
    conv_id_1 = result1.get('conversation_id')
    message1 = result1.get('message', '')

    print(f"✅ 第一轮响应：")
    print(f"   conversation_id: {conv_id_1}")
    print(f"   message: {message1[:100] if message1 else '(empty)'}...")

    if not conv_id_1:
        print("❌ 第一轮没有返回 conversation_id！")
        return

    time.sleep(1)

    # 第二轮：添加症状信息（应该使用同一 conversation_id）
    print("\n📝 第二轮：添加症状信息（应携带 conversation_id）")
    print("-" * 60)

    response2 = requests.post(
        API_BASE_STREAM,
        json={
            "user_id": USER_ID,
            "conversation_id": conv_id_1,
            "message": "发烧38.5度，伴有咳嗽"
        }
    )

    # 解析 SSE 响应
    print(f"🔍 第二轮原始响应（状态码 {response2.status_code}）：")
    result2 = parse_sse_response(response2.text)
    conv_id_2 = result2.get('conversation_id')
    message2 = result2.get('message', '')

    print(f"✅ 第二轮响应：")
    print(f"   发送的 conversation_id: {conv_id_1}")
    print(f"   返回的 conversation_id: {conv_id_2}")
    print(f"   message: {message2[:100] if message2 else '(empty)'}...")

    # 验证：两轮的 conversation_id 应该相同
    print("\n🔍 验证结果：")
    print("-" * 60)

    if conv_id_1 == conv_id_2:
        print("✅ SUCCESS: conversation_id 保持一致！")
        print(f"   两轮都使用: {conv_id_1}")
    else:
        print("❌ FAIL: conversation_id 不一致！")
        print(f"   第一轮: {conv_id_1}")
        print(f"   第二轮: {conv_id_2}")
        print("\n💡 这说明后端创建了新会话，'失忆' bug 未修复！")

    # 第三轮：继续添加信息（进一步验证）
    print("\n📝 第三轮：继续对话")
    print("-" * 60)

    response3 = requests.post(
        API_BASE_STREAM,
        json={
            "user_id": USER_ID,
            "conversation_id": conv_id_2,
            "message": "1天"
        }
    )

    # 解析 SSE 响应
    print(f"🔍 第三轮原始响应（状态码 {response3.status_code}）：")
    result3 = parse_sse_response(response3.text)
    conv_id_3 = result3.get('conversation_id')
    message3 = result3.get('message', '')

    print(f"✅ 第三轮响应：")
    print(f"   发送的 conversation_id: {conv_id_2}")
    print(f"   返回的 conversation_id: {conv_id_3}")
    print(f"   message: {message3[:100] if message3 else '(empty)'}...")

    print("\n🔍 最终验证：")
    print("-" * 60)

    if conv_id_1 == conv_id_2 == conv_id_3:
        print("✅ SUCCESS: 所有轮次 conversation_id 一致！")
        print(f"   统一会话ID: {conv_id_1}")
    else:
        print("❌ FAIL: conversation_id 发生变化！")
        print(f"   第一轮: {conv_id_1}")
        print(f"   第二轮: {conv_id_2}")
        print(f"   第三轮: {conv_id_3}")

    print("\n" + "="*60)


if __name__ == "__main__":
    try:
        test_multi_turn_conversation()
    except requests.exceptions.ConnectionError:
        print("\n❌ 连接失败！请确保后端服务正在运行。")
        print("启动命令：")
        print("  cd /Users/zhang/Desktop/Claude/pediatric-assistant/backend")
        print("  source venv/bin/activate")
        print("  PYTHONPATH=. uvicorn app.main:app --reload")
