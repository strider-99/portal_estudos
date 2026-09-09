document.addEventListener('DOMContentLoaded', function() {
    // ---------- Navegação por páginas ----------
    const pagesData = document.getElementById('pages-data');
    if (pagesData) {
        try {
            const pages = JSON.parse(pagesData.textContent);
            let current = 0;
            const totalPages = pages.length;
            const questionsSection = document.getElementById('questions-section');
            const slugEl = document.getElementById('materia-slug');
            const slug = slugEl ? slugEl.textContent.trim() : null;

            function showPage(index) {
                const pc = document.getElementById('page-content');
                if (pc) pc.innerHTML = pages[index];
                const ind = document.getElementById('pageIndicator');
                if (ind) ind.textContent = `Página ${index+1} de ${totalPages}`;
                const prev = document.getElementById('prevBtn');
                const next = document.getElementById('nextBtn');
                if (prev) prev.disabled = (index === 0);
                if (next) next.disabled = (index === totalPages - 1);
                // Mostra questões apenas na última página
                if (questionsSection) {
                    if (index === totalPages - 1) {
                        questionsSection.style.display = 'block';
                    } else {
                        questionsSection.style.display = 'none';
                    }
                }
            }

            const prevBtn = document.getElementById('prevBtn');
            const nextBtn = document.getElementById('nextBtn');
            if (prevBtn) prevBtn.addEventListener('click', function() {
                if (current > 0) { current--; showPage(current); }
            });
            if (nextBtn) nextBtn.addEventListener('click', function() {
                if (current < totalPages - 1) { current++; showPage(current); }
            });
            showPage(0);
        } catch (e) {
            console.error('Erro ao carregar páginas:', e);
        }
    }

    // ---------- Quiz corrigir + salvar histórico ----------
    const corrigirBtn = document.getElementById('corrigir-btn');
    if (corrigirBtn) {
        corrigirBtn.addEventListener('click', async function() {
            const questoes = document.querySelectorAll('.questao-item');
            let acertos = 0;
            let total = questoes.length;
            let detalhes = [];

            questoes.forEach((q, idx) => {
                const gabarito = (q.dataset.gabarito || '').trim().toUpperCase();
                const selected = q.querySelector('input[type="radio"]:checked');
                const userAnswer = selected ? selected.value.trim().toUpperCase() : '';
                const isCorrect = userAnswer === gabarito && userAnswer !== '';
                if (isCorrect) acertos++;

                detalhes.push({ index: idx+1, gabarito, resposta: userAnswer, correto: isCorrect });

                const labels = q.querySelectorAll('.alternativas label');
                labels.forEach(label => {
                    const input = label.querySelector('input');
                    if (input) {
                        const value = input.value.trim().toUpperCase();
                        // reset
                        label.style.color = '';
                        label.style.fontWeight = '';
                        if (value === gabarito) {
                            label.style.color = 'green';
                            label.style.fontWeight = 'bold';
                        } else if (value === userAnswer && userAnswer !== gabarito) {
                            label.style.color = 'red';
                        }
                    }
                });
            });

            const nota = total ? (acertos / total * 10).toFixed(1) : 0;
            let resultadoHTML = `<h3>📊 Resultado: ${acertos} de ${total} (Nota: ${nota})</h3>`;
            if (acertos === total) {
                resultadoHTML += '<p style="color:green;">🎉 Parabéns! Você acertou todas!</p>';
            } else {
                resultadoHTML += '<p>💡 Revise as questões que errou e tente novamente.</p>';
            }

            const resultadoDiv = document.getElementById('resultado');
            if (resultadoDiv) {
                resultadoDiv.innerHTML = resultadoHTML;
                resultadoDiv.style.display = 'block';
            }
            corrigirBtn.disabled = true;

            // Salva no servidor se logado
            const slugEl = document.getElementById('materia-slug');
            const slug = slugEl ? slugEl.textContent.trim() : null;
            if (slug) {
                try {
                    const resp = await fetch('/api/questoes/responder', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ slug_materia: slug, acertos, total, nota: parseFloat(nota), detalhes })
                    });
                    if (resp.ok) {
                        console.log('Progresso salvo');
                    } else if (resp.status === 401) {
                        console.log('Faça login para salvar histórico');
                    }
                } catch (e) {
                    console.error('Erro ao salvar histórico', e);
                }
            }
        });
    }

    // ---------- Botão Concluído ----------
    const btnConcluido = document.getElementById('btn-concluido');
    if (btnConcluido) {
        btnConcluido.addEventListener('click', async function() {
            const slug = btnConcluido.dataset.slug;
            btnConcluido.disabled = true;
            try {
                const resp = await fetch(`/api/progresso/${slug}/toggle`, { method: 'POST' });
                const data = await resp.json();
                if (resp.ok) {
                    const msg = document.getElementById('concluido-msg');
                    if (data.concluida) {
                        btnConcluido.textContent = '✅ Concluída';
                        btnConcluido.classList.add('concluido');
                        if (msg) msg.textContent = 'Matéria marcada como concluída!';
                    } else {
                        btnConcluido.textContent = '☐ Marcar como concluída';
                        btnConcluido.classList.remove('concluido');
                        if (msg) msg.textContent = 'Marcado como não concluída.';
                    }
                } else {
                    alert(data.erro || 'Erro ao salvar progresso');
                }
            } catch (e) {
                alert('Erro de rede ao salvar progresso');
            } finally {
                btnConcluido.disabled = false;
            }
        });
    }

    // ---------- Modal Importar Questões ----------
    const openBtn = document.getElementById('btn-importar-open');
    const modal = document.getElementById('import-modal');
    const closeBtn = document.getElementById('import-modal-close');
    const importForm = document.getElementById('import-form');
    const importResult = document.getElementById('import-result');

    if (openBtn && modal) {
        openBtn.addEventListener('click', () => modal.style.display = 'flex');
    }
    if (closeBtn && modal) {
        closeBtn.addEventListener('click', () => modal.style.display = 'none');
        window.addEventListener('click', (e) => { if (e.target === modal) modal.style.display = 'none'; });
    }
    if (importForm) {
        importForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const fileInput = document.getElementById('import-file');
            if (!fileInput.files.length) { alert('Selecione um arquivo JSON'); return; }
            const formData = new FormData();
            formData.append('arquivo', fileInput.files[0]);
            const btn = importForm.querySelector('button');
            btn.disabled = true; btn.textContent = 'Enviando...';
            try {
                const resp = await fetch('/importar_questoes', { method: 'POST', body: formData });
                const data = await resp.json();
                if (importResult) {
                    importResult.style.display = 'block';
                    if (resp.ok) {
                        let html = `<p style="color:green;">✅ ${data.importadas} questões importadas.</p>`;
                        if (data.slugs_afetados) html += `<p>Matérias: ${data.slugs_afetados.join(', ')}</p>`;
                        if (data.erros && data.erros.length) {
                            html += `<p style="color:red;">⚠️ ${data.erros.length} erro(s):</p><ul>`;
                            data.erros.forEach(err => { html += `<li>idx ${err.index}: ${err.erro} (${err.slug_materia||'-'})</li>`; });
                            html += `</ul>`;
                        }
                        if (data.importadas > 0) html += `<p><small>Recarregue a página para ver as novas questões.</small></p>`;
                        importResult.innerHTML = html;
                    } else {
                        importResult.innerHTML = `<p style="color:red;">Erro: ${data.erro || JSON.stringify(data.erros)}</p>`;
                    }
                }
            } catch (err) {
                alert('Erro ao enviar: ' + err);
            } finally {
                btn.disabled = false; btn.textContent = 'Enviar';
            }
        });
    }

    // ---------- Filtros e busca (home) ----------
    const searchInput = document.getElementById('search-input');
    const filtroBtns = document.querySelectorAll('.filtro-btn');
    function filtrar() {
        const termo = searchInput ? searchInput.value.toLowerCase() : '';
        const filtroAtivo = document.querySelector('.filtro-btn.active');
        const areaFiltro = filtroAtivo ? filtroAtivo.dataset.area : 'all';
        document.querySelectorAll('.area-section').forEach(sec => {
            const area = sec.dataset.area;
            const mostraArea = (areaFiltro === 'all' || area === areaFiltro);
            let temVisivel = false;
            sec.querySelectorAll('.card').forEach(card => {
                const titulo = card.querySelector('h4').textContent.toLowerCase();
                const cardArea = card.dataset.area;
                const matchBusca = titulo.includes(termo);
                const matchArea = (areaFiltro === 'all' || cardArea === areaFiltro);
                const visivel = matchBusca && matchArea;
                card.style.display = visivel ? 'flex' : 'none';
                if (visivel) temVisivel = true;
            });
            sec.style.display = (mostraArea && temVisivel) ? 'block' : 'none';
        });
    }
    if (searchInput) searchInput.addEventListener('input', filtrar);
    filtroBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filtroBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filtrar();
        });
    });
});
