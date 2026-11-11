/*
 * HyperAdmin inline cell editing keyboard and pointer behaviour.
 *
 * The editor (components/inline_editor.html) shows no Save or Cancel buttons:
 *   - Enter saves (a no-op edit just closes);
 *   - Escape cancels and discards;
 *   - a click outside the editor closes it when nothing changed, and asks
 *     Save or Discard when something did.
 * "Changed" compares each control with its server-rendered default, so it is
 * exact: typing a value and typing it back is not a change. An editor that
 * came back from a failed save (data-inline-dirty) always counts as changed,
 * so the rejected input is never thrown away by a stray click.
 * The hidden Save and Cancel buttons stay in the form; this script clicks them.
 */
(function () {
  'use strict';
  var FORM = '.ha-inline-form';
  var script = document.currentScript;
  var dialog = null;

  function changed(form) {
    if (form.hasAttribute('data-inline-dirty')) return true;
    return [].some.call(form.elements, function (el) {
      if (el.type === 'hidden' || el.type === 'submit' || el.type === 'button') return false;
      if (el.type === 'checkbox' || el.type === 'radio') return el.checked !== el.defaultChecked;
      if (el.tagName === 'SELECT') {
        return [].some.call(el.options, function (o) { return o.selected !== o.defaultSelected; });
      }
      return el.value !== el.defaultValue;
    });
  }

  function cancel(form) {
    var btn = form.querySelector('[data-inline-cancel]');
    if (!btn) return;
    if (window.htmx) window.htmx.process(form);
    btn.click();
  }

  function save(form) {
    // A just-swapped editor may not be processed by htmx yet; without this the
    // submit would fall back to a native GET.
    if (window.htmx) window.htmx.process(form);
    if (form.requestSubmit) form.requestSubmit(); else form.submit();
  }

  function ask(form) {
    if (dialog && dialog.open) return;
    if (!dialog) {
      dialog = document.createElement('dialog');
      dialog.className = 'ha-dialog ha-inline-confirm';
      dialog.setAttribute('data-testid', 'dialog-inline-discard');
      dialog.innerHTML =
        '<div class="ha-inline-confirm__body">' +
        '<p class="ha-inline-confirm__title"></p>' +
        '<div class="ha-inline-confirm__actions">' +
        '<button type="button" class="ha-btn ha-btn-primary" data-act="save" data-testid="inline-confirm-save"></button>' +
        '<button type="button" class="ha-btn ha-btn-link" data-act="discard" data-testid="inline-confirm-discard"></button>' +
        '</div></div>';
      dialog.querySelector('p').textContent = script.getAttribute('data-title') || 'Save your change?';
      dialog.querySelector('[data-act=save]').textContent = script.getAttribute('data-save') || 'Save';
      dialog.querySelector('[data-act=discard]').textContent = script.getAttribute('data-discard') || 'Discard';
      document.body.appendChild(dialog);
      dialog.addEventListener('click', function (e) {
        var act = e.target.getAttribute && e.target.getAttribute('data-act');
        if (!act) return;
        var f = dialog.haForm;
        dialog.close();
        if (!f || !f.isConnected) return;
        if (act === 'save') save(f); else cancel(f);
      });
    }
    dialog.haForm = form;
    dialog.showModal();
    dialog.querySelector('[data-act=save]').focus();
  }

  document.addEventListener('keydown', function (e) {
    var form = e.target.closest && e.target.closest(FORM);
    if (!form || e.isComposing) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      cancel(form);
    } else if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA' && e.target.tagName !== 'BUTTON') {
      e.preventDefault();
      if (changed(form)) save(form); else cancel(form);
    }
  });

  document.addEventListener('mousedown', function (e) {
    var open = document.querySelector(FORM);
    if (!open || !e.target.closest) return;
    if (open.contains(e.target) || (dialog && dialog.contains(e.target))) return;
    if (dialog && dialog.open) return;
    if (changed(open)) ask(open); else cancel(open);
  });
})();
