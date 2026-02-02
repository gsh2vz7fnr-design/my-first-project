import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // 启用代码分割
    rollupOptions: {
      output: {
        manualChunks: {
          // 将 React 相关库单独打包
          'react-vendor': ['react', 'react-dom'],
          // 将 antd 和相关库单独打包
          'antd-vendor': ['antd', 'dayjs'],
        },
      },
    },
    // 提高构建性能
    chunkSizeWarningLimit: 1000,
    // 启用压缩
    minify: 'esbuild',
  },
  // 开发服务器优化
  server: {
    hmr: {
      overlay: false, // 禁用错误覆盖层以提高性能
    },
  },
  // 优化依赖预构建
  optimizeDeps: {
    include: ['react', 'react-dom', 'antd', 'dayjs'],
  },
})
