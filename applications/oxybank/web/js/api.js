/**
 * api.js — Centralized API client for OxyBank
 */
(function (global) {
    const BASE = '/api';

    function getToken() {
        return localStorage.getItem('oxybank-token');
    }

    function headers(extra) {
        const h = { 'Content-Type': 'application/json', ...extra };
        const token = getToken();
        if (token) h['Authorization'] = 'Bearer ' + token;
        return h;
    }

    async function request(method, path, data, options = {}) {
        const opts = {
            method,
            headers: headers(options.headers),
        };
        if (data && method !== 'GET') {
            if (data instanceof FormData) {
                delete opts.headers['Content-Type'];
                opts.body = data;
            } else {
                opts.body = JSON.stringify(data);
            }
        }
        const resp = await fetch(BASE + path, opts);
        if (resp.status === 401) {
            localStorage.removeItem('oxybank-token');
            window.location.href = '/login.html';
            return;
        }
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || err.message || 'Request failed');
        }
        if (resp.status === 204) return null;
        return resp.json();
    }

    const api = {
        get: (path) => request('GET', path),
        post: (path, data) => request('POST', path, data),
        put: (path, data) => request('PUT', path, data),
        del: (path) => request('DELETE', path),
        upload: (path, formData) => request('POST', path, formData),

        // SSE streaming for LLM chat
        stream: function (path, data, onChunk, onDone) {
            const token = getToken();
            fetch(BASE + path, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token,
                },
                body: JSON.stringify(data),
            }).then(resp => {
                const reader = resp.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                function read() {
                    reader.read().then(({ done, value }) => {
                        if (done) { onDone && onDone(buffer); return; }
                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split('\n');
                        buffer = lines.pop();
                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                const payload = line.slice(6);
                                if (payload === '[DONE]') { onDone && onDone(); return; }
                                try {
                                    const json = JSON.parse(payload);
                                    const content = json.choices?.[0]?.delta?.content;
                                    if (content) onChunk(content);
                                } catch (e) {}
                            }
                        }
                        read();
                    });
                }
                read();
            });
        },
    };

    global.api = api;
})(window);
