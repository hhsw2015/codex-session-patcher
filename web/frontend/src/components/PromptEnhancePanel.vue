<template>
  <div class="prompt-enhance-panel">
    <n-space vertical size="large">
      <!-- CTF/渗透模式 -->
      <n-card :title="$t('enhance.ctfMode')" size="small">
        <template #header-extra>
          <n-space :size="4">
            <n-tag v-if="ctfStore.status?.installed" type="success" size="small">Profile</n-tag>
            <n-tag v-if="ctfStore.status?.global_installed" type="warning" size="small">{{ $t('enhance.ctfGlobalMode') }}</n-tag>
            <n-tag v-if="!ctfStore.status?.installed && !ctfStore.status?.global_installed" type="default" size="small">{{ $t('common.disabled') }}</n-tag>
          </n-space>
        </template>

        <n-space vertical size="large">
          <!-- Profile 模式 -->
          <div class="mode-section">
            <div class="mode-header">
              <n-text strong>Profile {{ $t('enhance.ctfMode') }}</n-text>
              <n-tag :type="ctfStore.status?.installed ? 'success' : 'default'" size="small" :bordered="false">
                {{ ctfStore.status?.installed ? $t('common.enabled') : $t('common.disabled') }}
              </n-tag>
            </div>
            <n-text depth="3" style="font-size: 13px; line-height: 1.6">
              {{ $t('enhance.ctfProfileDesc') }}
            </n-text>
            <div style="margin-top: 8px">
              <n-button
                v-if="!ctfStore.status?.installed"
                type="primary"
                size="small"
                :loading="ctfStore.installLoading"
                @click="handleInstall"
              >
                {{ $t('enhance.enable') }}
              </n-button>
              <n-button
                v-else
                type="warning"
                size="small"
                :loading="ctfStore.installLoading"
                @click="handleUninstall"
              >
                {{ $t('enhance.disable') }}
              </n-button>
            </div>
            <n-alert v-if="ctfStore.status?.installed" type="info" :bordered="false" style="margin-top: 8px">
              <code>codex -p ctf</code>
            </n-alert>
          </div>

          <n-divider style="margin: 4px 0" />

          <!-- 全局模式 -->
          <div class="mode-section">
            <div class="mode-header">
              <n-text strong>{{ $t('enhance.ctfGlobalMode') }}</n-text>
              <n-tag :type="ctfStore.status?.global_installed ? 'warning' : 'default'" size="small" :bordered="false">
                {{ ctfStore.status?.global_installed ? $t('common.enabled') : $t('common.disabled') }}
              </n-tag>
            </div>
            <n-text depth="3" style="font-size: 13px; line-height: 1.6">
              {{ $t('enhance.ctfGlobalDesc') }}
            </n-text>
            <div style="margin-top: 8px">
              <n-button
                v-if="!ctfStore.status?.global_installed"
                type="primary"
                size="small"
                :loading="ctfStore.globalInstallLoading"
                @click="handleInstallGlobal"
              >
                {{ $t('enhance.enableGlobal') }}
              </n-button>
              <n-button
                v-else
                type="warning"
                size="small"
                :loading="ctfStore.globalInstallLoading"
                @click="handleUninstallGlobal"
              >
                {{ $t('enhance.disableGlobal') }}
              </n-button>
            </div>
            <n-alert v-if="ctfStore.status?.global_installed" type="warning" :bordered="false" style="margin-top: 8px">
              {{ $t('enhance.ctfGlobalWarning') }}
            </n-alert>
          </div>
        </n-space>
      </n-card>

      <!-- 提示词改写器 -->
      <n-card :title="$t('enhance.promptRewrite')" size="small">
        <n-space vertical>
          <n-alert type="info" :bordered="false">
            {{ $t('enhance.promptRewriteDesc') }}
          </n-alert>

          <n-form-item :label="$t('enhance.originalPrompt')">
            <n-input
              v-model:value="rewriteInput"
              type="textarea"
              :rows="3"
              :placeholder="$t('enhance.originalPromptPlaceholder')"
            />
          </n-form-item>

          <n-button
            :disabled="!rewriteInput.trim() || !settingsStore.aiEnabled || !settingsStore.aiEndpoint || !settingsStore.aiModel"
            :loading="ctfStore.rewriteLoading"
            @click="handleRewrite"
          >
            {{ $t('enhance.rewriteBtn') }}
          </n-button>

          <n-alert
            v-if="!settingsStore.aiEnabled || !settingsStore.aiEndpoint || !settingsStore.aiModel"
            type="warning"
            :bordered="false"
          >
            {{ $t('enhance.noAiConfig') }}
          </n-alert>

          <n-collapse-transition :show="ctfStore.rewrittenRequest">
            <n-card size="small" style="margin-top: 12px">
              <template #header>
                <n-space align="center">
                  <span>{{ $t('enhance.rewrittenPrompt') }}</span>
                  <n-tag size="small" type="info">{{ ctfStore.rewriteStrategy }}</n-tag>
                </n-space>
              </template>
              <n-input
                :value="ctfStore.rewrittenRequest"
                type="textarea"
                :rows="4"
                readonly
              />
              <template #action>
                <n-space>
                  <n-button size="small" @click="copyRewritten">{{ $t('enhance.copyResult') }}</n-button>
                  <n-button size="small" @click="clearRewrite">{{ $t('common.clear') }}</n-button>
                </n-space>
              </template>
            </n-card>
          </n-collapse-transition>

          <n-alert v-if="ctfStore.rewriteError" type="error" :bordered="false">
            {{ ctfStore.rewriteError }}
          </n-alert>
        </n-space>
      </n-card>

      <!-- 推荐工作流 -->
      <n-card :title="$t('help.workflow')" size="small">
        <n-steps vertical :current="0">
          <n-step :title="$t('help.workflowCtfSteps[0]')" :description="$t('enhance.ctfModeDesc')" />
          <n-step :title="$t('help.workflowCtfSteps[1]')" description="Profile: codex -p ctf; Global: codex" />
          <n-step :title="$t('help.workflowCtfSteps[2]')" :description="$t('enhance.promptRewriteDesc')" />
          <n-step :title="$t('help.workflowCtfSteps[3]')" :description="$t('help.workflowCtfSteps[4]')" />
        </n-steps>
      </n-card>
    </n-space>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMessage, useDialog } from 'naive-ui'
