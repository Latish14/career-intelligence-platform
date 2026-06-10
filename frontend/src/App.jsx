import { ThemeProvider } from "./context/ThemeContext";
import ResumeUpload from "./components/ResumeUpload";
import ThemeToggle from "./components/ThemeToggle";
import "./App.css";

/* ── Static data for landing sections ─────────────────────────────────────── */



/* ── Network SVG Background ───────────────────────────────────────────────── */

function HeroNetworkSVG() {
  return (
    <svg
      className="landing-hero__network"
      width="320"
      height="320"
      viewBox="0 0 320 320"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path d="M 60 80 C 90 60, 140 100, 160 80" stroke="rgba(91,44,131,0.12)" strokeWidth="1.2" fill="none" />
      <path d="M 160 80 C 195 55, 240 90, 260 70" stroke="rgba(91,44,131,0.12)" strokeWidth="1.2" fill="none" />
      <path d="M 60 80 C 70 130, 100 160, 120 180" stroke="rgba(91,44,131,0.12)" strokeWidth="1.2" fill="none" />
      <path d="M 160 80 C 165 130, 155 160, 160 200" stroke="rgba(91,44,131,0.12)" strokeWidth="1.2" fill="none" />
      <path d="M 260 70 C 275 120, 265 170, 260 210" stroke="rgba(91,44,131,0.12)" strokeWidth="1.2" fill="none" />
      <path d="M 120 180 C 138 195, 152 198, 160 200" stroke="rgba(91,44,131,0.12)" strokeWidth="1.2" fill="none" />
      <path d="M 160 200 C 195 200, 230 205, 260 210" stroke="rgba(91,44,131,0.12)" strokeWidth="1.2" fill="none" />
      <path d="M 120 180 C 100 230, 140 270, 160 280" stroke="rgba(91,44,131,0.12)" strokeWidth="1.2" fill="none" />
      <path d="M 260 210 C 240 255, 205 275, 160 280" stroke="rgba(91,44,131,0.12)" strokeWidth="1.2" fill="none" />
      <circle cx="60" cy="80" r="7" fill="rgba(193,53,132,0.08)" stroke="rgba(91,44,131,0.12)" strokeWidth="1" />
      <circle cx="160" cy="80" r="9" fill="rgba(193,53,132,0.08)" stroke="rgba(91,44,131,0.12)" strokeWidth="1" />
      <circle cx="260" cy="70" r="6" fill="rgba(193,53,132,0.08)" stroke="rgba(91,44,131,0.12)" strokeWidth="1" />
      <circle cx="120" cy="180" r="8" fill="rgba(193,53,132,0.08)" stroke="rgba(91,44,131,0.12)" strokeWidth="1" />
      <circle cx="160" cy="200" r="10" fill="rgba(193,53,132,0.08)" stroke="rgba(91,44,131,0.12)" strokeWidth="1.2" />
      <circle cx="260" cy="210" r="7" fill="rgba(193,53,132,0.08)" stroke="rgba(91,44,131,0.12)" strokeWidth="1" />
      <circle cx="160" cy="280" r="6" fill="rgba(193,53,132,0.08)" stroke="rgba(91,44,131,0.12)" strokeWidth="1" />
    </svg>
  );
}

/* ── Main App ─────────────────────────────────────────────────────────────── */

function App() {
  return (
    <ThemeProvider>
      <div className="app">
        <header className="app-header">
          <div className="app-header__inner">
            <div className="app-header__brand">
              <img src="/logo.png" alt="Career IQ Logo" className="app-header__logo" />
              <div>
                <div className="app-header__title">
                  CAREER IQ
                </div>
              </div>
            </div>
            <ThemeToggle />
          </div>
        </header>

        <main className="app-main">
          <div className="app-main__inner">
            {/* ── Landing Hero ──────────────────────────────────────── */}
            <section className="landing-hero">
              <div className="landing-hero__glow" aria-hidden="true" />
              <div className="landing-hero__grain" aria-hidden="true" />
              <HeroNetworkSVG />

              <div className="landing-hero__content">
                <p className="landing-hero__eyebrow">
                  For Students · Graduates · Career Switchers
                </p>
                <h1 className="landing-hero__title">
                  See Your Career Through The Market&apos;s Eyes.
                </h1>
                <p className="landing-hero__description">
                  Upload your resume and discover which skills employers value,
                  where you stand today, and what to learn next.
                </p>
              </div>
            </section>

            {/* ── Upload (existing component, untouched) ───────────── */}
            <ResumeUpload />


          </div>
        </main>

        {/* ── Footer ─────────────────────────────────────────────── */}
        <footer className="landing-footer">
          <div className="landing-footer__bottom">
            <p className="landing-footer__copyright" style={{ textAlign: "center", width: "100%" }}>
              © {new Date().getFullYear()} CAREER IQ. All rights reserved.
            </p>
          </div>
        </footer>
      </div>
    </ThemeProvider>
  );
}

export default App;
