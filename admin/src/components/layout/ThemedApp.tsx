import type { ReactNode } from 'react';
import { App as AntdApp, ConfigProvider, theme } from 'antd';

export const ThemedApp = ({ children }: { children: ReactNode }) => {
  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#1677ff',
          borderRadius: 6,
        },
        algorithm: theme.defaultAlgorithm,
      }}
    >
      <AntdApp>{children}</AntdApp>
    </ConfigProvider>
  );
};
