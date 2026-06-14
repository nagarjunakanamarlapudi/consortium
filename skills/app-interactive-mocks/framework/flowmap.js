/* flowmap.js — auto-derived screen graph for app-interactive-mocks.
   Nodes from Router screens; edges from each screen's declared `links`.
   Pure deriveGraph is node-testable. */
(function (global) {
  function deriveGraph(screens) {
    const nodes = Object.values(screens).map(s => ({ id: s.id, title: s.title || s.id }));
    const edges = [];
    Object.values(screens).forEach(s => (s.links || []).forEach(to => {
      if (screens[to]) edges.push({ from: s.id, to });
    }));
    return { nodes, edges };
  }
  function mount(hostElId) {
    const host = document.getElementById(hostElId);
    if (!host || !global.Router) return;
    function paint() {
      const { nodes, edges } = deriveGraph(global.Router.getScreens());
      const cur = (global.Router.current() || {}).id;
      host.innerHTML = `<div class="flowmap">
        ${nodes.map(n => `<button class="fm-node${n.id === cur ? ' on' : ''}" onclick="Router.navigate('${n.id}',{mode:'replace'})">${n.title}</button>`).join('')}
        <div class="fm-edges">${edges.map(e => `<span class="fm-edge">${e.from} &rarr; ${e.to}</span>`).join('')}</div>
      </div>`;
    }
    paint();
    global.addEventListener('screenchange', paint);
  }
  const Flowmap = { deriveGraph, mount };
  global.Flowmap = Flowmap;
  if (typeof module !== 'undefined' && module.exports) module.exports = Flowmap;
})(typeof window !== 'undefined' ? window : globalThis);
