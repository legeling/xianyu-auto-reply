/**
 * 主题切换功能 - 简洁优雅版本
 * 支持蓝白主题和黑暗模式
 */

(function() {
    'use strict';

    // 主题管理器
    const ThemeManager = {
        // 主题配置
        themes: {
            light: {
                name: '浅色模式',
                icon: 'bi-sun-fill',
                class: ''
            },
            dark: {
                name: '深色模式',
                icon: 'bi-moon-fill',
                class: 'dark'
            }
        },

        // 初始化主题
        init: function() {
            this.loadTheme();
            this.createThemeToggle();
            this.bindEvents();
        },

        // 从localStorage加载主题设置
        loadTheme: function() {
            const savedTheme = localStorage.getItem('theme') || 'light';
            this.setTheme(savedTheme, false);
        },

        // 设置主题
        setTheme: function(theme, save = true) {
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');

            if (currentTheme === theme) return;

            // 移除旧主题
            if (currentTheme) {
                html.removeAttribute('data-theme');
            }

            // 应用新主题
            if (theme === 'dark') {
                html.setAttribute('data-theme', 'dark');
            }

            // 更新切换按钮
            this.updateToggleButton(theme);

            // 保存到localStorage
            if (save) {
                localStorage.setItem('theme', theme);
            }

            // 触发自定义事件
            this.dispatchThemeChange(theme);
        },

        // 切换主题
        toggleTheme: function() {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            this.setTheme(newTheme);
        },

        // 创建主题切换按钮
        createThemeToggle: function() {
            // 创建切换按钮
            const toggleButton = document.createElement('button');
            toggleButton.className = 'theme-toggle-btn';
            toggleButton.setAttribute('aria-label', '切换主题');
            toggleButton.innerHTML = '<i class="bi bi-sun-fill"></i>';

            // 添加到页面
            const topBar = document.querySelector('.top-bar') || document.body;
            topBar.appendChild(toggleButton);

            // 保存引用
            this.toggleButton = toggleButton;
        },

        // 更新切换按钮状态
        updateToggleButton: function(theme) {
            if (!this.toggleButton) return;

            const icon = this.toggleButton.querySelector('i');
            const themeConfig = this.themes[theme];

            if (icon) {
                icon.className = themeConfig.icon;
            }

            this.toggleButton.setAttribute('aria-label', `切换到${themeConfig.name}`);
        },

        // 绑定事件
        bindEvents: function() {
            // 主题切换按钮点击事件
            if (this.toggleButton) {
                this.toggleButton.addEventListener('click', () => {
                    this.toggleTheme();
                });
            }

            // 监听系统主题变化
            if (window.matchMedia) {
                const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
                mediaQuery.addEventListener('change', (e) => {
                    // 如果用户没有手动设置过主题，则跟随系统
                    if (!localStorage.getItem('theme')) {
                        this.setTheme(e.matches ? 'dark' : 'light');
                    }
                });
            }
        },

        // 触发自定义事件
        dispatchThemeChange: function(theme) {
            const event = new CustomEvent('themeChanged', {
                detail: { theme: theme }
            });
            document.dispatchEvent(event);
        },

        // 获取当前主题
        getCurrentTheme: function() {
            return document.documentElement.getAttribute('data-theme') || 'light';
        },

        // 重置为主题（用于重置功能）
        reset: function() {
            localStorage.removeItem('theme');
            this.setTheme('light');
        }
    };

    // 页面加载完成后初始化
    document.addEventListener('DOMContentLoaded', function() {
        ThemeManager.init();
    });

    // 暴露到全局
    window.ThemeManager = ThemeManager;

})();