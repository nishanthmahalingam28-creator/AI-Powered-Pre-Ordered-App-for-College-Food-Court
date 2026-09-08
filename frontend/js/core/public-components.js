(function () {
  'use strict';

  // Capture the script location before document.currentScript becomes unavailable.
  var currentScript = document.currentScript;
  var currentScriptUrl = currentScript
    ? new URL(currentScript.src, window.location.href)
    : null;

  function getFrontendRoot() {
    // Derive the frontend root from frontend/js/core/public-components.js.
    if (currentScriptUrl) {
      var scriptPath = currentScriptUrl.pathname;
      var marker = '/js/core/public-components.js';
      var index = scriptPath.toLowerCase().indexOf(marker);

      if (index >= 0) {
        return scriptPath.slice(0, index + 1);
      }
    }

    // Fallback when the script URL cannot be determined.
    var pathname = decodeURIComponent(new URL(window.location.href).pathname);
    var frontendMarker = '/frontend/';
    var frontendIndex = pathname.toLowerCase().indexOf(frontendMarker);

    return frontendIndex >= 0
      ? pathname.slice(0, frontendIndex + frontendMarker.length)
      : '/';
  }

  function getComponentUrl(name) {
    return new URL(
      getFrontendRoot() + 'components/' + name + '.html',
      window.location.href
    );
  }

  function getTarget(name) {
    var id = name === 'navbar' ? 'navbar-container' : 'footer-container';
    return document.getElementById(id);
  }

  async function loadComponent(name) {
    var url = getComponentUrl(name);

    console.log('[Shared Components] Loading ' + name + ':', url.href);

    var response = await fetch(url.href, { cache: 'no-cache' });

    if (!response.ok) {
      throw new Error(
        'Failed to load ' + name + ' component from ' + url.href +
        ' (HTTP ' + response.status + ' ' + response.statusText + ')'
      );
    }

    var markup = await response.text();
    var target = getTarget(name);

    if (!target) {
      throw new Error('Missing ' + name + ' component container.');
    }

    target.innerHTML = markup;
    console.log('[Shared Components] ' + name + ' loaded successfully.');
  }

  function resolveSitePaths() {
    document.querySelectorAll('[data-site-path]').forEach(function (element) {
      var path = element.dataset.sitePath;

      if (!path || /^(?:[a-z]+:|#|\/\/|\/)/i.test(path)) {
        return;
      }

      var resolved = new URL(
        getFrontendRoot() + path,
        window.location.href
      ).href;

      if (element.tagName === 'IMG') {
        element.setAttribute('src', resolved);
      } else if (element.hasAttribute('action')) {
        element.setAttribute('action', resolved);
      } else {
        element.setAttribute('href', resolved);
      }
    });
  }

  function normalizePageName() {
    var pathname = decodeURIComponent(new URL(window.location.href).pathname)
      .replace(/\/+$/, '');
    var filename = pathname.split('/').pop().toLowerCase();

    return !filename || filename === 'frontend' || filename === 'index'
      ? 'index.html'
      : filename;
  }

  function setActiveNavigation() {
    var currentPage = normalizePageName();

    document.querySelectorAll('header nav a[data-site-path]').forEach(function (link) {
      var sitePath = link.dataset.sitePath || '';
      var target = sitePath.split('/').pop().toLowerCase();
      var active = target === currentPage;

      link.classList.toggle('font-black', active);
      link.classList.toggle('font-bold', !active);
      link.classList.toggle('text-slate-950', active);
      link.classList.toggle('text-slate-300', !active);
      link.classList.toggle('bg-gradient-to-r', active);
      link.classList.toggle('from-teal-400', active);
      link.classList.toggle('via-cyan-400', active);
      link.classList.toggle('to-emerald-400', active);
      link.classList.toggle('px-6', active);
      link.classList.toggle('px-5', !active);
      link.setAttribute('aria-current', active ? 'page' : 'false');
    });
  }

  async function initialize() {
    console.log('[Shared Components] Initializing...');
    console.log('[Shared Components] Frontend root:', getFrontendRoot());

    try {
      await Promise.all([
        loadComponent('navbar'),
        loadComponent('footer')
      ]);

      document.querySelectorAll(
        'body > .fixed.bottom-3:not(.mobile-layout-dock),' +
        'body > .fixed.bottom-4:not(.mobile-layout-dock),' +
        'body > .customer-bottom-nav:not(.mobile-layout-dock)'
      ).forEach(function (element) {
        element.remove();
      });

      resolveSitePaths();
      setActiveNavigation();

      document.dispatchEvent(new CustomEvent('componentsReady'));
      console.log('[Shared Components] Ready ✓');

    } catch (error) {
      console.error('[Shared Components] ERROR:', error);
    }
  }

  document.addEventListener('DOMContentLoaded', initialize);
}());
