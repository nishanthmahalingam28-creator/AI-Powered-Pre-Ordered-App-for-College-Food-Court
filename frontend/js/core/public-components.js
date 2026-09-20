(function () {
  'use strict';

  // Capture script URL at execution time before currentScript becomes null
  var currentScript = document.currentScript;
  var currentScriptUrl = currentScript ? new URL(currentScript.src, window.location.href) : null;

  function loadGlobalResponsiveStyles() {
    if (document.getElementById('global-responsive-css')) return;
    var link = document.createElement('link');
    link.id = 'global-responsive-css';
    link.rel = 'stylesheet';
    link.href = getFrontendRoot() + 'css/global-responsive.css';
    document.head.appendChild(link);
  }

  function getFrontendRoot() {
    if (currentScriptUrl) {
      var scriptPath = currentScriptUrl.pathname;
      var marker = '/js/core/public-components.js';
      var index = scriptPath.toLowerCase().indexOf(marker);
      if (index >= 0) {
        return scriptPath.slice(0, index + 1);
      }

  loadGlobalResponsiveStyles();
    }

    var pathname = decodeURIComponent(new URL(window.location.href).pathname);
    var frontendMarker = '/frontend/';
    var frontendIndex = pathname.toLowerCase().indexOf(frontendMarker);

    return frontendIndex >= 0
      ? pathname.slice(0, frontendIndex + frontendMarker.length)
      : '/';
  }

  function getComponentUrl(name) {
    return new URL(getFrontendRoot() + 'components/' + name + '.html', window.location.href);
  }

  function getTarget(name) {
    var id = name === 'navbar' ? 'navbar-container' : 'footer-container';
    return document.getElementById(id);
  }

  async function loadComponent(name) {
    var url = getComponentUrl(name);
    var response = await fetch(url.href);

    if (!response.ok) {
      throw new Error(
        'Failed to load ' + name + ' component from ' + url.href + ' (HTTP ' + response.status + ')'
      );
    }

    var markup = await response.text();
    var target = getTarget(name);

    if (target) {
      target.innerHTML = markup;
    }
  }

  function resolveSitePaths() {
    document.querySelectorAll('[data-site-path]').forEach(function (element) {
      var path = element.dataset.sitePath;
      if (!path || /^(?:[a-z]+:|#|\/\/|\/)/i.test(path)) {
        return;
      }

      var resolved = new URL(getFrontendRoot() + path, window.location.href).href;

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
    var pathname = decodeURIComponent(new URL(window.location.href).pathname).replace(/\/+$/, '');
    var filename = pathname.split('/').pop().toLowerCase();
    if (!filename || filename === 'frontend' || filename === 'index') {
      return 'index.html';
    }
    return filename;
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

  async function updateAuthNavigation() {
    try {
      var userRaw = sessionStorage.getItem('foodCourtUser');
      if (userRaw) {
        var user = JSON.parse(userRaw);
        var loginBtns = document.querySelectorAll('header a[href*="login.html"], header a[data-site-path*="login.html"]');
        loginBtns.forEach(function (btn) {
          var dest = 'pages/customer/dashboard.html';
          if (user.role === 'vendor') dest = 'pages/vendor/dashboard.html';
          if (user.role === 'admin') dest = 'pages/admin/dashboard.html';
          btn.setAttribute('data-site-path', dest);
          btn.innerHTML = '<i class="fa-solid fa-user-circle mr-1.5"></i><span>' + (user.full_name || 'Dashboard') + '</span>';
        });
      }
    } catch (e) {}
  }

  async function initialize() {
    try {
      await Promise.all([loadComponent('navbar'), loadComponent('footer')]);
      resolveSitePaths();
      setActiveNavigation();
      updateAuthNavigation();
      document.dispatchEvent(new CustomEvent('componentsReady'));
    } catch (error) {
      console.warn('[Shared Components] Initialization note:', error.message);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
  } else {
    initialize();
  }
})();