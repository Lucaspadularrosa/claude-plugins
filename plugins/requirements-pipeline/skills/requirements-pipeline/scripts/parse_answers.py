#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lee las respuestas del stakeholder escritas DENTRO de stakeholder-questions.md.

El cuestionario se renderiza (render_baseline_docs.py) con un bloque
`**Respuesta QST-xxx:**` por pregunta y, para las de opcion, casillas `- [ ]`. El
stakeholder contesta ahi (o el orquestador copia ahi lo que le dijeron por chat) y
este script hace lo mecanico: parsea, clasifica cada respuesta y deriva los dos
artefactos canonicos de respuestas. El orquestador nunca transcribe respuestas a
mano ni decide que una respuesta "alcanza".

Clasificacion por pregunta (`status`):
  answered    hay texto o una casilla marcada, y no es ambigua
  ambiguous   el texto cae en el lexico de ambiguedad (depende, mas o menos, no se...)
              o hay mas de una casilla marcada en una pregunta de opcion unica;
              trae `follow_up`, la repregunta ya redactada
  defaulted   sin respuesta, pero la pregunta trae `default_assumption`
  unanswered  sin respuesta y sin default; `blocking` si la pregunta es `high`

Retrocompatible entre corridas: una pregunta que conserva su id y aparece en blanco
hereda la respuesta de la corrida anterior (`carried_from_version`); las preguntas que
ya no estan en el cuestionario se conservan como retiradas (`retired_answers`), nunca
se borran. Un `stakeholder-answers.md` escrito a mano por una version anterior (sin
JSON al lado) se archiva en `sources/` como una fuente mas antes de regenerarlo.

Escribe en la misma carpeta:
  stakeholder-answers.json   el dato (version +1 si ya existia)
  stakeholder-answers.md     la vista que leen lel-authoring y los agentes de
                             actualizacion (una entrada por QST-xxx), derivada

Stdout: una linea `respuestas:` con los conteos, una `falta QST-xxx (bloqueante)` por
bloqueante sin responder y una `repreguntar QST-xxx: ...` por ambigua.
Exit 0 si no hay bloqueantes sin responder ni ambiguas; 2 si las hay (el orquestador
muestra solo esas lineas y espera otra ronda); 1 ante error de IO.

Uso:
  python parse_answers.py [.dev/requirements] [--pipeline-version X] [--fecha AAAA-MM-DD]
  python parse_answers.py --self-test
