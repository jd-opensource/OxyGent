/**
 * config.js — System settings page logic
 */
$(function () {
    loadConfig();
});

async function loadConfig() {
    try {
        const cfg = await api.get('/config');

        // Editable: Annotation
        $('#maxConcurrency').val(cfg.annotation?.max_concurrency || 5);
        $('#agentTimeout').val(cfg.annotation?.agent_timeout || 120);

        // Editable: Embedding
        $('#tritonUrl').val(cfg.triton?.url || '');
        $('#openaiBaseUrl').val(cfg.openai_embedding?.base_url || '');
        $('#openaiModel').val(cfg.openai_embedding?.model || '');

        // Editable: Chunking
        $('#chunkSize').val(cfg.chunking?.chunk_size || 512);
        $('#chunkOverlap').val(cfg.chunking?.chunk_overlap || 50);
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

async function saveAnnotationConfig() {
    try {
        await api.put('/config/annotation', {
            max_concurrency: parseInt($('#maxConcurrency').val()) || 5,
        });
        OxyBank.showToast('Saved', 'success');
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

async function saveEmbeddingConfig() {
    try {
        await api.put('/config/embedding', {
            triton_url: $('#tritonUrl').val().trim() || null,
        });
        OxyBank.showToast('Saved', 'success');
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

async function saveOpenaiEmbeddingConfig() {
    try {
        await api.put('/config/embedding', {
            openai_base_url: $('#openaiBaseUrl').val().trim() || null,
            openai_model: $('#openaiModel').val().trim() || null,
        });
        OxyBank.showToast('Saved', 'success');
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

async function saveChunkingConfig() {
    try {
        await api.put('/config/chunking', {
            chunk_size: parseInt($('#chunkSize').val()) || 512,
            chunk_overlap: parseInt($('#chunkOverlap').val()) || 50,
        });
        OxyBank.showToast('Saved', 'success');
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}
