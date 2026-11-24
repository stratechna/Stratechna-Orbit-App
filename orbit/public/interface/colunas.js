/* Larguras das colunas à medida, em todas as tabelas da interface /orbit (24-11-2026, pedido do Vítor: «tal como
 * fizemos no email, haver a possibilidade de fazer resize à largura das colunas. No CRM é importante e não tem.
 * Verifica também outras apps. Nem todos os ecrãs têm a largura projetada»).
 *
 * Um só mecanismo para todas as listas (CRM, Desk, Projetos, RH, Gestão, Operações, Marketing, Administração e as fichas
 * com tabelas): cada cabeçalho `th` de uma `.tabela-wrap table` ganha uma pega na margem direita.
 *   · arrastar alarga ou estreita a coluna (mínimo 48 px); a tabela passa a `table-layout: fixed` e o texto que não cabe
 *     acaba em «…» (o texto inteiro fica na dica);
 *   · a largura fica guardada por ecrã e por coluna (localStorage deste aparelho — é uma preferência de quem vê);
 *   · duplo clique na pega volta às larguras automáticas dessa tabela.
 * Não toca no Vue: as pegas são elementos nossos dentro do `th`, repostas se o Vue redesenhar o cabeçalho.
 */
(function () {
	'use strict';
	var PREFIXO = 'orbit-colunas:';
	var MIN = 48;

	var css = document.createElement( 'style' );
	css.textContent = [
		'.tabela-wrap table thead th{position:relative}',
		'.oc-pega{position:absolute;top:0;right:-4px;width:9px;height:100%;cursor:col-resize;z-index:3;touch-action:none}',
		'.oc-pega::after{content:"";position:absolute;top:22%;bottom:22%;left:4px;width:1px;background:currentColor;opacity:0;transition:opacity .12s}',
		'.tabela-wrap thead th:hover .oc-pega::after,.oc-pega.on::after{opacity:.35}',
		'table.oc-fixa{table-layout:fixed}',
		'table.oc-fixa th,table.oc-fixa td{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
		'body.oc-a-arrastar,body.oc-a-arrastar *{cursor:col-resize!important;user-select:none!important}'
	].join( '' );
	document.head.appendChild( css );

	function ecra() { return ( location.pathname + ( location.hash || '' ) ).replace( /[?].*$/, '' ).replace( /\/[^/]*\d[^/]*$/, '/:id' ); }
	function cabecalhos( t ) { return Array.prototype.slice.call( t.querySelectorAll( ':scope > thead > tr:first-child > th' ) ); }
	function nomeCol( th, i ) { return ( th.textContent || '' ).trim().slice( 0, 40 ) || ( '#' + i ); }
	function chave( t ) { return PREFIXO + ecra() + '|' + cabecalhos( t ).map( nomeCol ).join( '¦' ); }
	function ler( k ) { try { return JSON.parse( localStorage.getItem( k ) || 'null' ); } catch ( e ) { return null; } }
	function gravar( k, v ) { try { if ( v ) { localStorage.setItem( k, JSON.stringify( v ) ); } else { localStorage.removeItem( k ); } } catch ( e ) {} }

	function fixar( t, larguras ) {   // larguras: { nome: px }
		var ths = cabecalhos( t ), total = 0;
		ths.forEach( function ( th, i ) {
			var w = larguras[ nomeCol( th, i ) ] || th.getBoundingClientRect().width;
			w = Math.max( MIN, Math.round( w ) ); th.style.width = w + 'px'; total += w;
			if ( ! th.title && th.textContent.trim() ) { th.title = th.textContent.trim(); }
		} );
		t.classList.add( 'oc-fixa' );
		t.style.width = total + 'px'; t.style.minWidth = '100%';
	}
	function soltar( t ) {
		cabecalhos( t ).forEach( function ( th ) { th.style.width = ''; } );
		t.classList.remove( 'oc-fixa' ); t.style.width = ''; t.style.minWidth = '';
	}

	function preparar( t ) {
		var ths = cabecalhos( t );
		if ( ! ths.length ) { return; }
		var k = chave( t );
		if ( t.__ocChave !== k ) {   // tabela nova ou colunas mudaram: aplicar o que estiver guardado
			t.__ocChave = k;
			var g = ler( k );
			if ( g ) { fixar( t, g ); } else if ( t.classList.contains( 'oc-fixa' ) ) { soltar( t ); }
		}
		ths.forEach( function ( th, i ) {
			if ( th.querySelector( ':scope > .oc-pega' ) ) { return; }
			if ( i === ths.length - 1 && ths.length > 1 && ! th.textContent.trim() ) { return; }   // coluna de acções vazia no fim
			var p = document.createElement( 'span' );
			p.className = 'oc-pega'; p.title = 'Arrastar para mudar a largura · duplo clique repõe';
			p.addEventListener( 'click', function ( e ) { e.stopPropagation(); } );   // não ordenar ao largar
			p.addEventListener( 'dblclick', function ( e ) { e.preventDefault(); e.stopPropagation(); gravar( chave( t ), null ); soltar( t ); } );
			p.addEventListener( 'pointerdown', function ( e ) {
				if ( e.button !== 0 ) { return; }
				e.preventDefault(); e.stopPropagation();
				var todos = cabecalhos( t ), atual = {};
				todos.forEach( function ( h, j ) { atual[ nomeCol( h, j ) ] = h.getBoundingClientRect().width; } );
				fixar( t, atual );
				var x0 = e.clientX, w0 = th.getBoundingClientRect().width, n = nomeCol( th, i );
				p.classList.add( 'on' ); document.body.classList.add( 'oc-a-arrastar' );
				try { p.setPointerCapture( e.pointerId ); } catch ( er ) {}
				function mexer( ev ) { atual[ n ] = Math.max( MIN, w0 + ev.clientX - x0 ); fixar( t, atual ); }
				function largar() {
					p.classList.remove( 'on' ); document.body.classList.remove( 'oc-a-arrastar' );
					p.removeEventListener( 'pointermove', mexer ); p.removeEventListener( 'pointerup', largar ); p.removeEventListener( 'pointercancel', largar );
					gravar( chave( t ), atual );
				}
				p.addEventListener( 'pointermove', mexer ); p.addEventListener( 'pointerup', largar ); p.addEventListener( 'pointercancel', largar );
			} );
			th.appendChild( p );
		} );
	}

	var pendente = null;
	function varrer() {
		pendente = null;
		document.querySelectorAll( '.tabela-wrap table' ).forEach( function ( t ) { try { preparar( t ); } catch ( e ) {} } );
	}
	new MutationObserver( function () { if ( ! pendente ) { pendente = requestAnimationFrame( varrer ); } } )
		.observe( document.documentElement, { childList: true, subtree: true } );
	window.addEventListener( 'hashchange', function () { setTimeout( varrer, 50 ); } );
	varrer();
}());
