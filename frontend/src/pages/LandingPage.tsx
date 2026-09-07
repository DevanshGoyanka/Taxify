import { useState, type ReactElement } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import taxifyBlackLogo from '../../svgs/taxify black.png';
import './LandingPage.css';

export default function LandingPage(): ReactElement {
  const navigate = useNavigate();
  const [signUpClicked, setSignUpClicked] = useState<boolean>(false);

  const handleSignUp = (): void => {
    setSignUpClicked(true);
    window.setTimeout(() => navigate('/login'), 500);
  };

  return (
    <div className="landing-page">
      <nav className="landing-navbar" aria-label="Main navigation">
        <Link className="landing-brand" to="/" aria-label="Taxify home">
          <img src={taxifyBlackLogo} alt="Taxify" />
        </Link>
        <div className="landing-nav-actions">
          <a href="#about-us">About us</a>
          <a href="#pricing">Pricing</a>
          <Link className="landing-login-button" to="/login">
            Login
          </Link>
        </div>
      </nav>

      <main>
        <section className="landing-hero" aria-labelledby="landing-title">
          <div className="landing-hero-content">
            <h1 id="landing-title">
              Taxi<span className={`landing-hero-f${signUpClicked ? ' landing-hero-f-selected' : ''}`}>f</span>y
            </h1>
            <p className="landing-tagline">
              Taxify automates the filing process, turning hours of manual work into a few simple clicks.
            </p>
            <div className="landing-hero-actions">
              <a className="landing-talk-button" href="mailto:hello@taxify.com">
                Talk with us
              </a>
              <button className="landing-cta" type="button" onClick={handleSignUp} aria-label="Sign up for Taxify">
                Sign up
              </button>
            </div>
          </div>
        </section>

        <section className="landing-about" id="about-us" aria-labelledby="about-title">
          <div className="landing-about-inner">
            <p className="landing-eyebrow">About Taxify</p>
            <h2 id="about-title">A focused workspace for confident filing.</h2>
            <p>
              Taxify brings client information, income details, deductions, review,
              and filing preparation together in one organized workspace for tax
              professionals.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
