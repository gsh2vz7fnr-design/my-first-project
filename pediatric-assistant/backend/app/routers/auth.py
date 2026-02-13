"""
认证路由 - 轻量级用户系统（无JWT/tokens）
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger
from typing import Optional

from app.services.conversation_service import conversation_service

router = APIRouter()


class RegisterRequest(BaseModel):
    """用户注册请求"""
    user_id: str
    nickname: Optional[str] = None
    email: Optional[str] = None


@router.post("/register")
async def register_user(request: RegisterRequest):
    """
    注册用户（或更新 last_login）

    Args:
        request: 注册请求

    Returns:
        dict: 用户信息
    """
    try:
        user = conversation_service.upsert_user(
            user_id=request.user_id,
            nickname=request.nickname,
            email=request.email
        )

        logger.info(f"用户注册/登录: {request.user_id}")

        return {
            "code": 0,
            "data": user,
            "message": "注册/登录成功"
        }

    except Exception as e:
        logger.error(f"用户注册失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}")
async def get_user(user_id: str):
    """
    获取用户信息（验证用户ID有效性）

    Args:
        user_id: 用户ID

    Returns:
        dict: 用户信息 + valid 字段
    """
    try:
        user = conversation_service.get_user(user_id)

        if user is None:
            return {
                "code": 404,
                "data": {"valid": False},
                "message": "用户不存在"
            }

        # 添加 valid 字段，前端依赖此字段判断用户ID是否有效
        user["valid"] = True
        return {
            "code": 0,
            "data": user,
            "message": "获取用户信息成功"
        }

    except Exception as e:
        logger.error(f"获取用户信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
