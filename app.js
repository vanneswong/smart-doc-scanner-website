// 智能文档扫描 介绍网站 · 轻量交互
(function () {
  'use strict';

  // 滚动渐显动画：为带 .reveal 的元素添加可见性
  var revealables = document.querySelectorAll(
    '.section-head, .feature, .pipe-step, .insight, .tech, .code-block, .env-list, .api, .table-wrap, .note'
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
})();
