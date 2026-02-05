"""
健康档案路由
"""
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.models.user import HealthProfile, BabyInfo

router = APIRouter()


@router.get("/{user_id}")
async def get_profile(user_id: str):
    """
    获取健康档案

    Args:
        user_id: 用户ID

    Returns:
        dict: 健康档案
    """
    try:
        # TODO: 从数据库加载健康档案
        # 这里返回示例数据
        profile = HealthProfile(
            user_id=user_id,
            baby_info=BabyInfo(
                age_months=6,
                weight_kg=8.5,
                gender="male"
            ),
            allergy_history=[],
            medical_history=[],
            medication_history=[]
        )

        return {
            "code": 0,
            "data": profile.model_dump()
        }

    except Exception as e:
        logger.error(f"获取健康档案失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{user_id}")
async def update_profile(user_id: str, profile: HealthProfile):
    """
    更新健康档案

    Args:
        user_id: 用户ID
        profile: 健康档案

    Returns:
        dict: 更新结果
    """
    try:
        # TODO: 更新数据库中的健康档案
        logger.info(f"更新用户 {user_id} 的健康档案")

        return {
            "code": 0,
            "message": "更新成功",
            "data": profile.model_dump()
        }

    except Exception as e:
        logger.error(f"更新健康档案失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{user_id}/confirm")
async def confirm_profile_update(user_id: str, updates: dict):
    """
    确认档案更新（用于强特征确认）

    Args:
        user_id: 用户ID
        updates: 待确认的更新

    Returns:
        dict: 确认结果
    """
    try:
        # TODO: 处理用户确认的档案更新
        logger.info(f"用户 {user_id} 确认档案更新: {updates}")

        return {
            "code": 0,
            "message": "确认成功"
        }

    except Exception as e:
        logger.error(f"确认档案更新失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
