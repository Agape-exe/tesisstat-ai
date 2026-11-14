import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { ResearchProjects } from './projects/ResearchProjects';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ResearchProjects />
  </StrictMode>,
);
