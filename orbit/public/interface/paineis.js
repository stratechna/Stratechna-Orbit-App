/* Painéis redimensionáveis na interface /orbit (24-11-2026, pedido do Vítor: «aqui os painéis têm que poder ser
 * redimensionados tal como no mail»).
 *
 * As vistas de vários painéis são grelhas com larguras fixas (menu 232 px; ficha 300 | centro | 300; caixa de entrada,
 * chat, documentos). Entre dois painéis fica uma pega (elemento nosso em `position: fixed`, fora da grelha, para não
 * contar como coluna): arrastar muda a largura do painel fixo vizinho, o painel flexível ocupa o resto. A largura fica
 * guardada neste aparelho por tipo de vista; duplo clique na pega repõe a de origem. Só em ecrãs com 900 px ou mais —
 * abaixo disso as vistas empilham e as larguras guardadas não se aplicam.
 */
(function () {
	'use strict';
	// selector → índices das colunas flexíveis (as outras são fixas e são as que se arrastam)
	var VISTAS = [
		{ sel: '.app', flex: [ 1 ] },
		{ sel: '.ficha', flex: [ 1 ] },
		{ sel: '.caixa3', flex: [ 2 ] },
		{ sel: '.caixa:not(.caixa3)', flex: [ 1 ] },
		{ sel: '.chat', flex: [ 1, 2 ] },
		{ sel: '.docs', flex: [ 1 ] },
		// 25-11-2026 (Vítor): também nos documentos — fichas do ERP, faturas/guias/propostas/recibos, tickets, compras
		{ sel: '.erp-registo', flex: [ 0 ] },
		{ sel: '.prop-corpo', flex: [ 0 ] },
		{ sel: '.desk-grelha', flex: [ 0 ] },
		{ sel: '.compras-rever', flex: [ 1 ] },
		{ sel: '.fila', flex: [ 0 ] }
	];
	var MIN = 160, CHAVE = 'orbit-paineis:';
	var css = document.createElement( 'style' );
	css.textContent = '.op-pega{position:fixed;width:9px;margin-left:-4px;cursor:col-resize;z-index:60;touch-action:none}'
		+ '.op-pega::after{content:"";position:absolute;top:0;bottom:0;left:4px;width:1px;background:var(--acao,#b20009);opacity:0;transition:opacity .12s}'
		+ '.op-pega:hover::after,.op-pega.on::after{opacity:.7}'
		+ 'body.op-a-arrastar,body.op-a-arrastar *{cursor:col-resize!important;user-select:none!important}';
	document.head.appendChild( css );

	function ler( k ) { try { return JSON.parse( localStorage.getItem( CHAVE + k ) || 'null' ); } catch ( e ) { return null; } }
	function gravar( k, v ) { try { if ( v ) { localStorage.setItem( CHAVE + k, JSON.stringify( v ) ); } else { localStorage.removeItem( CHAVE + k ); } } catch ( e ) {} }
	function largo() { return window.innerWidth >= 900; }
	function colunas( el ) { return Array.prototype.filter.call( el.children, function ( c ) { return getComputedStyle( c ).display !== 'none' && ! c.classList.contains( 'op-pega' ); } ); }

	function aplicar( el, v, larguras ) {   // larguras: { indice: px } das colunas fixas
		var cols = colunas( el );
		el.style.gridTemplateColumns = cols.map( function ( c, i ) { return v.flex.indexOf( i ) >= 0 ? 'minmax(0,1fr)' : ( larguras[ i ] ? larguras[ i ] + 'px' : c.getBoundingClientRect().width + 'px' ); } ).join( ' ' );
	}

	var pegas = [];
	function limparPegas() { pegas.forEach( function ( p ) { p.remove(); } ); pegas = []; }

	function preparar() {
		limparPegas();
		if ( ! largo() ) {
			document.querySelectorAll( '[data-op]' ).forEach( function ( el ) { el.style.gridTemplateColumns = ''; el.removeAttribute( 'data-op' ); } );
			return;
		}
		VISTAS.forEach( function ( v ) {
			document.querySelectorAll( v.sel ).forEach( function ( el ) {
				if ( getComputedStyle( el ).display !== 'grid' ) { return; }
				var cols = colunas( el );
				if ( cols.length < 2 ) { return; }
				var g = ler( v.sel );
				if ( g && el.getAttribute( 'data-op' ) !== '1' ) { aplicar( el, v, g ); }
				el.setAttribute( 'data-op', '1' );
				for ( var i = 0; i < cols.length - 1; i++ ) {
					var fixa = v.flex.indexOf( i ) < 0 ? i : ( v.flex.indexOf( i + 1 ) < 0 ? i + 1 : -1 );
					if ( fixa < 0 ) { continue; }
					var p = document.createElement( 'div' );
					p.className = 'op-pega'; p.title = 'Arrastar para mudar a largura · duplo clique repõe';
					p.__el = el; p.__v = v; p.__i = i; p.__fixa = fixa;
					document.body.appendChild( p ); pegas.push( p );
					ligar( p );
				}
			} );
		} );
		posicionar();
	}

	function posicionar() {
		pegas.forEach( function ( p ) {
			var cols = colunas( p.__el ), a = cols[ p.__i ];
			if ( ! a || ! document.body.contains( p.__el ) ) { p.style.display = 'none'; return; }
			var r = a.getBoundingClientRect(), c = p.__el.getBoundingClientRect();
			var topo = Math.max( c.top, 0 ), fundo = Math.min( c.bottom, window.innerHeight );
			if ( fundo - topo < 20 ) { p.style.display = 'none'; return; }
			p.style.display = ''; p.style.left = r.right + 'px'; p.style.top = topo + 'px'; p.style.height = ( fundo - topo ) + 'px';
		} );
	}

	function ligar( p ) {
		p.addEventListener( 'dblclick', function ( e ) { e.preventDefault(); gravar( p.__v.sel, null ); p.__el.style.gridTemplateColumns = ''; setTimeout( posicionar, 30 ); } );
		p.addEventListener( 'pointerdown', function ( e ) {
			if ( e.button !== 0 ) { return; }
			e.preventDefault();
			var el = p.__el, v = p.__v, cols = colunas( el ), larguras = {};
			cols.forEach( function ( c, i ) { if ( v.flex.indexOf( i ) < 0 ) { larguras[ i ] = Math.round( c.getBoundingClientRect().width ); } } );
			var x0 = e.clientX, w0 = larguras[ p.__fixa ], esquerda = p.__fixa === p.__i, max = el.getBoundingClientRect().width * 0.6;
			p.classList.add( 'on' ); document.body.classList.add( 'op-a-arrastar' );
			try { p.setPointerCapture( e.pointerId ); } catch ( er ) {}
			function mexer( ev ) {
				var d = ev.clientX - x0;
				larguras[ p.__fixa ] = Math.round( Math.min( max, Math.max( MIN, esquerda ? w0 + d : w0 - d ) ) );
				aplicar( el, v, larguras ); posicionar();
			}
			function largar() {
				p.classList.remove( 'on' ); document.body.classList.remove( 'op-a-arrastar' );
				p.removeEventListener( 'pointermove', mexer ); p.removeEventListener( 'pointerup', largar ); p.removeEventListener( 'pointercancel', largar );
				gravar( v.sel, larguras );
			}
			p.addEventListener( 'pointermove', mexer ); p.addEventListener( 'pointerup', largar ); p.addEventListener( 'pointercancel', largar );
		} );
	}

	var pend = null, posPend = null;
	function agendar() { if ( ! pend ) { pend = setTimeout( function () { pend = null; try { preparar(); } catch ( e ) {} }, 150 ); } }
	function reposicionar() { if ( ! posPend ) { posPend = requestAnimationFrame( function () { posPend = null; try { posicionar(); } catch ( e ) {} } ); } }
	new MutationObserver( function ( ms ) {
		if ( ms.every( function ( m ) { return Array.prototype.every.call( m.addedNodes, function ( n ) { return n.classList && n.classList.contains( 'op-pega' ); } )
			&& Array.prototype.every.call( m.removedNodes, function ( n ) { return n.classList && n.classList.contains( 'op-pega' ); } ); } ) ) { return; }
		agendar();
	} ).observe( document.documentElement, { childList: true, subtree: true } );
	window.addEventListener( 'resize', agendar );
	window.addEventListener( 'hashchange', agendar );
	document.addEventListener( 'scroll', reposicionar, true );
	agendar();
}());
