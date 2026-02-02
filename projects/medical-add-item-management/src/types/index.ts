// 单个加项
export type AddItem = {
  itemName: string;        // 项目名称
  price: number;           // 价格
  remark: string;          // 备注
}

// 加项单
export type AddItemOrder = {
  id: string;              // 加项单编号
  userId: string;          // 用户ID
  userName: string;        // 用户姓名
  userPhone: string;       // 用户手机号
  reportId: string;        // 原体检报告编号
  items: AddItem[];        // 加项列表
  totalPrice: number;      // 总价格
  operator: string;        // 操作人
  createTime: string;      // 创建时间
  status: 'pending' | 'paid' | 'completed'; // 状态
}

// 用户信息
export type User = {
  id: string;
  name: string;
  phone: string;
  reportId: string;        // 体检编号
}

// 状态映射
export const StatusMap = {
  pending: '待支付',
  paid: '已支付',
  completed: '已完成'
} as const;

// 状态颜色映射
export const StatusColorMap = {
  pending: 'orange',
  paid: 'blue',
  completed: 'green'
} as const;
