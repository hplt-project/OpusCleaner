import { fileURLToPath, URL } from 'node:url'
import { execSync } from 'node:child_process';
import fs from 'node:fs';

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

function getPythonPackageVersion(url) {
  try {
    return fs.readFileSync(url).toString().match(/^VERSION\s*=\s*(["'])(.+?)\1$/m)[2];
  } catch {
    return null;
  }
}

function getGitCommit() {
  try {
    return execSync('git rev-parse --short HEAD').toString().trim();
  } catch {
    return null;
  }
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  base: '/frontend/',
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000/'
    }
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  define: {
    '__OPUS_CLEANER_VERSION__': getPythonPackageVersion(new URL('../opuscleaner/__about__.py', import.meta.url)),
    '__OPUS_CLEANER_COMMIT__': getGitCommit(),
  }
})
