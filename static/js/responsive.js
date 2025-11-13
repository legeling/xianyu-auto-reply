/**
 * 响应式优化
 * 移动端适配和界面优化
 */

(function() {
    'use strict';

    const ResponsiveManager = {
        // 断点配置
        breakpoints: {
            mobile: 768,
            tablet: 1024,
            desktop: 1200
        },

        // 当前设备类型
        currentDevice: 'desktop',

        // 初始化
        init: function() {
            this.detectDevice();
            this.bindEvents();
            this.optimizeForDevice();
            console.log('响应式管理器已启动');
        },

        // 检测设备类型
        detectDevice: function() {
            const width = window.innerWidth;

            if (width < this.breakpoints.mobile) {
                this.currentDevice = 'mobile';
            } else if (width < this.breakpoints.tablet) {
                this.currentDevice = 'tablet';
            } else {
                this.currentDevice = 'desktop';
            }

            console.log('当前设备:', this.currentDevice, '宽度:', width);
        },

        // 绑定事件
        bindEvents: function() {
            // 窗口大小改变事件
            let resizeTimer;
            window.addEventListener('resize', () => {
                clearTimeout(resizeTimer);
                resizeTimer = setTimeout(() => {
                    this.handleResize();
                }, 250);
            });

            // 移动端菜单切换
            this.bindMobileMenu();

            // 触摸优化
            this.bindTouchEvents();
        },

        // 处理窗口大小改变
        handleResize: function() {
            const oldDevice = this.currentDevice;
            this.detectDevice();

            if (oldDevice !== this.currentDevice) {
                console.log('设备类型改变:', oldDevice, '->', this.currentDevice);
                this.optimizeForDevice();
            }
        },

        // 根据设备类型优化界面
        optimizeForDevice: function() {
            switch (this.currentDevice) {
                case 'mobile':
                    this.optimizeForMobile();
                    break;
                case 'tablet':
                    this.optimizeForTablet();
                    break;
                default:
                    this.optimizeForDesktop();
                    break;
            }
        },

        // 移动端优化
        optimizeForMobile: function() {
            console.log('应用移动端优化');

            // 隐藏侧边栏
            this.hideSidebar();

            // 优化卡片布局
            this.optimizeCardsForMobile();

            // 优化按钮大小
            this.optimizeButtonsForMobile();

            // 优化表格
            this.optimizeTablesForMobile();

            // 添加移动端特定的CSS类
            document.body.classList.add('mobile-device');
            document.body.classList.remove('tablet-device', 'desktop-device');
        },

        // 平板优化
        optimizeForTablet: function() {
            console.log('应用平板优化');

            // 显示侧边栏
            this.showFullSidebar();

            // 优化卡片布局
            this.optimizeCardsForTablet();

            // 优化按钮大小
            this.optimizeButtonsForTablet();

            // 添加平板特定的CSS类
            document.body.classList.add('tablet-device');
            document.body.classList.remove('mobile-device', 'desktop-device');
        },

        // 桌面端优化
        optimizeForDesktop: function() {
            console.log('应用桌面端优化');

            // 显示完整侧边栏
            this.showFullSidebar();

            // 恢复默认布局
            this.restoreDefaultLayout();

            // 添加桌面端特定的CSS类
            document.body.classList.add('desktop-device');
            document.body.classList.remove('mobile-device', 'tablet-device');
        },

        // 绑定移动端菜单事件
        bindMobileMenu: function() {
            // 移动端菜单切换按钮
            const mobileToggle = document.querySelector('.mobile-toggle');
            if (mobileToggle) {
                mobileToggle.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.toggleSidebar();
                });
            }

            // 点击外部关闭侧边栏
            document.addEventListener('click', (e) => {
                if (this.currentDevice === 'mobile') {
                    const sidebar = document.querySelector('.sidebar');
                    const mobileToggle = document.querySelector('.mobile-toggle');

                    if (sidebar && sidebar.classList.contains('open')) {
                        if (!sidebar.contains(e.target) && !mobileToggle.contains(e.target)) {
                            this.hideSidebar();
                        }
                    }
                }
            });

            // ESC键关闭侧边栏
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.currentDevice === 'mobile') {
                    this.hideSidebar();
                }
            });
        },

        // 绑定触摸事件
        bindTouchEvents: function() {
            if ('ontouchstart' in window) {
                // 为按钮添加触摸反馈
                const buttons = document.querySelectorAll('.btn, .nav-link, .quick-action');
                buttons.forEach(button => {
                    button.addEventListener('touchstart', function() {
                        this.style.transform = 'scale(0.98)';
                    });

                    button.addEventListener('touchend', function() {
                        this.style.transform = '';
                    });
                });

                // 为卡片添加触摸反馈
                const cards = document.querySelectorAll('.card');
                cards.forEach(card => {
                    card.addEventListener('touchstart', function() {
                        this.style.transform = 'scale(0.99)';
                    });

                    card.addEventListener('touchend', function() {
                        this.style.transform = '';
                    });
                });
            }
        },

        // 切换侧边栏
        toggleSidebar: function(force) {
            window.toggleSidebar(force);
        },

        // 显示侧边栏
        showSidebar: function() {
            window.toggleSidebar(true);
        },

        // 隐藏侧边栏
        hideSidebar: function() {
            window.toggleSidebar(false);
        },

        // 显示紧凑侧边栏（平板）
        showCompactSidebar: function() {
            const sidebar = document.querySelector('.sidebar');
            if (!sidebar) return;

            sidebar.classList.add('compact');
            window.toggleSidebar(true);
        },

        // 显示完整侧边栏（桌面）
        showFullSidebar: function() {
            const sidebar = document.querySelector('.sidebar');
            if (!sidebar) return;

            sidebar.classList.remove('compact');
            window.toggleSidebar(true);
        },

        // 创建侧边栏遮罩层（兼容旧逻辑）
        createSidebarOverlay: function() {
            const overlay = document.getElementById('sidebarOverlay');
            if (overlay) {
                overlay.classList.add('visible');
            }
        },

        // 移除侧边栏遮罩层（兼容旧逻辑）
        removeSidebarOverlay: function() {
            const overlay = document.getElementById('sidebarOverlay');
            if (overlay) {
                overlay.classList.remove('visible');
            }
        },

        // 优化卡片布局（移动端）
        optimizeCardsForMobile: function() {
            const cards = document.querySelectorAll('.card');
            cards.forEach(card => {
                card.style.marginBottom = '1rem';
                card.style.padding = '1rem';
            });

            // 优化统计卡片
            const statCards = document.querySelectorAll('.stat-card');
            statCards.forEach(card => {
                card.style.marginBottom = '1rem';
                card.style.padding = '1.5rem';
            });
        },

        // 优化卡片布局（平板）
        optimizeCardsForTablet: function() {
            const cards = document.querySelectorAll('.card');
            cards.forEach(card => {
                card.style.marginBottom = '1.5rem';
                card.style.padding = '1.5rem';
            });
        },

        // 优化按钮大小（移动端）
        optimizeButtonsForMobile: function() {
            const buttons = document.querySelectorAll('.btn');
            buttons.forEach(button => {
                button.style.padding = '0.75rem 1rem';
                button.style.fontSize = '1rem';
                button.style.minHeight = '44px'; // 触摸友好尺寸
            });
        },

        // 优化按钮大小（平板）
        optimizeButtonsForTablet: function() {
            const buttons = document.querySelectorAll('.btn');
            buttons.forEach(button => {
                button.style.padding = '0.625rem 1.25rem';
                button.style.fontSize = '0.875rem';
            });
        },

        // 优化表格（移动端）
        optimizeTablesForMobile: function() {
            const tables = document.querySelectorAll('.table');
            tables.forEach(table => {
                table.classList.add('table-responsive');

                // 添加移动端表格样式
                const wrapper = document.createElement('div');
                wrapper.className = 'table-wrapper';
                wrapper.style.overflowX = 'auto';
                wrapper.style.webkitOverflowScrolling = 'touch';

                table.parentNode.insertBefore(wrapper, table);
                wrapper.appendChild(table);
            });
        },

        // 恢复默认布局
        restoreDefaultLayout: function() {
            // 恢复卡片样式
            const cards = document.querySelectorAll('.card');
            cards.forEach(card => {
                card.style.marginBottom = '';
                card.style.padding = '';
            });

            // 恢复按钮样式
            const buttons = document.querySelectorAll('.btn');
            buttons.forEach(button => {
                button.style.padding = '';
                button.style.fontSize = '';
                button.style.minHeight = '';
            });

            // 移除移动端样式类
            document.body.classList.remove('mobile-device', 'tablet-device');
        },

        // 优化内容区域
        optimizeContentArea: function() {
            const contentArea = document.querySelector('.main-content');
            if (!contentArea) return;

            switch (this.currentDevice) {
                case 'mobile':
                    contentArea.style.padding = '1rem';
                    contentArea.style.marginLeft = '0';
                    break;
                case 'tablet':
                    contentArea.style.padding = '1.5rem';
                    contentArea.style.marginLeft = '0';
                    break;
                default:
                    contentArea.style.padding = '';
                    contentArea.style.marginLeft = '';
                    break;
            }
        },

        // 添加移动端CSS类
        addMobileStyles: function() {
            const style = document.createElement('style');
            style.textContent = `
                /* 移动端优化样式 */
                .mobile-device .sidebar {
                    position: fixed !important;
                    z-index: 1000 !important;
                    transform: translateX(-100%);
                    transition: transform 0.3s ease;
                }

                .mobile-device .sidebar.open {
                    transform: translateX(0);
                }

                .mobile-device .app-main {
                    margin-left: 0 !important;
                }

                .mobile-device .mobile-toggle {
                    display: block !important;
                }

                .mobile-device .theme-toggle {
                    top: 70px !important;
                }

                /* 平板优化样式 */
                .tablet-device .sidebar {
                    width: 220px !important;
                }

                .tablet-device .sidebar .nav-link {
                    padding: 0.75rem 1rem !important;
                }

                .tablet-device .sidebar .nav-link i {
                    margin-right: 0.5rem !important;
                }

                .tablet-device .app-main {
                    margin-left: 220px !important;
                }

                /* 触摸优化 */
                @media (hover: none) {
                    .btn:active,
                    .nav-link:active {
                        transform: scale(0.98);
                    }
                }

                /* 横向模式优化 */
                @media (max-height: 500px) and (orientation: landscape) {
                    .sidebar {
                        overflow-y: auto;
                    }
                }
            `;
            document.head.appendChild(style);
        }
    };

    // 页面加载完成后初始化
    document.addEventListener('DOMContentLoaded', function() {
        ResponsiveManager.init();
    });

    // 暴露到全局
    window.ResponsiveManager = ResponsiveManager;

})();

