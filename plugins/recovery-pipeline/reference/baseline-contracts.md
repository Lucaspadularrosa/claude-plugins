# Contratos de la linea de base — copia de referencia para la reconstruccion

`baseline-reconstruction` corre sin acceso a los archivos del plugin
`requirements-pipeline`, asi que los contratos que debe emitir estan **embebidos aca**.

> **Fuente canonica**: los agentes de `requirements-pipeline`
> (`product-mapping.md`, `lel-authoring.md`, `scenario-modeling.md`,
> `requirements-specification.md`, `technical-design.md`). Si esos contratos
> cambian, esta copia debe actualizarse en el mismo PR — es el precio de que la
> reconstruccion funcione sin leer otro plugin.

Convenciones transversales de la suite (aplican a todos los archivos):

- `version` empieza en 1 y se incrementa en cada reescritura; `metadata.updated_at`
  se actualiza siempre; los `*_version_ref` citan la `version` del archivo
  referenciado, como string (ej. `"3"`).
- Ids estables, nunca renumerar ni borrar (lo eliminado se deprecia). Formatos:
  `FG-01` features, `SCN-001` escenarios, `EP/ACT/RES/EXC-001` partes del escenario,
  `SYM/NOT/IMP-001` LEL, `RF/RNF-001` requisitos, `AC-001` criterios (numerados POR
  requisito; cita compuesta `RF-007/AC-002`), `BR-001` reglas de negocio,
  `ENT/REL-001` modelo de datos,
  `MOD/API/SCR/ADR-001` diseno, `Q-001` preguntas abiertas.
- Estados del mapa: `stub|elaborated|baselined|deprecated`. Estados de requisitos y
  escenarios: `active|proposed|deprecated`.
- **Extensiones validas de una linea de base reconstruida** (los consumidores las
  ignoran si no las usan): `"origin": "recovered"` por requisito, y
  `"code_refs": ["ruta/archivo.ext:123"]` opcional en features, escenarios,
  requisitos y entidades — la traza al codigo. Los `evidence_refs` de mapa,
  escenarios y requisitos citan **ids de la suite** (`SYM-xxx`, `SCN-xxx`,
  `OWN-xxx`); el `archivo:linea` va en `code_refs` y en los `evidence_refs` del LEL
  (que son strings libres).
- Todos los valores legibles por humanos en espanol.

## 1. `product-map.json`

```json
{
  "version": 1,
  "project": {"name": "string", "domain_summary": "string", "source_language": "es"},
  "metadata": {"created_at": "string", "updated_at": "string", "lel_version_ref": "string", "source_artifacts": ["string"]},
  "summary": {
    "feature_count": 0,
    "stub_count": 0, "elaborated_count": 0, "baselined_count": 0, "deprecated_count": 0,
    "pending_proposal_count": 0
  },
  "features": [
    {
      "id": "FG-01",
      "name": "string",
      "description": "string",
      "priority": "high|medium|low",
      "priority_rationale": "string",
      "status": "stub|elaborated|baselined|deprecated",
      "lel_symbol_ids": ["SYM-001"],
      "scenario_stubs": [
        {"id": "SCN-001", "title": "string", "goal": "string", "actors": ["string"], "status": "stub|elaborated|baselined|deprecated", "evidence_refs": ["SYM-001"]}
      ],
      "evidence_refs": ["SYM-001"],
      "discovered_in": "REC-001"
    }
  ],
  "pending_proposals": [],
  "warnings": ["string"]
}
```

En reconstruccion, `discovered_in` cita la corrida `REC-xxx` y los `evidence_refs`
citan simbolos del LEL (`SYM-xxx`); la traza al codigo va en `code_refs`.

## 2. `lel.json`

