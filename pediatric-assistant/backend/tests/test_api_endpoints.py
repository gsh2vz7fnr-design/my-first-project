"""API 端点单元测试

Bug #6: 覆盖 main.py 的 API 端点
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    """创建测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestRootEndpoint:
    """Bug #6: 根路径端点测试"""

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client):
        """TC-API-01: 根路径返回应用信息"""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "app" in data
        assert "version" in data
        assert data["status"] == "running"


class TestHealthCheck:
    """Bug #6: 健康检查端点测试"""

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """TC-API-02: 健康检查返回 healthy"""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestPerformanceMetrics:
    """Bug #6: 性能指标端点测试"""

    @pytest.mark.asyncio
    async def test_performance_metrics(self, client):
        """TC-API-03: 性能指标端点返回统计数据"""
        response = await client.get("/metrics/performance")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data


class TestPerformanceSummary:
    """Bug #6: 性能摘要端点测试"""

    @pytest.mark.asyncio
    async def test_performance_summary(self, client):
        """TC-API-04: 性能摘要端点返回摘要数据"""
        response = await client.get("/metrics/performance/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data
