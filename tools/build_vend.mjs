// Vercel build step (vercel.json buildCommand): bundles BotID's browser client into site/vend/botid.js, which the
// page imports only on the Vercel build (the game itself is one HTML file with no build). See api/lb.mjs.
import { build } from 'esbuild';
await build({
  stdin: { contents: "export { initBotId } from 'botid/client/core';", resolveDir: process.cwd(), loader: 'js' },
  bundle: true, format: 'esm', minify: true, target: 'es2020', platform: 'browser', outfile: 'site/vend/botid.js',
});
console.log('built site/vend/botid.js');
