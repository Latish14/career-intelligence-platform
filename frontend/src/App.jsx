// frontend/src/App.jsx

import ResumeUpload from "./components/ResumeUpload";

function App() {
  return (
    <main
      style={{
        minHeight: "100vh",
        padding: "2rem",
      }}
    >
      <h1
        style={{
          textAlign: "center",
          marginBottom: "2rem",
        }}
      >
        Career Intelligence Platform
      </h1>

      <ResumeUpload />
    </main>
  );
}

export default App;