/* router.js — in-frame screen router for app-interactive-mocks.
   Swaps the active screen inside one .phone-screen; keeps a back-stack and tab bar.
   Pure reducer (_reduce) is node-testable. */
(function (global) {
  const screens = {};   // id -> {id,title,tab,render,links}
  let stack = [];       // screen ids; last = active
  let tabs = [];        // [{id,label,icon,screen}]
  let rootEl = null;

  function registerScreen(id, def) { screens[id] = Object.assign({ id, title: id, links: [] }, def); }
  function getScreens() { return screens; }
  function current() { return screens[stack[stack.length - 1]] || null; }
  function stackIds() { return stack.slice(); }

  // pure: given a stack + action, return the next stack
  function reduce(stk, action) {
    const s = stk.slice();
    switch (action.type) {
      case 'push':    s.push(action.id); return s;
      case 'replace': s[s.length - 1] = action.id; return s;
      case 'pop':     return s.length > 1 ? s.slice(0, -1) : s;
      case 'tab':     return [action.id];
      default:        return s;
    }
  }

  function renderTabBar() {
    if (!tabs.length) return '';
    const activeTab = (current() || {}).tab;
    return `<nav class="tabbar">${tabs.map(t =>
      `<button class="tab${t.id === activeTab ? ' on' : ''}" onclick="Router.navigate('${t.screen}',{mode:'tab'})">
         <span class="tab-ico">${t.icon || ''}</span><span class="tab-lbl">${t.label}</span>
       </button>`).join('')}</nav>`;
  }

  function paint(transition) {
    if (!rootEl) return;
    const scr = current();
    if (!scr) return;
    const ctx = {
      surface: document.body.dataset.surface || 'phone',
      theme: document.documentElement.dataset.theme || 'neutral',
      state: global.state,
      back: back, navigate: navigate,
    };
    const head = (typeof global.statusBar === 'function') ? global.statusBar() : '';
    rootEl.innerHTML = head + `<div class="scr ${transition || ''}">${scr.render(ctx)}</div>` + renderTabBar();
    global.dispatchEvent(new CustomEvent('screenchange', { detail: { id: scr.id, stack: stackIds() } }));
  }

  function navigate(id, opts) {
    opts = opts || {};
    const mode = opts.mode || 'push';
    if (!screens[id]) { console.warn('[router] unknown screen:', id); return; }
    const reduceType = (mode === 'modal') ? 'push' : mode;
    const transition = mode === 'push' ? 'scr-push' : mode === 'modal' ? 'scr-modal' : mode === 'pop' ? 'scr-pop' : '';
    stack = reduce(stack, { type: reduceType, id });
    paint(transition);
  }
  function back() {
    const before = stack.length;
    stack = reduce(stack, { type: 'pop' });
    if (stack.length !== before) paint('scr-pop');
  }
  function mountTabBar(t) { tabs = (t || []).slice(); }
  function mount(rootElId, defaultScreenId) {
    rootEl = document.getElementById(rootElId);
    stack = [defaultScreenId];
    paint('');
  }

  const Router = { registerScreen, getScreens, current, stack: stackIds, navigate, back, mountTabBar, mount, _reduce: reduce };
  global.Router = Router;
  if (typeof module !== 'undefined' && module.exports) module.exports = Router;
})(typeof window !== 'undefined' ? window : globalThis);
