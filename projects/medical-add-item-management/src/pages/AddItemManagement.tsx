import React, { useState, useMemo, useCallback, lazy, Suspense } from 'react';
import {
  Table,
  Button,
  Space,
  Tag,
  Input,
  Select,
  DatePicker,
  message,
  Popconfirm,
  Badge,
  Typography
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, SearchOutlined, ClearOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import type { AddItemOrder } from '../types';
import { StatusMap, StatusColorMap } from '../types';
import { mockOrders } from '../mock/data';
import './AddItemManagement.css';

// 懒加载模态框组件以提升初始加载性能
const AddItemModal = lazy(() => import('../components/AddItemModal'));
const OrderDetailModal = lazy(() => import('../components/OrderDetailModal'));

const { RangePicker } = DatePicker;
const { Option } = Select;
const { Text } = Typography;

const AddItemManagement: React.FC = () => {
  const [dataSource, setDataSource] = useState<AddItemOrder[]>(mockOrders);
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);

  // 弹窗状态
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [currentOrder, setCurrentOrder] = useState<AddItemOrder | null>(null);

  // 分页
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: mockOrders.length
  });

  // 增强的搜索过滤 - 支持更多字段搜索
  const filteredData = useMemo(() => {
    let filtered = [...dataSource];

    // 搜索过滤 - 扩展到更多字段
    if (searchText) {
      const searchLower = searchText.toLowerCase();
      filtered = filtered.filter(item => {
        // 搜索基本字段
        const basicMatch =
          item.userName.toLowerCase().includes(searchLower) ||
          item.id.toLowerCase().includes(searchLower) ||
          item.reportId.toLowerCase().includes(searchLower) ||
          item.userId.toLowerCase().includes(searchLower) ||
          item.userPhone.includes(searchText) ||
          item.operator.toLowerCase().includes(searchLower);

        // 搜索加项项目名称
        const itemMatch = item.items.some(addItem =>
          addItem.itemName.toLowerCase().includes(searchLower)
        );

        // 搜索总价
        const priceMatch = item.totalPrice.toString().includes(searchText);

        return basicMatch || itemMatch || priceMatch;
      });
    }

    // 状态过滤
    if (statusFilter) {
      filtered = filtered.filter(item => item.status === statusFilter);
    }

    // 时间范围过滤
    if (dateRange) {
      filtered = filtered.filter(item => {
        const itemDate = dayjs(item.createTime);
        return itemDate.isAfter(dateRange[0]) && itemDate.isBefore(dateRange[1]);
      });
    }

    return filtered;
  }, [dataSource, searchText, statusFilter, dateRange]);

  // 清除所有筛选条件
  const handleClearFilters = useCallback(() => {
    setSearchText('');
    setStatusFilter('');
    setDateRange(null);
    message.info('已清除所有筛选条件');
  }, []);

  // 判断是否有活动的筛选条件
  const hasActiveFilters = searchText || statusFilter || dateRange;

  // 处理新增
  const handleAdd = useCallback((order: AddItemOrder) => {
    setDataSource(prev => [order, ...prev]);
    setPagination(prev => ({ ...prev, total: prev.total + 1 }));
    message.success('加项单创建成功！');
    setAddModalVisible(false);
  }, []);

  // 处理编辑
  const handleEdit = useCallback((order: AddItemOrder) => {
    setDataSource(prev => prev.map(item =>
      item.id === order.id ? order : item
    ));
    message.success('加项单更新成功！');
    setEditModalVisible(false);
  }, []);

  // 处理删除
  const handleDelete = useCallback((id: string) => {
    setDataSource(prev => {
      const newData = prev.filter(item => item.id !== id);
      setPagination(p => ({ ...p, total: newData.length }));
      return newData;
    });
    message.success('删除成功！');
  }, []);

  // 处理导出
  const handleExport = useCallback((record: AddItemOrder) => {
    // 模拟导出功能
    const content = `
加项单编号: ${record.id}
用户姓名: ${record.userName}
手机号: ${record.userPhone}
体检编号: ${record.reportId}
操作人: ${record.operator}
创建时间: ${record.createTime}
状态: ${StatusMap[record.status]}

加项明细:
${record.items.map((item, index) => `
${index + 1}. ${item.itemName}
   价格: ¥${item.price}
   备注: ${item.remark}
`).join('\n')}

总价: ¥${record.totalPrice}
    `.trim();

    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `加项单_${record.id}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    message.success('导出成功！');
  }, []);

  // 批量导出
  const handleBatchExport = useCallback(() => {
    if (filteredData.length === 0) {
      message.warning('没有可导出的数据');
      return;
    }

    const content = filteredData.map(record => `
加项单编号: ${record.id}
用户姓名: ${record.userName}
手机号: ${record.userPhone}
体检编号: ${record.reportId}
操作人: ${record.operator}
创建时间: ${record.createTime}
状态: ${StatusMap[record.status]}
加项明细: ${record.items.map(item => item.itemName).join(', ')}
总价: ¥${record.totalPrice}
${'='.repeat(60)}
`).join('\n');

    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `加项单汇总_${dayjs().format('YYYY-MM-DD')}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    message.success(`成功导出 ${filteredData.length} 条记录！`);
  }, [filteredData]);

  // 高亮搜索文本的渲染函数 - 使用 useCallback 优化
  const highlightText = useCallback((text: string, highlight: string) => {
    if (!highlight) return text;

    const parts = text.split(new RegExp(`(${highlight})`, 'gi'));
    return (
      <span>
        {parts.map((part, index) =>
          part.toLowerCase() === highlight.toLowerCase() ? (
            <Text key={index} mark>{part}</Text>
          ) : (
            <span key={index}>{part}</span>
          )
        )}
      </span>
    );
  }, []);

  // 处理查看详情
  const handleViewDetail = useCallback((record: AddItemOrder) => {
    setCurrentOrder(record);
    setDetailModalVisible(true);
  }, []);

  // 处理编辑点击
  const handleEditClick = useCallback((record: AddItemOrder) => {
    setCurrentOrder(record);
    setEditModalVisible(true);
  }, []);

  // 表格列定义 - 使用 useMemo 优化，添加搜索高亮
  const columns: ColumnsType<AddItemOrder> = useMemo(() => [
    {
      title: '加项单编号',
      dataIndex: 'id',
      key: 'id',
      width: 150,
      fixed: 'left',
      render: (text) => highlightText(text, searchText)
    },
    {
      title: '用户姓名',
      dataIndex: 'userName',
      key: 'userName',
      width: 100,
      render: (text) => highlightText(text, searchText)
    },
    {
      title: '用户ID',
      dataIndex: 'userId',
      key: 'userId',
      width: 100,
      render: (text) => highlightText(text, searchText)
    },
    {
      title: '手机号',
      dataIndex: 'userPhone',
      key: 'userPhone',
      width: 120,
      render: (text) => highlightText(text, searchText)
    },
    {
      title: '体检编号',
      dataIndex: 'reportId',
      key: 'reportId',
      width: 150,
      render: (text) => highlightText(text, searchText)
    },
    {
      title: '加项项目',
      dataIndex: 'items',
      key: 'items',
      width: 250,
      render: (items: AddItemOrder['items']) => (
        <div>
          {items.map((item, index) => (
            <div key={index} style={{ marginBottom: 4 }}>
              {index + 1}. {highlightText(item.itemName, searchText)} (¥{item.price})
            </div>
          ))}
        </div>
      )
    },
    {
      title: '总价',
      dataIndex: 'totalPrice',
      key: 'totalPrice',
      width: 100,
      render: (price: number) => (
        <span style={{ fontWeight: 'bold', color: '#ff4d4f' }}>
          {highlightText(`¥${price}`, searchText)}
        </span>
      ),
      sorter: (a, b) => a.totalPrice - b.totalPrice
    },
    {
      title: '操作人',
      dataIndex: 'operator',
      key: 'operator',
      width: 100,
      render: (text) => highlightText(text, searchText)
    },
    {
      title: '创建时间',
      dataIndex: 'createTime',
      key: 'createTime',
      width: 180,
      sorter: (a, b) => dayjs(a.createTime).unix() - dayjs(b.createTime).unix()
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: AddItemOrder['status']) => (
        <Tag color={StatusColorMap[status]}>{StatusMap[status]}</Tag>
      )
    },
    {
      title: '操作',
      key: 'action',
      width: 280,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            onClick={() => handleViewDetail(record)}
          >
            查看详情
          </Button>
          <Button
            type="link"
            size="small"
            onClick={() => handleEditClick(record)}
          >
            编辑
          </Button>
          <Button
            type="link"
            size="small"
            onClick={() => handleExport(record)}
          >
            导出
          </Button>
          <Popconfirm
            title="确定要删除这条记录吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ], [searchText, highlightText, handleViewDetail, handleEditClick, handleExport, handleDelete]);

  return (
    <div className="add-item-management">
      <div className="page-header">
        <h1>体检报告加项管理</h1>
      </div>

      {/* 搜索和筛选区域 */}
      <div className="filter-section">
        <Space size="middle" wrap>
          <Input
            placeholder="搜索姓名/编号/手机/操作人/项目名..."
            prefix={<SearchOutlined />}
            style={{ width: 350 }}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            allowClear
          />
          <Select
            placeholder="选择状态"
            style={{ width: 150 }}
            value={statusFilter || undefined}
            onChange={(value) => setStatusFilter(value)}
            allowClear
          >
            <Option value="pending">待支付</Option>
            <Option value="paid">已支付</Option>
            <Option value="completed">已完成</Option>
          </Select>
          <RangePicker
            value={dateRange}
            onChange={(dates) => setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)}
            placeholder={['开始时间', '结束时间']}
          />
          {hasActiveFilters && (
            <Button
              icon={<ClearOutlined />}
              onClick={handleClearFilters}
            >
              清除筛选
            </Button>
          )}
          <Button
            type="default"
            onClick={handleBatchExport}
            disabled={filteredData.length === 0}
          >
            批量导出
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setAddModalVisible(true)}
          >
            新增加项
          </Button>
        </Space>
      </div>

      {/* 搜索结果统计 */}
      {hasActiveFilters && (
        <div style={{ marginTop: 16, marginBottom: 8 }}>
          <Space>
            <Badge
              count={filteredData.length}
              showZero
              color="#1890ff"
              overflowCount={9999}
            />
            <Text type="secondary">
              从 {dataSource.length} 条记录中筛选出 {filteredData.length} 条结果
            </Text>
          </Space>
        </div>
      )}

      {/* 表格 */}
      <Table
        columns={columns}
        dataSource={filteredData}
        rowKey="id"
        pagination={{
          ...pagination,
          total: filteredData.length,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 条记录`,
          onChange: (page, pageSize) => {
            setPagination({ ...pagination, current: page, pageSize });
          }
        }}
        scroll={{ x: 1600 }}
      />

      {/* 新增加项弹窗 */}
      <Suspense fallback={null}>
        <AddItemModal
          visible={addModalVisible}
          onCancel={() => setAddModalVisible(false)}
          onSubmit={handleAdd}
        />
      </Suspense>

      {/* 查看详情弹窗 */}
      {currentOrder && (
        <Suspense fallback={null}>
          <OrderDetailModal
            visible={detailModalVisible}
            order={currentOrder}
            onCancel={() => setDetailModalVisible(false)}
          />
        </Suspense>
      )}

      {/* 编辑弹窗 */}
      {currentOrder && (
        <Suspense fallback={null}>
          <AddItemModal
            visible={editModalVisible}
            onCancel={() => setEditModalVisible(false)}
            onSubmit={handleEdit}
            initialData={currentOrder}
          />
        </Suspense>
      )}
    </div>
  );
};

export default AddItemManagement;
