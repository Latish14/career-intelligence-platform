import { ThemeProvider } from "./context/ThemeContext";
import ResumeUpload from "./components/ResumeUpload";
import ThemeToggle from "./components/ThemeToggle";

function App() {
  return (
    <ThemeProvider>
      <div className="app">
        <header className="app-header">
          <div className="app-header__inner">
            <div className="app-header__brand">
              <div className="app-header__logo" aria-hidden="true">
                CIP
              </div>
              <div>
                <div className="app-header__title">
                  Career Intelligence Platform
                </div>
                <div className="app-header__subtitle">
                  AI-powered career insights
                </div>
              </div>
            </div>
            <ThemeToggle />
          </div>
        </header>

        <main className="app-main">
          <div className="app-main__inner">
            <ResumeUpload />
          </div>
        </main>
      </div>
    </ThemeProvider>
  );
}

export default App;
