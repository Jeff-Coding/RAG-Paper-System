<template>
  <div class="chat-page chat-page--simple">
    <header class="page-header">
      <div>
        <p class="card__eyebrow">论文助手</p>
        <h2>主页面仅用于提问</h2>
        <p>输入你的问题立即获取回答；若需抓取数据，请前往数据收集页面。</p>
      </div>

      <RouterLink class="btn btn--ghost" to="/collect">前往数据收集</RouterLink>
    </header>

    <section class="chat-panel card">
      <header class="chat-panel__head">
        <div>
          <p class="card__eyebrow">智能对话</p>
          <h3>与论文助手聊天</h3>
          <p class="chat-panel__hint">消息会以气泡形式呈现，自动拆分摘要、要点、引用等段落。</p>
        </div>
        <div class="chat-panel__status" v-if="askState.isLoading">正在生成回答…</div>
      </header>

      <div ref="historyRef" class="chat-history" aria-live="polite">
        <div v-if="!messages.length" class="chat-placeholder">
          <p>试着提问：<strong>“Swin Transformer 如何实现线性计算复杂度？”</strong></p>
        </div>

        <article v-for="message in messages" :key="message.id" class="chat-message" :class="`chat-message--${message.role}`">
          <div class="chat-avatar" :aria-label="message.role === 'user' ? '提问' : '回答'">
            {{ message.role === 'user' ? '你' : '助' }}
          </div>
          <div class="chat-bubble" :class="`chat-bubble--${message.role}`">
            <header class="chat-bubble__header">
              <span class="chat-bubble__role">{{ message.role === 'user' ? '提问' : '论文助手' }}</span>
              <span class="chat-bubble__time">{{ formatTime(message.createdAt) }}</span>
            </header>

            <div class="chat-bubble__body">
              <template v-if="message.role === 'assistant' && message.answer">
                <div
                  class="chat-markdown"
                  v-if="message.answer.answer"
                  v-html="renderMarkdown(message.answer.answer)"
                />

                <div v-if="message.answer.references?.length" class="chat-meta">
                  <h5>参考链接</h5>
                  <div class="result__reference-tags">
                    <template v-for="(ref, rIdx) in normalizeReferences(message.answer.references)" :key="rIdx">
                      <a
                        v-if="ref.href"
                        :href="ref.href"
                        class="chip chip--link"
                        target="_blank"
                        rel="noopener"
                      >
                        {{ ref.label }}
                      </a>
                      <span v-else class="chip">{{ ref.label }}</span>
                    </template>
                  </div>
                </div>

                <div v-if="message.answer.cues?.length" class="chat-meta chat-meta--inline">
                  <h5>提示</h5>
                  <div class="chat-meta__chips">
                    <span v-for="cue in message.answer.cues" :key="cue" class="chip">{{ cue }}</span>
                  </div>
                </div>

                <p v-if="message.answer.elapsed" class="chat-meta chat-meta__time">响应时间 {{ message.answer.elapsed.toFixed(2) }}s</p>
              </template>

              <template v-else>
                <p class="chat-section__text">{{ message.text }}</p>
              </template>
            </div>
          </div>
        </article>

        <div v-if="askState.isLoading" class="chat-message chat-message--assistant chat-message--pending">
          <div class="chat-avatar">…</div>
          <div class="chat-bubble chat-bubble--assistant">
            <p class="chat-section__text">正在生成回答，请稍候…</p>
          </div>
        </div>
      </div>

      <form class="chat-composer" @submit.prevent="handleAsk">
        <div class="composer__field">
          <textarea
            v-model="query"
            rows="3"
            placeholder="像 ChatGPT 一样提问：例如“Transformer 在长文本建模上的改进有哪些？”"
            required
          />
          <div class="composer__actions">
            <div class="composer__tips">
              <span>快捷提问：</span>
              <button type="button" class="chip" @click="applySuggestion('Swin Transformer 的 Shifted Window 有什么优势？')">
                Swin Transformer
              </button>
              <button type="button" class="chip" @click="applySuggestion('如何快速综述大语言模型的安全评测？')">
                安全评测
              </button>
            </div>
            <button class="btn" type="submit" :disabled="askState.isLoading || !query.trim().length">
              <span v-if="askState.isLoading">发送中…</span>
              <span v-else>发送</span>
            </button>
          </div>
        </div>
      </form>

      <p v-if="askState.error" class="alert alert--error">{{ askState.error }}</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { nextTick, reactive, ref, watch } from 'vue';
