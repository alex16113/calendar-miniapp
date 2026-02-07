import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary } from './ErrorBoundary.tsx'

console.log('[MAIN] main.tsx loaded, starting React...');

try {
  const rootElement = document.getElementById('root');
  if (!rootElement) {
    console.error('[MAIN] #root element not found!');
    throw new Error('Root element not found');
  }
  
  console.log('[MAIN] Creating React root...');
  const root = createRoot(rootElement);
  
  console.log('[MAIN] Rendering App...');
  root.render(
    <StrictMode>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </StrictMode>,
  );
  
  console.log('[MAIN] React render complete');
} catch (error) {
  console.error('[MAIN] Failed to start React:', error);
  const rootElement = document.getElementById('root');
  if (rootElement) {
    rootElement.innerHTML = `
      <div style="padding:20px;color:red;font-family:system-ui">
        <h3>Ошибка запуска приложения</h3>
        <pre style="font-size:11px;white-space:pre-wrap">${error instanceof Error ? error.message : String(error)}</pre>
      </div>
    `;
  }
}
