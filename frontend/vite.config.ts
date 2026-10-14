import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The desk talks to the FastAPI backend at http://localhost:8000 directly, and
// that backend allows this origin by name, so no proxy is involved.
export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5173, strictPort: true },
})
