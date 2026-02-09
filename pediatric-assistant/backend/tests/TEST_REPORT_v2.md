# 测试执行报告 (v2.0)

**日期**: 2026-02-08
**状态**: ✅ 全部通过 (138 tests passed)

## 1. 概览
本次测试重点覆盖了健康档案模块的边界条件、数据校验及业务逻辑完整性。

| 模块 | 测试文件 | 覆盖内容 | 结果 |
|---|---|---|---|
| **边界测试** | `test_profile_edge_cases.py` | E-3, E-4, E-14, E-15, U-5 | ✅ Pass |
| **去重逻辑** | `test_profile_deduplication.py` | U-6 | ✅ Pass |
| **BMI计算** | `test_bmi_calculation.py` | U-1, U-2, E-1, E-2, E-5 | ✅ Pass |
| **成员管理** | `test_member_profile.py` | U-3, U-4, E-8, E-12 | ✅ Pass |
| **数据校验** | `test_profile_validation.py` | U-7 | ✅ Pass |
| **其他** | (现有测试文件) | 基础功能回归 | ✅ Pass |

## 2. 新增覆盖详情

### 2.1 边界值校验 (Edge Cases)
- **体重**: 成功拦截 1000kg 等异常输入 (Limit: 300kg)
- **身高**: 成功拦截 0.5cm 等异常输入 (Range: 20-250cm)
- **血糖**: 成功拦截 999 等异常输入 (Range: 0.5-50.0)
- **血压**: 成功拦截 收缩压 <= 舒张压 的逻辑错误

### 2.2 业务逻辑
- **去重**: 验证了 `apply_updates_from_message` 在接收到重复的过敏/病史信息时，不会生成重复的待确认记录。
- **年龄计算**: 实现了 `calculate_age_months`，能准确根据出生日期计算月龄。

### 2.3 修复的问题
- **Gender Unknown**: 修复了创建空档案时 `gender="unknown"` 导致的 Pydantic 校验错误。
- **Loose Validation**: 增强了 `upsert_vital_signs` 的校验逻辑，从"允许无效值但不计算"升级为"拒绝无效值并抛出异常"。

## 3. 下一步建议
- 建议在集成测试阶段增加 E-6 (断网测试) 和 E-7 (并发测试)。
- 前端需要适配后端的严格校验，做好错误提示展示。
