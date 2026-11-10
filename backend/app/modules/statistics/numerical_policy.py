"""S04A validation scope for future S04B eligibility, not a technique selector."""

NUMERICAL_POLICY_VERSION = "priority-numerics-1.0.0"
VALIDATED_TECHNIQUES = frozenset(
    {
        "descriptive_summary",
        "pearson",
        "spearman",
        "t_welch",
        "t_independent",
        "mann_whitney",
        "t_paired",
        "wilcoxon",
        "cronbach_alpha",
    }
)
VALIDATED_ALTERNATIVES = frozenset({"two-sided"})
POLICIES = {
    "descriptive_summary": "Cuantiles Hyndman–Fan 7; varianza n−1; frecuencias sobre presentes.",
    "pearson": "Casos completos conjuntos; n>=3; p bilateral t(n−2), equivalente beta bajo H0.",
    "spearman": "Rangos medios; n>=3; p bilateral asintótico t(n−2), cautela en muestras pequeñas.",
    "t_welch": "Casos válidos por grupo; n>=2; df Welch–Satterthwaite; izquierda−derecha.",
    "t_independent": "Casos válidos por grupo; n>=2; varianza agrupada; izquierda−derecha.",
    "t_paired": "Casos completos conjuntos; n>=2; diferencias primera−segunda; varianza positiva.",
    "mann_whitney": "U mínimo; exacto N<=20 sin empates; "
    "resto normal con empates y continuidad 0.5.",
    "wilcoxon": "Ceros descartados (wilcox); >=2 no ceros; exacto n<=20 sin ceros/empates; "
    "resto normal con corrección de empates y continuidad 0.5. Sin redondeo oculto.",
    "cronbach_alpha": ">=2 ítems y >=2 filas completas; "
    "varianza total positiva; alfa negativo posible.",
}
LIMITATIONS = (
    "Solo bilateral contrastado. IC existentes del 95 %; no adaptan alpha de una intención.",
    "Mann–Whitney contrasta distribuciones; no es una prueba general de medianas.",
    "rank_biserial_effect legado usa U mínimo: magnitud no negativa, sin dirección.",
    "rank_effect de Wilcoxon es magnitud z/sqrt(n_no_ceros); no informa dirección.",
    "Alfa no demuestra validez ni unidimensionalidad; requiere ítems recodificados y revisados.",
    "Tukey/Games–Howell legados son t/Welch por pares con Bonferroni; fuera del mínimo validado.",
)
