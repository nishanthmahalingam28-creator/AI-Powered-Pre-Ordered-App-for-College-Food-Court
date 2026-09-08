(function () {
  'use strict';

  function getFrontendRoot() {
    var pathname = decodeURIComponent(new URL(window.location.href).pathname);
    var marker = '/frontend/';
    var index = pathname.toLowerCase().indexOf(marker);
    return index >= 0 ? pathname.slice(0, index + marker.length) : '/';
  }

  function getComponentUrl(name) {
    return new URL(getFrontendRoot() + 'components/' + name + '.html', window.location.href);
  }

  function getTarget(name) {
    var id = name === 'navbar' ? 'navbar' : 'footer';
    var selector = name === 'navbar' ? 'header' : 'footer';
    return document.getElementById(id) || document.querySelector(selector);
  }

  async function loadComponent(name) {
    var url = getComponentUrl(name);
    var response = await fetch(url.href);
    if (!response.ok) {
      throw new Error(
        'Failed to load ' + name + ' component from ' + url.href +
        ' (HTTP ' + response.status + ' ' + response.statusText + ')'
      );
    }

    var markup = await response.text();
    var target = getTarget(name);

    if (target) {
      target.insertAdjacentHTML('beforebegin', markup);
      target.remove();
    } else {
      document.body.insertAdjacentHTML('beforeend', markup);
    }
  }

  function resolveSitePaths() {
    document.querySelectorAll('[data-site-path]').forEach(function (element) {
      var path = element.dataset.sitePath;
      var resolved = new URL(getFrontendRoot() + path, window.location.href).href;
      if (element.tagName === 'IMG') {
        element.setAttribute('src', resolved);
      } else {
        element.setAttribute('href', resolved);
      }
    });
  }

  function normalizePageName() {
    var pathname = decodeURIComponent(new URL(window.location.href).pathname).replace(/\/+$/, '');
    var filename = pathname.split('/').pop().toLowerCase();
    return !filename || filename === 'frontend' || filename === 'index' ? 'index.html' : filename;
  }

  function setActiveNavigation() {
    var currentPage = normalizePageName();
    document.querySelectorAll('header nav a[data-site-path]').forEach(function (link) {
      var target = link.dataset.sitePath.split('/').pop().toLowerCase();
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
    try {
      await Promise.all([loadComponent('navbar'), loadComponent('footer')]);
      document.querySelectorAll('body > .fixed.bottom-3:not(.mobile-layout-dock), body > .fixed.bottom-4:not(.mobile-layout-dock), body > .customer-bottom-nav:not(.mobile-layout-dock)').forEach(function (element) {
        element.remove();
      });
      resolveSitePaths();
      setActiveNavigation();
    } catch (error) {
      console.error('Shared layout component error:', error);
    }
  }

  document.addEventListener('DOMContentLoaded', initialize);
}());
