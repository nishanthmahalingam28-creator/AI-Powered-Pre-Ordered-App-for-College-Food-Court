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

  async function loadComponent(name, container) {
    var url = getComponentUrl(name);
    var response;

    try {
      response = await fetch(url.href);
      if (!response.ok) {
        throw new Error(
          'Failed to load ' + name + ' component from ' + url.href +
          ' (HTTP ' + response.status + ' ' + response.statusText + ')'
        );
      }

      container.innerHTML = await response.text();
    } catch (error) {
      container.dataset.componentFailed = 'true';
      container.setAttribute('role', 'alert');
      container.textContent = name + ' is temporarily unavailable.';
      console.error('Public component error:', error);
    }
  }

  function resolveSitePaths() {
    document.querySelectorAll('[data-site-path]').forEach(function (element) {
      var path = element.dataset.sitePath;
      element.setAttribute('href', new URL(getFrontendRoot() + path, window.location.href).href);
      if (element.tagName === 'IMG') {
        element.setAttribute('src', new URL(getFrontendRoot() + path, window.location.href).href);
      }
    });
  }

  function normalizePageName() {
    var pathname = decodeURIComponent(new URL(window.location.href).pathname)
      .replace(/\/+$/, '');
    var filename = pathname.split('/').pop().toLowerCase();

    if (!filename || filename === 'frontend') {
      return 'index.html';
    }
    return filename === 'index' ? 'index.html' : filename;
  }

  function setActiveNavigation() {
    var currentPage = normalizePageName();
    var desktopLinks = document.querySelectorAll('#navbar nav [data-site-path]');
    var mobileLinks = document.querySelectorAll('#mobile-drawer [data-site-path]');
    var activeDesktop = 'font-black text-slate-950 bg-gradient-to-r from-teal-400 via-cyan-400 to-emerald-400 px-6 shadow-[0_4px_15px_rgba(45,212,191,0.4)]';
    var inactiveDesktop = 'font-bold text-slate-300 px-5';

    desktopLinks.forEach(function (link) {
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
      link.classList.toggle('shadow-[0_4px_15px_rgba(45,212,191,0.4)]', active);
      link.setAttribute('aria-current', active ? 'page' : 'false');
    });

    mobileLinks.forEach(function (link) {
      var target = link.dataset.sitePath.split('/').pop().toLowerCase();
      var active = target === currentPage;
      link.classList.toggle('font-black', active);
      link.classList.toggle('font-bold', !active);
      link.classList.toggle('text-teal-400', active);
      link.classList.toggle('text-slate-300', !active);
      link.setAttribute('aria-current', active ? 'page' : 'false');
    });
  }

  function initializeMobileMenu() {
    var button = document.getElementById('mobile-menu-btn');
    var drawer = document.getElementById('mobile-drawer');
    if (!button || !drawer) {
      return;
    }

    button.addEventListener('click', function () {
      var isHidden = drawer.classList.toggle('hidden');
      button.setAttribute('aria-expanded', String(!isHidden));
    });

    drawer.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        drawer.classList.add('hidden');
        button.setAttribute('aria-expanded', 'false');
      });
    });
  }

  async function initialize() {
    var navbar = document.getElementById('navbar');
    var footer = document.getElementById('footer');
    if (!navbar || !footer) {
      console.error('Public component error: navbar and footer containers are required.');
      return;
    }

    await Promise.all([
      loadComponent('navbar', navbar),
      loadComponent('footer', footer)
    ]);
    resolveSitePaths();
    if (!navbar.dataset.componentFailed) {
      setActiveNavigation();
      initializeMobileMenu();
    }
  }

  document.addEventListener('DOMContentLoaded', initialize);
}());
