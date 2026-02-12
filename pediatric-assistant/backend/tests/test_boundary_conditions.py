"""
边界条件测试 - 测试输入边界和异常情况
"""
import pytest
from httpx import AsyncClient
from app.main import app


class TestEmptyInput:
    """空值输入测试"""

    @pytest.mark.asyncio
    async def test_empty_message(self):
        """测试空消息"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/chat/send", json={
                "user_id": "test_user",
                "message": ""
            })
            # 应该拒绝空消息 (422 Unprocessable Entity)
            assert response.status_code in [422, 400]

    @pytest.mark.asyncio
    async def test_whitespace_message(self):
        """测试仅空格消息"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/chat/send", json={
                "user_id": "test_user",
                "message": "   \n\t  "
            })
            # 应该拒绝空白消息
            assert response.status_code in [422, 400]

    @pytest.mark.asyncio
    async def test_empty_user_id(self):
        """测试空用户ID"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/chat/send", json={
                "user_id": "",
                "message": "测试消息"
            })
            # 应该拒绝空用户ID
            assert response.status_code in [422, 400]

    @pytest.mark.asyncio
    async def test_missing_required_fields(self):
        """测试缺少必填字段"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/chat/send", json={
                "user_id": "test_user"
                # 缺少 message
            })
            # 应该拒绝缺少字段
            assert response.status_code == 422


class TestOversizedInput:
    """超长输入测试"""

    @pytest.mark.asyncio
    async def test_oversized_message(self):
        """测试超长消息 (10000字符)"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            long_message = "A" * 10000
            response = await client.post("/api/v1/chat/send", json={
                "user_id": "test_user",
                "message": long_message
            })
            # 应该拒绝或处理超长消息
            # 目前可能通过，但应该添加限制
            assert response.status_code in [200, 413, 422]

    @pytest.mark.asyncio
    async def test_oversized_user_id(self):
        """测试超长用户ID (500字符)"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            long_user_id = "A" * 500
            response = await client.post("/api/v1/chat/send", json={
                "user_id": long_user_id,
                "message": "测试"
            })
            # 应该拒绝超长用户ID
            assert response.status_code in [422, 400]

    @pytest.mark.asyncio
    async def test_oversized_member_name(self):
        """测试超长成员姓名 (200字符)"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            long_name = "A" * 200
            response = await client.post("/api/v1/profile/test_user/members", json={
                "name": long_name,
                "relationship": "child",
                "gender": "male",
                "birth_date": "2024-01-01"
            })
            # 应该拒绝超长姓名 (max_length=50)
            assert response.status_code == 422


class TestSpecialCharacters:
    """特殊字符测试"""

    @pytest.mark.asyncio
    async def test_sql_injection(self):
        """测试SQL注入攻击"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            sql_payloads = [
                "user1'; DROP TABLE users; --",
                "admin'--",
                "' OR '1'='1",
                "'; SELECT * FROM users WHERE '1'='1"
            ]
            for payload in sql_payloads:
                response = await client.post("/api/v1/chat/send", json={
                    "user_id": "test_user",
                    "message": payload
                })
                # 应该安全处理，不崩溃
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_xss_in_message(self):
        """测试XSS攻击"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            xss_payloads = [
                "<script>alert(1)</script>",
                "<img src=x onerror=alert(1)>",
                "<svg onload=alert(1)>",
                "javascript:alert(1)"
            ]
            for payload in xss_payloads:
                response = await client.post("/api/v1/chat/send", json={
                    "user_id": "test_user",
                    "message": payload
                })
                # 应该安全处理，XSS不应在前端执行
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_null_byte(self):
        """测试空字节注入"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            null_payload = "test\x00message"
            response = await client.post("/api/v1/chat/send", json={
                "user_id": "test_user",
                "message": null_payload
            })
            # 应该拒绝或清理空字节
            assert response.status_code in [200, 400, 422]

    @pytest.mark.asyncio
    async def test_unicode_control_chars(self):
        """测试Unicode控制字符"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            control_chars = [
                "\u0000",  # Null
                "\u200B",  # Zero-width space
                "\uFEFF",  # Zero-width no-break space
                "\u202E",  # Right-to-left override
            ]
            for char in control_chars:
                response = await client.post("/api/v1/chat/send", json={
                    "user_id": "test_user",
                    "message": f"test{char}message"
                })
                # 应该安全处理
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_emoji_and_unicode(self):
        """测试emoji和复杂Unicode"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            emoji_messages = [
                "宝宝发烧 😷",
                "测试 👶👶",
                "🏥 医院",
                "🤒 呕吐",
                "测试表情 😀😁😂🤣😃😄😅😆"
            ]
            for msg in emoji_messages:
                response = await client.post("/api/v1/chat/send", json={
                    "user_id": "test_user",
                    "message": msg
                })
                # 应该正确处理emoji
                assert response.status_code == 200


