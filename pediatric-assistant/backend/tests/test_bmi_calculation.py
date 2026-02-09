"""
BMI 计算单元测试
测试 profile_service.py 中的 BMI 计算和状态分级逻辑

测试范围：
- U-1: BMI 计算函数 (weight_kg / (height_cm/100)²，结果保留 1 位小数)
- U-2: BMI 状态分级 (四档：<18.5 偏瘦 / 18.5-24 正常 / 24-28 偏胖 / ≥28 肥胖)
"""
import pytest
import tempfile
import os
from app.services.profile_service import MemberProfileService
from app.models.user import VitalSigns, BMIStatus


class TestBMICalculation:
    """BMI 计算测试类"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        # 创建临时文件数据库
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = MemberProfileService(self.db_path)
        self.service.init_member_tables()

    def teardown_method(self):
        """每个测试方法执行后清理"""
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_bmi_calculation_newborn(self):
        """
        TC-BMI-001: 新生儿 BMI 计算
        身高 50cm, 体重 3.5kg -> BMI=14.0, 状态=偏瘦
        """
        vital_signs = VitalSigns(
            member_id="test_001",
            height_cm=50.0,
            weight_kg=3.5
        )

        self.service.upsert_vital_signs(vital_signs)

        assert vital_signs.bmi == pytest.approx(14.0, 0.1)
        assert vital_signs.bmi_status == BMIStatus.UNDERWEIGHT

    def test_bmi_calculation_6month_infant(self):
        """
        TC-BMI-002: 6月龄婴儿 BMI 计算
        身高 75cm, 体重 9.5kg -> BMI=16.9, 状态=偏瘦
        """
        vital_signs = VitalSigns(
            member_id="test_002",
            height_cm=75.0,
            weight_kg=9.5
        )

        self.service.upsert_vital_signs(vital_signs)

        assert vital_signs.bmi == pytest.approx(16.9, 0.1)
        assert vital_signs.bmi_status == BMIStatus.UNDERWEIGHT

    def test_bmi_calculation_preschooler(self):
        """
        TC-BMI-003: 学龄前儿童 BMI 计算
        身高 100cm, 体重 20kg -> BMI=20.0, 状态=正常
        """
        vital_signs = VitalSigns(
            member_id="test_003",
            height_cm=100.0,
            weight_kg=20.0
        )

        self.service.upsert_vital_signs(vital_signs)

        assert vital_signs.bmi == pytest.approx(20.0, 0.1)
        assert vital_signs.bmi_status == BMIStatus.NORMAL

    def test_bmi_calculation_teenager(self):
        """
        TC-BMI-004: 青少年 BMI 计算
        身高 150cm, 体重 65kg -> BMI=28.9, 状态=肥胖
        """
        vital_signs = VitalSigns(
            member_id="test_004",
            height_cm=150.0,
            weight_kg=65.0
        )

        self.service.upsert_vital_signs(vital_signs)

        assert vital_signs.bmi == pytest.approx(28.9, 0.1)
        assert vital_signs.bmi_status == BMIStatus.OBESE

    def test_bmi_boundary_exactly_18_5(self):
        """
        TC-BMI-008: BMI 边界值测试 - 恰好 18.5
        身高 100cm, 体重 18.5kg -> BMI=18.5, 状态=正常 (非偏瘦)
        """
        vital_signs = VitalSigns(
            member_id="test_005",
            height_cm=100.0,
            weight_kg=18.5
        )

        self.service.upsert_vital_signs(vital_signs)

        assert vital_signs.bmi == pytest.approx(18.5, 0.1)
        assert vital_signs.bmi_status == BMIStatus.NORMAL

    def test_bmi_boundary_exactly_24(self):
        """
        TC-BMI-009: BMI 边界值测试 - 恰好 24.0
        身高 100cm, 体重 24kg -> BMI=24.0, 状态=偏胖 (非正常)
        """
        vital_signs = VitalSigns(
            member_id="test_006",
            height_cm=100.0,
            weight_kg=24.0
        )

        self.service.upsert_vital_signs(vital_signs)

        assert vital_signs.bmi == pytest.approx(24.0, 0.1)
        assert vital_signs.bmi_status == BMIStatus.OVERWEIGHT

    def test_bmi_boundary_exactly_28(self):
        """
        TC-BMI-010: BMI 边界值测试 - 恰好 28.0
        身高 100cm, 体重 28kg -> BMI=28.0, 状态=肥胖 (非偏胖)
        """
        vital_signs = VitalSigns(
            member_id="test_007",
            height_cm=100.0,
            weight_kg=28.0
        )

        self.service.upsert_vital_signs(vital_signs)

        assert vital_signs.bmi == pytest.approx(28.0, 0.1)
        assert vital_signs.bmi_status == BMIStatus.OBESE

    def test_bmi_status_underweight_boundary(self):
        """测试偏瘦状态边界 - BMI 18.4 应为偏瘦"""
        # 身高100cm，体重18.4kg -> BMI=18.4
        vital_signs = VitalSigns(
            member_id="test_008",
            height_cm=100.0,
            weight_kg=18.4
        )

        self.service.upsert_vital_signs(vital_signs)

        assert vital_signs.bmi == pytest.approx(18.4, 0.1)
        assert vital_signs.bmi_status == BMIStatus.UNDERWEIGHT

    def test_bmi_status_normal_upper_boundary(self):
        """测试正常状态上边界 - BMI 23.9 应为正常"""
        vital_signs = VitalSigns(
            member_id="test_009",
            height_cm=100.0,
            weight_kg=23.9
        )

        self.service.upsert_vital_signs(vital_signs)

        assert vital_signs.bmi == pytest.approx(23.9, 0.1)
        assert vital_signs.bmi_status == BMIStatus.NORMAL

    def test_bmi_status_overweight_upper_boundary(self):
        """测试偏胖状态上边界 - BMI 27.9 应为偏胖"""
        vital_signs = VitalSigns(
            member_id="test_010",
            height_cm=100.0,
            weight_kg=27.9
        )

        self.service.upsert_vital_signs(vital_signs)

        assert vital_signs.bmi == pytest.approx(27.9, 0.1)
        assert vital_signs.bmi_status == BMIStatus.OVERWEIGHT

    def test_bmi_rounding_precision(self):
        """测试BMI计算保留1位小数的精度"""
        # 身高65cm，体重7.3kg -> BMI = 7.3 / (0.65)^2 = 17.283... -> 17.3
        vital_signs = VitalSigns(
            member_id="test_011",
            height_cm=65.0,
            weight_kg=7.3
        )

        self.service.upsert_vital_signs(vital_signs)

        assert vital_signs.bmi == pytest.approx(17.3, 0.1)

    def test_bmi_with_decimal_height(self):
        """测试小数身高的BMI计算"""
        # 身高83.5cm，体重11.2kg
        vital_signs = VitalSigns(
            member_id="test_012",
            height_cm=83.5,
            weight_kg=11.2
        )

        self.service.upsert_vital_signs(vital_signs)

        expected_bmi = 11.2 / (0.835 * 0.835)
        assert vital_signs.bmi == pytest.approx(round(expected_bmi, 1), 0.1)

    def test_bmi_not_calculated_when_height_zero(self):
        """
        E-1: 身高为0时不计算BMI -> 应抛出异常
        """
        vital_signs = VitalSigns(
            member_id="test_013",
            height_cm=0.0,
            weight_kg=10.0
        )

        with pytest.raises(ValueError, match="身高必须大于0"):
            self.service.upsert_vital_signs(vital_signs)

    def test_bmi_not_calculated_when_weight_zero(self):
        """
        E-5: 体重为0时不计算BMI -> 应抛出异常
        """
        vital_signs = VitalSigns(
            member_id="test_014",
            height_cm=100.0,
            weight_kg=0.0
        )

        with pytest.raises(ValueError, match="体重必须大于0"):
            self.service.upsert_vital_signs(vital_signs)

    def test_bmi_not_calculated_when_negative_height(self):
        """
        E-2: 身高为负数时不计算BMI -> 应抛出异常
        """
        vital_signs = VitalSigns(
            member_id="test_015",
            height_cm=-10.0,
            weight_kg=10.0
        )

        with pytest.raises(ValueError, match="身高必须大于0"):
            self.service.upsert_vital_signs(vital_signs)

    def test_bmi_not_calculated_when_negative_weight(self):
        """
        测试体重为负数时不计算BMI -> 应抛出异常
        """
        vital_signs = VitalSigns(
            member_id="test_016",
            height_cm=100.0,
            weight_kg=-5.0
        )

        with pytest.raises(ValueError, match="体重必须大于0"):
            self.service.upsert_vital_signs(vital_signs)


class TestBMICalculateStatusMethod:
    """直接测试 _calculate_bmi_status 方法"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        # 创建临时文件数据库
        import tempfile
        import os
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = MemberProfileService(self.db_path)
        self.service.init_member_tables()

    def teardown_method(self):
        """每个测试方法执行后清理"""
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_calculate_status_underweight(self):
        """测试偏瘦状态计算"""
        result = self.service._calculate_bmi_status(15.0)
        assert result == BMIStatus.UNDERWEIGHT

    def test_calculate_status_normal(self):
        """测试正常状态计算"""
        result = self.service._calculate_bmi_status(20.0)
        assert result == BMIStatus.NORMAL

    def test_calculate_status_overweight(self):
        """测试偏胖状态计算"""
        result = self.service._calculate_bmi_status(26.0)
        assert result == BMIStatus.OVERWEIGHT

    def test_calculate_status_obese(self):
        """测试肥胖状态计算"""
        result = self.service._calculate_bmi_status(30.0)
        assert result == BMIStatus.OBESE

    def test_calculate_status_boundary_18_5(self):
        """测试边界 18.5 应为正常"""
        result = self.service._calculate_bmi_status(18.5)
        assert result == BMIStatus.NORMAL

    def test_calculate_status_boundary_24(self):
        """测试边界 24 应为偏胖"""
        result = self.service._calculate_bmi_status(24.0)
        assert result == BMIStatus.OVERWEIGHT

    def test_calculate_status_boundary_28(self):
        """测试边界 28 应为肥胖"""
        result = self.service._calculate_bmi_status(28.0)
        assert result == BMIStatus.OBESE
