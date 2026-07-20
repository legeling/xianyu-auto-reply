// 在页面加载前立即设置主题，避免闪白（从 index.html 内联脚本外置，以满足 CSP script-src 'self'）
(function() {
  var theme = localStorage.getItem('theme');
  var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  if (theme === 'dark' || (!theme && prefersDark)) {
    document.documentElement.classList.add('dark');
  }
})();
