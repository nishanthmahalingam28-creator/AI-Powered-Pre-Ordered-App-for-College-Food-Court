(function () {
  'use strict';

<<<<<<< HEAD
  /*
   * Capture the script URL immediately.
   *
   * IMPORTANT:
   * document.currentScript can become null after the script
   * finishes executing, so we capture it here.
   */
  var currentScript = document.currentScript;
  var currentScriptUrl = currentScript
      ? new URL(currentScript.src, window.location.href)
      : null;


  /*
   * Find the frontend root based on the location of:
   *
   * frontend/js/core/public-components.js
   *
   * This supports:
   *
   * http://localhost:5500/
   *
   * and:
   *
   * http://localhost:5500/frontend/
   */
  function getFrontendRoot() {

      if (currentScriptUrl) {
=======
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
>>>>>>> 37f337a8d99dd74cc3f87f5079918161e9a50f11

          var scriptPath = currentScriptUrl.pathname;

<<<<<<< HEAD
          var marker = '/js/core/public-components.js';

          var index = scriptPath
              .toLowerCase()
              .indexOf(marker);

          if (index >= 0) {

              return scriptPath.slice(0, index + 1);
          }
      }


      /*
       * Fallback if the script URL cannot be detected.
       */
      var pathname = decodeURIComponent(
          new URL(window.location.href).pathname
=======
  async function loadComponent(name) {
    var url = getComponentUrl(name);

    console.log('[Shared Components] Loading ' + name + ':', url.href);

    var response = await fetch(url.href, { cache: 'no-cache' });

    if (!response.ok) {
      throw new Error(
        'Failed to load ' + name + ' component from ' + url.href +
        ' (HTTP ' + response.status + ' ' + response.statusText + ')'
>>>>>>> 37f337a8d99dd74cc3f87f5079918161e9a50f11
      );

      var frontendMarker = '/frontend/';

      var frontendIndex = pathname
          .toLowerCase()
          .indexOf(frontendMarker);

<<<<<<< HEAD
      if (frontendIndex >= 0) {

          return pathname.slice(
              0,
              frontendIndex + frontendMarker.length
          );
      }

      return '/';
=======
    target.innerHTML = markup;
    console.log('[Shared Components] ' + name + ' loaded successfully.');
>>>>>>> 37f337a8d99dd74cc3f87f5079918161e9a50f11
  }


  /*
   * Build component URL.
   */
  function getComponentUrl(name) {

      return new URL(
          getFrontendRoot() +
          'components/' +
          name +
          '.html',
          window.location.href
      );
  }


  /*
   * Find component container.
   */
  function getTarget(name) {

      var id =
          name === 'navbar'
              ? 'navbar-container'
              : 'footer-container';

      return document.getElementById(id);
  }


  /*
   * Load navbar/footer HTML.
   */
  async function loadComponent(name) {

      var url = getComponentUrl(name);

      console.log(
          '[Shared Components] Loading ' +
          name +
          ':',
          url.href
      );

      var response = await fetch(url.href);

      if (!response.ok) {

          throw new Error(
              'Failed to load ' +
              name +
              ' component from ' +
              url.href +
              ' (HTTP ' +
              response.status +
              ' ' +
              response.statusText +
              ')'
          );
      }

      var markup = await response.text();

      var target = getTarget(name);

      if (!target) {

          throw new Error(
              'Missing ' +
              name +
              ' component container.'
          );
      }

      target.innerHTML = markup;

      console.log(
          '[Shared Components] ' +
          name +
          ' loaded successfully.'
      );
  }


  /*
   * Resolve internal paths.
   *
   * data-site-path="pages/public/about.html"
   *
   * becomes:
   *
   * /pages/public/about.html
   *
   * or:
   *
   * /frontend/pages/public/about.html
   */
  function resolveSitePaths() {
<<<<<<< HEAD

      document
          .querySelectorAll('[data-site-path]')
          .forEach(function (element) {

              var path =
                  element.dataset.sitePath;

              if (!path) {
                  return;
              }


              /*
               * Ignore:
               * http://
               * https://
               * //
               * #
               * /
               * mailto:
               * tel:
               */
              if (
                  /^(?:[a-z]+:|#|\/\/|\/)/i.test(path)
              ) {
                  return;
              }


              var resolved = new URL(
                  getFrontendRoot() + path,
                  window.location.href
              ).href;


              /*
               * Images
               */
              if (element.tagName === 'IMG') {

                  element.setAttribute(
                      'src',
                      resolved
                  );

              }


              /*
               * Forms
               */
              else if (
                  element.hasAttribute('action')
              ) {

                  element.setAttribute(
                      'action',
                      resolved
                  );

              }


              /*
               * Links
               */
              else {

                  element.setAttribute(
                      'href',
                      resolved
                  );
              }
          });
=======
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
>>>>>>> 37f337a8d99dd74cc3f87f5079918161e9a50f11
  }


  /*
   * Determine current page.
   */
  function normalizePageName() {
<<<<<<< HEAD

      var pathname = decodeURIComponent(
          new URL(window.location.href).pathname
      ).replace(/\/+$/, '');

      var filename = pathname
          .split('/')
          .pop()
          .toLowerCase();

      if (
          !filename ||
          filename === 'frontend' ||
          filename === 'index'
      ) {
          return 'index.html';
      }

      return filename;
=======
    var pathname = decodeURIComponent(new URL(window.location.href).pathname)
      .replace(/\/+$/, '');
    var filename = pathname.split('/').pop().toLowerCase();

    return !filename || filename === 'frontend' || filename === 'index'
      ? 'index.html'
      : filename;
>>>>>>> 37f337a8d99dd74cc3f87f5079918161e9a50f11
  }


  /*
   * Highlight active navbar link.
   */
  function setActiveNavigation() {
<<<<<<< HEAD

      var currentPage =
          normalizePageName();

      document
          .querySelectorAll(
              'header nav a[data-site-path]'
          )
          .forEach(function (link) {

              var sitePath =
                  link.dataset.sitePath || '';

              var target =
                  sitePath
                      .split('/')
                      .pop()
                      .toLowerCase();

              var active =
                  target === currentPage;


              link.classList.toggle(
                  'font-black',
                  active
              );

              link.classList.toggle(
                  'font-bold',
                  !active
              );

              link.classList.toggle(
                  'text-slate-950',
                  active
              );

              link.classList.toggle(
                  'text-slate-300',
                  !active
              );

              link.classList.toggle(
                  'bg-gradient-to-r',
                  active
              );

              link.classList.toggle(
                  'from-teal-400',
                  active
              );

              link.classList.toggle(
                  'via-cyan-400',
                  active
              );

              link.classList.toggle(
                  'to-emerald-400',
                  active
              );

              link.classList.toggle(
                  'px-6',
                  active
              );

              link.classList.toggle(
                  'px-5',
                  !active
              );

              link.setAttribute(
                  'aria-current',
                  active
                      ? 'page'
                      : 'false'
              );
          });
=======
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
>>>>>>> 37f337a8d99dd74cc3f87f5079918161e9a50f11
  }


  /*
   * Initialize shared components.
   */
  async function initialize() {
<<<<<<< HEAD

      console.log(
          '[Shared Components] Initializing...'
      );

      console.log(
          '[Shared Components] Frontend root:',
          getFrontendRoot()
      );


      try {

          /*
           * Load navbar and footer simultaneously.
           */
          await Promise.all([
              loadComponent('navbar'),
              loadComponent('footer')
          ]);


          /*
           * Remove old duplicate mobile navigation
           * if it exists on legacy pages.
           */
          document
              .querySelectorAll(
                  'body > .fixed.bottom-3:not(.mobile-layout-dock),' +
                  'body > .fixed.bottom-4:not(.mobile-layout-dock),' +
                  'body > .customer-bottom-nav:not(.mobile-layout-dock)'
              )
              .forEach(function (element) {

                  element.remove();
              });


          /*
           * Resolve all shared internal paths.
           */
          resolveSitePaths();


          /*
           * Highlight current page.
           */
          setActiveNavigation();


          /*
           * Notify other page scripts.
           */
          document.dispatchEvent(
              new CustomEvent(
                  'componentsReady'
              )
          );


          console.log(
              '[Shared Components] Ready ✓'
          );

      }

      catch (error) {

          console.error(
              '[Shared Components] ERROR:',
              error
          );


          /*
           * Show a visible development error.
           * This makes debugging much easier than
           * leaving empty containers.
           */
          var navbar =
              document.getElementById(
                  'navbar-container'
              );

          var footer =
              document.getElementById(
                  'footer-container'
              );


          if (navbar) {

              navbar.innerHTML =
                  '<div style="' +
                  'padding:15px;' +
                  'background:#fee2e2;' +
                  'color:#991b1b;' +
                  'font-family:Arial;' +
                  '">' +
                  'Navbar failed to load. Check the browser console.' +
                  '</div>';
          }


          if (footer) {

              footer.innerHTML =
                  '<div style="' +
                  'padding:15px;' +
                  'background:#fee2e2;' +
                  'color:#991b1b;' +
                  'font-family:Arial;' +
                  '">' +
                  'Footer failed to load. Check the browser console.' +
                  '</div>';
          }
      }
=======
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
>>>>>>> 37f337a8d99dd74cc3f87f5079918161e9a50f11
  }


  /*
   * Start after the HTML document is ready.
   */
  document.addEventListener(
      'DOMContentLoaded',
      initialize
  );

}());