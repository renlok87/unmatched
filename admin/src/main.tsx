import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { ThemedApp } from './components/layout/ThemedApp';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ThemedApp>
        <App />
      </ThemedApp>
    </BrowserRouter>
  </StrictMode>,
);
