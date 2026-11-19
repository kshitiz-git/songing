// /login and /signup (same form shell)
import { h } from '../dom.js';
import { api, ApiError } from '../api.js';
import { store, setUser, refreshPlaylists } from '../store.js';
import { navigate, safeNext } from '../router.js';
import { field, showErrors, formError } from '../ui/form.js';
import { toast } from '../ui/toast.js';

// Already logged in: go straight to the target.
export async function load(ctx) {
  if (store.user) await navigate(safeNext(ctx.query.get('next')), { replace: true });
}

export function render(_data, ctx) {
  const signup = ctx.name === 'signup';
  const rawNext = ctx.query.get('next');
  const next = safeNext(rawNext);
  const nextQuery = rawNext && next !== '/' ? `?next=${encodeURIComponent(next)}` : '';
  ctx.setTitle(signup ? 'Sign up' : 'Log in');

  const username = field({
    label: 'Username',
    control: h('input', { type: 'text', name: 'username', required: true, maxlength: 150, autocomplete: 'username', autocapitalize: 'none', spellcheck: 'false' }),
  });
  const email = signup
    ? field({ label: 'Email (optional)', control: h('input', { type: 'email', name: 'email', autocomplete: 'email', maxlength: 254 }) })
    : null;
  const password = field({
    label: 'Password',
    hint: signup ? 'At least 8 characters. Not a common password, not all digits.' : '',
    control: h('input', { type: 'password', name: 'password', required: true, autocomplete: signup ? 'new-password' : 'current-password' }),
  });
  const fields = { username, password, ...(email ? { email } : {}) };
  const err = formError();
  const submit = h('button', { type: 'submit', class: 'btn btn-accent btn-lg', text: signup ? 'Create account' : 'Log in' });

  const form = h('form', { class: 'form', novalidate: true }, err.el, username.el, email && email.el, password.el, submit);
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    err.set('');
    for (const f of Object.values(fields)) f.setError('');
    if (!username.control.value.trim()) {
      username.setError('Enter your username.');
      username.control.focus();
      return;
    }
    if (!password.control.value) {
      password.setError('Enter your password.');
      password.control.focus();
      return;
    }
    const body = { username: username.control.value.trim(), password: password.control.value };
    if (signup && email.control.value.trim()) body.email = email.control.value.trim();
    submit.disabled = true;
    try {
      const data = await api(signup ? '/api/auth/signup/' : '/api/auth/login/', { method: 'POST', body });
      setUser(data.user);
      await refreshPlaylists();
      toast(signup ? `Welcome to Songing, ${data.user.username}` : `Welcome back, ${data.user.username}`);
      navigate(next, { replace: true });
    } catch (ex) {
      submit.disabled = false;
      if (ex instanceof ApiError && ex.status === 429) {
        const detail = ex.data && typeof ex.data.detail === 'string' ? ex.data.detail : '';
        err.set(`Too many attempts. ${detail || 'Wait a minute and try again.'}`);
        return;
      }
      err.set(showErrors(fields, ex));
      const bad = form.querySelector('[aria-invalid="true"]');
      if (bad) bad.focus();
    }
  });

  const other = signup
    ? h('p', { class: 'form-switch' }, 'Already have an account? ', h('a', { href: `/login${nextQuery}`, text: 'Log in' }))
    : h('p', { class: 'form-switch' }, 'New to Songing? ', h('a', { href: `/signup${nextQuery}`, text: 'Sign up' }));

  setTimeout(() => username.control.focus(), 0);
  return h(
    'div',
    { class: 'auth-card' },
    h('h1', { class: 'auth-title', text: signup ? 'Create your Songing account' : 'Log in to Songing' }),
    form,
    other,
  );
}