function setSidebarVisibility(shouldOpen) {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (!sidebar) return;

    sidebar.classList.toggle('open', shouldOpen);
    sidebar.classList.toggle('show', shouldOpen);

    const isMobile = window.innerWidth <= 1024;

    if (overlay) {
        overlay.classList.toggle('visible', shouldOpen && isMobile);
    }

    if (shouldOpen && isMobile) {
        document.body.classList.add('sidebar-open');
    } else {
        document.body.classList.remove('sidebar-open');
    }
}

// 移动端菜单切换函数
function toggleSidebar(force) {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;

    const shouldOpen = typeof force === 'boolean'
        ? force
        : !sidebar.classList.contains('open');

    setSidebarVisibility(shouldOpen);
}

// 全局函数兼容
window.toggleSidebar = toggleSidebar;

// 监听主题变化
document.addEventListener('themeChanged', function(e) {
    console.log('主题已切换为:', e.detail.theme);
    // 可以在这里添加主题切换后的额外处理
});

// 添加CSS动画
const additionalStyles = `
    /* 移动端菜单动画 */
    .sidebar {
        transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* 遮罩层动画 */
    .sidebar-overlay {
        animation: fadeIn 0.3s ease;
    }

    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    /* 内容区域动画 */
    .content-section {
        animation: slideIn 0.3s ease;
    }

    @keyframes slideIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* 加载动画优化 */
    .loading {
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    /* 脉冲动画 */
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }

    .pulse {
        animation: pulse 2s infinite;
    }

    /* 悬浮效果 */
    .hover-lift {
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }

    .hover-lift:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    }
`;

// 添加额外的CSS样式
const style = document.createElement('style');
style.textContent = additionalStyles;
document.head.appendChild(style);

// 添加移动端CSS类
if (!document.querySelector('style[data-responsive]')) {
    ResponsiveManager.addMobileStyles();
}