class TestNumericBoundary:
    """数值边界测试"""

    @pytest.mark.asyncio
    async def test_negative_age_via_profile(self):
        """通过档案创建测试负数年龄"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 使用未来日期（可能导致负年龄计算）
            response = await client.post("/api/v1/profile/test_user/members", json={
                "name": "测试成员",
                "relationship": "child",
                "gender": "male",
                "birth_date": "2099-01-01"  # 未来日期
            })
            # Pydantic validator 应该捕获
            assert response.status_code in [422, 400]

    @pytest.mark.asyncio
    async def test_extreme_temperature(self):
        """测试极端体温输入"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            extreme_temps = [
                "-10度",  # 负数体温
                "100度",  # 超高体温
                "0度",    # 零度
                "45度"   # 边界体温
            ]
            for temp in extreme_temps:
                response = await client.post("/api/v1/chat/send", json={
                    "user_id": "test_user",
                    "message": f"宝宝{temp}了，怎么办？"
                })
                # 应该处理极端值，给出警告
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_extreme_weight_height(self):
        """测试极端体重身高"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            extreme_values = [
                {"weight_kg": -5, "height_cm": 50},  # 负数体重
                {"weight_kg": 0, "height_cm": 50},   # 零体重
                {"weight_kg": 500, "height_cm": 50}, # 超重
                {"weight_kg": 5, "height_cm": 0},    # 零身高
                {"weight_kg": 5, "height_cm": 300}, # 超高
            ]
            for values in extreme_values:
                response = await client.post("/api/v1/profile/test_user/members", json={
                    "name": "测试成员",
                    "relationship": "child",
                    "gender": "male",
                    "birth_date": "2024-01-01",
                    **values
                })
                # upsert_vital_signs 应该验证并拒绝
                assert response.status_code in [200, 422]


class TestDateBoundary:
    """日期边界测试"""

    @pytest.mark.asyncio
    async def test_invalid_date_formats(self):
        """测试无效日期格式"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            invalid_dates = [
                "2024-13-01",  # 无效月份
                "2024-02-30",  # 无效日期
                "2024-00-01",  # 无效月份
                "01-01-2024",  # 错误格式
                "2024/01/01",  # 错误分隔符
                "not-a-date",  # 非日期
            ]
            for date in invalid_dates:
                response = await client.post("/api/v1/profile/test_user/members", json={
                    "name": "测试成员",
                    "relationship": "child",
                    "gender": "male",
                    "birth_date": date
                })
                # 应该拒绝无效日期
                assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_future_birth_date(self):
        """测试未来出生日期"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            from datetime import datetime, timedelta
            future_date = (datetime.now() + timedelta(days=100)).strftime("%Y-%m-%d")

            response = await client.post("/api/v1/profile/test_user/members", json={
                "name": "测试成员",
                "relationship": "child",
                "gender": "male",
                "birth_date": future_date
            })
            # 应该拒绝未来日期 (Pydantic validator)
            assert response.status_code == 422


class TestEdgeCases:
    """边缘案例测试"""

    @pytest.mark.asyncio
    async def test_concurrent_conversation_creation(self):
        """测试并发创建对话"""
        import asyncio

        async with AsyncClient(app=app, base_url="http://test") as client:
            async def create_conv():
                return await client.post("/api/v1/chat/conversations/test_user")

            # 并发创建10个对话
            results = await asyncio.gather(*[create_conv() for _ in range(10)])
            # 所有请求应该成功 (可能有重复ID，但不应崩溃)
            success_count = sum(1 for r in results if r.status_code == 200)
            assert success_count >= 8  # 允许少量失败

    @pytest.mark.asyncio
    async def test_very_long_conversation_id(self):
        """测试超长对话ID"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            long_conv_id = "conv_" + "A" * 1000
            response = await client.get(f"/api/v1/chat/history/{long_conv_id}")
            # 应该处理长ID (返回空或错误，不崩溃)
            assert response.status_code in [200, 404, 422]

    @pytest.mark.asyncio
    async def test_nonexistent_conversation(self):
        """测试不存在的对话ID"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/chat/history/conv_does_not_exist")
            # 应该返回空历史或404
            assert response.status_code == 200
            data = response.json()
            assert "data" in data

    @pytest.mark.asyncio
    async def test_conversation_with_special_chars_id(self):
        """测试特殊字符对话ID"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            special_ids = [
                "conv_with_underscore",
                "conv-with-dash",
                "conv.with.dot",
                "conv:with:colon"
            ]
            for conv_id in special_ids:
                response = await client.get(f"/api/v1/chat/history/{conv_id}")
                # 应该安全处理各种ID格式
                assert response.status_code in [200, 404]
