import { useEffect, useState } from 'react';
import { Link, Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom';
import { api, validateFile } from './api.js';

function ErrorMessage({ message }) {
  return message ? <div className="error" role="alert">{message}</div> : null;
}

function TextField({ label, name, ...props }) {
  return <label className="field" htmlFor={name}>
    <span>{label}</span>
    <input id={name} name={name} required {...props} />
  </label>;
}

function FileField({ required = false }) {
  return <label className="field" htmlFor="file">
    <span>Text file {required ? '' : <small>(optional)</small>}</span>
    <input id="file" name="file" type="file" accept=".txt,text/plain" required={required} />
    <small>Choose your assignment’s Limerick (1).txt. UTF-8 text, up to 1 MB.</small>
  </label>;
}

function Register({ session, setSession }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  async function submit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError('');
    setBusy(true);
    try {
      validateFile(form.get('file'));
      const data = await api('/register', { method: 'POST', body: form, csrfToken: session.csrf_token });
      setSession(data);
      navigate('/profile', { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return <section className="card" aria-labelledby="register-title">
    <h1 id="register-title">Create your account</h1>
    <p className="intro">Add your details. You can view them again whenever you sign in.</p>
    <ErrorMessage message={error} />
    <form onSubmit={submit}>
      <fieldset disabled={busy}>
        <TextField label="Username" name="username" autoComplete="username" minLength={3} maxLength={30}
          pattern="[A-Za-z0-9_.\-]{3,30}" title="3–30 letters, numbers, dots, dashes, or underscores" />
        <TextField label="Password" name="password" type="password" autoComplete="new-password" minLength={8} maxLength={128} />
        <p className="hint">Use at least 8 characters.</p>
        <div className="two-columns">
          <TextField label="First name" name="first_name" autoComplete="given-name" maxLength={100} />
          <TextField label="Last name" name="last_name" autoComplete="family-name" maxLength={100} />
        </div>
        <TextField label="Email" name="email" type="email" autoComplete="email" maxLength={254} />
        <label className="field" htmlFor="address">
          <span>Address</span>
          <textarea id="address" name="address" autoComplete="street-address" required maxLength={500} rows={2} />
        </label>
        <FileField />
        <button className="button full-width" type="submit">{busy ? 'Creating account…' : 'Create account'}</button>
      </fieldset>
    </form>
    <p className="footnote">Already registered? <Link to="/login">Sign in</Link></p>
  </section>;
}

function Login({ session, setSession }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  async function submit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError('');
    setBusy(true);
    try {
      const data = await api('/login', {
        method: 'POST', csrfToken: session.csrf_token,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: form.get('username'), password: form.get('password') }),
      });
      setSession(data);
      navigate('/profile', { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return <section className="card" aria-labelledby="login-title">
    <h1 id="login-title">Welcome back</h1>
    <p className="intro">Sign in to see your saved details and text file.</p>
    <ErrorMessage message={error} />
    <form onSubmit={submit}>
      <fieldset disabled={busy}>
        <TextField label="Username" name="username" autoComplete="username" maxLength={30} />
        <TextField label="Password" name="password" type="password" autoComplete="current-password" maxLength={128} />
        <button className="button full-width" type="submit">{busy ? 'Signing in…' : 'Sign in'}</button>
      </fieldset>
    </form>
    <p className="footnote">New here? <Link to="/register">Create an account</Link></p>
  </section>;
}

function Profile({ session, setSession }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const { user } = session;
  const navigate = useNavigate();

  async function logout() {
    setError('');
    setBusy(true);
    try {
      setSession(await api('/logout', { method: 'POST', csrfToken: session.csrf_token }));
      navigate('/login', { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function upload(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setError('');
    setNotice('');
    setBusy(true);
    try {
      validateFile(form.get('file'));
      const data = await api('/upload', { method: 'POST', body: form, csrfToken: session.csrf_token });
      setSession((previous) => ({ ...previous, user: data.user }));
      formElement.reset();
      setNotice('Your file has been saved.');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return <section className="card" aria-labelledby="profile-title">
    <div className="profile-heading">
      <div><p className="eyebrow">YOUR ACCOUNT</p><h1 id="profile-title">Hello, {user.first_name}</h1></div>
      <button type="button" className="button secondary" onClick={logout} disabled={busy}>Sign out</button>
    </div>
    <p className="intro">Your details are saved. Sign out and sign back in to retrieve them.</p>
    <ErrorMessage message={error} />
    <dl className="details">
      {[
        ['Username', user.username], ['First name', user.first_name], ['Last name', user.last_name],
        ['Email', user.email], ['Address', user.address],
      ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
    </dl>
    <div className="file-section">
      <h2>Your text file</h2>
      {user.upload ? <div className="saved-file">
        <p className="filename">{user.upload.filename}</p>
        <p className="word-count"><strong>{user.upload.word_count.toLocaleString()}</strong> words</p>
        <a className="button secondary" href="/api/download" download>Download file</a>
      </div> : <p className="muted">No file uploaded yet. Add your text file below.</p>}
      <form onSubmit={upload}>
        <fieldset disabled={busy}>
          <FileField required />
          <button type="submit" className="button">{busy ? 'Please wait…' : user.upload ? 'Replace file' : 'Upload file'}</button>
        </fieldset>
      </form>
      {notice && <p className="success" role="status">{notice}</p>}
      <p className="hint">Words are counted by separating text at spaces and line breaks.</p>
    </div>
  </section>;
}

export default function App() {
  const [session, setSession] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    api('/session', { signal: controller.signal }).then((data) => { if (active) setSession(data); })
      .catch(() => { if (active) setError('Unable to connect. Check that the server is running, then reload this page.'); });
    return () => { active = false; controller.abort(); };
  }, []);

  const props = { session, setSession };
  return <>
    <header className="site-header">
      <Link className="brand" to={session?.user ? '/profile' : '/register'}>Simple Auth</Link>
      <nav aria-label="Main navigation">
        {session?.user ? <NavLink to="/profile">My profile</NavLink> : <>
          <NavLink to="/register">Register</NavLink><NavLink to="/login">Sign in</NavLink>
        </>}
      </nav>
    </header>
    <main>
      {error ? <section className="card"><ErrorMessage message={error} /><button className="button secondary" onClick={() => window.location.reload()}>Reload page</button></section>
        : !session ? <section className="card" role="status">Loading…</section>
        : <Routes>
          <Route path="/register" element={session.user ? <Navigate to="/profile" replace /> : <Register {...props} />} />
          <Route path="/login" element={session.user ? <Navigate to="/profile" replace /> : <Login {...props} />} />
          <Route path="/profile" element={session.user ? <Profile {...props} /> : <Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to={session.user ? '/profile' : '/register'} replace />} />
        </Routes>}
    </main>
    <footer>Simple registration, saved details, and your text file.</footer>
  </>;
}
