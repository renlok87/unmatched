import React from 'react';
import Editor from '@monaco-editor/react';

interface JsonEditorProps {
  value: string;
  onChange: (value: string | undefined) => void;
  height?: string;
  readOnly?: boolean;
}

export const JsonEditor: React.FC<JsonEditorProps> = ({
  value,
  onChange,
  height = '400px',
  readOnly = false,
}) => {
  const handleEditorChange = (value: string | undefined) => {
    onChange(value);
  };

  const validateJson = () => {
    try {
      JSON.parse(value);
      return true;
    } catch {
      return false;
    }
  };

  const isValid = validateJson();

  return (
    <div style={{ border: `1px solid ${isValid ? '#d9d9d9' : '#ff4d4f'}`, borderRadius: 6 }}>
      <Editor
        height={height}
        defaultLanguage="json"
        value={value}
        onChange={handleEditorChange}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 14,
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          automaticLayout: true,
          tabSize: 2,
          formatOnPaste: true,
          formatOnType: true,
        }}
        theme="vs-light"
      />
    </div>
  );
};