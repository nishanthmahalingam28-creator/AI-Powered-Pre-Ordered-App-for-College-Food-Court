(function () {
  'use strict';

  // Shared Student/Customer Workspace mobile menu.
  // Mobile UI/UX only: active from 0px through 640px.
  function initWorkspaceMobileMenu() {
    var header = document.querySelector('body.customer-workspace-page .customer-workspace-header');
    if (!header) return;

    var menu = document.getElementById('mobile-workspace-menu');
    var panel = document.getElementById('mobile-workspace-panel');

    if (!menu) {
      menu = document.createElement('button');
      menu.type = 'button';
      menu.id = 'mobile-workspace-menu';
      menu.className = 'student-mobile-menu-toggle';
      menu.setAttribute('aria-label', 'Open dashboard menu');
      menu.setAttribute('aria-expanded', 'false');
      menu.innerHTML = '<span></span><span></span><span></span>';

      var first = header.firstElementChild;
      if (first) {
        first.appendChild(menu);
      } else {
        header.appendChild(menu);
      }
    }

    if (!panel) {
      panel = document.createElement('nav');
      panel.id = 'mobile-workspace-panel';
      panel.className = 'mobile-workspace-panel';
      panel.setAttribute('aria-label', 'Mobile dashboard navigation');
      panel.innerHTML =
        '<a href="dashboard.html">Dashboard</a>' +
        '<a href="menu.html">Order Food</a>' +
        '<a href="preorder.html">My Cart</a>' +
        '<a href="orders.html">My Orders</a>' +
        '<a href="morning-survey.html">Morning Survey</a>' +
        '<a href="expenses.html">Expenses</a>' +
        '<a href="budgets.html">Food Budget</a>' +
        '<a href="assistant.html">AI Assistant</a>' +
        '<a href="profile.html">Profile</a>';
      header.appendChild(panel);
    }

    function isMobile() {
      return window.matchMedia('(max-width: 640px)').matches;
    }

    function closeMenu() {
      panel.classList.remove('open');
      menu.setAttribute('aria-expanded', 'false');
    }

    menu.addEventListener('click', function () {
      if (!isMobile()) {
        closeMenu();
        return;
      }
      var open = panel.classList.toggle('open');
      menu.setAttribute('aria-expanded', String(open));
    });

    panel.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', closeMenu);
    });

    document.addEventListener('click', function (event) {
      if (!menu.contains(event.target) && !panel.contains(event.target)) {
        closeMenu();
      }
    });

    window.addEventListener('resize', function () {
      if (!isMobile()) closeMenu();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initWorkspaceMobileMenu);
  } else {
    initWorkspaceMobileMenu();
  }
})();