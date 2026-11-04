# Matriz E2E Research → Statistics

Cada fila identifica al menos una prueba que crea el proyecto Research, construye un paquete
vigente, propone, aprueba explícitamente y ejecuta el motor Statistics con un dataset sintético
controlado. No se ejecuta código indicado por el cliente: la técnica llega al motor mediante el
catálogo permitido y las entradas validadas del adaptador.

| Técnica del catálogo | Caso E2E de referencia |
| --- | --- |
| `descriptive_summary` | `test_real_descriptive_metrics_and_reload` |
| `pearson` | `test_real_pearson_columns` |
| `spearman` | `test_real_spearman_columns_with_ordinal_variable` |
| `chi_square` | `test_real_chi_square_columns_with_categorical_variables` |
| `fisher_exact` | `test_real_fisher_exact_columns_with_categorical_variables` |
| `t_paired` | `test_real_paired_t_columns_with_paired_observations` |
| `wilcoxon` | `test_real_wilcoxon_columns_with_paired_ordinal_observations` |
| `t_independent` | `test_real_independent_t_columns_with_two_groups` |
| `t_welch` | `test_real_welch_t_columns_with_two_groups` |
| `mann_whitney` | `test_real_mann_whitney_columns_with_two_groups` |
| `cronbach_alpha` | `test_real_cronbach_alpha_with_linked_item_columns` |
| `anova` | `test_real_multigroup_columns[anova-…]` |
| `anova_welch` | `test_real_multigroup_columns[anova_welch-…]` |
| `kruskal_wallis` | `test_real_multigroup_columns[kruskal_wallis-…]` |
| `tukey` | `test_real_multigroup_columns[tukey-…]` |
| `games_howell` | `test_real_multigroup_columns[games_howell-…]` |
| `ancova` | `test_real_ancova_columns` |
| `linear_regression_simple` | `test_real_simple_regression_columns` |
| `linear_regression_multiple` | `test_real_multiple_regression_columns` |

La matriz se complementa con casos de control: rechazo de entradas de grupo incompatibles,
datos constantes o insuficientes, cambios de fuente que invalidan propuestas, aprobación
explícita y reintentos sin recalcular un resultado persistido.
