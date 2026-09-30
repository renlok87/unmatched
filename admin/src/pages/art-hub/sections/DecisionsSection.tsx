import React from 'react';
import { Alert, Card, Empty, Space, Typography } from 'antd';
import type { DecisionView } from '../../../../art-hub/types';
import { DocList } from '../components/DocList';

const { Text, Paragraph } = Typography;

export const DecisionsSection: React.FC<{ decisions?: DecisionView[] }> = ({ decisions }) => {
  if (!decisions) return <Empty />;
  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }} data-testid="art-hub-decisions">
      <Alert
        type="info"
        showIcon
        message="Журналы решений"
        description={
          <span>
            Файлы <Text code>docs/game-design/decisions/*.md</Text>, свежие первыми. Происхождение решения (пользователь / оркестратор /
            исполнитель) — как записано в журнале.
          </span>
        }
      />
      {decisions.length === 0 ? <Empty description="журналов решений нет" /> : null}
      {decisions.map((d) => (
        <Card key={d.file.path} size="small">
          <DocList docs={[d]} />
          {d.origin ? (
            <Paragraph type="secondary" ellipsis={{ rows: 3, expandable: true, symbol: 'ещё' }} style={{ marginBottom: 0, fontSize: 12 }}>
              {d.origin}
            </Paragraph>
          ) : null}
        </Card>
      ))}
    </Space>
  );
};
