/**
 * 闲鱼助手 - 简洁版前端逻辑
 * 核心功能：账号管理、关键词设置、界面切换
 */

(function() {
    'use strict';

    // 全局状态管理
    const App = {
        // 当前激活的账号
        currentAccount: null,

        // 账号列表
        accounts: [],

        // 关键词列表
        keywords: [],

        // 商品列表
        items: [],

        // 初始化应用
        init: function() {
            this.bindEvents();
            this.loadDashboard();
            console.log('闲鱼助手 - 简洁版已启动');
        },

        // 绑定事件
        bindEvents: function() {
            // 导航点击事件
            document.querySelectorAll('.nav-link').forEach(link => {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    const section = link.getAttribute('onclick').match(/showSection\('(\w+)'\)/)[1];
                    this.showSection(section);
                });
            });

            // 快速操作点击事件
            document.querySelectorAll('.quick-action').forEach(action => {
                action.addEventListener('click', () => {
                    const section = action.getAttribute('onclick').match(/showSection\('(\w+)'\)/)[1];
                    this.showSection(section);
                });
            });
        },

        // 显示指定部分
        showSection: function(sectionName) {
            console.log('切换到:', sectionName);

            // 隐藏所有内容区域
            document.querySelectorAll('.content-section').forEach(section => {
                section.style.display = 'none';
            });

            // 移除所有导航的激活状态
            document.querySelectorAll('.nav-link').forEach(link => {
                link.classList.remove('active');
            });

            // 显示目标区域
            const targetSection = document.getElementById(sectionName + '-section');
            if (targetSection) {
                targetSection.style.display = 'block';
            }

            // 激活对应导航
            const activeLink = document.querySelector(`[onclick="showSection('${sectionName}')"]`);
            if (activeLink) {
                activeLink.classList.add('active');
            }

            // 加载对应数据
            this.loadSectionData(sectionName);
        },

        // 加载部分内容数据
        loadSectionData: function(sectionName) {
            switch(sectionName) {
                case 'dashboard':
                    this.loadDashboard();
                    break;
                case 'accounts':
                    this.loadAccounts();
                    break;
                case 'keywords':
                    this.loadKeywords();
                    break;
                case 'items':
                    this.loadItems();
                    break;
                case 'settings':
                    this.loadSettings();
                    break;
            }
        },

        // 加载仪表板数据
        loadDashboard: function() {
            console.log('加载仪表板数据');
            // 这里可以添加实际的数据加载逻辑
            this.updateDashboardStats();
        },

        // 更新仪表板统计
        updateDashboardStats: function() {
            // 模拟数据统计
            const stats = {
                accounts: this.accounts.length,
                keywords: this.keywords.length,
                items: this.items.length
            };

            // 更新统计数字
            const statElements = document.querySelectorAll('.card h3');
            statElements.forEach((element, index) => {
                const keys = Object.keys(stats);
                if (keys[index]) {
                    element.textContent = stats[keys[index]];
                }
            });
        },

        // 加载账号列表
        loadAccounts: function() {
            console.log('加载账号列表');
            // 这里添加实际的API调用逻辑
            this.renderAccounts();
        },

        // 渲染账号列表
        renderAccounts: function() {
            const container = document.querySelector('#accounts-section .card-body');
            if (!container) return;

            if (this.accounts.length === 0) {
                container.innerHTML = `
                    <div class="text-center py-5">
                        <i class="bi bi-person-plus display-1 text-muted mb-4"></i>
                        <h5 class="text-muted">暂无账号</h5>
                        <p class="text-muted">点击上方按钮添加你的第一个闲鱼账号</p>
                    </div>
                `;
            } else {
                // 渲染账号列表
                let html = '<div class="list-group">';
                this.accounts.forEach(account => {
                    html += `
                        <div class="list-group-item d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="mb-1">${account.name || '未命名账号'}</h6>
                                <small class="text-muted">${account.status || '状态未知'}</small>
                            </div>
                            <div class="btn-group" role="group">
                                <button class="btn btn-sm btn-outline-primary" onclick="App.editAccount('${account.id}')">
                                    <i class="bi bi-pencil"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-danger" onclick="App.deleteAccount('${account.id}')">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
                container.innerHTML = html;
            }
        },

        // 加载关键词
        loadKeywords: function() {
            console.log('加载关键词');
            this.renderKeywords();
        },

        // 渲染关键词列表
        renderKeywords: function() {
            const container = document.querySelector('#keywords-section .card-body');
            if (!container) return;

            if (this.keywords.length === 0) {
                container.innerHTML = `
                    <div class="text-center py-5">
                        <i class="bi bi-chat-text display-1 text-muted mb-4"></i>
                        <h5 class="text-muted">暂无关键词</h5>
                        <p class="text-muted">设置自动回复关键词，让回复更智能</p>
                    </div>
                `;
            } else {
                let html = '<div class="list-group">';
                this.keywords.forEach(keyword => {
                    html += `
                        <div class="list-group-item d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="mb-1">${keyword.keyword}</h6>
                                <small class="text-muted">${keyword.reply}</small>
                            </div>
                            <div class="btn-group" role="group">
                                <button class="btn btn-sm btn-outline-primary" onclick="App.editKeyword('${keyword.id}')">
                                    <i class="bi bi-pencil"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-danger" onclick="App.deleteKeyword('${keyword.id}')">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
                container.innerHTML = html;
            }
        },

        // 加载商品
        loadItems: function() {
            console.log('加载商品');
            this.renderItems();
        },

        // 渲染商品列表
        renderItems: function() {
            const container = document.querySelector('#items-section .card-body');
            if (!container) return;

            if (this.items.length === 0) {
                container.innerHTML = `
                    <div class="text-center py-5">
                        <i class="bi bi-box display-1 text-muted mb-4"></i>
                        <h5 class="text-muted">暂无商品</h5>
                        <p class="text-muted">系统会自动收集你的商品信息</p>
                    </div>
                `;
            } else {
                let html = '<div class="list-group">';
                this.items.forEach(item => {
                    html += `
                        <div class="list-group-item d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="mb-1">${item.title || '未命名商品'}</h6>
                                <small class="text-muted">${item.price || '价格未设置'}</small>
                            </div>
                            <div class="btn-group" role="group">
                                <button class="btn btn-sm btn-outline-primary" onclick="App.viewItem('${item.id}')">
                                    <i class="bi bi-eye"></i>
                                </button>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
                container.innerHTML = html;
            }
        },

        // 加载设置
        loadSettings: function() {
            console.log('加载设置');
            // 这里可以加载保存的设置
        },

        // 显示添加账号模态框
        showAddAccountModal: function() {
            // 创建一个简单的模态框
            const modal = this.createModal('添加账号', `
                <div class="mb-3">
                    <label class="form-label">账号名称</label>
                    <input type="text" class="form-control" id="accountName" placeholder="输入账号名称">
                </div>
                <div class="mb-3">
                    <label class="form-label">Cookie</label>
                    <textarea class="form-control" id="accountCookie" rows="4" placeholder="粘贴闲鱼Cookie"></textarea>
                </div>
            `, () => {
                const name = document.getElementById('accountName').value;
                const cookie = document.getElementById('accountCookie').value;
                if (name && cookie) {
                    this.addAccount(name, cookie);
                }
            });
            document.body.appendChild(modal);
        },

        // 显示添加关键词模态框
        showAddKeywordModal: function() {
            const modal = this.createModal('添加关键词', `
                <div class="mb-3">
                    <label class="form-label">关键词</label>
                    <input type="text" class="form-control" id="keywordText" placeholder="输入触发关键词">
                </div>
                <div class="mb-3">
                    <label class="form-label">回复内容</label>
                    <textarea class="form-control" id="replyText" rows="3" placeholder="输入自动回复内容"></textarea>
                </div>
            `, () => {
                const keyword = document.getElementById('keywordText').value;
                const reply = document.getElementById('replyText').value;
                if (keyword && reply) {
                    this.addKeyword(keyword, reply);
                }
            });
            document.body.appendChild(modal);
        },

        // 创建模态框
        createModal: function(title, content, onConfirm) {
            const modal = document.createElement('div');
            modal.className = 'modal fade show';
            modal.style.display = 'block';
            modal.style.backgroundColor = 'rgba(0,0,0,0.5)';

            modal.innerHTML = `
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${title}</h5>
                            <button type="button" class="btn-close" onclick="this.closest('.modal').remove()"></button>
                        </div>
                        <div class="modal-body">
                            ${content}
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-outline" onclick="this.closest('.modal').remove()">取消</button>
                            <button type="button" class="btn btn-primary" onclick="this.closest('.modal').remove()">确定</button>
                        </div>
                    </div>
                </div>
            `;

            // 绑定确认按钮事件
            const confirmBtn = modal.querySelector('.btn-primary');
            confirmBtn.addEventListener('click', () => {
                onConfirm();
                modal.remove();
            });

            return modal;
        },

        // 添加账号
        addAccount: function(name, cookie) {
            const account = {
                id: Date.now().toString(),
                name: name,
                cookie: cookie,
                status: '未连接',
                createdAt: new Date().toISOString()
            };

            this.accounts.push(account);
            this.loadAccounts();
            this.updateDashboardStats();

            // 显示成功提示
            this.showToast('账号添加成功', 'success');
        },

        // 添加关键词
        addKeyword: function(keyword, reply) {
            const keywordObj = {
                id: Date.now().toString(),
                keyword: keyword,
                reply: reply,
                createdAt: new Date().toISOString()
            };

            this.keywords.push(keywordObj);
            this.loadKeywords();
            this.updateDashboardStats();

            // 显示成功提示
            this.showToast('关键词添加成功', 'success');
        },

        // 编辑账号
        editAccount: function(id) {
            console.log('编辑账号:', id);
            // 实现编辑功能
        },

        // 删除账号
        deleteAccount: function(id) {
            if (confirm('确定要删除这个账号吗？')) {
                this.accounts = this.accounts.filter(account => account.id !== id);
                this.loadAccounts();
                this.updateDashboardStats();
                this.showToast('账号删除成功', 'success');
            }
        },

        // 编辑关键词
        editKeyword: function(id) {
            console.log('编辑关键词:', id);
            // 实现编辑功能
        },

        // 删除关键词
        deleteKeyword: function(id) {
            if (confirm('确定要删除这个关键词吗？')) {
                this.keywords = this.keywords.filter(keyword => keyword.id !== id);
                this.loadKeywords();
                this.updateDashboardStats();
                this.showToast('关键词删除成功', 'success');
            }
        },

        // 显示提示信息
        showToast: function(message, type = 'info') {
            const toast = document.createElement('div');
            toast.className = `toast show position-fixed`;
            toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 250px;';

            const bgClass = type === 'success' ? 'bg-success' : type === 'error' ? 'bg-danger' : 'bg-info';

            toast.innerHTML = `
                <div class="toast-header ${bgClass} text-white">
                    <strong class="me-auto">提示</strong>
                    <button type="button" class="btn-close btn-close-white" onclick="this.closest('.toast').remove()"></button>
                </div>
                <div class="toast-body">${message}</div>
            `;

            document.body.appendChild(toast);

            // 3秒后自动移除
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.remove();
                }
            }, 3000);
        },

        // 主题切换（与theme.js配合）
        toggleTheme: function() {
            if (window.ThemeManager) {
                window.ThemeManager.toggleTheme();
            }
        }
    };

    // 页面加载完成后初始化
    document.addEventListener('DOMContentLoaded', function() {
        App.init();
    });

    // 暴露到全局
    window.App = App;

})();\n\n// 辅助函数\nfunction showSection(sectionName) {\n    window.App.showSection(sectionName);\n}\n\nfunction showAddAccountModal() {\n    window.App.showAddAccountModal();\n}\n\nfunction showAddKeywordModal() {\n    window.App.showAddKeywordModal();\n}\n\nfunction toggleTheme() {\n    window.App.toggleTheme();\n}