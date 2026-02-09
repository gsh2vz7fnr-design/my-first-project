"""PerformanceMonitor 单元测试

Bug #1: 覆盖 get_summary()、get_statistics() 等方法
"""
import pytest
from app.middleware.performance import PerformanceMonitor


class TestGetSummaryEmptyMetrics:
    """Bug #1: 空指标时 get_summary() 不崩溃"""

    def test_get_summary_empty_metrics(self):
        """TC-PM-01: 空指标时 get_summary() 应返回 total_requests=0，不抛异常"""
        monitor = PerformanceMonitor()
        summary = monitor.get_summary()
        assert summary["total_requests"] == 0
        assert summary["endpoints"] == 0
        assert summary["avg_response_time_ms"] == 0


class TestGetStatistics:
    """Bug #1: get_statistics() 边界条件测试"""

    def test_get_statistics_empty(self):
        """TC-PM-02: 空指标时 get_statistics() 返回空 dict"""
        monitor = PerformanceMonitor()
        assert monitor.get_statistics() == {}

    def test_get_statistics_single_request(self):
        """TC-PM-03: 单个请求后统计正确"""
        monitor = PerformanceMonitor()
        monitor.metrics["/api/test"].append(100.0)
        monitor.request_counts["/api/test"] = 1
        stats = monitor.get_statistics()
        assert "/api/test" in stats
        assert stats["/api/test"]["count"] == 1
        assert stats["/api/test"]["avg_ms"] == 100.0

    def test_get_statistics_empty_duration_list(self):
        """TC-PM-04: 端点存在但 durations 为空列表时应跳过"""
        monitor = PerformanceMonitor()
        # 有 key 但 durations 列表为空（边界情况）
        monitor.metrics["/api/test"] = []
        monitor.request_counts["/api/test"] = 0
        stats = monitor.get_statistics()
        # 空 durations 应该被跳过
        assert "/api/test" not in stats


class TestGetSummaryWithData:
    """Bug #1: 有数据时 get_summary() 返回完整信息"""

    def test_get_summary_with_data(self):
        """TC-PM-05: get_summary() 含数据时返回 slowest_endpoint"""
        monitor = PerformanceMonitor()
        monitor.metrics["/fast"].append(10.0)
        monitor.metrics["/slow"].append(500.0)
        monitor.request_counts["/fast"] = 1
        monitor.request_counts["/slow"] = 1
        summary = monitor.get_summary()
        assert summary["total_requests"] == 2
        assert summary["endpoints"] == 2
        assert summary["slowest_endpoint"]["path"] == "/slow"
        assert summary["slowest_endpoint"]["avg_ms"] == 500.0

    def test_reset_then_summary(self):
        """TC-PM-06: reset_metrics() 清空后 get_summary() 安全"""
        monitor = PerformanceMonitor()
        monitor.metrics["/api"].append(50.0)
        monitor.request_counts["/api"] = 1
        monitor.reset_metrics()
        summary = monitor.get_summary()
        assert summary["total_requests"] == 0
        assert summary["endpoints"] == 0


class TestGetEndpointStatistics:
    """Bug #1: get_endpoint_statistics() 边界测试"""

    def test_get_endpoint_statistics_nonexistent(self):
        """TC-PM-07: 不存在的端点返回空 dict"""
        monitor = PerformanceMonitor()
        assert monitor.get_endpoint_statistics("/nonexistent") == {}

    def test_get_endpoint_statistics_exists(self):
        """TC-PM-08: 存在的端点返回正确统计"""
        monitor = PerformanceMonitor()
        monitor.metrics["/api/test"].append(100.0)
        monitor.request_counts["/api/test"] = 1
        stats = monitor.get_endpoint_statistics("/api/test")
        assert stats["count"] == 1
        assert stats["avg_ms"] == 100.0


class TestPrintStatistics:
    """Bug #1: print_statistics() 不应崩溃"""

    def test_print_statistics_empty(self, capsys):
        """TC-PM-09: 空指标时 print_statistics() 不应崩溃"""
        monitor = PerformanceMonitor()
        monitor.print_statistics()
        captured = capsys.readouterr()
        assert "No metrics recorded yet" in captured.out

    def test_print_statistics_with_data(self, capsys):
        """TC-PM-10: 有数据时 print_statistics() 正确输出"""
        monitor = PerformanceMonitor()
        monitor.metrics["/api/test"].append(100.0)
        monitor.request_counts["/api/test"] = 1
        monitor.print_statistics()
        captured = capsys.readouterr()
        assert "/api/test" in captured.out
        assert "Performance Statistics" in captured.out
