import { APP_NAME } from "./constants";

export function App() {
  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="brand" aria-label={APP_NAME}>
          <img src={`${import.meta.env.BASE_URL}brand/portflow-mark.png`} alt="" />
          <span>{APP_NAME}</span>
        </div>
        <div className="title-region">
          <h1>Terminal Operations Control Tower</h1>
          <p>Simulated terminal operations data</p>
        </div>
      </header>
    </main>
  );
}
