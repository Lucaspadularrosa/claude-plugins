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
    ("duda", ["no se", "ni idea", "creo que", "supongo", "me parece", "quizas", "quiza",
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
    blocking = question.get("priority") == "high"
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


def build(questions_doc, md_text, pipeline_version=None, fecha=None, prev_version=0):
    blocks = parse_markdown(md_text)
    answers = [classify(q, blocks.get(q.get("id"))) for q in questions_doc.get("questions", []) or []]
    counts = {k: sum(1 for a in answers if a["status"] == k)
              for k in ("answered", "unanswered", "ambiguous", "defaulted")}
    counts["blocking_open"] = sum(1 for a in answers if a["status"] == "unanswered" and a.get("blocking"))
    return {
        "version": prev_version + 1,
        "pipeline_version": pipeline_version,
        "fecha": fecha,
        "questions_version_ref": questions_doc.get("version"),
        "summary": counts,
        "answers": answers,
    }


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
    prev = 0
    ajson = folder / "stakeholder-answers.json"
    if ajson.is_file():
        try:
            prev = int(json.loads(ajson.read_text(encoding="utf-8")).get("version") or 0)
        except (OSError, ValueError, TypeError):
            prev = 0
    doc = build(questions_doc, md_text, pipeline_version, fecha, prev)
    ajson.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "stakeholder-answers.md").write_text(render(doc, questions_doc), encoding="utf-8")
    s = doc["summary"]
    print("respuestas: contestadas %d, sin responder %d (bloqueantes %d), ambiguas %d, con supuesto %d"
          % (s["answered"], s["unanswered"], s["blocking_open"], s["ambiguous"], s["defaulted"]))
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
        (doc["summary"] == {"answered": 2, "unanswered": 1, "ambiguous": 4, "defaulted": 1, "blocking_open": 1}, "resumen"),
        (doc["version"] == 2 and doc["questions_version_ref"] == 3, "version y referencia"),
        ("## QST-006 — Quien aprueba?" in render(doc, qdoc) and "queda como pregunta abierta" in render(doc, qdoc), "render del md"),
        (build(qdoc, "# vacio\n", None, None)["summary"]["answered"] == 0, "md sin bloques: nada contestado"),
    ]
    failures = 0
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
