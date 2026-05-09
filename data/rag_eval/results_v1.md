# Resultados del benchmark cuantitativo del RAG Agent (N30)

Set de evaluación: 15 queries en español sobre el reglamento deportivo FIA 2023-2025, distribuidas en 5 categorías (drs, flags_penalties, pit_stops, safety_car, tyre_allocation). Cada query lleva ground truth manual verificada como substring literal del PDF correspondiente.

**Métricas reportadas.** `Precision@k (estricta)` exige match de artículo (en el payload o en el texto del chunk) **y** match de keyword en el texto. `Content P@5` relaja la condición y exige solo match de keyword, aislando así la calidad del embedding del ruido del article-tagging del indexador. Reportar ambas columnas es la forma honesta de presentar el resultado: la métrica estricta refleja lo que el agente realmente cita, la de contenido refleja lo que el retriever realmente encuentra.

## Tabla resumen comparativa

| Configuración | Precision@1 | Precision@3 | Precision@5 | Content P@5 | MRR | Latencia P50 (ms) | Latencia P95 (ms) |
|---|---|---|---|---|---|---|---|
| BGE-M3 chunk 512 (production) | 0.133 | 0.133 | 0.200 | 0.800 | 0.191 | 34.6 | 107.8 |
| MiniLM-L6-v2 chunk 512 | 0.000 | 0.067 | 0.067 | 0.267 | 0.033 | 17.5 | 26.2 |
| BGE-M3 chunk 256 | 0.067 | 0.067 | 0.067 | 0.800 | 0.093 | 45.3 | 51.6 |

## Discusión

**Precision@5 estricta vs Content P@5.** La métrica estricta exige match de artículo (en payload o en texto del chunk) y match de keyword. La métrica `content_p_at_5` ignora el campo `article` y exige solo presencia de keyword en el texto, aislando así la calidad pura del embedding. La diferencia entre las dos columnas cuantifica el coste de la regex `_ARTICLE_RE` de `scripts/build_rag_index.py`, que tagea cada chunk con la primera referencia `Article X.Y` que encuentra - referencia que en muchos chunks corresponde a una cita cruzada (por ejemplo `Article 30.1a)`) y no al artículo del que el chunk realmente forma parte. Esta degradación es una limitación conocida del pipeline de indexación; mitigarla requiere un post-proceso del payload (enriquecer con la heading más cercana del documento) que está fuera de alcance de este benchmark.

**BGE-M3 vs MiniLM-L6-v2.** BGE-M3 es un modelo multilingüe de 1024d con MTEB ~67 entrenado con contraste masivo; MiniLM-L6-v2 es ~6x más pequeño (384d) y monolingüe en inglés. La diferencia de Precision@k entre filas 1 y 2 de la tabla cuantifica el coste en calidad de sustituir el modelo de producción por una alternativa ligera, y la diferencia de latencia cuantifica el ahorro CPU correspondiente.

**Chunk 512 vs chunk 256 con BGE-M3.** Chunks más finos dan mayor granularidad de recuperación pero aumentan la probabilidad de partir un artículo en dos fragmentos. La comparación filas 1 y 3 de la tabla mide ese trade-off de forma directa: si Precision@5 cae al pasar a chunk 256, el chunking fino está dejando contenido relevante fuera del top-k.

**Latencia P50 / P95.** El retriever se llama una vez por turno del orquestador. Una P95 por debajo de 100 ms hace que el RAG no sea el cuello de botella frente a la llamada al LLM (varios cientos de ms incluso con un modelo local), de modo que el coste de la fase de recuperación es absorbible dentro del SLA del agente.

### Casos de fallo típicos

- **Chunking demasiado fino**: artículos como `30.2`, que ocupan más de 500 caracteres en el PDF, se parten en dos chunks. El chunk con la cláusula numérica concreta (por ejemplo `thirteen (13) sets`) puede quedar fuera del top-k aunque el artículo sí esté representado por su header.
- **Query ambigua**: queries que mencionan simultáneamente DRS y Safety Car (Q14, Q15) compiten contra los chunks de las secciones 55 (Safety Car) y 56 (Virtual Safety Car), que también mencionan ambos términos.
- **Año equivocado**: el retriever no filtra por temporada, así que para una query 2023 puede devolver un chunk 2025 con artículo correcto pero contenido distinto. Las keywords literales suelen capturar este fallo cuando los valores numéricos cambian entre años (intermediates: 4 sets en 2023 vs 5 sets en 2025; DRS habilitado tras 2 vueltas en 2023 vs 1 vuelta en 2025) pero no en todos los casos.

### Reproducibilidad

El cuaderno `notebooks/agents/N30B_rag_benchmark.ipynb` reconstruye el set y las dos colecciones nuevas de Qdrant de forma idempotente: Restart Kernel → Run All las salta si ya existen. El JSON con las queries vive en `data/rag_eval/queries_v1.json` y la verificación literal de keywords es responsabilidad del autor del set, no del cuaderno - cualquier ampliación futura debe pasar por el mismo filtro contra los PDFs originales.
