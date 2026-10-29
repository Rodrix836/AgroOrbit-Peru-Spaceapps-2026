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
