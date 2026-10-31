import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { compile } from 'json-schema-to-typescript';

const names = [
  'ResearchPackage',
  'ResearchHypothesis',
  'ResearchVariable',
  'DatasetReference',
  'AnalysisPlan',
  'AnalysisResult',
];
const output = new URL('../src/shared/contracts/generated/', import.meta.url);
await mkdir(output, { recursive: true });
for (const name of names) {
  const schema = JSON.parse(
    await readFile(
      new URL(`../../contracts/v1/${name}.schema.json`, import.meta.url),
      'utf8',
    ),
  );
  await writeFile(new URL(`${name}.ts`, output), await compile(schema, name));
}
