#!/usr/bin/env node
/* ==========================================================================
   bundle.mjs — make a flow self-contained (double-clickable, shareable)
   ==========================================================================
   A flow authored against design/_framework/ links ~13 external CSS/JS files.
   Browsers SANDBOX file:// pages from reading sibling files, so opening such a
   flow by double-click renders it unstyled with no JavaScript. (It only works
   over http:// — e.g. a local dev server.) This bundler inlines every LOCAL
   <link rel="stylesheet"> and <script src> into the HTML, producing one file
   that works anywhere: double-click, email, drop in Slack, open offline.

   Remote resources (https:// CDN fonts, data: URIs) are left untouched.

   Usage:
     node design/_framework/bundle.mjs design/<flow>.html [out.html]

   Default output: design/<flow>.standalone.html (next to the input).
   Hand the user the .standalone.html — that is the portable deliverable.
   ========================================================================== */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const input = process.argv[2];
if (!input) {
  console.error('usage: node bundle.mjs <flow.html> [out.html]');
  process.exit(1);
}
const dir = dirname(resolve(input));
const out = process.argv[3] || resolve(input).replace(/\.html?$/i, '') + '.standalone.html';

const isRemote = (h) => /^(?:https?:)?\/\//i.test(h) || h.startsWith('data:') || h.startsWith('#');
const missing = [];
let inlined = 0;

function readLocal(href) {
  try { return readFileSync(resolve(dir, href.split(/[?#]/)[0]), 'utf8'); }
  catch { missing.push(href); return null; }
}

let html = readFileSync(input, 'utf8');

// Inline local stylesheets:  <link rel="stylesheet" href="...">  (CDN fonts kept)
html = html.replace(/<link\b[^>]*\brel=["']stylesheet["'][^>]*>/gi, (tag) => {
  const m = tag.match(/\bhref=["']([^"']+)["']/i);
  if (!m || isRemote(m[1])) return tag;
  const css = readLocal(m[1]);
  if (css == null) return tag;
  inlined++;
  return `<style>\n/* ${m[1]} */\n${css.replace(/<\/style>/gi, '<\\/style>')}\n</style>`;
});

// Inline local scripts:  <script src="..."></script>
html = html.replace(/<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*>\s*<\/script>/gi, (tag, src) => {
  if (isRemote(src)) return tag;
  const js = readLocal(src);
  if (js == null) return tag;
  inlined++;
  return `<script>\n/* ${src} */\n${js.replace(/<\/script>/gi, '<\\/script>')}\n</script>`;
});

writeFileSync(out, html);

const remaining = (html.match(/(?:href|src)=["'](?!https?:|\/\/|data:|#)[^"']+\.(?:css|js)["']/gi) || []).length;
console.log(`bundled ${inlined} file(s) -> ${out}`);
if (missing.length) console.warn(`  warning: could not read: ${missing.join(', ')}`);
if (remaining) console.warn(`  warning: ${remaining} local css/js reference(s) still present`);
process.exit(remaining ? 1 : 0);