```json
{
  "version": 1,
  "project": {"name": "string", "domain_summary": "string", "source_language": "es"},
  "metadata": {"created_at": "string", "updated_at": "string", "source_artifacts": ["string"]},
  "symbols": [
    {
      "id": "SYM-001",
      "canonical_name": "string",
      "names": ["string"],
      "type": "sujeto|objeto|verbo|estado",
      "status": "active|deprecated|proposed",
      "notions": [{"id": "NOT-001", "statement": "string", "evidence_refs": ["ruta/archivo.ext:123"]}],
      "impacts": [{"id": "IMP-001", "statement": "string", "evidence_refs": ["ruta/archivo.ext:123"], "referenced_symbol_ids": ["SYM-002"]}],
      "aliases": ["string"],
      "related_symbol_ids": ["SYM-002"],
      "open_questions": ["string"],
      "assumptions": ["string"],
      "revision": {"created_from": ["string"], "last_changed_reason": "REC-001"}
    }
  ],
  "alias_map": [{"alias": "string", "symbol_id": "SYM-001", "confidence": "high|medium|low", "evidence_refs": ["string"]}],
  "open_questions": [{"id": "Q-001", "question": "string", "blocking": true, "target_role": "string", "reason": "string", "related_symbol_ids": ["SYM-001"]}],
  "traceability_links": [{"source": {"kind": "source|symbol|notion|impact|alias|question", "id": "string"}, "target": {"kind": "source|symbol|notion|impact|alias|question", "id": "string"}, "relationship": "derived_from|defines|mentions|aliases|questions|relates_to"}],
  "assumptions": ["string"],
  "warnings": ["string"]
}
```

## 3. `scenarios.json`

```json
{
  "version": 1,
  "project": {"name": "string", "domain_summary": "string", "source_language": "es"},
  "metadata": {"created_at": "string", "updated_at": "string", "source_artifacts": ["string"], "lel_version_ref": "string"},
  "summary": {
    "total_scenarios": 0, "current_scenarios": 0, "future_scenarios": 0,
    "total_episodes": 0, "total_exceptions": 0,
    "covered_symbol_ids": ["SYM-001"], "uncovered_symbol_ids": ["SYM-002"], "blocking_questions": 0
  },
  "scenarios": [
    {
      "id": "SCN-001", "title": "string", "goal": "string",
      "scenario_type": "current|future", "status": "active|proposed|deprecated",
      "context": {"geographic_location": "string", "temporality": "string", "preconditions": ["string"], "evidence_refs": ["SYM-001"]},
      "actors": [{"id": "ACT-001", "name": "string", "lel_symbol_id": "SYM-001", "evidence_refs": ["SYM-001"]}],
      "resources": [{"id": "RES-001", "name": "string", "lel_symbol_id": "SYM-002", "evidence_refs": ["SYM-002"]}],
      "episodes": [{"id": "EP-001", "sentence": "string", "episode_type": "simple|conditional|optional", "condition": "string", "referenced_scenario_id": "SCN-002", "referenced_symbol_ids": ["SYM-001"], "evidence_refs": ["IMP-001"]}],
      "exceptions": [{"id": "EXC-001", "cause": "string", "solution": "string", "referenced_scenario_id": "SCN-003", "evidence_refs": ["SYM-001"]}],
      "lel_symbol_ids": ["SYM-001"], "related_scenario_ids": ["SCN-002"],
      "open_questions": ["string"], "assumptions": ["string"], "evidence_refs": ["SYM-001"]
    }
  ],
  "open_questions": [{"id": "Q-001", "question": "string", "blocking": true, "target_role": "string", "reason": "string", "related_scenario_ids": ["SCN-001"], "related_symbol_ids": ["SYM-001"]}],
  "traceability_links": [{"source": {"kind": "symbol|scenario|episode|exception|question", "id": "string"}, "target": {"kind": "symbol|scenario|episode|exception|question", "id": "string"}, "relationship": "derived_from|uses|triggers|handles|questions|relates_to"}],
  "assumptions": ["string"],
  "warnings": ["string"]
}
```

Los `evidence_refs` de escenarios apuntan a simbolos/impactos del LEL existentes
(los validadores de `requirements-pipeline` lo exigen). En reconstruccion,
`scenario_type` es `"current"`.

## 4. `requirements.json`

