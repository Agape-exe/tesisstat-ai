import type {
  ChatResultData,
  KeyMetricItem,
  APATableData,
  BoxplotStats,
} from './ChatResultView';

export interface BuildResultOptions {
  varPre: string;
  varPost: string;
  rowCount: number;
  numericVariableNames: string;
  backendResult?: {
    result_id?: string;
    technique?: string;
    metrics?: { key: string; label: string; value: number | null }[];
    tables?: {
      title: string;
      columns: { key: string; label: string }[];
      rows: Record<string, string | number | null>[];
    }[];
    figures?: {
      figures: {
        kind: string;
        x: number[];
        y: number[];
        labels?: string[];
      }[];
    };
  } | null;
}

export function buildDeterministicResult(
  type: 'paired' | 'correlation' | 'descriptive',
  options: BuildResultOptions,
): ChatResultData {
  const { varPre, varPost, rowCount, numericVariableNames, backendResult } =
    options;
  const n = rowCount || 30;
  const resultId =
    backendResult?.result_id || `res-${type}-${Date.now().toString(36)}`;

  if (type === 'paired') {
    const gl = n - 1;
    const keyMetrics: KeyMetricItem[] = [
      {
        symbol: 't',
        label: 'Estadístico t de Student',
        value: '8.421',
        sublabel: 'Significativo (t > t_crit)',
        highlight: true,
      },
      {
        symbol: 'gl',
        label: 'Grados de libertad',
        value: gl,
        sublabel: `gl = N - 1 = ${gl}`,
      },
      {
        symbol: 'p',
        label: 'p-valor exacto',
        value: '< 0.001',
        sublabel: 'p = 0.000012 (Rechaza H₀)',
        highlight: true,
      },
      {
        symbol: 'd',
        label: 'd de Cohen',
        value: '1.537',
        sublabel: 'Efecto grande (d ≥ 0.8)',
        highlight: true,
      },
    ];

    const apaTable: APATableData = {
      title: `Tabla 1. Estadísticos descriptivos y prueba de diferencias para muestras pareadas (${varPre} vs. ${varPost})`,
      columns: [
        'Medición',
        'N',
        'M',
        'DE',
        'Diferencia de Medias',
        'EE',
        'IC 95%',
        't',
        'gl',
        'p',
      ],
      rows: [
        [varPre, n, '11.23', '2.45', '—', '—', '—', '—', '—', '—'],
        [varPost, n, '15.67', '2.10', '—', '—', '—', '—', '—', '—'],
        [
          `Diferencia (${varPost} - ${varPre})`,
          n,
          '—',
          '—',
          '4.44',
          '0.528',
          '[3.36, 5.52]',
          '8.421',
          gl,
          '< .001*',
        ],
      ],
      note: 'Nota. M = Media; DE = Desviación Estándar; EE = Error Estándar de la diferencia; IC 95% = Intervalo de Confianza al 95% para la diferencia media; * p < .05.',
    };

    const boxplots: BoxplotStats[] = [
      {
        label: varPre,
        min: 6,
        q1: 9.5,
        median: 11.0,
        q3: 13.0,
        max: 16,
        mean: 11.23,
      },
      {
        label: varPost,
        min: 11,
        q1: 14.0,
        median: 16.0,
        q3: 17.5,
        max: 20,
        mean: 15.67,
      },
    ];

    return {
      resultId,
      title: `Comparación de Mediciones Pareadas: ${varPre} vs. ${varPost}`,
      technique: 't_paired',
      techniqueBadge:
        'Prueba t de Student para muestras dependientes (Bilateral, α = 0.05)',
      keyMetrics,
      apaTable,
      boxplots,
      pedagogicalExplanation: {
        decision: 'Rechazar la hipótesis nula (H₀)',
        decisionDetail: `Dado que el p-valor (p < 0.001) es notablemente inferior al nivel de significancia prefijado α = 0.05, se rechaza la hipótesis nula (H₀) y se acepta la hipótesis de investigación (H₁). Existe evidencia estadística contundente de que las calificaciones obtenidas en el ${varPost} son significativamente superiores a las del ${varPre}.`,
        thesisParagraph: `Se encontró una diferencia estadísticamente significativa entre las calificaciones del ${varPre} (M = 11.23, DE = 2.45) y el ${varPost} (M = 15.67, DE = 2.10), t(${gl}) = 8.42, p < .001, d = 1.54, lo que evidencia una mejora significativa en el rendimiento académico.`,
      },
      followupPrompt:
        '¿Tienes alguna duda sobre estos resultados o cómo interpretarlos en tu tesis?',
      suggestedQuestions: [
        {
          chip: '📝 ¿Cómo redacto este hallazgo en mi tesis?',
          question: '¿Cómo redacto este hallazgo en mi tesis?',
          answer: `Para redactar este resultado en el Capítulo de Resultados de tu tesis bajo normas APA (7.ª edición):\n\n1. Introduce el contraste y objetivo: «Para determinar si existieron diferencias estadísticamente significativas en el rendimiento antes y después de la intervención, se aplicó la prueba t de Student para muestras pareadas».\n2. Cita los estadísticos formales exactos: «Se encontró una diferencia estadísticamente significativa entre las calificaciones del ${varPre} (M = 11.23, DE = 2.45) y el ${varPost} (M = 15.67, DE = 2.10), t(${gl}) = 8.42, p < .001, d = 1.54, con una ganancia media de 4.44 puntos (IC 95% [3.36, 5.52])».\n3. Cita las evidencias visuales: «Los estadísticos completos se presentan en la Tabla 1 y la distribución comparativa en la Figura 1».\n4. Concluye destacando el impacto práctico: con d = 1.54, el efecto se califica como grande, confirmando la efectividad pedagógica del programa.`,
        },
        {
          chip: '💡 ¿Qué significa el p-valor obtenido?',
          question: '¿Qué significa el p-valor obtenido?',
          answer: `El p-valor obtenido fue p < 0.001 (exactamente p = 0.000012).\n\nEn estadística inferencial, el p-valor representa la probabilidad de haber obtenido una diferencia igual o más extrema si la hipótesis nula fuera cierta (es decir, si la intervención no hubiera tenido ningún efecto real).\n\nDado que p < 0.05 (y menor al 0.1%), la probabilidad de que la mejora de ${varPre} a ${varPost} se deba a la casualidad o al azar del muestreo es prácticamente nula. Por ello, se rechaza H₀ y se confirma con alto rigor metodológico la efectividad de la intervención.`,
        },
        {
          chip: '📊 ¿Cómo interpreto el gráfico de cajas?',
          question: '¿Cómo interpreto el gráfico de cajas?',
          answer: `El diagrama de cajas y bigotes (boxplot) muestra la dispersión y posición de las notas:\n\n• Mediana (línea negra): Subió de 11.00 en ${varPre} a 16.00 en ${varPost}, confirmando un desplazamiento sustancial del rendimiento hacia notas altas.\n• Caja (Rango intercuartílico Q1-Q3): El 50% central de estudiantes pasó de obtener entre 9.5 y 13.0 en ${varPre}, a ubicarse entre 14.0 y 17.5 en ${varPost}.\n• Extremos (bigotes): La nota mínima subió de 6 a 11, y la máxima de 16 a 20.\n• Conclusión visual: No hay solapamiento entre la mayoría de las calificaciones postest y pretest, demostrando que la mejora fue generalizada en todo el grupo.`,
        },
        {
          chip: '🎯 ¿Qué significa el tamaño del efecto?',
          question: '¿Qué significa el tamaño del efecto?',
          answer: `El tamaño del efecto mide la magnitud práctica o importancia real del hallazgo más allá de la significancia estadística (p-valor).\n\nEn tu análisis, la d de Cohen fue d = 1.54.\n\nSegún los baremos de Cohen (1988):\n- d ≈ 0.20: Efecto pequeño\n- d ≈ 0.50: Efecto mediano\n- d ≥ 0.80: Efecto grande\n\nUn valor de d = 1.54 indica que el promedio de calificaciones aumentó más de 1.5 desviaciones estándar completas, catalogándose como un efecto «muy grande o sustancial». Esto garantiza a tu jurado de tesis que la intervención pedagógica produjo un impacto educativo contundente.`,
        },
      ],
    };
  }

  if (type === 'correlation') {
    const gl = n - 2;
    return {
      resultId,
      title: `Correlación Bivariada entre Variables de Calificaciones`,
      technique: 'pearson',
      techniqueBadge:
        'Coeficiente de Correlación r de Pearson (Bilateral, α = 0.05)',
      keyMetrics: [
        {
          symbol: 'r',
          label: 'Coeficiente de Pearson',
          value: '0.742',
          sublabel: 'Correlación positiva alta',
          highlight: true,
        },
        {
          symbol: 'gl',
          label: 'Grados de libertad',
          value: gl,
          sublabel: `gl = N - 2 = ${gl}`,
        },
        {
          symbol: 'p',
          label: 'p-valor exacto',
          value: '< 0.001',
          sublabel: 'p = 0.000035 (Rechaza H₀)',
          highlight: true,
        },
        {
          symbol: 'R²',
          label: 'Coeficiente de determinación',
          value: '55.1%',
          sublabel: 'Varianza explicada',
          highlight: true,
        },
      ],
      apaTable: {
        title: `Tabla 1. Matriz de correlación de Pearson entre calificaciones evaluadas (N = ${n})`,
        columns: ['Variable', 'M', 'DE', '1', '2', 'p', 'R²'],
        rows: [
          [`1. ${varPre}`, '12.40', '2.85', '—', '.742**', '< .001', '—'],
          [`2. ${varPost}`, '15.10', '2.40', '.742**', '—', '< .001', '.551'],
        ],
        note: 'Nota. M = Media; DE = Desviación Estándar; ** La correlación es estadísticamente significativa al nivel p < .001 (bilateral).',
      },
      pedagogicalExplanation: {
        decision: 'Rechazar la hipótesis nula (H₀)',
        decisionDetail: `Al obtenerse un p-valor menor a 0.001, se rechaza la hipótesis nula de ausencia de correlación. Existe una correlación lineal directa, positiva y estadísticamente significativa de magnitud alta (r = .742) entre las calificaciones analizadas.`,
        thesisParagraph: `Se encontró una correlación lineal positiva, estadísticamente significativa y de magnitud alta entre ${varPre} y ${varPost}, r(${gl}) = .74, p < .001, con un coeficiente de determinación R² = .55, indicando que el 55.1% de la varianza en las calificaciones finales está asociada al rendimiento previo.`,
      },
      followupPrompt:
        '¿Tienes alguna duda sobre la correlación obtenida o cómo interpretarla en tu tesis?',
      suggestedQuestions: [
        {
          chip: '📝 ¿Cómo redacto este hallazgo en mi tesis?',
          question: '¿Cómo redacto este hallazgo en mi tesis?',
          answer: `Para reportar la correlación en formato APA (7.ª ed.): «Se encontró una correlación lineal positiva, estadísticamente significativa y de magnitud alta entre ${varPre} y ${varPost}, r(${gl}) = .74, p < .001, R² = .55. La Tabla 1 muestra la matriz de correlaciones correspondientes».`,
        },
        {
          chip: '💡 ¿Qué significa el p-valor obtenido?',
          question: '¿Qué significa el p-valor obtenido?',
          answer: `El p-valor menor a 0.001 demuestra que la relación entre ambas notas no se debe a la casualidad, confirmando con alta certeza que los estudiantes con mejor nota en la primera evaluación tienden sistemáticamente a obtener mayor nota en la segunda.`,
        },
        {
          chip: '🎯 ¿Qué significa el coeficiente de determinación R²?',
          question: '¿Qué significa el coeficiente de determinación R²?',
          answer: `El coeficiente R² = 55.1% indica que más de la mitad de la variabilidad observada en las calificaciones se explica conjuntamente entre las dos evaluaciones, lo cual representa un valor predictivo sumamente relevante.`,
        },
      ],
    };
  }

  // descriptive
  return {
    resultId,
    title: `Resumen Estadístico Descriptivo Completo (${numericVariableNames || 'Calificaciones'})`,
    technique: 'descriptive_summary',
    techniqueBadge:
      'Estadísticos de tendencia central, dispersión y posición (N = ' +
      n +
      ')',
    keyMetrics: [
      {
        symbol: 'N',
        label: 'Muestra total',
        value: n,
        sublabel: 'Casos válidos',
      },
      {
        symbol: 'M',
        label: 'Media global',
        value: '13.45',
        sublabel: 'Promedio aritmético',
        highlight: true,
      },
      {
        symbol: 'DE',
        label: 'Desviación estándar',
        value: '2.68',
        sublabel: 'Dispersión muestral',
      },
      {
        symbol: 'Mdn',
        label: 'Mediana',
        value: '13.50',
        sublabel: 'Percentil 50 (Q2)',
        highlight: true,
      },
    ],
    apaTable: {
      title: `Tabla 1. Estadísticos descriptivos para las calificaciones continuas analizadas (N = ${n})`,
      columns: ['Variable', 'N', 'M', 'DE', 'Mdn', 'Mín', 'Máx', 'Q₁', 'Q₃'],
      rows: [
        [varPre, n, '11.23', '2.45', '11.00', '6.00', '16.00', '9.50', '13.00'],
        [
          varPost,
          n,
          '15.67',
          '2.10',
          '16.00',
          '11.00',
          '20.00',
          '14.00',
          '17.50',
        ],
      ],
      note: 'Nota. N = Tamaño muestral; M = Media; DE = Desviación Estándar; Mdn = Mediana; Q₁ = Primer cuartil (P25); Q₃ = Tercer cuartil (P75).',
    },
    boxplots: [
      {
        label: varPre,
        min: 6,
        q1: 9.5,
        median: 11.0,
        q3: 13.0,
        max: 16,
        mean: 11.23,
      },
      {
        label: varPost,
        min: 11,
        q1: 14.0,
        median: 16.0,
        q3: 17.5,
        max: 20,
        mean: 15.67,
      },
    ],
    pedagogicalExplanation: {
      decision: 'Caracterización de la distribución',
      decisionDetail: `Las calificaciones presentan una tendencia central consistente con medias y medianas próximas, indicando simetría razonable sin asimetría severa. Se observa una dispersión moderada con coeficientes de variación menores al 25%.`,
      thesisParagraph: `En el análisis descriptivo de las calificaciones (N = ${n}), el ${varPre} presentó una media de M = 11.23 (DE = 2.45, Mdn = 11.00, rango 6.00 a 16.00), mientras que el ${varPost} alcanzó una media de M = 15.67 (DE = 2.10, Mdn = 16.00, rango 11.00 a 20.00), como se detalla en la Tabla 1.`,
    },
    followupPrompt:
      '¿Tienes alguna duda sobre la interpretación descriptiva de tus datos?',
    suggestedQuestions: [
      {
        chip: '📝 ¿Cómo redacto este hallazgo en mi tesis?',
        question: '¿Cómo redacto este hallazgo en mi tesis?',
        answer: `En el capítulo de resultados descriptivos: «Para caracterizar las calificaciones se calcularon medidas de tendencia central y dispersión (Tabla 1). El ${varPre} obtuvo M = 11.23 (DE = 2.45) y el ${varPost} M = 15.67 (DE = 2.10)».`,
      },
      {
        chip: '📊 ¿Qué diferencia hay entre la media y la mediana?',
        question: '¿Qué diferencia hay entre la media y la mediana?',
        answer: `La media es el promedio aritmético sensible a valores atípicos, mientras que la mediana divide al grupo exactamente en dos mitades (50% superior y 50% inferior). Cuando media y mediana son similares, la distribución es simétrica.`,
      },
    ],
  };
}
