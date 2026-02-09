"""任务队列取消精度测试"""
import pytest
import tempfile
import os
import json
import uuid
from datetime import datetime, timedelta
from app.services.profile_service import ProfileService


class TestCancelPendingTask:
    def setup_method(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = ProfileService(self.db_path)
        self.service.init_db()

    def teardown_method(self):
        try:
            os.unlink(self.db_path)
        except Exception:
            pass

    def _insert_task(self, user_id, conversation_id, status="pending"):
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        execute_at = (datetime.now() + timedelta(minutes=30)).isoformat()
        payload = json.dumps({"user_id": user_id, "conversation_id": conversation_id})
        with self.service._connect() as conn:
            conn.execute(
                "INSERT INTO task_queue VALUES (?,?,?,?,?,?,?)",
                (task_id, "extract_profile", payload, execute_at, status, now, now))
            conn.commit()
        return task_id

    def _get_status(self, task_id):
        with self.service._connect() as conn:
            row = conn.execute("SELECT status FROM task_queue WHERE id=?", (task_id,)).fetchone()
        return row["status"] if row else None

    def test_cancels_matching(self):
        """TC-TQ-001: 正确取消匹配任务"""
        tid = self._insert_task("user_A", "conv_001")
        self.service._cancel_pending_task("user_A", "conv_001")
        assert self._get_status(tid) == "cancelled"

    def test_no_cross_user_cancel(self):
        """TC-TQ-002: 不取消其他用户的任务"""
        tid = self._insert_task("user_B", "conv_001")
        self.service._cancel_pending_task("user_A", "conv_001")
        assert self._get_status(tid) == "pending"

    def test_no_cross_conv_cancel(self):
        """TC-TQ-003: 不取消其他对话的任务"""
        tid = self._insert_task("user_A", "conv_002")
        self.service._cancel_pending_task("user_A", "conv_001")
        assert self._get_status(tid) == "pending"

    def test_skip_completed(self):
        """TC-TQ-004: 不影响已完成任务"""
        tid = self._insert_task("user_A", "conv_001", status="completed")
        self.service._cancel_pending_task("user_A", "conv_001")
        assert self._get_status(tid) == "completed"

    def test_no_error_on_empty(self):
        """TC-TQ-005: 无匹配任务不报错"""
        self.service._cancel_pending_task("user_X", "conv_999")
