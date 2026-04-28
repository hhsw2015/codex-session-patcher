import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '../services/api'
import { useSettingsStore } from './settingsStore'

export const useSessionStore = defineStore('session', () => {
  const sessions = ref([])
  const selectedId = ref(null)
  const preview = ref(null)
  const loading = ref(false)
  const previewLoading = ref(false)
  const aiRewrite = ref(null)
  const aiRewriteLoading = ref(false)
  const lastError = ref(null) // 最近一次错误信息，组件层可监听并展示
  const activeTab = ref('codex') // 'codex' | 'claude_code' | 'opencode'
  const incrementalFromLine = ref(0) // 增量扫描起始行号，0=全量
  const isSearchMode = ref(false) // 是否处于搜索模式
  const undoStack = ref([]) // [{sessionId, operation, backupPath, description}]
  let _tabInitialized = false

  // 按格式拆分
  const codexSessions = computed(() => sessions.value.filter(s => s.format === 'codex'))
  const claudeSessions = computed(() => sessions.value.filter(s => s.format === 'claude_code'))
  const opencodeSessions = computed(() => sessions.value.filter(s => s.format === 'opencode'))

  // 当前 Tab 的会话
  const activeTabSessions = computed(() => {
    if (activeTab.value === 'codex') return codexSessions.value
    if (activeTab.value === 'opencode') return opencodeSessions.value
    return claudeSessions.value
  })

  async function fetchSessions(checkRefusal = true, format = 'auto', scanMode = '') {
    loading.value = true
    try {
      // 固定拉取全部格式，客户端按 format 字段拆分
      const data = await api.getSessions(!checkRefusal, format, scanMode)
      sessions.value = data.sessions

      // 仅首次加载时自动选 Tab，刷新时保留当前 Tab
      if (!_tabInitialized) {
        _tabInitialized = true
        // Codex 优先，有数据就停在 Codex
        if (codexSessions.value.length > 0) {
          activeTab.value = 'codex'
        } else {
          const settingsStore = useSettingsStore()
          if (settingsStore.claudeCodeEnabled && claudeSessions.value.length > 0) {
            activeTab.value = 'claude_code'
          } else if (opencodeSessions.value.length > 0) {
            activeTab.value = 'opencode'
          }
        }
      }

      // 自动选中当前 Tab 的第一条会话（仅初次无选中时）
      if (!selectedId.value && activeTabSessions.value.length > 0) {
        await selectSession(activeTabSessions.value[0].id)
      }
    } catch (error) {
      console.error('Failed to fetch sessions:', error)
      lastError.value = error.message || '加载会话列表失败'
    } finally {
      loading.value = false
    }
  }

  function setActiveTab(tab) {
    activeTab.value = tab
    // Tab 切换时重置预览，但不重新请求 API
    const stillExists = activeTabSessions.value.find(s => s.id === selectedId.value)
    if (!stillExists) {
      selectedId.value = null
      preview.value = null
      aiRewrite.value = null
    }
  }

  async function selectSession(id) {
    selectedId.value = id
    preview.value = null
    aiRewrite.value = null

    previewLoading.value = true
    try {
      const data = await api.previewSession(id)
      preview.value = data
    } catch (error) {
      console.error('Failed to preview session:', error)
      lastError.value = error.message || '预览会话失败'
    } finally {
      previewLoading.value = false
    }
  }

  async function previewSession(id) {
    previewLoading.value = true
    try {
      const data = await api.previewSession(id || selectedId.value)
      preview.value = data
      return data
    } catch (error) {
      console.error('Failed to preview session:', error)
      throw error
    } finally {
      previewLoading.value = false
    }
  }

  async function requestAIRewrite(id) {
    aiRewriteLoading.value = true
    aiRewrite.value = null
    try {
      const data = await api.aiRewriteSession(id || selectedId.value)
      if (data.success) {
        aiRewrite.value = data
        if (preview.value && preview.value.changes.length > 0 && data.items) {
          for (const item of data.items) {
            const change = preview.value.changes.find(c => c.line_num === item.line_num)
            if (change) {
              change.replacement = item.replacement
              change._ai_generated = true
            }
          }
        }
      }
      return data
    } catch (error) {
      console.error('AI rewrite failed:', error)
      throw error
    } finally {
      aiRewriteLoading.value = false
    }
  }

  async function patchSession(id, selectedLines = null, cleanReasoning = null, customReplacements = null) {
    let replacements = customReplacements
    if (!replacements && aiRewrite.value?.items?.length > 0) {
      replacements = aiRewrite.value.items.map(item => ({
        line_num: item.line_num,
        replacement_text: item.replacement
      }))
    }
    try {
      const sid = id || selectedId.value
      const data = await api.patchSession(sid, replacements, selectedLines, cleanReasoning)
      if (data.success) {
        if (data.backup_path) {
          const desc = replacements
            ? `改写 ${replacements.length} 条消息`
            : `批量处理 (${data.changes?.length || 0} 处)`
          undoStack.value.push({
            sessionId: sid,
            operation: 'patch',
            backupPath: data.backup_path,
            description: desc,
          })
        }
        aiRewrite.value = null
        await previewSession(sid)
        fetchSessions().catch(() => {})
      }
      return data
    } catch (error) {
      console.error('Failed to patch session:', error)
      throw error
    }
  }

  // 搜索会话内容
  async function searchSessions(query) {
    if (!query || !query.trim()) {
      isSearchMode.value = false
      await fetchSessions()
      return
    }
    loading.value = true
    isSearchMode.value = true
    const previousSelectedId = selectedId.value
    try {
      const data = await api.searchSessions(query, 'auto')
      sessions.value = data.sessions
      // 如果之前有选中的会话，且在搜索结果中，保留选中状态和预览
      const stillExists = previousSelectedId && data.sessions.some(s => s.id === previousSelectedId)
      if (!stillExists) {
        // 只有当选中的会话不在搜索结果中时才清除
        selectedId.value = null
        preview.value = null
        aiRewrite.value = null
      }
    } catch (error) {
      console.error('Failed to search sessions:', error)
      lastError.value = error.message || '搜索失败'
    } finally {
      loading.value = false
    }
  }

  // 清除搜索（恢复全部会话）
  async function clearSearch() {
    isSearchMode.value = false
    await fetchSessions()
  }

  async function listBackups(id) {
    return api.listBackups(id || selectedId.value)
  }

  async function restoreSession(id, backupFilename) {
    const sid = id || selectedId.value
    const data = await api.restoreSession(sid, backupFilename)
    if (data.success) {
      api.clearCache('sessions')
      await previewSession(sid)
      fetchSessions().catch(() => {})
    }
    return data
  }

  async function deleteMessages(id, lineNums, deletePaired = true) {
    try {
      const sid = id || selectedId.value
      const data = await api.deleteMessages(sid, lineNums, deletePaired)
      if (data.success) {
        if (data.backup_path) {
          undoStack.value.push({
            sessionId: sid,
            operation: 'delete',
            backupPath: data.backup_path,
            description: `删除 ${data.deleted_lines.length} 行 (L${lineNums.join(',L')})`,
          })
        }
        await previewSession(sid)
        fetchSessions().catch(() => {})
      }
      return data
    } catch (error) {
      console.error('Failed to delete messages:', error)
      throw error
    }
  }

  async function scanSingleSession(id, mode = 'full') {
    try {
      const data = await api.scanSession(id || selectedId.value, mode)
      const session = sessions.value.find(s => s.id === (id || selectedId.value))
      if (session && data) {
        session.has_refusal = data.has_refusal
        session.refusal_count = data.refusal_count
        session.cached = false
      }
      incrementalFromLine.value = data.incremental_from_line || 0
      return data
    } catch (error) {
      console.error('Failed to scan session:', error)
      throw error
    }
  }

  async function cleanThinking(id) {
    try {
      const sid = id || selectedId.value
      const data = await api.cleanThinking(sid)
      if (data.success) {
        if (data.backup_path) {
          undoStack.value.push({
            sessionId: sid,
            operation: 'clean-thinking',
            backupPath: data.backup_path,
            description: `清理 thinking blocks (${data.changes?.length || 0} 处)`,
          })
        }
        await previewSession(sid)
        fetchSessions().catch(() => {})
      }
      return data
    } catch (error) {
      console.error('Failed to clean thinking:', error)
      throw error
    }
  }

  async function undoLast() {
    if (undoStack.value.length === 0) return null
    const last = undoStack.value.pop()
    try {
      const backupFilename = last.backupPath.split('/').pop()
      const data = await api.restoreSession(last.sessionId, backupFilename)
      if (data.success) {
        await previewSession(last.sessionId)
        fetchSessions().catch(() => {})
      } else if (data.message && data.message.includes('不存在')) {
        // Backup was cleaned up by max_backups limit, discard stale undo entries
        console.warn('Undo backup missing, clearing stale entries')
        undoStack.value = []
      }
      return data
    } catch (error) {
      console.error('Undo failed:', error)
      undoStack.value.push(last)
      throw error
    }
  }

  function getSelectedSession() {
    return sessions.value.find(s => s.id === selectedId.value)
  }

  return {
    sessions,
    selectedId,
    preview,
    loading,
    previewLoading,
    aiRewrite,
    aiRewriteLoading,
    lastError,
    activeTab,
    incrementalFromLine,
    isSearchMode,
    codexSessions,
    claudeSessions,
    opencodeSessions,
    activeTabSessions,
    fetchSessions,
    setActiveTab,
    selectSession,
    previewSession,
    requestAIRewrite,
    patchSession,
    searchSessions,
    clearSearch,
    listBackups,
    restoreSession,
    getSelectedSession,
    deleteMessages,
    scanSingleSession,
    cleanThinking,
    undoLast,
    undoStack,
  }
})
