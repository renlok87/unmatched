import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ApolloProvider } from '@apollo/client'
import { apolloClient } from './lib/apolloClient'
import { initAuthStore } from './store/authStore'
import './index.css'
import App from './App.tsx'

initAuthStore().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <ApolloProvider client={apolloClient}>
        <App />
      </ApolloProvider>
    </StrictMode>,
  )
})
