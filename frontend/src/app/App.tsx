import { useEffect, useState } from 'react';
import { getHealth } from '../shared/api/health';

type Connection = {
  state: 'loading' | 'error' | 'connected';
  version?: string;
};

export function App() {
  const [connection, setConnection] = useState<Connection>({
    state: 'loading',
  });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then((health) => {
        if (!controller.signal.aborted)
          setConnection({ state: 'connected', version: health.version });
      })
      .catch(() => {
        if (!controller.signal.aborted) setConnection({ state: 'error' });
      });
    return () => controller.abort();
  }, [attempt]);

  return (
    <main>
      <header>
        <a href="/" aria-label="TesisStat AI, inicio">
          TesisStat <strong>AI</strong>
        </a>
        <span>Sesión 01 · Base compartida</span>
      </header>
      <section className="intro">
        <p className="eyebrow">INVESTIGACIÓN CUANTITATIVA</p>
        <h1>
          Tu investigación,
          <br />
          <em>con fundamento.</em>
        </h1>
        <p className="lead">
          Un espacio para conectar la metodología de tu tesis con un análisis
          estadístico claro, trazable y justificado.
        </p>
      </section>
      <section className="connection" aria-labelledby="connection-title">
        <div>
          <p className="eyebrow">ESTADO DEL SISTEMA</p>
          <h2 id="connection-title">Conexión con el backend</h2>
          <p role="status" aria-live="polite">
            {connection.state === 'loading' && 'Verificando la conexión…'}
            {connection.state === 'connected' &&
              `Backend conectado · API v${connection.version}`}
            {connection.state === 'error' &&
              'No se pudo conectar. Comprueba que el backend esté en ejecución y revisa la configuración de CORS.'}
          </p>
        </div>
        <button
          onClick={() => {
            setConnection({ state: 'loading' });
            setAttempt((value) => value + 1);
          }}
          disabled={connection.state === 'loading'}
        >
          Verificar conexión
        </button>
      </section>
      <section className="modules" aria-label="Módulos en preparación">
        <article>
          <span className="number">01 / RESEARCH</span>
          <h2>Comprender tu investigación</h2>
          <p>Proyectos, documentos, instrumentos y preparación de datos.</p>
          <span className="badge">En preparación</span>
        </article>
        <article>
          <span className="number">02 / STATISTICS</span>
          <h2>Analizar con criterio</h2>
          <p>Planificación estadística, resultados verificables e informes.</p>
          <span className="badge">En preparación</span>
        </article>
      </section>
      <footer>
        Los módulos funcionales se implementarán en las siguientes sesiones.
        Esta pantalla verifica la base técnica compartida.
      </footer>
    </main>
  );
}
