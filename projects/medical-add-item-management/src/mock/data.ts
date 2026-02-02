import type { AddItemOrder, User } from '../types/index';

// Mock 用户数据
export const mockUsers: User[] = [
  { id: '1', name: '张三', phone: '13800138001', reportId: 'TJ20260124001' },
  { id: '2', name: '李四', phone: '13800138002', reportId: 'TJ20260124002' },
  { id: '3', name: '王五', phone: '13800138003', reportId: 'TJ20260124003' },
  { id: '4', name: '赵六', phone: '13800138004', reportId: 'TJ20260124004' },
  { id: '5', name: '钱七', phone: '13800138005', reportId: 'TJ20260124005' },
];

// Mock 加项单数据
export const mockOrders: AddItemOrder[] = [
  {
    id: 'AO20260124001',
    userId: '1',
    userName: '张三',
    userPhone: '13800138001',
    reportId: 'TJ20260124001',
    items: [
      { itemName: '心电图检查', price: 120, remark: '用户要求加做' },
      { itemName: '血糖检测', price: 80, remark: '医生建议' }
    ],
    totalPrice: 200,
    operator: '操作员A',
    createTime: '2026-01-24 09:30:00',
    status: 'pending'
  },
  {
    id: 'AO20260124002',
    userId: '2',
    userName: '李四',
    userPhone: '13800138002',
    reportId: 'TJ20260124002',
    items: [
      { itemName: '肝功能检查', price: 150, remark: '深度检查' }
    ],
    totalPrice: 150,
    operator: '操作员B',
    createTime: '2026-01-24 10:15:00',
    status: 'paid'
  },
  {
    id: 'AO20260124003',
    userId: '3',
    userName: '王五',
    userPhone: '13800138003',
    reportId: 'TJ20260124003',
    items: [
      { itemName: 'CT扫描', price: 800, remark: '头部CT' },
      { itemName: '核磁共振', price: 1200, remark: '腰椎MRI' },
      { itemName: '血常规', price: 60, remark: '常规检查' }
    ],
    totalPrice: 2060,
    operator: '操作员A',
    createTime: '2026-01-23 14:20:00',
    status: 'completed'
  },
  {
    id: 'AO20260124004',
    userId: '4',
    userName: '赵六',
    userPhone: '13800138004',
    reportId: 'TJ20260124004',
    items: [
      { itemName: '胸部X光', price: 180, remark: '肺部检查' }
    ],
    totalPrice: 180,
    operator: '操作员C',
    createTime: '2026-01-23 16:45:00',
    status: 'paid'
  }
];
