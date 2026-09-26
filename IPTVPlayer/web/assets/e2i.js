/* E2iPlayer web interface - fills the pages through /iptvplayer/api (web/webApi.py) */
(function () {
	'use strict';

	var E = window.E2I || {txt: {}};

	// ------------------------------------------------------------------ helpers

	function t(text) {
		var s = (E.txt && E.txt[text]) || text;
		for (var i = 1; i < arguments.length; i++) {
			s = s.replace(/%[sd]/, String(arguments[i]));
		}
		return s;
	}

	function el(tag, attrs) {
		var node = document.createElement(tag);
		if (attrs) {
			Object.keys(attrs).forEach(function (key) {
				var value = attrs[key];
				if (value === null || value === undefined || value === false) { return; }
				if (key === 'text') { node.textContent = value; }
				else if (key === 'cls') { node.className = value; }
				else if (key.indexOf('on') === 0) { node.addEventListener(key.substring(2), value); }
				else { node.setAttribute(key, value === true ? '' : value); }
			});
		}
		for (var i = 2; i < arguments.length; i++) {
			var child = arguments[i];
			if (child === null || child === undefined || child === false) { continue; }
			if (Array.isArray(child)) {
				child.forEach(function (c) { if (c) { node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); } });
			} else {
				node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
			}
		}
		return node;
	}

	function $(id) { return document.getElementById(id); }

	function clear(node) { while (node.firstChild) { node.removeChild(node.firstChild); } return node; }

	function api(path, body) {
		var opts = {cache: 'no-store'};
		if (body !== undefined) {
			opts.method = 'POST';
			opts.headers = {'Content-Type': 'application/json'};
			opts.body = JSON.stringify(body);
		}
		return fetch('/iptvplayer/api/' + path, opts).then(function (r) {
			return r.json().catch(function () { return {ok: false, error: 'HTTP ' + r.status}; });
		});
	}

	var toastTimer = null;
	function toast(msg, isError) {
		var node = $('toast');
		node.textContent = msg;
		node.className = 'show' + (isError ? ' err' : '');
		clearTimeout(toastTimer);
		toastTimer = setTimeout(function () { node.className = ''; }, isError ? 5000 : 2200);
	}

	function fmtBytes(n) {
		if (!(n > 0)) { return '0 B'; }
		var units = ['B', 'KB', 'MB', 'GB', 'TB'], i = 0;
		while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
		return (i ? n.toFixed(1) : n) + ' ' + units[i];
	}

	function fmtDuration(sec) {
		if (!(sec > 0)) { return '0:00'; }
		var h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = Math.floor(sec % 60);
		return (h ? h + ':' + (m < 10 ? '0' : '') : '') + m + ':' + (s < 10 ? '0' : '') + s;
	}

	function spinnerText(text) { return el('span', null, el('span', {cls: 'spinner'}), ' ' + text); }

	function notice(text, kind, onClose) {
		return el('div', {cls: 'notice' + (kind ? ' ' + kind : '')},
			onClose ? el('span', {cls: 'close', text: '✕', title: t('Close'), onclick: onClose}) : null, text);
	}

	function store(key, value) {
		try {
			if (value === undefined) { return JSON.parse(sessionStorage.getItem('e2i.' + key)); }
			sessionStorage.setItem('e2i.' + key, JSON.stringify(value));
		} catch (e) { /* private mode */ }
		return null;
	}

	function thumb(src, fallback) {
		var img = el('img', {cls: 'thumb', loading: 'lazy', alt: '', src: src || fallback || ''});
		img.addEventListener('error', function () {
			if (fallback && img.getAttribute('src') !== fallback) { img.setAttribute('src', fallback); }
			else { img.style.visibility = 'hidden'; }
		});
		return img;
	}

	var TYPE_ICONS = {CATEGORY: 'CategoryItem.png', VIDEO: 'VideoItem.png', AUDIO: 'AudioItem.png', SEARCH: 'SearchItem.png',
		ARTICLE: 'ArticleItem.png', PICTURE: 'PictureItem.png', MORE: 'MoreItem.png', MARKER: 'MarkerItem.png', DATA: 'DataItem.png'};
	function typeIcon(type) { return TYPE_ICONS[type] ? '/iptvplayer/icons/' + TYPE_ICONS[type] : ''; }

	// ------------------------------------------------------------------ information

	function pageInfo() {
		(function binaries() {
			api('binaries').then(function (r) {
				if (r.text) { $('binaries').textContent = r.text; $('binaries').classList.remove('muted'); }
				else { setTimeout(binaries, 1500); }
			}).catch(function () { setTimeout(binaries, 3000); });
		})();

		checkUpdates();

		$('resetBtn').addEventListener('click', function () {
			api('reset', {}).then(function (r) {
				var msg = t('Web interface has been reset.');
				if (r.stillRunning && r.stillRunning.length) { msg += ' ' + t('Still running:') + ' ' + r.stillRunning.join(', '); }
				$('resetResult').textContent = msg;
			});
		});
	}

	function checkUpdates() {
		var box = $('updates');
		// asked by the browser, not the box
		fetch('https://api.github.com/repos/oe-mirrors/e2iplayer/compare/v' + encodeURIComponent(E.version) + '...python3')
			.then(function (r) { return r.json().then(function (data) { return {status: r.status, data: data}; }); })
			.then(function (res) {
				clear(box).classList.remove('muted');
				if (res.status === 404) {
					box.appendChild(el('span', {cls: 'badge warn', text: t('Installed version %s has no release tag (local build?)', E.version)}));
					return;
				}
				var data = res.data;
				if (!data || !data.status) { throw new Error('no data'); }
				if (data.status === 'identical' || data.ahead_by === 0) {
					box.appendChild(el('span', {cls: 'badge ok', text: t('Up to date') + ' (v' + E.version + ')'}));
					return;
				}
				box.appendChild(el('span', {cls: 'badge info', text: t('%d commits behind %s', data.ahead_by, 'python3')}));
				box.appendChild(el('div', {cls: 'kv-title', text: t('New since the installed version')}));
				box.appendChild(el('ul', {cls: 'plain'}, collapseCommits(data.commits || []).slice(0, 25).map(function (c) {
					return el('li', null, el('a', {href: c.url, target: '_blank', rel: 'noopener', text: c.title}),
						el('span', {cls: 'muted', text: '  ' + c.date}));
				})));
			})
			.catch(function () {
				clear(box).appendChild(el('span', {cls: 'muted', text: t('Update check not possible')}));
			});
	}

	function collapseCommits(commits) {
		// "Merge pull request #N" + the PR commit it merged -> one "PR #N: title" line, newest first
		var hidden = {}, out = [];
		commits.slice().reverse().forEach(function (c) {
			if (hidden[c.sha]) { return; }
			var msg = (c.commit && c.commit.message) || '';
			var lines = msg.split('\n');
			var title = lines[0];
			var m = /^Merge pull request #(\d+)/.exec(title);
			if (m && c.parents && c.parents.length === 2) {
				hidden[c.parents[1].sha] = true;
				var body = lines.slice(1).join('\n').trim().split('\n')[0];
				title = 'PR #' + m[1] + ': ' + (body || title);
			}
			out.push({title: title, url: c.html_url, date: ((c.commit && c.commit.author && c.commit.author.date) || '').substring(0, 10)});
		});
		return out;
	}

	// ------------------------------------------------------------------ hosts

	function pageHosts() {
		var filter = $('hostFilter');
		filter.value = store('hostFilter') || '';
		api('hosts').then(function (r) {
			var box = clear($('hosts'));
			if (r.pinBlocked) {
				$('hostsMsg').appendChild(notice(t('The whole plugin is protected by a PIN - hosts can only be used on the receiver.'), 'warn'));
				return;
			}
			if (!r.hosts || !r.hosts.length) {
				box.appendChild(el('div', {cls: 'empty', text: t('No hosts are enabled.')}));
				return;
			}
			r.hosts.forEach(function (h) {
				var card = el('a', {cls: 'hostcard', href: '/iptvplayer/usehost', 'data-filter': (h.title + ' ' + h.name + ' ' + h.site).toLowerCase(),
					onclick: function (ev) { ev.preventDefault(); openHost(h.name); }},
					el('div', {cls: 'logo'}, h.logo ? el('img', {src: h.logo, alt: '', loading: 'lazy'}) : null),
					el('div', {cls: 'title', text: h.title}));
				box.appendChild(card);
			});
			applyFilter();
		});
		function applyFilter() {
			var q = filter.value.trim().toLowerCase();
			store('hostFilter', filter.value);
			Array.prototype.forEach.call($('hosts').children, function (card) {
				if (card.dataset.filter !== undefined) { card.classList.toggle('hidden', q !== '' && card.dataset.filter.indexOf(q) < 0); }
			});
		}
		filter.addEventListener('input', applyFilter);
	}

	function openHost(name) {
		api('host/action', {action: 'open', host: name}).then(function (r) {
			if (!r.ok) { toast(r.error, true); return; }
			location.href = '/iptvplayer/usehost';
		});
	}

	// ------------------------------------------------------------------ host browsing

	var hostState = null, hostPollTimer = null, lastListKey = '';

	function pageUseHost() {
		loadHostState();
	}

	function loadHostState() {
		clearTimeout(hostPollTimer);
		api('host/state').then(function (s) {
			hostState = s;
			renderHost();
			if (s.busy) { hostPollTimer = setTimeout(loadHostState, 700); }
		}).catch(function () { hostPollTimer = setTimeout(loadHostState, 2000); });
	}

	function hostAction(params) {
		if (hostState && hostState.busy && params.action !== 'cancel') { return; }
		api('host/action', params).then(function (r) {
			if (!r.ok) { toast(r.error, true); }
			if (params.action === 'close') { location.href = '/iptvplayer/hosts'; return; }
			loadHostState();
		});
	}

	function renderHost() {
		var s = hostState, box = clear($('host'));
		if (!s.host && !s.busy) {
			box.appendChild(el('div', {cls: 'empty'}, el('p', {text: t('No host is open.')}),
				el('a', {cls: 'btn primary', href: '/iptvplayer/hosts', text: t('Open a host from the host list.')})));
			return;
		}
		if (s.host) {
			box.appendChild(el('div', {cls: 'hosthead'},
				s.host.logo ? el('img', {src: s.host.logo, alt: ''}) : null,
				el('h1', {style: 'margin:0', text: s.host.title}),
				el('div', {cls: 'crumbs'}, [el('span', {text: s.host.title})].concat((s.path || []).map(function (p) { return el('span', {text: p}); })))));
		}
		var busy = s.busy;
		var backDisabled = busy || !s.host || (s.view === 'list' && !(s.path && s.path.length));
		box.appendChild(el('div', {cls: 'toolbar'},
			el('button', {cls: 'btn', text: '← ' + t('Back'), disabled: backDisabled, onclick: function () { hostAction({action: 'back'}); }}),
			el('button', {cls: 'btn', text: t('Initial list'), disabled: busy || !s.host, onclick: function () { hostAction({action: 'home'}); }}),
			el('button', {cls: 'btn', text: t('Reload list'), disabled: busy || !s.host || s.view !== 'list', onclick: function () { hostAction({action: 'refresh'}); }}),
			el('span', {cls: 'spacer'}),
			el('button', {cls: 'btn', text: t('Return to hosts list'), disabled: busy, onclick: function () { hostAction({action: 'close'}); }})));

		if (busy && s.cancelling) {
			box.appendChild(el('div', {cls: 'notice warn'}, spinnerText(t('Cancelling - waiting for the host to finish its current request') + ' (' + s.elapsed + 's)')));
		} else if (busy) {
			box.appendChild(el('div', {cls: 'notice'}, spinnerText(t('Loading data, please wait') + ' (' + s.elapsed + 's)  '),
				el('button', {cls: 'btn small', text: t('Cancel'), onclick: function () { hostAction({action: 'cancel'}); }})));
		}
		var dismiss = function () { hostAction({action: 'dismiss'}); };
		if (s.error) { box.appendChild(notice(s.error, 'err', dismiss)); }
		(s.notices || []).forEach(function (n) { box.appendChild(notice(n, 'warn', dismiss)); });
		if (!s.host) { return; }

		if (s.hasSearch && s.view === 'list') { box.appendChild(hostSearchForm(s)); }

		if (s.view === 'links') { box.appendChild(renderLinks(s)); }
		else if (s.view === 'article') { box.appendChild(renderArticle(s)); }
		else { box.appendChild(renderItems(s)); }

		var key = s.view + '|' + (s.path || []).join('/') + '|' + (s.items || []).length;
		if (key !== lastListKey && !busy) { window.scrollTo(0, 0); lastListKey = key; }
	}

	function hostSearchForm(s) {
		var input = el('input', {type: 'search', id: 'hostSearchText', placeholder: t('Search text'), value: store('hostSearch') || ''});
		var form = el('form', {cls: 'searchform card'}, input);
		var types = s.searchTypes || [];
		if (types.length) {
			types.forEach(function (st) {
				form.appendChild(el('button', {cls: 'btn primary', type: 'submit', 'data-type': st[1], text: t('Search') + ': ' + st[0]}));
			});
		} else {
			form.appendChild(el('button', {cls: 'btn primary', type: 'submit', 'data-type': '', text: t('Search')}));
		}
		form.addEventListener('submit', function (ev) {
			ev.preventDefault();
			var btn = ev.submitter || form.querySelector('button');
			store('hostSearch', input.value);
			hostAction({action: 'search', pattern: input.value, searchType: btn.getAttribute('data-type') || ''});
		});
		return form;
	}

	function renderItems(s) {
		var list = el('div', {cls: 'items'});
		if (!s.items || !s.items.length) {
			list.appendChild(el('div', {cls: 'empty', text: t('No results.')}));
			return list;
		}
		s.items.forEach(function (item) {
			if (item.type === 'SEARCH' && s.hasSearch) { return; }  // the search form above does that
			if (item.type === 'MARKER') {
				list.appendChild(el('div', {cls: 'item marker'}, el('div', {cls: 'body'}, el('div', {cls: 'name', text: item.name}),
					item.desc ? el('div', {cls: 'desc', text: item.desc}) : null)));
				return;
			}
			var clickable = item.type !== 'SEARCH';
			var row = el('div', {cls: 'item' + (clickable ? ' click' : ''), title: item.desc || item.name},
				thumb(item.icon, typeIcon(item.type)),
				el('div', {cls: 'body'},
					el('div', {cls: 'name'}, item.name + ' ', item.pin ? el('span', {cls: 'badge warn', text: t('Protected by PIN')}) : null),
					item.desc ? el('div', {cls: 'desc', text: item.desc}) : null));
			if (clickable) {
				row.addEventListener('click', function () { hostAction({action: 'item', index: item.i}); });
			} else {
				row.addEventListener('click', function () { var f = $('hostSearchText'); if (f) { f.focus(); } });
			}
			list.appendChild(row);
		});
		return list;
	}

	function renderLinks(s) {
		var wrap = el('div', null, el('h2', {text: t('Links for') + ' "' + s.linksTitle + '"'}));
		var list = el('div', {cls: 'items'});
		(s.links || []).forEach(function (link) {
			var actions = el('div', {cls: 'actions'});
			if (link.resolve) {
				actions.appendChild(el('button', {cls: 'btn small primary', text: t('Select'), onclick: function () { hostAction({action: 'resolve', index: link.i}); }}));
			} else {
				if (link.watch) { actions.appendChild(el('a', {cls: 'btn small', href: link.url, target: '_blank', rel: 'noopener noreferrer', text: t('Watch')})); }
				actions.appendChild(el('button', {cls: 'btn small', text: t('Add to downloader'), onclick: function () { hostAction({action: 'download', index: link.i}); }}));
				actions.appendChild(el('button', {cls: 'btn small', text: t('Copy link'), onclick: function () { copyText(link.url); }}));
			}
			list.appendChild(el('div', {cls: 'item'}, el('div', {cls: 'body'}, el('div', {cls: 'name', text: link.name}),
				link.resolve ? null : el('div', {cls: 'desc', text: link.url}), actions)));
		});
		wrap.appendChild(list);
		return wrap;
	}

	function renderArticle(s) {
		var a = s.article || {};
		var text = el('div', {cls: 'text'}, el('h2', {text: a.title || ''}), a.text || '');
		if (a.other && a.other.length) {
			text.appendChild(el('dl', {cls: 'kv', style: 'margin-top:12px'}, [].concat.apply([], a.other.map(function (kv) {
				return [el('dt', {text: kv[0]}), el('dd', {text: kv[1]})];
			}))));
		}
		return el('div', {cls: 'card article'}, (a.images || []).slice(0, 1).map(function (src) { return el('img', {src: src, alt: ''}); }), text);
	}

	function copyText(text) {
		var done = function () { toast(t('Link copied')); };
		if (navigator.clipboard && window.isSecureContext) {
			navigator.clipboard.writeText(text).then(done);
			return;
		}
		var ta = el('textarea', {style: 'position:fixed;opacity:0'});
		ta.value = text;
		document.body.appendChild(ta);
		ta.select();
		try { document.execCommand('copy'); done(); } catch (e) { /* ignore */ }
		document.body.removeChild(ta);
	}

	// ------------------------------------------------------------------ global search

	var searchTimer = null;
	var searchFilter = store('searchFilter') || {CATEGORY: true, VIDEO: true, AUDIO: true, exact: true};

	function pageSearch() {
		$('searchForm').addEventListener('submit', function (ev) {
			ev.preventDefault();
			api('search/start', {query: $('searchText').value}).then(function (r) {
				if (!r.ok) { toast(r.error, true); }
				loadSearch();
			});
		});
		$('searchStop').addEventListener('click', function () { api('search/stop', {}).then(loadSearch); });
		renderSearchFilters();
		loadSearch();
	}

	function renderSearchFilters() {
		var bar = clear($('searchFilters'));
		[['CATEGORY', t('Folders')], ['VIDEO', t('Videos')], ['AUDIO', t('Music')]].forEach(function (f) {
			bar.appendChild(el('button', {cls: 'btn small' + (searchFilter[f[0]] ? ' on' : ''), text: f[1], onclick: function () {
				searchFilter[f[0]] = !searchFilter[f[0]];
				store('searchFilter', searchFilter);
				renderSearchFilters();
				loadSearch();
			}}));
		});
		var exact = el('input', {type: 'checkbox', checked: !!searchFilter.exact, onchange: function () {
			searchFilter.exact = exact.checked;
			store('searchFilter', searchFilter);
			loadSearch();
		}});
		bar.appendChild(el('label', {cls: 'muted'}, exact, ' ' + t('Only exact matches')));
	}

	function loadSearch() {
		clearTimeout(searchTimer);
		api('search/state').then(function (s) {
			renderSearch(s);
			if (s.busy) { searchTimer = setTimeout(loadSearch, 1000); }
		});
	}

	function renderSearch(s) {
		var status = clear($('searchStatus'));
		$('searchStop').classList.toggle('hidden', !s.busy);
		if (s.busy) {
			var pct = s.total ? Math.round(100 * s.done / s.total) : 0;
			var bar = el('div', {cls: 'progress'}, el('div', {style: 'width:' + pct + '%'}));
			status.appendChild(el('div', {cls: 'card'},
				spinnerText(s.host ? t('Searching in %s', s.host) : t('Searching, please wait')),
				el('span', {cls: 'muted', text: '  ' + t('%d of %d hosts', s.done, s.total)}), el('div', {style: 'margin-top:8px'}, bar)));
		}
		var box = clear($('searchResults'));
		var query = (s.query || '').toLowerCase();
		var shown = 0;
		(s.results || []).forEach(function (res) {
			var items = res.items.filter(function (it) {
				var typeOk = it.type in searchFilter ? searchFilter[it.type] : true;
				var textOk = !searchFilter.exact || (it.name + ' ' + it.desc).toLowerCase().indexOf(query) >= 0;
				return typeOk && textOk;
			});
			if (!items.length) { return; }
			shown++;
			var open = function () {
				api('host/action', {action: 'openSearch', host: res.host, searchType: res.searchType}).then(function (r) {
					if (!r.ok) { toast(r.error, true); return; }
					location.href = '/iptvplayer/usehost';
				});
			};
			var section = el('div', {cls: 'resulthost'},
				el('h2', null, res.logo ? el('img', {src: res.logo, alt: ''}) : null, res.title,
					el('span', {cls: 'badge', text: items.length + ' ' + t('entries')}),
					el('button', {cls: 'btn small', text: t('Open in host') + ' →', onclick: open})));
			var list = el('div', {cls: 'items'});
			items.forEach(function (it) {
				list.appendChild(el('div', {cls: 'item click', onclick: open}, thumb(it.icon, typeIcon(it.type)),
					el('div', {cls: 'body'}, el('div', {cls: 'name', text: it.name}), it.desc ? el('div', {cls: 'desc', text: it.desc}) : null)));
			});
			section.appendChild(list);
			box.appendChild(section);
		});
		if (!shown && !s.busy && s.query) { box.appendChild(el('div', {cls: 'empty', text: t('No results.')})); }
	}

	// ------------------------------------------------------------------ download manager

	var dmTab = store('dmTab') || 'downloads', dmTimer = null;
	var DM_STATUS = {waiting: ['PENDING', ''], downloading: ['DOWNLOADING', 'info'], downloaded: ['DOWNLOADED', 'ok'],
		interrupted: ['ABORTED', 'warn'], error: ['DOWNLOAD ERROR', 'err'], postprocessing: ['POSTPROCESSING', 'info']};

	function pageDownloader() { loadDM(); }

	function dmCmd(params, confirmText) {
		if (confirmText && !window.confirm(confirmText)) { return; }
		api('dm', params).then(function (r) {
			if (!r.ok) { toast(r.error, true); }
			loadDM();
		});
	}

	function loadDM() {
		clearTimeout(dmTimer);
		api('dm').then(function (s) {
			renderDMToolbar(s);
			if (dmTab === 'archive') {
				api('dm/archive').then(renderArchive);
			} else {
				renderDMList(s);
				dmTimer = setTimeout(loadDM, 2000);
			}
		});
	}

	function renderDMToolbar(s) {
		var bar = clear($('dmToolbar')), status = clear($('dmStatus'));
		if (!s.initialized) {
			bar.appendChild(el('button', {cls: 'btn primary', text: t('Initialize Download Manager'), onclick: function () { dmCmd({cmd: 'init'}); }}));
			status.appendChild(el('span', {cls: 'badge warn', text: t('Download manager is not initialized')}));
			return;
		}
		status.appendChild(el('span', {cls: 'muted', text: t('Manager status:') + ' '}));
		status.appendChild(el('span', {cls: 'badge ' + (s.running ? 'ok' : 'warn'), text: s.running ? t('STARTED') : t('STOPPED')}));
		bar.appendChild(el('button', {cls: 'btn' + (dmTab === 'downloads' ? ' on' : ''), text: t('Downloads'), onclick: function () { dmTab = 'downloads'; store('dmTab', dmTab); loadDM(); }}));
		bar.appendChild(el('button', {cls: 'btn' + (dmTab === 'archive' ? ' on' : ''), text: t('Archive'), onclick: function () { dmTab = 'archive'; store('dmTab', dmTab); loadDM(); }}));
		bar.appendChild(el('span', {cls: 'spacer'}));
		bar.appendChild(el('button', {cls: 'btn', text: '▶ ' + t('Start'), disabled: s.running, onclick: function () { dmCmd({cmd: 'start'}); }}));
		bar.appendChild(el('button', {cls: 'btn', text: '■ ' + t('Stop'), disabled: !s.running, onclick: function () { dmCmd({cmd: 'stop'}); }}));
	}

	function renderDMList(s) {
		var box = clear($('dmList'));
		if (!s.initialized) { return; }
		if (!s.items.length) { box.appendChild(el('div', {cls: 'empty', text: t('No materials waiting in the downloader queue')})); return; }
		s.items.forEach(function (it) {
			var st = DM_STATUS[it.status] || [it.status, ''];
			var info = it.done > 0 || it.size > 0 ? fmtBytes(it.done) : '';
			if (it.size > 0) { info += ' / ' + fmtBytes(it.size); }
			else if (it.duration > 0 && it.doneDuration > 0) { info = fmtDuration(it.doneDuration) + ' / ' + fmtDuration(it.duration) + ' (' + info + ')'; }
			if (it.percent >= 0) { info += ', ' + it.percent + '%'; }
			if (it.status === 'downloading') { info += ', ' + fmtBytes(it.speed) + '/s'; }
			if (it.downloader) { info += (info ? '  ·  ' : '') + it.downloader; }
			var actions = el('div', {cls: 'actions'});
			var add = function (label, params, cls, confirmText) {
				actions.appendChild(el('button', {cls: 'btn small' + (cls ? ' ' + cls : ''), text: t(label), onclick: function () { dmCmd(params, confirmText); }}));
			};
			if (it.href && it.status !== 'waiting') { actions.appendChild(el('a', {cls: 'btn small', href: it.href, text: t('Watch')})); }
			if (it.status === 'waiting') { add('Move to top', {cmd: 'top', idx: it.idx}); add('Remove from queue', {cmd: 'removeQueued', idx: it.idx}, 'danger'); }
			else if (it.status === 'downloading') { add('Stop download', {cmd: 'stopItem', idx: it.idx}); }
			else if (it.status === 'interrupted') { add('Resume download', {cmd: 'resume', idx: it.idx}); add('Delete', {cmd: 'remove', idx: it.idx}, 'danger', t('Delete the file %s?', it.file)); }
			else if (it.status === 'downloaded' || it.status === 'error') { add('Download again', {cmd: 'retry', idx: it.idx}); add('Delete', {cmd: 'remove', idx: it.idx}, 'danger', t('Delete the file %s?', it.file)); }
			var progress = it.percent >= 0 && it.status === 'downloading' ? el('div', {cls: 'progress'}, el('div', {style: 'width:' + it.percent + '%'})) : null;
			box.appendChild(el('div', {cls: 'dmitem'},
				el('div', {cls: 'body'}, el('div', {cls: 'name'}, it.file + ' ', el('span', {cls: 'badge ' + st[1], text: t(st[0])})),
					el('div', {cls: 'url', text: it.url}), info ? el('div', {cls: 'stats', text: info}) : null, progress),
				actions));
		});
	}

	function renderArchive(r) {
		var box = clear($('dmList'));
		box.appendChild(el('p', {cls: 'muted', text: r.folder || ''}));
		if (r.error) { box.appendChild(notice(r.error, 'err')); }
		if (!r.files || !r.files.length) { box.appendChild(el('div', {cls: 'empty', text: t('Nothing has been downloaded yet.')})); return; }
		r.files.forEach(function (f) {
			box.appendChild(el('div', {cls: 'dmitem'},
				el('div', {cls: 'body'}, el('div', {cls: 'name', text: f.file}),
					el('div', {cls: 'stats', text: fmtBytes(f.size) + '  ·  ' + new Date(f.mtime * 1000).toLocaleString()})),
				el('div', {cls: 'actions'}, el('a', {cls: 'btn small', href: f.href, text: t('Watch')}),
					el('button', {cls: 'btn small danger', text: t('Delete'), onclick: function () { dmCmd({cmd: 'deleteFile', path: f.path}, t('Delete the file %s?', f.file)); }}))));
		});
	}

	// ------------------------------------------------------------------ settings

	var settingsLocked = false;

	function pageSettings() {
		api('settings/sections').then(function (r) {
			settingsLocked = r.locked;
			if (r.locked) { $('settingsMsg').appendChild(notice(t('The settings are protected by a PIN on the receiver - here they can only be viewed.'), 'warn')); }
			var box = clear($('settings'));
			var opened = store('openSections') || [];
			r.sections.forEach(function (sec) { box.appendChild(settingsSection(sec.id, sec.label, opened.indexOf(sec.id) >= 0)); });
			box.appendChild(settingsSection('__hosts', t('Hosts'), opened.indexOf('__hosts') >= 0));
		});
		var timer = null;
		$('settingsFilter').addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(filterSettings, 250); });
	}

	function settingsSection(id, label, open) {
		var content = el('div', {cls: 'content'});
		var det = el('details', {cls: 'section', 'data-id': id}, el('summary', {text: label}), content);
		det.addEventListener('toggle', function () {
			var opened = (store('openSections') || []).filter(function (x) { return x !== id; });
			if (det.open) { opened.push(id); if (!det.dataset.loaded) { loadSection(det); } }
			store('openSections', opened);
		});
		if (open) { det.open = true; }
		return det;
	}

	function loadSection(det) {
		var id = det.dataset.id, content = det.querySelector('.content');
		det.dataset.loaded = '1';
		if (!content.firstChild) { content.appendChild(el('div', {cls: 'empty'}, el('span', {cls: 'spinner'}))); }
		var p = id === '__hosts' ? api('settings/hosts').then(function (r) { renderHostRows(content, r.hosts); })
			: api('settings/section?id=' + encodeURIComponent(id)).then(function (r) { renderRows(clear(content), r.rows, function () { loadSection(det); }); });
		return p;
	}

	function renderRows(content, rows, reload) {
		if (!rows.length) { content.appendChild(el('div', {cls: 'empty', text: t('Nothing found.')})); return; }
		rows.forEach(function (row) {
			if (row.header !== undefined) { content.appendChild(el('div', {cls: 'row sub', text: row.header})); return; }
			content.appendChild(settingRow(row, reload));
		});
	}

	function saveSetting(name, value, rowNode, reload) {
		api('settings/set', {name: name, value: value}).then(function (r) {
			if (!r.ok) { toast(r.error || t('Error'), true); }
			else {
				toast(t('Saved'));
				if (rowNode) { rowNode.classList.add('saved'); setTimeout(function () { rowNode.classList.remove('saved'); }, 800); }
			}
			if (reload) { reload(); }
		});
	}

	function settingRow(row, reload) {
		var label = el('div', {cls: 'label', style: row.indent ? 'padding-left:' + (row.indent * 18) + 'px' : null, text: row.label});
		var control = el('div', {cls: 'control'});
		var node = el('div', {cls: 'row', 'data-filter': (row.label + ' ' + row.name).toLowerCase()}, label, control);
		var save = function (value) { saveSetting(row.name, value, node, reload); };
		if (row.kind === 'bool') {
			var cb = el('input', {type: 'checkbox', checked: !!row.value, onchange: function () { save(cb.checked); }});
			control.appendChild(el('label', {cls: 'switch'}, cb, el('span')));
		} else if (row.kind === 'select') {
			var sel = el('select', {onchange: function () { save(sel.value); }}, row.choices.map(function (c) {
				return el('option', {value: c[0], selected: c[0] === row.value, text: c[1]});
			}));
			control.appendChild(sel);
		} else if (row.kind === 'int') {
			var num = el('input', {type: 'number', value: row.value, min: row.min, max: row.max, style: 'width:120px'});
			num.addEventListener('change', function () {
				var v = parseInt(num.value, 10);
				if (isNaN(v) || (row.min !== undefined && v < row.min) || (row.max !== undefined && v > row.max)) {
					toast(t('The value must be between %d and %d.', row.min, row.max), true);
					num.value = row.value;
					return;
				}
				save(v);
			});
			control.appendChild(num);
		} else if (row.kind === 'text' || row.kind === 'password') {
			var txt = el('input', {type: row.kind === 'password' ? 'password' : 'text', value: row.value,
				placeholder: row.kind === 'password' ? t('(unchanged - type a new one to change it)') : null, autocomplete: 'off'});
			txt.addEventListener('change', function () { if (row.kind !== 'password' || txt.value) { save(txt.value); } });
			txt.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') { txt.blur(); } });
			control.appendChild(txt);
		} else {
			control.appendChild(el('span', {text: row.value}));
			if (row.note) { control.appendChild(el('span', {cls: 'note', text: '(' + row.note + ')'})); }
		}
		return node;
	}

	function renderHostRows(content, hosts) {
		clear(content);
		hosts.forEach(function (h) {
			var cb = el('input', {type: 'checkbox', checked: h.enabled, disabled: settingsLocked, onchange: function () {
				saveSetting('host' + h.name, cb.checked, node);
			}});
			var opts = el('div', {cls: 'hostopts hidden'});
			var optBtn = h.hasOptions ? el('button', {cls: 'btn small', text: t('Options') + ' ▾', onclick: function () {
				var show = opts.classList.contains('hidden');
				opts.classList.toggle('hidden', !show);
				if (show && !opts.dataset.loaded) { loadHostOptions(h.name, opts); }
			}}) : null;
			var node = el('div', {cls: 'hostrow', 'data-filter': (h.title + ' ' + h.name).toLowerCase()},
				h.logo ? el('img', {src: h.logo, alt: '', loading: 'lazy'}) : el('span', {cls: 'nologo'}),
				el('div', {cls: 'title', text: h.title}),
				el('div', {cls: 'controls'}, optBtn, el('label', {cls: 'switch', title: t('Enabled')}, cb, el('span'))), opts);
			content.appendChild(node);
		});
	}

	function loadHostOptions(name, opts) {
		opts.dataset.loaded = '1';
		clear(opts).appendChild(el('span', {cls: 'spinner'}));
		api('settings/host?name=' + encodeURIComponent(name)).then(function (r) {
			renderRows(clear(opts), r.rows, function () { loadHostOptions(name, opts); });
		});
	}

	function filterSettings() {
		var q = $('settingsFilter').value.trim().toLowerCase();
		var sections = Array.prototype.slice.call(document.querySelectorAll('details.section'));
		if (!q) {
			sections.forEach(function (det) {
				det.classList.remove('hidden');
				Array.prototype.forEach.call(det.querySelectorAll('.row, .hostrow'), function (r) { r.classList.remove('hidden'); });
			});
			return;
		}
		// every section has to be loaded to be searched
		Promise.all(sections.map(function (det) { return det.dataset.loaded ? null : loadSection(det); })).then(function () {
			sections.forEach(function (det) {
				var hits = 0;
				Array.prototype.forEach.call(det.querySelectorAll('.content > .row, .content > .hostrow'), function (r) {
					var match = r.dataset.filter !== undefined && r.dataset.filter.indexOf(q) >= 0;
					r.classList.toggle('hidden', !match);
					if (match) { hits++; }
				});
				det.classList.toggle('hidden', !hits);
				if (hits) { det.open = true; }
			});
		});
	}

	// ------------------------------------------------------------------ debug log

	var log = {pos: -1, paused: false, follow: true, onlyErrors: false, filter: '', lines: 0, timer: null};
	var MAX_LOG_LINES = 5000;

	function pageLogs() {
		var bar = $('logToolbar');
		var pauseBtn = el('button', {cls: 'btn', text: '❚❚ ' + t('Pause'), onclick: function () {
			log.paused = !log.paused;
			pauseBtn.textContent = log.paused ? '▶ ' + t('Resume') : '❚❚ ' + t('Pause');
			pauseBtn.classList.toggle('on', log.paused);
			if (!log.paused) { pollLog(); }
		}});
		var followBtn = el('button', {cls: 'btn on', text: t('Follow'), onclick: function () {
			log.follow = !log.follow;
			followBtn.classList.toggle('on', log.follow);
			if (log.follow) { scrollLog(); }
		}});
		var errBtn = el('button', {cls: 'btn', text: t('Only errors and warnings'), onclick: function () {
			log.onlyErrors = !log.onlyErrors;
			errBtn.classList.toggle('on', log.onlyErrors);
			applyLogFilter();
		}});
		var filter = el('input', {type: 'search', placeholder: t('Filter')});
		filter.addEventListener('input', function () { log.filter = filter.value.toLowerCase(); applyLogFilter(); });
		bar.appendChild(pauseBtn);
		bar.appendChild(followBtn);
		bar.appendChild(errBtn);
		bar.appendChild(filter);
		bar.appendChild(el('span', {cls: 'spacer'}));
		bar.appendChild(el('button', {cls: 'btn', text: t('Clear view'), onclick: function () { clear($('log')); log.lines = 0; updateLogInfo(); }}));
		bar.appendChild(el('a', {cls: 'btn', href: '/iptvplayer/logs?cmd=downloadLog', text: t('Download log file')}));
		bar.appendChild(el('button', {cls: 'btn danger', text: t('Delete log file'), onclick: function () {
			if (!window.confirm(t('Delete the debug log file?'))) { return; }
			api('log/delete', {}).then(function (r) {
				if (r.ok) { toast(t('Debug file has been deleted')); clear($('log')); log.lines = 0; log.pos = 0; }
				else { toast(r.error, true); }
			});
		}}));
		// stop following when the user scrolls up, follow again at the bottom
		$('log').addEventListener('scroll', function () {
			var box = $('log');
			var atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 30;
			if (log.follow !== atBottom) { log.follow = atBottom; followBtn.classList.toggle('on', atBottom); }
		});
		pollLog();
	}

	function logClass(line) {
		if (/Traceback|EXCEPTION|Exception|Error|ERROR|error:/.test(line)) { return 'e'; }
		if (/WARNING|Warning|WARN/.test(line)) { return 'w'; }
		if (/^\s*(={3,}|>{3,})/.test(line)) { return 'i'; }
		return '';
	}

	function lineVisible(node) {
		if (log.onlyErrors && node.className.indexOf('e') < 0 && node.className.indexOf('w') < 0) { return false; }
		return !log.filter || node.textContent.toLowerCase().indexOf(log.filter) >= 0;
	}

	function applyLogFilter() {
		Array.prototype.forEach.call($('log').children, function (node) { node.classList.toggle('hidden', !lineVisible(node)); });
		scrollLog();
	}

	function scrollLog() { if (log.follow) { var box = $('log'); box.scrollTop = box.scrollHeight; } }

	function updateLogInfo(r) {
		var info = $('logInfo');
		if (r && r.path) { info.dataset.path = r.path + '  ·  ' + fmtBytes(r.size); }
		info.textContent = (info.dataset.path || '') + '  ·  ' + log.lines + ' ' + t('lines');
	}

	function pollLog() {
		clearTimeout(log.timer);
		if (log.paused) { return; }
		api('log?pos=' + log.pos).then(function (r) {
			var msg = clear($('logMsg'));
			if (r.state !== 'ok') {
				var texts = {off: 'Debug option is disabled - nothing to display', console: 'Debug option set to console - nothing to display',
					nofile: 'Debug file does not exist yet, waiting for it'};
				msg.appendChild(notice(t(texts[r.state] || r.state), 'warn'));
				log.pos = 0;
			} else {
				var box = $('log');
				if (r.reset && log.pos > 0) {
					clear(box);
					log.lines = 0;
					box.appendChild(el('div', {cls: 'i', text: '—— ' + t('The log file was started again.') + ' ——'}));
				}
				log.pos = r.pos;
				if (r.text) {
					var frag = document.createDocumentFragment();
					r.text.replace(/\r?\n$/, '').split(/\r?\n/).forEach(function (line) {
						var node = el('div', {cls: logClass(line), text: line});
						if (!lineVisible(node)) { node.classList.add('hidden'); }
						frag.appendChild(node);
						log.lines++;
					});
					box.appendChild(frag);
					while (box.children.length > MAX_LOG_LINES) { box.removeChild(box.firstChild); log.lines--; }
					scrollLog();
				}
				updateLogInfo(r);
			}
			log.timer = setTimeout(pollLog, 1500);
		}).catch(function () { log.timer = setTimeout(pollLog, 4000); });
	}

	// ------------------------------------------------------------------

	// light / dark design; the page head sets it before drawing (webParts.page), this only switches
	(function themeToggle() {
		var btn = $('themeToggle');
		if (!btn) { return; }
		var show = function () {
			var light = document.documentElement.getAttribute('data-theme') === 'light';
			btn.innerHTML = light ? '&#9790;' : '&#9788;';  // moon in the light design, sun in the dark one
		};
		btn.addEventListener('click', function () {
			var next = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
			document.documentElement.setAttribute('data-theme', next);
			try { localStorage.setItem('e2i.theme', next); } catch (e) { /* private mode */ }
			show();
		});
		show();
	})();

	var pages = {info: pageInfo, hosts: pageHosts, usehost: pageUseHost, search: pageSearch, downloader: pageDownloader,
		settings: pageSettings, logs: pageLogs};
	var init = pages[document.body.getAttribute('data-page')];
	if (init) { init(); }
})();
