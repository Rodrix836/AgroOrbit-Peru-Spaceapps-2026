# Contrato propuesto para recomendaciones

Esta propuesta está lista para revisión conjunta con Luis y Milene. El endpoint se activará cuando el motor tenga una salida definida y exista un catálogo de cultivos con fuentes. No se presenta ningún resultado de prueba como consejo agronómico.

## Solicitud

`POST /api/recommendations` con `Authorization: Bearer <token de Supabase Auth>`.

```json
{
  "plot_id": "uuid-de-la-parcela",
  "horizon_days": 180,
  "priority": "save_water"
}
```

La API obtiene el usuario desde el token y comprueba que la parcela le pertenece. `priority` admite `save_water`, `improve_soil`, `reduce_climate_risk`, `diversify` y `maintain_productivity`. No se acepta un `user_id` del cliente.

## Respuesta prevista

```json
{
  "id": "uuid-de-la-recomendacion",
  "plot_id": "uuid-de-la-parcela",
  "status": "ready",
  "generated_at": "2026-10-29T12:00:00Z",
  "engine_version": "version-del-motor",
  "confidence": "medium",
  "recommended_crop": {"id": "uuid-del-cultivo", "name": "Nombre"},
  "summary": "Resumen explicativo",
  "ranking": [
    {
      "crop": {"id": "uuid-del-cultivo", "name": "Nombre"},
      "rank": 1,
      "score": 0.72,
      "eligible": true,
      "reasons": ["Motivo verificable"],
      "limiting_factors": ["Factor limitante"],
      "exclusion_reason": null
    }
  ],
  "rotation": [
    {
      "step": 1,
      "action": "crop",
      "crop": {"id": "uuid-del-cultivo", "name": "Nombre"},
      "start_on": "2026-11-01",
      "end_on": "2027-02-28",
      "climate_basis": "historical",
      "confidence": "medium",
      "reason": "Justificación con fuente"
    }
  ]
}
```

Si faltan datos, `status` será `insufficient_data`, `confidence` será `insufficient`, `recommended_crop` será `null` y las listas estarán vacías. El motor y la API deberán acordar la forma exacta de `reasons`, `limiting_factors` y el catálogo antes de activar la ruta. Las pruebas de persistencia previas usarán `engine_version=test-fixture` y `input_snapshot.test_data=true`.

---

## Puntos pendientes a acordar para el motor agronómico (Equipo)

1. **Catálogo de Cultivos y Fuentes Técnicas (`crop`, `agronomic_source`):**
   - Definir qué cultivos iniciales de los valles del Perú (ej. Piura, Ica, Lambayeque) se incluirán en la siembra de datos.
   - Establecer las fuentes agronómicas mínimas requeridas (INIA, FAO, SENAMHI, CIP) para validar requerimientos agroclimáticos y umbrales térmicos/hídricos.

2. **Cálculo de Indicadores Climáticos (`indicator`):**
   - Especificar cómo derivar indicadores agregados a partir de `nasa_observation` (ej. precipitación acumulada a 30/60/90 días, suma térmica GDD, días secos consecutivos, radiación solar media).
   - Acordar el manejo de ventanas temporales (histórico de los últimos 3-5 años vs. ventana reciente).

3. **Ponderación de Factores Limitantes (`limiting_factors`):**
   - Reglas de penalización o exclusión directa según disponibilidad hídrica (`water_availability`), pH y salinidad del suelo (`soil_salinity_ds_m`).
   - Algoritmo de puntuación (`score` de 0.0 a 1.0) para el ranking de cultivos aptos.

4. **Reglas de Rotación (`rotation_rule`, `rotation_plan`):**
   - Definir reglas fijas (ej. no repetir leguminosa con leguminosa consecutiva, rotación maíz-frijol para recuperación de nitrógeno).
   - Determinación del calendario tentativo (`start_on`, `end_on`) según ciclo vegetativo (`cycle_min_days`, `cycle_max_days`).

5. **Integración IoT / Sensores de Terreno (`device`, `sensor_reading`):**
   - Prioridad de calibración: si hay lecturas recientes de humedad de suelo (`soil_moisture`), cómo reemplazan o ajustan las estimaciones de balance hídrico de POWER.
