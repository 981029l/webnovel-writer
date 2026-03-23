// Copyright (c) 2026 左岚. All rights reserved.
// Vue Router 配置 — 两层多项目架构

import { createRouter, createWebHistory } from 'vue-router'

const routes = [
    // Layer 1: Project overview (no sidebar)
    {
        path: '/',
        name: 'home',
        component: () => import('../views/HomeView.vue')
    },

    // Layer 2: Workspace (with sidebar via WorkspaceLayout)
    {
        path: '/workspace',
        component: () => import('../views/WorkspaceLayout.vue'),
        children: [
            {
                path: '',
                redirect: '/workspace/dashboard'
            },
            {
                path: 'dashboard',
                name: 'dashboard',
                component: () => import('../views/DashboardView.vue')
            },
            {
                path: 'project',
                name: 'project',
                component: () => import('../views/ProjectView.vue')
            },
            {
                path: 'prompts',
                name: 'prompts',
                component: () => import('../views/PromptConfigView.vue')
            },
            {
                path: 'outline',
                name: 'outline',
                component: () => import('../views/OutlineView.vue')
            },
            {
                path: 'write',
                name: 'write',
                component: () => import('../views/WriteView.vue')
            },
            {
                path: 'write/:chapter',
                name: 'write-chapter',
                component: () => import('../views/WriteView.vue')
            },
            {
                path: 'entities',
                name: 'entities',
                component: () => import('../views/EntityView.vue')
            },
            {
                path: 'rag',
                name: 'rag',
                component: () => import('../views/RagView.vue')
            },
            {
                path: 'characters',
                name: 'characters',
                component: () => import('../views/CharacterView.vue')
            },
            {
                path: 'relations',
                name: 'relations',
                component: () => import('../views/RelationGraphView.vue')
            },
            {
                path: 'fanqie',
                name: 'fanqie',
                component: () => import('../views/FanqiePublishView.vue')
            }
        ]
    },

    // Legacy redirects
    { path: '/project', redirect: '/workspace/project' },
    { path: '/prompts', redirect: '/workspace/prompts' },
    { path: '/outline', redirect: '/workspace/outline' },
    { path: '/write', redirect: '/workspace/write' },
    { path: '/write/:chapter', redirect: to => `/workspace/write/${to.params.chapter}` },
    { path: '/entities', redirect: '/workspace/entities' },
    { path: '/rag', redirect: '/workspace/rag' },
    { path: '/characters', redirect: '/workspace/characters' },
    { path: '/relations', redirect: '/workspace/relations' }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

// Navigation guard: workspace routes require a selected project
router.beforeEach((to) => {
    if (to.path.startsWith('/workspace')) {
        const hasProject = sessionStorage.getItem('webnovel_project_root')
        if (!hasProject) {
            return '/'
        }
    }
})

export default router
