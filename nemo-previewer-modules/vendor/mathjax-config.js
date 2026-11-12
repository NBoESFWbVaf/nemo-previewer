// mathjax-config.js - F89: MathJax 3 configuration for the Nemo
// Previewer Markdown preview and print. Loaded BEFORE
// mathjax-tex-svg.js via the private previewer-res: scheme; the
// CSP (script-src previewer-res:) blocks inline scripts, so the
// configuration ships as its own whitelisted vendor file. The
// pageReady override marks the document with data-mathjax-done="1"
// once the initial typeset finished - the print poll waits for
// that marker (bounded, on timeout the document prints as loaded).
window.MathJax = {
  tex: {
    inlineMath: [["$", "$"], ["\\(", "\\)"]],
    displayMath: [["$$", "$$"], ["\\[", "\\]"]]
  },
  startup: {
    pageReady: function () {
      return MathJax.startup.defaultPageReady().then(function () {
        document.documentElement.setAttribute(
          "data-mathjax-done", "1");
      });
    }
  }
};
