"""
Performance Monitoring Middleware

Tracks API response times and provides statistics.
Implements P50/P90/P95/P99 percentile calculations.
"""
import time
from collections import defaultdict
from typing import Dict, List
from fastapi import Request, Response
from loguru import logger


class PerformanceMonitor:
    """
    Performance monitoring middleware

    Tracks:
    - Request count per endpoint
    - Response times (min, max, avg, percentiles)
    - Slow request warnings
    """

    def __init__(self):
        """Initialize performance monitor"""
        self.metrics: Dict[str, List[float]] = defaultdict(list)
        self.request_counts: Dict[str, int] = defaultdict(int)

    async def log_request(self, request: Request, call_next):
        """
        Log request duration and update metrics

        Args:
            request: Incoming request
            call_next: Next middleware/route handler

        Returns:
            Response with timing headers
        """
        start_time = time.time()

        # Process request
        response: Response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time
        duration_ms = duration * 1000

        # Get endpoint path
        endpoint = request.url.path

        # Record metrics
        self.metrics[endpoint].append(duration_ms)
        self.request_counts[endpoint] += 1

        # Add response time header
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        response.headers["X-Response-Time-ms"] = f"{duration_ms:.0f}ms"

        # Warn on slow requests (>1s)
        if duration > 1.0:
            logger.warning(
                f"⚠️  Slow request: {request.method} {endpoint} "
                f"took {duration:.2f}s"
            )

        # Log very slow requests (>2s)
        if duration > 2.0:
            logger.error(
                f"🐌 Very slow request: {request.method} {endpoint} "
                f"took {duration:.2f}s"
            )

        return response

    def get_statistics(self) -> Dict:
        """
        Calculate statistics for all endpoints

        Returns:
            Dict with statistics per endpoint
        """
        import numpy as np

        stats = {}

        for endpoint, durations in self.metrics.items():
            if not durations:
                continue

            durations_array = np.array(durations)

            stats[endpoint] = {
                "count": len(durations),
                "total_requests": self.request_counts[endpoint],
                "avg_ms": float(np.mean(durations_array)),
                "median_ms": float(np.median(durations_array)),
                "min_ms": float(np.min(durations_array)),
                "max_ms": float(np.max(durations_array)),
                "std_dev_ms": float(np.std(durations_array)),
                "p50_ms": float(np.percentile(durations_array, 50)),
                "p90_ms": float(np.percentile(durations_array, 90)),
                "p95_ms": float(np.percentile(durations_array, 95)),
                "p99_ms": float(np.percentile(durations_array, 99)),
            }

        return stats

    def get_endpoint_statistics(self, endpoint: str) -> Dict:
        """
        Get statistics for a specific endpoint

        Args:
            endpoint: Endpoint path

        Returns:
            Statistics dict or empty dict if no data
        """
        all_stats = self.get_statistics()
        return all_stats.get(endpoint, {})

    def get_summary(self) -> Dict:
        """
        Get overall summary statistics

        Returns:
            Summary dict with aggregated stats
        """
        all_stats = self.get_statistics()

        if not all_stats:
            return {
                "total_requests": 0,
                "endpoints": 0,
                "avg_response_time_ms": 0,
            }

        total_requests = sum(s["count"] for s in all_stats.values())

        # Calculate weighted average response time
        weighted_sum = sum(
            s["avg_ms"] * s["count"] for s in all_stats.values()
        )
        avg_response_time = weighted_sum / total_requests if total_requests > 0 else 0

        # Find slowest endpoint
        slowest_endpoint = max(all_stats.items(), key=lambda x: x[1]["avg_ms"])

        return {
            "total_requests": total_requests,
            "endpoints": len(all_stats),
            "avg_response_time_ms": avg_response_time,
            "slowest_endpoint": {
                "path": slowest_endpoint[0],
                "avg_ms": slowest_endpoint[1]["avg_ms"],
            },
        }

    def reset_metrics(self):
        """Clear all recorded metrics"""
        self.metrics.clear()
        self.request_counts.clear()

    def print_statistics(self):
        """Print statistics to console"""
        stats = self.get_statistics()

        print("\n" + "=" * 70)
        print("📊 Performance Statistics")
        print("=" * 70)

        if not stats:
            print("No metrics recorded yet.")
            return

        print(f"\n{'Endpoint':<40} {'Count':<8} {'Avg':<8} {'P95':<8} {'Max':<8}")
        print("-" * 70)

        # Sort by average response time (slowest first)
        sorted_endpoints = sorted(stats.items(), key=lambda x: x[1]["avg_ms"], reverse=True)

        for endpoint, stat in sorted_endpoints:
            print(
                f"{endpoint:<40} {stat['count']:<8} "
                f"{stat['avg_ms']:<7.0f}ms {stat['p95_ms']:<7.0f}ms "
                f"{stat['max_ms']:<7.0f}ms"
            )

        # Print summary
        summary = self.get_summary()
        print("-" * 70)
        print(f"Total Requests: {summary['total_requests']}")
        print(f"Average Response Time: {summary['avg_response_time_ms']:.0f}ms")
        print(f"Slowest Endpoint: {summary['slowest_endpoint']['path']} "
              f"({summary['slowest_endpoint']['avg_ms']:.0f}ms avg)")
        print("=" * 70 + "\n")


# Global instance
performance_monitor = PerformanceMonitor()
