# 健康档案模块测试覆盖率报告

**生成时间**: 2026-02-08 00:28 +0800
**测试工具**: pytest + pytest-cov
**覆盖率工具**: coverage.py v7.13.3

---

## 执行摘要

| 指标 | 数值 |
|------|------|
| **总体覆盖率** | **68%** |
| **总语句数** | 601 |
| **已覆盖语句** | 408 |
| **未覆盖语句** | 193 |
| **测试用例数** | 53 |

---

## 分模块覆盖率详情

### 1. app/models/user.py - 100% ✅

| 指标 | 数值 |
|------|------|
| **覆盖率** | **100%** |
| **语句数** | 232 |
| **未覆盖** | 0 |

**说明**: 所有 Pydantic 模型类完全覆盖，包括：
- `MemberProfile`
- `MemberCreateRequest`
- `VitalSigns`
- `HealthHabits`
- `AllergyRecord`
- `MedicalHistoryRecord`
- `FamilyHistoryRecord`
- `MedicationRecord`
- `HealthRecord`
- 枚举类 (`Relationship`, `Gender`, `BMIStatus`, 等)

---

### 2. app/services/profile_service.py - 48% ⚠️

| 指标 | 数值 |
|------|------|
| **覆盖率** | **48%** |
| **语句数** | 369 |
| **已覆盖** | 176 |
| **未覆盖** | 193 |

#### 未覆盖代码行号

```
29-31, 35-65, 69-77, 81-116, 120-126, 130-154, 160-212, 229-254,
260-273, 278-288, 301-314, 326-327, 331-362, 365-371, 383, 489,
499, 507, 539-557, 561-566, 599-620, 961-987, 999-1011, 1017-1029,
1034-1046, 1052-1064, 1070-1083
```

#### 未覆盖功能分析

| 功能模块 | 未覆盖行号 | 说明 |
|----------|------------|------|
| **HealthRecordsService** | 29-65, 69-116, 120-212 | 健康记录服务类（完整） |
| **年龄计算相关** | 229-254, 260-273 | `calculate_age` 等方法 |
| **成员更新/删除** | 278-288, 301-314 | `update_member`, `delete_member` |
| **生活习惯操作** | 326-362, 365-371 | `upsert_health_habits` |
| **健康史CRUD** | 539-620 | `HealthHistoryService` 部分方法 |
| **其他服务方法** | 961-1083 | 未使用的辅助方法 |

---

## 覆盖率可视化

```
整体覆盖率: 68%
████████████████████████████░░░░░░░░░░░░░░░░░░░░░░

分模块覆盖率:
┌─────────────────────────────────────────────────┐
│ models/user.py          100% ████████████      │
│ services/profile_service  48% ██████░░░░░░░░░░ │
└─────────────────────────────────────────────────┘
```

---

## 未覆盖功能详解

### 1. HealthRecordsService 类（未使用）

**位置**: 第 29-212 行

**未覆盖原因**: 这是一个独立的服务类，用于健康记录管理，但当前测试主要针对 `MemberProfileService` 和 `HealthHistoryService`。

```python
class HealthRecordsService:
    """健康记录管理服务"""
    # 完整未覆盖
```

**建议**: 如果此服务类不再使用，建议删除；如果需要使用，需要补充测试用例。

---

### 2. 年龄计算相关方法

**位置**: 第 229-273 行

**未覆盖方法**:
- `calculate_age()`
- `calculate_age_from_birthdate()`

**建议测试用例**:
```python
def test_calculate_age_newborn():
    """测试新生儿年龄计算"""
    # 出生日期: 2024-01-01, 当前日期: 2024-06-01
    # 预期: 5个月

def test_calculate_age_adult():
    """测试成人年龄计算"""
    # 出生日期: 1990-01-01
    # 预期: 34岁
```

---

### 3. 成员更新方法

**位置**: 第 278-314 行

**未覆盖方法**:
- `update_member()`

**原因**: 当前测试中没有 `TestMemberUpdate` 测试类

**建议**: 补充成员更新测试用例