import { useApiClient } from '@/composables/useApiClient';
import type { AskResponse } from '@/types/api';

const apiClient = useApiClient();
const ASK_TOP_K = 10;

const askState = reactive({
  isLoading: false,
  error: null as string | null
});

interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  text: string;
  createdAt: number;
  answer?: AskResponse;
}

const messages = reactive<ChatMessage[]>([]);
const query = ref('');
const historyRef = ref<HTMLElement | null>(null);
const currentTime = () => Date.now();

watch(
  () => messages.length,
  () => scrollToBottom()
);

function escapeHtml(text: string) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatInline(text: string) {
  let safe = escapeHtml(text);
  safe = safe.replace(/\[([^\]]+)]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  safe = safe.replace(/`([^`]+)`/g, '<code>$1</code>');
  safe = safe.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  safe = safe.replace(/__([^_]+)__/g, '<strong>$1</strong>');
  safe = safe.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
  safe = safe.replace(/(?<!_)_([^_]+)_(?!_)/g, '<em>$1</em>');
  return safe;
}

function renderMarkdown(content: string) {
  if (!content) return '';

  const lines = content.split(/\r?\n/);
  const htmlParts: string[] = [];
  let listBuffer: string[] = [];

  const flushList = () => {
    if (listBuffer.length) {
      htmlParts.push(`<ul>${listBuffer.join('')}</ul>`);
      listBuffer = [];
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (!line) {
      flushList();
      continue;
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      flushList();
      const level = headingMatch[1].length;
      htmlParts.push(`<h${level}>${formatInline(headingMatch[2])}</h${level}>`);
      continue;
    }

    if (/^[-*•+]\s+/.test(line)) {
      const itemText = line.replace(/^[-*•+]\s+/, '');
      listBuffer.push(`<li>${formatInline(itemText)}</li>`);
      continue;
    }

    flushList();
    htmlParts.push(`<p>${formatInline(line)}</p>`);
  }

  flushList();
  return htmlParts.join('');
}

function normalizeReferences(items: AskResponse['references'] = []) {
  return items.map((entry, index) => {
    if (typeof entry === 'string') {
      const trimmed = entry.trim();
      const href = /^https?:\/\//i.test(trimmed) ? trimmed : undefined;
      return { label: trimmed || `参考 ${index + 1}`, href };
    }

    const label = entry.title || entry.url || entry.source || `参考 ${index + 1}`;
    const href = entry.url && entry.url.trim().length ? entry.url : undefined;
    return { label, href };
  });
}

function formatTime(timestamp: number) {
  const date = new Date(timestamp);
  return `${date.getHours().toString().padStart(2, '0')}:${date
    .getMinutes()
    .toString()
    .padStart(2, '0')}`;
}

function scrollToBottom() {
  nextTick(() => {
    if (historyRef.value) {
      historyRef.value.scrollTop = historyRef.value.scrollHeight;
    }
  });
}

async function handleAsk() {
  const trimmed = query.value.trim();
  if (!trimmed || askState.isLoading) return;

  const userMessage: ChatMessage = {
    id: Date.now(),
    role: 'user',
    text: trimmed,
    createdAt: currentTime()
  };
  messages.push(userMessage);
  query.value = '';
  scrollToBottom();

  askState.isLoading = true;
  askState.error = null;

  const response = await apiClient.ask({ q: trimmed, k: ASK_TOP_K });
  askState.isLoading = false;

  if ('status' in response) {
    askState.error = `请求失败（${response.status || '网络'}）：${response.message}`;
    return;
  }

  const assistantMessage: ChatMessage = {
    id: Date.now() + 1,
    role: 'assistant',
    text: response.data.answer,
    createdAt: currentTime(),
    answer: response.data
  };

  messages.push(assistantMessage);
  scrollToBottom();
}

function applySuggestion(text: string) {
  query.value = text;
}
</script>
