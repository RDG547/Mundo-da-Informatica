// ==========================================
// LOAD MORE POSTS
// ==========================================

(function () {
    if (window.PostsLoadMore && typeof window.PostsLoadMore.initAll === 'function') {
        window.PostsLoadMore.initAll();
        return;
    }

    function createElement(tagName) {
        return document.createElement(tagName);
    }

    function stripHtml(html) {
        const temp = createElement('div');
        temp.innerHTML = html || '';
        return temp.textContent || temp.innerText || '';
    }

    function buildPostCard(post, isAuthenticated) {
        const card = createElement('div');
        card.className = 'post-card';
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';

        const imageWrapper = createElement('div');
        imageWrapper.className = 'post-image';
        const image = createElement('img');
        image.src = post.image_url;
        image.alt = post.title;
        imageWrapper.appendChild(image);
        card.appendChild(imageWrapper);

        const categoryBar = createElement('div');
        categoryBar.className = 'post-category';
        const categoryIcon = createElement('i');
        categoryIcon.className = post.category_icon;
        const categoryLabel = createElement('span');
        categoryLabel.textContent = post.category_str;
        categoryBar.appendChild(categoryIcon);
        categoryBar.appendChild(categoryLabel);

        const downloadFiles = post.download_files || [];
        if (downloadFiles.length > 1) {
            const badge = createElement('span');
            badge.className = 'download-types-badge';
            badge.style.cssText = 'margin-left:6px;background:rgba(var(--primary-rgb),0.15);color:var(--primary-color);padding:2px 8px;border-radius:10px;font-size:0.7rem;font-weight:600;';
            badge.textContent = downloadFiles.map(function (file) {
                return file.type;
            }).join('/');
            categoryBar.appendChild(badge);
        }
        card.appendChild(categoryBar);

        const content = createElement('div');
        content.className = 'post-content';

        const title = createElement('h3');
        const titleLink = createElement('a');
        titleLink.href = post.post_url;
        titleLink.style.cssText = 'text-decoration:none;color:inherit;';
        titleLink.textContent = post.title;
        title.appendChild(titleLink);
        content.appendChild(title);

        const meta = createElement('div');
        meta.className = 'post-meta';
        const date = createElement('span');
        date.innerHTML = '<i class="far fa-calendar-alt"></i> ' + post.date_posted;
        const views = createElement('span');
        views.innerHTML = '<i class="far fa-eye"></i> ' + post.views;
        meta.appendChild(date);
        meta.appendChild(views);
        content.appendChild(meta);

        const descriptionSection = createElement('div');
        descriptionSection.className = 'post-description-section';
        const descriptionTitle = createElement('div');
        descriptionTitle.className = 'post-description-title';
        descriptionTitle.textContent = 'Descrição';
        const descriptionText = createElement('div');
        descriptionText.className = 'post-description-text';
        descriptionText.textContent = stripHtml(post.content);
        descriptionSection.appendChild(descriptionTitle);
        descriptionSection.appendChild(descriptionText);
        content.appendChild(descriptionSection);

        const buttons = createElement('div');
        buttons.style.cssText = 'display:flex;gap:10px;align-items:stretch;flex-wrap:wrap;';

        if (post.download_link) {
            if (downloadFiles.length > 1) {
                const downloadButton = createElement('button');
                downloadButton.type = 'button';
                downloadButton.className = 'btn btn-download download-btn multi-download-trigger';
                downloadButton.dataset.postId = post.id;
                downloadButton.dataset.postTitle = post.title;
                downloadButton.dataset.downloadFiles = JSON.stringify(downloadFiles);
                downloadButton.style.cssText = 'flex:1;min-width:120px;';
                downloadButton.innerHTML = '<i class="fas fa-download"></i> Download';
                buttons.appendChild(downloadButton);
            } else {
                const downloadLink = createElement('a');
                downloadLink.href = '/download/' + post.id;
                downloadLink.className = 'btn btn-download download-btn';
                downloadLink.dataset.action = 'download';
                downloadLink.style.cssText = 'flex:1;min-width:120px;';
                downloadLink.innerHTML = '<i class="fas fa-download"></i> Download';
                buttons.appendChild(downloadLink);
            }
        }

        const detailLink = createElement('a');
        detailLink.href = post.post_url;
        detailLink.className = 'btn';
        detailLink.style.cssText = 'flex:1;min-width:120px;display:flex;align-items:center;justify-content:center;white-space:nowrap;gap:6px;';
        detailLink.innerHTML = '<i class="fas fa-eye"></i> Ver Detalhes';
        buttons.appendChild(detailLink);

        if (isAuthenticated) {
            const favoriteButton = createElement('button');
            favoriteButton.dataset.postId = post.id;
            favoriteButton.setAttribute('onclick', 'toggleFavorite(' + post.id + ')');
            favoriteButton.className = 'favorite-btn-card' + (post.is_favorited ? ' favorited' : '');
            favoriteButton.title = post.is_favorited ? 'Remover dos favoritos' : 'Adicionar aos favoritos';
            favoriteButton.innerHTML = '<i class="' + (post.is_favorited ? 'fas' : 'far') + ' fa-star"></i>';
            buttons.appendChild(favoriteButton);
        }

        content.appendChild(buttons);
        card.appendChild(content);

        return card;
    }

    function buildEndpoint(baseEndpoint, page) {
        const url = new URL(baseEndpoint, window.location.origin);
        url.searchParams.set('page', String(page));
        return url.toString();
    }

    function initGrid(grid) {
        if (!grid || grid.dataset.loadMoreInitialized === 'true') {
            return;
        }

        const button = document.getElementById('load-more-btn');
        const wrapper = document.getElementById('load-more-wrapper');
        const endpoint = grid.dataset.loadMoreEndpoint;

        if (!button || !wrapper || !endpoint) {
            return;
        }

        grid.dataset.loadMoreInitialized = 'true';

        let nextPage = Number.parseInt(grid.dataset.nextPage, 10) || 2;
        let hasNext = grid.dataset.hasNext === 'true';
        let isLoading = false;

        button.addEventListener('click', function () {
            if (isLoading || !hasNext) {
                return;
            }

            isLoading = true;
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Carregando...';

            fetch(buildEndpoint(endpoint, nextPage))
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error('HTTP ' + response.status);
                    }
                    return response.json();
                })
                .then(function (data) {
                    if (!data.success) {
                        throw new Error('API error');
                    }

                    const appendedCards = [];
                    data.posts.forEach(function (post) {
                        const card = buildPostCard(post, data.is_authenticated);
                        grid.appendChild(card);
                        appendedCards.push(card);
                    });

                    appendedCards.forEach(function (card, index) {
                        setTimeout(function () {
                            card.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
                            card.style.opacity = '1';
                            card.style.transform = 'translateY(0)';
                        }, index * 60);
                    });

                    hasNext = Boolean(data.has_next);
                    nextPage = data.next_page || (nextPage + 1);
                    grid.dataset.nextPage = String(nextPage);
                    grid.dataset.hasNext = hasNext ? 'true' : 'false';

                    if (hasNext) {
                        button.disabled = false;
                        button.innerHTML = '<i class="fas fa-plus-circle"></i> Carregar Mais';
                    } else {
                        wrapper.style.display = 'none';
                    }

                    if (typeof window.setupDownloadButtons === 'function') {
                        window.setupDownloadButtons();
                    }

                    isLoading = false;
                })
                .catch(function (error) {
                    console.error('Erro ao carregar mais posts:', error);
                    button.disabled = false;
                    button.innerHTML = '<i class="fas fa-plus-circle"></i> Carregar Mais';
                    isLoading = false;
                });
        });
    }

    function initAll() {
        document.querySelectorAll('[data-load-more-endpoint]').forEach(initGrid);
    }

    window.PostsLoadMore = {
        buildPostCard: buildPostCard,
        initAll: initAll
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }

    document.addEventListener('contentLoaded', initAll);
    document.addEventListener('pageLoaded', initAll);
})();
