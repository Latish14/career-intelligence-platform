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

const ROLE_BARS = [
  { name: 'Data Scientist', val: 92 },
  { name: 'Backend Engineer', val: 84 },
  { name: 'Cyber Security Analyst', val: 78 },
  { name: 'Data Engineer', val: 71 }
];

const SKILL_ITEMS = [
  { label: 'Python', val: '94%' },
  { label: 'Kubernetes', val: '81%' },
  { label: 'LLM Engineering', val: '+210% YoY', highlight: true }
];

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

              <div className="landing-hero__grid">
                {/* Left: Hero Content */}
                <div className="landing-hero__content">
                  <p className="landing-hero__eyebrow">
                    For Students · Graduates · Career Switchers
                  </p>
                  <h1 className="landing-hero__title">
                    Career Decisions Backed By Real Market Data.
                  </h1>
                  <p className="landing-hero__description">
                    Upload your resume and discover which skills employers actually value,
                    where you stand today, and what to learn next.
                  </p>
                  
                  <div className="landing-hero__cta-wrapper">
                    <button className="landing-hero__cta" onClick={() => {
                      document.querySelector('.upload-section')?.scrollIntoView({ behavior: 'smooth' });
                    }}>
                      <span>Start Analysis</span>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="5" y1="12" x2="19" y2="12"></line>
                        <polyline points="12 5 19 12 12 19"></polyline>
                      </svg>
                    </button>
                    <p className="landing-hero__cta-hint">Built for students, graduates, and career switchers.</p>
                  </div>
                </div>

                {/* Right: Dashboard Mockup */}
                <div className="landing-hero__mockup-container">
                  <div className="dashboard-mockup">
                    {/* Stats Row */}
                    <div className="dashboard-mockup__stats">
                      <div className="dashboard-mockup__stat-card">
                        <div className="dashboard-mockup__stat-label">Market Fit Score</div>
                        <div className="dashboard-mockup__stat-value-container">
                          <span className="dashboard-mockup__stat-value">87/100</span>
                          <span className="dashboard-mockup__stat-change dashboard-mockup__stat-change--up">+5.2%</span>
                        </div>
                        <div className="dashboard-mockup__progress-bg">
                          <div className="dashboard-mockup__progress-bar" style={{ width: '87%' }} />
                        </div>
                      </div>
                      <div className="dashboard-mockup__stat-card">
                        <div className="dashboard-mockup__stat-label">Skill Coverage</div>
                        <div className="dashboard-mockup__stat-value-container">
                          <span className="dashboard-mockup__stat-value">73%</span>
                          <span className="dashboard-mockup__stat-change dashboard-mockup__stat-change--accent">+12 matched</span>
                        </div>
                        <div className="dashboard-mockup__progress-bg">
                          <div className="dashboard-mockup__progress-bar" style={{ width: '73%' }} />
                        </div>
                      </div>
                    </div>

                    {/* Career Matches */}
                    <div className="dashboard-mockup__section">
                      <div className="dashboard-mockup__section-header">
                        <h4>Top Career Matches</h4>
                        <span>Calculated Live</span>
                      </div>
                      <div className="dashboard-mockup__roles">
                        {ROLE_BARS.map(role => (
                          <div key={role.name} className="dashboard-mockup__role-item">
                            <div className="dashboard-mockup__role-info">
                              <span className="dashboard-mockup__role-name">{role.name}</span>
                              <span className="dashboard-mockup__role-match">{role.val}% match</span>
                            </div>
                            <div className="dashboard-mockup__progress-bg">
                              <div className="dashboard-mockup__progress-bar" style={{ width: `${role.val}%` }} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Trending Skills */}
                    <div className="dashboard-mockup__section">
                      <div className="dashboard-mockup__section-header">
                        <h4>Trending Skills</h4>
                        <span>Updated today</span>
                      </div>
                      <div className="dashboard-mockup__skills">
                        {SKILL_ITEMS.map(skill => (
                          <div key={skill.label} className={`dashboard-mockup__skill-item ${skill.highlight ? 'dashboard-mockup__skill-item--highlight' : ''}`}>
                            <span className="dashboard-mockup__skill-label">{skill.label}</span>
                            <span className="dashboard-mockup__skill-val">{skill.val}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
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