```json
{
  "version": 1,
  "project": {"name": "string", "domain_summary": "string", "source_language": "es"},
  "metadata": {"created_at": "string", "updated_at": "string", "source_artifacts": ["string"], "lel_version_ref": "string", "scenario_version_ref": "string"},
  "summary": {
    "total_requirements": 0, "functional_count": 0, "non_functional_count": 0,
    "high_priority": 0, "medium_priority": 0, "low_priority": 0,
    "feature_count": 0, "business_rule_count": 0,
    "covered_scenario_ids": ["SCN-001"], "uncovered_scenario_ids": ["SCN-002"], "blocking_questions": 0
  },
  "feature_groups": [
    {"id": "FG-01", "name": "string", "description": "string", "scenario_ids": ["SCN-001"], "requirement_ids": ["RF-001"]}
  ],
  "functional_requirements": [
    {
      "id": "RF-001", "title": "string", "statement": "El sistema debe ...",
      "feature_group": "FG-01",
      "priority": "high|medium|low", "status": "active|proposed|deprecated",
      "estimated_effort": "xs|s|m|l|xl",
      "depends_on": ["RF-002"],
      "verification_method": "test|demonstration|inspection|analysis",
      "acceptance_criteria": [
        {"id": "AC-001", "given": "string", "when": "string", "then": "string"}
      ],
      "source_scenario_ids": ["SCN-001"], "source_episode_ids": ["EP-001"],
      "lel_symbol_ids": ["SYM-001"], "rationale": "string",
      "origin": "recovered",
      "assumptions": ["string"], "open_questions": ["string"], "evidence_refs": ["SCN-001"]
    }
  ],
  "non_functional_requirements": [
    {
      "id": "RNF-001", "title": "string", "statement": "El sistema debe ...",
      "feature_group": "FG-01",
      "category": "performance|security|usability|reliability|availability|maintainability|portability|scalability|compliance|other",
      "priority": "high|medium|low", "status": "active|proposed|deprecated",
      "estimated_effort": "xs|s|m|l|xl",
      "depends_on": ["RF-001"],
      "verification_method": "test|demonstration|inspection|analysis",
      "metric": "string",
      "acceptance_criteria": [
        {"id": "AC-001", "given": "string", "when": "string", "then": "string"}
      ],
      "source_scenario_ids": ["SCN-001"], "lel_symbol_ids": ["SYM-001"],
      "rationale": "string", "assumptions": ["string"], "open_questions": ["string"], "evidence_refs": ["SCN-001"]
    }
  ],
  "business_rules": [
    {
      "id": "BR-001", "statement": "string (invariante del dominio, en voz declarativa)",
      "kind": "invariant|constraint|derivation",
      "status": "active|proposed|deprecated",
      "lel_symbol_ids": ["SYM-001"], "source_scenario_ids": ["SCN-001"],
      "enforced_by": ["RF-007/AC-002"],
      "rationale": "string", "open_questions": ["string"], "evidence_refs": ["SCN-001"]
    }
  ],
  "open_questions": [{"id": "Q-001", "question": "string", "blocking": true, "target_role": "string", "reason": "string", "related_requirement_ids": ["RF-001"], "related_scenario_ids": ["SCN-001"]}],
  "proposed_baseline_changes": [],
  "traceability_links": [{"source": {"kind": "symbol|scenario|episode|requirement|question", "id": "string"}, "target": {"kind": "symbol|scenario|episode|requirement|question", "id": "string"}, "relationship": "derived_from|verifies|covers|uses|questions|relates_to"}],
  "assumptions": ["string"],
  "warnings": ["string"]
}
```

Campos que la planificacion consume si o si (no pueden faltar): `feature_groups[]`
completo, y por requisito `feature_group`, `priority`, `status`, `estimated_effort`,
`depends_on`, `verification_method`, `acceptance_criteria` Gherkin, y los
`metadata.*_version_ref`.

`business_rules`: en reconstruccion, deriva las reglas evidentes en el codigo
(validaciones, constraints de esquema, guards repetidos entre modulos) con su
evidencia en `code_refs`; si no hay reglas claras, deja el array vacio — no inventes
invariantes que el codigo no demuestra.

## 5. `data-model.json`

