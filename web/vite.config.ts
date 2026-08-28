import { copyFileSync, mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { join } from 'node:path'
import { defineConfig, loadEnv, type Plugin } from 'vite'
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

export default defineConfig(({ command, mode }) => {
  // VITE_DEV_API_PROXY_TARGET is dev-only (set in a gitignored .env.local,
  // never committed) -- keeps the actual API host out of source, matching
  // this repo's convention of injecting infra specifics via env rather
  // than literals in committed config.
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const devApiProxyTarget = env.VITE_DEV_API_PROXY_TARGET

  return {
    plugins: [react(), copyMaplibreWorker()],
    // GitHub Pages serves this as a project site under /traffic-tracker/,
    // not the origin root -- asset URLs need that prefix baked in at
    // build time. Dev/preview keep serving from `/`.
    base: command === 'build' ? '/traffic-tracker/' : '/',
    // Letting Vite's dev-time dependency pre-bundler rewrite maplibre-gl's
    // own worker bundle hangs the worker's script request indefinitely.
    // Excluding it makes Vite serve the package as-is instead.
    optimizeDeps: {
      exclude: ['maplibre-gl'],
    },
    // Dev-only: proxies API calls through Vite's own server so the
    // browser sees a same-origin request -- the deployed API's CORS
    // policy only allows the production frontend origin, which
    // `localhost` isn't. The proxy issues the real request server-side,
    // where browser CORS doesn't apply. Never used in the production
    // build (that talks to VITE_API_BASE_URL directly, per api.ts); a
    // no-op locally too unless VITE_DEV_API_PROXY_TARGET is set.
    server: devApiProxyTarget
      ? { proxy: { '/v1': { target: devApiProxyTarget, changeOrigin: true } } }
      : undefined,
  }
})
