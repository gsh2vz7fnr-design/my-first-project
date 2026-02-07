"""
pytest 配置文件
"""
import pytest
import sys
import os
import tempfile

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def test_db_path():
    """创建临时测试数据库路径"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # 清理临时文件
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def mock_user_id():
    """模拟用户ID"""
    return "test_user_001"


@pytest.fixture
def mock_member_id():
    """模拟成员ID"""
    return "test_member_001"


@pytest.fixture
def temp_db():
    """创建临时数据库路径用于测试类"""
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except:
        pass