```json
{
  "version": 1,
  "project": {"name": "string", "domain_summary": "string", "source_language": "es"},
  "metadata": {"created_at": "string", "updated_at": "string", "source_artifacts": ["string"], "lel_version_ref": "string", "requirements_version_ref": "string"},
  "summary": {"entity_count": 0, "relationship_count": 0, "covered_symbol_ids": ["SYM-001"], "uncovered_symbol_ids": ["SYM-002"]},
  "entities": [
    {
      "id": "ENT-001",
      "name": "string",
      "lel_symbol_id": "SYM-001",
      "description": "string",
      "fields": [
        {"name": "string", "type": "string", "required": true, "unique": false, "notes": "string"}
      ],
      "primary_key": ["string"],
      "source_requirement_ids": ["RF-001"],
      "evidence_refs": ["SYM-001"],
      "assumptions": ["string"],
      "open_questions": ["string"]
    }
  ],
  "relationships": [
    {"id": "REL-001", "type": "one_to_one|one_to_many|many_to_one|many_to_many", "from_entity_id": "ENT-001", "to_entity_id": "ENT-002", "name": "string", "notes": "string", "evidence_refs": ["SYM-001"]}
  ],
  "open_questions": [{"id": "Q-001", "question": "string", "blocking": true, "target_role": "string", "reason": "string"}],
  "traceability_links": [{"source": {"kind": "symbol|requirement|entity|relationship", "id": "string"}, "target": {"kind": "symbol|requirement|entity|relationship", "id": "string"}, "relationship": "derived_from|models|relates_to"}],
  "assumptions": ["string"],
  "warnings": ["string"]
}
```

## 6. `technical-design.json`

```json
{
  "version": 1,
  "project": {"name": "string", "domain_summary": "string", "source_language": "es"},
  "metadata": {"created_at": "string", "updated_at": "string", "source_artifacts": ["string"], "requirements_version_ref": "string", "data_model_version_ref": "string"},
  "summary": {"module_count": 0, "api_contract_count": 0, "screen_count": 0, "decision_count": 0},
  "stack": [
    {"layer": "string", "technology": "string", "rationale": "string", "evidence_refs": ["string"]}
  ],
  "modules": [
    {"id": "MOD-001", "name": "string", "responsibility": "string", "depends_on": ["MOD-002"], "feature_group": "FG-01", "requirement_ids": ["RF-001"], "entity_ids": ["ENT-001"]}
  ],
  "api_contracts": [
    {"id": "API-001", "method": "GET|POST|PATCH|PUT|DELETE", "path": "string", "purpose": "string", "auth_required": true, "request_summary": "string", "response_summary": "string", "requirement_ids": ["RF-001"], "evidence_refs": ["string"]}
  ],
  "screens": [
    {"id": "SCR-001", "name": "string", "purpose": "string", "role_access": ["string"], "design_source": "mockup|proposed", "design_assets": ["ruta/al/mockup.html"], "requirement_ids": ["RF-001"], "evidence_refs": ["string"]}
  ],
  "decisions": [
    {"id": "ADR-001", "title": "string", "status": "proposed|accepted", "context": "string", "decision": "string", "alternatives": ["string"], "consequences": "string", "requirement_ids": ["RNF-001"]}
  ],
  "open_questions": [{"id": "Q-001", "question": "string", "blocking": true, "target_role": "string", "reason": "string"}],
  "traceability_links": [{"source": {"kind": "requirement|module|api|screen|decision|entity", "id": "string"}, "target": {"kind": "requirement|module|api|screen|decision|entity", "id": "string"}, "relationship": "derived_from|implements|satisfies|relates_to"}],
  "assumptions": ["string"],
  "warnings": ["string"]
}
```

## 7. Entrada del changelog (la escribe el ORQUESTADOR, no el agente)

Una entrada `REC-xxx`, `kind: "recovery"`, con el mismo esquema del changelog de la
suite (definido en la skill de `requirements-pipeline`): `status`
`in_progress|applied|rejected`, `sources`, `feature_ids`, `verdicts` y
`artifact_versions` (before/after por archivo tocado).
