"""
档案模块边界与异常测试
覆盖范围：
- E-3: 体重超大值校验
- E-4: 身高极小值校验
- E-14: 血糖值合理性校验
- E-15: 血压逻辑校验
- U-5: 年龄/月龄自动计算逻辑
"""
import pytest
import tempfile
import os
from datetime import date, timedelta
from app.services.profile_service import MemberProfileService
from app.models.user import VitalSigns, MemberProfile, Relationship, Gender

class TestProfileEdgeCases:
    """边界与异常测试类"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = MemberProfileService(self.db_path)
        self.service.init_member_tables()
        self.user_id = "test_user_edge"
        
        # 创建一个基础成员用于测试体征
        self.member = MemberProfile(
            id="",
            user_id=self.user_id,
            name="测试用户",
            relationship=Relationship.CHILD,
            gender=Gender.MALE,
            birth_date="2024-01-01"
        )
        self.member_id = self.service.create_member(self.member)

    def teardown_method(self):
        """每个测试方法执行后清理"""
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_extreme_weight_validation(self):
        """
        E-3: 体重输入 1000 kg -> 拒绝保存
        合理范围建议：1kg - 300kg
        """
        vital_signs = VitalSigns(
            member_id=self.member_id,
            height_cm=170.0,
            weight_kg=1000.0  # 异常值
        )

        with pytest.raises(ValueError, match="体重数值不合理"):
            self.service.upsert_vital_signs(vital_signs)

    def test_extreme_height_validation(self):
        """
        E-4: 身高输入 0.5 cm -> 拒绝保存
        合理范围建议：20cm - 250cm
        """
        vital_signs = VitalSigns(
            member_id=self.member_id,
            height_cm=0.5,  # 异常值
            weight_kg=60.0
        )

        with pytest.raises(ValueError, match="身高数值不合理"):
            self.service.upsert_vital_signs(vital_signs)

    def test_blood_sugar_validation(self):
        """
        E-14: 血糖值输入 999 -> 拒绝保存
        合理范围建议：0.5 - 50.0 mmol/L
        """
        vital_signs = VitalSigns(
            member_id=self.member_id,
            height_cm=170.0,
            weight_kg=60.0,
            blood_sugar=999.0  # 异常值
        )

        with pytest.raises(ValueError, match="血糖数值不合理"):
            self.service.upsert_vital_signs(vital_signs)

    def test_blood_pressure_logic_validation(self):
        """
        E-15: 血压收缩压 < 舒张压 -> 警告或拒绝
        这里预期拒绝保存
        """
        vital_signs = VitalSigns(
            member_id=self.member_id,
            height_cm=170.0,
            weight_kg=60.0,
            blood_pressure_systolic=80,   # 收缩压（低压）
            blood_pressure_diastolic=120  # 舒张压（高压） - 填反了
        )

        with pytest.raises(ValueError, match="收缩压应大于舒张压"):
            self.service.upsert_vital_signs(vital_signs)

    def test_age_calculation_months(self):
        """
        U-5: 年龄自动计算 - 月龄
        测试 calculate_age_months 方法
        """
        # 假设今天是 2024-06-01 (在测试中动态计算)
        today = date.today()
        
        # 6个月前的日期
        birth_date_6m = (today - timedelta(days=30*6)).strftime("%Y-%m-%d")
        age_months = self.service.calculate_age_months(birth_date_6m)
        assert 5 <= age_months <= 7  # 允许一定的天数误差

    def test_age_calculation_years(self):
        """
        U-5: 年龄自动计算 - 岁数转换为月龄
        """
        today = date.today()
        # 2年前的日期
        birth_date_2y = (today.replace(year=today.year - 2)).strftime("%Y-%m-%d")
        age_months = self.service.calculate_age_months(birth_date_2y)
        assert 23 <= age_months <= 25

    def test_age_calculation_future_date(self):
        """
        测试未来日期的月龄计算（应为0或负数，或抛异常，这里假设返回0）
        """
        today = date.today()
        future_date = (today + timedelta(days=30)).strftime("%Y-%m-%d")
        
        # 假设返回0表示尚未出生
        age_months = self.service.calculate_age_months(future_date)
        assert age_months <= 0
