import React from 'react';

interface JsonViewerProps {
  data: any;
}

export const JsonViewer: React.FC<JsonViewerProps> = ({ data }) => {
  return (
    <pre
      style={{
        backgroundColor: '#f5f5f5',
        padding: '16px',
        borderRadius: '6px',
        fontSize: '14px',
        overflow: 'auto',
        maxHeight: '500px',
      }}
    >
      {JSON.stringify(data, null, 2)}
    </pre>
  );
};