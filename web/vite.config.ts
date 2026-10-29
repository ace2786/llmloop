import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 后端地址可通过 .env.local 里的 VITE_API_BASE 覆盖，默认指向本地联调地址
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: false,
  },
})
