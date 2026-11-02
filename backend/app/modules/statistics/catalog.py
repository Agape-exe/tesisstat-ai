"""Verified, declarative statistical technique catalog.

The catalog contains eligibility metadata only. Technique names are identifiers,
never executable code; calculations belong to a later deterministic engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TechniqueGroup = Literal[
    "descriptive",
    "reliability",
    "association",
    "parametric_comparison",
    "nonparametric_comparison",
    "posthoc",
    "categorical",
    "covariance",
    "regression",
]


@dataclass(frozen=True)
class TechniqueDefinition:
    """Non-executable metadata used by the deterministic planner."""

    name: str
    label: str
    group: TechniqueGroup
    rationale: str
    assumptions_to_check: tuple[str, ...]


_TECHNIQUES = (
    TechniqueDefinition(
        "descriptive_summary",
        "Resumen descriptivo",
        "descriptive",
        "Resume las variables seleccionadas sin contrastar una hipótesis.",
        (),
    ),
    TechniqueDefinition(
        "cronbach_alpha",
        "Alfa de Cronbach",
        "reliability",
        "Estima la consistencia interna de varios ítems de un instrumento.",
        ("Los ítems deben medir el mismo constructo.",),
    ),
    TechniqueDefinition(
        "pearson",
        "Correlación de Pearson",
        "association",
        "Mide asociación lineal entre dos variables cuantitativas.",
        ("Linealidad", "Normalidad aproximada", "Ausencia de valores atípicos influyentes"),
    ),
    TechniqueDefinition(
        "spearman",
        "Correlación de Spearman",
        "association",
        "Mide asociación monótona usando rangos, apropiada para escalas ordinales.",
        ("Observaciones independientes", "Relación monótona"),
    ),
    TechniqueDefinition(
        "t_independent",
        "t de Student independiente",
        "parametric_comparison",
        "Compara medias de dos grupos independientes.",
        ("Normalidad por grupo", "Homogeneidad de varianzas", "Independencia"),
    ),
    TechniqueDefinition(
        "t_paired",
        "t de Student pareada",
        "parametric_comparison",
        "Compara medias de dos mediciones emparejadas.",
        ("Normalidad de las diferencias", "Pares completos"),
    ),
    TechniqueDefinition(
        "t_welch",
        "t de Welch",
        "parametric_comparison",
        "Compara dos medias independientes sin asumir varianzas iguales.",
        ("Normalidad por grupo", "Independencia"),
    ),
    TechniqueDefinition(
        "mann_whitney",
        "Mann–Whitney",
        "nonparametric_comparison",
        "Compara dos grupos independientes con una alternativa no paramétrica.",
        ("Independencia", "Forma comparable de las distribuciones"),
    ),
    TechniqueDefinition(
        "wilcoxon",
        "Wilcoxon pareada",
        "nonparametric_comparison",
        "Compara dos mediciones emparejadas sin asumir normalidad.",
        ("Pares completos", "Distribución simétrica de diferencias como convención usual"),
    ),
    TechniqueDefinition(
        "anova",
        "ANOVA de un factor",
        "parametric_comparison",
        "Compara medias de tres o más grupos independientes.",
        ("Normalidad por grupo", "Homogeneidad de varianzas", "Independencia"),
    ),
    TechniqueDefinition(
        "anova_welch",
        "ANOVA de Welch",
        "parametric_comparison",
        "Compara medias de varios grupos sin asumir varianzas iguales.",
        ("Normalidad aproximada", "Independencia"),
    ),
    TechniqueDefinition(
        "kruskal_wallis",
        "Kruskal–Wallis",
        "nonparametric_comparison",
        "Compara varios grupos independientes mediante rangos.",
        ("Independencia", "Distribuciones con forma comparable"),
    ),
    TechniqueDefinition(
        "tukey",
        "Tukey HSD",
        "posthoc",
        "Compara pares de medias después de un ANOVA compatible.",
        ("ANOVA global significativo", "Homogeneidad de varianzas"),
    ),
    TechniqueDefinition(
        "games_howell",
        "Games–Howell",
        "posthoc",
        "Compara pares de medias después de un análisis global heterocedástico.",
        ("Análisis global significativo", "Independencia"),
    ),
    TechniqueDefinition(
        "chi_square",
        "Chi-cuadrado de independencia",
        "categorical",
        "Evalúa asociación entre dos variables categóricas.",
        ("Frecuencias esperadas suficientes", "Observaciones independientes"),
    ),
    TechniqueDefinition(
        "fisher_exact",
        "Prueba exacta de Fisher",
        "categorical",
        "Evalúa asociación categórica en tablas pequeñas.",
        ("Tabla 2 × 2", "Observaciones independientes"),
    ),
    TechniqueDefinition(
        "ancova",
        "ANCOVA",
        "covariance",
        "Compara grupos ajustando el efecto de una covariable cuantitativa.",
        ("Linealidad", "Homogeneidad de pendientes", "Normalidad de residuos", "Independencia"),
    ),
    TechniqueDefinition(
        "linear_regression_simple",
        "Regresión lineal simple",
        "regression",
        "Modela una variable cuantitativa con un predictor cuantitativo.",
        ("Linealidad", "Normalidad de residuos", "Homoscedasticidad", "Independencia"),
    ),
    TechniqueDefinition(
        "linear_regression_multiple",
        "Regresión lineal múltiple",
        "regression",
        "Modela una variable cuantitativa con varios predictores.",
        (
            "Linealidad",
            "Normalidad de residuos",
            "Homoscedasticidad",
            "Independencia",
            "Ausencia de colinealidad severa",
        ),
    ),
)

TECHNIQUE_CATALOG: tuple[TechniqueDefinition, ...] = _TECHNIQUES
_BY_NAME = {technique.name: technique for technique in TECHNIQUE_CATALOG}


def list_techniques() -> tuple[TechniqueDefinition, ...]:
    """Return the immutable verified catalog in deterministic order."""

    return TECHNIQUE_CATALOG


def get_technique(name: str) -> TechniqueDefinition:
    """Resolve an allowlisted technique identifier."""

    try:
        return _BY_NAME[name]
    except KeyError as error:
        raise ValueError(f"Técnica no permitida: {name}") from error
