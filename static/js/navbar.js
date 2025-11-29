/**
 * Navbar Functionality
 * Handles mobile menu, dropdowns, and scroll effects
 */

// Fixed Header Scroll Effect
document.addEventListener('DOMContentLoaded', function() {
    const header = document.querySelector('header');

    window.addEventListener('scroll', function() {
        if (window.scrollY > 50) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
    });
});

// Mobile menu functionality
function toggleMobileMenu() {
    const navMenu = document.querySelector('.nav-menu');
    const menuToggle = document.querySelector('.mobile-menu-toggle i');

    navMenu.classList.toggle('active');

    if (navMenu.classList.contains('active')) {
        menuToggle.classList.remove('fa-bars');
        menuToggle.classList.add('fa-times');
    } else {
        menuToggle.classList.remove('fa-times');
        menuToggle.classList.add('fa-bars');
    }
}

// Dropdown functionality for both mobile and desktop
document.addEventListener('DOMContentLoaded', function() {
    const dropdowns = document.querySelectorAll('.dropdown');
    const submenus = document.querySelectorAll('.dropdown-submenu');

    dropdowns.forEach(dropdown => {
        const toggle = dropdown.querySelector('.dropdown-toggle');

        // Mobile functionality (click to toggle)
        toggle.addEventListener('click', function(e) {
            if (window.innerWidth <= 992) {
                e.preventDefault();
                dropdown.classList.toggle('active');
            }
        });

        // Desktop functionality (hover is handled by CSS)
        // Additional click functionality for desktop (optional)
        toggle.addEventListener('click', function(e) {
            if (window.innerWidth > 992) {
                // Let hover handle it, but prevent default link behavior if needed
                if (toggle.getAttribute('href') === '#') {
                    e.preventDefault();
                }
            }
        });
    });

    submenus.forEach(submenu => {
        const toggle = submenu.querySelector('.dropdown-item-main');
        toggle.addEventListener('click', function(e) {
            if (window.innerWidth <= 992) {
                e.preventDefault();
                submenu.classList.toggle('active');
            }
        });
    });

    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.dropdown')) {
            dropdowns.forEach(dropdown => {
                dropdown.classList.remove('active');
            });
        }
    });
});
