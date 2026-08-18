/* ==========================================================================
   gestures.js — Mobile-native pointer gestures
   ==========================================================================
   Wires up swipe-left (delete) + swipe-right (reveal save/snooze) on rows
   marked with `data-id` attribute. Tap-without-drag fires the row's tapHandler.

   Usage in your feature HTML:
     <div class="digrow" data-id="42" onpointerdown="gStart(event, 42)">...</div>

   The page must define globally:
     - deleteItem(id)        called when swipe-left commits past 80 px
     - tapRow(id)            called on tap (no drag, < 8 px movement)

   Optional: longPress(id) — fired on a 500ms press with no drag.

   Optionally:
     - state.swipeShowcase = { id, dx }    forces a row into a frozen swipe state
                                            (used by catalog tiles · do not set in playground)
   ========================================================================== */

let drag = null;

function gStart(e, id) {
  if (e.pointerType === 'mouse' && e.button !== 0) return;
  const fg = e.currentTarget;
  fg.classList.remove('swipe-anim');
  closeAllRevealedExcept(fg);
  drag = {
    id, fg,
    startX: e.clientX, startY: e.clientY,
    axis: null, dx: 0, dy: 0,
    revealed: fg.dataset.revealed === 'true',
  };
  drag.lpTimer = setTimeout(() => {
    if (drag && drag.axis === null && Math.abs(drag.dx) < 8 && Math.abs(drag.dy) < 8) {
      if (typeof longPress === 'function') longPress(id);
      drag = null; // long-press consumes the gesture
    }
  }, 500);
}

function closeAllRevealedExcept(except) {
  document.querySelectorAll('.digrow[data-revealed="true"]').forEach(r => {
    if (r !== except) {
      r.classList.add('swipe-anim');
      r.style.transform = 'translateX(0)';
      r.dataset.revealed = 'false';
    }
  });
}

document.addEventListener('pointermove', e => {
  if (!drag) return;
  const dx = e.clientX - drag.startX;
  const dy = e.clientY - drag.startY;
  drag.dy = dy;
  if ((Math.abs(dx) > 8 || Math.abs(dy) > 8) && drag.lpTimer) { clearTimeout(drag.lpTimer); drag.lpTimer = null; }
  if (drag.axis === null) {
    if (Math.abs(dx) > 8 || Math.abs(dy) > 8) drag.axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
    if (drag.axis !== 'x') return;
  }
  if (drag.axis === 'x') {
    e.preventDefault();
    let dxClamped;
    if (drag.revealed && dx > 0) {
      // already revealed (right) · drag back left to close
      dxClamped = Math.max(0, Math.min(128, dx));
      drag.fg.style.transform = `translateX(${128 - dxClamped}px)`;
    } else {
      dxClamped = Math.max(-220, Math.min(160, dx));
      drag.fg.style.transform = `translateX(${dxClamped}px)`;
    }
    drag.dx = dx;
    drag.fg.classList.add('dragging');
  }
});

function gEnd() {
  if (!drag) return;
  if (drag.lpTimer) clearTimeout(drag.lpTimer);
  const fg = drag.fg, dx = drag.dx, id = drag.id;
  fg.classList.remove('dragging');
  fg.classList.add('swipe-anim');
  if (drag.axis === 'x') {
    if (dx < -80) {
      // commit delete · slide off-screen then call deleteItem
      fg.style.transform = 'translateX(-110%)';
      setTimeout(() => { if (typeof deleteItem === 'function') deleteItem(id); }, 170);
    } else if (dx > 60 && !drag.revealed) {
      // reveal right actions
      fg.style.transform = 'translateX(128px)';
      fg.dataset.revealed = 'true';
    } else if (drag.revealed && dx < -30) {
      // close revealed
      fg.style.transform = 'translateX(0)';
      fg.dataset.revealed = 'false';
    } else if (drag.revealed) {
      // stay revealed
      fg.style.transform = 'translateX(128px)';
    } else {
      // snap back
      fg.style.transform = 'translateX(0)';
    }
  } else if (drag.axis === null && Math.abs(drag.dx) < 8 && Math.abs(drag.dy) < 8) {
    // tap (no drag)
    if (typeof tapRow === 'function') tapRow(id);
  } else {
    fg.style.transform = 'translateX(0)';
  }
  drag = null;
}
document.addEventListener('pointerup', gEnd);
document.addEventListener('pointercancel', gEnd);
