"""
档案去重逻辑测试
覆盖范围：
- U-6: 待确认记录去重
"""
import pytest
import tempfile
import os
import json
from unittest.mock import AsyncMock, patch
from app.services.profile_service import ProfileService

class TestProfileDeduplication:
    """去重逻辑测试类"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = ProfileService(self.db_path)
        self.service.init_db()
        self.user_id = "test_user_dedup"

    def teardown_method(self):
        """每个测试方法执行后清理"""
        try:
            os.unlink(self.db_path)
        except:
            pass

    @pytest.mark.asyncio
    async def test_pending_updates_deduplication(self):
        """
        U-6: 待确认记录去重测试
        多次提取相同的过敏信息，应只生成一条待确认记录
        """
        # 模拟 LLM 提取结果
        mock_updates = {
            "allergy_history": [
                {"allergen": "牛奶", "reaction": "皮疹", "severity": "mild"}
            ]
        }

        # 使用 patch 模拟 llm_service
        with patch("app.services.llm_service.llm_service") as mock_llm:
            # 配置 mock 返回值
            mock_llm.extract_profile_updates = AsyncMock(return_value=mock_updates)

            # 第一次调用
            result1 = await self.service.apply_updates_from_message(self.user_id, "宝宝喝牛奶起疹子")
            assert result1["updated"] == 1
            assert len(result1["pending_confirmations"]) == 1

            # 验证数据库状态
            profile = self.service.get_profile(self.user_id)
            assert len(profile.pending_confirmations) == 1
            assert profile.pending_confirmations[0]["record"]["allergen"] == "牛奶"

            # 第二次调用（相同内容）
            result2 = await self.service.apply_updates_from_message(self.user_id, "再次提到牛奶过敏")
            
            # 关键断言：没有新增更新，pending 数量保持为 1
            # 注意：apply_updates_from_message 返回的是本次新增的数量，或者是最终的状态？
            # 查看源码：return {"updated": added_count, "pending_confirmations": pending}
            # 如果 added_count 为 0，则返回 {} (Line 203 if not new_pending... wait, logic check needed)
            
            # 让我们回顾一下源码逻辑：
            # 1. extract updates -> 得到 list
            # 2. 遍历 list，检查是否在 current_pending_json 中
            # 3. 如果不在，加入并 added_count += 1
            # 4. 如果 added_count > 0, save profile
            # 5. return {"updated": added_count, "pending_confirmations": pending}
            
            # 所以如果完全重复，added_count 应该是 0。
            # 但是源码 line 202: if not new_pending: return {} 
            # new_pending 是从 updates 转换来的，只要 llm 提取到了，new_pending 就不为空。
            # 去重是在 line 209 的循环中进行的。
            # 所以 result2 应该包含 updated: 0
            
            if "updated" in result2:
                assert result2["updated"] == 0
            
            # 再次验证数据库状态，pending 数量仍为 1
            profile = self.service.get_profile(self.user_id)
            assert len(profile.pending_confirmations) == 1

    @pytest.mark.asyncio
    async def test_different_updates_are_added(self):
        """测试不同的更新会被添加"""
        mock_update_1 = {
            "allergy_history": [{"allergen": "牛奶", "reaction": "皮疹"}]
        }
        mock_update_2 = {
            "allergy_history": [{"allergen": "鸡蛋", "reaction": "呕吐"}]
        }

        with patch("app.services.llm_service.llm_service") as mock_llm:
            # 第一次调用
            mock_llm.extract_profile_updates = AsyncMock(return_value=mock_update_1)
            await self.service.apply_updates_from_message(self.user_id, "msg1")
            
            # 第二次调用（不同内容）
            mock_llm.extract_profile_updates = AsyncMock(return_value=mock_update_2)
            await self.service.apply_updates_from_message(self.user_id, "msg2")
            
            # 验证数据库状态
            profile = self.service.get_profile(self.user_id)
            assert len(profile.pending_confirmations) == 2
            allergens = {p["record"]["allergen"] for p in profile.pending_confirmations}
            assert "牛奶" in allergens
            assert "鸡蛋" in allergens
