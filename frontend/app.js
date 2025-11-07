const { createApp } = Vue;

createApp({
  data() {
    return {
      apiBase: window.localStorage.getItem('rag-api-base') || 'http://localhost:8000',
      askForm: {
        question: '',
        k: 5,
      },
      crawlForm: {
        query: '',
        providers: 'arxiv,openalex,semanticscholar',
        maxPerSource: 50,
        yearMin: null,
        yearMax: null,
        runIngest: false,
      },
      askResult: {
        answer: '',
        references: [],
      },
      crawlResult: '',
      loading: {
        ask: false,
        crawl: false,
      },
      errors: {
        ask: '',
        crawl: '',
      },
      showReferences: false,
    };
  },
  computed: {
    formattedReferences() {
      return JSON.stringify(this.askResult.references, null, 2);
    },
  },
  watch: {
    apiBase(newBase) {
      if (newBase) {
        window.localStorage.setItem('rag-api-base', newBase);
      }
    },
  },
  methods: {
    buildUrl(path) {
      const base = this.apiBase.replace(/\/$/, '');
      return `${base}${path}`;
    },
    async ask() {
      if (!this.askForm.question.trim()) {
        this.errors.ask = '请输入问题';
        return;
      }
      this.loading.ask = true;
      this.errors.ask = '';
      this.showReferences = false;
      try {
        const response = await fetch(this.buildUrl('/ask'), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            q: this.askForm.question,
            k: this.askForm.k || undefined,
          }),
        });
        if (!response.ok) {
          const errorPayload = await response.json().catch(() => ({}));
          throw new Error(errorPayload.error || `请求失败：${response.status}`);
        }
        const payload = await response.json();
        this.askResult.answer = payload.answer || '';
        this.askResult.references = payload.references || [];
      } catch (error) {
        console.error(error);
        this.errors.ask = error.message || '请求失败';
      } finally {
        this.loading.ask = false;
      }
    },
    resetAsk() {
      this.askForm.question = '';
      this.askForm.k = 5;
      this.askResult.answer = '';
      this.askResult.references = [];
      this.errors.ask = '';
      this.showReferences = false;
    },
    async runCrawl() {
      if (!this.crawlForm.query.trim()) {
        this.errors.crawl = '请输入关键词';
        return;
      }
      this.loading.crawl = true;
      this.errors.crawl = '';
      this.crawlResult = '';
      try {
        const body = {
          query: this.crawlForm.query,
          providers: this.crawlForm.providers || undefined,
          max_per_source: this.crawlForm.maxPerSource || undefined,
          year_min: this.crawlForm.yearMin || undefined,
          year_max: this.crawlForm.yearMax || undefined,
          run_ingest: this.crawlForm.runIngest,
        };
        const response = await fetch(this.buildUrl('/crawl'), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(payload.message || `请求失败：${response.status}`);
        }
        if (payload.status === 'ok') {
          this.crawlResult = payload.message || '抓取完成';
        } else {
          this.crawlResult = payload.message || '任务完成';
        }
      } catch (error) {
        console.error(error);
        this.errors.crawl = error.message || '请求失败';
      } finally {
        this.loading.crawl = false;
      }
    },
    resetCrawl() {
      this.crawlForm = {
        query: '',
        providers: 'arxiv,openalex,semanticscholar',
        maxPerSource: 50,
        yearMin: null,
        yearMax: null,
        runIngest: false,
      };
      this.errors.crawl = '';
      this.crawlResult = '';
    },
  },
}).mount('#app');
