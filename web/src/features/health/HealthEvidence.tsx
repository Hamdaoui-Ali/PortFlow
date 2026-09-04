import type { HealthViewModel } from "./healthPresentation";

export function HealthEvidence({ model }: { model: HealthViewModel }) {
  return (
    <>
      <section className="health-evidence-grid" aria-label="Pipeline and reconciliation evidence">
        <div className="health-evidence-card">
          <p className="section-kicker">Pipeline</p>
          <h2>Pipeline status</h2>
          <p className="health-evidence-value">{model.pipelineStatus}</p>
          <p>dbt quality checks for the published snapshot.</p>
        </div>
        <div className="health-evidence-card">
          <p className="section-kicker">Reconciliation</p>
          <h2>Layer counts</h2>
          <p>{model.reconciliation.layers}</p>
          <p>{model.reconciliation.reasons}</p>
        </div>
      </section>

      <section className="health-rejections" aria-labelledby="health-rejections-title">
        <h2 id="health-rejections-title">Rejection reasons</h2>
        <div className="health-table-scroll">
          <table aria-describedby="health-rejections-title">
            <caption>Rejection reasons and rejected records</caption>
            <thead>
              <tr><th scope="col">Reason</th><th scope="col">Rejected records</th></tr>
            </thead>
            <tbody>
              {model.rejections.rows.length ? model.rejections.rows.map((row) => (
                <tr key={row.reason}><th scope="row">{row.reason}</th><td>{row.count}</td></tr>
              )) : (
                <tr><td colSpan={2}>{model.rejections.emptyMessage.replace(/\.$/, "")}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <details className="health-rules">
        <summary>Quality rules and documentation</summary>
        <p>{model.rules.staleAfter}</p>
        <p>{model.rules.layerCounts}</p>
        <p>{model.rules.rejectionTotals}</p>
        <p><a href="https://github.com/Hamdaoui-Ali/PortFlow/blob/main/docs/design/PORTFLOW_UI_SPEC.md">PortFlow UI specification</a></p>
        <p><a href="https://github.com/Hamdaoui-Ali/PortFlow">PortFlow source repository</a></p>
      </details>
    </>
  );
}