import { useCTFStore } from '../stores/ctfStore'
import { useSettingsStore } from '../stores/settingsStore'

const { t } = useI18n()
const message = useMessage()
const dialog = useDialog()
const ctfStore = useCTFStore()
const settingsStore = useSettingsStore()

const rewriteInput = ref('')

onMounted(() => {
  ctfStore.fetchStatus()
})

async function handleInstall() {
  const result = await ctfStore.install()
  if (result.success) {
    message.success(result.message)
  } else {
    message.error(result.message)
  }
}

async function handleUninstall() {
  dialog.warning({
    title: t('common.confirm'),
    content: t('enhance.confirmDisableCtf'),
    positiveText: t('common.confirm'),
    negativeText: t('common.cancel'),
    onPositiveClick: async () => {
      const result = await ctfStore.uninstall()
      if (result.success) {
        message.success(result.message)
      } else {
        message.error(result.message)
      }
    }
  })
}

async function handleInstallGlobal() {
  const result = await ctfStore.installGlobal()
  if (result.success) {
    message.success(result.message)
  } else {
    message.error(result.message)
  }
}

async function handleUninstallGlobal() {
  dialog.warning({
    title: t('common.confirm'),
    content: t('enhance.confirmDisableGlobal'),
    positiveText: t('common.confirm'),
    negativeText: t('common.cancel'),
    onPositiveClick: async () => {
      const result = await ctfStore.uninstallGlobal()
      if (result.success) {
        message.success(result.message)
      } else {
        message.error(result.message)
      }
    }
  })
}

async function handleRewrite() {
  if (!rewriteInput.value.trim()) return
  const result = await ctfStore.rewritePrompt(rewriteInput.value)
  if (result.success) {
    message.success(t('enhance.rewriteSuccess'))
  }
}

async function copyRewritten() {
  try {
    await navigator.clipboard.writeText(ctfStore.rewrittenRequest)
    message.success(t('common.copied'))
  } catch {
    message.error(t('common.error'))
  }
}

function clearRewrite() {
  rewriteInput.value = ''
  ctfStore.resetRewrite()
}
</script>

<style scoped>
.prompt-enhance-panel {
  max-width: 800px;
  margin: 0 auto;
}

.n-card {
  background: var(--color-bg-1);
}

code {
  background: #333;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.mode-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mode-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
