import React from 'react';
import { Collapse, Empty, List, Space, Tag, Typography } from 'antd';
import type { DocView } from '../../../../art-hub/types';
import { basename, timeAgo } from '../format';
import { ExistsTag, FileActions } from './common';

const { Text, Paragraph } = Typography;

/** Markdown documents with title, «Дата/Статус» line and «##» headings (collapsed). */
export const DocList: React.FC<{ docs: DocView[]; emptyText?: string; testId?: string }> = ({ docs, emptyText = 'документов нет', testId }) => {
  if (!docs.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />;
  return (
    <List
      data-testid={testId}
      size="small"
      dataSource={docs}
      renderItem={(d) => (
        <List.Item key={d.file.path} style={{ display: 'block' }}>
          <Space direction="vertical" size={2} style={{ width: '100%' }}>
            <Space wrap align="center" size={6}>
              <Text strong>{d.title ?? basename(d.file.path)}</Text>
              {d.date ? <Tag>{d.date}</Tag> : null}
              <ExistsTag file={d.file} />
              <FileActions file={d.file} title={d.title} />
            </Space>
            <Text type="secondary" copyable={{ text: d.file.path }} style={{ fontSize: 11, wordBreak: 'break-all' }}>
              {d.file.path}
              {d.file.mtime ? ` · изменён ${timeAgo(d.file.mtime)}` : ''}
            </Text>
            {d.statusLine ? (
              <Paragraph ellipsis={{ rows: 2, expandable: true, symbol: 'ещё' }} style={{ marginBottom: 0, fontSize: 12 }}>
                {d.statusLine}
              </Paragraph>
            ) : null}
            {d.headings.length ? (
              <Collapse
                size="small"
                ghost
                items={[
                  {
                    key: 'h',
                    label: <Text type="secondary" style={{ fontSize: 12 }}>разделы ({d.headings.length})</Text>,
                    children: (
                      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12 }}>
                        {d.headings.map((h, i) => (
                          <li key={`${i}-${h}`}>{h}</li>
                        ))}
                      </ul>
                    ),
                  },
                ]}
              />
            ) : null}
          </Space>
        </List.Item>
      )}
    />
  );
};
