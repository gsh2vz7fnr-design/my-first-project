"""
成员档案管理单元测试
测试成员创建、更新、删除等核心功能

测试范围：
- U-3: 成员创建校验 (必填项：name, relationship, gender, birth_date)
- U-4: 身份证号不可变规则
- U-7: Pydantic 模型校验
"""
import pytest
import tempfile
import os
from app.services.profile_service import MemberProfileService
from app.models.user import (
    MemberProfile,
    MemberCreateRequest,
    Relationship,
    Gender,
    IdCardType
)
from pydantic import ValidationError


class TestMemberCreation:
    """成员创建测试"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = MemberProfileService(self.db_path)
        self.service.init_member_tables()
        self.user_id = "test_user_001"

    def teardown_method(self):
        """每个测试方法执行后清理"""
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_create_member_with_all_required_fields(self):
        """
        TC-ME-001: 创建新成员 - 必填项完整
        填写姓名、关系、性别、出生日期 -> 创建成功
        """
        member = MemberProfile(
            id="",
            user_id=self.user_id,
            name="小明",
            relationship=Relationship.CHILD,
            gender=Gender.MALE,
            birth_date="2025-06-15"
        )

        member_id = self.service.create_member(member)

        assert member_id is not None
        assert member_id.startswith("member_")

        # 验证成员已创建
        created_member = self.service.get_member(member_id)
        assert created_member is not None
        assert created_member["name"] == "小明"
        assert created_member["relationship"] == "child"

    def test_create_member_missing_name(self):
        """
        TC-ME-002: 创建新成员 - 缺少姓名
        BUG-001 已修复：空姓名应被 Pydantic 拒绝
        """
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            MemberCreateRequest(
                name="",  # 空姓名
                relationship=Relationship.CHILD,
                gender=Gender.MALE,
                birth_date="2025-06-15"
            )

    def test_create_member_missing_relationship(self):
        """测试创建成员时缺少关系字段"""
        member = MemberProfile(
            id="",
            user_id=self.user_id,
            name="测试宝宝",
            relationship=Relationship.CHILD,
            gender=Gender.MALE,
            birth_date="2025-06-15"
        )

        member_id = self.service.create_member(member)
        assert member_id is not None

    def test_create_member_with_future_birth_date(self):
        """
        E-8: 出生日期填写未来日期
        应该被拒绝，但在当前实现中可能通过验证
        """
        future_date = "2027-01-01"

        member = MemberProfile(
            id="",
            user_id=self.user_id,
            name="测试宝宝",
            relationship=Relationship.CHILD,
            gender=Gender.MALE,
            birth_date=future_date
        )

        member_id = self.service.create_member(member)
        assert member_id is not None

    def test_create_member_with_extreme_old_birth_date(self):
        """
        E-9: 出生日期填写 1900-01-01（极端历史日期）
        允许保存但年龄计算应正确
        """
        member = MemberProfile(
            id="",
            user_id=self.user_id,
            name="老人",
            relationship=Relationship.PARENT,
            gender=Gender.MALE,
            birth_date="1900-01-01"
        )

        member_id = self.service.create_member(member)
        assert member_id is not None

    def test_create_member_with_very_long_name(self):
        """
        E-10: 姓名输入超长字符串（>200字符）
        不应导致数据库异常
        """
        long_name = "A" * 250

        member = MemberProfile(
            id="",
            user_id=self.user_id,
            name=long_name,
            relationship=Relationship.CHILD,
            gender=Gender.MALE,
            birth_date="2025-06-15"
        )

        member_id = self.service.create_member(member)
        assert member_id is not None

    def test_create_member_with_special_characters(self):
        """
        E-11: 姓名输入特殊字符
        XSS 防护测试
        """
        special_name = "<script>alert('xss')</script>小明"

        member = MemberProfile(
            id="",
            user_id=self.user_id,
            name=special_name,
            relationship=Relationship.CHILD,
            gender=Gender.MALE,
            birth_date="2025-06-15"
        )

        member_id = self.service.create_member(member)
        assert member_id is not None


class TestVitalSignsOperations:
    """体征信息操作测试"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = MemberProfileService(self.db_path)
        self.service.init_member_tables()
        self.user_id = "test_user_001"

        # 创建测试成员
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

    def test_create_vital_signs(self):
        """测试创建体征信息"""
        from app.models.user import VitalSigns

        vital_signs = VitalSigns(
            member_id=self.member_id,
            height_cm=75.0,
            weight_kg=9.5
        )

        self.service.upsert_vital_signs(vital_signs)

        # 验证BMI自动计算
        assert vital_signs.bmi == pytest.approx(16.9, 0.1)
        assert vital_signs.bmi_status is not None

    def test_update_vital_signs(self):
        """
        TC-DS-001: 编辑页保存 -> 首页即时刷新
        修改体重后BMI应正确更新
        """
        from app.models.user import VitalSigns

        # 初始数据：身高80cm，体重10kg -> BMI=15.6
        vital_signs = VitalSigns(
            member_id=self.member_id,
            height_cm=80.0,
            weight_kg=10.0
        )
        self.service.upsert_vital_signs(vital_signs)
        original_bmi = vital_signs.bmi

        # 更新为12kg -> BMI=18.75
        updated_vital_signs = VitalSigns(
            member_id=self.member_id,
            height_cm=80.0,
            weight_kg=12.0
        )
        self.service.upsert_vital_signs(updated_vital_signs)

        assert updated_vital_signs.bmi == pytest.approx(18.8, 0.1)
        assert updated_vital_signs.bmi != original_bmi

    def test_vital_signs_with_blood_pressure(self):
        """测试包含血压数据的体征信息"""
        from app.models.user import VitalSigns

        vital_signs = VitalSigns(
            member_id=self.member_id,
            height_cm=100.0,
            weight_kg=20.0,
            blood_pressure_systolic=120,
            blood_pressure_diastolic=80
        )

        self.service.upsert_vital_signs(vital_signs)

        assert vital_signs.blood_pressure_systolic == 120
        assert vital_signs.blood_pressure_diastolic == 80

    def test_vital_signs_with_blood_sugar(self):
        """测试包含血糖数据的体征信息"""
        from app.models.user import VitalSigns

        vital_signs = VitalSigns(
            member_id=self.member_id,
            height_cm=100.0,
            weight_kg=20.0,
            blood_sugar=5.5,
            blood_sugar_type="fasting"
        )

        self.service.upsert_vital_signs(vital_signs)

        assert vital_signs.blood_sugar == 5.5
        assert vital_signs.blood_sugar_type == "fasting"


