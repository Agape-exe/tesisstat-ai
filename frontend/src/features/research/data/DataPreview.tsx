export function DataPreview({
  names,
  rows,
}: {
  names: string[];
  rows: (string | null)[][];
}) {
  return (
    <div
      className="rp-dataset-scroll"
      tabIndex={0}
      role="region"
      aria-label="Vista previa de valores"
    >
      <table>
        <thead>
          <tr>
            {names.map((n, i) => (
              <th key={i} scope="col">
                {n}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j}>
                  {cell === null ? (
                    <span className="rp-hint">Sin valor</span>
                  ) : cell === '' ? (
                    <span className="rp-hint">Vacío</span>
                  ) : (
                    cell
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
