(() => {
    const CHAVE_VISTO = 'megagame-manual-visto';
    const MARGEM = 16;
    const FOLGA = 6;
    const DISTANCIA = 12;

    const ajuda = document.getElementById('manualHelp');
    if (!ajuda) return;

    const botao = ajuda.querySelector('.manual-fab');
    const menu = ajuda.querySelector('.manual-menu');
    const dica = ajuda.querySelector('.manual-hint');

    const lerVisto = () => { try { return localStorage.getItem(CHAVE_VISTO) === '1'; } catch { return true; } };
    const marcarVisto = () => {
        try { localStorage.setItem(CHAVE_VISTO, '1'); } catch { }
        ajuda.classList.remove('is-new');
    };

    const tours = {};
    document.querySelectorAll('template[data-manual]').forEach(modelo => {
        const passos = [...modelo.content.querySelectorAll('[data-passo]')].map(el => ({
            alvo: el.dataset.alvo || null,
            abrir: el.dataset.abrir || null,
            titulo: el.dataset.titulo || '',
            html: el.innerHTML.trim(),
        }));
        if (passos.length) tours[modelo.dataset.manual] = { nome: modelo.dataset.nome, passos };
    });

    menu.querySelectorAll('[data-tour]').forEach(item => {
        if (!tours[item.dataset.tour]) item.remove();
    });

    const visivel = el => {
        if (!el || !el.getClientRects().length) return false;
        const estilo = getComputedStyle(el);
        return estilo.visibility !== 'hidden' && estilo.display !== 'none';
    };

    const abrirContainer = seletor => {
        const el = seletor && document.querySelector(seletor);
        if (el) el.classList.add('open');
        return el;
    };
    const fecharContainer = el => { if (el) el.classList.remove('open'); };

    const passoDisponivel = passo => {
        if (!passo.alvo) return true;
        const container = abrirContainer(passo.abrir);
        const ok = visivel(document.querySelector(passo.alvo));
        fecharContainer(container);
        return ok;
    };

    let estado = null;

    const camada = document.createElement('div');
    camada.className = 'manual-layer';
    camada.hidden = true;
    camada.innerHTML = `
        <div class="manual-backdrop"></div>
        <div class="manual-spot"></div>
        <div class="manual-pop" role="dialog" aria-modal="true" aria-labelledby="manualPopTitle" tabindex="-1">
            <div class="manual-pop-head">
                <span class="manual-pop-tour"></span>
                <button type="button" class="manual-close" aria-label="Fechar manual">&times;</button>
            </div>
            <h3 class="manual-pop-title" id="manualPopTitle"></h3>
            <div class="manual-pop-body"></div>
            <div class="manual-pop-foot">
                <span class="manual-progress" aria-live="polite"></span>
                <div class="manual-pop-actions">
                    <button type="button" class="btn btn-ghost btn-sm" data-acao="voltar">Anterior</button>
                    <button type="button" class="btn btn-primary btn-sm" data-acao="avancar">Próximo</button>
                </div>
            </div>
            <button type="button" class="manual-next-tour link text-sm" hidden></button>
        </div>`;
    document.body.appendChild(camada);

    const spot = camada.querySelector('.manual-spot');
    const pop = camada.querySelector('.manual-pop');
    const btnVoltar = pop.querySelector('[data-acao="voltar"]');
    const btnAvancar = pop.querySelector('[data-acao="avancar"]');
    const proximoTour = pop.querySelector('.manual-next-tour');

    const estreito = () => window.matchMedia('(max-width: 600px)').matches;

    const rolarAte = el => {
        if (el.closest('.site-header')) return;
        const r = el.getBoundingClientRect();
        const topo = (document.querySelector('.site-header')?.offsetHeight || 0) + MARGEM;
        const reservaBaixo = estreito() ? pop.offsetHeight + MARGEM * 2 : MARGEM;
        const limite = window.innerHeight - reservaBaixo;
        if (r.top >= topo && r.bottom <= limite) return;
        const alturaUtil = limite - topo;
        const deslocamento = r.height < alturaUtil ? r.top - topo - (alturaUtil - r.height) / 2 : r.top - topo;
        const reduzir = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        window.scrollTo({ top: window.scrollY + deslocamento, behavior: reduzir ? 'auto' : 'smooth' });
    };

    const posicionar = () => {
        if (!estado) return;
        const passo = estado.passos[estado.indice];
        const el = passo.alvo && document.querySelector(passo.alvo);
        const larguraPop = pop.offsetWidth;
        const alturaPop = pop.offsetHeight;
        const vw = window.innerWidth;
        const vh = window.innerHeight;

        if (!el || !visivel(el)) {
            camada.classList.add('sem-alvo');
            pop.style.left = `${Math.max(MARGEM, (vw - larguraPop) / 2)}px`;
            pop.style.top = `${Math.max(MARGEM, (vh - alturaPop) / 2)}px`;
            return;
        }

        camada.classList.remove('sem-alvo');
        const r = el.getBoundingClientRect();
        const alvo = {
            top: Math.max(r.top - FOLGA, 0),
            left: Math.max(r.left - FOLGA, 0),
            bottom: Math.min(r.bottom + FOLGA, vh),
            right: Math.min(r.right + FOLGA, vw),
        };
        spot.style.top = `${alvo.top}px`;
        spot.style.left = `${alvo.left}px`;
        spot.style.width = `${Math.max(alvo.right - alvo.left, 0)}px`;
        spot.style.height = `${Math.max(alvo.bottom - alvo.top, 0)}px`;

        if (estreito()) {
            pop.style.left = `${MARGEM}px`;
            pop.style.top = `${vh - alturaPop - MARGEM}px`;
            return;
        }

        const limitarX = x => Math.min(Math.max(x, MARGEM), vw - larguraPop - MARGEM);
        const limitarY = y => Math.min(Math.max(y, MARGEM), vh - alturaPop - MARGEM);
        const centroX = (alvo.left + alvo.right) / 2 - larguraPop / 2;
        const centroY = (alvo.top + alvo.bottom) / 2 - alturaPop / 2;

        let top, left;
        if (vh - alvo.bottom >= alturaPop + DISTANCIA + MARGEM) {
            top = alvo.bottom + DISTANCIA; left = limitarX(centroX);
        } else if (alvo.top >= alturaPop + DISTANCIA + MARGEM) {
            top = alvo.top - DISTANCIA - alturaPop; left = limitarX(centroX);
        } else if (vw - alvo.right >= larguraPop + DISTANCIA + MARGEM) {
            left = alvo.right + DISTANCIA; top = limitarY(centroY);
        } else if (alvo.left >= larguraPop + DISTANCIA + MARGEM) {
            left = alvo.left - DISTANCIA - larguraPop; top = limitarY(centroY);
        } else {
            left = limitarX(centroX); top = vh - alturaPop - MARGEM;
        }
        pop.style.left = `${left}px`;
        pop.style.top = `${limitarY(top)}px`;
    };

    const loop = () => {
        if (!estado) return;
        posicionar();
        estado.quadro = requestAnimationFrame(loop);
    };

    const mostrar = indice => {
        fecharContainer(estado.container);
        estado.indice = indice;
        const passo = estado.passos[indice];
        const total = estado.passos.length;

        estado.container = abrirContainer(passo.abrir);
        pop.querySelector('.manual-pop-tour').textContent = estado.nome;
        pop.querySelector('.manual-pop-title').textContent = passo.titulo;
        pop.querySelector('.manual-pop-body').innerHTML = passo.html;
        pop.querySelector('.manual-progress').textContent = `${indice + 1} de ${total}`;
        btnVoltar.hidden = indice === 0;
        btnAvancar.textContent = indice === total - 1 ? 'Concluir' : 'Próximo';

        const ultimo = indice === total - 1;
        const outro = estado.chave === 'pagina' ? 'navegacao' : 'pagina';
        proximoTour.hidden = !(ultimo && tours[outro]);
        proximoTour.textContent = outro === 'navegacao' ? 'Ver também: como navegar pelo site →' : 'Ver também: como usar esta página →';
        proximoTour.dataset.tour = outro;

        const el = passo.alvo && document.querySelector(passo.alvo);
        posicionar();
        if (el) rolarAte(el);
        pop.focus({ preventScroll: true });
    };

    const iniciar = chave => {
        const tour = tours[chave];
        if (!tour) return;
        encerrar(false);
        const passos = tour.passos.filter(passoDisponivel);
        if (!passos.length) return;

        marcarVisto();
        fecharMenu();
        estado = { chave, nome: tour.nome, passos, indice: 0, container: null, quadro: null };
        camada.hidden = false;
        document.documentElement.classList.add('manual-ativo');
        mostrar(0);
        estado.quadro = requestAnimationFrame(loop);
    };

    const encerrar = (devolverFoco = true) => {
        if (!estado) return;
        cancelAnimationFrame(estado.quadro);
        fecharContainer(estado.container);
        estado = null;
        camada.hidden = true;
        document.documentElement.classList.remove('manual-ativo');
        if (devolverFoco) botao.focus({ preventScroll: true });
    };

    const avancar = () => {
        if (estado.indice < estado.passos.length - 1) mostrar(estado.indice + 1);
        else encerrar();
    };
    const voltar = () => { if (estado.indice > 0) mostrar(estado.indice - 1); };

    camada.addEventListener('click', e => e.stopPropagation());
    btnAvancar.addEventListener('click', avancar);
    btnVoltar.addEventListener('click', voltar);
    pop.querySelector('.manual-close').addEventListener('click', () => encerrar());
    proximoTour.addEventListener('click', () => iniciar(proximoTour.dataset.tour));

    document.addEventListener('keydown', e => {
        if (estado) {
            if (e.key === 'Escape') { e.preventDefault(); encerrar(); }
            else if (e.key === 'ArrowRight') { e.preventDefault(); avancar(); }
            else if (e.key === 'ArrowLeft') { e.preventDefault(); voltar(); }
        } else if (e.key === 'Escape' && !menu.hidden) {
            fecharMenu();
            botao.focus();
        }
    });

    const fecharMenu = () => {
        menu.hidden = true;
        botao.setAttribute('aria-expanded', 'false');
    };

    botao.addEventListener('click', e => {
        marcarVisto();
        const itens = menu.querySelectorAll('[data-tour]');
        if (itens.length === 1) {
            e.stopPropagation();
            iniciar(itens[0].dataset.tour);
            return;
        }
        menu.hidden = !menu.hidden;
        botao.setAttribute('aria-expanded', String(!menu.hidden));
    });
    menu.addEventListener('click', e => {
        const item = e.target.closest('[data-tour]');
        if (!item) return;
        e.stopPropagation();
        iniciar(item.dataset.tour);
    });
    document.addEventListener('click', e => {
        if (!menu.hidden && !ajuda.contains(e.target)) fecharMenu();
    });
    dica?.querySelector('.manual-hint-close')?.addEventListener('click', marcarVisto);

    if (!lerVisto()) ajuda.classList.add('is-new');
})();