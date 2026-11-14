# Orquestación futura

LangGraph coordinará los tres agentes a través de contratos de `app.shared` y puertos.
No hay grafo ejecutable ni dependencia LangGraph en sesión 1. No importar implementaciones
internas de Research desde Statistics, ni a la inversa.

Límites previstos: pasos de grafo acotados, tiempo máximo por solicitud, presupuesto
de tokens y control de concurrencia. Nunca ejecutar código procedente del modelo o documentos.