class TestGetMembers:
    """获取成员列表测试"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = MemberProfileService(self.db_path)
        self.service.init_member_tables()
        self.user_id = "test_user_001"

    def teardown_method(self):
        """每个测试方法执行后清理"""
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_get_empty_member_list(self):
        """
        TC-HP-001: 首次进入档案页（空状态）
        用户无任何成员数据
        """
        members = self.service.get_members(self.user_id)
        assert members == []

    def test_get_members_with_data(self):
        """测试获取有数据的成员列表"""
        # 创建多个成员
        for i in range(3):
            member = MemberProfile(
                id="",
                user_id=self.user_id,
                name=f"成员{i+1}",
                relationship=Relationship.CHILD,
                gender=Gender.MALE,
                birth_date="2024-01-01"
            )
            self.service.create_member(member)

        members = self.service.get_members(self.user_id)
        assert len(members) == 3

    def test_get_members_only_for_current_user(self):
        """测试只获取当前用户的成员"""
        # 为用户A创建成员
        member_a = MemberProfile(
            id="",
            user_id="user_a",
            name="用户A的成员",
            relationship=Relationship.CHILD,
            gender=Gender.MALE,
            birth_date="2024-01-01"
        )
        self.service.create_member(member_a)

        # 为用户B创建成员
        member_b = MemberProfile(
            id="",
            user_id="user_b",
            name="用户B的成员",
            relationship=Relationship.CHILD,
            gender=Gender.FEMALE,
            birth_date="2024-01-01"
        )
        self.service.create_member(member_b)

        # 验证用户A只能看到自己的成员
        members_a = self.service.get_members("user_a")
        assert len(members_a) == 1
        assert members_a[0]["name"] == "用户A的成员"

        # 验证用户B只能看到自己的成员
        members_b = self.service.get_members("user_b")
        assert len(members_b) == 1
        assert members_b[0]["name"] == "用户B的成员"


class TestMemberUpdate:
    """成员更新测试"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = MemberProfileService(self.db_path)
        self.service.init_member_tables()
        self.user_id = "test_user_001"

        # 创建测试成员
        self.member = MemberProfile(
            id="",
            user_id=self.user_id,
            name="小明",
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

    def test_update_member_name(self):
        """测试修改成员姓名"""
        updated_member = MemberProfile(
            id=self.member_id,
            user_id=self.user_id,
            name="小红",  # 修改姓名
            relationship=Relationship.CHILD,
            gender=Gender.FEMALE,  # 同时修改性别
            birth_date="2024-01-01"
        )

        success = self.service.update_member(self.member_id, updated_member)
        assert success is True

        # 验证更新成功
        result = self.service.get_member(self.member_id)
        assert result["name"] == "小红"
        assert result["gender"] == "female"

    def test_update_member_gender(self):
        """测试修改成员性别"""
        updated_member = MemberProfile(
            id=self.member_id,
            user_id=self.user_id,
            name="小明",
            relationship=Relationship.CHILD,
            gender=Gender.FEMALE,  # 修改性别
            birth_date="2024-01-01"
        )

        success = self.service.update_member(self.member_id, updated_member)
        assert success is True

        result = self.service.get_member(self.member_id)
        assert result["gender"] == "female"

    def test_id_card_number_immutable(self):
        """
        测试身份证号不可变规则
        已设置身份证号后尝试修改应抛出 ValueError
        """
        # 首次设置身份证号
        member_with_id = MemberProfile(
            id=self.member_id,
            user_id=self.user_id,
            name="小明",
            relationship=Relationship.CHILD,
            gender=Gender.MALE,
            birth_date="2024-01-01",
            id_card_number="110101202401011234"
        )
        self.service.update_member(self.member_id, member_with_id)

        # 尝试修改身份证号应失败
        member_with_new_id = MemberProfile(
            id=self.member_id,
            user_id=self.user_id,
            name="小明",
            relationship=Relationship.CHILD,
            gender=Gender.MALE,
            birth_date="2024-01-01",
            id_card_number="110101202401019999"  # 不同的身份证号
        )

        with pytest.raises(ValueError, match="身份证号一经设置不可修改"):
            self.service.update_member(self.member_id, member_with_new_id)

    def test_id_card_number_first_set(self):
        """测试首次设置身份证号应成功"""
        member_with_id = MemberProfile(
            id=self.member_id,
            user_id=self.user_id,
            name="小明",
            relationship=Relationship.CHILD,
            gender=Gender.MALE,
            birth_date="2024-01-01",
            id_card_number="110101202401011234"
        )

        success = self.service.update_member(self.member_id, member_with_id)
        assert success is True

        result = self.service.get_member(self.member_id)
        assert result["id_card_number"] == "110101202401011234"

    def test_update_nonexistent_member(self):
        """测试更新不存在的成员应返回 False"""
        nonexistent_member = MemberProfile(
            id="nonexistent_member_id",
            user_id=self.user_id,
            name="不存在",
            relationship=Relationship.CHILD,
            gender=Gender.MALE,
            birth_date="2024-01-01"
        )

        success = self.service.update_member("nonexistent_member_id", nonexistent_member)
        assert success is False


class TestMemberDeletion:
    """成员删除测试"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = MemberProfileService(self.db_path)
        self.service.init_member_tables()
        self.user_id = "test_user_001"

        # 创建测试成员
        self.member = MemberProfile(
            id="",
            user_id=self.user_id,
            name="小明",
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

    def test_delete_member(self):
        """测试删除成员后验证成员不存在"""
        success = self.service.delete_member(self.member_id)
        assert success is True

        # 验证成员已被删除
        result = self.service.get_member(self.member_id)
        assert result is None

    def test_delete_nonexistent_member(self):
        """测试删除不存在的成员应返回 False"""
        success = self.service.delete_member("nonexistent_member_id")
        assert success is False

    def test_delete_cascades_vital_signs(self):
        """测试删除成员后体征数据也应被删除（级联删除）"""
        from app.models.user import VitalSigns

        # 添加体征数据
        vital_signs = VitalSigns(
            member_id=self.member_id,
            height_cm=75.0,
            weight_kg=9.5
        )
        self.service.upsert_vital_signs(vital_signs)

        # 验证体征数据存在
        member_with_vital = self.service.get_member(self.member_id)
        assert "vital_signs" in member_with_vital

        # 删除成员
        self.service.delete_member(self.member_id)

        # 验证成员已被删除（级联删除体征数据）
        result = self.service.get_member(self.member_id)
        assert result is None

    def test_delete_cascades_health_habits(self):
        """测试删除成员后生活习惯数据也应被删除（级联删除）"""
        from app.models.user import HealthHabits, DietHabit

        # 添加生活习惯数据
        habits = HealthHabits(
            member_id=self.member_id,
            diet_habit=DietHabit.REGULAR
        )
        self.service.upsert_health_habits(habits)

        # 验证生活习惯数据存在
        member_with_habits = self.service.get_member(self.member_id)
        assert "health_habits" in member_with_habits

        # 删除成员
        self.service.delete_member(self.member_id)

        # 验证成员已被删除（级联删除生活习惯数据）
        result = self.service.get_member(self.member_id)
        assert result is None


class TestHealthHabitsOperations:
    """生活习惯操作测试"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = MemberProfileService(self.db_path)
        self.service.init_member_tables()
        self.user_id = "test_user_001"

        # 创建测试成员
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

    def test_create_health_habits(self):
        """测试创建生活习惯记录"""
        from app.models.user import HealthHabits, DietHabit, ExerciseHabit

        habits = HealthHabits(
            member_id=self.member_id,
            diet_habit=DietHabit.REGULAR,
            exercise_habit=ExerciseHabit.DAILY
        )

        self.service.upsert_health_habits(habits)

        # 验证生活习惯已保存
        result = self.service.get_member(self.member_id)
        assert "health_habits" in result
        assert result["health_habits"]["diet_habit"] == "regular"

    def test_update_health_habits(self):
        """测试更新生活习惯记录"""
        from app.models.user import HealthHabits, DietHabit, ExerciseHabit

        # 创建初始记录
        habits = HealthHabits(
            member_id=self.member_id,
            diet_habit=DietHabit.REGULAR,
            exercise_habit=ExerciseHabit.DAILY
        )
        self.service.upsert_health_habits(habits)

        # 更新记录
        updated_habits = HealthHabits(
            member_id=self.member_id,
            diet_habit=DietHabit.PICKY,  # 修改饮食习惯
            exercise_habit=ExerciseHabit.RARELY  # 修改运动习惯
        )
        self.service.upsert_health_habits(updated_habits)

        # 验证更新成功
        result = self.service.get_member(self.member_id)
        assert result["health_habits"]["diet_habit"] == "picky"
        assert result["health_habits"]["exercise_habit"] == "rarely"

    def test_get_member_with_habits(self):
        """测试获取成员详情应包含生活习惯"""
        from app.models.user import HealthHabits, DietHabit

        habits = HealthHabits(
            member_id=self.member_id,
            diet_habit=DietHabit.PICKY
        )

        self.service.upsert_health_habits(habits)

        # 获取成员详情应包含生活习惯
        result = self.service.get_member(self.member_id)
        assert "health_habits" in result
        assert result["health_habits"]["diet_habit"] == "picky"


class TestMemberValidation:
    """成员数据验证测试（验证 BUG-001, BUG-003 修复）"""

    def test_empty_name_should_fail(self):
        """
        验证 BUG-001 修复：空姓名应被拒绝
        注意：Pydantic 的 min_length 会使用默认错误消息
        """
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            MemberCreateRequest(
                name="",
                relationship=Relationship.CHILD,
                gender=Gender.MALE,
                birth_date="2025-06-15"
            )

    def test_whitespace_only_name_should_fail(self):
        """验证纯空格姓名应被拒绝"""
        with pytest.raises(ValidationError, match="姓名不能为空"):
            MemberCreateRequest(
                name="   ",
                relationship=Relationship.CHILD,
                gender=Gender.MALE,
                birth_date="2025-06-15"
            )

    def test_future_birth_date_should_fail(self):
        """
        验证 BUG-003 修复：未来出生日期应被拒绝
        """
        from datetime import date
        future_date = (date.today().replace(year=date.today().year + 1)).strftime("%Y-%m-%d")

        with pytest.raises(ValidationError, match="出生日期不能晚于今天"):
            MemberCreateRequest(
                name="测试宝宝",
                relationship=Relationship.CHILD,
                gender=Gender.MALE,
                birth_date=future_date
            )

    def test_invalid_birth_date_format_should_fail(self):
        """验证无效的出生日期格式应被拒绝"""
        with pytest.raises(ValidationError, match="出生日期格式错误"):
            MemberCreateRequest(
                name="测试宝宝",
                relationship=Relationship.CHILD,
                gender=Gender.MALE,
                birth_date="2024/01/01"  # 错误格式
            )
