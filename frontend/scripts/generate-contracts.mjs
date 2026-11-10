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
const v2Output = new URL('v2/', output);
await mkdir(v2Output, { recursive: true });
for (const name of [
  'ProjectContextV2',
  'ContextImport',
  'ContextSuggestion',
  'SuggestionCreate',
  'SuggestionApply',
  'AnalysisIntentV2',
  'DiagnosticV2',
  'IntentPatch',
  'DiagnosticRequest',
  'AnalysisSnapshotV2',
  'SourceFileV2',
  'SourceSheetV2',
  'ImportedTableV2',
  'TableContextV2',
  'TablePreviewV2',
  'DatasetRefV2',
  'VariableDictionaryV2',
  'TableProfileV2',
  'TableRecipeV2',
  'PreparationPreviewV2',
  'DerivedTableV2',
]) {
  const schema = JSON.parse(
    await readFile(
      new URL(`../../contracts/v2/${name}.schema.json`, import.meta.url),
      'utf8',
    ),
  );
  await writeFile(new URL(`${name}.ts`, v2Output), await compile(schema, name));
}
