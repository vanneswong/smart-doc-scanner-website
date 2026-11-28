// 智能文档扫描 介绍网站 · 轻量交互
(function () {
  'use strict';

  /* ---------------------------------------------- 滚动渐显动画 */
  var revealables = document.querySelectorAll(
    '.section-head, .feature, .pipe-step, .insight, .tech, .code-block, .env-list, .api, .table-wrap, .note, .news-feature, .more-card'
  );

  revealables.forEach(function (el, i) {
    el.classList.add('reveal');
    el.style.transitionDelay = (i % 3) * 60 + 'ms';
  });

  if ('IntersectionObserver' in window) {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    );

    revealables.forEach(function (el) { observer.observe(el); });
  } else {
    revealables.forEach(function (el) { el.classList.add('visible'); });
  }

  /* ---------------------------------------------- 文章阅读进度条 */
  var bar = document.getElementById('readProgress');
  if (!bar) return;

  var ticking = false;

  function updateProgress() {
    var doc = document.documentElement;
    var scrollTop = window.pageYOffset || doc.scrollTop || 0;
    var height = (doc.scrollHeight || 0) - window.innerHeight;
    var ratio = height > 0 ? Math.min(Math.max(scrollTop / height, 0), 1) : 0;
    bar.style.width = (ratio * 100).toFixed(2) + '%';
    ticking = false;
  }

  function onScroll() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(updateProgress);
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  updateProgress();
})();
