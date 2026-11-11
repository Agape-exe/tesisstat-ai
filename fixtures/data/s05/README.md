# S05 — Respuestas sintéticas verificables

Datos totalmente sintéticos de experiencia de servicio y observaciones declaradas de
parcelas. No son instrumentos validados ni evidencia de un constructo real. `id` sirve solo
para reconocer filas; no es una respuesta puntuada. El usuario declara qué agrupación y
pregunta tienen sentido en su investigación; estos nombres no son una estructura universal.

En ambos ejemplos: tres ítems numéricos con límites 1–5; el segundo se invierte mediante
1 + 5 − valor. Una regla usa solo los dos primeros ítems. El tercero no participa.

- Ítems recodificados por fila: (1,1), (2,2), (3,4), (4,5), (null,3).
- Suma: 2, 4, 7, 9, null. Promedio: 1, 2, 3.5, 4.5, null.
- El tercer ítem ausente en la primera fila no anula esa regla.
- Cuatro casos completos. Varianzas muestrales: 5/3 y 10/3; varianza de totales: 29/3.
  Alfa = 2 × [1 − (5/3 + 10/3)/(29/3)] = 28/29.

Tests C6 añaden códigos A/B con puntuaciones explícitas 1/3, código Z desconocido, respuesta
9 fuera de rango y ausencias; excluyen cada fila de su puntuación sin convertirla en cero.
El caso alfa negativo usa pares recodificados (1,3),(2,2),(3,2): varianzas 1 y 1/3, total
1/3; alfa = 2 × (1 − 4) = −6. Se conserva el signo, sin umbral universal de aprobación.
