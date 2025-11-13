/**
 * 简洁主题切换功能
 * 蓝白主题 + 黑暗模式支持
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

        // 当前主题
        currentTheme: 'light',

        // 初始化
        init: function() {
            this.loadTheme();
            this.bindEvents();
            this.updateUI();
        },

        // 从localStorage加载主题设置
        loadTheme: function() {
            const savedTheme = localStorage.getItem('theme') || 'light';
            this.setTheme(savedTheme, false);
        },

        // 设置主题
        setTheme: function(theme, save = true) {
            if (!this.themes[theme]) return;

            const html = document.documentElement;
            const oldTheme = this.currentTheme;

            // 移除旧主题类
            if (oldTheme === 'dark') {
                html.removeAttribute('data-theme');
            }

            // 应用新主题
            if (theme === 'dark') {
                html.setAttribute('data-theme', 'dark');
            }

            this.currentTheme = theme;

            // 保存到localStorage
            if (save) {
                localStorage.setItem('theme', theme);
            }

            // 更新UI
            this.updateUI();

            // 触发自定义事件
            this.dispatchThemeChange(theme);
        },

        // 切换主题
        toggleTheme: function() {
            const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
            this.setTheme(newTheme);
        },

        // 更新UI
        updateUI: function() {
            const toggleButton = document.getElementById('themeToggle');
            if (!toggleButton) return;

            const themeConfig = this.themes[this.currentTheme];
            const icon = toggleButton.querySelector('i');
            const text = toggleButton.querySelector('span');

            if (icon) {
                icon.className = `bi ${themeConfig.icon}`;
            }

            if (text) {
                text.textContent = themeConfig.name;
            }

            toggleButton.setAttribute('aria-label', `切换到${this.currentTheme === 'light' ? '深色' : '浅色'}模式`);
        },

        // 绑定事件
        bindEvents: function() {
            const toggleButton = document.getElementById('themeToggle');
            if (toggleButton) {
                toggleButton.addEventListener('click', () => {
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
            return this.currentTheme;
        }
    };

    // 页面加载完成后初始化
    document.addEventListener('DOMContentLoaded', function() {
        ThemeManager.init();
    });

    // 暴露到全局
    window.ThemeManager = ThemeManager;
    window.toggleTheme = function() {
        ThemeManager.toggleTheme();
    };

})();