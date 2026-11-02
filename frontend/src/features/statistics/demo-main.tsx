import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { DescriptiveDemo } from './DescriptiveDemo';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DescriptiveDemo />
  </StrictMode>,
);
