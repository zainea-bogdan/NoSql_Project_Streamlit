import streamlit as st

import api

ORDER = ["teams", "players", "matches", "events"]

st.title("Ingest Wyscout JSON")
st.info("Recommended order: teams -> players -> matches -> events. "
        "Accepted shapes: one object, a list of objects, or a wrapper like {\"events\": [...]}.")

# a new key after each insert gives fresh, empty upload zones
nonce = st.session_state.setdefault("upload_nonce", 0)

done = st.session_state.pop("ingest_done", None)
if done:
    summary = ", ".join(f"{r['inserted']} {r['entity']}" for r in done)
    problems = sum(r["rejected"] for r in done) + sum(len(r["errors"]) for r in done)
    if problems:
        st.warning(f"Insert finished with problems. Inserted: {summary}. See the errors below.")
    else:
        st.success(f"Insert complete. Inserted: {summary}.")
    st.toast("Insert complete")
error = st.session_state.pop("ingest_error", None)
if error:
    st.error(f"Insert stopped: {error}")

grid = [st.columns(2), st.columns(2)]
for i, entity in enumerate(ORDER):
    with grid[i // 2][i % 2]:
        st.file_uploader(entity.capitalize(), type=["json"], accept_multiple_files=True,
                         key=f"upload_{entity}_{nonce}")


def selected_files() -> dict[str, list[tuple[str, bytes]]]:
    out = {}
    for entity in ORDER:
        files = st.session_state.get(f"upload_{entity}_{nonce}") or []
        if files:
            out[entity] = [(f.name, f.getvalue()) for f in files]
    return out


def signature(files: dict) -> tuple:
    return tuple((e, name, len(data)) for e, items in files.items() for name, data in items)


def show_report(rep: dict) -> None:
    with st.container(border=True):
        mode = "dry run" if rep["dry_run"] else "insert"
        st.markdown(f"**{rep['entity']}** ({mode}, {len(rep['files'])} file(s))")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Accepted", rep["accepted"])
        c2.metric("Skipped", rep["skipped"])
        c3.metric("Rejected", rep["rejected"])
        c4.metric("Inserted", rep["inserted"])
        if rep["errors"]:
            with st.expander(f"Errors ({len(rep['errors'])})"):
                for msg in rep["errors"]:
                    st.write(f"- {msg}")
        if rep["warnings"]:
            with st.expander(f"Warnings ({len(rep['warnings'])})"):
                for msg in rep["warnings"]:
                    st.write(f"- {msg}")


files = selected_files()
col_validate, col_insert = st.columns(2)

if col_validate.button("Validate (dry run)", disabled=not files):
    reports = []
    try:
        for entity, items in files.items():
            reports.append(api.ingest(entity, items, dry_run=True))
        st.session_state["ingest_reports"] = reports
        st.session_state["ingest_signature"] = signature(files)
    except api.ApiError as exc:
        st.error(str(exc))

validated = bool(files) and st.session_state.get("ingest_signature") == signature(files)
if col_insert.button("Insert", type="primary", disabled=not validated,
                     help="Enabled after validating the currently selected files."):
    reports = []
    try:
        for entity in ORDER:  # inserted in the recommended order
            if entity in files:
                reports.append(api.ingest(entity, files[entity], dry_run=False))
    except api.ApiError as exc:
        st.session_state["ingest_error"] = str(exc)  # shown after the rerun
    st.session_state["ingest_reports"] = reports
    st.session_state.pop("ingest_signature", None)  # validate again before another insert
    if reports:
        st.session_state["ingest_done"] = reports  # confirmation shown after the rerun
        st.session_state["upload_nonce"] = nonce + 1  # clears the upload zones
    st.cache_data.clear()  # refresh the counts in the sidebar
    st.rerun()

for report in st.session_state.get("ingest_reports", []):
    show_report(report)
