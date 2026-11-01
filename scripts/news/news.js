(() => {
  const root = document.documentElement;
  const preferred = () => matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  const getSaved = () => { try { return localStorage.getItem('kp-theme'); } catch { return null; } };
  function setTheme(theme, save) {
    root.dataset.kpTheme = theme;
    root.classList.toggle('dark', theme === 'dark');
    if (save) { try { localStorage.setItem('kp-theme', theme); } catch {} }
    document.querySelectorAll('[data-kp-theme-toggle]').forEach(b => {
      b.textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
      b.setAttribute('aria-label', 'Switch to ' + (theme === 'dark' ? 'light' : 'dark') + ' mode');
    });
  }
  setTheme(getSaved() || preferred(), false);
  document.querySelectorAll('[data-kp-theme-toggle]').forEach(b => b.addEventListener('click', () => setTheme(root.dataset.kpTheme === 'dark' ? 'light' : 'dark', true)));
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if (!getSaved()) setTheme(preferred(), false); });
  const pause = document.querySelector('[data-kp-pause]');
  pause?.addEventListener('click', () => {
    const stopped = pause.getAttribute('aria-pressed') !== 'true';
    pause.setAttribute('aria-pressed', String(stopped));
    pause.textContent = stopped ? 'Resume' : 'Pause';
    pause.setAttribute('aria-label', (stopped ? 'Resume' : 'Pause') + ' scrolling news');
    document.querySelector('.kp-announcement').classList.toggle('kp-paused', stopped);
  });
  document.querySelectorAll('[data-copy-link]').forEach(b => b.addEventListener('click', async () => {
    const result = document.querySelector('[data-share-result]');
    const url = document.querySelector('link[rel="canonical"]').href;
    try { await navigator.clipboard.writeText(url); result.textContent = 'Link copied. Ready to share.'; }
    catch { result.textContent = 'Copy this link: ' + url; }
  }));
  const share = document.querySelector('[data-share]');
  if (share && navigator.share) {
    share.hidden = false;
    share.addEventListener('click', async () => {
      try { await navigator.share({title:document.title, url:document.querySelector('link[rel="canonical"]').href}); }
      catch (e) { if (e.name !== 'AbortError') document.querySelector('[data-share-result]').textContent = 'Use Copy link to share this story.'; }
    });
  }
})();
