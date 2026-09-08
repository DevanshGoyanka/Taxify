import { useState, type FormEvent, type ReactElement } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { authApi } from '../api/auth';
import { tokenManager } from '../api/tokenManager';
import { Spinner } from '../components/ui/Spinner';
import { useSeo } from '../hooks/useSeo';
import taxifyBlackLogo from '../../svgs/taxify black.png';
import googleIcon from '../../svgs/google-icon.svg';
import microsoftIcon from '../../svgs/microsoft.svg';
import './LoginPage.css';

interface SocialProvider {
  readonly name: string;
  readonly icon: string;
  readonly className: string;
}

const socialProviders: readonly SocialProvider[] = [
  { name: 'Google', icon: googleIcon, className: 'login-social-google' },
  { name: 'Microsoft', icon: microsoftIcon, className: 'login-social-microsoft' },
];

export default function LoginPage(): ReactElement {
  useSeo({
    title: 'Sign In',
    description:
      'Sign in to ITR Bharo to compute and file Indian income tax returns ITR-1 to ITR-4 for AY 2026-27.',
    path: '/login',
  });

  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const navigate = useNavigate();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setLoading(true);
    try {
      const data = await authApi.login(email, password);
      tokenManager.save(data.token, data.email);
      toast.success('Login successful!');
      navigate('/dashboard');
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Login failed';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const handleSocialLogin = (provider: string): void => {
    toast(`${provider} login is not configured yet.`);
  };

  return (
    <main className="login-page">
      <div className="login-background-shape login-background-shape-top" />
      <div className="login-background-shape login-background-shape-bottom" />

      <header className="login-brand" aria-label="Taxify">
        <img src={taxifyBlackLogo} alt="Taxify" />
      </header>

      <section className="login-card" aria-labelledby="login-heading">
        <h1 id="login-heading">Log in to Taxify</h1>

        <form onSubmit={handleSubmit}>
          <div className="login-field">
            <label htmlFor="login-email">Enter your email</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
              autoFocus
            />
          </div>

          <div className="login-field login-password-field">
            <label htmlFor="login-password">Password</label>
            <div className="login-password-wrap">
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
              />
              <button
                className="login-password-toggle"
                type="button"
                onClick={() => setShowPassword((visible) => !visible)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>

          <button
            className={`login-continue${email && password ? ' login-continue-ready' : ''}`}
            type="submit"
            disabled={loading || !email || !password}
          >
            {loading ? <Spinner size={16} /> : 'Log in'}
          </button>
        </form>

        <>
          <div className="login-divider" aria-hidden="true"><span /> <b>OR</b> <span /></div>
          <div className="login-social-list">
            {socialProviders.map((provider) => (
              <button
                className={`login-social ${provider.className}`}
                type="button"
                key={provider.name}
                onClick={() => handleSocialLogin(provider.name)}
              >
                <img className="login-social-icon" src={provider.icon} alt="" aria-hidden="true" />
                Continue with {provider.name}
              </button>
            ))}
          </div>
        </>

        <div className="login-links">
          <a href="/login" onClick={(event) => { event.preventDefault(); toast('Please contact support to recover your account.'); }}>Can't log in?</a>
          <span>·</span>
          <a href="/register">Create an account</a>
        </div>

        <div className="login-legal">
          <div className="login-legal-links">
            <a href="/privacy">Privacy Policy</a>
            <span>·</span>
            <a href="/terms">User Notice</a>
          </div>
          <p>This site is protected by reCAPTCHA and the Google <a href="https://policies.google.com/privacy">Privacy Policy</a> and <a href="https://policies.google.com/terms">Terms of Service</a> apply.</p>
        </div>
      </section>
    </main>
  );
}
