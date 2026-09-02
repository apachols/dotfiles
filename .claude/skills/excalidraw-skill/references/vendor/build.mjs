import * as esbuild from "esbuild";

// exportToSvg never reaches the interactive editor's mermaid-import dialog, its
// math subset, or any locale but the built-in English default. Left in, they are
// ~3.5MB of the bundle.
const STUB_PKGS = /^(mermaid|@mermaid-js\/.*|cytoscape(-.*)?|katex|roughjs-fix)$/;
// esbuild filters compile as Go RE2, which has no lookahead, so English is
// excluded in the callback instead of the pattern.
const LOCALE_FILE = /[/\\]locales[/\\][^/\\]+\.js$/;
const IS_EN = /[/\\]locales[/\\]en[.-]/;

const stub = {
  name: "stub",
  setup(build) {
    build.onResolve({ filter: STUB_PKGS }, (a) => ({ path: a.path, namespace: "stub" }));
    build.onResolve({ filter: LOCALE_FILE }, (a) =>
      IS_EN.test(a.path) ? null : { path: a.path, namespace: "stub" });
    build.onLoad({ filter: /.*/, namespace: "stub" }, () => ({
      contents: "export default {}; export const __stubbed = true;",
      loader: "js",
    }));
  },
};

const result = await esbuild.build({
  entryPoints: ["entry.js"],
  bundle: true,
  format: "esm",
  minify: true,
  platform: "browser",
  define: { "process.env.NODE_ENV": '"production"' },
  loader: {
    ".woff2": "dataurl", ".woff": "dataurl", ".ttf": "dataurl",
    ".png": "dataurl", ".svg": "dataurl", ".css": "text",
  },
  plugins: [stub],
  outfile: "excalidraw.vendor.js",
  metafile: true,
});
console.log(await esbuild.analyzeMetafile(result.metafile, { verbose: false }).then(s => s.split("\n").slice(0, 6).join("\n")));