Solo stdlib, Python 3.8+.
"""
from __future__ import print_function

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

# Lexico de ambiguedad: (grupo, giros, repregunta). Coincidencia por palabra completa
# sobre texto normalizado (minusculas, sin tildes). Es una lista: se edita aca.
LEXICON = [
    ("condicional", ["depende", "segun", "varia", "a veces", "en general"],
     "Dijiste '{t}': ¿de que depende y cual es la regla en cada caso?"),
    ("duda", ["ni idea", "creo que", "supongo", "me parece", "quizas", "quiza",
              "tal vez", "puede ser"],
     "Dijiste '{t}': ¿quien lo sabe con certeza? Si nadie, ¿que asumimos y quien lo confirma?"),
    ("vaguedad", ["mas o menos", "algo asi", "lo tipico", "lo normal", "lo habitual",
                  "lo de siempre", "lo estandar", "un poco de cada"],
     "Dijiste '{t}': dame un ejemplo concreto o el valor exacto."),
    ("postergacion", ["a definir", "despues vemos", "mas adelante", "lo charlamos", "por ahora no"],
     "Dijiste '{t}': ¿que asumimos mientras tanto y cuando se define?"),
]
# Solo en preguntas de opcion unica (yes_no / choice).
BOTH = (["ambas", "ambos", "las dos", "los dos", "un mix"],
        "Tiene que ser una: ¿cual va primero, o que distingue un caso del otro?")
SINGLE_CHOICE = {"yes_no", "choice"}

PLACEHOLDER = "_(completar)_"
Q_HEAD = re.compile(r"^### (QST-\d+)\b")
ANSWER_LINE = re.compile(r"^\*\*Respuesta(?: (QST-\d+))?:\*\*\s*$")
CHECKBOX = re.compile(r"^\s*- \[([ xX])\]\s*(.*)$")
SECTION = re.compile(r"^#{1,3} ")


def normalize(text):
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text.lower()).strip()


# "no se" es duda solo si es "no sé" con tilde, o "no se" cerrado por puntuacion, fin de
# texto o un giro de duda ("no se si", "no se bien", "no se cuando"). "No se puede
# reservar" es una regla, no una duda (falso positivo H-04 de la corrida de prueba).
NO_SE_RAW = re.compile(r"\bno s[eé]\b", re.IGNORECASE)
NO_SE_DUDA = re.compile(r"(?<![a-z0-9])no se(?=\s*(?:$|[.,;:!?)]|(?:si|bien|cuando|todavia|aun|muy|que|quien|cual|como|donde)(?![a-z])))")


def es_no_se_duda(text):
    if re.search(r"\bno sé\b", text or "", re.IGNORECASE):
        return True
    return bool(NO_SE_DUDA.search(normalize(text)))


def find_terms(text, terms):
    norm = normalize(text)
    found = []
    for t in terms:
        if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", norm):
            found.append(t)
    return found


def parse_markdown(md_text):
    """{QST-xxx: {"text": str, "checked": [str], "unchecked": [str]}} por bloque."""
    blocks, current, in_answer = {}, None, False
    for raw in md_text.splitlines():
        line = raw.rstrip()
        m = Q_HEAD.match(line)
        if m:
            current = m.group(1)
            blocks[current] = {"text": [], "checked": [], "unchecked": []}
            in_answer = False
            continue
        if SECTION.match(line):
            current, in_answer = None, False
            continue
        if current is None:
            continue
        if ANSWER_LINE.match(line):
            in_answer = True
            continue
        if not in_answer:
            continue
        cb = CHECKBOX.match(line)
        if cb:
            (blocks[current]["checked"] if cb.group(1).lower() == "x" else blocks[current]["unchecked"]).append(cb.group(2).strip())
            continue
        if line.strip() == PLACEHOLDER:
            continue
        blocks[current]["text"].append(line)
    for b in blocks.values():
        b["text"] = "\n".join(b["text"]).strip()
    return blocks


def classify(question, block):
    """Una entrada de `answers` para la pregunta."""
    qid = question.get("id")
    kind = question.get("expected_answer_type") or "free_text"
    blocking = bool(question.get("blocking")) if "blocking" in question else question.get("priority") == "high"
    text = (block or {}).get("text", "")
    checked = (block or {}).get("checked", [])
    entry = {"id": qid, "status": None, "answer": text or None,
             "choice": checked[0] if len(checked) == 1 else (checked or None)}
    if not text and not checked:
        if question.get("default_assumption"):
            entry.update(status="defaulted", assumed=question["default_assumption"])
        else:
            entry.update(status="unanswered", blocking=blocking)
        return entry
    if kind in SINGLE_CHOICE and len(checked) > 1:
        entry.update(status="ambiguous", ambiguity_terms=["dos casillas marcadas"],
                     follow_up=BOTH[1])
        return entry
    if es_no_se_duda(text):
        entry.update(status="ambiguous", ambiguity_terms=["no se"],
                     follow_up=LEXICON[1][2].format(t="no se"), ambiguity_group="duda")
        return entry
    for group, terms, follow in LEXICON:
        hit = find_terms(text, terms)
        if hit:
            entry.update(status="ambiguous", ambiguity_terms=hit,
                         follow_up=follow.format(t=hit[0]), ambiguity_group=group)
            return entry
    if kind in SINGLE_CHOICE:
        hit = find_terms(text, BOTH[0])
        if hit:
            entry.update(status="ambiguous", ambiguity_terms=hit, follow_up=BOTH[1],
                         ambiguity_group="ambos")
            return entry
    entry["status"] = "answered"
    return entry


def build(questions_doc, md_text, pipeline_version=None, fecha=None, prev_version=0, previous=None):
    """`previous` es el stakeholder-answers.json anterior (o None): las respuestas que
    el archivo ya no trae se heredan, y las de preguntas retiradas se conservan."""
    blocks = parse_markdown(md_text)
    prev_answers = {}
    for a in ((previous or {}).get("answers") or []) + ((previous or {}).get("retired_answers") or []):
        if isinstance(a, dict) and a.get("id"):
            prev_answers[a["id"]] = a
    answers = []
    current_ids = set()
    for q in questions_doc.get("questions", []) or []:
        qid = q.get("id")
        current_ids.add(qid)
        block = blocks.get(qid) or {}
        entry = classify(q, block)
        blank = not block.get("text") and not block.get("checked")
        prev = prev_answers.get(qid)
        if blank and prev and prev.get("status") in ("answered", "ambiguous"):
            entry = {k: v for k, v in prev.items() if k not in ("retired", "carried_from_version")}
            entry["carried_from_version"] = (previous or {}).get("version")
        answers.append(entry)
    retired = []
    for qid, a in prev_answers.items():
        if qid not in current_ids:
            r = dict(a)
            r["retired"] = True
            retired.append(r)
    counts = {k: sum(1 for a in answers if a["status"] == k)
              for k in ("answered", "unanswered", "ambiguous", "defaulted")}
    counts["blocking_open"] = sum(1 for a in answers if a["status"] == "unanswered" and a.get("blocking"))
    counts["carried"] = sum(1 for a in answers if a.get("carried_from_version") is not None)
    counts["retired"] = len(retired)
    doc = {
        "version": prev_version + 1,
        "pipeline_version": pipeline_version,
        "fecha": fecha,
        "questions_version_ref": questions_doc.get("version"),
        "summary": counts,
        "answers": answers,
    }
    if retired:
        doc["retired_answers"] = retired
    return doc


def render(doc, questions_doc):
    qmap = {q.get("id"): q for q in questions_doc.get("questions", []) or []}
    out = ["# Respuestas del stakeholder", "",
           "> Derivado de `stakeholder-answers.json` version %s — no editar a mano." % doc.get("version", "?"),
           "> Las respuestas se escriben en `stakeholder-questions.md`; este archivo lo regenera parse_answers.py.",
           ""]
    s = doc.get("summary", {})
    out.append("Contestadas: %s. Sin responder: %s (bloqueantes: %s). Ambiguas: %s. Con supuesto por defecto: %s."
               % (s.get("answered", 0), s.get("unanswered", 0), s.get("blocking_open", 0),
                  s.get("ambiguous", 0), s.get("defaulted", 0)))
    out.append("")
    for a in doc.get("answers", []):
        q = qmap.get(a["id"], {})
        out.append("## %s — %s" % (a["id"], q.get("question", "")))
        if a.get("carried_from_version") is not None:
            out.append("_Heredada de la version %s de las respuestas._" % a["carried_from_version"])
        if a["status"] == "answered":
            if a.get("choice"):
                out.append("Opcion: %s" % (a["choice"] if isinstance(a["choice"], str) else " / ".join(a["choice"])))
            if a.get("answer"):
                out.append(a["answer"])
        elif a["status"] == "defaulted":
            out.append("_Sin respuesta; se asume:_ %s" % a.get("assumed", ""))
        elif a["status"] == "unanswered":
            out.append("_Sin respuesta%s: queda como pregunta abierta._" % (" (bloqueante)" if a.get("blocking") else ""))
        elif a["status"] == "ambiguous":
            out.append("_Respuesta ambigua (%s):_ %s" % (", ".join(a.get("ambiguity_terms", [])), a.get("answer") or ""))
            out.append("")
            out.append("_Repregunta:_ %s" % a.get("follow_up", ""))
        out.append("")
    retired = doc.get("retired_answers") or []
    if retired:
        out.append("## Respuestas anteriores (preguntas que ya no estan en el cuestionario)")
        out.append("")
        for a in retired:
            txt = a.get("answer") or (a.get("choice") if isinstance(a.get("choice"), str) else None) or "(sin respuesta)"
            out.append("- **%s** (%s): %s" % (a["id"], a.get("status"), txt))
        out.append("")
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def run(folder, pipeline_version=None, fecha=None):
    folder = Path(folder)
    qjson, qmd = folder / "stakeholder-questions.json", folder / "stakeholder-questions.md"
    for p in (qjson, qmd):
        if not p.is_file():
            print("ERROR: no existe %s" % p)
            return 1
    try:
        questions_doc = json.loads(qjson.read_text(encoding="utf-8"))
        md_text = qmd.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        print("ERROR: %s" % exc)
        return 1
    prev, previous = 0, None
    ajson, amd = folder / "stakeholder-answers.json", folder / "stakeholder-answers.md"
    if ajson.is_file():
        try:
            previous = json.loads(ajson.read_text(encoding="utf-8"))
            prev = int(previous.get("version") or 0)
        except (OSError, ValueError, TypeError):
            previous, prev = None, 0
    elif amd.is_file():
        # Version anterior del pipeline: el .md lo escribia el orquestador a mano. Se
        # archiva como fuente antes de regenerarlo; el LEL ya absorbio esas respuestas.
        legado = folder / "sources" / "stakeholder-answers-manual.txt"
        legado.parent.mkdir(parents=True, exist_ok=True)
        if not legado.is_file():
            legado.write_text(amd.read_text(encoding="utf-8"), encoding="utf-8")
        print("aviso: %s era un archivo manual de una version anterior; archivado en %s" % (amd, legado))
    doc = build(questions_doc, md_text, pipeline_version, fecha, prev, previous)
    ajson.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "stakeholder-answers.md").write_text(render(doc, questions_doc), encoding="utf-8")
    s = doc["summary"]
    print("respuestas: contestadas %d, sin responder %d (bloqueantes %d), ambiguas %d, con supuesto %d"
          % (s["answered"], s["unanswered"], s["blocking_open"], s["ambiguous"], s["defaulted"]))
    if s.get("carried") or s.get("retired"):
        print("heredadas de la corrida anterior: %d; preguntas retiradas conservadas: %d" % (s.get("carried", 0), s.get("retired", 0)))
    qmap = {q.get("id"): q for q in questions_doc.get("questions", []) or []}
    for a in doc["answers"]:
        if a["status"] == "unanswered" and a.get("blocking"):
            print("falta %s (bloqueante): %s" % (a["id"], qmap.get(a["id"], {}).get("question", "")))
        elif a["status"] == "ambiguous":
            print("repreguntar %s: %s" % (a["id"], a["follow_up"]))
    print("derivado: %s y %s (version %s)" % (ajson, folder / "stakeholder-answers.md", doc["version"]))
    return 2 if (s["blocking_open"] or s["ambiguous"]) else 0


def self_test():
    qdoc = {"version": 3, "questions": [
        {"id": "QST-001", "question": "Que es un socio?", "priority": "high", "expected_answer_type": "free_text"},
        {"id": "QST-002", "question": "Hay cuotas?", "priority": "medium", "expected_answer_type": "yes_no"},
        {"id": "QST-003", "question": "Medio de pago", "priority": "medium", "expected_answer_type": "choice",
         "choices": ["efectivo", "tarjeta"]},
        {"id": "QST-004", "question": "Plazo de baja", "priority": "high", "expected_answer_type": "free_text"},
        {"id": "QST-005", "question": "Cuantos usuarios?", "priority": "medium", "source_kind": "nfr_checklist",
         "default_assumption": "menos de 100"},
        {"id": "QST-006", "question": "Quien aprueba?", "priority": "high", "expected_answer_type": "free_text"},
        {"id": "QST-007", "question": "Tope de descuento", "priority": "low", "expected_answer_type": "free_text"},
        {"id": "QST-008", "question": "Renovacion automatica?", "priority": "medium", "expected_answer_type": "yes_no"},
    ]}
    md = "\n".join([
        "# Cuestionario", "", "## SEC-001 — Dominio", "",
        "### QST-001 **[bloqueante]** — Que es un socio?", "", "**Respuesta QST-001:**", "",
        "Una persona con cuota al dia.", "",
        "### QST-002 — Hay cuotas?", "", "**Respuesta QST-002:**", "", "- [x] Si", "- [ ] No", "",
        "### QST-003 — Medio de pago", "", "**Respuesta QST-003:**", "", "- [x] efectivo", "- [x] tarjeta", "",
        "### QST-004 **[bloqueante]** — Plazo de baja", "", "**Respuesta QST-004:**", "",
        "DEPENDE del tipo de socio, más o menos 30 días.", "",
        "## SEC-002 — No funcionales", "",
        "### QST-005 — Cuantos usuarios?", "", "> Si no respondes, asumimos: menos de 100", "",
        "**Respuesta QST-005:**", "", PLACEHOLDER, "",
        "### QST-006 **[bloqueante]** — Quien aprueba?", "", "**Respuesta QST-006:**", "", PLACEHOLDER, "",
        "### QST-007 — Tope de descuento", "", "**Respuesta:**", "", "Según el convenio vigente.", "",
        "### QST-008 — Renovacion automatica?", "", "**Respuesta QST-008:**", "", "- [ ] Si", "- [ ] No", "",
        "Ambas, depende del plan.", "",
    ])
    doc = build(qdoc, md, "2.9.0", "2026-10-07", prev_version=1)
    a = {x["id"]: x for x in doc["answers"]}
    checks = [
        (a["QST-001"]["status"] == "answered" and a["QST-001"]["answer"] == "Una persona con cuota al dia.", "texto libre contestado"),
        (a["QST-002"]["status"] == "answered" and a["QST-002"]["choice"] == "Si", "casilla unica"),
        (a["QST-003"]["status"] == "ambiguous" and "dos casillas marcadas" in a["QST-003"]["ambiguity_terms"], "dos casillas en opcion unica"),
        (a["QST-004"]["status"] == "ambiguous" and a["QST-004"]["ambiguity_terms"] == ["depende"], "lexico con mayusculas y tildes"),
        ("de que depende" in a["QST-004"]["follow_up"], "repregunta redactada"),
        (a["QST-005"]["status"] == "defaulted" and a["QST-005"]["assumed"] == "menos de 100", "sin respuesta con default"),
        (a["QST-006"]["status"] == "unanswered" and a["QST-006"]["blocking"] is True, "bloqueante sin responder"),
        (a["QST-007"]["status"] == "ambiguous" and a["QST-007"]["ambiguity_terms"] == ["segun"], "linea de respuesta sin id (formato viejo) y tilde"),
        (a["QST-008"]["status"] == "ambiguous", "texto 'ambas' en pregunta de opcion unica"),
        ({k: doc["summary"][k] for k in ("answered", "unanswered", "ambiguous", "defaulted", "blocking_open")}
         == {"answered": 2, "unanswered": 1, "ambiguous": 4, "defaulted": 1, "blocking_open": 1}, "resumen"),
        (doc["version"] == 2 and doc["questions_version_ref"] == 3, "version y referencia"),
        ("## QST-006 — Quien aprueba?" in render(doc, qdoc) and "queda como pregunta abierta" in render(doc, qdoc), "render del md"),
        (build(qdoc, "# vacio\n", None, None)["summary"]["answered"] == 0, "md sin bloques: nada contestado"),
        (not es_no_se_duda("No se puede reservar dos turnos el mismo dia.") and not es_no_se_duda("no se cobra penalidad"), "'no se puede' es regla, no duda (H-04)"),
        (es_no_se_duda("No sé, preguntale a Ana") and es_no_se_duda("no se.") and es_no_se_duda("La verdad no se") and es_no_se_duda("no se si conviene"), "'no sé' / 'no se.' / 'no se si' son duda"),
    ]
    failures = 0
    for cond, label in checks:
        print("self-test %s: %s" % ("ok" if cond else "FALLO", label))
        failures += 0 if cond else 1
    # Corrida siguiente: cuestionario re-renderizado en blanco, con una pregunta menos
    # y una nueva. Lo contestado se hereda; lo retirado se conserva.
    qdoc2 = {"version": 4, "questions": [q for q in qdoc["questions"] if q["id"] != "QST-002"]
             + [{"id": "QST-009", "question": "Nueva?", "priority": "low", "expected_answer_type": "free_text"}]}
    md2 = "\n".join(["# Cuestionario", ""] + sum(([
        "### %s — x" % q["id"], "", "**Respuesta %s:**" % q["id"], "", PLACEHOLDER, ""]
        for q in qdoc2["questions"]), []))
    doc2 = build(qdoc2, md2, None, None, prev_version=doc["version"], previous=doc)
    b = {x["id"]: x for x in doc2["answers"]}
    checks = [
        (b["QST-001"]["status"] == "answered" and b["QST-001"]["carried_from_version"] == 2, "respuesta heredada"),
        (b["QST-004"]["status"] == "ambiguous", "ambigua heredada sigue ambigua (se repregunta)"),
        (b["QST-006"]["status"] == "unanswered" and "carried_from_version" not in b["QST-006"], "sin responder no se hereda"),
        (b["QST-009"]["status"] == "unanswered", "pregunta nueva en blanco"),
        ([r["id"] for r in doc2["retired_answers"]] == ["QST-002"] and doc2["retired_answers"][0]["retired"] is True, "pregunta retirada conservada"),
        (doc2["summary"]["carried"] == 5 and doc2["summary"]["retired"] == 1, "conteos de heredadas y retiradas"),
        ("Respuestas anteriores" in render(doc2, qdoc2) and "Heredada de la version 2" in render(doc2, qdoc2), "render de heredadas y retiradas"),
    ]
    import shutil
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="answers-"))
    try:
        (tmp / "stakeholder-questions.json").write_text(json.dumps(qdoc), encoding="utf-8")
        (tmp / "stakeholder-questions.md").write_text(md, encoding="utf-8")
        (tmp / "stakeholder-answers.md").write_text("# Respuestas\n\nQST-001: lo que dijo el cliente\n", encoding="utf-8")
        code = run(tmp)
        legado = tmp / "sources" / "stakeholder-answers-manual.txt"
        checks += [
            (legado.is_file() and "lo que dijo el cliente" in legado.read_text(encoding="utf-8"), "md manual heredado archivado en sources/"),
            ((tmp / "stakeholder-answers.json").is_file() and code == 2, "regenerado (exit 2 por bloqueante y ambiguas)"),
        ]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for cond, label in checks:
        print("self-test %s: %s" % ("ok" if cond else "FALLO", label))
        failures += 0 if cond else 1
    print("SELF-TEST: %d fallo(s)" % failures)
    return 1 if failures else 0


def main(argv):
    if "--self-test" in argv:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("carpeta", nargs="?", default=".dev/requirements")
    ap.add_argument("--pipeline-version", default=None)
    ap.add_argument("--fecha", default=None)
    args = ap.parse_args(argv)
    return run(args.carpeta, args.pipeline_version, args.fecha)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
