import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  build: {
    lib: {
      entry: resolve(__dirname, 'src/main.ts'),
      name: 'OlSimpleMap',
      fileName: () => 'demo-geocontext.min.js',
      formats: ['umd']
    },
    sourcemap: true,
    emptyOutDir: true
  }
});
