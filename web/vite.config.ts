import { copyFileSync, mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { join } from 'node:path'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

const require = createRequire(import.meta.url)

// maplibre-gl's worker (node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs)
// is a static file requested at runtime via a relative `new URL(...,
// import.meta.url)` lookup, not a statically analyzable import -- Rollup's
// build never bundles or copies it into dist/assets/, so it 404s only in
// production. The worker file also has its own relative sibling import
// (maplibre-gl-shared.mjs), invisible to Rollup for the same reason, so
// both files have to be copied together.
function copyMaplibreWorker(): Plugin {
  let outDir = 'dist'
  return {
    name: 'copy-maplibre-gl-worker',
    apply: 'build',
    configResolved(config) {
      outDir = config.build.outDir
    },
    closeBundle() {
      const assetsDir = join(outDir, 'assets')
      mkdirSync(assetsDir, { recursive: true })
      for (const file of ['maplibre-gl-worker.mjs', 'maplibre-gl-shared.mjs']) {
        copyFileSync(require.resolve(`maplibre-gl/dist/${file}`), join(assetsDir, file))
      }
    },
  }
}

export default defineConfig(({ command }) => ({
  plugins: [react(), copyMaplibreWorker()],
  // GitHub Pages serves this as a project site under /traffic-tracker/, not
  // the origin root -- asset URLs need that prefix baked in at build time.
  // Dev/preview keep serving from `/`.
  base: command === 'build' ? '/traffic-tracker/' : '/',
  // Letting Vite's dev-time dependency pre-bundler rewrite maplibre-gl's
  // own worker bundle hangs the worker's script request indefinitely.
  // Excluding it makes Vite serve the package as-is instead.
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
}))
