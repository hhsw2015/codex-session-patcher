<template>
  <div class="preview-panel">
    <div v-if="!session" class="empty-state">
      <n-empty :description="$t('session.selectPrompt')" />
    </div>

    <div v-else-if="!preview" class="empty-state">
      <n-spin size="large" />
    </div>

    <div v-else class="preview-container">
      <!-- Tab 切换 -->
      <div class="preview-tabs">
        <div
          class="tab-item"
          :class="{ active: activeTab === 'changes' }"
          @click="activeTab = 'changes'"
        >
          <n-icon><SwapHorizontalOutline /></n-icon>
          <span>{{ $t('preview.changes') }}</span>
          <n-tag v-if="preview.has_changes" type="warning" size="small" style="margin-left: 4px">
            {{ preview.changes.length }}
          </n-tag>
        </div>
        <div
          class="tab-item"
          :class="{ active: activeTab === 'diff' }"
          @click="activeTab = 'diff'"
        >
          <n-icon><CodeOutline /></n-icon>
          <span>{{ $t('preview.diff') }}</span>
        </div>
        <div
          class="tab-item"
          :class="{ active: activeTab === 'conversation' }"
          @click="activeTab = 'conversation'"
        >
          <n-icon><ChatbubbleEllipsesOutline /></n-icon>
          <span>{{ $t('preview.conversation') || '对话' }}</span>
          <n-tag v-if="preview.total_turns" size="small" :bordered="false" style="margin-left: 4px">
            {{ preview.total_turns }}
          </n-tag>
        </div>
        <!-- 撤销按钮 -->
        <div
          v-if="sessionStore.undoStack.length > 0"
          class="tab-item undo-btn"
          @click="handleUndo"
        >
          <n-icon><ArrowUndoOutline /></n-icon>
          <span>{{ $t('preview.undo') || '撤销' }}</span>
          <n-tag size="small" type="warning" :bordered="false" style="margin-left: 4px">
            {{ sessionStore.undoStack.length }}
          </n-tag>
        </div>
      </div>

      <!-- 修改预览 Tab -->
      <div v-show="activeTab === 'changes'" class="preview-scrollbar">
        <!-- 无拒绝内容时显示对话摘要 -->
        <div v-if="!preview.changes || preview.changes.length === 0" class="no-refusal-content">
          <!-- 状态提示 -->
          <div class="status-banner success-banner" v-if="!preview.has_changes">
            <n-icon color="#18a058"><CheckmarkCircleOutline /></n-icon>
            <span>{{ $t('preview.noRefusal') }}</span>
          </div>
          <div class="status-banner info-banner" v-if="preview.reasoning_count > 0">
            <n-checkbox
              :checked="cleanReasoning"
              @update:checked="emit('update:cleanReasoning', $event)"
            />
            <n-icon color="#2080f0"><InformationCircleOutline /></n-icon>
            <span>{{ $t('preview.willDeleteReasoning', { count: preview.reasoning_count }) }}</span>
          </div>
          <div class="status-banner info-banner thinking-banner-inline" v-if="preview.thinking_count > 0">
            <n-checkbox
              :checked="cleanReasoning"
              @update:checked="emit('update:cleanReasoning', $event)"
            />
            <n-icon color="#8b5cf6"><InformationCircleOutline /></n-icon>
            <span>{{ $t('preview.willDeleteThinking', { count: preview.thinking_count }) }}</span>
          </div>

          <!-- 对话摘要（只读预览，操作按钮在独立 "对话" tab） -->
          <div v-if="preview.conversation_summary && preview.conversation_summary.length > 0" class="conversation-summary">
            <div class="summary-header">
              <span>{{ $t('preview.conversation') }}</span>
              <n-tag size="small" :bordered="false">{{ preview.total_turns }} {{ $t('preview.turns') }}</n-tag>
            </div>
            <div class="summary-list">
              <div
                v-for="(turn, idx) in preview.conversation_summary"
                :key="idx"
                class="summary-turn"
                :class="turn.role"
              >
                <div class="turn-header">
                  <n-tag
                    :type="turn.role === 'user' ? 'info' : 'default'"
                    size="small"
                    :bordered="false"
                  >
                    {{ turn.role === 'user' ? 'User' : 'Assistant' }}
                  </n-tag>
                  <span class="turn-line">L{{ turn.line_num }}</span>
                </div>
                <pre class="turn-content">{{ turn.content }}</pre>
              </div>
            </div>
          </div>
          <div v-else class="empty-content">
            <n-empty :description="$t('preview.noConversation')" />
          </div>
        </div>

        <div v-else class="preview-content">
          <!-- 推理内容提示 -->
          <div v-if="preview.reasoning_count > 0" class="reasoning-banner">
            <n-checkbox
              :checked="cleanReasoning"
              @update:checked="$emit('update:cleanReasoning', $event)"
            />
            <n-icon><InformationCircleOutline /></n-icon>
            <span>{{ $t('preview.willDeleteReasoning', { count: preview.reasoning_count }) }}</span>
          </div>

          <!-- Thinking Block 提示 -->
          <div v-if="preview.thinking_count > 0" class="thinking-banner">
            <n-checkbox
              :checked="cleanReasoning"
              @update:checked="$emit('update:cleanReasoning', $event)"
            />
            <n-icon><InformationCircleOutline /></n-icon>
            <span>{{ $t('preview.willDeleteThinking', { count: preview.thinking_count }) }}</span>
          </div>

          <!-- 选择操作栏 -->
          <div v-if="preview.changes && preview.changes.length > 1" class="select-toolbar">
            <n-checkbox :checked="isAllSelected" @update:checked="toggleSelectAll" />
            <span class="select-label">
              {{ $t('preview.selectedCount', { selected: selectedLines.size, total: preview.changes.length }) }}
            </span>
            <n-button text size="tiny" type="primary" @click="toggleSelectAll">
              {{ isAllSelected ? $t('preview.deselectAll') : $t('preview.selectAll') }}
            </n-button>
          </div>

          <div class="changes-list">
            <div
              v-for="(change, index) in preview.changes"
              :key="index"
              class="change-item"
              :class="{ unselected: !selectedLines.has(change.line_num) }"
            >
              <div class="change-header">
                <n-checkbox
                  :checked="selectedLines.has(change.line_num)"
                  @update:checked="toggleLine(change.line_num)"
                />
                <n-tag
                  :type="changeTagType(change.type)"
                  size="small"
                >
                  {{ changeTagLabel(change.type) }}
                </n-tag>
                <span class="line-num">
                  <template v-if="change.line_nums && change.line_nums.length > 1">
                    {{ change.line_nums.map(n => 'L' + n).join(' ') }}
                  </template>
                  <template v-else>L{{ change.line_num }}</template>
                </span>
                <div v-if="change.type === 'replace'" class="turn-actions" style="margin-left: auto">
                  <n-dropdown :options="messageActions" size="small" @select="(key) => handleMessageAction(key, { line_num: change.line_num, content: change.original || '' })">
                    <n-button text size="tiny" type="default">
                      <template #icon><n-icon size="14"><EllipsisHorizontalOutline /></n-icon></template>
                    </n-button>
                  </n-dropdown>
                </div>
              </div>

              <div v-if="change.type === 'replace'" class="change-content">
                <!-- 显示对应的用户提问 -->
                <template v-for="uq in [findPrecedingUserQuestion(change.line_num)]" :key="'uq-' + change.line_num">
                  <div v-if="uq" class="content-block user-context">
                    <div class="content-label">
                      <n-tag type="info" size="small" :bordered="false">User</n-tag>
                      L{{ uq.line_num }}
                    </div>
                    <pre>{{ uq.content }}</pre>
                  </div>
                </template>
                <div class="content-block original">
                  <div class="content-label">{{ $t('preview.original') }}</div>
                  <pre>{{ change.original }}</pre>
                </div>
                <div class="content-arrow">
                  <n-icon size="20" color="#18a058">
                    <ArrowDownOutline />
                  </n-icon>
                </div>
                <div class="content-block replacement">
                  <div class="content-label">
                    {{ $t('preview.replacement') }}
                    <n-tag v-if="change._ai_generated" size="small" type="success" style="margin-left: 6px">AI</n-tag>
                  </div>
                  <pre>{{ change.replacement }}</pre>
                </div>
              </div>

              <div v-else-if="change.type === 'remove_thinking'" class="change-content">
                <div class="content-block thinking">
                  <div class="content-label">{{ $t('preview.removeThinking') }}</div>
                  <pre>{{ change.content || '(Thinking block)' }}</pre>
                </div>
              </div>

              <div v-else class="change-content">
                <div class="content-block deleted">
                  <div class="content-label">{{ $t('preview.deleted') }}</div>
                  <pre>{{ change.content }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Diff 视图 Tab -->
      <div v-show="activeTab === 'diff'" class="preview-scrollbar">
        <!-- 已清理会话：显示清理前后对比 -->
        <div v-if="preview.diff_items && preview.diff_items.length > 0" class="diff-content">
          <div class="diff-header-banner">
            <n-icon><InformationCircleOutline /></n-icon>
            <span>{{ $t('preview.diffWithBackup') }}</span>
          </div>
          <div
            v-for="(item, index) in preview.diff_items"
            :key="'backup-' + index"
            class="diff-block"
          >
            <div class="diff-line deleted">
              <span class="line-number">{{ item.line_num || '-' }}</span>
              <span class="diff-marker">-</span>
              <pre class="diff-text">{{ item.before }}</pre>
            </div>
            <div class="diff-line added">
              <span class="line-number">{{ item.line_num || '-' }}</span>
              <span class="diff-marker">+</span>
              <pre class="diff-text">{{ item.after }}</pre>
            </div>
          </div>
        </div>

        <!-- 未清理会话：显示待修改的 diff -->
        <div v-else-if="preview.has_changes" class="diff-content">
          <div
            v-for="(change, index) in preview.changes"
            :key="index"
            class="diff-block"
          >
            <!-- 删除行 -->
            <div v-if="change.type === 'delete'" class="diff-line deleted">
              <span class="line-number">{{ change.line_num }}</span>
              <span class="diff-marker">-</span>
              <pre class="diff-text">{{ change.content || $t('preview.reasoningBlocks') }}</pre>
            </div>

            <!-- 移除 Thinking Block -->
            <div v-else-if="change.type === 'remove_thinking'" class="diff-line thinking-removed">
              <span class="line-number">{{ change.line_num }}</span>
              <span class="diff-marker">~</span>
              <pre class="diff-text">{{ change.content || '[Thinking Block]' }}</pre>
            </div>

            <!-- 替换：显示删除和新增 -->
            <template v-else-if="change.type === 'replace'">
              <div class="diff-line deleted">
                <span class="line-number">{{ change.line_num }}</span>
                <span class="diff-marker">-</span>
                <pre class="diff-text">{{ change.original }}</pre>
              </div>
              <div class="diff-line added">
                <span class="line-number">{{ change.line_num }}</span>
                <span class="diff-marker">+</span>
                <pre class="diff-text">{{ change.replacement }}</pre>
                <n-tag v-if="change._ai_generated" size="small" type="success" style="margin-left: 6px; flex-shrink: 0">AI</n-tag>
              </div>
            </template>
          </div>
        </div>

        <div v-else class="empty-content">
          <n-empty :description="$t('preview.noChanges')" type="success">
            <template #icon>
              <n-icon size="48" color="#18a058">
                <CheckmarkCircleOutline />
              </n-icon>
            </template>
          </n-empty>
        </div>
      </div>

      <!-- 对话视图 Tab (独立 tab，始终可用) -->
      <div v-show="activeTab === 'conversation'" class="preview-scrollbar">
        <div v-if="preview.conversation_summary && preview.conversation_summary.length > 0" class="conversation-summary">
          <!-- 搜索框 -->
          <div class="conversation-search">
            <n-input
              v-model:value="conversationSearch"
              :placeholder="$t('preview.searchConversation') || '搜索对话内容...'"
              clearable
              size="small"
            />
          </div>
          <!-- 视图范围切换 -->
          <div class="conversation-filter">
            <n-button-group size="tiny">
              <n-button
                v-if="sessionStore.incrementalFromLine > 0"
                :type="conversationView === 'incremental' ? 'primary' : 'default'"
                @click="conversationView = 'incremental'"
              >
                {{ $t('preview.incrementalOnly') || '仅增量' }} (L{{ sessionStore.incrementalFromLine }}+)
              </n-button>
              <n-button :type="conversationView === 'refusal' ? 'primary' : 'default'" @click="conversationView = 'refusal'">
                {{ $t('preview.refusalOnly') || '仅拒绝' }}
              </n-button>
              <n-button :type="conversationView === 'all' ? 'primary' : 'default'" @click="conversationView = 'all'">
                {{ $t('preview.allConversation') || '全部' }}
              </n-button>
            </n-button-group>
            <n-tag v-if="filteredConversation.length !== (preview.conversation_summary || []).length" size="small" :bordered="false" style="margin-left: 8px">
              {{ filteredConversation.length }} / {{ (preview.conversation_summary || []).length }}
            </n-tag>
          </div>
          <div class="summary-list">
            <div v-if="filteredConversation.length === 0 && debouncedSearch" class="empty-content" style="padding: 16px">
              <n-empty :description="`未找到匹配 '${debouncedSearch}' 的对话`" size="small" />
            </div>
            <div
              v-for="(turn, idx) in filteredConversation"
              :key="idx"
              class="summary-turn"
              :class="turn.role"
            >
              <div class="turn-header">
                <n-tag
                  :type="turn.has_refusal ? 'error' : (turn.role === 'user' ? 'info' : 'default')"
                  size="small"
                  :bordered="false"
                >
                  {{ turn.role === 'user' ? 'User' : 'Assistant' }}
                </n-tag>
                <span class="turn-line">L{{ turn.line_num }}</span>
                <n-tag v-if="turn.has_refusal" size="small" type="error" :bordered="false">refusal</n-tag>
                <div v-if="turn.role === 'assistant'" class="turn-actions">
                  <n-dropdown :options="messageActions" size="small" @select="(key) => handleMessageAction(key, turn)">
                    <n-button text size="tiny" type="default">
                      <template #icon><n-icon size="14"><EllipsisHorizontalOutline /></n-icon></template>
                    </n-button>
                  </n-dropdown>
                </div>
              </div>
              <pre class="turn-content" :class="{ refusal: turn.has_refusal }">{{ turn.content }}</pre>
            </div>
          </div>
        </div>
        <div v-else class="empty-content">
          <n-empty :description="$t('preview.noConversation') || '暂无对话'" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { CheckmarkCircleOutline, ArrowDownOutline, SwapHorizontalOutline, CodeOutline, InformationCircleOutline, EllipsisHorizontalOutline, ChatbubbleEllipsesOutline, ArrowUndoOutline } from '@vicons/ionicons5'
import { useSessionStore } from '../stores/sessionStore'

const { t } = useI18n()
const sessionStore = useSessionStore()
const activeTab = ref('changes')

// 接收 cleanReasoning prop
const props = defineProps({
  cleanReasoning: {
    type: Boolean,
    default: true
  }
})

// 定义 emit
const emit = defineEmits(['update:cleanReasoning'])

// 选中的行号集合
const selectedLines = ref(new Set())

const session = computed(() => sessionStore.getSelectedSession())
const preview = computed(() => sessionStore.preview)
const conversationView = ref('refusal') // 'refusal' | 'all' | 'incremental'
const conversationSearch = ref('')
const debouncedSearch = ref('')
let _searchTimer = null
watch(conversationSearch, (val) => {
  clearTimeout(_searchTimer)
  _searchTimer = setTimeout(() => { debouncedSearch.value = val }, 300)
})

// 按组过滤：user + 后续所有 assistant 为一组，组内任一匹配则整组保留
function filterByGroup(list, predicate) {
  const groups = []
  let current = null
  list.forEach((t, i) => {
    if (t.role === 'user') {
      current = { indices: [i] }
      groups.push(current)
    } else if (current) {
      current.indices.push(i)
    } else {
      current = { indices: [i] }
      groups.push(current)
    }
  })
  const matched = new Set()
  for (const group of groups) {
    if (group.indices.some(i => predicate(list[i]))) {
      group.indices.forEach(i => matched.add(i))
    }
  }
  return list.filter((_, i) => matched.has(i))
}

const filteredConversation = computed(() => {
  let list = preview.value?.conversation_summary || []
  if (conversationView.value === 'incremental' && sessionStore.incrementalFromLine > 0) {
    list = list.filter(t => t.line_num > sessionStore.incrementalFromLine)
  } else if (conversationView.value === 'refusal') {
    list = filterByGroup(list, t => t.has_refusal)
  }
  const q = debouncedSearch.value.trim().toLowerCase()
  if (q) {
    list = filterByGroup(list, t => {
      const text = (t.search_text || t.content || '').toLowerCase()
      return text.includes(q)
    })
  }
  // Reverse group order (newest first), but keep messages within each group in original order
  const groups = []
  let current = null
  list.forEach(t => {
    if (t.role === 'user') {
      current = [t]
      groups.push(current)
    } else if (current) {
      current.push(t)
    } else {
      current = [t]
      groups.push(current)
    }
  })
  groups.reverse()
  return groups.flat()
})

// 监听预览数据变化，初始化选中状态（默认全选）
watch(() => sessionStore.preview, (newPreview) => {
  if (newPreview?.changes?.length) {
    selectedLines.value = new Set(newPreview.changes.map(c => c.line_num))
  } else {
    selectedLines.value = new Set()
  }
}, { immediate: true })

// 全选/取消全选
function toggleSelectAll() {
  if (!preview.value?.changes?.length) return
  if (selectedLines.value.size === preview.value.changes.length) {
    selectedLines.value = new Set()
  } else {
    selectedLines.value = new Set(preview.value.changes.map(c => c.line_num))
  }
}

// 切换单个选择
function toggleLine(lineNum) {
  const newSet = new Set(selectedLines.value)
  if (newSet.has(lineNum)) {
    newSet.delete(lineNum)
  } else {
    newSet.add(lineNum)
  }
  selectedLines.value = newSet
}

// 是否全选
const isAllSelected = computed(() => {
  if (!preview.value?.changes?.length) return false
  return selectedLines.value.size === preview.value.changes.length
})

// 获取选中的行号列表
function getSelectedLines() {
  return Array.from(selectedLines.value)
}

// 根据行号找到前一个 user 提问
function findPrecedingUserQuestion(lineNum) {
  const summary = preview.value?.conversation_summary || []
  const idx = summary.findIndex(t => t.line_num === lineNum)
  if (idx < 0) return null
  for (let i = idx - 1; i >= 0; i--) {
    if (summary[i].role === 'user') return summary[i]
  }
  return null
}

// 单条消息操作
const messageActions = [
  { label: '撤回 (Revoke)', key: 'revoke' },
  { label: '删除回复 (Delete)', key: 'delete' },
  { label: '改写 (Rewrite)', key: 'rewrite' },
  { label: 'AI 改写', key: 'ai-rewrite' },
]

// 找到当前 assistant 所在组的全部信息
function findGroup(turn) {
  const summary = preview.value?.conversation_summary || []
  const idx = summary.findIndex(t => t.line_num === turn.line_num)
  if (idx < 0) return { userTurn: null, assistantTurns: [turn], allLineNums: [turn.line_num] }

  // Scan backward to find group start (user message)
  let groupStart = idx
  for (let i = idx - 1; i >= 0; i--) {
    if (summary[i].role === 'user') { groupStart = i; break }
  }

  // Collect group: user + all assistants until next user
  const userTurn = summary[groupStart].role === 'user' ? summary[groupStart] : null
  const assistantTurns = []
  const allLineNums = []
  for (let i = groupStart; i < summary.length; i++) {
    if (i > groupStart && summary[i].role === 'user') break
    allLineNums.push(summary[i].line_num)
    if (summary[i].role === 'assistant') assistantTurns.push(summary[i])
  }
  return { userTurn, assistantTurns, allLineNums }
}

async function handleMessageAction(action, turn) {
  const sessionId = sessionStore.selectedId
  if (!sessionId) return

  const group = findGroup(turn)
  const assistantLineNums = group.assistantTurns.map(t => t.line_num)
  const lastAssistant = group.assistantTurns[group.assistantTurns.length - 1] || turn

  if (action === 'revoke') {
    const desc = group.allLineNums.map(n => 'L' + n).join(', ')
    if (!confirm(`确定撤回整组对话？将删除 ${group.allLineNums.length} 条消息 (${desc})`)) return
    await sessionStore.deleteMessages(sessionId, group.allLineNums, true)

  } else if (action === 'delete') {
    const desc = assistantLineNums.map(n => 'L' + n).join(', ')
    if (!confirm(`确定删除该组全部 ${assistantLineNums.length} 条 AI 回复？用户问题保留。(${desc})`)) return
    await sessionStore.deleteMessages(sessionId, assistantLineNums, true)

  } else if (action === 'rewrite') {
    const newText = prompt('输入替换内容（将替换该组所有 AI 回复为一条）:', lastAssistant.content)
    if (newText === null || newText === lastAssistant.content) return
    // Step 1: rewrite last assistant FIRST (line numbers unchanged at this point)
    const { patchSession: rawPatch, deleteMessages: rawDelete } = await import('../services/api')
    const replacements = [{ line_num: lastAssistant.line_num, replacement_text: newText }]
    const patchResult = await rawPatch(sessionId, replacements, [lastAssistant.line_num])
    if (patchResult.backup_path) {
      sessionStore.undoStack.push({ sessionId, operation: 'rewrite-group', backupPath: patchResult.backup_path, description: `改写 L${lastAssistant.line_num}` })
    }
    // Step 2: delete other assistants in group (line shift doesn't matter now)
    const toDelete = assistantLineNums.slice(0, -1)
    if (toDelete.length > 0) {
      const delResult = await rawDelete(sessionId, toDelete, true)
      if (delResult.backup_path) {
        sessionStore.undoStack.push({ sessionId, operation: 'rewrite-group-delete', backupPath: delResult.backup_path, description: `删除组内 ${toDelete.length} 条中间回复` })
      }
    }
    // Step 3: reload
    await sessionStore.fetchSessions()
    await sessionStore.previewSession(sessionId)

  } else if (action === 'ai-rewrite') {
    const contextBefore = group.userTurn
      ? (group.userTurn.search_text || group.userTurn.content || '')
      : ''
    const originalContent = lastAssistant.search_text || lastAssistant.content || ''
    try {
      const { aiRewriteSingle, patchSession: rawPatch, deleteMessages: rawDelete } = await import('../services/api')
      const result = await aiRewriteSingle(originalContent, contextBefore)
      if (!result.success) {
        alert('AI 改写失败: ' + (result.error || '未知错误'))
        return
      }
      const confirmed = prompt('AI 改写结果（可编辑后确认，将替换该组所有 AI 回复为一条）:', result.replacement)
      if (confirmed === null) return
      // Step 1: rewrite last assistant FIRST
      const replacements = [{ line_num: lastAssistant.line_num, replacement_text: confirmed }]
      const patchResult = await rawPatch(sessionId, replacements, [lastAssistant.line_num])
      if (patchResult.backup_path) {
        sessionStore.undoStack.push({ sessionId, operation: 'ai-rewrite-group', backupPath: patchResult.backup_path, description: `AI 改写 L${lastAssistant.line_num}` })
      }
      // Step 2: delete other assistants
      const toDelete = assistantLineNums.slice(0, -1)
      if (toDelete.length > 0) {
        const delResult = await rawDelete(sessionId, toDelete, true)
        if (delResult.backup_path) {
          sessionStore.undoStack.push({ sessionId, operation: 'ai-rewrite-group-delete', backupPath: delResult.backup_path, description: `删除组内 ${toDelete.length} 条中间回复` })
        }
      }
      // Step 3: reload
      await sessionStore.fetchSessions()
      await sessionStore.previewSession(sessionId)
    } catch (e) {
      alert('AI 改写失败: ' + e.message)
    }
  }
}

async function handleUndo() {
  const last = sessionStore.undoStack[sessionStore.undoStack.length - 1]
  if (!last) return
  if (!confirm(`确定撤销上一步操作？\n${last.description}`)) return
  await sessionStore.undoLast()
}

// 暴露方法给父组件
defineExpose({
  getSelectedLines,
  hasChanges: () => preview.value?.has_changes,
  changesCount: () => preview.value?.changes?.length || 0,
  selectedCount: () => selectedLines.value.size
})

function changeTagType(type) {
  if (type === 'replace') return 'warning'
  if (type === 'remove_thinking') return 'info'
  return 'error'
}

function changeTagLabel(type) {
  if (type === 'replace') return t('preview.replace')
  if (type === 'remove_thinking') return t('preview.removeThinking')
  return t('preview.delete')
}

// 已清理会话（有备份）默认显示 Diff 视图
watch(() => sessionStore.selectedId, () => {
  const s = sessionStore.getSelectedSession()
  // 有新拒绝内容时优先显示修改预览；只有备份且无新拒绝才显示 Diff
  if (s?.has_backup && !s?.has_refusal) {
    activeTab.value = 'diff'
  } else {
    activeTab.value = 'changes'
  }
  // 重置对话视图状态
  conversationView.value = 'refusal'
  conversationSearch.value = ''
})
</script>

<style scoped>
.content-block.user-context {
  opacity: 0.7;
  border-left: 2px solid var(--info-color, #2080f0);
  padding-left: 8px;
  margin-bottom: 4px;
}
.content-block.user-context pre {
  font-size: 12px;
  max-height: 60px;
  overflow: hidden;
}
.undo-btn {
  margin-left: auto !important;
  color: var(--warning-color, #f0a020) !important;
}
.conversation-search {
  padding: 0 0 8px 0;
}
.conversation-filter {
  padding: 0 0 8px 0;
}
.turn-actions {
  margin-left: auto;
  opacity: 0;
  transition: opacity 0.15s;
}
.summary-turn:hover .turn-actions {
  opacity: 1;
}
.turn-header {
  display: flex;
  align-items: center;
  gap: 6px;
}
.turn-content.refusal {
  border-left: 2px solid var(--error-color, #e88080);
  padding-left: 8px;
}
.preview-panel {
  flex: 1;
  overflow: hidden;
  background: var(--color-bg-1, #1a1a1a);
  border-radius: 8px;
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.empty-state {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.preview-tabs {
  display: flex;
  border-bottom: 1px solid var(--color-border, #3a3a3a);
  padding: 0 16px;
  flex-shrink: 0;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  font-size: 13px;
  color: var(--color-text-3, #888);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: all 0.2s;
}

.tab-item:hover {
  color: var(--color-text-2, #ccc);
}

.tab-item.active {
  color: var(--color-primary, #18a058);
  border-bottom-color: var(--color-primary, #18a058);
}

.preview-scrollbar {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.empty-content {
  padding: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-content {
  padding: 16px;
}

.changes-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.change-item {
  background: var(--color-bg-2, #2d2d2d);
  border-radius: 8px;
  padding: 12px;
}

.change-item.unselected {
  opacity: 0.5;
}

.change-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.select-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--color-bg-2, #2d2d2d);
  border-radius: 6px;
  margin-bottom: 12px;
}

.select-label {
  font-size: 13px;
  color: var(--color-text-2, #ccc);
}

.line-num {
  font-size: 12px;
  color: var(--color-text-3, #888);
  font-family: monospace;
}

.change-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.content-block {
  padding: 12px;
  border-radius: 6px;
}

.content-block.original {
  background: #3d2d2d;
  border-left: 3px solid #d03050;
}

.content-block.replacement {
  background: #2d3d2d;
  border-left: 3px solid #18a058;
}

.content-block.deleted {
  background: #3d2d2d;
  border-left: 3px solid #909090;
}

.content-label {
  font-size: 11px;
  color: var(--color-text-3, #888);
  margin-bottom: 8px;
  text-transform: uppercase;
}

.content-block pre {
  font-size: 13px;
  color: var(--color-text-2, #ccc);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  line-height: 1.5;
}

.content-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px 0;
}

/* Diff 视图样式 */
.diff-content {
  padding: 16px;
  font-family: 'Fira Code', 'SF Mono', Monaco, monospace;
}

.diff-block {
  margin-bottom: 8px;
}

.diff-line {
  display: flex;
  align-items: flex-start;
  padding: 4px 0;
  font-size: 13px;
  line-height: 1.5;
}

.diff-line.deleted {
  background: rgba(208, 48, 80, 0.15);
}

.diff-line.added {
  background: rgba(24, 160, 88, 0.15);
}

.line-number {
  min-width: 40px;
  padding: 0 8px;
  color: var(--color-text-4, #666);
  text-align: right;
  user-select: none;
}

.diff-marker {
  min-width: 20px;
  text-align: center;
  font-weight: bold;
}

.diff-line.deleted .diff-marker {
  color: #d03050;
}

.diff-line.added .diff-marker {
  color: #18a058;
}

.diff-text {
  flex: 1;
  margin: 0;
  padding: 0 8px;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--color-text-2, #ccc);
}

/* Diff 头部横幅 */
.diff-header-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(32, 128, 240, 0.15);
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--color-text-2, #ccc);
}

/* Thinking Block 内容块 */
.content-block.thinking {
  background: #2d2d3d;
  border-left: 3px solid #7b68ee;
}

/* Thinking Block 提示 */
.thinking-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(123, 104, 238, 0.15);
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--color-text-2, #ccc);
}

.thinking-banner .n-checkbox {
  flex-shrink: 0;
}

/* Diff 视图 Thinking Block 移除 */
.diff-line.thinking-removed {
  background: rgba(123, 104, 238, 0.15);
}

.diff-line.thinking-removed .diff-marker {
  color: #7b68ee;
}

/* 推理内容提示 */
.reasoning-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(32, 128, 240, 0.15);
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--color-text-2, #ccc);
}

.reasoning-banner .n-checkbox {
  flex-shrink: 0;
}

.reasoning-info {
  text-align: center;
  line-height: 1.6;
}

.reasoning-info strong {
  color: #2080f0;
  font-weight: 600;
}

/* 无拒绝内容区域 */
.no-refusal-content {
  padding: 16px;
}

.status-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 6px;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--color-text-2, #ccc);
}

.status-banner .n-checkbox {
  flex-shrink: 0;
}

.status-banner.success-banner {
  background: rgba(24, 160, 88, 0.12);
}

.status-banner.info-banner {
  background: rgba(32, 128, 240, 0.12);
}

/* 对话摘要 */
.conversation-summary {
  margin-top: 8px;
}

.summary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-2, #ccc);
  border-bottom: 1px solid var(--color-border, #3a3a3a);
  margin-bottom: 8px;
}

.summary-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.summary-turn {
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--color-bg-2, #2d2d2d);
}

.summary-turn.user {
  border-left: 3px solid #2080f0;
}

.summary-turn.assistant {
  border-left: 3px solid #18a058;
}

.turn-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.turn-line {
  font-size: 11px;
  color: var(--color-text-4, #666);
  font-family: monospace;
}

.turn-content {
  font-size: 12px;
  color: var(--color-text-2, #ccc);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  line-height: 1.5;
}
</style>