---

### 4. 成员删除方法

**位置**: 第 326-371 行

**未覆盖方法**:
- `delete_member()`

**原因**: 当前测试中没有 `TestMemberDeletion` 测试类

**建议**: 补充成员删除测试用例

---

### 5. 生活习惯操作

**位置**: 第 599-620 行

**未覆盖方法**:
- `upsert_health_habits()` 部分

**原因**: 当前测试中 `TestHealthHabitsOperations` 类被移除

**建议**: 重新添加生活习惯测试

---

## 测试用例与覆盖率对应关系

| 测试文件 | 测试用例数 | 覆盖的服务方法 |
|----------|------------|----------------|
| `test_bmi_calculation.py` | 23 | `_calculate_bmi()`, `_calculate_bmi_status()` |
| `test_member_profile.py` | 12 | `create_member()`, `get_member()`, `get_members()`, `upsert_vital_signs()` |
| `test_health_history.py` | 18 | `add_allergy()`, `get_allergy_history()`, `get_history_summary()` 等 |

---

## 提高覆盖率的建议

### 高优先级

1. **补充成员更新测试** (`update_member`)
   ```python
   class TestMemberUpdate:
       def test_update_member_name(self)
       def test_update_member_gender(self)
       def test_update_member_birth_date(self)
       def test_id_card_number_immutable(self)
   ```

2. **补充成员删除测试** (`delete_member`)
   ```python
   class TestMemberDeletion:
       def test_delete_member(self)
       def test_delete_nonexistent_member(self)
       def test_delete_member_cascades_to_vital_signs(self)
   ```

3. **补充生活习惯测试** (`upsert_health_habits`)
   ```python
   class TestHealthHabitsOperations:
       def test_create_health_habits(self)
       def test_update_health_habits(self)
   ```

### 中优先级

4. **年龄计算测试**
   ```python
   class TestAgeCalculation:
       def test_calculate_age_newborn(self)
       def test_calculate_age_child_years(self)
       def test_calculate_age_adult(self)
       def test_calculate_age_future_birth_date(self)
   ```

5. **健康史记录更新/删除测试**
   ```python
   class TestHealthHistoryUpdateDelete:
       def test_update_allergy_record(self)
       def test_delete_allergy_record(self)
       def test_update_medical_history(self)
       ```

### 低优先级

6. **决定是否保留 `HealthRecordsService`**
   - 如果不再使用，删除该类
   - 如果需要使用，补充完整测试

---

## HTML 报告位置

详细的 HTML 格式覆盖率报告已生成在：

```
pediatric-assistant/backend/htmlcov/index.html
```

使用浏览器打开此文件可查看：
- 每个文件的详细覆盖率
- 逐行代码覆盖情况
- 分支覆盖率
- 函数覆盖率

---

## 覆盖率目标

| 当前状态 | 目标 | 差距 |
|----------|------|------|
| 68% | 85% | -17% |

**达成目标需要**:
1. 补充成员更新/删除测试 (+10%)
2. 补充生活习惯测试 (+5%)
3. 补充年龄计算测试 (+3%)
4. 决定 `HealthRecordsService` 去留 (+5%)

---

## 命令行参考

```bash
# 生成覆盖率报告
python -m pytest tests/ --cov=app.services.profile_service --cov=app.models.user --cov-report=term-missing

# 生成HTML报告
python -m pytest tests/ --cov=app.services.profile_service --cov=app.models.user --cov-report=html

# 生成XML报告（用于CI/CD）
python -m pytest tests/ --cov=app.services.profile_service --cov=app.models.user --cov-report=xml

# 查看特定模块覆盖率
python -m pytest tests/ --cov=app.services.profile_service.MemberProfileService --cov-report=term-missing

# 设置覆盖率阈值（低于80%则失败）
python -m pytest tests/ --cov=app.services.profile_service --cov-fail-under=80
```

---

**报告生成时间**: 2026-02-08 00:28 +0800
**覆盖率工具**: coverage.py v7.13.3
**测试工具**: pytest 9.0.2
