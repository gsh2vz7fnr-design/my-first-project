import React, { useMemo } from 'react';
import { Modal, Descriptions, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { AddItemOrder, AddItem } from '../types';
import { StatusMap, StatusColorMap } from '../types';

interface OrderDetailModalProps {
  visible: boolean;
  order: AddItemOrder;
  onCancel: () => void;
}

const OrderDetailModal: React.FC<OrderDetailModalProps> = ({
  visible,
  order,
  onCancel
}) => {
  const columns: ColumnsType<AddItem & { index: number }> = useMemo(() => [
    {
      title: '序号',
      dataIndex: 'index',
      key: 'index',
      width: 60
    },
    {
      title: '项目名称',
      dataIndex: 'itemName',
      key: 'itemName'
    },
    {
      title: '价格（元）',
      dataIndex: 'price',
      key: 'price',
      render: (price: number) => `¥${price}`
    },
    {
      title: '备注',
      dataIndex: 'remark',
      key: 'remark'
    }
  ], []);

  const dataSource = useMemo(() =>
    order.items.map((item, index) => ({
      ...item,
      index: index + 1,
      key: index
    })),
    [order.items]
  );

  return (
    <Modal
      title="加项单详情"
      open={visible}
      onCancel={onCancel}
      footer={null}
      width={800}
    >
      <Descriptions bordered column={2}>
        <Descriptions.Item label="加项单编号" span={2}>
          {order.id}
        </Descriptions.Item>
        <Descriptions.Item label="用户姓名">
          {order.userName}
        </Descriptions.Item>
        <Descriptions.Item label="用户ID">
          {order.userId}
        </Descriptions.Item>
        <Descriptions.Item label="手机号">
          {order.userPhone}
        </Descriptions.Item>
        <Descriptions.Item label="体检编号">
          {order.reportId}
        </Descriptions.Item>
        <Descriptions.Item label="操作人">
          {order.operator}
        </Descriptions.Item>
        <Descriptions.Item label="创建时间">
          {order.createTime}
        </Descriptions.Item>
        <Descriptions.Item label="状态" span={2}>
          <Tag color={StatusColorMap[order.status]}>
            {StatusMap[order.status]}
          </Tag>
        </Descriptions.Item>
      </Descriptions>

      <div style={{ marginTop: 24, marginBottom: 12 }}>
        <h3>加项明细</h3>
      </div>

      <Table
        columns={columns}
        dataSource={dataSource}
        pagination={false}
        summary={() => (
          <Table.Summary fixed>
            <Table.Summary.Row>
              <Table.Summary.Cell index={0} colSpan={2}>
                <strong>总计</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={1}>
                <strong style={{ color: '#ff4d4f', fontSize: 16 }}>
                  ¥{order.totalPrice}
                </strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={2} />
            </Table.Summary.Row>
          </Table.Summary>
        )}
      />
    </Modal>
  );
};

export default OrderDetailModal;
