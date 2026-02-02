import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Modal,
  Form,
  Input,
  InputNumber,
  Button,
  Space,
  Select,
  Divider,
  Card,
  message
} from 'antd';
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import type { AddItemOrder, User, AddItem } from '../types';
import { mockUsers } from '../mock/data';

const { TextArea } = Input;

interface AddItemModalProps {
  visible: boolean;
  onCancel: () => void;
  onSubmit: (order: AddItemOrder) => void;
  initialData?: AddItemOrder;
}

const AddItemModal: React.FC<AddItemModalProps> = ({
  visible,
  onCancel,
  onSubmit,
  initialData
}) => {
  const [form] = Form.useForm();
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [items, setItems] = useState<AddItem[]>([{ itemName: '', price: 0, remark: '' }]);
  const [totalPrice, setTotalPrice] = useState(0);

  useEffect(() => {
    if (visible && initialData) {
      // 编辑模式
      const user = mockUsers.find(u => u.id === initialData.userId);
      setSelectedUser(user || null);
      setItems(initialData.items);
      calculateTotal(initialData.items);
    } else if (visible) {
      // 新增模式
      resetForm();
    }
  }, [visible, initialData]);

  const resetForm = useCallback(() => {
    form.resetFields();
    setSelectedUser(null);
    setItems([{ itemName: '', price: 0, remark: '' }]);
    setTotalPrice(0);
  }, [form]);

  const calculateTotal = useCallback((currentItems: AddItem[]) => {
    const total = currentItems.reduce((sum, item) => sum + (item.price || 0), 0);
    setTotalPrice(total);
  }, []);

  const handleUserSelect = useCallback((userId: string) => {
    const user = mockUsers.find(u => u.id === userId);
    setSelectedUser(user || null);
  }, []);

  const handleAddItem = useCallback(() => {
    const newItems = [...items, { itemName: '', price: 0, remark: '' }];
    setItems(newItems);
  }, [items]);

  const handleRemoveItem = useCallback((index: number) => {
    if (items.length === 1) {
      message.warning('至少保留一个加项项目');
      return;
    }
    const newItems = items.filter((_, i) => i !== index);
    setItems(newItems);
    calculateTotal(newItems);
  }, [items, calculateTotal]);

  const handleItemChange = useCallback((index: number, field: keyof AddItem, value: any) => {
    const newItems = [...items];
    newItems[index] = { ...newItems[index], [field]: value };
    setItems(newItems);
    if (field === 'price') {
      calculateTotal(newItems);
    }
  }, [items, calculateTotal]);

  const handleSubmit = useCallback(() => {
    if (!selectedUser) {
      message.error('请选择用户');
      return;
    }

    // 验证所有项目是否填写完整
    const hasEmptyItem = items.some(
      item => !item.itemName || !item.price || !item.remark
    );
    if (hasEmptyItem) {
      message.error('请完整填写所有加项信息');
      return;
    }

    const order: AddItemOrder = {
      id: initialData?.id || `AO${dayjs().format('YYYYMMDDHHmmss')}`,
      userId: selectedUser.id,
      userName: selectedUser.name,
      userPhone: selectedUser.phone,
      reportId: selectedUser.reportId,
      items: items,
      totalPrice: totalPrice,
      operator: '当前操作员', // 实际应该从登录信息获取
      createTime: initialData?.createTime || dayjs().format('YYYY-MM-DD HH:mm:ss'),
      status: initialData?.status || 'pending'
    };

    onSubmit(order);
    resetForm();
  }, [selectedUser, items, totalPrice, initialData, onSubmit, resetForm]);

  // 使用 useMemo 优化用户选项
  const userOptions = useMemo(() =>
    mockUsers.map(user => ({
      value: user.id,
      label: `${user.name} - ${user.phone}`
    })),
    []
  );

  return (
    <Modal
      title={initialData ? '编辑加项单' : '新增加项'}
      open={visible}
      onCancel={onCancel}
      onOk={handleSubmit}
      width={800}
      okText="确认"
      cancelText="取消"
    >
      <Form form={form} layout="vertical">
        {/* 用户选择 */}
        <Form.Item label="选择用户" required>
          <Select
            placeholder="请搜索并选择用户"
            showSearch
            value={selectedUser?.id}
            onChange={handleUserSelect}
            filterOption={(input, option) =>
              (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
            }
            options={userOptions}
            disabled={!!initialData}
          />
        </Form.Item>

        {/* 用户信息展示 */}
        {selectedUser && (
          <Card size="small" style={{ marginBottom: 16, background: '#f5f5f5' }}>
            <Space direction="vertical" size="small">
              <div><strong>姓名：</strong>{selectedUser.name}</div>
              <div><strong>手机号：</strong>{selectedUser.phone}</div>
              <div><strong>体检编号：</strong>{selectedUser.reportId}</div>
            </Space>
          </Card>
        )}

        <Divider>加项明细</Divider>

        {/* 加项列表 */}
        {items.map((item, index) => (
          <Card
            key={index}
            size="small"
            style={{ marginBottom: 12 }}
            title={`项目 ${index + 1}`}
            extra={
              items.length > 1 && (
                <Button
                  type="text"
                  danger
                  size="small"
                  icon={<MinusCircleOutlined />}
                  onClick={() => handleRemoveItem(index)}
                >
                  删除
                </Button>
              )
            }
          >
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Form.Item label="项目名称" style={{ marginBottom: 0 }} required>
                <Input
                  placeholder="请输入项目名称"
                  value={item.itemName}
                  onChange={(e) => handleItemChange(index, 'itemName', e.target.value)}
                />
              </Form.Item>
              <Form.Item label="项目价格（元）" style={{ marginBottom: 0 }} required>
                <InputNumber
                  placeholder="请输入价格"
                  value={item.price}
                  onChange={(value) => handleItemChange(index, 'price', value || 0)}
                  min={0}
                  precision={2}
                  style={{ width: '100%' }}
                />
              </Form.Item>
              <Form.Item label="备注说明" style={{ marginBottom: 0 }} required>
                <TextArea
                  placeholder="请输入备注说明"
                  value={item.remark}
                  onChange={(e) => handleItemChange(index, 'remark', e.target.value)}
                  rows={2}
                />
              </Form.Item>
            </Space>
          </Card>
        ))}

        {/* 添加项目按钮 */}
        <Button
          type="dashed"
          onClick={handleAddItem}
          block
          icon={<PlusOutlined />}
          style={{ marginBottom: 16 }}
        >
          添加项目
        </Button>

        {/* 总价显示 */}
        <Card size="small" style={{ background: '#e6f7ff' }}>
          <div style={{ fontSize: 16, fontWeight: 'bold', textAlign: 'right' }}>
            总价：<span style={{ color: '#ff4d4f', fontSize: 20 }}>¥{totalPrice.toFixed(2)}</span>
          </div>
        </Card>
      </Form>
    </Modal>
  );
};

export default AddItemModal;
